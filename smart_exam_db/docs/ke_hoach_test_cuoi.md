# Đánh giá test cuối CẢ HỆ THỐNG trên 0035–0040 – KẾ HOẠCH ĐÃ DUYỆT + ĐĂNG KÝ TRƯỚC (21/10/2026; **CHƯA CHẠY**)

> Một lần duy nhất đo toàn chuỗi **nắn ảnh → OMR → CNN chữ số + đối chiếu → chấm điểm → giáo viên** trên 12 ảnh test (6 phiếu).
> Chỉ chạy khi người dùng gõ **"chạy test hệ thống"**. Trạng thái: công cụ `tools/eval_he_thong.py` đã viết + thử trên dev (mục 8); bản đăng ký
> `docs/dang_ky_test_he_thong.json` đã commit. Trước đây trên test chỉ chạy: nắn ảnh (07/10, Tuần 4 Bước 7: 12/12 đúng). OMR, CNN, chấm điểm: **chưa**.

## 1. Quyết định của người dùng (21/10/2026)
- **OMR**: phương án (A) – giữ nguyên `models/omr_m1.json` (huấn luyện trên 0001–0028, đã kiểm val). Không huấn luyện lại.
- **CNN**: giữ `models/ocr_cnn.json` (g0, seed 2026). **Luật đối chiếu**: Q3 nguyên vẹn, τ_khop 0,5 (GIỮ, không dùng luật mềm).
- **Đáp án chấm**: kỳ thi mô phỏng (4 mã đề giả lập `demo.khoa_demo`, như `kiem_backend_dau_cuoi.py`); điểm "đúng thật" tính độc lập từ nhãn người tô.
- **MO_MIN** giữ 0,012 (chưa chỉnh).

## 2. Đăng ký trước – mã, SHA, kiểm tra trước khi chạy (yêu cầu 1)
- **Mã đăng ký = MỘT commit cụ thể: `551b356f33f4ae2f677f442766592f8242ef9d8a`** (`cv_engine/`, `models/`, `tools/`, `backend/`, `answer_sheet/`, `frontend/`).
  Các commit sau chỉ được đổi `docs/`, `CLAUDE.md`.
- SHA-256 (cũng ghi trong `docs/dang_ky_test_he_thong.json`, file mà công cụ đọc):
  | File | SHA-256 |
  |---|---|
  | `models/omr_m1.json` | `f8f87577b42e28741def10bb9d42f4b6e937e6e3b37c025c5e63b8d8c81c60af` |
  | `models/ocr_cnn.json` | `6d87205c83a29fccc4eb450f0aec0c9d51ba56e1bb141664060041ab0f2fcad5` |
  | `data/_eval/nguong.json` (ngưỡng nắn ảnh Tuần 4) | `df9908623638b392b31488c5f1af00963541b1eada0324b7b7a592e3aea91780` |
  | `answer_sheet/output/layout.json` | `a35ccb7e259f5f7a30355d85d79ba4ef267a0d465f29c09b8fd05906cfc0ecbd` |
  | `answer_sheet/output/phieu_trang_300dpi.png` | `7b7db1a95344564a95460af9c076ed74833e75583fc117028f83bb86e1bbf30f` |
  | `cv_engine/preprocessing.py` | `651f14fa720714fe4f3ff218694b296f66840dbf4c848a8b06b26b0060fe4352` |
- **Công cụ TỰ KIỂM trước khi chạy test** (`kiem_dang_ky`): có file đăng ký; `git diff 551b356 HEAD` các đường dẫn mã **rỗng**; mã không có thay đổi chưa commit; mọi SHA-256 trên **khớp**. Sai một điều → DỪNG, chưa tạo khoá.
- Tham số: `MO_MIN` 0,012, ngưỡng ô OMR `ro_min` 0,5 / `trong_min` 0,90 / `to_min` 0,50 (bubble 0,90 / 0,70), τ_khop 0,5, ngưỡng ô viết tay (`NGUONG_*` trong `ocr.py`).

