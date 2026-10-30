<!-- LƯU TRỮ KẾT QUẢ CHÍNH THỨC TEST ĐỢT 2 (lệnh S, 29/10/2026) – data/ nằm ngoài git nên chép vào docs/.
Nội dung dưới khối này là bản chép NGUYÊN VĂN data/_eval/dot2/bao_cao_ket_qua_dot2.md (lệnh R), không sửa chữ nào.
SHA-256 tệp nguồn:
  data/_eval/dot2/bao_cao_ket_qua_dot2.md  9178DBF1D2B80B93EFE5E341C4F1EF1EE3A67E62CCE562D5DA112E0BFC79447D
  data/_eval/dot2/that/ket_qua.json        8AE1FC622702E92C9CCE6AE8EBD7A3A0EEA4AE313BD5C4E00FE497E808C0DB63  (= docs/ket_qua_dot2.json, chép từng byte)
Phân tích sau chạy (kiểm giấy thật 20:19 29/10/2026, SAU khi chạy): docs/phan_tich_sau_chay_dot2.md. -->

# Báo cáo kết quả test đợt 2 (lệnh R, 29/10/2026)

## Phạm vi và nguồn số liệu
- Lần chạy **duy nhất**: nhánh `chay-dot2` (`85d00e1`), 29/10/2026 18:02:34, 45,8 s.
  - Khoá: `data/_eval/dot2/da_chay_dot2.lock` = "đã chạy xong 2026-10-29 18:03:20".
  - Không chạy lại, không sửa mã / nhãn / ngưỡng / đăng ký.
- Số liệu lấy từ:
  - `data/_eval/dot2/that/ket_qua.json`, `data/_eval/dot2/nhat_ky_chay.txt`;
  - ảnh nắn của 0107 trích từ `xem_may.html` (ảnh 620×877 px, khoảng 75 DPI);
  - kết luận mắt `docs/ket_luan_mat_dot2.csv`, đã khoá ở `a4da472` TRƯỚC khi mở kết quả máy.
- **Nhãn dùng khi chạy là bản đã sửa:**
  - `data/dot2/ground_truth_dot2_da_sua.csv` (SHA `0a262f75…`) và `cell_labels_dot2_da_sua.csv` (`c3766560…`);
  - cả hai SHA đều có trong `bo_sung` của `docs/dang_ky_test_dot2.json`;
  - `kiem-nhan` báo nguồn `ground_truth_dot2_da_sua.csv`.
- Kịch bản tính số: `tools/eval_dot2.py` (bản ở tag / nhánh `chay-dot2`, không đổi). Bảng đối chiếu mắt ↔ máy là script chỉ đọc ở thư mục tạm, không thuộc dự án.

## 1. Mã thoát 1 nghĩa là gì
Mã thoát 1 là do **tiêu chí không đạt**, không phải lỗi chạy. Dòng cuối của `main()` trong `tools/eval_dot2.py` (dòng 445), nguyên văn:
```
    sys.exit(0 if all(ok[k] is True for k in ("H2", "H3", "H4", "H5")) else 1)
```
Lần chạy đi hết tới dòng này:
- `ket_qua.json` được ghi đủ;
- khoá được ghi "đã chạy xong" (dòng 443, ngay trước dòng 445);
- nhật ký có đủ 20 dòng tiến độ và khối JSON tóm tắt;
- không có traceback. Dòng cảnh báo duy nhất trong nhật ký là `StarletteDeprecationWarning` của thư viện httpx (dòng 1–2), không liên quan.

Trong `ket_qua.json`: `"dat_bat_buoc": {"H2": false, "H3": false, "H4": true, "H5": true, "H3_0107_thieu_bubble_phai_can_xem": false}`.

## 2. Kết quả theo tiêu chí đã đăng ký
| Tiêu chí (đăng ký) | Số đo | Kết luận theo đăng ký |
|---|---|---|
| **H1** nắn sai mà không từ chối = 0 (mắt mù) | Máy từ chối 0/20 ảnh. Mắt: 15 `dung`, 5 `khong_chac`, 0 `sai` | **Chưa kết luận được đầy đủ**: không ảnh nào bị mắt kết luận sai, nhưng 5 ảnh (0102_C3, 0103_C3, 0106_C3, 0107_C3, 0110_C3) mắt chưa kết luận được |
| **H2** OMR lỗi nặng không cờ = 0 (câu + cột, gồm vết đọc thành đáp án chắc) | **2 / 980** (câu 0/800, cột 2/180; vết đọc thành đáp án chắc 0). CP 95% cận trên 0,74% | **KHÔNG ĐẠT** |
| **H3** SBD / mã đề nhận mà sai = 0; 0107 SBD phải cần xem | SBD nhận sai 0/20, mã đề nhận sai 0/20 (CP cận trên 16,8%); **0107 SBD cần xem: 0/2** (cả hai ảnh được nhận) | **KHÔNG ĐẠT** (vì điều kiện 0107) |
| **H4** chấm sai không cờ = 0; điểm tạm vi phạm = 0; tự chốt sai = 0 | 0 / 0 / 0 (CP cận trên 0,91%) | **ĐẠT** |
| **H5** điểm chính thức sau giáo viên oracle đúng 20/20 | 20/20 | **ĐẠT** |

