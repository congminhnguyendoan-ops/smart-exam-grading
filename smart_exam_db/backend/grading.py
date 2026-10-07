"""
grading.py - Chấm điểm THUẦN (không CSDL, không ảnh): dễ kiểm thử, một nơi duy nhất quyết định "câu nào được chấm".

Quy tắc (người dùng chốt 07/10/2026): câu OMR gắn "cần xem" KHÔNG BAO GIỜ được chấm như câu chắc chắn.
  - câu cần xem  -> is_correct = None (chưa chấm); không cộng vào điểm tạm; chỉ cộng vào điểm tối đa có thể đạt;
  - câu chắc chắn -> đúng khi state = 'filled' và đáp án chọn trùng đáp án chuẩn (câu trống, nhiều ô: sai);
  - chỉ state 'filled' mới tính (state 'faint' / 'multiple' chưa qua giáo viên không được tính dù không bị gắn cờ).
Làm tròn 3 chữ số như fn_grade_sheet của CSDL (ROUND half-up); service kiểm chéo với fn_grade_sheet khi chốt điểm.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

LUA_CHON = "ABCDEF"


def lam_tron(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def chuan_hoa_lua_chon(s: str, so_lua_chon: int = 4) -> str:
    """'ca' -> 'AC' (sắp theo thứ tự, bỏ trùng). '' = bỏ trống. Ném ValueError nếu có ký tự ngoài A..(số lựa chọn)."""
    hop_le = LUA_CHON[:so_lua_chon]
    s = (s or "").strip().upper()
    if any(c not in hop_le for c in s):
        raise ValueError(f"lựa chọn '{s}' không hợp lệ – chỉ gồm các chữ {', '.join(hop_le)} (hoặc rỗng = bỏ trống)")
    return "".join(sorted(set(s)))


def trang_thai_tu_lua_chon(lua_chon: str) -> str:
    """Giá trị bubble_state khi giáo viên chốt lựa chọn: '' -> blank, 1 ô -> filled, ≥ 2 ô -> multiple."""
    return "blank" if not lua_chon else ("filled" if len(lua_chon) == 1 else "multiple")


@dataclass(frozen=True)
class CauDaCham:
    question_no: int
    correct_option: str | None
    points: Decimal
    is_correct: bool | None            # None = cần xem, chưa chấm


@dataclass(frozen=True)
class KetQuaCham:
    cau: tuple[CauDaCham, ...]
    num_correct: int                   # số câu chắc chắn đúng
    diem_tam: Decimal                  # điểm chỉ tính câu chắc chắn
    diem_toi_da: Decimal               # điểm nếu mọi câu cần xem đều đúng
    so_cau_can_xem: int


def cham_diem(hang: Iterable[Mapping], dap_an: Mapping[int, tuple[str, Decimal | None]],
              diem_mac_dinh: Decimal) -> KetQuaCham:
    """hang: mỗi phần tử có question_no, selected_options, state, needs_review (như hàng sheet_answers).
    dap_an: {số câu: (đáp án chuẩn, điểm hoặc None = điểm mặc định)}. Câu có trong đáp án mà thiếu hàng bài làm: tính như bỏ trống."""
    theo_cau = {r["question_no"]: r for r in hang}
    ket, tam, toi_da, dem, cho = [], Decimal(0), Decimal(0), 0, 0
    for q in sorted(dap_an):
        dung, diem = dap_an[q]
        d = Decimal(diem) if diem is not None else diem_mac_dinh
        r = theo_cau.get(q)
        if r is not None and r["needs_review"]:
            ok = None
            cho += 1
            toi_da += d
        else:
            ok = bool(r is not None and r["state"] == "filled" and r["selected_options"] == dung)
            if ok:
                tam += d
                toi_da += d
                dem += 1
        ket.append(CauDaCham(q, dung, d, ok))
    return KetQuaCham(tuple(ket), dem, lam_tron(tam), lam_tron(toi_da), cho)