## 3. Nắn ảnh: kiểm nhất quán với Tuần 4 (yêu cầu 2)
- `cv_engine/preprocessing.py` **không đổi từ commit `aa2748b`** (`git diff aa2748b HEAD -- smart_exam_db/cv_engine/preprocessing.py` rỗng; lần sửa cuối `fc4946b`, trước Bước 7 Tuần 4).
- Nên nắn 12 ảnh test PHẢI trùng Tuần 4: kết quả "xem mù 07/10/2026 – 12/12 đúng, 0 lỗi im lặng, 0 từ chối" (`data/_eval/v6_api/truth_test.csv`). **Phép kiểm nhất quán** (trong `eval_he_thong.py`): mỗi ảnh phải cùng ok / từ chối và có 4 marker (sai ≤ 0,01 px), hướng xoay, blur trùng `data/_eval/v6_api/diem_test.csv`. Lệch bất kỳ ảnh nào = ghi rõ (không phải điều kiện ĐẠT riêng, nhưng thay đổi hành vi nắn so với Tuần 4 phải giải thích).
- Thử trên dev: 56/56 ảnh nhất quán với `diem_dev.csv`.

## 4. Chỉ số, tiêu chí, ca thử (yêu cầu 3, 4)
**Tiêu chí ĐẠT bắt buộc (tất cả = 0 lỗi):**
| # | Tiêu chí | Ngưỡng |
|---|---|---|
| H1 | Nắn ảnh sai mà không bị từ chối (lỗi im lặng) – theo **kết luận mắt mù** của người dùng, kèm kiểm nhất quán Tuần 4 | = 0 / 12 |
| H2 | OMR lỗi nặng không gắn cần xem: câu (tập ô đọc ≠ tập ô người tô) + cột bubble (chữ số ≠ nhãn và không bị cờ) | = 0 / 480 câu + 108 cột |
| H3 | SBD / mã đề được nhận tự động mà ≠ chữ VIẾT TAY thật | = 0 / 12 SBD + 12 mã đề |
| H4 | Câu chấm sai mà không gắn cần xem; điểm tạm / điểm tối đa không bao điểm thật; phiếu tự chốt sai điểm / sai sinh viên | = 0 |
| H5 | Sau giáo viên oracle (chốt đúng như giấy): điểm chính thức = điểm tính độc lập, đúng sinh viên | tất cả ảnh không bị từ chối (số ảnh bị từ chối báo riêng, kèm lý do) |

**Chỉ báo – báo kèm CI và cận trên Clopper–Pearson (CP 95%), KHÔNG là điều kiện ĐẠT:** T3 độ đúng chữ số CNN (mục tiêu ≥ 97%); T4 ảnh có SBD hoặc mã đề cần xem (mục tiêu ≤ 10%); cần xem thừa câu rõ 1 ô (mục tiêu ≤ 3%); F1 mờ cấp CÂU (tổng và C1–C4; bootstrap theo phiếu; n mờ ≈ 30 – CI rất rộng); lỗi nhẹ OMR; số ảnh bị từ chối; thời gian / ảnh; cận trên CP của mọi số đếm 0 / n.

**Ca thử bắt buộc báo riêng:**
1. **0035: mã đề viết `103`, KHÔNG tô bubble** (nhãn `---`): phải **cần xem** (`thieu_bubble`); nhận / chấm tự động = vi phạm H3. (Công cụ kiểm tổng quát: mọi cột nhãn "không tô" phải làm trường cần xem.)
2. **8 mục rõ / mờ của test, nhãn ĐÃ XÁC NHẬN bằng giấy ở Tuần 4 (07/10/2026), chỉ dùng ở đây**: 0036 câu 2, 10, 13; 0037 câu 1, 15, 31; 0040 câu 5 (nhãn mờ), 0040 câu 10 (nhãn rõ). Báo từng ảnh: nhãn, máy đọc, cần xem. Mờ đọc thành rõ chắc chắn = lỗi nhẹ (chỉ báo).
3. **0035_C3** (nội dung lệch 2,06 mm > dung sai cố định 2,0 mm) và **0039_C3** (độ phối cảnh 0,618 nhỏ nhất): định vị phải đúng hoặc gắn `vi_tri`.

