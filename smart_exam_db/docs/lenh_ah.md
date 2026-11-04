# Lệnh AH – Nhiều tài khoản đăng nhập + chấm đồng thời (04/11/2026, nhánh `hoan-thien`)

**Chỉ đọc mã + thử thật. KHÔNG sửa mã hệ thống** (backend/, cv_engine/, models/, tệp đóng băng). Công cụ: `tools/ah_thu_dong_thoi.py`.
Kết quả thô (không vào git): `data/_eval/ah/ket_qua_lan1.json`, `ket_qua_lan2.json`, `may_chu_lan{1,2}.log`.

## 1. Cách thử

- Máy chủ thử **riêng**: uvicorn cổng **8010**, 1 tiến trình, `AUTH_MODE=on`, `ANH_XOA_TU_DONG=0`, `STORAGE_DIR=data/_eval/ah/kho`; **cùng CSDL** `smart_exam`.
- Dữ liệu thử tạo mới, ghi hồ sơ `data/_eval/ah/ho_so.json`, **dọn trong `finally`**: 3 giáo viên `ah_thu_1..3` (mật khẩu ngẫu nhiên, không in), 4 lớp `AH-THU-L1/L2/L3/LD`
  (LD = lớp chung của GV1 + GV2), môn `AHTHU`, 8 kỳ thi `[AH-THU] …` (mỗi GV: 1 kỳ thi đồng thời + 1 kỳ thi đối chứng tuần tự; XD chung GV1+GV2; XR thang tải), 138 thí sinh mã `97xxxx`.
  Lệch so với đề bài "2 lớp, 2 kỳ thi": cần lớp riêng cho mỗi GV (kịch bản C) **và** một lớp chung (kịch bản D), và kỳ thi đối chứng riêng (cùng ảnh không tải lại được vào cùng kỳ thi – chống trùng theo SHA).
  `gv_thu` và mọi tài khoản thật **không dùng, không đổi**.
- Ảnh: ảnh GIẢ HOÁ vẽ trên mẫu phiếu trắng (như `thu_bo_demo.py`; không chữ viết tay) – đủ để thử đồng thời, **không** phải số đo độ chính xác.
  Ảnh "sạch" (mọi câu một ô đậm, SBD trong danh sách) phải được chấm tự động với điểm = số câu đúng × 0,25 – kiểm độc lập theo cách vẽ.
- HTTP thật (httpx, luồng thật, `threading.Barrier` cho "cùng lúc"); mỗi GV 2 luồng như `/m` (tối đa 2 ảnh song song).
- Chạy **2 lần** (máy 16 luồng CPU, Python 3.14.7 có GIL). Lần 1 nhóm B bị chậm bất thường (xem mục 3) – ghi cả hai.

```powershell
python tools/ah_thu_dong_thoi.py chay     # dựng -> A, B, C, D (+D-ép, D-ảnh trùng, D-lô chéo), E (+thang tải) -> dọn -> data/_eval/ah/ket_qua.json
python tools/ah_thu_dong_thoi.py dem      # đếm dữ liệu thử còn sót (chỉ đọc)
python tools/ah_thu_dong_thoi.py don      # dọn riêng (nếu lần chạy bị ngắt)
```

## 2. Kết quả

