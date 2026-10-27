"""
chay_server_lan.py - Chạy máy chủ cho ĐIỆN THOẠI cùng mạng nội bộ (docs/thiet_ke_chup_dien_thoai.md mục 4).

Tìm IP LAN → in địa chỉ trang điện thoại + mã QR ra terminal + lệnh tường lửa (CHỈ IN – bạn tự chạy bằng PowerShell quản trị) →
chạy uvicorn backend.main:app --host 0.0.0.0. Bật luồng dọn ẢNH TẠM (ANH_XOA_TU_DONG=1) trừ khi --khong-xoa-anh.
Không đổi cấu hình hệ thống (không chạy lệnh tường lửa / mạng nào).

  python tools/chay_server_lan.py                 # cổng 8000
  python tools/chay_server_lan.py --cong 8080 --khong-xoa-anh
  python tools/chay_server_lan.py --chi-in        # chỉ in địa chỉ / QR / lệnh, không chạy máy chủ
Thường (chỉ máy này, 127.0.0.1):  uvicorn backend.main:app --port 8000
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import mang  # noqa: E402


def in_huong_dan(cong: int, xoa_anh: bool) -> str | None:
    uv = mang.ung_vien_ip()
    chinh = next((u for u in uv if not u.ao), uv[0] if uv else None)
    print("=" * 72)
    print("SMART EXAM – máy chủ cho điện thoại (mạng nội bộ)")
    print("=" * 72)
    if not uv:
        print("KHÔNG tìm thấy IP mạng nội bộ (10.x / 172.16–31.x / 192.168.x). Máy đã nối Wi‑Fi / LAN chưa?")
    for u in uv:
        nhan = ", ".join(x for x, c in (("tuyến mặc định", u.mac_dinh), ("điểm phát sóng Windows", u.hotspot), ("CARD ẢO – điện thoại thường không tới được", u.ao)) if c)
        print(f"  {'→' if u is chinh else ' '} {mang.url_dien_thoai(u.ip, cong):32} {u.card}{' (' + nhan + ')' if nhan else ''}")
    url = mang.url_dien_thoai(chinh.ip, cong) if chinh else None
    if url:
        print(f"\nĐIỆN THOẠI mở: {url}   (quét mã QR dưới đây)")
        print(mang.qr_terminal(url))
    lt = mang.lenh_tuong_lua(cong)
    print("Tường lửa – BẠN tự chạy MỘT LẦN trong PowerShell (Run as Administrator); công cụ này KHÔNG chạy:")
    print("  " + lt["mo"])
    print("  Chỉ nhận kết nối từ CÙNG mạng nội bộ (LocalSubnet), không mở ra Internet. Xoá luật sau buổi demo:")
    print("  " + lt["go"])
    print("Wi‑Fi trường chặn thiết bị nói chuyện với nhau (QR mở không được dù đúng IP)? Bật điểm phát sóng (hotspot) trên điện thoại,")
    print("máy tính nối vào đó, rồi chạy lại công cụ này để lấy IP mới.")
    print(f"Ảnh tạm: {'XOÁ ảnh của phiếu đã chốt sau ANH_GIU_GIO giờ (mặc định 24)' if xoa_anh else 'KHÔNG tự xoá (--khong-xoa-anh)'}.")
    print("Máy tính: http://127.0.0.1:%d/  ·  Dừng máy chủ: Ctrl+C" % cong)
    print("=" * 72)
    return url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cong", type=int, default=mang.CONG_MAC_DINH)
    ap.add_argument("--khong-xoa-anh", action="store_true", help="không chạy luồng dọn ảnh tạm")
    ap.add_argument("--chi-in", action="store_true", help="chỉ in địa chỉ / QR / lệnh tường lửa, không chạy máy chủ")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    in_huong_dan(a.cong, not a.khong_xoa_anh)
    if a.chi_in:
        return 0
    os.chdir(ROOT)
    os.environ["SMART_EXAM_HOST"] = "0.0.0.0"                     # cho GET /meta/ket-noi biết đang mở LAN
    os.environ["ANH_XOA_TU_DONG"] = "0" if a.khong_xoa_anh else "1"
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=a.cong)
    return 0


if __name__ == "__main__":
    sys.exit(main())
