# Phân tích SAU CHẠY – test đợt 2 (29/10/2026)

> **Đây là phân tích sau chạy, KHÔNG phải nhãn đăng ký.** Người dùng kiểm giấy thật lúc **20:19 ngày 29/10/2026**,
> tức SAU khi chạy test (18:02–18:03) và SAU khi xem kết quả máy.
> Không phát hiện nào dưới đây được đưa vào nhãn (`data/dot2/*_da_sua.csv` giữ nguyên SHA trong `bo_sung`), mã, ngưỡng, đăng ký
> hay kết luận mắt đã khoá (`a4da472`). Kết quả chính thức: `docs/ket_qua_dot2.md`, `docs/ket_qua_dot2.json`.

## a) Bốn kiểm tra trên giấy thật (20:19, 29/10/2026)
| Phiếu / mục | Giấy thật | Nhãn kế hoạch (đăng ký) | Máy | Kết luận mắt (đã khoá) | Hệ quả |
|---|---|---|---|---|---|
| **0107 SBD cột 3** | bubble **có tô**, ô **8**; chữ viết tay **8** | chữ viết tay `8`, bubble **cố ý KHÔNG tô** (`-`) | bubble `8`, CNN `8`, không cờ; trường SBD được nhận `378273` (cả 2 ảnh) | không kết luận về bubble; chữ viết tay ghi `376273` (chữ số thứ 3 = `6`) | Máy đọc **đúng giấy**. Hai lỗi nặng H2 là do nhãn khác giấy. Tình huống H3 cần kiểm ("bubble trống, chữ có số, hai kênh lệch") **CHƯA xảy ra** trên giấy → H3 ở trường hợp này **chưa được kiểm chứng** (không ghi là đạt). Kết luận mắt `6` khác giấy (`8`) |
| **0110 câu 21** | tô **ĐẬM A, B, D** | `ABC` (A+B+C) | nhiều ô `ABD`, cần xem (cả 2 ảnh) | "A B D đều đậm" | Máy **đúng giấy**; nhãn khác giấy. Câu nhiều ô bị chấm sai dù là ABC hay ABD → điểm không đổi |
| **0101 câu 3** | **A đậm, B mờ** | `Ab` (đúng giấy) | nhiều ô `AB`, cần xem (cả 2 ảnh) | "tô đậm ở A" | Nhãn và máy đúng giấy. Kết luận mắt **thiếu "B mờ"** → thiếu sót của người xem mù |
| **0103 câu 8** | **B mờ, C đậm** | `bC` (đúng giấy) | nhiều ô `BC`, cần xem (cả 2 ảnh) | "B mờ, D đậm" | Nhãn và máy đúng giấy. Kết luận mắt **sai một ô** (ghi D đậm thay vì C đậm) → thiếu sót của người xem mù |

## b) Các chỗ tô khác kế hoạch đã biết
| Phiếu | Số chỗ | Chỗ | Phát hiện lúc | Áp dụng vào nhãn? |
|---|---|---|---|---|
| 0103 | 3 | SBD bubble cột 4 (`9` → `3`), câu 3 (`-` → `B`), câu 5 (`B` → `C`) | nhóm khai, người dùng xác nhận giấy thật 29/10/2026, **TRƯỚC khi chạy** (`docs/sai_lech_dot2.md`) | **Có**: `data/dot2/*_da_sua.csv`, SHA ở `bo_sung` của đăng ký |
| 0107 | 1 | SBD bubble cột 3: kế hoạch không tô, giấy tô `8` | **SAU khi chạy** (20:19) | **Không** |
| 0110 | 1 | câu 21: kế hoạch `ABC`, giấy `ABD` (đậm cả ba) | **SAU khi chạy** (20:19) | **Không** |

Tổng đã biết: **5 chỗ trên 3 phiếu.** 3 chỗ đã áp dụng trước khi chạy; 2 chỗ phát hiện sau khi chạy và không áp dụng.
Các câu khác chưa được rà toàn bộ trên giấy, nên có thể còn chỗ chưa biết.

## c) Tiêu chí: theo đăng ký và phân tích sau chạy
- **Theo đăng ký (chính thức, không đổi): H2 KHÔNG ĐẠT (2/980), H3 KHÔNG ĐẠT** (0107 SBD cần xem 0/2), H4 đạt, H5 đạt.
  H1 chưa kết luận được đầy đủ (5 ảnh mắt `khong_chac`).