**Dự đoán đăng ký trước (để so, không chỉnh theo kết quả):** H1 = 0 (nắn trùng Tuần 4 12/12); H2 = 0; H3 = 0; H4 = 0; H5 12/12; nhất quán Tuần 4 12/12; mã đề 0035 cần xem; T3 ≈ 94–99% (val 98,1%, dev 92,7%; test toàn người 5 – nét dễ nhất); **T4 ≈ 15–50% (2–6 / 12 ảnh) – dự đoán KHÔNG đạt ≤ 10%**; cần xem thừa 0–4%; tổng câu cần xem 22–28%; F1 mờ cấp câu gộp 0,90–0,99; thời gian ≈ 0,75 s / ảnh; 0040 câu 5 đọc `mờ` và cần xem.

**Giới hạn phải nêu trong báo cáo:** chỉ **12 ảnh / 6 phiếu** (hai ảnh cùng phiếu không độc lập; CP cho 0 / 480 ≈ 0,8%, 0 / 12 ≈ 26%); **toàn bộ do người 5 viết**, người 5 cũng viết D009–D010 (dữ liệu tinh chỉnh CNN) ⇒ CNN chỉ đo "nét chữ đã gặp", lạc quan hơn người lạ (OOF T3 ≈ 92%); test đã được mở một lần ở Tuần 4 cho nắn ảnh và audit nhãn (sửa nhãn mã đề 0035 theo giấy) – không tham số nào chọn theo test; kỳ thi và đáp án là mô phỏng.

## 5. Xem bằng mắt MÙ (yêu cầu 5)
`eval_he_thong.py run --tap test --xac-nhan-test --xem` ghi hai file (tạo cùng lúc, nhưng người dùng chỉ mở file thứ nhất trước):
1. **`data/_eval/he_thong/test/xem_mu.html`** – KHÔNG chứa bất kỳ kết luận nào của máy (không chữ số đọc, không cần xem / lý do, không trạng thái; kiểm bằng pytest): với mỗi ảnh gồm ảnh nắn thu nhỏ (để kết luận nắn đúng / sai), 9 ô viết tay, các câu cần đọc (mọi câu nhãn mờ / nhiều ô + 8 mục ở mục 4, chọn theo NHÃN không theo máy).
   Người dùng ghi kết luận trước: ảnh nắn đúng / sai; SBD và mã đề đọc được; từng câu tô gì / mức nào.
2. **`xem_may.html`** – kết quả máy (ô tô, chữ số máy đọc + %, câu máy đọc, cần xem + lý do). Chỉ mở SAU khi đã có kết luận của người dùng; mọi ca máy ≠ mắt được liệt kê; nghi nhãn `ground_truth.csv` sai → người dùng so giấy, KHÔNG tự sửa.

## 6. Chốt chặn và quy tắc sau khi chạy (yêu cầu 6, 7)
- `--xac-nhan-test` + `chan_test` + bản đăng ký khớp (mục 2) + **file khoá `data/_eval/he_thong/da_chay_test.lock`** (tạo NGAY khi bắt đầu, kể cả chạy hỏng giữa chừng): lần chạy test thứ hai bị **từ chối** (pytest `test_khoa_chay_mot_lan`).
- **Có lỗi trên test ⇒ ghi nguyên trạng** (số liệu + phân tích nguyên nhân) vào mục KẾT QUẢ bên dưới; **không chạy lại test, không chỉnh mã / mô hình / ngưỡng rồi đo lại trên test**; sửa (nếu có) làm ở phiên bản sau và chỉ kiểm lại trên dev. Không sửa `ground_truth.csv` khi chưa được người dùng xác nhận bằng giấy.

