# Khảo sát: camera trực tiếp trong trình duyệt (getUserMedia) – chụp liên tục, tự bắt khung phiếu (27/10/2026)

**CHỈ KHẢO SÁT – chưa cài gì, không đổi cấu hình máy / mạng.** Hiện trạng (lệnh M Phần 1): `/m` mở **ứng dụng camera gốc** qua `<input capture>` (chạy trên http),
ảnh vào hàng đợi gửi nền – giáo viên không phải chờ kết quả. Mỗi tờ vẫn cần ~2 lần chạm trên điện thoại (nút chụp của camera + "Dùng ảnh" / "OK") và camera mở lại mỗi tờ.
Ghi chú độ tin cậy: mục đánh dấu **[cần thử]** là hành vi trình duyệt tôi KHÔNG kiểm được ở đây (khi viết khảo sát này không có điện thoại thật; từ 27/10/2026 đã thử luồng `capture` trên một iPhone nhưng CHƯA thử `getUserMedia`) – phải thử trên đúng máy trước khi dựa vào.

## 1. Vì sao cần HTTPS
`navigator.mediaDevices.getUserMedia` chỉ có trong **ngữ cảnh an toàn** (secure context): `https://…` hoặc `http://localhost`. Trang `http://192.168.1.142:8000/m`
KHÔNG phải ngữ cảnh an toàn → `navigator.mediaDevices` là `undefined` trên cả iPhone Safari lẫn Chrome Android. `<input capture>` hiện tại không bị giới hạn này.

## 2. Phương án A – HTTPS cục bộ cho LAN (khuyến nghị nếu làm)
**Các bước** (sau buổi bảo vệ; mọi bước đổi cấu hình do người dùng tự làm):
1. Cài `mkcert` (một tệp .exe) → `mkcert -install` tạo **CA gốc cục bộ** và đưa vào kho tin cậy của Windows (ĐỔI CẤU HÌNH HỆ THỐNG).
2. `mkcert 192.168.1.142 localhost 127.0.0.1` → `…pem` + `…-key.pem` (chứng chỉ ghi đúng IP trong SAN).
3. Chạy `uvicorn … --ssl-certfile … --ssl-keyfile …` (cần thêm cờ cho `chay_server_lan.py`), đặt `COOKIE_SECURE=1`; QR trỏ `https://<IP>:8000/m`.
4. Điện thoại tin CA gốc (`rootCA.pem` của mkcert, chép sang máy – KHÔNG chép `rootCA-key.pem`):
   - **iPhone**: mở tệp → Cài đặt → "Đã tải về hồ sơ" → Cài đặt; rồi Cài đặt → Cài đặt chung → Giới thiệu → **Cài đặt tin cậy chứng nhận** → bật tin cậy hoàn toàn cho CA đó.
   - **Android**: Cài đặt → Bảo mật → Mã hoá & thông tin xác thực → Cài đặt chứng chỉ → **Chứng chỉ CA**. Chrome Android tin CA do người dùng cài [cần thử theo hãng máy].
5. Sau buổi demo: gỡ hồ sơ / chứng chỉ CA trên điện thoại; `mkcert -uninstall` trên máy tính.

**Bỏ qua cảnh báo thay vì cài CA (chứng chỉ tự ký, không tin cậy)**:
- Chrome Android: "Nâng cao → Tiếp tục (không an toàn)" mở được trang; trang vẫn là https nên **thường** có getUserMedia, nhưng trình duyệt đánh dấu "Không an toàn",
  quyền camera có thể bị hỏi lại mỗi lần [cần thử].
- iPhone Safari: "Hiển thị chi tiết → truy cập trang web này" mở được trang; camera sau khi bỏ qua cảnh báo **không chắc** hoạt động ổn định [cần thử] → với iPhone nên cài CA (bước 4).
**Rủi ro**: khoá riêng của CA cục bộ nằm trên laptop – lộ ra thì ai có nó có thể giả mạo MỌI trang https với điện thoại đã tin CA đó → nhất định gỡ sau demo;
chứng chỉ gắn với IP – đổi Wi‑Fi / hotspot (IP mới) phải tạo lại chứng chỉ (hoặc ghi sẵn nhiều IP); thêm bước cài đặt trên từng điện thoại (dễ hỏng ngay trước buổi bảo vệ).