Hai lỗi nặng (H2) và vi phạm H3 có **cùng một nguồn**: cột SBD thứ 3 của phiếu 0107 (xem mục 4).

### Chỉ báo (so với dự đoán đã đăng ký)
| Chỉ báo | Kết quả | Dự đoán đăng ký |
|---|---|---|
| T3 (chữ số viết tay CNN đúng) | 170/180 = **94,4%**; CI 95% của tỉ lệ sai 2,7–10,0% (tức đúng 90,0–97,3%) | 85–95% (trong khoảng) |
| T4 (ảnh có SBD hoặc mã đề cần xem) | 9/20 = **45%**; CI 23,1–68,5% | 40–65% (trong khoảng) |
| Cần xem thừa – câu 1 ô đậm | 11/272 = **4,04%**; CI 2,0–7,1% | 1–5% (trong khoảng) |
| Cần xem thừa – câu trống | 0/118 | 0–1 câu (trong khoảng) |
| Tổng câu cần xem | 397/800 = **49,6%** | 51–58% (**thấp hơn dự đoán**) |
| F1 lớp mờ (cấp câu) | **0,795**; CI bootstrap theo phiếu 0,563–0,962 (n mờ = 170) | 0,80–0,95 (**hụt nhẹ dưới khoảng**) |
| F1 mờ theo điều kiện | C1 0,70 (n 50) · C2 0,71 (57) · C3 0,89 (35) · C4 0,93 (28) | – |
| Vết (chấm nhỏ) được gắn cờ | 36/60 = **60%**; CI 46,5–72,4%; bỏ sót 24 (đọc trống, không cờ); vết đọc thành đáp án chắc 0 | ≥ 90% (**không đạt dự đoán**) |
| Lỗi nhẹ (câu mờ đọc thành đậm chắc chắn) | 0 | – |
| Thời gian / ảnh (trung vị, cả API) | 1,044 s | 0,7–1,5 s |
| 0105 (tô nhẹ tay) | 0 lỗi nặng; cờ `to_nhat` có ở **2/2 ảnh**; cần xem 31 và 32 câu | 0 lỗi nặng; `to_nhat` ≥ 1/2 ảnh (~60%) |
| Phiếu tự chốt khi tải | 0/20 (mọi ảnh `needs_review` lúc tải) | – |

Theo loại câu: mọi câu mờ / nhiều ô (350 câu) đều cần xem 100%, 0 lỗi nặng. Câu 1 ô đậm: cần xem 4,0%. Câu trống: 0%.

### Đóng góp của 0103 vào lỗi nặng, trước và sau khi sửa nhãn
Máy đọc ở cả hai ảnh 0103:
- cột SBD thứ 4 bubble = `3`, không cờ;
- câu 3 = `B` chắc;
- câu 5 = `C` chắc.

Tính lại theo đúng công thức `nang_cau` / `nang_cot` của `eval_dot2.py` (dòng 234, 260):
- **Nhãn gốc** (bubble cột 4 = 9, câu 3 = `-`, câu 5 = `B`): 3 lỗi nặng mỗi ảnh → **6 lỗi nặng** (0103_C3: 3, 0103_C4: 3).
- **Nhãn đã sửa** (bubble cột 4 = 3, câu 3 = `B`, câu 5 = `C`): **0 lỗi nặng**.

Ba sai lệch này đã được người dùng xác nhận trên giấy thật TRƯỚC khi máy đọc ảnh (`docs/sai_lech_dot2.md`, commit `963314e`; đăng ký bổ sung `85d00e1`).

