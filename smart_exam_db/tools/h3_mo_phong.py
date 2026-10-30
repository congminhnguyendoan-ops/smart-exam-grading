"""
h3_mo_phong.py - Lệnh T (30/10/2026): tạo ảnh MÔ PHỎNG "ô tô trống, chữ viết tay có" cho tiêu chí H3 (đợt 2 không xảy ra trên giấy).

  python tools/h3_mo_phong.py dien-tap        # DIỄN TẬP trên 2 ảnh dev (0001_C1, 0002_C2) -> data/_eval/h3/dien_tap/ + data/_eval/h3/mau_truoc_sau.png
  (ảnh đợt 2 CHỈ được tạo bên trong lượt chạy chính thức: tools/eval_h3_mo_phong.py run --xac-nhan-h3, sau đăng ký + tag)

Cách làm (tất định – chạy lại ra cùng ảnh, cùng SHA):
1. Đọc ảnh bằng cv_engine.preprocessing.doc_anh (đúng mảng xám hệ thống dùng, đã áp EXIF) -> preprocess_anh -> 4 tâm marker CUỐI (đã xử lý lật 180°).
   Phép nắn của hệ thống là MỘT getPerspectiveTransform(marker -> tâm marker layout) nên nghịch đảo chính xác: sửa TRỰC TIẾP trên ảnh gốc.
2. Chọn (hạt giống 2026, lần lượt theo tên ảnh đã sắp xếp) MỘT trường rồi MỘT cột có đúng một ô tô: nhãn có chữ số; với đợt 2 thêm điều kiện
   bubble đợt 2 đọc đúng chữ số đó và không bị 'bubble_cx' (loại cột vốn trống như 0107 cột 3). Tuỳ chọn chi_truong_nhan: chỉ chọn trường
   mà đợt 2 đã NHẬN (để "cần xem" quy được cho việc xoá ô); không trường nào như vậy thì chọn trong mọi trường và đánh dấu.
3. Định vị ô thật trên ảnh nắn: khớp mẫu phiếu trắng (phieu_trang_300dpi.png) cho cả khối bubble của trường (±30 px), rồi tinh chỉnh từng ô
   trống ±8 px; tâm ô bị tô = vị trí layout + dịch của khối + dịch tinh chỉnh trung bình của các ô trống cùng cột.
4. Ô NGUỒN (trống) – hai biến thể: 'cot' = cùng cột, cách 2 hàng (hàng kề quá sát vết tô); 'hang' = cùng hàng (CÙNG chữ số in sẵn), cột kề.
5. Chép: mỗi điểm ảnh gốc trong vùng sửa -> toạ độ nắn a -> a + (tâm nguồn - tâm đích) -> ngược về ảnh gốc -> lấy mẫu song tuyến ảnh gốc.
   Trọng số 1 trong bán kính R+6 px (@300 DPI), giảm tuyến tính về 0 ở R+12 (viền khe giữa hai ô ≥ 16 px). Không chỉnh độ sáng: giữ ánh sáng và
   nhiễu tự nhiên của chính ảnh. Chữ viết tay (ô phía trên khối bubble) không bị chạm.
6. Lưu PNG KHÔNG MẤT MÁT của mảng xám đã sửa (không EXIF – chiều đã áp sẵn). Lý do không lưu JPEG: nén lại đổi MỌI điểm ảnh, phép đối chứng
   T3 (trường không sửa phải giống đợt 2) sẽ lẫn tác động nén với tác động sửa.
"""
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cv_engine.preprocessing import GOC, doc_anh, nap_layout, preprocess_anh  # noqa: E402  (CHỈ dùng, không sửa)