## 7. Công cụ `tools/eval_he_thong.py` (đã viết, commit `551b356`)
- **Độc lập (yêu cầu 6)**: không import `cv_engine.omr` / `ocr` / `backend.service` / `grading` (pytest kiểm bằng AST); chỉ gọi API công khai của backend qua TestClient trong giao dịch **ROLLBACK** + thư mục ảnh tạm (không ghi CSDL thật). Kết quả "đúng thật" tính riêng từ `ground_truth.csv`: câu đúng ⇔ người tô ĐÚNG MỘT ô và ô đó = đáp án chuẩn (ô mờ cũng tính); lỗi nặng / nhẹ, chữ số viết tay thật, bubble thật đều từ nhãn. `cv_engine.preprocessing` chỉ được import trong hàm kiểm nhất quán Tuần 4. Chỉ đọc dòng nhãn của tập được chạy.
- Lệnh: `python tools/eval_he_thong.py run --tap dev [--xem]` (thử); `run --tap test --xac-nhan-test --xem` (MỘT lần).

## 8. Chạy thử trên dev 0001–0028 (21/10/2026, 56 ảnh) – ra lại đúng các số đã biết
H2 lỗi nặng **0 / 2 744** (CP95% ≤ 0,13%) · H3 SBD 0, mã đề 0 / 56 · H4: **0 câu chấm sai không cờ**, điểm tạm / tối đa 0 vi phạm, 0 phiếu tự chốt sai · **H5 điểm chính thức khớp 56/56** · nhất quán nắn ảnh với Tuần 4 **56/56** · câu cần xem 560 / 2 240 (25,0%) · T4 26 / 56 (46,4%) · T3 467 / 504 (92,7%) · cần xem thừa 18 / 1 468 (1,23%) · ca "cột không tô bubble" (0001_C1, 0001_C2) → SBD cần xem (`thieu_bubble`) · 0,76 s / ảnh. Số liệu: `data/_eval/he_thong/dev/ket_qua.json`.

## 9. KẾT QUẢ (điền SAU khi chạy – hiện trống)

**Chạy MỘT lần ngày 21/10/2026** theo đăng ký (mã `551b356`, `git diff` mã rỗng, SHA khớp, khoá chạy một lần đã tạo). Lệnh: `eval_he_thong.py run --tap test --xac-nhan-test --xem`. Số liệu: `data/_eval/he_thong/test/ket_qua.json`; HTML `xem_mu.html` / `xem_may.html`. Không chỉnh gì sau khi thấy số, không chạy lại.

### Tiêu chí ĐẠT bắt buộc
| # | Kết quả | Đánh giá |
|---|---|---|
| H1 nắn ảnh | 0 ảnh bị từ chối; **nhất quán Tuần 4 12/12** (marker ≤ 0,01 px, hướng xoay, blur trùng `diem_test.csv`) ⇒ nắn 12/12 như kết luận mắt mù 07/10. **Kết luận mắt mù lần này: CHỜ người dùng (`xem_mu.html`)** | nhất quán đạt; mắt chờ |
| H2 OMR lỗi nặng | **0 / 588** (480 câu + 108 cột), CP95% trên 0,63% | **ĐẠT** |
| H3 SBD / mã đề nhận mà sai | **0 / 12 SBD, 0 / 12 mã đề** (CP95% trên 26,5% mỗi loại) | **ĐẠT** |
| H4 chấm sai không cờ / điểm tạm vi phạm / tự chốt sai | **0 / 0 / 0** (CP95% trên 1,0% số câu chắc) | **ĐẠT** |
| H5 điểm chính thức sau giáo viên = điểm độc lập, đúng sinh viên | **12 / 12** (0 ảnh bị từ chối) | **ĐẠT** |