## 3. Bảng từng ảnh
Ký hiệu cột:
- "SBD máy": `bubble / CNN viết tay`. SBD hệ thống ghi nhận (`detected_sbd`) là chuỗi bubble.
- "Nhãn": chữ viết tay theo kế hoạch, trong ngoặc là nhãn bubble (`?` = nhãn ghi cột không tô).
- "Điểm thật" = điểm đúng theo nhãn = điểm chính thức sau oracle (H5 đúng cả 20).
- Điểm tạm (`provisional`) **không được lưu** trong `ket_qua.json`. Công cụ chỉ ghi `vi_pham_can`, tức điểm tạm ≤ điểm thật ≤ điểm tối đa có thể: 0 vi phạm.

| Ảnh | ĐK | SBD máy (bubble / CNN) | SBD | Mã đề máy (bubble / CNN) | Mã đề | Câu cần xem | Điểm thật | Cuối (oracle) | Mắt: SBD / mã | Nhãn: SBD (bubble) / mã (bubble) | Mắt: nắn |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0101_C1 | C1 | 864325 / 864925 | cần xem (lech_bubble, tin_cay_thap) | 101 / 101 | nhận | 19 | 2.0 | đúng | 864325 / 101 | 864325 (864325) / 101 (101) | dung |
| 0101_C2 | C2 | 864325 / 864925 | cần xem (lech_bubble) | 101 / 101 | nhận | 19 | 2.0 | đúng | 864325 / 101 | 864325 (864325) / 101 (101) | dung |
| 0102_C2 | C2 | 097160 / 097180 | cần xem (lech_bubble) | 102 / 102 | nhận | 24 | 1.0 | đúng | 097160 / 102 | 097160 (097160) / 102 (102) | dung |
| 0102_C3 | C3 | 097160 / 097160 | nhận | 102 / 102 | nhận | 23 | 1.0 | đúng | 097160 / 102 | 097160 (097160) / 102 (102) | khong_chac |
| 0103_C3 | C3 | 183354 / 181954 | cần xem (lech_bubble) | 103 / 102 | cần xem (lech_bubble) | 17 | 1.0 | đúng | 183954 / 103 | 183954 (183354) / 103 (103) | khong_chac |
| 0103_C4 | C4 | 183354 / 183954 | cần xem (lech_bubble) | 103 / 109 | cần xem (lech_bubble) | 16 | 1.0 | đúng | 183954 / 103 | 183954 (183354) / 103 (103) | dung |
| 0104_C4 | C4 | 278103 / 278103 | nhận | 104 / 104 | nhận | 16 | 1.0 | đúng | 278103 / 104 | 278103 (278103) / 104 (104) | dung |
| 0104_C1 | C1 | 278103 / 278103 | nhận | 104 / 104 | nhận | 16 | 1.0 | đúng | 278103 / 104 | 278103 (278103) / 104 (104) | dung |
| 0105_C1 | C1 | 527694 / 527694 | nhận | 101 / 101 | nhận | 31 | 1.75 | đúng | 527694 / 101 | 527694 (527694) / 101 (101) | dung |
| 0105_C2 | C2 | 527694 / 527694 | nhận | 101 / 101 | nhận | 32 | 1.75 | đúng | 527694 / 101 | 527694 (527694) / 101 (101) | dung |
| 0106_C2 | C2 | 564901 / 564901 | nhận | 102 / 102 | nhận | 16 | 1.75 | đúng | 564901 / 102 | 564901 (564901) / 102 (102) | dung |
| 0106_C3 | C3 | 564901 / 584901 | cần xem (lech_bubble) | 102 / 102 | nhận | 16 | 1.75 | đúng | 564901 / 102 | 564901 (564901) / 102 (102) | khong_chac |
| 0107_C3 | C3 | 378273 / 378273 | **nhận** | 103 / 103 | nhận | 20 | 1.75 | đúng | **376273** / 103 | 378273 (37**?**273) / 103 (103) | khong_chac |
| 0107_C4 | C4 | 378273 / 378273 | **nhận** | 103 / 103 | cần xem (bubble_cx) | 19 | 1.75 | đúng | **376273** / 103 | 378273 (37**?**273) / 103 (103) | dung |
| 0108_C4 | C4 | 452180 / 452180 | nhận | 104 / 104 | nhận | 19 | 1.5 | đúng | 452180 / 104 | 452180 (452180) / 104 (104) | dung |
| 0108_C1 | C1 | 452180 / 452180 | nhận | 104 / 104 | nhận | 19 | 1.5 | đúng | 452180 / 104 | 452180 (452180) / 104 (104) | dung |
| 0109_C1 | C1 | 697132 / 697132 | nhận | 101 / 101 | nhận | 18 | 1.5 | đúng | 697132 / 101 | 697132 (697132) / 101 (101) | dung |
| 0109_C2 | C2 | 697132 / 697132 | nhận | 101 / 101 | nhận | 19 | 1.5 | đúng | 697132 / 101 | 697132 (697132) / 101 (101) | dung |
| 0110_C2 | C2 | 498560 / 494560 | cần xem (bubble_cx, lech_bubble) | 102 / 102 | nhận | 19 | 0.5 | đúng | 498560 / 102 | 498560 (498560) / 102 (102) | dung |
| 0110_C3 | C3 | 498560 / 194560 | cần xem (bubble_cx, lech_bubble) | 102 / 102 | nhận | 19 | 0.5 | đúng | 498560 / 102 | 498560 (498560) / 102 (102) | khong_chac |