| Kịch bản | Lần 1 | Lần 2 | Ghi chú |
|---|---|---|---|
| **A** đăng nhập đồng thời + 5 lần sai | ĐẠT | ĐẠT | 3 GV + GV1 trình duyệt thứ hai + phiên cũ của GV3, cùng lúc GV3 bị sai 5 lần: không lẫn phiên (`/me`, `/exams`, `/me/classes` đúng người); GV1/GV2 đăng nhập lại 200; GV3 cùng IP → **429**, phiên cũ của GV3 vẫn 200; GV3 từ IP 127.0.0.2 → 200 (khoá theo **tên + IP**) |
| **B** 3 GV × 6 ảnh cùng lúc | ĐẠT | ĐẠT | 18/18 HTTP 201, 0 lỗi 500, 0 deadlock; **18/18 trùng khít** chạy tuần tự (trạng thái, điểm tạm, điểm chính thức, SBD, mã đề, từng câu); 12 graded + 6 needs_review đúng kỳ vọng |
| **C** cô lập dữ liệu | ĐẠT | ĐẠT | 310 yêu cầu sang kỳ thi / phiếu / ảnh / ô viết tay / bảng điểm / Excel / trang bìa / lớp / duyệt / sửa SBD / tải ảnh của người khác: **310/310 = 404**, 0 tên / SBD rò, 0 phiếu lạ được tạo |
| **D** 2 GV cùng tải 2 ảnh CÙNG SBD (20 lần) | ĐẠT | ĐẠT | **0/40 lần có hai điểm chính thức**. Nhưng **13/20 và 17/20 lần**: yêu cầu thua nhận **409** "Vi phạm ràng buộc dữ liệu: … uq_results_exam_student" và phiếu đó **không được lưu** (mất, phải tải lại); các lần còn lại phiếu thứ hai vào hàng đợi `duplicate_sbd` (đúng thiết kế F2) |
| D-ép (khoá bảng ép cuộc đua, 5 lần) | ĐẠT | ĐẠT | Công cụ giữ `LOCK TABLE results IN SHARE MODE` tới khi CẢ HAI yêu cầu đã qua bước kiểm trùng: 10/10 lần đúng 1 điểm chính thức, bên kia 409 |
| D-ảnh trùng (cùng tệp gửi 2 lần cùng lúc, 10 lần) | **KHÔNG ĐẠT** | **KHÔNG ĐẠT** | Dữ liệu an toàn (luôn đúng 1 phiếu), nhưng **3/10 lần → 500** (`PermissionError WinError 32` ở `service._ghi_file`), còn lại 409 thay vì "đã tồn tại" |
| D-lô chéo (`/sheets/batch`, GV1 [p,q] – GV2 [q,p]) | **KHÔNG ĐẠT** | **KHÔNG ĐẠT** | **Deadlock 5/5 lần** (mỗi lần 1 ảnh "Lỗi nội bộ: DeadlockDetected", ảnh kia "UniqueViolation"); vẫn ≤ 1 điểm chính thức / thí sinh. Giao diện `/app/` và `/m` KHÔNG dùng `/sheets/batch` |
| **E** 3 GV × 20 ảnh | ĐẠT | ĐẠT | 60/60 HTTP 201, 0 lỗi, điểm đúng kỳ vọng; xem bảng thời gian |

Thời gian mỗi ảnh (từ lúc gửi tới khi nhận kết quả chấm, ms; trung vị / p95):

| Đo | Lần 1 | Lần 2 |
|---|---|---|
| Một mình, tuần tự (18 ảnh) | 1 283 / 1 638 | **784 / 883** |
| B: 3 GV × 2 luồng = 6 yêu cầu đồng thời | 4 656 / 5 735 | **1 985 / 2 220** |
| B tổng thời gian 18 ảnh: tuần tự → đồng thời | 22,2 s → 14,6 s | 14,3 s → 6,0 s |
| E: 60 ảnh, 6 đồng thời | 2 190 / 2 566 (2,80 ảnh/s) | 2 120 / 2 343 (2,86 ảnh/s) |
| Bộ nhớ máy chủ E (working set) | 160 → đỉnh **946 MB** | 215 → đỉnh **1 104 MB** |
| Kết nối CSDL đỉnh (E / thang tải 12) | 6 / 12 | 6 / 12 |

Thang tải (một GV, N yêu cầu đồng thời, 2N ảnh; lần 2 – lần 1 gần như giống):

| N | 1 | 2 | 4 | 6 | 8 | 12 |
|---|---|---|---|---|---|---|
| Trung vị ms | 801 | 998 | 1 484 | 2 098 | 2 924 | 4 540 |
| Ảnh / giây | 1,24 | 1,99 | 2,61 | 2,78 | 2,71 | 2,59 |

- **Điểm bắt đầu chậm: N ≈ 4** – thông lượng bão hoà ~2,6–2,8 ảnh/s; từ đó mỗi yêu cầu thêm chỉ làm chờ lâu hơn (độ trễ ≈ N / 2,7 s). 16 luồng CPU nhưng chỉ nhanh ~2,2× so với 1 yêu cầu → phần lớn bị tuần tự hoá (GIL).
- Bộ nhớ ~150 MB mỗi yêu cầu đang chạy: đỉnh **~1,9–2,0 GB ở N = 12** (lần 1: 1 998 MB, lần 2: 1 908 MB); không có giới hạn số yêu cầu đồng thời.
- Lần 1, nhóm B chậm gấp ~2 lần lần 2 ở cả tuần tự lẫn đồng thời (máy chủ tự đo cũng chậm: 1 106 so với 665 ms) → nhiễu của máy lúc đó, không phải do đồng thời; các kết luận an toàn giống nhau cả hai lần.

