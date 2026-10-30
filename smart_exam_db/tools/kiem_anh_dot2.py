"""
kiem_anh_dot2.py - Kiểm ảnh ĐỢT 2 (data/raw_dot2/, phiếu 0101–0110) TRƯỚC khi chạy test – CHỈ ĐỌC (lệnh K, 29/10/2026).

Làm: (1) tên tệp: đủ 20 ảnh, mỗi mã đúng 2 ảnh, đúng cặp điều kiện chụp trong tệp phân công
     (answer_sheet/dot2/phan_cong_va_dap_an_dot2.xlsx, sheet "Phân công") và cột `conditions` của ground_truth_dot2.csv;
     (2) từng ảnh: kích thước điểm ảnh (header), EXIF Orientation, dung lượng, SHA-256, EXIF hãng / máy / thời điểm / phần mềm;
     (3) tìm 4 marker góc bằng cv_engine.preprocessing.find_markers (CHỈ phát hiện: không nắn, không chấm,
     không đọc SBD / mã đề / ô tô).
Ghi: data/_eval/kiem_anh_dot2.csv, data/_eval/sha_anh_dot2.txt. Không ghi gì vào data/raw*.
KHÔNG đọc cột đáp án của tệp phân công / nhãn (chỉ mã phiếu + điều kiện chụp).

  python tools/kiem_anh_dot2.py
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

import openpyxl
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cv_engine.preprocessing import LoiDocAnh, doc_anh, find_markers, nap_layout  # noqa: E402

RAW_DOT2 = ROOT / "data" / "raw_dot2"
PHAN_CONG = ROOT / "answer_sheet" / "dot2" / "phan_cong_va_dap_an_dot2.xlsx"
GT = ROOT / "answer_sheet" / "dot2" / "ground_truth_dot2.csv"
OUT_CSV = ROOT / "data" / "_eval" / "kiem_anh_dot2.csv"
OUT_SHA = ROOT / "data" / "_eval" / "sha_anh_dot2.txt"
MA_DOT2 = [f"{i:04d}" for i in range(101, 111)]
TEN_RE = re.compile(r"^(\d{4})_(C[1-4])\.jpe?g$", re.I)
MIN_CANH = 1500
EXIF_IFD = 0x8769


def dieu_kien_phan_cong() -> dict[str, list[str]]:
    """{mã phiếu: [Ck, Ck]} từ cột 'Điều kiện chụp' – chỉ đọc 2 cột, bỏ qua mọi cột khác."""
    ws = openpyxl.load_workbook(PHAN_CONG, read_only=True)["Phân công"]
    hang = list(ws.iter_rows(values_only=True))
    tieu_de = [str(x or "") for x in hang[0]]
    c_ma = tieu_de.index("Mã phiếu")
    c_dk = next(i for i, t in enumerate(tieu_de) if t.startswith("Điều kiện chụp"))
    out = {}
    for r in hang[1:]:
        if r[c_ma]:
            out[str(r[c_ma]).zfill(4)] = sorted(set(re.findall(r"C[1-4]", str(r[c_dk] or ""))))
    return out


def dieu_kien_gt() -> dict[str, list[str]]:
    with GT.open(encoding="utf-8-sig", newline="") as f:
        return {r["sheet_id"].zfill(4): sorted(set(re.findall(r"C[1-4]", r["conditions"]))) for r in csv.DictReader(f)}


def doc_exif(p: Path) -> dict:
    with Image.open(p) as im:
        rong, cao = im.size
        ex = im.getexif()
        ifd = ex.get_ifd(EXIF_IFD)
    return {"rong": rong, "cao": cao, "orientation": ex.get(274, ""), "hang": str(ex.get(271, "")).strip(),
            "may": str(ex.get(272, "")).strip(), "phan_mem": str(ex.get(305, "")).strip(),
            "chup_luc": str(ifd.get(36867, "") or ex.get(306, "")).strip(), "so_the_exif": len(ex) + len(ifd)}


def main():
    pc, gt = dieu_kien_phan_cong(), dieu_kien_gt()
    tep = sorted(p for p in RAW_DOT2.iterdir() if p.is_file())
    layout = nap_layout("phieu")
    van_de, hang, sha_dong = [], [], []

    # --- tên tệp
    theo_ma: dict[str, list[str]] = {}
    for p in tep:
        m = TEN_RE.match(p.name)
        if not m:
            van_de.append(f"tên sai quy ước: {p.name}")
            continue
        theo_ma.setdefault(m.group(1), []).append(m.group(2).upper())
    for ma in sorted(set(theo_ma) | set(MA_DOT2)):
        co = sorted(theo_ma.get(ma, []))
        if ma not in MA_DOT2:
            van_de.append(f"thừa mã ngoài 0101–0110: {ma} {co}")
            continue
        if len(co) != len(set(co)):
            van_de.append(f"trùng điều kiện: {ma} {co}")
        if sorted(set(co)) != pc.get(ma):
            van_de.append(f"{ma}: có {co}, phân công {pc.get(ma)}")
        if pc.get(ma) != gt.get(ma):
            van_de.append(f"{ma}: phân công {pc.get(ma)} ≠ ground_truth_dot2 {gt.get(ma)}")
    if len(tep) != 20:
        van_de.append(f"số tệp = {len(tep)} (cần 20)")

    # --- từng ảnh
    for p in tep:
        b = p.read_bytes()
        sha = hashlib.sha256(b).hexdigest().upper()
        sha_dong.append(f"{sha}  {len(b):>9}  {p.name}")
        r = {"file": p.name, "dung_luong": len(b), "sha256": sha}
        try:
            r.update(doc_exif(p))
        except Exception as e:  # noqa: BLE001 – ảnh hỏng: chỉ báo
            r["loi_exif"] = f"{type(e).__name__}: {e}"
        try:
            gray, _ = doc_anh(p)
            tam, ly_do, ct = find_markers(gray, layout)
            r.update({"anh_sau_exif": f"{gray.shape[1]}x{gray.shape[0]}", "marker_4": "co" if tam is not None else "khong",
                      "marker_ly_do": ly_do, "so_ung_vien": len(ct.get("ung_vien", [])),
                      "marker_tam": "" if tam is None else ";".join(f"{x:.0f},{y:.0f}" for x, y in tam)})
        except LoiDocAnh as e:
            r.update({"marker_4": "khong", "marker_ly_do": "khong_doc_duoc", "loi_exif": str(e)})
        canh = min(r.get("rong", 0), r.get("cao", 0))
        canh_bao = []
        if canh < MIN_CANH:
            canh_bao.append("do_phan_giai_thap")
        if (r.get("rong"), r.get("cao")) not in ((4032, 3024), (3024, 4032)):
            canh_bao.append("kich_thuoc_khac_4032x3024")
        if not r.get("hang") or not r.get("chup_luc"):
            canh_bao.append("thieu_exif")
        if r.get("phan_mem") and not re.fullmatch(r"\d+(\.\d+)*", r["phan_mem"]):
            canh_bao.append("phan_mem_khac_phien_ban_ios")
        if r.get("marker_4") != "co":
            canh_bao.append("khong_du_4_marker")
        r["canh_bao"] = ";".join(canh_bao)
        hang.append(r)

    cot = ["file", "dung_luong", "rong", "cao", "orientation", "anh_sau_exif", "hang", "may", "phan_mem", "chup_luc",
           "so_the_exif", "marker_4", "marker_ly_do", "so_ung_vien", "marker_tam", "canh_bao", "loi_exif", "sha256"]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, cot)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in cot} for r in hang)
    OUT_SHA.write_text("# SHA-256  dung_lượng(byte)  tên tệp – data/raw_dot2 (khoá ảnh đợt 2 trước khi chạy test)\n"
                       + "\n".join(sha_dong) + "\n", encoding="utf-8")

    for r in hang:
        print(f"{r['file']:<13} {r.get('rong', '?')}x{r.get('cao', '?')} o={r.get('orientation', '')} "
              f"{r['dung_luong'] / 1e6:5.2f} MB  {r.get('may', '')} | {r.get('phan_mem', '')} | {r.get('chup_luc', '')}  "
              f"marker={r.get('marker_4')} {r.get('marker_ly_do', '')}  {r['canh_bao']}")
    print("\nTÊN TỆP: " + ("ĐẠT (20 ảnh, 10 mã × 2, đúng cặp điều kiện)" if not van_de else "VẤN ĐỀ:\n  " + "\n  ".join(van_de)))
    print(f"Ghi: {OUT_CSV}\n     {OUT_SHA}")


if __name__ == "__main__":
    main()
