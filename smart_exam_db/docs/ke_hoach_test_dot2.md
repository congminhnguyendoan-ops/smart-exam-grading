# Kế hoạch + ĐĂNG KÝ TRƯỚC – test hệ thống đợt 2 (phiếu 0101–0110)

Viết 28/10/2026, **TRƯỚC khi có bất kỳ ảnh đợt 2 nào** (`data/raw_dot2/` chưa tồn tại). Đăng ký máy đọc: `docs/dang_ky_test_dot2.json` (tag `dang-ky-dot2`).
Công cụ: `tools/eval_dot2.py` (độc lập với mã chấm, như `eval_he_thong.py`). Lệnh chạy thật (CHỈ khi người dùng gõ **"chạy test đợt 2"**):

    python tools/eval_dot2.py run --xac-nhan-dot2 --xem

## 1. Vị trí của đợt 2 và trung thực về phiên bản
- Test cuối cả hệ thống 21/10 (0035–0040) chạy trên mã TRƯỚC khi `omr.py` thêm luật `vet_nho` (28/10) và `to_nhat`, và TRƯỚC khi backend sửa `LY_DO_OMR_CAU`.
  Kết quả 21/10 là của bản cũ; **đợt 2 là phép kiểm MỚI trên bản đóng băng v3** (tag `ma-dot2-dong-bang-v3`; SHA + tham số: `docs/dong_bang_ma_dot2.json`).
- Thay đổi mã giữa 21/10 và đóng băng v3 (đều trước khi có ảnh đợt 2): `vet_nho` (N = 90 px) · `to_nhat` (Xs = 0,44, n ≥ 10) · sửa backend `LY_DO_OMR_CAU` (phát hiện khi thử công cụ đợt 2 trên ảnh giả hoá,
  `ke_hoach_cai_tien_27-10.md` mục 7c) · sửa test `test_val_bi_khoa_neu_khong_xac_nhan` (môi trường, mục 6.5). Nợ không cài: `nhat_tuyet_doi` theo từng ô (mục 6.4).
- Từ tag v3 mã (`cv_engine/`, `models/`, `backend/`, `answer_sheet/output/`) KHÔNG đổi cho tới khi đợt 2 chạy xong. Có lỗi thì ghi nguyên trạng; **nếu về sau đổi mã thì đợt 2 trở thành dev và phải thu đợt 3**.

## 2. Dữ liệu
- 10 phiếu (0101–0110) × 2 ảnh = **20 ảnh**, chụp bằng điện thoại, tên `data/raw_dot2/NNNN_Ck.jpg` (k theo cột "Điều kiện chụp" trên phiếu giao việc / `ground_truth_dot2.csv` cột `conditions`).
  Ảnh gốc điện thoại; **không gửi qua Zalo / Messenger (bị nén)**; đủ 4 marker; `data/` nằm trong `.gitignore`.
- 5 người viết (A–E, 2 phiếu mỗi người; viết tay SBD + mã đề). Bút: chì 2B / bi xanh / bi đen / chì HB nhẹ tay (0105). Kỳ thi và đáp án **mô phỏng** (khoá `backend.demo`, 4 mã đề 101–104).
- Nhãn gốc: `answer_sheet/dot2/ground_truth_dot2.csv`, `cell_labels_dot2.csv` (SHA trong đăng ký). Ký hiệu: `B` đậm · `b` mờ · `*B` **chấm nhỏ (vết, KHÔNG phải đáp án)** · `-` trống.
- 400 câu: 1 đậm 135 · 1 mờ 85 · hai đậm 27 · đậm + mờ 27 · hai mờ 26 · ba đậm 9 · ba mờ 1 · **vết 30** · trống 60. Phiếu **0105**: tô NHẸ cả tờ (không có ô đậm). Phiếu **0107**: cố ý KHÔNG tô bubble SBD thứ 3 (`37-273`).
- Kiểm nhãn: `python tools/eval_dot2.py kiem-nhan` – parser độc lập sinh lại `cell_labels` từ `ground_truth` và đối chiếu từng ô; lệch thì DỪNG (đã khớp 2 500 dòng).