Dọn dẹp (cả hai lần, và cả lần chạy hỏng đầu tiên vì lỗi in chữ Việt ra ống – `finally` vẫn dọn): đếm lại **0** tài khoản / lớp / thí sinh / kỳ thi / phiếu / kết quả / lô / môn /
nhật ký quản trị của tài khoản thử; kho ảnh thử xoá (2 662 tệp). Sau đó `dat_lai_demo.py` (xem trước): **0 phiếu sẽ xoá**, 1380 = 1381 = 1633 = 0, **1632 = 6 phiếu**;
`kiem_truoc_demo.py`: **ĐẠT 27, CẢNH BÁO 1 (PUBLIC_BASE_URL, có sẵn), KHÔNG ĐẠT 0**.

## 3. Đọc mã – trả lời a–e

**a) Phiên đăng nhập.** Không có bảng phiên: phiên là **token ký HMAC không trạng thái** `v1.<payload>.<chữ ký>`, payload {user_id, hết hạn, dấu vân tay hash mật khẩu}
(`backend/auth.py:87-104`), đặt trong cookie `se_session` HttpOnly + SameSite=Lax (`backend/main.py:377`) hoặc `Authorization: Bearer` (`main.py:78-80`). Mỗi yêu cầu tra lại `users`
(`is_active`, vân tay mật khẩu – `backend/nguoi_dung.py:58-65`). Mỗi tài khoản / mỗi lần đăng nhập một token độc lập. Cùng tài khoản ở hai trình duyệt: hai token, cả hai dùng được (đã thử).
Đăng xuất **chỉ xoá cookie ở trình duyệt đó** (`main.py:381-385`): trình duyệt kia không ảnh hưởng (đã thử); nhưng token đã bị chép vẫn dùng được tới khi hết hạn (`SESSION_HOURS`, mặc định 8 giờ)
(đã thử: 200 sau đăng xuất). Chỉ đổi / đặt lại mật khẩu hoặc vô hiệu hoá tài khoản mới làm mọi token cũ mất hiệu lực.

**b) Khoá đăng nhập.** Khoá theo **cặp (tên đăng nhập viết thường, IP)** (`nguoi_dung.py:30`), IP = `request.client.host` (`main.py:376`), bộ đếm trong bộ nhớ của tiến trình
(`auth.py:108-132`; khởi động lại máy chủ là mất; nhiều worker thì mỗi worker một bộ đếm). **Không khoá theo IP đơn thuần** → nhiều giáo viên chung Wi‑Fi / chung IP sau NAT **không khoá nhầm
nhau** (đã thử: GV3 bị khoá, GV1/GV2 cùng IP vẫn đăng nhập được). Một tài khoản bị khoá không ảnh hưởng tài khoản khác và **không cắt phiên đang có** của chính nó (đã thử). Rủi ro còn lại:
(1) bất kỳ ai **cùng IP** (sau NAT, hoặc mọi người nếu máy chủ đặt sau reverse proxy – khi đó mọi yêu cầu có cùng `client.host`) gõ sai 5 lần là **khoá được một giáo viên cụ thể 15 phút** từ IP đó;
(2) không có giới hạn chung theo IP → dò nhiều tên / nhiều IP không bị chặn; từ điển bộ đếm không bao giờ dọn khoá cũ. Lưu ý: chạy LAN như demo (`chay_server_lan.py`, điện thoại cùng Wi‑Fi với máy chủ)
thì máy chủ thấy IP riêng từng thiết bị – NAT chỉ đáng kể khi máy chủ ở ngoài mạng của lớp.

