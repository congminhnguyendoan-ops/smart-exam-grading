"""
kiem_tuong_phan.py - Lệnh AA (B2): tính TỶ LỆ TƯƠNG PHẢN (WCAG 2.x) cho các cặp màu chữ / nền chính của giao diện.
Đọc biến màu từ frontend/mau.css (nguồn duy nhất của bảng màu) – không ghi gì, không cần CSDL.

  python tools/kiem_tuong_phan.py            # in bảng Markdown; mã thoát 1 nếu có cặp KHÔNG ĐẠT

Ngưỡng: chữ thường ≥ 4,5:1 · chữ lớn (≥ 18,66 px đậm hoặc ≥ 24 px) ≥ 3:1 · thành phần giao diện (viền tiêu điểm, nền nút so với nền trang) ≥ 3:1.
Tỷ lệ = (L1 + 0,05) / (L2 + 0,05), L = độ chói tương đối sRGB (WCAG 2.1, mục 1.4.3).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAU_CSS = ROOT / "frontend" / "mau.css"
NGUONG = {"thuong": 4.5, "lon": 3.0, "thanh_phan": 3.0}

# (biến chữ, biến nền, loại, nơi dùng)
CAP = [
    ("--ink", "--bg", "thuong", "chữ chính trên nền trang"),
    ("--ink", "--card", "thuong", "chữ chính trên thẻ"),
    ("--ink", "--side", "thuong", "chữ thanh bên"),
    ("--ink", "--th", "thuong", "tiêu đề cột bảng"),
    ("--ink", "--hover", "thuong", "dòng bảng khi rê chuột"),
    ("--ink", "--okbg", "thuong", "câu đúng / thẻ câu đã chốt"),
    ("--ink", "--warnbg", "thuong", "câu cần xem"),
    ("--ink", "--badbg", "thuong", "câu sai / cột lệch"),
    ("--mut", "--bg", "thuong", "chữ phụ trên nền trang"),
    ("--mut", "--card", "thuong", "chữ phụ trên thẻ / cột đã khớp"),
    ("--mut", "--side", "thuong", "chữ phụ thanh bên"),
    ("--mut", "--th", "thuong", "chữ phụ trong tiêu đề bảng"),
    ("--mut", "--xam-nen", "thuong", "nhãn xám (Chưa có phiếu, Đang xử lý)"),
    ("--mut", "--pri-nhat", "thuong", "gợi ý trong khối hướng dẫn chụp (/m)"),
    ("--mut", "--okbg", "thuong", "chữ phụ trong thẻ câu đã chốt"),
    ("--tren-pri", "--pri", "thuong", "nút chính, mục đang chọn ở thanh bên, thanh đầu /m"),
    ("--tren-pri", "--pri-dam", "thuong", "nút chính khi rê chuột"),
    ("--pri-dam", "--side", "lon", "tiêu đề SMART EXAM (18 px đậm)"),
    ("--pri-dam", "--pri-nhat", "thuong", "tiêu đề khối hướng dẫn chụp (/m)"),
    ("--link", "--card", "thuong", "liên kết trên thẻ"),
    ("--link", "--bg", "thuong", "liên kết trên nền trang"),
    ("--link", "--side", "thuong", "liên kết thanh bên"),
    ("--link", "--okbg", "thuong", "liên kết trong thông báo xanh"),
    ("--link", "--warnbg", "thuong", "liên kết trong thông báo hổ phách"),
    ("--link", "--badbg", "thuong", "liên kết trong thông báo đỏ"),
    ("--ok", "--okbg", "thuong", "nhãn / thông báo Chính thức"),
    ("--warn", "--warnbg", "thuong", "nhãn / thông báo Cần xem"),
    ("--bad", "--badbg", "thuong", "nhãn / thông báo Bị từ chối"),
    ("--ok", "--card", "thuong", "số Chính thức trong tổng kết /m"),
    ("--warn", "--card", "thuong", "cảnh báo trên thẻ (ô nhập, tờ /m)"),
    ("--bad", "--card", "thuong", "lỗi trên thẻ (ô nhập, tờ /m)"),
    ("--tren-pri", "--bad", "thuong", "số đếm hàng đợi, thông báo lỗi nổi"),
    ("--tren-pri", "--toast", "thuong", "thông báo nổi"),
    ("--pri2", "--pri2-nhat", "thuong", "nhãn xanh dương (/m)"),
    ("--pri2", "--card", "thanh_phan", "viền tiêu điểm bàn phím trên thẻ"),
    ("--pri2", "--bg", "thanh_phan", "viền tiêu điểm bàn phím trên nền trang"),
    ("--pri", "--bg", "thanh_phan", "nền nút chính so với nền trang"),
    ("--pri", "--side", "thanh_phan", "mục đang chọn so với nền thanh bên"),
    # lệnh AB: viền Ô NHẬP (input / select / textarea) – WCAG 1.4.11; viền thẻ (--line) là trang trí nên không xét
    ("--vien-o", "--card", "thanh_phan", "viền ô nhập trên thẻ"),
    ("--vien-o", "--bg", "thanh_phan", "viền ô nhập trên nền trang"),
    ("--vien-o", "--side", "thanh_phan", "viền ô chọn kỳ thi ở thanh bên"),
]


def doc_bien(css: str | None = None) -> dict[str, str]:
    """Biến màu dạng #RRGGBB trong :root của mau.css -> {"--ink": "#1E2A32", …}."""
    css = css if css is not None else MAU_CSS.read_text(encoding="utf-8")
    return {k: v.upper() for k, v in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", css)}


def do_choi(hex_: str) -> float:
    def kenh(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * kenh(r) + 0.7152 * kenh(g) + 0.0722 * kenh(b)


def ty_le(a: str, b: str) -> float:
    la, lb = sorted((do_choi(a), do_choi(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def bang(bien: dict[str, str] | None = None) -> list[dict]:
    bien = bien or doc_bien()
    ra = []
    for chu, nen, loai, noi in CAP:
        t = ty_le(bien[chu], bien[nen])
        ra.append({"chu": chu, "nen": nen, "mau_chu": bien[chu], "mau_nen": bien[nen], "loai": loai, "noi_dung": noi,
                   "ty_le": round(t, 2), "nguong": NGUONG[loai], "dat": t >= NGUONG[loai]})
    return ra


def markdown(ds: list[dict]) -> str:
    ten = {"thuong": "chữ thường", "lon": "chữ lớn", "thanh_phan": "thành phần"}
    dong = ["| Chữ / phần tử | Nền | Loại | Tỷ lệ | Ngưỡng | Kết quả | Dùng ở |", "|---|---|---|---:|---:|---|---|"]
    for d in ds:
        dong.append(f"| `{d['chu']}` {d['mau_chu']} | `{d['nen']}` {d['mau_nen']} | {ten[d['loai']]} | {d['ty_le']:.2f}:1 | {d['nguong']}:1 | "
                    f"{'ĐẠT' if d['dat'] else 'KHÔNG ĐẠT'} | {d['noi_dung']} |")
    return "\n".join(dong)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ds = bang()
    print(markdown(ds))
    hong = [d for d in ds if not d["dat"]]
    print(f"\n{len(ds) - len(hong)}/{len(ds)} cặp ĐẠT" + (f" – KHÔNG ĐẠT: {', '.join(d['chu'] + '/' + d['nen'] for d in hong)}" if hong else ""))
    sys.exit(1 if hong else 0)
