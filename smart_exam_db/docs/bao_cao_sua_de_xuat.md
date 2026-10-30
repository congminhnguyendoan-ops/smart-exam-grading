# Đoạn sửa đề xuất cho `BaoCao_DoAnChuyenNganh.docx` (lệnh E, 28/10/2026)

Bản gốc (CHỈ ĐỌC, không sửa, không ghi đè): `C:\Users\MSI\Desktop\kì 7\đồ án chuyên ngành cntt\BaoCao_DoAnChuyenNganh.docx` (136 951 byte, sửa lần cuối 23/10).
Cách xuất: **đoạn Markdown kèm vị trí để dán tay** (người dùng chọn; không tạo `_sua.docx` vì sửa trực tiếp Word dễ vỡ định dạng/mục lục).
Vị trí: tìm theo **chuỗi trích dẫn** (chắc chắn nhất). Số `#n` = thứ tự phần tử trong thân tài liệu khi trích văn bản bằng script; chỉ để tham khảo, có thể lệch vài đơn vị so với Word.
Mọi số liệu có nguồn ở `docs/nhat_ky_sua_bao_cao.md`. Chỗ ghi `[ĐIỀN SAU – nhóm xác nhận: …]` = ô để nhóm điền một lần (danh sách đầy đủ ở `nhat_ky_sua_bao_cao.md`). Cập nhật theo lệnh E2 (28/10/2026).

---

## A. Sửa "23" → "22" (việc 1)

Chỉ có **một** chỗ ghi 23 trong báo cáo. Nguồn: `data/_eval/bao_cao_cuoi_tuan4.md`, bảng "Gộp dev + test", dòng `align_cu | Tổng | 90 | 68 | 22`;
= 19 (dev, 78 ảnh) + 3 (test, 12 ảnh: 0035_C3, 0038_C3, 0039_C3). Cũng khớp Bảng 3.6 của báo cáo (59/19/0 và 9/3/0).

| # | Vị trí | Trước | Sau |
|---|---|---|---|
| A1 | Mục 3.2.2 "Tiền xử lý ảnh", đoạn #133, câu "Khi thử trên 90 ảnh thật…" | "…hàm này nắn sai **23** ảnh nhưng vẫn báo thành công, tức là lỗi im lặng." | "…hàm này nắn sai **22** ảnh (19 ảnh phát triển và 3 ảnh kiểm tra) nhưng vẫn báo thành công, tức là lỗi im lặng." |

