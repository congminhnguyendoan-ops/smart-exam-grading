# Tiêu chí thử GIẤY THẬT – lệnh AG (chốt 01/11/2026, commit TRƯỚC khi có công cụ chấm và TRƯỚC khi có bất kỳ ảnh thật nào)

Nhánh `hoan-thien`. Mã đọc phiếu dùng nguyên trạng (OMR `models/omr_m1.json`, CNN `models/ocr_cnn.json`, `cv_engine/*` – khớp SHA của
`docs/dong_bang_ma_dot2.json`); công cụ chấm `tools/ag_cham_that.py` chạy pipeline OFFLINE (không CSDL, không server). Kết quả xấu ghi "không đạt",
không chỉnh tiêu chí / ngưỡng / kịch bản / nhãn sau khi thấy ảnh hay kết quả.

## 1. H3 – chép NGUYÊN VĂN từ tiêu chí đã đăng ký của đợt 2 (`docs/ke_hoach_test_dot2.md`, mục 5)

> - **H3** SBD / mã đề được nhận mà sai = 0; **0107** (thiếu bubble) phải ở trạng thái SBD "cần xem" (`thieu_bubble`) – nhận tự động là vi phạm.

Quy ước câu đúng đi kèm (cùng mục 5):

> Câu đúng ⇔ người tô ĐÚNG MỘT ô và ô đó = đáp án chuẩn (đậm hay mờ đều là "được tô"); lỗi nhẹ = ô mờ đọc thành "rõ chắc".

Tình trạng trước lệnh này: đợt 2 ghi H3 **không đạt** vì vế 0107; phân tích sau đó (`docs/ket_qua_dot2.md` mục 4.1, `docs/phan_tich_sau_chay_dot2.md`)
cho thấy người tô đã tô bubble nên điều kiện "thiếu bubble" **không xảy ra trên giấy** → vế này **chưa được kiểm chứng trên giấy**; phép thử mô phỏng
bằng ảnh chỉnh (`docs/ket_qua_h3_mo_phong.md`) đạt 20/20 nhưng không phải giấy thật.

**Áp dụng H3 cho lần thử này (không đổi tiêu chí, chỉ thay "0107" bằng các cột thiếu bubble của kịch bản AG):**
- **H3a:** mọi trường SBD / mã đề được hệ thống NHẬN (không cần xem) phải đúng giá trị kịch bản – trên MỌI ảnh (thường + khó). Một trường nhận sai → H3 không đạt.
- **H3b:** kịch bản AG cố ý có cột "thiếu bubble" (viết chữ số tay, KHÔNG tô ô tròn – tờ T03, T06, T10, xem `kich_ban.json`). Trường chứa cột đó phải ở trạng
  thái "cần xem" và cột đó có lý do `thieu_bubble`; trường đó được nhận tự động → vi phạm → H3 không đạt.
- H3 **đạt** ⇔ H3a và H3b cùng đạt trên mọi ảnh không bị tiền xử lý từ chối. Nếu MỌI ảnh của một tờ có cột thiếu bubble đều bị từ chối, H3b cho tờ đó
  ghi "chưa kiểm được" (không ghi đạt). Nếu không có ảnh nào kiểm được H3b → H3 "chưa kết luận được".

## 2. C1 (bắt buộc) – sai âm thầm = 0

"Sai âm thầm" = máy trả đáp án khác kịch bản và câu / cột đó **KHÔNG** bị gắn cờ cần xem. Áp dụng cho MỌI loại câu và cho SBD / mã đề (mức cột bubble
và mức trường). Có dù chỉ 1 ca → **C1 không đạt**, nêu rõ tờ, câu, loại kịch bản, máy đọc gì, xác suất.

Cách phân loại mỗi câu trên mỗi ảnh (E = tập ô đúng theo kịch bản; R = tập ô máy đọc; cx = máy gắn cần xem):
- cx → **"can_xem"** (chấp nhận được với mọi loại câu – giáo viên sẽ xem);
- không cx và R = E → **"doc_dung"**;
- không cx và R ≠ E → **"sai_am_tham"** (vi phạm C1).