Mọi ảnh đều ở trạng thái `needs_review` lúc tải. Sau oracle, cả 20 đều `graded`, điểm chính thức đúng.

## 4. Mọi chỗ lỗi
### 4.1 Hai lỗi nặng H2 = vi phạm H3 0107 (một nguồn)
**Chỗ lỗi:** 0107_C3 và 0107_C4, SBD **cột 3**.

**Ba nguồn đọc khác nhau:**
- Máy:
  - bubble = `8`, không cờ;
  - CNN đọc ô viết tay = `8` (p 0,69 ở C3 / 0,96 ở C4);
  - trường SBD **được nhận** = `378273`.
- Nhãn: chữ viết tay `8`; **bubble `-` (không tô)**. Kịch bản cố ý bỏ tô cột này để kiểm H3: "0107 SBD phải cần xem".
- Ảnh nắn (trích từ `xem_may.html`, khoảng 75 DPI): ở cả hai ảnh, ô **8 của cột 3 trông tô đậm rõ**, đậm như các ô tô ở các cột khác. Ảnh phóng to (tệp tạm): `C:\Users\MSI\AppData\Local\Temp\claude\C--Users-MSI-PycharmProjects-smart-exam-db-1\b677cadb-245a-443b-8a2e-61da5b9be0ce\scratchpad\r\0107_C3_sbd.png` và `…\r\0107_C4_sbd.png`.
- Kết luận mắt: không kết luận về bubble (xem mù chỉ hỏi chữ viết tay). SBD viết tay mắt ghi `376273`, tức chữ số thứ 3 = `6`. Xem 4.3.

**Phân loại:** theo bằng chứng ảnh, đây nhiều khả năng là **nhãn sai** (người tô đã tô bubble cột 3, khác kịch bản), máy đọc đúng giấy. Hệ quả: tiền đề của điều kiện H3-0107 ("thiếu bubble") không có trên giấy.

**Chưa xác nhận trên giấy thật.** Theo đăng ký, kết quả vẫn ghi **H2 không đạt, H3 không đạt**. Sửa nhãn sau khi chạy thì không được dùng để đổi kết quả này.

### 4.2 Lỗi thầm lặng khác
- Câu: lỗi nặng 0/800; chấm sai không cờ 0; lỗi nhẹ 0.
- SBD / mã đề nhận mà khác chữ viết tay theo nhãn: 0.
- Điểm: tự chốt sai 0; điểm tạm vi phạm 0; điểm cuối sai 0/20.
- **Vết bỏ sót (chỉ báo, không phải lỗi nặng theo định nghĩa):** 24 vết đọc thành trống mà không gắn cờ. Điểm không đổi vì vết không phải đáp án.
  - 0103: câu 14, 19, 22 × 2 ảnh
  - 0104: câu 3, 7, 33 × 2
  - 0105_C1: câu 11, 20, 27; 0105_C2: câu 11, 27
  - 0106: câu 9, 22, 39 × 2
  - 0109_C1: câu 26

### 4.3 SBD / mã đề: máy, nhãn, mắt
CNN đọc sai 10/180 chữ số. Cả 10 đều kéo theo cột / trường **cần xem** (lech_bubble); không trường nào bị nhận sai:
- 0101_C1, 0101_C2: SBD cột 4, viết `3`, CNN `9`
- 0102_C2: SBD cột 5, `6` → `8`
- 0103_C3: SBD cột 3, `3` → `1`; mã đề cột 3, `3` → `2`
- 0103_C4: mã đề cột 3, `3` → `9`
- 0106_C3: SBD cột 2, `6` → `8`
- 0110_C2: SBD cột 3, `8` → `4`
- 0110_C3: SBD cột 1, `4` → `1`; SBD cột 3, `8` → `4`