### Ca thử bắt buộc
- **0035 mã đề `103` không tô bubble**: cả 0035_C3 và 0035_C4 → mã đề **CẦN XEM** (`thieu_bubble`), không nhận, không tự chốt – **đúng yêu cầu**. (SBD của 0035 cũng bị gắn `lech_bubble` – CNN đọc sai chữ số.)
- **8 mục rõ / mờ** (mỗi mục 2 ảnh): máy đọc `faint` + cần xem ở 0036 q2, q10, q13 (cả 2 ảnh), 0037_C1 q15 và q31, 0040 q5 (cả 2 ảnh), 0040_C4 q10; máy đọc **`filled` chắc chắn (không cờ) cho nhãn mờ**: 0037 q1 (cả 2 ảnh), 0037_C2 q15 và q31 = 4 lượt **lỗi nhẹ** (điểm không sai vì ô mờ vẫn tính là đáp án); 0040_C1 q10 (nhãn rõ) đọc rõ, 0040_C4 q10 đọc mờ cần xem (cần xem thừa, vô hại). Không lượt nào đọc trống / đọc sai ô.
- **0035_C3, 0039_C3** (định vị khó): lỗi nặng 0, không câu nào bị gắn `vi_tri`.

### Chỉ báo (không là điều kiện ĐẠT) so với dự đoán đã đăng ký
| Chỉ báo | Kết quả [CP95% / bootstrap] | Dự đoán | |
|---|---|---|---|
| T3 độ đúng chữ số CNN (mục tiêu ≥ 97%) | **100 / 108 = 92,6%** [85,9–96,7%] | 94–99% | **thấp hơn dự đoán**, chưa đạt 97% |
| T4 ảnh có SBD / mã đề cần xem (mục tiêu ≤ 10%) | **7 / 12 = 58,3%** [27,7–84,8%] | 15–50% | **cao hơn dự đoán**, chưa đạt |
| Cần xem thừa câu rõ 1 ô (mục tiêu ≤ 3%) | 12 / 326 = 3,68% [1,9–6,3%] | 0–4% | trong dự đoán, > 3% (0037_C2: 4 câu) |
| Tổng câu cần xem | 118 / 480 = 24,6% | 22–28% | đúng |
| Lỗi nhẹ OMR | 6 (0037_C1: 1, 0037_C2: 5) | – | tập trung ở phiếu 0037 |
| F1 mờ cấp CÂU gộp (n mờ 84) | 0,897 [0,840–0,979] | 0,90–0,99 | sát đáy |
| F1 mờ C1 / C2 / C3 / C4 (n mờ 26 / 19 / 16 / 23) | 0,980 / **0,700** / 0,941 / 0,939 | – | C2 yếu (như dev / val) |
| Thời gian / ảnh | trung vị 0,778 s | ≈ 0,75 s | đúng |
| Cần xem thừa câu trống | 0 / 42 | – | – |

### Nhận xét
- **Các điều kiện bắt buộc H2–H5 đạt (0 lỗi im lặng ở mọi tầng; điểm chính thức khớp 12/12 sau giáo viên); H1 chờ mắt mù.** Cỡ mẫu nhỏ: CP95% cho H3 0 / 12 chỉ ≤ 26%, H2 0 / 588 ≤ 0,63% (lạc quan vì lượt không độc lập).
- Điểm yếu giữ nguyên như dev / val: **CNN đọc sai ~7% chữ số** (không do "nét lạ": toàn người 5, nét đã gặp) ⇒ T4 58% (7 / 12 ảnh phải xem SBD hoặc mã đề); lệch hai kênh luôn bị bắt (lech_bubble) nên không thành lỗi im lặng – đúng thiết kế an toàn. **C2 vẫn là điều kiện yếu** của OMR (F1 mờ 0,70; 0037_C2 5 lỗi nhẹ, 4 cần xem thừa) – nét tô nhạt ở ảnh C2, ranh giới rõ/mờ mơ hồ.
- Giới hạn (như đăng ký): 12 ảnh / 6 phiếu; một người viết; kỳ thi và đáp án mô phỏng; test từng được mở cho nắn ảnh và audit nhãn ở Tuần 4.
- **Việc còn lại của người dùng**: xem mù `data/_eval/he_thong/test/xem_mu.html` (ảnh nắn đúng / sai; SBD, mã đề; các câu mờ / nhiều ô) rồi mới mở `xem_may.html` để so; nếu nghi nhãn `ground_truth.csv` sai → so giấy, không tự sửa. Kết luận mắt quyết định H1.
