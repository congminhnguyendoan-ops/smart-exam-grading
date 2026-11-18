import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine import ocr, omr  # noqa: E402
from cv_engine.preprocessing import nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_TEST, PHIEU_VAL, chan_test, ma_phieu, nguoi_viet  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "_eval" / "an"
UNG_VIEN = DATA / "_eval" / "am" / "ocr_cnn_sau_seed2026.json"
SHA_UNG_VIEN = "9e84b9093e12b45f6483419f569e46eba041bbac846f01898304aaddd14eb048"
SHA_HIEN_TAI = "6d87205c83a29fccc4eb450f0aec0c9d51ba56e1bb141664060041ab0f2fcad5"


def sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xac-nhan-val", action="store_true")
    ap.add_argument("--xac-nhan-test", action="store_true")
    a = ap.parse_args()
    if not a.xac_nhan_val:
        sys.exit("DỪNG: thiếu --xac-nhan-val")
    assert sha(UNG_VIEN) == SHA_UNG_VIEN, "SHA ứng viên khác đăng ký"
    assert sha(ocr.DUONG_DAN_MO_HINH) == SHA_HIEN_TAI, "SHA mô hình hiện tại khác đăng ký"
    tap = set(PHIEU_VAL) | set(PHIEU_TEST)
    anhs = sorted(p for p in (DATA / "raw").glob("*.jpg") if ma_phieu(p.stem) in tap)
    chan_test([p.stem for p in anhs], a.xac_nhan_test, "Lệnh AN (đo thay mô hình)")
    nhan = {}
    with (DATA / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if int(r["sheet_id"]) in tap:
                nhan[int(r["sheet_id"])] = (r["sbd"], r["exam_code"])
    lay, mo_om = nap_layout("phieu"), omr.nap_mo_hinh()
    mh = {"hien_tai": ocr.nap_mo_hinh_ocr(), "ung_vien": ocr.nap_mo_hinh_ocr(UNG_VIEN)}
    rows = []
    for p in anhs:
        ph = ma_phieu(p.stem)
        sbd_t, ma_t = nhan[ph]
        kq = preprocess(str(p), lay)
        r = {"anh": p.stem, "tap": "val" if ph in PHIEU_VAL else "test", "nguoi": nguoi_viet(p.stem), "truth": {"sbd": sbd_t, "ma_de": ma_t}}
        if not kq.ok:
            rows.append({**r, "tu_choi": kq.ly_do})
            continue
        res = omr.doc_phieu(kq, lay, mo_om)
        bubble = {"sbd": res.sbd, "ma_de": res.ma_de}
        for ten, m in mh.items():
            hv = ocr.doc_chu_so(kq, lay, m)
            dc = ocr.doi_chieu_dinh_danh(res, hv, True, True, mo_hinh=m)
            r[ten] = {}
            for f, cot in (("sbd", hv.sbd), ("ma_de", hv.ma_de)):
                t = r["truth"][f]
                hw = "".join(c.chu_so for c in cot)
                gia, chac, ly = dc[f]
                r[ten][f] = {"hw": hw, "hw_dung": hw == t, "chac": bool(chac), "can_xem": not chac, "gia_tri": gia, "ly_do": list(ly),
                             "loi_im_lang": bool(chac and (gia != t or bubble[f] != t))}
        rows.append(r)
        print(r["anh"], {t: [(f, int(r[t][f]["hw_dung"]), int(r[t][f]["can_xem"]), int(r[t][f]["loi_im_lang"])) for f in ("sbd", "ma_de")] for t in mh}, flush=True)

    def tong(dieu_kien):
        out = {}
        for ten in mh:
            ok = [r for r in rows if "tu_choi" not in r and dieu_kien(r)]
            truong = [r[ten][f] for r in ok for f in ("sbd", "ma_de")]
            out[ten] = {"anh": len(ok), "truong": len(truong), "hw_dung": sum(t["hw_dung"] for t in truong), "can_xem": sum(t["can_xem"] for t in truong),
                        "loi_im_lang": sum(t["loi_im_lang"] for t in truong), "nhan": sum(t["chac"] for t in truong),
                        "sbd_dung": sum(r[ten]["sbd"]["hw_dung"] for r in ok), "ma_de_dung": sum(r[ten]["ma_de"]["hw_dung"] for r in ok)}
        return out
    kq = {"sha_hien_tai": SHA_HIEN_TAI, "sha_ung_vien": SHA_UNG_VIEN, "tu_choi": [r["anh"] for r in rows if "tu_choi" in r],
          "gop": tong(lambda r: True), "val": tong(lambda r: r["tap"] == "val"), "test": tong(lambda r: r["tap"] == "test"),
          "nguoi4": tong(lambda r: r["nguoi"] == 4), "nguoi5": tong(lambda r: r["nguoi"] == 5), "anh": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ket_qua.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("gop", "val", "test"):
        print(k, json.dumps(kq[k]))


if __name__ == "__main__":
    main()
