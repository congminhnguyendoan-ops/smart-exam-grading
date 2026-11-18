import csv
import ctypes
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent.parent
RA = ROOT / "data" / "_eval" / "so_sanh_ocr"
MO_HINH = RA / "mo_hinh" / "PP-OCRv6_rec_small.onnx"
SHA_MO_HINH = "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884"
CAO, RONG = 48, 320
LE_GOC = 0.15


def ws_mb() -> float:
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t)] + [(f"f{i}", ctypes.c_size_t) for i in range(6)]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    assert k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2 ** 20


def resize_song_tuyen(a: np.ndarray, h: int, w: int) -> np.ndarray:
    a = a.astype(np.float32)
    H, W = a.shape
    ys = np.clip((np.arange(h) + 0.5) * H / h - 0.5, 0, H - 1)
    xs = np.clip((np.arange(w) + 0.5) * W / w - 0.5, 0, W - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, H - 1), np.minimum(x0 + 1, W - 1)
    wy, wx = (ys - y0)[:, None], (xs - x0)[None, :]
    top = a[y0][:, x0] * (1 - wx) + a[y0][:, x1] * wx
    bot = a[y1][:, x0] * (1 - wx) + a[y1][:, x1] * wx
    return top * (1 - wy) + bot * wy


def chuan_bi(o_muc: np.ndarray, le: float) -> np.ndarray:
    g = 255.0 - o_muc.astype(np.float32)
    if le > 0:
        p = int(round(le * g.shape[0]))
        g = np.pad(g, p, constant_values=255.0)
    h, w = g.shape
    nw = min(RONG, max(1, int(np.ceil(CAO * w / h))))
    r = resize_song_tuyen(g, CAO, nw) / 255.0
    t = np.zeros((3, CAO, RONG), np.float32)
    t[:, :, :nw] = (r - 0.5) / 0.5
    return t


class NhanDang:
    def __init__(self):
        b = MO_HINH.read_bytes()
        assert hashlib.sha256(b).hexdigest() == SHA_MO_HINH, "mô hình ONNX khác bản đã ghi"
        so = ort.SessionOptions()
        so.log_severity_level = 3
        self.s = ort.InferenceSession(b, so, providers=["CPUExecutionProvider"])
        ky_tu = self.s.get_modelmeta().custom_metadata_map["character"].splitlines()
        self.vocab = ["<blank>"] + ky_tu + [" "]
        self.chi_so = [self.vocab.index(str(d)) for d in range(10)]
        self.ten_vao = self.s.get_inputs()[0].name

    def chay(self, x: np.ndarray) -> np.ndarray:
        p = self.s.run(None, {self.ten_vao: x})[0]
        assert p.shape[2] == len(self.vocab), (p.shape, len(self.vocab))
        return p

    def giai_ma(self, p: np.ndarray):
        loc = []
        for q in p:
            a = q.argmax(1)
            giu = [t for t in range(len(a)) if a[t] != 0 and (t == 0 or a[t] != a[t - 1])]
            s = "".join(self.vocab[a[t]] for t in giu)
            so = [(self.vocab[a[t]], float(q[t, a[t]])) for t in giu if self.vocab[a[t]].isdigit()]
            loc.append((so[0][0], so[0][1], s) if len(so) == 1 else ("", 0.0, s))
        return loc, p[:, :, self.chi_so].max(axis=1)


def o_goc(npz, tap: str) -> list[np.ndarray]:
    hw, flat = npz[f"{tap}_goc_hw"], npz[f"{tap}_goc"]
    out, k = [], 0
    for h, w in hw:
        out.append(flat[k:k + h * w].reshape(h, w))
        k += h * w
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    z = np.load(RA / "o_chu_so.npz")
    w0 = ws_mb()
    t0 = time.perf_counter()
    nd = NhanDang()
    t_nap = (time.perf_counter() - t0) * 1000
    w1 = ws_mb()
    vao = {tap: {"x28": [(o, 0.0) for o in z[f"{tap}_x28"]], "goc": [(o, LE_GOC) for o in o_goc(z, tap)]} for tap in ("P", "D")}
    cp = {"mo_hinh": "PP-OCRv6_rec_small.onnx (rapidocr 3.10.0)", "sha256": SHA_MO_HINH, "tep_mb": round(MO_HINH.stat().st_size / 2 ** 20, 2),
          "onnxruntime": ort.__version__, "numpy": np.__version__, "nap_ms": round(t_nap, 1), "ws_truoc_nap_mb_da_import_ort": round(w0, 1), "ram_tang_khi_nap_mb": round(w1 - w0, 1),
          "so_ky_tu_vocab": len(nd.vocab), "tham_so_uoc_tinh": f"~{MO_HINH.stat().st_size / 4 / 1e6:.1f} triệu (tệp / 4 byte float32)"}
    for bien in ("x28", "goc"):
        q_all = {}
        for tap in ("P", "D"):
            X = np.stack([chuan_bi(o, le) for o, le in vao[tap][bien]])
            loc, ep = [], []
            for i in range(0, len(X), 64):
                a, b = nd.giai_ma(nd.chay(X[i:i + 64]))
                loc += a
                ep.append(b)
            ep = np.concatenate(ep)
            q_all[tap] = ep
            with (RA / f"du_doan_ocr_{bien}_loc.csv").open("a" if tap == "D" else "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                if tap == "P":
                    w.writerow(["tap", "i", "chu_so", "tin_cay", "chuoi_tu_do"])
                w.writerows([tap, i, c, f"{t:.4f}", s] for i, (c, t, s) in enumerate(loc))
            with (RA / f"du_doan_ocr_{bien}_ep.csv").open("a" if tap == "D" else "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                if tap == "P":
                    w.writerow(["tap", "i", "chu_so", "tin_cay"])
                w.writerows([tap, i, int(q.argmax()), f"{q.max():.4f}"] for i, q in enumerate(ep))
            print(f"  {bien} {tap}: {len(X)} ô")
        np.savez_compressed(RA / f"q_ocr_{bien}.npz", P=q_all["P"], D=q_all["D"])
        del X
    goc = vao["P"]["goc"]
    for i in range(10):
        nd.giai_ma(nd.chay(chuan_bi(*goc[i])[None]))
    t1, t9 = [], []
    for i in range(300):
        a = time.perf_counter(); nd.giai_ma(nd.chay(chuan_bi(*goc[i % len(goc)])[None])); t1.append((time.perf_counter() - a) * 1000)
    for i in range(100):
        j = (9 * i) % (len(goc) - 9)
        a = time.perf_counter(); nd.giai_ma(nd.chay(np.stack([chuan_bi(*g) for g in goc[j:j + 9]]))); t9.append((time.perf_counter() - a) * 1000)
    pc = lambda a, q: round(float(np.percentile(a, q)), 2)  # noqa: E731
    cp["ms_1_chu_so"] = {"p50": pc(t1, 50), "p95": pc(t1, 95), "n": len(t1)}
    cp["ms_9_chu_so_mot_lo"] = {"p50": pc(t9, 50), "p95": pc(t9, 95), "n": len(t9)}
    cp["ws_sau_nap_mb"] = round(w1, 1)
    cp["ws_sau_do_thoi_gian_mb"] = round(ws_mb(), 1)
    cp["luong_onnxruntime"] = "mặc định (nhiều luồng nội bộ)"
    (RA / "ocr_chi_phi.json").write_text(json.dumps(cp, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(cp, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