- **Phân tích sau chạy, chỉ báo số, không sửa nhãn:**
  - Đếm lại từ `docs/ket_qua_dot2.json` theo đúng công thức `nang_cau + nang_cot` của `tools/eval_dot2.py` (dòng 234, 260), chỉ thay nhãn bubble 0107 SBD cột 3 từ `-` thành `8` như giấy thật: **H2 = 0 / 980**. Vết đọc thành đáp án chắc vẫn là 0.
  - 0110 câu 21 không ảnh hưởng H2 vì máy đã gắn cần xem.
- **H3 ở 0107 không thể tính lại thành "đạt".** Tình huống được thiết kế để kiểm (thiếu bubble) không có trên giấy, nên đợt 2 **không kiểm chứng** được hành vi "bubble trống + chữ viết có số → cần xem". Muốn kiểm phải dùng phiếu mới (đợt sau) có bubble trống thật.
- Theo đăng ký (mục giới hạn): đổi mã về sau thì đợt 2 thành dev. Các con số sau chạy ở đây không thay kết quả chính thức.

## d) 15 chỗ mắt khác máy (395/410 câu cùng tập ô được chọn)
Nguồn: so khớp tập ô được chọn giữa kết luận mắt (`docs/ket_luan_mat_dot2.csv`, chuyển lời → ký hiệu bằng script) và kết quả máy (`docs/ket_qua_dot2.json`).
Ký hiệu nhãn: `B` đậm, `b` mờ, `*B` vết. Máy: trạng thái + ô đọc được. Mọi chỗ dưới đây máy đều **gắn cần xem**.

| # | Ảnh | Mục | Máy | Nhãn kế hoạch | Kết luận mắt | Kiểm giấy |
|---|---|---|---|---|---|---|
| 1 | 0101_C1 | câu 3 | multiple `AB` | `Ab` | "tô đậm ở A" | **ĐÃ KIỂM**: A đậm, B mờ (máy, nhãn đúng; mắt thiếu) |
| 2 | 0101_C2 | câu 3 | multiple `AB` | `Ab` | "tô đậm ở A" | **ĐÃ KIỂM** (cùng phiếu 0101) |
| 3 | 0103_C3 | câu 8 | multiple `BC` | `bC` | "B mờ, D đậm" | **ĐÃ KIỂM**: B mờ, C đậm (máy, nhãn đúng; mắt sai một ô) |
| 4 | 0103_C4 | câu 8 | multiple `BC` | `bC` | "B mờ, D đậm" | **ĐÃ KIỂM** (cùng phiếu 0103) |
| 5 | 0105_C1 | câu 5 | filled `C` | `ac` | "A và C đều mờ" | chưa kiểm giấy |
| 6 | 0107_C3 | câu 10 | faint `B` | `*B` | "chấm nhỏ B" | chưa kiểm giấy |
| 7 | 0107_C3 | câu 35 | faint `B` | `*B` | "chấm nhỏ B" | chưa kiểm giấy |
| 8 | 0107_C4 | câu 10 | faint `B` | `*B` | "chấm nhỏ B" | chưa kiểm giấy |
| 9 | 0107_C4 | câu 35 | faint `B` | `*B` | "chấm nhỏ B" | chưa kiểm giấy |
| 10 | 0108_C4 | câu 25 | faint `B` | `*B` | "chấm nhỏ B" | chưa kiểm giấy |
| 11 | 0108_C4 | câu 30 | faint `D` | `*D` | "chấm nhỏ D" | chưa kiểm giấy |
| 12 | 0108_C1 | câu 25 | faint `B` | `*B` | "chấm nhỏ B" | chưa kiểm giấy |
| 13 | 0108_C1 | câu 30 | faint `D` | `*D` | "chấm nhỏ D" | chưa kiểm giấy |
| 14 | 0110_C2 | câu 23 | faint `D` | `*D` | "chấm nhỏ D" | chưa kiểm giấy |
| 15 | 0110_C3 | câu 23 | faint `D` | `*D` | "chấm nhỏ D" | chưa kiểm giấy |

Ghi chú:
- **0110 câu 21 không nằm trong 15 chỗ này** vì máy và mắt cùng đọc `ABD`. Chỗ này chỉ khác nhãn và đã kiểm giấy ở mục a.
- Chỗ 6–15 là vết theo nhãn và theo mắt, nhưng máy đọc thành ô mờ và gắn cần xem (`o_mo`). Điểm không đổi.
- Chỗ 5: mắt và nhãn đều ghi hai ô mờ; máy đọc một ô C và gắn cần xem.
- Chưa kiểm giấy: **11 chỗ trên 5 phiếu.** Các chỗ khác mắt ↔ nhãn ở mức vết / đậm–mờ (báo cáo lệnh R mục 4.4) cũng chưa kiểm giấy.