**c) Tải ảnh và chấm.** Chấm **đồng bộ trong yêu cầu**: endpoint `def` thường (`main.py:198-207`) → Starlette chạy trong **threadpool của anyio (mặc định 40 luồng)**; **1 tiến trình uvicorn, 1 worker**
(`tools/chay_server_lan.py:80`, không có `workers`); **không có khoá toàn cục, không hàng đợi, không giới hạn số ảnh chấm cùng lúc**. Mô hình nạp một lần, dùng chung chỉ đọc (`main.py:36`).
**Không có pool kết nối**: mỗi yêu cầu `psycopg.connect` riêng + một giao dịch (`backend/db.py:13-14`, `main.py:61-71`); `max_connections` của PostgreSQL = 100 (đo được tối đa 12 kết nối ở 12 yêu cầu).
OpenCV / NumPy nhả GIL một phần nên chạy song song được **một phần**: Python 3.14.7 bản thường (GIL bật), đo được thông lượng bão hoà ~2,7 ảnh/s từ 4 yêu cầu (×2,2 so với 1 yêu cầu, máy 16 luồng).
`/sheets/batch` xử lý tuần tự từng ảnh trong **một** giao dịch, mỗi ảnh một savepoint (`main.py:220-236`).

**d) Chống trùng phiếu (cùng SBD, cùng kỳ thi).** Bảo đảm thật là **ràng buộc CSDL**: chỉ mục duy nhất một phần `uq_results_exam_student ON results (exam_id, student_id) WHERE status <> 'void'`
(`database/01_schema.sql:326`). Kiểm trong mã (`backend/service.py:425-429`) là `SELECT` không khoá → có khe đua. Hai yêu cầu đồng thời **không bao giờ tạo được hai phiếu chính thức** (đã thử 40 + 10 lần),
nhưng bên thua gặp `UniqueViolation` → 409 (`main.py:115-117`), **cả giao dịch rollback → phiếu thứ hai không được lưu** (tệp ảnh nằm lại trên đĩa, không có dòng CSDL) thay vì vào hàng đợi
`duplicate_sbd`. Tương tự cho cùng một tệp ảnh: `uq_sheets_image_hash` (`01_schema.sql:273`) chặn, nhưng kiểm trước bằng `SELECT` (`service.py:278-280`) có khe đua → 409; và `_ghi_file`
đặt tên tệp tạm theo PID (`service.py:222-226`) nên hai luồng cùng tiến trình ghi cùng ảnh đụng nhau trên Windows → **500** (đã thấy 3/10 lần, cả hai lần chạy).
`/m` hiển thị 409 với tiêu đề "Kỳ thi không nhận ảnh" (`frontend/loi_tai.js:21`) – sai nghĩa cho trường hợp này, và không có nút Gửi lại.

**e) Deadlock lệnh AA.** Không còn nhật ký gốc (không tìm thấy trong `data/_eval`, `docs`) → nguyên nhân là **suy luận**, có cơ chế đã tái hiện được: pytest (`tests/test_backend_api.py:29`) và
`tools/kiem_backend_dau_cuoi.py:114` mỗi bên chạy trong **một giao dịch dài** (ROLLBACK ở cuối) và cùng chèn thí sinh với các SBD dev giống nhau (`INSERT … ON CONFLICT DO NOTHING` vẫn phải
**chờ** khoá duy nhất chưa commit của giao dịch kia), cùng phiếu / kết quả, theo **thứ tự khác nhau** → giao dịch 1 giữ khoá khoá-duy-nhất x chờ y, giao dịch 2 giữ y chờ x → `DeadlockDetected`.
**Giữa hai yêu cầu thật**: tái hiện được **chỉ với `/sheets/batch`** (một giao dịch cho cả lô; 2 lô chéo thứ tự thí sinh → deadlock 5/5 lần). Với `/exams/{id}/sheets` (một ảnh, giao diện dùng):
mỗi yêu cầu một giao dịch ngắn, chỉ tranh **một** khoá duy nhất (INSERT results) và `FOR UPDATE` chỉ trên phiếu của chính nó → không có vòng chờ; **không thấy deadlock** trong 40 + 10 + 20 + 60 + 66 yêu cầu đồng thời.
`phieu_trung.thay_phieu_cu` đã khoá theo thứ tự cố định (`backend/phieu_trung.py:60`).

## 4. Kết luận

**Chịu được (trong điều kiện đã thử):** 3 giáo viên đăng nhập cùng lúc, mỗi người 2 ảnh song song (6 yêu cầu), tới 12 yêu cầu đồng thời: **0 lỗi 500, 0 deadlock, 0 rò dữ liệu, kết quả chấm
trùng khít chạy tuần tự, không bao giờ có hai điểm chính thức cho một thí sinh.** Một ảnh mất ~0,8 s khi một mình, ~2,1 s khi 6 yêu cầu cùng lúc; thông lượng tối đa ~2,7 ảnh/s
(≈ 160 ảnh/phút). Với nhịp chụp thực tế ~1 tờ / 3–5 s mỗi giáo viên, ước lượng 3 giáo viên dư sức; **số lớn hơn 3 người chưa thử** (chỉ suy từ thang tải).

