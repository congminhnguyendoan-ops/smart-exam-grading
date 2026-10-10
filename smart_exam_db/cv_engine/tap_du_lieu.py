"""
tap_du_lieu.py - NGUỒN DUY NHẤT cho ranh giới dev / test của bộ dữ liệu 40 phiếu (Tuần 4, Bước 6).

  dev  = phiếu 0001–0034 + trang chữ số D001–D010: thử ý tưởng, chọn mọi tham số / ngưỡng.
  test = phiếu 0035–0040: chạy MỘT LẦN ở đánh giá cuối (Tuần 4 Bước 7; đánh giá cuối OMR Tuần 5).
OMR (CLAUDE.md mục 4, chia THEO MÃ PHIẾU để 2 ảnh của cùng phiếu không rơi vào hai tập):
  train 0001–0028 · val 0029–0034 · test 0035–0040 (val ∪ train = dev của preprocessing ⇒ không rò rỉ giữa các tuần).

Tuần 5 (split.csv của OMR) và mọi công cụ sau này PHẢI dùng lại module này, KHÔNG định nghĩa lại ranh giới.
Công cụ nào có thể đọc ảnh / nhãn test thì gọi chan_test() TRƯỚC khi đọc bất kỳ file nào.
"""
import re
from pathlib import Path

PHIEU_DEV = range(1, 35)
PHIEU_TEST = range(35, 41)
PHIEU_TRAIN = range(1, 29)          # OMR
PHIEU_VAL = range(29, 35)           # OMR

_MA = re.compile(r"^(\d{4})(?:_C[1-4])?$", re.I)


class ChamTapTest(Exception):
    """Định đọc ảnh / nhãn của tập test mà không có cờ xác nhận (--xac-nhan-test)."""


def ma_phieu(ten) -> int | None:
    """'0035_C1' / '0035_C1.jpg' / '0035' / Path -> 35. Trang chữ số 'D003' và tên khác -> None."""
    m = _MA.match(Path(str(ten)).stem)
    return int(m.group(1)) if m else None


def la_test(ten) -> bool:
    return ma_phieu(ten) in PHIEU_TEST


def tap_cua(ten) -> str:
    """'dev' / 'test' / 'khac' (tên không theo quy ước NNNN_Ck / NNNN / DNNN)."""
    m = ma_phieu(ten)
    if m is not None:
        return "test" if m in PHIEU_TEST else ("dev" if m in PHIEU_DEV else "khac")
    return "dev" if re.match(r"^D\d{3}$", Path(str(ten)).stem, re.I) else "khac"


def chan_test(ds, xac_nhan: bool = False, viec: str = "") -> None:
    """Ném ChamTapTest nếu ds có tên thuộc tập test mà xac_nhan = False. Gọi TRƯỚC khi đọc file."""
    t = sorted({Path(str(x)).stem for x in ds if la_test(x)})
    if t and not xac_nhan:
        raise ChamTapTest(f"{viec or 'Lệnh này'} định dùng {len(t)} mục của tập TEST ({', '.join(t[:6])}"
                          f"{', …' if len(t) > 6 else ''}). Tập test 0035–0040 chỉ chạy một lần ở đánh giá cuối "
                          f"(docs/ke_hoach_tuan4.md Bước 7). Nếu đúng là lúc đó, thêm --xac-nhan-test.")


# ---------------------------------------------------------------------------------------------
# Tuần 6 (CNN chữ số, chốt 10/10/2026): NGƯỜI VIẾT. KHÔNG đổi các hằng / hàm ở trên.
#   Trang chữ số: người 1 = D001–D002, 2 = D003–D004, 3 = D005–D006, 4 = D007–D008, 5 = D009–D010 (mỗi người 2 trang).
#   Chữ số viết tay trên phiếu: người 1 = 0001–0008, 2 = 0009–0016, 3 = 0017–0024, 4 = 0025–0032, 5 = 0033–0040.
#   5-fold CHIA THEO NGƯỜI VIẾT (fold = người − 1; mỗi fold bỏ ra 1 người). Chỉ ghi "người 1–5", không tên thật.
#   Hạn chế: test 0035–0040 toàn do người 5 viết, người 5 cũng viết D009–D010 → test chỉ đo "nét chữ đã gặp".
# ---------------------------------------------------------------------------------------------
TRANG_CHU_SO = range(1, 11)                 # D001–D010
SO_NGUOI_VIET = 5
_MA_TRANG = re.compile(r"^D(\d{3})$", re.I)


def ma_trang(ten) -> int | None:
    """'D003' / 'D003.jpg' / Path -> 3. Phiếu và tên khác -> None."""
    m = _MA_TRANG.match(Path(str(ten)).stem)
    return int(m.group(1)) if m and int(m.group(1)) in TRANG_CHU_SO else None


def nguoi_viet_trang(trang: int) -> int:
    """Số trang chữ số (1–10) -> người viết 1–5."""
    if trang not in TRANG_CHU_SO:
        raise ValueError(f"Trang chữ số phải 1–10, nhận {trang}")
    return (trang - 1) // 2 + 1


def nguoi_viet_phieu(phieu: int) -> int:
    """Mã phiếu (1–40) -> người viết 1–5 (mỗi người 8 phiếu)."""
    if phieu not in range(1, 41):
        raise ValueError(f"Mã phiếu phải 1–40, nhận {phieu}")
    return (phieu - 1) // 8 + 1


def nguoi_viet(ten) -> int | None:
    """'D003' -> 2; '0035_C1' -> 5; tên khác -> None."""
    t = ma_trang(ten)
    if t is not None:
        return nguoi_viet_trang(t)
    p = ma_phieu(ten)
    return nguoi_viet_phieu(p) if p is not None and 1 <= p <= 40 else None


def fold_nguoi_viet(ten) -> int | None:
    """Fold 0–4 của 5-fold theo người viết (= người − 1); tên khác -> None."""
    n = nguoi_viet(ten)
    return None if n is None else n - 1