0103 SBD cột 4: viết `9`, bubble `3` (đúng giấy theo nhãn đã sửa). Máy để **cần xem**, đúng thiết kế hai kênh.

**Mắt khác nhãn đúng 1 chỗ:** 0107 (cả hai ảnh) SBD chữ số thứ 3, mắt `6`, còn nhãn / CNN / bubble đều `8`. Trên ảnh nắn khoảng 75 DPI, ô viết tay thứ 3 trông giống `8`. Nghi **kết luận mắt sai hoặc gõ nhầm**; cần người dùng xem lại ảnh / giấy. Tôi không sửa.

Các ô còn lại: mắt = nhãn ở 38/40 trường (20 SBD + 20 mã đề).

### 4.4 Câu: mắt, nhãn, máy khác nhau về tập ô được chọn (không kể đậm / mờ)
Tất cả câu dưới đây máy đều **gắn cần xem**, nên không có lỗi nặng và điểm không đổi.

| Ảnh | Câu | Mắt | Nhãn | Máy | Nhận định |
|---|---|---|---|---|---|
| 0101_C1, 0101_C2 | 3 | "tô đậm ở A" (`A`) | `Ab` | nhiều ô `AB`, cần xem | Máy = nhãn; **mắt khác** (có thể không thấy B mờ). Chưa xác minh |
| 0103_C3, 0103_C4 | 8 | "B mờ, D đậm" (`bD`) | `bC` | nhiều ô `BC`, cần xem | Máy = nhãn; **mắt khác** (D thay C). Chưa xác minh |
| 0110_C2, 0110_C3 | 21 | "A B D đều đậm" (`ABD`) | `ABC` | nhiều ô `ABD`, cần xem | **Máy = mắt, khác nhãn** → nghi **nhãn sai** (chưa đối chiếu giấy). Câu nhiều ô chấm sai dù là ABC hay ABD, nên điểm không đổi |
| 0105_C1 | 5 | "A và C đều mờ" (`ac`) | `ac` | `filled C`, cần xem | Mắt = nhãn; **máy đọc thiếu A mờ** nhưng đã gắn cờ |

Khác ở mức vết (chấm nhỏ):
- 0103 (2 ảnh) câu 19: mắt "B và C đều chấm nhỏ", nhãn `*B`, máy trống không cờ.
- 0104 (2 ảnh) câu 33: mắt "bỏ trống", nhãn `*D`, máy trống không cờ.

Khác ở mức đậm / mờ (cùng tập ô, máy đều cần xem):
- 0102 câu 21, 26 · 0106 câu 5, 14, 16 · 0107 câu 40 · 0110 câu 12, 22, 32, mỗi câu × 2 ảnh. Ví dụ 0106 câu 5: mắt `bc`, nhãn `BC`.
- Đây đúng là vùng mà CLAUDE.md đã ghi: người phân biệt rõ / mờ không ổn định.

## 5. Đối chiếu kết luận mắt ↔ máy (mô tả, không đổi tiêu chí)
- **Nắn (H1):**
  - mắt 15 `dung` + 5 `khong_chac`, 0 `sai`; máy không từ chối ảnh nào;
  - 5 ảnh `khong_chac` (0102_C3, 0103_C3, 0106_C3, 0107_C3, 0110_C3; ghi chú "4 góc và cạnh thấy rõ nhưng góc phải dưới ảnh nắn bị gấp nên không chắc") ghi nguyên là **chưa kết luận được**. Cả 5 đều là ảnh C3.
- **SBD / mã đề:** 38/40 trường mắt = nhãn viết tay; 2 trường khác là 0107 SBD (mục 4.3).
- **Câu:**
  - Mắt ghi 410 dòng câu, đúng bằng 410 câu có nhãn mờ / nhiều / vết được liệt kê trong `xem_mu.html` (không thiếu, không thừa).
  - Kết luận viết bằng lời được chuyển sang ký hiệu bằng script. 4 chỗ phải hiểu theo chính tả: "C mở" (0101_C1 câu 28), "C mò" (0110 câu 35, × 2) → mờ; "chám nhỏ" (0102_C2 câu 35) → chấm nhỏ.
  - Mắt = nhãn (đủ ký hiệu đậm / mờ / vết): 382/410.
  - Mắt = nhãn (tập ô được chọn): 404/410.
  - Mắt = máy (tập ô được chọn; vết coi khớp khi máy đọc trống): **395/410**. 15 khác:
    - 6 ở bảng 4.4: 0101 câu 3 × 2, 0103 câu 8 × 2, 0105_C1 câu 5. Riêng 0110 câu 21 có máy = mắt.
    - 9 vết mà máy đọc thành **ô mờ** và gắn cần xem (`o_mo`): 0107 câu 10, 35 × 2; 0108 câu 25, 30 × 2; 0110 câu 23 × 2.

