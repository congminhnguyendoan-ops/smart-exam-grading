from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

LUA_CHON = "ABCDEF"


def lam_tron(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def chuan_hoa_lua_chon(s: str, so_lua_chon: int = 4) -> str:
    hop_le = LUA_CHON[:so_lua_chon]
    s = (s or "").strip().upper()
    if any(c not in hop_le for c in s):
        raise ValueError(f"lựa chọn '{s}' không hợp lệ – chỉ gồm các chữ {', '.join(hop_le)} (hoặc rỗng = bỏ trống)")
    return "".join(sorted(set(s)))


def trang_thai_tu_lua_chon(lua_chon: str) -> str:
    return "blank" if not lua_chon else ("filled" if len(lua_chon) == 1 else "multiple")


@dataclass(frozen=True)
class CauDaCham:
    question_no: int
    correct_option: str | None
    points: Decimal
    is_correct: bool | None


@dataclass(frozen=True)
class KetQuaCham:
    cau: tuple[CauDaCham, ...]
    num_correct: int
    diem_tam: Decimal
    diem_toi_da: Decimal
    so_cau_can_xem: int


def cham_diem(hang: Iterable[Mapping], dap_an: Mapping[int, tuple[str, Decimal | None]],
              diem_mac_dinh: Decimal) -> KetQuaCham:
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