## 3. Phương án khác
| Phương án | Ưu | Nhược | Kết luận |
|---|---|---|---|
| **Tunnel công khai** (Cloudflare Tunnel `trycloudflare.com`, ngrok…) | HTTPS hợp lệ ngay, không cài gì lên điện thoại | Đưa server ra **Internet** (trái nguyên tắc chỉ LAN đã chốt); ảnh phiếu + điểm đi qua bên thứ ba; cần Internet ổn định tại phòng bảo vệ; ảnh 2–4 MB đi vòng Internet → chậm; URL ngẫu nhiên đổi mỗi lần | **Không nên** (kể cả cho demo) |
| **Cờ Chrome Android** `chrome://flags` → "Insecure origins treated as secure" → thêm `http://192.168.1.142:8000` | Không cần chứng chỉ; getUserMedia chạy trên http | Chỉ Chrome Android, chỉ máy đã bật cờ; cờ thử nghiệm có thể bị bỏ; không có cho iPhone | Chấp nhận được **chỉ để thử nghiệm** trên một máy Android của người làm |
| `http://localhost` qua cáp USB (`adb reverse tcp:8000 tcp:8000`) | localhost là ngữ cảnh an toàn, không chứng chỉ | Cần cáp + bật gỡ lỗi USB + adb; chỉ Android | Tiện để PHÁT TRIỂN, không hợp để demo |
| Ứng dụng gốc / PWA đóng gói | Camera đầy đủ, chụp liên tục thật | Ngoài phạm vi đồ án, nhiều tuần | Không |

## 4. Ước lượng: "bấm một lần, chụp liên tục, tự bắt khung phiếu" trong trình duyệt
Việc cần làm: (1) HTTPS (mục 2); (2) màn camera `getUserMedia` (camera sau, độ phân giải cao nhất xin được); (3) dò 4 marker trên khung hình thu nhỏ bằng JS thuần (ngưỡng + thành phần liên
thông – không dùng OpenCV.js ~8 MB) + kiểm "đứng yên" vài khung liên tiếp; (4) tự chụp: Chrome Android có `ImageCapture.takePhoto()` (ảnh độ phân giải cảm biến) nhưng
**iPhone Safari không có** → chỉ lấy được khung **video** (thường ≤ 1920×1080 hoặc 4K tuỳ máy [cần thử]); (5) chống chụp trùng: chờ marker biến mất / nội dung đổi trước khi chụp tờ kế;
(6) đưa vào hàng đợi hiện có (Phần 1 dùng lại được nguyên).
**Rủi ro lớn nhất – độ chính xác**: ảnh từ khung video (~1920 px cạnh dài ≈ 160 DPI trên A4, so với ~12 MP ≈ 340 DPI hiện nay) chưa từng được đánh giá với OMR + CNN chữ số;
nén video, tự lấy nét / phơi sáng liên tục làm mờ nhoè. Muốn dùng phải đánh giá lại trên dev (và nếu đổi gì trong `cv_engine` thì vi phạm đóng băng đợt 2 / cần đăng ký mới).
**Công sức ước lượng**: 3–5 ngày làm + 1–2 ngày thử trên ≥ 2 điện thoại thật (iPhone + Android) + đánh giá độ chính xác ảnh video (1–2 ngày). Rủi ro: trung bình–cao.

## 5. Kết luận
**KHÔNG nên làm trước buổi bảo vệ.** Phần 1 (hàng đợi + camera gốc) đã bỏ được thời gian chờ chấm – thứ chiếm nhiều thời gian nhất; phần còn lại (2 chạm / tờ, ~3–5 s / tờ
⇒ ~2–3 phút cho 40 tờ) chấp nhận được. Camera trực tiếp cần thêm HTTPS + cài chứng chỉ trên từng điện thoại (dễ hỏng ngay trước buổi bảo vệ) và – quan trọng hơn –
chất lượng ảnh khung video chưa được kiểm chứng với OMR / CNN. Ghi vào báo cáo như **hướng phát triển**: HTTPS cục bộ (mkcert) → getUserMedia → tự bắt 4 marker → đánh giá lại độ chính xác.