## 6. Quan sát (chỉ số liệu, không suy diễn nguyên nhân)
| ĐK | Ảnh | Câu cần xem | Vết gắn cờ | F1 mờ | Chữ số CNN đúng | Ảnh có SBD / mã cần xem |
|---|---|---|---|---|---|---|
| C1 | 5 | 103/200 (51,5%) | 8/15 | 0,70 | 44/45 | 1/5 |
| C2 | 6 | 129/240 (53,8%) | 13/18 | 0,71 | 51/54 | 3/6 |
| C3 | 5 | 95/200 (47,5%) | 9/15 | 0,89 | 40/45 | 3/5 |
| C4 | 4 | 70/160 (43,8%) | 6/12 | 0,93 | 35/36 | 2/4 |

- **Vết bỏ sót theo phiếu:** 0103 6, 0104 6, 0105 5, 0106 6, 0109 1, các phiếu khác 0. Theo người viết: B 12, C 11, E 1, A 0, D 0. Ở các phiếu này, hai ảnh của cùng phiếu có số gắn cờ gần như giống nhau (0103, 0104, 0106: 0/3 cả hai ảnh), dù điều kiện chụp khác. Đợt 2 dùng chấm khoảng 1,5 mm (khoảng 250 px), còn `vet_nho` chỉnh ở 90 px (giới hạn này đã ghi trong đăng ký). Chưa có bằng chứng tách nguyên nhân.
- **Độ phân giải:**
  - Ảnh đợt 2: 5712×4284 (24,5 MP, iPhone 16 Pro Max). Bộ dev: 4032×3024 (12,2 MP).
  - Từ chối 0/20; thời gian trung vị 1,044 s / ảnh (toàn bộ API).
  - Đợt 2 không có ảnh 12 MP cùng phiếu để so, nên **không tách được** ảnh hưởng của độ phân giải.
- **0107 (H3):** SBD **được nhận** ở 2/2 ảnh, trái với dự đoán "2/2 cần xem". Trên ảnh, bubble cột 3 có tô (mục 4.1). 0107_C4 có mã đề cần xem (`bubble_cx`, cột 3).
- 5 ảnh mắt `khong_chac` về nắn đều là ảnh C3.

## 7. Giới hạn
- 10 phiếu / 20 ảnh, 5 người viết, một điện thoại (iPhone 24 MP), một buổi chụp. Kỳ thi và đáp án là mô phỏng: điểm thật chỉ 0,5–2,0, phần lớn câu là mờ / nhiều ô / vết theo kịch bản, không giống bài thi thật.
- CI rộng: H2 cận trên 0,74% / lượt; H3 cận trên 16,8% / trường. "0 lỗi" ở H3–H5 không chứng minh tỉ lệ lỗi thật ở mức thấp.
- **H1 chưa đóng:** 5/20 ảnh mắt chưa kết luận được. Ảnh trong `xem_mu.html` / `xem_may.html` chỉ khoảng 75 DPI.
- **Nhãn chưa chắc là đúng giấy** ở ít nhất 0107 SBD bubble cột 3 và 0110 câu 21 (ảnh và máy và/hoặc mắt cùng chỉ khác nhãn). Chưa đối chiếu giấy thật. Theo đăng ký, kết quả H2 / H3 vẫn giữ là **không đạt**. Mọi sửa nhãn về sau chỉ là phân tích bổ sung, và theo đăng ký, đổi mã thì đợt 2 thành dev.
- Kết luận mắt viết bằng lời; việc chuyển sang ký hiệu là diễn giải của script (4 chỗ theo chính tả). Mắt không kết luận về bubble SBD / mã đề.
- Điểm tạm không được lưu trong `ket_qua.json`; chỉ có kiểm tra khoảng `vi_pham_can`.
- Không đo Android, không đo ảnh 12 MP cùng phiếu, không đo tờ nhạt thật ngoài 0105, không có lần chạy lặp để đo độ ổn định.
- Bản đối chiếu mắt ↔ máy là phân tích sau khi chạy, không có trong đăng ký.