**Đề xuất sửa (KHÔNG làm), xếp theo mức nghiêm trọng:**

| # | Mức | Vấn đề | Đề xuất | Đụng tệp đóng băng? |
|---|---|---|---|---|
| 1 | Trung bình–cao | Hai ảnh cùng SBD tải đồng thời: bên thua **409 + phiếu không được lưu** (13–17/20 lần), thông báo kỹ thuật, `/m` ghi "Kỳ thi không nhận ảnh", không Gửi lại | (a) Trong `danh_gia_phieu`: `pg_advisory_xact_lock(exam_id, student_id)` trước khi kiểm trùng → bên sau thấy kết quả đã commit → `duplicate_sbd` (cách đúng gốc). (b) Không đụng tệp đóng băng: ở `main.py` bắt `UniqueViolation` của `uq_results_exam_student` và chạy lại `nhan_anh` một lần trong giao dịch mới; sửa câu chữ 409 trong `loi_tai.js` | (a) **CÓ** – `backend/service.py`; (b) không (`main.py`, `frontend/loi_tai.js`) |
| 2 | Trung bình | Không giới hạn số ảnh chấm đồng thời: ~150 MB / yêu cầu, đỉnh ~2 GB ở 12; threadpool cho tới 40 → máy yếu (8 GB) có thể hết bộ nhớ | Semaphore (vd 4 = điểm bão hoà) quanh `nhan_anh` trong `main.py`; yêu cầu dư xếp hàng – thông lượng không giảm | Không (`main.py`) |
| 3 | Trung bình | Cùng một tệp gửi 2 lần cùng lúc (nút Gửi lại khi yêu cầu đầu chưa xong): 3/10 → 500, còn lại 409 thay vì "đã tồn tại" | Tên tệp tạm duy nhất mỗi lần ghi (uuid / luồng) trong `_ghi_file`; bắt `uq_sheets_image_hash` → trả phiếu đã có (`da_ton_tai`) | **CÓ** – `backend/service.py` (phần trả "đã tồn tại" có thể làm ở `main.py`) |
| 4 | Trung bình (thấp nếu chỉ dùng giao diện) | `/sheets/batch` deadlock khi hai lô chéo thứ tự thí sinh (5/5) | Commit từng ảnh (mỗi ảnh một giao dịch) hoặc bỏ endpoint khỏi tài liệu cho tới khi sửa | Không (`main.py`) |
| 5 | Thấp–trung bình | Đăng xuất không thu hồi token (chép được thì dùng tới 8 giờ) | Bảng phiên / "phiên bản phiên" trên `users` (migration mới), đăng xuất tăng phiên bản; hoặc giảm `SESSION_HOURS` | Không (`auth.py`, `nguoi_dung.py`, `main.py`, migration) |
| 6 | Thấp | Khoá đăng nhập (tên, IP): người cùng IP / sau proxy khoá được một giáo viên 15 phút; không giới hạn chung theo IP; bộ đếm không dọn, mỗi worker một bộ đếm | Thêm giới hạn theo IP (số lần sai mọi tên), dọn khoá hết hạn, ghi nhật ký lần khoá; nếu đặt sau proxy: lấy IP thật từ `X-Forwarded-For` của proxy tin cậy | Không (`auth.py`, `nguoi_dung.py`) |
| 7 | Thấp | Không pool kết nối (mỗi yêu cầu một kết nối mới) | `psycopg_pool` khi > ~40 yêu cầu đồng thời; hiện 12 / 100 là ổn | Không (`db.py`, `main.py`) |

**Chưa kiểm:** nhiều worker uvicorn (bộ đếm khoá đăng nhập và bộ nhớ mô hình nhân theo worker), máy yếu hơn (đây là máy 16 luồng), nhiều hơn 3 giáo viên thật,
điện thoại thật cùng lúc qua Wi‑Fi (chỉ có HTTP từ chính máy chủ, ảnh giả hoá 2480×3508 thay vì ảnh 12 MP), mạng chậm / rớt giữa chừng khi đồng thời, duyệt phiếu đồng thời (hai GV cùng duyệt một phiếu).