HAT_GIONG = 2026
DATA = ROOT / "data"
RAW_DEV, RAW_DOT2 = DATA / "raw", DATA / "raw_dot2"
OUT_DOT2 = DATA / "h3_mo_phong"
OUT_EVAL = DATA / "_eval" / "h3"
DIEN_TAP = OUT_EVAL / "dien_tap"
KQ_DOT2 = DATA / "_eval" / "dot2" / "that" / "ket_qua.json"
SHA_ANH_DOT2 = ROOT / "docs" / "sha_anh_dot2.txt"
MAU_PNG = ROOT / "answer_sheet" / "output" / "phieu_trang_300dpi.png"
ANH_DIEN_TAP = ["0001_C1", "0002_C2"]
TRUONG = {"sbd": ("sbd_bubble", 6), "exam_code": ("ma_de_bubble", 3)}
R_TRONG, R_NGOAI = 6, 12          # vùng sửa: R+6 trọng số 1, giảm về 0 ở R+12 (px @300 DPI)
TIM_KHOI, TIM_O = 30, 8           # bán kính dò dịch: cả khối bubble / từng ô


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def kiem_sha_dot2() -> dict:
    """{tên tệp: SHA} theo docs/sha_anh_dot2.txt; DỪNG nếu ảnh nào thiếu / khác SHA / khác dung lượng."""
    ds = {}
    for d in SHA_ANH_DOT2.read_text(encoding="utf-8").splitlines():
        if d.strip() and not d.startswith("#"):
            h, n, ten = d.split()
            ds[ten] = (h.upper(), int(n))
    sai = [t for t, (h, n) in ds.items() if not (RAW_DOT2 / t).is_file() or (RAW_DOT2 / t).stat().st_size != n or sha256(RAW_DOT2 / t) != h]
    if len(ds) != 20 or sai:
        raise SystemExit(f"DỪNG: ảnh đợt 2 không khớp {SHA_ANH_DOT2.name}: {len(ds)} dòng, sai {sai}")
    return {t: h for t, (h, _) in ds.items()}


# ------------------------------------------------------------------------------------------------ chọn trường / cột / ô nguồn
def cot_hop_le(t: dict, ref: dict | None) -> dict:
    """{truong: [cột i (0-based) có đúng một ô tô]}. ref = dòng ảnh trong kết quả đợt 2 (None ở diễn tập dev: chỉ theo nhãn)."""
    out = {}
    for truong, (khoa, n) in TRUONG.items():
        ds = []
        for i in range(n):
            d = t[khoa][i]
            if d == "-":
                continue
            if ref is not None:
                c = next(c for c in ref["cot"] if c["truong"] == truong and c["i"] == i)
                if c["bubble"] != d or "bubble_cx" in c["ly_do"]:
                    continue
            ds.append(i)
        if ds:
            out[truong] = ds
    return out


def chon(ds_anh: list[str], nhan: dict, ref: dict | None, chi_truong_nhan: bool) -> dict:
    """Hạt giống 2026, lần lượt theo tên ảnh đã sắp xếp: {ảnh: (trường, cột, chữ số, trường_da_can_xem_san)}."""
    rng = random.Random(HAT_GIONG)
    out = {}
    for ten in sorted(ds_anh):
        t = nhan[ten.split("_")[0]]
        r = ref.get(ten) if ref is not None else None
        hl = cot_hop_le(t, r)
        san = False
        if chi_truong_nhan and r is not None:
            nhan_dc = {k: v for k, v in hl.items() if not r["sbd_can_xem" if k == "sbd" else "ma_can_xem"]}
            san = not nhan_dc
            hl = nhan_dc or hl
        truong = rng.choice(sorted(hl))
        i = rng.choice(hl[truong])
        out[ten] = (truong, i, int(t[TRUONG[truong][0]][i]), san)
    return out


def o_nguon(t: dict, truong: str, i: int, d: int, bien_the: str, ref: dict | None) -> tuple[int, int]:
    """(cột, hàng) của ô TRỐNG dùng làm nguồn. 'cot': cùng cột, hàng d∓2 (ưu tiên phía trên); 'hang': cùng hàng d, cột gần nhất (ưu tiên bên trái)
    mà ô (cột, d) trống theo nhãn (và theo bubble đợt 2 nếu có)."""
    khoa, n = TRUONG[truong]
    if bien_the == "cot":
        for h in (d - 2, d + 2, d - 3, d + 3):
            if 0 <= h <= 9:
                return i, h
    for k in range(1, n):
        for j in (i - k, i + k):
            if 0 <= j < n and t[khoa][j] != str(d):
                if ref is not None and next(c for c in ref["cot"] if c["truong"] == truong and c["i"] == j)["bubble"] == str(d):
                    continue
                return j, d
    raise SystemExit(f"DỪNG: không có ô nguồn trống ({truong} cột {i + 1}, chữ số {d}, {bien_the}).")