Đã rà các nơi có thể mang số này (tóm tắt Mở đầu #34, Bảng 3.6, đoạn nhận xét sau Bảng 3.6 #139/#143, Danh mục bảng): **không có chỗ nào khác ghi 23**; các chỗ còn lại đã dùng 19 + 3 hoặc 59/19/0 và 9/3/0, nhất quán với 22.

## B. Đồng bộ số kiểm thử (đã chốt theo lệnh E2)

Quy ước chốt: viết **"380 (tính đến 28/10/2026; 232 tại 21/10/2026)"** ở mọi chỗ liên quan, kèm một câu giải thích số tăng. Số 380 = `python -m pytest tests` chạy 28/10/2026 trên `cai-tien-b`: **380 đạt, 1 bỏ qua có chủ đích, 109,73 s**.

| # | Vị trí | Trước | Sau |
|---|---|---|---|
| B1 | Mục 1.5 "Phương pháp thực nghiệm", đoạn #56, câu cuối | "Toàn bộ mã nguồn có 232 kiểm thử tự động (pytest)." | "Toàn bộ mã nguồn có 380 kiểm thử tự động (pytest) đạt, 1 kiểm thử bỏ qua có chủ đích (tính đến 28/10/2026; 232 tại 21/10/2026). Số kiểm thử tăng do các cải tiến sau góp ý (đăng nhập và phân quyền, chụp bằng điện thoại, luật `vet_nho` và `to_nhat`, ma trận ô tô, môn và lớp) đều kèm kiểm thử mới." |
| B2 | Bảng 3.5, dòng "Kiểm thử" | "232 kiểm thử tự động (pytest)" | "380 kiểm thử tự động (pytest), 1 bỏ qua có chủ đích (tính đến 28/10/2026; 232 tại 21/10/2026)" |
| B3 | Mục 3.5.8 (bảng kiểm tra lại) và Kết luận Ý 1 | – | dùng đúng cách viết trên; Kết luận nêu "380 (tính đến 28/10/2026; 232 tại 21/10/2026)" |

## C. Mục mới (việc 5) — đặt sau mục 3.4.3 "Nhận xét", trước "KẾT LUẬN"

Đánh số **3.5**. Cập nhật Mục lục; thêm vào "Danh mục bảng" các bảng 3.15–3.16 bên dưới nếu giữ bảng.
Câu văn dùng giọng trung tính ("đề tài", "hệ thống"), không gán việc cho một người cụ thể; ngôi chung của báo cáo là **"nhóm"** (đồ án nhóm theo bìa), xem mục F.

### 3.5. Các cải tiến sau góp ý (27–28/10/2026)

Sau buổi góp ý, đề tài bổ sung bảy cải tiến trên nhánh `cai-tien-b`. Phần này ghi, với mỗi cải tiến: đã làm gì, đo được gì, giới hạn. Mọi số do script/tài liệu trong dự án tái tạo được; số đo điện thoại thật ghi rõ thiết bị và ngày đo. Kết quả kiểm tra cuối cả hệ thống ở mục 3.4 **không** được chạy lại sau các cải tiến này (xem 3.5.9).

**3.5.1. Hiển thị tên môn và tên lớp của kỳ thi**
- *Đã làm:* kỳ thi gắn với một môn và một lớp (thêm cột `exams.class_id` và bảng `teacher_classes`, migration 002). Tạo kỳ thi nhận `class_id` hoặc `class_code`; lớp phải có sẵn, hệ thống không tự tạo lớp (lớp không tồn tại → mã 422). Danh sách kỳ thi, bảng điểm và tệp Excel hiện môn và lớp (ô A4 "Môn:", ô F4 "Lớp:").
- *Đo được:* bộ kiểm quyền chỉ-đọc 24/24 đạt, trong đó có đọc chéo lớp trả 404 và `GET /exams` có môn và lớp (`docs/ke_hoach_cai_tien_27-10.md` mục 5a).
- *Giới hạn:* kỳ thi cũ tạo trước cải tiến không có lớp (cột cho phép NULL) nên chỉ hiện với người tạo; lớp là dữ liệu danh mục do quản trị tạo trước.

**3.5.2. Chụp bằng điện thoại và chấm ngay, gồm chụp liên tục**
- *Đã làm:* trang `/m` dùng camera gốc của điện thoại (`<input capture="environment">`, ảnh gốc không nén) gửi thẳng lên API chấm, hiện thẻ kết quả (điểm tạm, số câu cần xem, cảnh báo). Điện thoại không duyệt câu; giáo viên duyệt trên máy tính, danh sách tự làm mới mỗi 4 giây. Chế độ chụp liên tục dùng hàng đợi gửi nền (tối đa 2 yêu cầu song song), có "Gửi lại" khi lỗi mạng và "Chụp lại" khi ảnh bị từ chối. Công cụ `tools/chay_server_lan.py` chạy máy chủ trong mạng nội bộ, in địa chỉ và mã QR.
- *Đo được:*
  - Điện thoại thật qua Wi‑Fi, một tờ, một lần đo: **1,8 giây** từ lúc chụp đến lúc hiện kết quả. *(Đo trực tiếp ngày 27/10/2026 trên **một** iPhone, trình duyệt Safari, cùng Wi‑Fi với máy chủ; có ảnh chụp màn hình điện thoại và nhật ký làm việc 27/10. Chưa thử Android. `[ĐIỀN SAU – nhóm xác nhận: người đo]`)*
  - Cũng ngày 27/10 trên iPhone đó đã thử: chụp liên tục, chọn nhiều ảnh, chụp mờ bị từ chối kèm lý do, xuất Excel, và phân quyền (tài khoản gv_binh không xem được phiếu lớp K22A).
  - Giả lập Pixel 7 (ảnh 3024×4032, ~2,3 MB), chụp liên tục 20 tờ, mỗi 2 giây một tờ: **0 tờ lỗi**, thời gian xử lý mỗi tờ trung vị 0,79 s, p95 0,83 s, tổng 39,5 s (`docs/thiet_ke_chup_dien_thoai.md` mục 9; chạy qua mạng loopback, không gồm Wi‑Fi).
  - Rớt Wi‑Fi rồi gửi lại: khoảng **2 giây** (ước chừng, cùng lần thử 27/10 trên iPhone). Bản giả lập ngắt mạng 2 tờ: cả 2 tờ chấm được ở lần gửi lại thứ hai.
- *Giới hạn:* chạy bằng http trong mạng nội bộ (chưa HTTPS); điện thoại và máy tính phải cùng mạng, tường lửa phải mở cổng 8000 do người dùng tự thực hiện; camera trực tiếp bằng `getUserMedia` (tự bắt khung phiếu) mới được khảo sát, **chưa làm** (cần HTTPS); số đo điện thoại thật chỉ là **một thiết bị (iPhone/Safari), một tờ, một lần đo**; **chưa thử Android; chưa đo thời gian 40 tờ liên tục qua Wi‑Fi thật**. Ảnh tạm bị xoá sau 24 giờ khi chạy `chay_server_lan.py` không kèm `--khong-xoa-anh` (phiếu còn chờ duyệt và kỳ thi `[DEMO…]` được giữ).

**3.5.3. So sánh OCR với CNN đọc chữ số** (nguồn: `docs/so_sanh_ocr_cnn.md`, kể cả mục 5b; chỉ dùng dữ liệu phát triển, không chạm tập kiểm định/kiểm tra)
- *Đã làm:* đo ba ứng viên trên cùng tập và cùng thước đo: M0 (HOG + hồi quy logistic), CNN của hệ thống, và một thư viện OCR (mô hình nhận dạng PP‑OCRv6 chạy bằng onnxruntime, môi trường riêng, không huấn luyện thêm).
- *Đo được* (độ đúng chữ số, khoảng tin cậy Wilson 95%):

| Ứng viên | 504 chữ số trên phiếu dev (chưa mô hình nào học) | 3 872 chữ số trang D, người viết lạ | Tham số | Phụ thuộc thêm | Thời gian 9 chữ số |
|---|---|---|---|---|---|
| M0 | 92,1% [89,4–94,1] | 92,8% [92,0–93,6] | 3 250 | — | 0,59 ms |
| CNN (hệ thống hiện dùng) | 92,7% [90,0–94,6] | 95,8% [95,2–96,4] | 105 866 | — | 3,8 ms |
| OCR (PP‑OCRv6, ép chữ số) | **98,2% [96,6–99,1]** | **96,9% [96,3–97,4]** | ~5,3 triệu | ~71 MB | 54 ms |

  - OCR đúng hơn CNN có ý nghĩa thống kê: trên phiếu dev p < 0,001 (33 chữ số chỉ OCR đúng, 5 chỉ CNN đúng; số lỗi 37 → 9); trên trang D p = 0,003 (chênh nhỏ hơn: lỗi 161 → 121).
  - Giữa CNN và M0: trên phiếu dev không khác biệt (p = 0,78); trên trang D CNN tốt hơn (p < 0,001).
  - OCR lớn hơn nhiều: gấp ~50 lần số tham số, thêm ~71 MB thư viện và ~54 MB bộ nhớ, chậm hơn ~14 lần (54 ms so với 3,8 ms cho 9 chữ số). CNN hiện tại nhỏ: 0,4 MB trọng số, chỉ cần NumPy, ~17 ms cho cả phiếu.
  - Khi lắp vào hệ thống nguyên trạng (cùng luật đối chiếu hai kênh, ngưỡng τ = 0,5), cả ba ứng viên đều **0 lỗi im lặng** ở mức trường (112 trường SBD và mã đề), nhưng tỉ lệ ảnh có SBD hoặc mã đề cần xem của OCR là **53,6% (30/56), cao hơn 46,4% (26/56) của CNN**, dù OCR đọc đúng hơn. Tài liệu giải thích nguyên nhân là điểm tin cậy của OCR chưa hiệu chỉnh nên nhiều chữ số đúng bị coi là chưa chắc (28 chữ số đúng của OCR có p < 0,5, của CNN là 5).
  - Phép thử chẩn đoán (bỏ cổng tin cậy cho cả ba, không phải đề xuất áp dụng): T4 của OCR còn 16,1% (9/56), của CNN 42,9%. Tài liệu lưu ý cổng tin cậy có tác dụng chặn trường hợp thí sinh tô sai bubble mà chữ số đọc trùng ngẫu nhiên, và rủi ro này chưa đo được trên dữ liệu hiện có.
- *Kết luận của tài liệu nguồn:* bản bảo vệ giữ CNN (đã kiểm đầu–cuối, không thêm phụ thuộc); OCR là hướng cải tiến có số liệu, chỉ nên dùng sau khi hiệu chỉnh điểm tin cậy, chọn lại ngưỡng, mô phỏng rủi ro tô sai bubble và đánh giá lại theo đăng ký mới.
- *Giới hạn:* tập phiếu dev chỉ 504 chữ số của 4 người viết (252 cặp ảnh cùng phiếu, không hoàn toàn độc lập); tập này từng được dùng ở Tuần 6 để so các cấu hình CNN nên có thể hơi lạc quan cho CNN; chỉ đo một thư viện OCR, không đo Tesseract; thời gian đo trên một máy; chưa đo trên tập kiểm định hay kiểm tra, nên "OCR đúng hơn" mới là kết luận ở mức dữ liệu phát triển.

**3.5.4. Phủ các trường hợp ô tô** (nguồn: `docs/ke_hoach_cai_tien_27-10.md` mục 6; `tests/test_omr_ma_tran_o_to.py`)
- *Đã làm:* bộ kiểm thử ma trận vẽ ô bằng điểm ảnh thật với mức xám cho trước (0–255), chạy qua cả chuỗi `doc_phieu`: một ô, một đậm một nhạt, 2–4 ô cùng mức, vùng tô to nhỏ, 40 câu đủ, chấm nhỏ. Bổ sung luật `vet_nho` (ô không được chọn mà có khối tối đặc ≥ 90 px sau phép mở 7×7 → câu cần xem; lấp lỗ hổng "chấm nhỏ đậm bị đọc là trống mà không báo") và luật mức tờ `to_nhat` (tờ tô nhạt cả tờ → mọi câu đã chọn cần xem). Cả hai luật chỉ cộng cờ "cần xem", không đổi đáp án máy đọc, không đổi tệp mô hình.
- *Đo được* (56 ảnh phát triển, tiêu chí chốt trước khi sửa mã): lỗi nặng 0; "cần xem thừa" ở câu rõ một ô không đổi (C1/C2/C3/C4 = 0,27 / 2,71 / 1,10 / 2,19%); `vet_nho` gắn cờ 0 câu thật, `to_nhat` gắn 0/56 phiếu thật; chấm giả bán kính ≥ 0,3r gắn cờ 100%; điểm chính thức khớp độc lập 56/56. Bộ kiểm thử ma trận ô tô hiện có **32 ca** (đếm lại 28/10/2026: `python -m pytest --collect-only -q tests/test_omr_ma_tran_o_to.py` → "32 tests collected"; gồm 22 ca ban đầu và 10 ca của luật `to_nhat`).
- *Giới hạn:* phép thử vẽ giả phẳng, chưa có nhiễu thật; tờ nhạt thật chưa từng có trong dữ liệu phát triển nên luật `to_nhat` chưa được thử trên tờ nhạt thật; `to_nhat` chỉ bắt tờ có độ tối trung vị T < 0,44, tờ nhạt vừa (T 0,44–0,53) chưa bắt được; luật `vet_nho` **chưa áp dụng cho bubble SBD và mã đề** (nợ kỹ thuật đã biết, hai kênh bubble + chữ viết tay vẫn đối chiếu nhau); chấm rất nhỏ (< ~0,15 bán kính) và chấm nhạt hơn 0,6 lần giấy vành không bị bắt; bút chì nhạt xem 3.5.6.

**3.5.5. Chấm đủ 40 câu**
- *Đã làm:* bộ demo bảo vệ `[DEMO-BV]` với 4 mã đề 40 câu và 10 kịch bản tô (BV01–BV10) gồm tô đủ 40 câu, tờ nhạt, SBD ngoài danh sách; hai kỳ thi mẫu của hai giáo viên. Bổ sung test "đủ 40 câu mỗi câu một đáp án khác nhau" và "40 câu xen kẽ rõ/mờ/trống/nhiều ô".
- *Đo được:* chạy ảnh giả hoá qua API thật (có đăng nhập, giao dịch hoàn tác): **10/10 kịch bản khớp**, 0 câu chấm sai không cờ; BV07 (tờ nhạt) → 40 câu có cờ `to_nhat`; BV10 không ghi điểm vì SBD không thuộc danh sách dự thi (đúng thiết kế).
- *Giới hạn:* ảnh demo là ảnh giả hoá phẳng, không có chữ viết tay, chỉ minh hoạ luồng; trên ảnh thật khoảng một nửa số phiếu vẫn có SBD hoặc mã đề cần xem (chỉ báo T4, mục 3.4).

**3.5.6. Rà soát tô đậm/nhạt trên thang 0–255**
- *Đã làm:* rà mã đo độ tối (`1 − trung bình lõi / giấy vành`) và đo phân bố trên 56 ảnh phát triển (`tools/omr_s_anh.py`). Phát hiện: ranh giới rõ/mờ/trống phụ thuộc độ đậm chung của chính tờ phiếu, nên trên tờ tô toàn bút chì nhạt, một vệt nhạt lạc có thể bị đọc là "rõ" mà không gắn cờ.
- *Đo được:* thang độ tối của tờ (`S_anh`) từ 0,400 đến 0,804, trung vị 0,682, không ảnh nào chạm sàn 0,20. Thử luật ngưỡng độ tối tuyệt đối với tiêu chí chốt trước: **không có ngưỡng nào thoả đồng thời** (bắt vệt xám 150 cần ngưỡng > 0,412, kéo C2 thừa +13 câu = +3,5 điểm %, vượt mức cho phép +1,0). Đề tài không nới tiêu chí và không sửa mã theo hướng này; thay vào đó dùng luật mức tờ `to_nhat` (3.5.4).
- *Giới hạn:* nợ kỹ thuật "thang phụ thuộc cả tờ" vẫn còn; dữ liệu phát triển không có tờ nhạt thật nên kiểm tra tiếp bằng phiếu 0105 (tô nhạt cả tờ) ở đợt 2, chỉ báo cáo, không chỉnh mã theo kết quả.

**3.5.7. Đăng nhập giáo viên và phân quyền theo lớp**
- *Đã làm:* đăng nhập bằng tài khoản (mật khẩu băm scrypt, phiên là cookie HttpOnly, SameSite=Lax); quyền: quản trị xem tất cả, giáo viên chỉ thấy lớp mình phụ trách và kỳ thi mình tạo, sinh viên không dùng được API chấm (403), ngoài quyền trả 404 như không tồn tại, chưa đăng nhập trả 401; sai mật khẩu 5 lần trong 15 phút bị khoá tạm (429) và mọi lỗi đăng nhập cùng một thông báo. Có công cụ quản lý tài khoản dòng lệnh.
- *Đo được:* 3 kiểm thử tự động quét **toàn bộ route**: mọi route (trừ công khai) phải yêu cầu đăng nhập, mọi route trừ `/me*` chặn sinh viên, mọi route có mã kỳ thi/phiếu/lớp phải gọi hàm kiểm quyền — thêm route mới mà quên thì kiểm thử đỏ. Bộ kiểm quyền thật 24/24 đạt (3.5.1).
- *Giới hạn:* chạy http nội bộ nên cookie chưa đặt cờ Secure; giới hạn thử sai lưu trong bộ nhớ tiến trình (khởi động lại thì đếm lại); chưa có CSRF token riêng (dựa SameSite=Lax); trang tĩnh `/app/` công khai (chỉ mã giao diện); chế độ `AUTH_MODE=demo` không kiểm quyền, chỉ dùng khi phát triển. Một sự cố đã ghi nhận: ngày 27/10 migration 002 vô tình được áp lên CSDL thật khi chạy kiểm thử; chỉ thêm cột/bảng, không mất dữ liệu; đã sửa để kiểm thử không tự áp migration (`docs/thiet_ke_dang_nhap.md` mục 8).

**3.5.8. Kết quả kiểm tra lại sau cải tiến (chạy 28/10/2026, nhánh cai-tien-b)**

| Hạng mục | Kết quả | Nguồn |
|---|---|---|
| `python -m pytest tests` | **380 đạt, 1 bỏ qua có chủ đích**, 109,73 s | chạy lại 28/10/2026 |
| Hồi quy đầu–cuối `tools/kiem_backend_dau_cuoi.py` (56 ảnh phát triển, giao dịch hoàn tác) | điểm chính thức khớp điểm tính độc lập **56/56**; 0 câu chấm sai không cờ trên 1 680 câu chắc chắn; 0 SBD/mã đề sai im lặng; câu cần xem 560/2 240 (25,0%); ảnh có SBD/mã đề cần xem 26/56 (46,4%) | chạy lại 28/10/2026 |

**3.5.9. Điều chưa làm hoặc đang chờ**
- *Đợt 2 (phiếu 0101–0110, chụp bằng điện thoại, mã đóng băng):* **đang chờ chạy** — ô cập nhật: `[kết quả đợt 2: ……]`. Chưa có số nào được báo cáo cho đợt này.
- Kết quả kiểm tra cuối 21/10 (mục 3.4) là của phiên bản mã **trước** luật `vet_nho` và `to_nhat`; không chạy lại, và nếu cần kiểm lại thì phải đăng ký tiêu chí mới (`docs/ke_hoach_cai_tien_27-10.md` mục 6.3).
- Nợ kỹ thuật: `vet_nho` cho bubble; thang `S_anh` phụ thuộc cả tờ; hiệu chỉnh OCR (3.5.3); camera trực tiếp (3.5.2); bảng điểm chưa cảnh báo phiếu thứ hai cùng SBD đang chờ (`docs/so_sanh_ocr_cnn.md` mục 7).

## D. Phần "KẾT LUẬN" (việc 2) — thay hai dòng tiêu đề trống "Ý 1" và "Ý 2"

> Chỉ dùng số đã đo ở mục 3.4 và 3.5. Đợt 2 chưa chạy → ghi "đang chờ".

**Ý 1: Đề tài đã làm được gì**

Đề tài xây dựng được hệ thống chấm thi trắc nghiệm chạy trọn vòng từ ảnh chụp bằng điện thoại đến bảng điểm Excel: nắn phẳng ảnh phiếu, đọc 40 câu bằng mô hình hồi quy logistic, đọc SBD và mã đề bằng hai kênh độc lập (CNN chữ viết tay và ô tô) rồi đối chiếu, chấm điểm tạm, để giáo viên duyệt các chỗ máy không chắc, lưu điểm chính thức vào PostgreSQL. Nguyên tắc "AI hỗ trợ, con người kiểm soát" được giữ ở mọi khâu: chỗ nào không chắc thì gắn cờ "cần xem" thay vì đoán.

Về an toàn, trên tập kiểm tra cuối (12 ảnh của 6 phiếu, chạy một lần theo tiêu chí đăng ký trước) cả năm tiêu chí bắt buộc H1–H5 đều đạt: nắn ảnh đúng 12/12 (bản nắn cũ chỉ đúng 9/12, lỗi im lặng 3/12; gộp cả tập phát triển, bản cũ nắn sai im lặng 22/90 ảnh, bản mới 0/90), lỗi nặng của OMR 0/588 (cận trên 95% là 0,63%), không SBD hay mã đề nào nhận sai, không câu nào chấm sai mà không gắn cờ, điểm chính thức sau duyệt khớp điểm tính độc lập 12/12. Sau các cải tiến 27–28/10, kiểm tra lại cho kết quả: 380 kiểm thử tự động đạt (1 bỏ qua có chủ đích; tính đến 28/10/2026, còn 232 tại 21/10/2026, số tăng do các cải tiến đều kèm kiểm thử mới) và điểm chính thức khớp 56/56 trên tập phát triển.

Sau góp ý, hệ thống được bổ sung: tên môn và lớp của kỳ thi, chụp bằng điện thoại và chấm ngay (kể cả chụp liên tục; một lần đo trên một iPhone thật, ngày 27/10/2026, từ chụp đến hiện kết quả là 1,8 giây), đăng nhập giáo viên và phân quyền theo lớp, bộ kiểm thử các trường hợp ô tô thang 0–255 cùng hai luật cảnh báo mới (`vet_nho`, `to_nhat`), và phép so sánh OCR với CNN trên dữ liệu phát triển.

**Những chỉ báo chưa đạt (ghi nguyên trạng):** độ đúng chữ số của CNN 92,6% (mục tiêu ≥ 97%); tỉ lệ ảnh có SBD hoặc mã đề cần xem 58,3% (mục tiêu ≤ 10%); "cần xem thừa" ở câu rõ một ô 3,68% (mục tiêu ≤ 3%); F1 lớp ô tô mờ gộp 0,897 (mục tiêu ≥ 0,90), riêng điều kiện thiếu sáng C2 là 0,70. Các chỉ số này ảnh hưởng khối lượng việc của giáo viên chứ không gây ghi sai điểm.

**Ý 2: Hạn chế và hướng phát triển**

*Hạn chế.* Tập kiểm tra chỉ có 12 ảnh của 6 phiếu, toàn bộ một người viết, kỳ thi và đáp án là mô phỏng nên khoảng tin cậy rộng. Kết quả kiểm tra cuối 21/10 là của phiên bản trước luật `vet_nho` và `to_nhat`; kiểm lại cần đăng ký tiêu chí mới. Hệ thống chạy trong mạng nội bộ qua http; số đo điện thoại thật mới là một tờ, một lần, trên một thiết bị (iPhone/Safari), chưa thử Android và chưa đo 40 tờ liên tục qua Wi‑Fi thật. Luật `vet_nho` chưa áp dụng cho SBD và mã đề; tờ tô nhạt cả tờ chưa từng được thử với ảnh thật. Phép so sánh OCR chỉ ở mức dữ liệu phát triển.

*Đang chờ.* Kiểm tra đợt 2 (phiếu 0101–0110, chụp bằng điện thoại, trên mã đã đóng băng): **đang chờ chạy**. Ô cập nhật: `[kết quả đợt 2 và nhận xét: ……]`.

*Hướng phát triển.* (1) Thay kênh chữ viết tay bằng OCR sau khi hiệu chỉnh điểm tin cậy, chọn lại ngưỡng, mô phỏng rủi ro tô sai bubble và đánh giá lại; vẫn giữ quy tắc chỉ nhận khi hai kênh khớp. (2) Thu thêm người viết để cải thiện độ đúng chữ số với người viết lạ. (3) Áp luật `vet_nho` cho SBD, mã đề và xử lý nợ thang độ tối phụ thuộc cả tờ. (4) Camera trực tiếp bằng `getUserMedia` (cần HTTPS). (5) Cảnh báo trên bảng điểm khi có phiếu thứ hai cùng SBD đang chờ duyệt. (6) Lưu các lần giáo viên sửa làm dữ liệu huấn luyện thêm.

## E. Chú thích lược đồ CSDL/ERD và số bảng thật (đã chốt theo lệnh E2)

**Số liệu đếm từ CSDL thật** (chỉ `SELECT` trên `information_schema.tables`, schema `public`, kết nối chỉ-đọc, 28/10/2026; không ghi, không migration):
**30 đối tượng = 22 bảng + 8 view.**

| Nhóm | Số | Tên |
|---|---|---|
| Bảng nghiệp vụ gốc (ERD thiết kế) | **20** | `answer_keys`, `answer_sheets`, `classes`, `exam_codes`, `exam_students`, `exams`, `ml_models`, `ocr_digits`, `questions`, `results`, `review_queue`, `scan_batches`, `score_audit_logs`, `sheet_answers`, `sheet_templates`, `student_imports`, `students`, `subjects`, `system_settings`, `users` |
| Bảng nghiệp vụ thêm sau cải tiến (migration 002) | **1** | `teacher_classes` (quan hệ giáo viên–lớp) |
| Bảng kỹ thuật | **1** | `schema_migrations` (3 dòng: 001, 002, 003) |
| View | **8** | `v_exam_results`, `v_exam_summary`, `v_missing_results`, `v_ocr_correction_stats`, `v_question_difficulty`, `v_review_pending`, `v_score_distribution`, `v_student_transcript` |

Đối chiếu migration 001–003 (`backend/migrations/`): 001 chỉ thêm cột/chỉ mục vào `sheet_answers` (`needs_review`, `review_reasons`, `omr_state`, `omr_selected_options`, `reviewed_by`, `reviewed_at`) và `answer_sheets` (`reject_code`, `omr_detail`, `original_filename`); **002 thêm bảng `teacher_classes` + cột `exams.class_id`** (+ chỉ mục); **003 thêm cột `answer_sheets.image_deleted_at`** (+ chỉ mục). Kiểm tra trực tiếp: `exams.class_id` và `answer_sheets.image_deleted_at` đều tồn tại. Không bảng nào ngoài `teacher_classes` và `schema_migrations` được thêm bằng migration: 22 − 20 = 2, khớp.
ERD gốc (20 bảng) **không đổi**.

**Cách viết trong báo cáo (vị trí: mục 3.1.4, đoạn #121 và ngay sau Bảng 3.4):**
- Đoạn #121: giữ "20 bảng" cho thiết kế ban đầu và thêm: "…gồm 20 bảng nghiệp vụ theo thiết kế ban đầu; sau các cải tiến 27–28/10/2026, cơ sở dữ liệu có thêm bảng nghiệp vụ `teacher_classes` và bảng kỹ thuật `schema_migrations` (tổng 22 bảng, 8 khung nhìn)."
- Bảng 3.4, nhóm "Người dùng": thêm `teacher_classes (thêm sau cải tiến)`. Chú thích dưới bảng:

> **Chú thích.** `schema_migrations` là bảng kỹ thuật theo dõi các tệp migration đã được áp (mỗi dòng ghi tên một tệp), giúp chạy lại lệnh migrate nhiều lần mà không áp trùng; bảng này không thuộc nghiệp vụ chấm thi và không có trong ERD. Bảng `teacher_classes` và các cột `exams.class_id`, `answer_sheets.image_deleted_at` (cùng các cột bổ sung ở `sheet_answers` và `answer_sheets` từ migration 001) được thêm sau khi vẽ ERD gốc nên ERD 20 bảng không thể hiện; ERD gốc được giữ nguyên.

## F. Ngôi "nhóm" và phân công (đã chốt theo lệnh E2: đồ án NHÓM, theo bìa)

**Quy ước:** thống nhất ngôi **"nhóm"** toàn báo cáo; câu hay bảng gán một người cụ thể cho một phần việc → thay bằng câu trung tính hoặc ô `[ĐIỀN SAU – nhóm xác nhận: …]`. Không điền tên, không suy từ lịch sử commit. Giữ nguyên sự thật: **cả nhóm tham gia thu dữ liệu (tô và viết phiếu); đợt 2 do 5 người cùng tô.** `CLAUDE.md` không sửa.

| # | Chỗ (mục / đoạn) | Trước | Sau |
|---|---|---|---|
| 1 | Bìa; Danh sách nhóm (bảng 5 thành viên, cột Ghi chú "Nhóm Trưởng") | Nhóm 12, 5 thành viên | **Giữ nguyên** (sự thật trên bìa; vai trò nhóm trưởng không phải phân công kỹ thuật) |
| 2 | `CLAUDE.md` mục 1 ("làm cá nhân") | – | **Không sửa** theo yêu cầu; chỉ ghi nhận là chỗ lệch với bìa |
| 3 | #33, #49, #50, #54, #55, #56, #111, #115, #151, #160, #164 ("nhóm tự thiết kế…", "nhóm thu 40 phiếu"…) | "nhóm" | **Giữ nguyên** – đã đúng ngôi; không câu nào nêu tên người |
| 4 | Mục 3.4.1 (#191) và 3.4.2 (#193) | "Người thực hiện xem mù ảnh trước, kết luận bằng mắt rồi mới mở kết quả của máy." / "kết luận bằng mắt của người thực hiện" | "Ảnh được xem mù trước: nhóm ghi kết luận bằng mắt rồi mới mở kết quả của máy." / "kết luận bằng mắt của nhóm". Ô điền: `[ĐIỀN SAU – nhóm xác nhận: thành viên xem mù ảnh kiểm tra cuối]` (đặt trong ngoặc ở cuối #191 nếu cần nêu tên) |
| 5 | #204 | "toàn bộ do một người viết" | "toàn bộ do một người viết tay" (làm rõ đây là dữ liệu, không phải phân công) |
| 6 | Văn phong "em" (`so_sanh_ocr_cnn.md` mục 5b) | "CNN của em…" | Không dán nguyên vào báo cáo; mục 3.5.3 đã viết ở giọng trung tính. (`so_sanh_ocr_cnn.md` là tài liệu nội bộ, không đổi) |
| 7 | 5 tờ thuyết trình theo từng thành viên (ngoài báo cáo) | – | Không thuộc báo cáo, không sửa; chỉ nhắc: phần phân công của báo cáo cần khớp các tờ này |
| 8 | Mục 3.5.2 (đo điện thoại) | – | Ghi "đo trực tiếp ngày 27/10/2026 trên một iPhone", không nêu ai đo. Ô điền: `[ĐIỀN SAU – nhóm xác nhận: người đo]` |
| 9 | **Mới** – bảng "Phân công công việc" (đề xuất đặt cuối Chương 1, sau mục 1.6, hoặc Phụ lục) | (chưa có) | Bảng bên dưới, mọi ô người phụ trách để trống trừ hai sự thật đã biết |

Bảng đề xuất (mục 9):

| Hạng mục | Người phụ trách |
|---|---|
| Thiết kế phiếu và bố cục | `[ĐIỀN SAU – nhóm xác nhận]` |
| Thu dữ liệu: tô và viết phiếu | Cả nhóm cùng tham gia |
| Chụp ảnh phiếu | `[ĐIỀN SAU – nhóm xác nhận]` |
| Tiền xử lý ảnh (nắn phẳng) | `[ĐIỀN SAU – nhóm xác nhận]` |
| Nhận dạng ô tô (OMR) | `[ĐIỀN SAU – nhóm xác nhận]` |
| Nhận dạng chữ số (CNN) và so sánh OCR | `[ĐIỀN SAU – nhóm xác nhận]` |
| Cơ sở dữ liệu | `[ĐIỀN SAU – nhóm xác nhận]` |
| Backend, đăng nhập và phân quyền | `[ĐIỀN SAU – nhóm xác nhận]` |
| Giao diện web và trang điện thoại | `[ĐIỀN SAU – nhóm xác nhận]` |
| Đánh giá, kiểm thử, xem mù | `[ĐIỀN SAU – nhóm xác nhận]` |
| Kiểm tra đợt 2 (tô phiếu) | Cả 5 thành viên cùng tô |
| Viết báo cáo | `[ĐIỀN SAU – nhóm xác nhận]` |

## G. Điều còn chưa kiểm chứng

1. **Số đo điện thoại thật (1,8 s; ~2 s):** nguồn do người dùng khai (đo trực tiếp 27/10/2026, một iPhone/Safari, cùng Wi‑Fi; có ảnh chụp màn hình điện thoại và nhật ký làm việc 27/10). Hai thứ đó không nằm trong dự án (không thấy trong `data/_eval/ui_m/` hay `docs/`) nên tôi chưa tự đối chiếu được; "~2 s" là ước chừng. Các tài liệu `docs/` còn ghi "CHƯA thử điện thoại thật" đã được sửa cho khớp (xem nhật ký).
2. Chưa thử Android; chưa đo 40 tờ liên tục qua Wi‑Fi thật.
3. Đã bỏ cụm "ma trận 16 nhóm"; số thật là 32 ca (đã đếm lại).
4. Các ô `[ĐIỀN SAU]` còn trống – chờ nhóm.