## 3. Chuẩn bị ảnh (không chỉnh theo kết quả pipeline)
- Kiểm tên / độ phân giải / nắn được bằng `python answer_sheet/check_photos.py --dir ../data/raw_dot2` (regex 4 chữ số + `C1..C4`, không cứng 0001–0040; không phải tập test nên không bị chặn).
- Chụp lại CHỈ khi nhìn bằng mắt thấy marker bị khung hình cắt hoặc tên sai (cùng quy ước thu dữ liệu 03/10). **Không chụp lại vì pipeline từ chối ảnh**: từ chối là một kết quả hợp lệ (H1 chỉ phạt nắn SAI mà không từ chối).

## 4. Sửa nhãn theo giấy (chỉ khi người dùng xác nhận bằng giấy thật)
- Mỗi thay đổi ghi vào `data/dot2/sua_nhan.csv` (`phieu, muc, nhan_cu, nhan_moi, ly_do, ngay`; `muc` = `q1..q40 | sbd | exam_code | sbd_bubble | exam_code_bubble`), rồi `python tools/eval_dot2.py ap-dung-sua`
  sinh `data/dot2/ground_truth_dot2_da_sua.csv` + `cell_labels_dot2_da_sua.csv` (cell_labels sinh lại bằng cùng parser).
- SHA của 3 file này phải được ghi vào **đăng ký bổ sung** (`bo_sung` trong `dang_ky_test_dot2.json`, commit riêng) TRƯỚC khi chạy; công cụ từ chối nếu có bản sửa mà chưa có SHA khớp.
- Không bao giờ sửa nhãn dựa vào kết quả máy; không sửa `answer_sheet/dot2/` gốc.

## 5. Tiêu chí ĐẠT bắt buộc (tất cả = 0 lỗi; chốt trước)
- **H1** nắn ảnh sai mà không từ chối = 0 (người dùng kết luận bằng mắt, xem mù; không có số Tuần 4 để đối chiếu marker – đợt 2 chưa từng chạy `preprocess`).
- **H2** OMR lỗi nặng không cờ = 0 (câu + cột bubble). Lỗi nặng câu = tập ô đọc ≠ tập ô thật mà không gắn cần xem, **gồm chấm nhỏ bị đọc thành đáp án CHẮC**. "Bỏ sót vết" (vết đọc trống chắc, không cờ) là chỉ báo, không phải lỗi nặng.
- **H3** SBD / mã đề được nhận mà sai = 0; **0107** (thiếu bubble) phải ở trạng thái SBD "cần xem" (`thieu_bubble`) – nhận tự động là vi phạm.
- **H4** chấm sai không cờ = 0; điểm tạm vi phạm cận (tạm ≤ thật ≤ tối đa) = 0; phiếu tự chốt sai điểm / sai sinh viên = 0.
- **H5** điểm chính thức sau giáo viên oracle (chốt đúng như nhãn giấy) = điểm tính độc lập và đúng sinh viên, 20/20 ảnh.
Câu đúng ⇔ người tô ĐÚNG MỘT ô và ô đó = đáp án chuẩn (đậm hay mờ đều là "được tô"); lỗi nhẹ = ô mờ đọc thành "rõ chắc".

## 6. Chỉ báo (KHÔNG là điều kiện ĐẠT; kèm Clopper–Pearson 95%)
T3 độ đúng chữ số CNN (người viết mới A–E ≈ ước lượng cho người lạ thật sự) · T4 ảnh có SBD / mã đề cần xem · cần xem thừa câu 1 đậm / câu trống · tổng câu cần xem · F1 mờ cấp câu (bootstrap theo phiếu) ·
bảng theo LOẠI câu (từ `question_state`), theo C1–C4, theo phiếu (0105, 0107 riêng), theo người viết A–E · **tỉ lệ vết được gắn cờ** (kỳ vọng cho chấm ~1,5 mm; KHÔNG cam kết với chấm ~1 mm) · thời gian / ảnh.