| Loại kịch bản | E (đáp án đúng) | Kết quả chấp nhận |
|---|---|---|
| `binh_thuong` – tô đậm đúng 1 ô | {ô đó} | doc_dung hoặc can_xem |
| `bo_trong` – không tô | {} | doc_dung hoặc can_xem |
| `nhat` – tô nhẹ / vội 1 ô | {ô đó} (mờ vẫn là được tô) | doc_dung hoặc can_xem |
| `hai_o` – tô 2 ô | {2 ô} | **chỉ can_xem**; máy tự chốt (dù 1 ô hay 2 ô) = sai âm thầm |
| `te` – tô ô X, tẩy bằng tẩy bút chì, tô ô Y (chỉ tờ bút chì) | {Y} | doc_dung hoặc can_xem |
| `vet` – tô ô Y + một chấm bút nhỏ ở ô Z ≠ Y (trước hoặc sau) | {Y} | doc_dung hoặc can_xem |

SBD / mã đề: cột bình thường (viết + tô cùng chữ số d): bubble máy đọc ≠ d mà cột không cần xem → sai âm thầm mức cột; trường được nhận mà khác giá trị
kịch bản → sai âm thầm mức trường (= vi phạm H3a). Cột `thieu_bubble`: bubble đọc ra MỘT chữ số mà cột không cần xem → sai âm thầm mức cột (máy "thấy" ô
không được tô).

Ảnh bị tiền xử lý TỪ CHỐI (thiếu marker, mờ…) KHÔNG phải sai âm thầm (hệ thống từ chối, giáo viên chụp lại) – nhưng phải liệt kê từng ảnh và lý do, và
tờ nào không còn ảnh nào được đọc thì báo rõ "tờ T0X chưa kiểm được".

## 3. C2 (báo cáo, KHÔNG có ngưỡng đạt / trượt)

- Tỉ lệ cần xem của câu **bình thường**: (a) `binh_thuong` (1 ô đậm), (b) `bo_trong` – riêng từng loại, kèm Clopper–Pearson 95%.
- Tỉ lệ cột SBD / mã đề cần xem; tỉ lệ trường cần xem; **số ảnh phải xem** (ảnh có ≥ 1 câu hoặc SBD / mã đề cần xem) và số ảnh có SBD / mã đề cần xem.
- Đối chiếu đợt 2 (`docs/ket_qua_dot2.md`): câu 1 ô đậm cần xem **4,04%** (11/272), câu trống **0/118**, ảnh có SBD / mã đề cần xem **45%** (9/20).
- Tách theo điều kiện chụp (thường / khó) và theo bút (bi / chì).

## 4. C3 (báo cáo) – câu "tẩy"

Với các câu `te`: máy đọc ra gì – doc_dung / can_xem (nhiều ô, mờ, …) / sai âm thầm; **bao nhiêu câu tẩy còn đậm bị đọc thành "nhiều ô"** (R chứa cả X và
Y, lý do `nhieu_o`) và trong đó bao nhiêu có MỌI ô chọn "rõ". Con số này dùng để quyết sau này có nên tự chấm "nhiều ô toàn đậm" (đề xuất ĐX1 của lệnh AE)
hay không: nếu có câu tẩy bị đọc "nhiều ô toàn đậm" thì luật đó sẽ chấm SAI một câu thí sinh làm đúng.

## 5. Giới hạn biết trước (ghi vào mọi kết luận)

- **Mẫu nhỏ:** 10 tờ × 40 câu = 400 câu ở điều kiện thường (+ 3 ảnh điều kiện khó), 20 trường SBD / mã đề. 0 lỗi trên 400 câu chỉ cho cận trên CP95 ≈ 0,92%;
  0 lỗi trên 20 trường cho cận trên ≈ 16,8%. "0 lỗi" KHÔNG chứng minh tỉ lệ lỗi thật thấp.
- Kịch bản do nhóm tự tô (biết trước mình đang bị thử, tô cẩn thận hơn thí sinh thật); các loại đặc biệt chiếm ~20–25% số câu, cao hơn bài thi thật.
- Người tô có thể trùng 5 người đã viết trang chữ số dùng tinh chỉnh CNN → số đo chữ viết tay có thể lạc quan.
- Một điện thoại / một phòng: điều kiện chụp ít đa dạng.
