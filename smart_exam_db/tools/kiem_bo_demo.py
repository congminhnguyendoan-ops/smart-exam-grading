import csv
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THU_MUC = ROOT / "answer_sheet" / "demo_bv"
DAP_AN, KICH_BAN = THU_MUC / "demo_bv_dap_an.csv", THU_MUC / "demo_bv_kich_ban.csv"
SO_CAU, THANG = 40, Decimal(10)
SBD_KY_THI = {**{str(s): "E1" for s in range(220001, 220006)}, **{str(s): "E2" for s in range(220006, 220011)}}
KY_HIEU = re.compile(r"^(-|[A-Da-d]{1,4})$")


def doc(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dung(nhan: str, dap_an: str) -> bool:
    return len(nhan) == 1 and nhan != "-" and nhan.upper() == dap_an


def kiem(dap_an_rows: list[dict], kich_ban: list[dict]) -> tuple[list[str], list[dict]]:
    loi, ky_thi, ma_de = [], {}, {}
    for r in dap_an_rows:
        a = r["answers"]
        if len(a) != SO_CAU or set(a) - set("ABCD"):
            loi.append(f"mã đề {r['exam_code']}: đáp án phải đủ {SO_CAU} ký tự A–D (có {len(a)})")
        if r["exam_code"] in ma_de:
            loi.append(f"mã đề {r['exam_code']} bị trùng")
        ma_de[r["exam_code"]] = r
        k = (r["exam_title"], r["subject_code"], r["class_code"], r["teacher"])
        if ky_thi.setdefault(r["exam"], k) != k:
            loi.append(f"kỳ thi {r['exam']}: các mã đề khác tiêu đề / môn / lớp / giáo viên")
        if "[DEMO-BV]" not in r["exam_title"]:
            loi.append(f"kỳ thi {r['exam']}: tiêu đề thiếu nhãn [DEMO-BV]")
    for e, n in {e: sum(r["exam"] == e for r in dap_an_rows) for e in ky_thi}.items():
        if n != 2:
            loi.append(f"kỳ thi {e}: cần 2 mã đề, có {n}")
    bang, da = [], set()
    for p in kich_ban:
        ma = p["sheet_id"]
        if ma in da:
            loi.append(f"{ma}: trùng mã phiếu")
        da.add(ma)
        thieu = [q for q in range(1, SO_CAU + 1) if f"q{q}" not in p or p[f"q{q}"] is None]
        if thieu:
            loi.append(f"{ma}: thiếu câu {thieu}")
            continue
        sai_kh = [q for q in range(1, SO_CAU + 1) if not KY_HIEU.match(p[f"q{q}"])]
        if sai_kh:
            loi.append(f"{ma}: ký hiệu không hợp lệ ở câu {sai_kh}")
        md = ma_de.get(p["exam_code"])
        if md is None or md["exam"] != p["exam"]:
            loi.append(f"{ma}: mã đề {p['exam_code']} không thuộc kỳ thi {p['exam']}")
            continue
        if len(md["answers"]) != SO_CAU:
            continue
        if SBD_KY_THI.get(p["sbd"]) != p["exam"]:
            loi.append(f"{ma}: SBD {p['sbd']} không thuộc kỳ thi {p['exam']} theo quy ước (220001–220005 → E1, 220006–220010 → E2)")
        n = sum(dung(p[f"q{q}"], md["answers"][q - 1]) for q in range(1, SO_CAU + 1))
        diem = THANG * n / SO_CAU
        mo = [q for q in range(1, SO_CAU + 1) if any(c.islower() for c in p[f"q{q}"])]
        nhieu = [q for q in range(1, SO_CAU + 1) if len(p[f"q{q}"]) > 1]
        trong = [q for q in range(1, SO_CAU + 1) if p[f"q{q}"] == "-"]
        if n != int(p["so_cau_dung"]):
            loi.append(f"{ma}: tính lại {n} câu đúng ≠ so_cau_dung {p['so_cau_dung']}")
        if diem != Decimal(p["diem_mong_doi"]):
            loi.append(f"{ma}: tính lại {diem} điểm ≠ diem_mong_doi {p['diem_mong_doi']}")
        bang.append({"phieu": ma, "sbd": p["sbd"], "ky_thi": p["exam"], "ma_de": p["exam_code"], "dung": n, "diem": diem,
                     "cau_mo": mo, "cau_nhieu_o": nhieu, "cau_trong": trong})
    return loi, bang


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    loi, bang = kiem(doc(DAP_AN), doc(KICH_BAN))
    for b in bang:
        print(f"{b['phieu']} SBD {b['sbd']} {b['ky_thi']}/{b['ma_de']}: {b['dung']} đúng → {b['diem']:g} điểm · mờ {len(b['cau_mo'])} · "
              f"nhiều ô {b['cau_nhieu_o']} · trống {b['cau_trong']}")
    if loi:
        print("\nLỖI KỊCH BẢN – DỪNG:")
        for x in loi:
            print("  -", x)
        return 1
    print(f"\nKHỚP: {len(bang)} phiếu, điểm tính lại = điểm mong đợi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
