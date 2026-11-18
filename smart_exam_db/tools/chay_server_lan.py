"""
chay_server_lan.py - Chạy máy chủ cho ĐIỆN THOẠI cùng mạng nội bộ (docs/thiet_ke_chup_dien_thoai.md mục 4).

Tìm IP LAN → in địa chỉ trang điện thoại + mã QR ra terminal + lệnh tường lửa (CHỈ IN – bạn tự chạy bằng PowerShell quản trị) →
chạy uvicorn backend.main:app --host 0.0.0.0. Không đổi cấu hình hệ thống (không chạy lệnh tường lửa / mạng nào).

DỌN ẢNH TẠM (backend/don_anh.py) – lệnh Z, 30/10/2026: MẶC ĐỊNH TẮT. Chỉ bật khi CHỦ Ý thêm --bat-don-anh: khi đó một lượt chạy NGAY lúc khởi động rồi mỗi giờ,
xoá ảnh gốc + ảnh nắn + ô viết tay của phiếu đã chốt / bị từ chối sau ANH_GIU_GIO (24) giờ ở MỌI kỳ thi không có "[DEMO" trong tên (kể cả kỳ thi thật).
Trước lệnh Z mặc định là BẬT (đã làm mất ảnh kỳ thi 115 lúc 28/10/2026 09:16:21). --khong-xoa-anh vẫn nhận (tương thích, = mặc định tắt).

  python tools/chay_server_lan.py                 # cổng 8000, KHÔNG dọn ảnh
  python tools/chay_server_lan.py --bat-don-anh   # bật dọn ảnh tạm (chỉ khi chủ ý)
  python tools/chay_server_lan.py --cong 8080 --khong-xoa-anh   # cách gọi cũ, vẫn chạy (không dọn ảnh)
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
    print("Máy tính: http://127.0.0.1:%d/  ·  Dừng máy chủ: Ctrl+C" % cong)
    print("=" * 72)
    print(dong_trang_thai_don_anh(xoa_anh))
    return url


def dong_trang_thai_don_anh(bat: bool) -> str:
    if bat:
        return ("!!! CẢNH BÁO: DỌN ẢNH TẠM ĐANG BẬT (--bat-don-anh) – ngay bây giờ và mỗi giờ sẽ XOÁ ảnh phiếu đã chốt / bị từ chối quá 24 giờ "
                "ở mọi kỳ thi không có \"[DEMO\" trong tên (kể cả kỳ thi thật). Ctrl+C ngay nếu không chủ ý.")
    return "Dọn ảnh tạm: TẮT (mặc định) – không xoá ảnh nào. Muốn bật: thêm --bat-don-anh."


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cong", type=int, default=mang.CONG_MAC_DINH)
    nhom = ap.add_mutually_exclusive_group()
    nhom.add_argument("--bat-don-anh", action="store_true", help="BẬT luồng dọn ảnh tạm (mặc định TẮT) – chỉ dùng khi chủ ý")
    nhom.add_argument("--khong-xoa-anh", action="store_true", help="(tương thích, giống mặc định) không chạy luồng dọn ảnh tạm")
    ap.add_argument("--chi-in", action="store_true", help="chỉ in địa chỉ / QR / lệnh tường lửa, không chạy máy chủ")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    in_huong_dan(a.cong, a.bat_don_anh)
    if a.chi_in:
        return 0
    os.chdir(ROOT)
    os.environ["SMART_EXAM_HOST"] = "0.0.0.0"
    os.environ["ANH_XOA_TU_DONG"] = "1" if a.bat_don_anh else "0"
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=a.cong)
    return 0


if __name__ == "__main__":
    sys.exit(main())