# ------------------------------------------------------------------------------------------------ định vị ô trên ảnh nắn
def _khop(anh: np.ndarray, mau: np.ndarray, x0: int, y0: int, x1: int, y1: int, r: int, ox: int = 0, oy: int = 0) -> tuple[float, float, float]:
    """Dịch (dx, dy) tốt nhất của mẫu[y0:y1, x0:x1] trên ảnh, dò quanh độ lệch (ox, oy) trong ±r px (khớp chuẩn hoá) + điểm khớp."""
    m = mau[y0:y1, x0:x1].astype(np.float32)
    v = anh[y0 + oy - r:y1 + oy + r, x0 + ox - r:x1 + ox + r].astype(np.float32)
    s = cv2.matchTemplate(v, m, cv2.TM_CCOEFF_NORMED)
    _, best, _, (bx, by) = cv2.minMaxLoc(s)
    return float(bx - r + ox), float(by - r + oy), float(best)


def dinh_vi(anh_nan: np.ndarray, mau: np.ndarray, L: dict, truong: str, cot_can: set[int], d_to: dict[int, int]) -> dict:
    """{(cột, hàng): (x, y)} tâm ô thật trên ảnh nắn cho các cột cần. d_to[cột] = hàng đang tô (ô đó lấy dịch trung bình các ô trống cùng cột)."""
    f = L[truong]
    R = f["bubble_radius"]
    tam = np.array(f["bubbles"], dtype=np.float64)            # [cột][hàng] -> (x, y)
    p = int(R + 10)
    x0, y0 = int(tam[..., 0].min()) - p, int(tam[..., 1].min()) - p
    x1, y1 = int(tam[..., 0].max()) + p, int(tam[..., 1].max()) + p
    dx, dy, diem_khoi = _khop(anh_nan, mau, x0, y0, x1, y1, TIM_KHOI)
    out = {"_khoi": (dx, dy, diem_khoi)}
    for j in sorted(cot_can):
        trong = []
        for h in range(10):
            if d_to.get(j) == h:
                continue
            x, y = int(tam[j, h, 0]), int(tam[j, h, 1])
            ox, oy, _ = _khop(anh_nan, mau, x - p, y - p, x + p, y + p, TIM_O, int(dx), int(dy))
            ex, ey = ox - dx, oy - dy                                      # phần dịch riêng của ô so với cả khối
            out[(j, h)] = tuple(tam[j, h] + (dx + ex, dy + ey))
            trong.append((h, ex, ey))
        if j in d_to:
            h0 = d_to[j]
            gan = sorted(trong, key=lambda z: abs(z[0] - h0))[:2]           # hai ô trống gần nhất cùng cột
            ex, ey = np.mean([z[1] for z in gan]), np.mean([z[2] for z in gan])
            out[(j, h0)] = tuple(tam[j, h0] + (dx + ex, dy + ey))
    return out


# ------------------------------------------------------------------------------------------------ chép điểm ảnh trên ảnh gốc
def _ma_tran(marker: np.ndarray, L: dict) -> np.ndarray:
    m = L["markers"]["centers"]
    return cv2.getPerspectiveTransform(np.float32(marker), np.float32([m[g] for g in GOC])).astype(np.float64)