## 7. Dự đoán đăng ký trước (không chỉnh theo kết quả)
Cơ sở: dev OOF 56 ảnh, test 21/10 (T3 92,6% · T4 58,3% · cần xem thừa 3,68%), ảnh giả hoá đợt 2 (công cụ chạy thử, 20 ảnh vẽ phẳng), giới hạn đã biết.
| Hạng mục | Dự đoán |
|---|---|
| H2–H5 | **đạt cả (0 lỗi)**; rủi ro chính đã biết: ô mờ rất nhạt đọc "trống chắc" (C2), chấm nhỏ < ~0,15r hoặc quá nhạt không bị `vet_nho` bắt |
| H3 – 0107 | cả 2 ảnh SBD "cần xem" (`thieu_bubble`) – gần như chắc chắn |
| H1 | 0 nắn sai; 0–2 ảnh bị từ chối (C3 nghiêng 15–25° bằng điện thoại: dev C3 độ phối cảnh 0,60–0,73) |
| T3 (chữ số CNN đúng) | 85–95% (dev ≈ 92%); người viết khác nhau chênh nhiều (dev: người 3 yếu) |
| T4 (ảnh có SBD / mã đề cần xem) | 40–65% (dev 46–58%) – gồm cả 2 ảnh 0107 |
| Cần xem thừa, câu 1 đậm | 1–5% (dev 1,57%; test 3,68%); 0105 không đóng góp (không có nhãn đậm) |
| Cần xem thừa, câu trống | 0–1 câu |
| Tổng câu cần xem | **51–58%** (thành phần bắt buộc 205/400 = 51,25% vì thiết kế đợt 2 nhiều ca khó; dev chỉ ≈ 25%) |
| Vết gắn cờ (chấm ~1,5 mm) | ≥ 90% (ảnh giả hoá 60/60; CP95 dưới 94% với n = 60); chấm ~1 mm: không cam kết |
| F1 mờ cấp câu | 0,80–0,95 (ảnh giả hoá 0,85; dev theo ô 0,93–0,99) |
| **0105 (tô nhạt cả tờ)** | **0 lỗi nặng**; `to_nhat` được gắn ở ≥ 1 trong 2 ảnh với xác suất ~60% (chì HB nhẹ tay: T = trung vị ld có thể < 0,44; nếu T ∈ [0,44; ~0,55] thì luật KHÔNG gắn và có thể có lỗi nhẹ "mờ đọc rõ chắc" 0–10 câu – đúng là nợ đã biết, không phải lỗi nặng) |
| Thời gian / ảnh (API) | 0,7–1,5 s (ảnh giả hoá 0,73 s) |

## 8. Giới hạn phải nêu
- 10 phiếu / 20 ảnh (cận trên CP95 của 0 lỗi / 400 câu ≈ 0,9%); chỉ 5 người viết; ảnh điện thoại chụp tay (chưa qua trang chụp của hệ thống); kỳ thi và đáp án mô phỏng; chỉ 1 phiếu tô nhạt cả tờ (0105) và 1 phiếu thiếu bubble (0107).
- `vet_nho`: ngưỡng 90 px nằm sát chấm bút bi ~1 mm (~110 px ở 300 DPI); phiếu đợt 2 dùng chấm ~1,5 mm (~250 px) nên **không chứng minh được với chấm ~1 mm**.
- `to_nhat`: Xs = 0,44 chọn trên dev (biên 0,027 so với T thật nhỏ nhất); chưa từng thử trên tờ nhạt THẬT; tờ nhạt vừa (T 0,44–0,53) còn là nợ.
- Đợt 2 chạy MỘT LẦN (khoá `data/_eval/dot2/da_chay_dot2.lock`). Có lỗi thì ghi nguyên trạng, KHÔNG chỉnh mã rồi đo lại.
- Công cụ chỉ được thử trên ảnh giả hoá (`--thu-gia`, `data/_eval/dot2/thu_gia/`); số đó không là kết quả đợt 2.

## 9. Quy trình mắt mù
`xem_mu.html` (không chứa kết luận của máy – có test) → người dùng ghi kết luận (nắn đúng? chữ số viết tay? các câu liệt kê) → mới mở `xem_may.html`. Kết quả: `data/_eval/dot2/that/ket_qua.json`.