def _bien(M: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(pts.reshape(-1, 1, 2).astype(np.float64), M).reshape(-1, 2)


def chep_o(gray: np.ndarray, M: np.ndarray, dich: tuple, nguon: tuple, R: float) -> tuple[np.ndarray, list[int]]:
    """Ảnh gốc mới (uint8) + vùng sửa (x0, y0, x1, y1) trên ảnh gốc. dich / nguon: tâm ô trên ảnh NẮN."""
    Mi = np.linalg.inv(M)
    rn = R + R_NGOAI
    goc = _bien(Mi, np.array([[dich[0] + sx * rn, dich[1] + sy * rn] for sx in (-1, 1) for sy in (-1, 1)]))
    x0, y0 = np.floor(goc.min(0)).astype(int) - 2
    x1, y1 = np.ceil(goc.max(0)).astype(int) + 3
    xs, ys = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    p = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float64)
    a = _bien(M, p)
    kc = np.hypot(a[:, 0] - dich[0], a[:, 1] - dich[1])
    w = np.clip((rn - kc) / (R_NGOAI - R_TRONG), 0, 1).reshape(xs.shape)
    q = _bien(Mi, a + (nguon[0] - dich[0], nguon[1] - dich[1]))
    mx, my = q[:, 0].reshape(xs.shape).astype(np.float32), q[:, 1].reshape(xs.shape).astype(np.float32)
    mau = cv2.remap(gray.astype(np.float32), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    out = gray.copy()
    vung = out[y0:y1, x0:x1].astype(np.float32)
    out[y0:y1, x0:x1] = np.clip(np.rint(w * mau + (1 - w) * vung), 0, 255).astype(np.uint8)
    return out, [int(x0), int(y0), int(x1), int(y1)]


def do_toi(anh_nan: np.ndarray, c: tuple, R: float) -> float:
    """Độ tối trung bình (0 trắng – 1 đen) trong hình tròn bán kính 0,7R quanh tâm (phần ruột ô, không lấy viền in)."""
    y, x = np.ogrid[:anh_nan.shape[0], :anh_nan.shape[1]]
    m = (x - c[0]) ** 2 + (y - c[1]) ** 2 <= (0.7 * R) ** 2
    return float(1 - anh_nan[m].mean() / 255)


# ------------------------------------------------------------------------------------------------ một ảnh
def sua_anh(duong_dan: Path, t: dict, truong: str, i: int, d: int, bien_the: str, ref: dict | None, L: dict, mau: np.ndarray) -> dict:
    gray, exif = doc_anh(duong_dan)
    kq = preprocess_anh(gray, L, exif)
    if not kq.ok:
        return {"tu_choi_khi_tao": kq.ly_do}
    M = _ma_tran(kq.marker, L)
    j, h = o_nguon(t, truong, i, d, bien_the, ref)
    vt = dinh_vi(kq.anh_nan, mau, L, truong, {i, j}, {i: d})
    R = L[truong]["bubble_radius"]
    moi, vung = chep_o(gray, M, vt[(i, d)], vt[(j, h)], R)
    nan_moi = cv2.warpPerspective(moi, M, tuple(L["page_px"]))
    trong_cot = [do_toi(kq.anh_nan, vt[(i, k)], R) for k in range(10) if k != d]
    return {"gray": moi, "gray_goc": gray, "nan_goc": kq.anh_nan, "nan_moi": nan_moi, "M": M, "exif": exif, "o_nguon": [j + 1, h],
            "tam_dich_nan": [round(v, 1) for v in vt[(i, d)]], "tam_nguon_nan": [round(v, 1) for v in vt[(j, h)]],
            "dich_khoi": [round(v, 2) for v in vt["_khoi"]], "vung_sua_goc": vung,
            "do_toi_truoc": round(do_toi(kq.anh_nan, vt[(i, d)], R), 3), "do_toi_sau": round(do_toi(nan_moi, vt[(i, d)], R), 3),
            "do_toi_o_trong_cot_trung_vi": round(float(np.median(trong_cot)), 3)}


def ghi_png(anh: np.ndarray, p: Path) -> str:
    p.parent.mkdir(parents=True, exist_ok=True)
    ok, b = cv2.imencode(".png", anh, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    assert ok
    b.tofile(p)
    assert np.array_equal(cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_GRAYSCALE), anh)      # không mất mát
    return sha256(p)


def tao(ds_anh: list[str], thu_muc_goc: Path, nhan: dict, ref: dict | None, bien_the: str, chi_truong_nhan: bool, out: Path) -> list[dict]:
    """Tạo ảnh chỉnh + bảng (bang.csv, bang.json) trong `out`. Trả các dòng bảng (không có mảng ảnh)."""
    L, mau = nap_layout("phieu"), cv2.imdecode(np.fromfile(MAU_PNG, np.uint8), cv2.IMREAD_GRAYSCALE)
    ch = chon(ds_anh, nhan, ref, chi_truong_nhan)
    bang = []
    for ten in sorted(ds_anh):
        truong, i, d, san = ch[ten]
        tep = next(p for p in thu_muc_goc.iterdir() if p.stem == ten)
        r = sua_anh(tep, nhan[ten.split("_")[0]], truong, i, d, bien_the, ref.get(ten) if ref else None, L, mau)
        dong = {"anh": ten, "anh_goc": tep.name, "sha_goc": sha256(tep), "truong": truong, "cot": i + 1, "chu_so_xoa": d, "bien_the": bien_the,
                "truong_da_can_xem_o_dot2": san}
        if "tu_choi_khi_tao" in r:
            dong["ghi_chu"] = f"ảnh gốc bị từ chối khi nắn ({r['tu_choi_khi_tao']}) – không tạo ảnh chỉnh"
        else:
            dong["sha_anh_chinh"] = ghi_png(r["gray"], out / f"{ten}.png")
            dong.update({k: r[k] for k in ("o_nguon", "tam_dich_nan", "tam_nguon_nan", "dich_khoi", "vung_sua_goc", "do_toi_truoc", "do_toi_sau",
                                            "do_toi_o_trong_cot_trung_vi", "exif")})
            dong["so_diem_anh_doi"] = int((r["gray"] != r["gray_goc"]).sum())
        bang.append(dong)
    (out / "bang.json").write_text(json.dumps(bang, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out / "bang.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for d in bang for k in d)))
        w.writeheader()
        w.writerows(bang)
    return bang


# ------------------------------------------------------------------------------------------------ diễn tập (dev)
def _cat(anh: np.ndarray, M: np.ndarray, c_nan: tuple, nua: float) -> np.ndarray:
    """Cắt vùng quanh tâm (toạ độ nắn) trên ẢNH GỐC (đúng điểm ảnh đã sửa), phóng ×3."""
    x, y = _bien(np.linalg.inv(M), np.array([c_nan]))[0]
    n = int(nua)
    v = anh[int(y) - n:int(y) + n, int(x) - n:int(x) + n]
    return cv2.resize(v, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)


def _nhan_chu(anh: np.ndarray, chu: str) -> np.ndarray:
    k = np.full((34, anh.shape[1]), 255, np.uint8)
    cv2.putText(k, chu, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2, cv2.LINE_AA)
    return np.vstack([k, anh])


def dien_tap() -> None:
    import eval_he_thong as H
    from cv_engine.tap_du_lieu import PHIEU_TRAIN
    nhan = H.doc_nhan(PHIEU_TRAIN)
    L, mau = nap_layout("phieu"), cv2.imdecode(np.fromfile(MAU_PNG, np.uint8), cv2.IMREAD_GRAYSCALE)
    hang = []
    for bt in ("cot", "hang"):
        bang = tao(ANH_DIEN_TAP, RAW_DEV, nhan, None, bt, False, DIEN_TAP / bt)
        print(f"[{bt}]", json.dumps(bang, ensure_ascii=False))
    ch = chon(ANH_DIEN_TAP, nhan, None, False)
    for ten in ANH_DIEN_TAP:
        truong, i, d, _ = ch[ten]
        t = nhan[ten.split("_")[0]]
        o = []
        for bt in ("cot", "hang"):
            r = sua_anh(RAW_DEV / f"{ten}.jpg", t, truong, i, d, bt, None, L, mau)
            if not o:
                o.append(_nhan_chu(_cat(r["gray_goc"], r["M"], r["tam_dich_nan"], 95), f"{ten} {truong} cot {i + 1} so {d}: TRUOC"))
            o.append(_nhan_chu(_cat(r["gray"], r["M"], r["tam_dich_nan"], 95),
                               f"SAU – {'cung cot, hang ' + str(r['o_nguon'][1]) if bt == 'cot' else 'cung hang, cot ' + str(r['o_nguon'][0])}"))
        hang.append(np.hstack([np.pad(x, ((0, 0), (0, 16)), constant_values=255) for x in o]))
    w = max(x.shape[1] for x in hang)
    tong = np.vstack([np.pad(x, ((0, 12), (0, w - x.shape[1])), constant_values=255) for x in hang])
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", tong)[1].tofile(OUT_EVAL / "mau_truoc_sau.png")
    print(f"Đã ghi {OUT_EVAL / 'mau_truoc_sau.png'} (vùng trên ẢNH GỐC, phóng ×3) và ảnh chỉnh ở {DIEN_TAP}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] != ["dien-tap"]:
        sys.exit("Dùng: python tools/h3_mo_phong.py dien-tap   (ảnh đợt 2 chỉ tạo trong tools/eval_h3_mo_phong.py run --xac-nhan-h3)")
    dien_tap()
