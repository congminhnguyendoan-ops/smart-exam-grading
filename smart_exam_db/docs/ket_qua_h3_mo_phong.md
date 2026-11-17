# Kết quả phép thử mô phỏng H3 – "ô tô trống, chữ viết tay có"

Chạy MỘT lần 2026-10-30 08:23:29 theo đăng ký `docs/dang_ky_h3_mo_phong.md` (tag `dang-ky-h3-mo-phong`, mã được kiểm `9ea19093`, biến thể ô nguồn `hang`, chỉ chọn trường đợt 2 đã nhận: True). Nguồn: `data/_eval/h3/ket_qua.json` (SHA-256 `15B75161BE482A39C6708F4E3989341B3FF69BE954ECCE120B01A3C541E9524C`), bản sao `docs/ket_qua_h3_mo_phong.json`.

## Tiêu chí

| Tiêu chí | Kết quả | Dự đoán | Đạt |
|---|---|---|---|
| T1 – trường bị xoá bubble mà hệ thống NHẬN | 0 / 20 (bị từ chối khi nắn: 0) | 0 (20/20 cần xem) | ĐẠT |
| T2 – tự chốt sai / điểm chính thức sai sau oracle | 0 (tự chốt khi tải: 0) | 0 | ĐẠT |
| T3 – trường không sửa giống đợt 2 | 19 / 20 | ≥ 19 / 20 | ĐẠT |
| KT0 – ảnh gốc PNG không sửa giống đợt 2 (kiểm công cụ, không phải tiêu chí) | 20 / 20 | 20 / 20 | – |

## 20 ca

| Ảnh | Trường | Cột | Chữ số xoá | Ô nguồn (cột, hàng) | Bubble đọc | CNN đọc (p) | Trường | Lý do hiển thị | Phiếu tải → cuối | Điểm CT / thật | T3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0101_C1 | exam_code | 2 | 0 | [1, 0] | ? | 0 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 2.0 / 2.0 | khớp |
| 0101_C2 | exam_code | 1 | 1 | [2, 1] | ? | 1 (0.99) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 2.0 / 2.0 | khớp |
| 0102_C2 | exam_code | 3 | 2 | [2, 2] | ? | 2 (0.63) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.0 / 1.0 | khớp |
| 0102_C3 | sbd | 5 | 6 | [4, 6] | ? | 6 (0.63) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.0 / 1.0 | khớp |
| 0103_C3 | sbd | 2 | 8 | [1, 8] | ? | 8 (0.68) | cần xem | chữ viết tay khác chữ số bubble; cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.0 / 1.0 | khớp |
| 0103_C4 | exam_code | 3 | 3 | [2, 3] | ? | 9 (0.43) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.0 / 1.0 | khớp |
| 0104_C4 | sbd | 1 | 2 | [2, 2] | ? | 2 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.0 / 1.0 | khớp |
| 0104_C1 | exam_code | 1 | 1 | [2, 1] | ? | 1 (0.99) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.0 / 1.0 | khớp |
| 0105_C1 | sbd | 1 | 5 | [2, 5] | ? | 5 (0.97) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.75 / 1.75 | khớp |
| 0105_C2 | sbd | 6 | 4 | [5, 4] | ? | 4 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.75 / 1.75 | khớp |
| 0106_C2 | sbd | 2 | 6 | [1, 6] | ? | 6 (0.73) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.75 / 1.75 | khớp |
| 0106_C3 | exam_code | 2 | 0 | [1, 0] | ? | 0 (0.80) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.75 / 1.75 | khớp |
| 0107_C3 | sbd | 4 | 2 | [3, 2] | ? | 2 (0.88) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.75 / 1.75 | khớp |
| 0107_C4 | sbd | 6 | 3 | [5, 3] | ? | 3 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.75 / 1.75 | khớp |
| 0108_C4 | sbd | 1 | 4 | [2, 4] | ? | 4 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.5 / 1.5 | khớp |
| 0108_C1 | exam_code | 3 | 4 | [2, 4] | ? | 4 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.5 / 1.5 | khớp |
| 0109_C1 | sbd | 3 | 7 | [2, 7] | ? | 7 (0.99) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.5 / 1.5 | khớp |
| 0109_C2 | sbd | 2 | 9 | [1, 9] | ? | 9 (0.98) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 1.5 / 1.5 | khớp |
| 0110_C2 | exam_code | 1 | 1 | [2, 1] | ? | 1 (0.99) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 0.5 / 0.5 | khớp |
| 0110_C3 | exam_code | 2 | 0 | [1, 0] | ? | 0 (1.00) | cần xem | cột bubble không đọc được (không tô / tô nhiều ô) | needs_review → graded | 0.5 / 0.5 | **khác** |

## Ca bất thường / cần lưu ý

- 0103_C3: {"status_tai": "needs_review", "tu_choi": "", "T1_nhan": false, "T2_vi_pham": false, "T3_khop": true, "truong_da_can_xem_o_dot2": true, "T3_khac": null}
- 0103_C4: {"status_tai": "needs_review", "tu_choi": "", "T1_nhan": false, "T2_vi_pham": false, "T3_khop": true, "truong_da_can_xem_o_dot2": true, "T3_khac": null}
- 0110_C3: {"status_tai": "needs_review", "tu_choi": "", "T1_nhan": false, "T2_vi_pham": false, "T3_khop": false, "truong_da_can_xem_o_dot2": false, "T3_khac": {"anh_chinh": {"can_xem": true, "ly_do": ["lech_bubble"], "detected": "498560", "cot": [{"i": 0, "bubble": "4", "may": "1", "p": 0.5859, "cx": true, "ly_do": ["lech_bubble"]}, {"i": 1, "bubble": "9", "may": "9", "p": 0.8952, "cx": false, "ly_do": []}, {"i": 2, "bubble": "8", "may": "4", "p": 0.61, "cx": true, "ly_do": ["lech_bubble"]}, {"i": 3, "bubble": "5", "may": "5", "p": 0.9876, "cx": false, "ly_do": []}, {"i": 4, "bubble": "6", "may": "6", "p": 0.84, "cx": false, "ly_do": []}, {"i": 5, "bubble": "0", "may": "0", "p": 0.9859, "cx": false, "ly_do": []}]}, "tham_chieu": {"can_xem": true, "ly_do": ["bubble_cx", "lech_bubble"], "cot": [{"i": 0, "bubble": "4", "may": "1", "cx": true, "ly_do": ["bubble_cx"]}, {"i": 1, "bubble": "9", "may": "9", "cx": false, "ly_do": []}, {"i": 2, "bubble": "8", "may": "4", "cx": true, "ly_do": ["lech_bubble"]}, {"i": 3, "bubble": "5", "may": "5", "cx": false, "ly_do": []}, {"i": 4, "bubble": "6", "may": "6", "cx": false, "ly_do": []}, {"i": 5, "bubble": "0", "may": "0", "cx": false, "ly_do": []}]}}}

### Phân tích (viết sau khi chạy, không đổi số liệu ở trên)
- **0110_C3 – T3 lệch (trường không sửa: SBD)**: kết luận cấp trường KHÔNG đổi (cần xem ở cả đợt 2 lẫn ảnh chỉnh). Chỉ **lý do của cột SBD 1** đổi:
  đợt 2 là `bubble_cx` (bubble máy chưa chắc), ảnh chỉnh là `lech_bubble` (bubble đọc chắc là 4, CNN đọc 1, p 0,59). Lý do cấp trường đổi theo:
  `[bubble_cx, lech_bubble]` → `[lech_bubble]`. KT0 của chính ảnh này KHỚP, nên lệch do CHỖ SỬA chứ không do đường PNG. Chỗ sửa ở mã đề cột 2,
  xa cột SBD 1. Giả thuyết (CHƯA kiểm chứng, không chạy thêm trên ảnh đợt 2): thang đo OMR phụ thuộc cả tờ, đúng nợ kỹ thuật "thang `S_anh` phụ thuộc
  cả tờ" (`docs/ke_hoach_tuan5.md` mục 15). Bỏ một ô tô đậm làm đổi thang, nên một cột sát ngưỡng chuyển từ "chưa chắc" sang "chắc". Hệ quả an toàn:
  trường vẫn cần xem, nhưng điều này cho thấy độ tin cậy bubble của một cột có thể phụ thuộc phần khác của tờ.
- **0103_C3, 0103_C4**: phiếu 0103 không có trường nào được nhận ở đợt 2 (cả SBD lẫn mã đề đều cần xem), nên "cần xem" ở hai ca này KHÔNG quy riêng được
  cho việc xoá ô. Phần T1 có ý nghĩa là **18/18** ca còn lại. Ở 0103_C4, CNN đọc chữ viết tay "3" thành "9" (p 0,43; đợt 2 cũng đọc 9). Trường cần xem,
  giáo viên oracle chốt đúng, điểm chính thức đúng.
- Ở cả 20 ca, cột bị xoá đọc ra `?` với lý do cột `thieu_bubble` ("cột bubble không đọc được (không tô / tô nhiều ô)"). Không có phiếu nào tự chốt
  khi tải; sau giáo viên oracle, 20/20 điểm chính thức bằng điểm thật.
- Độ tối ruột ô sau khi xoá cao hơn trung vị ô trống cùng cột tối đa 0,017 (thang 0–1). Ô bị tô trước khi xoá có độ tối ≥ 0,477
  (`data/h3_mo_phong/bang.json`).

## Giới hạn

- Ảnh chỉnh bằng phần mềm (chép điểm ảnh của một ô trống thật trên chính ảnh sang vị trí ô đã tô), KHÔNG phải ô để trống trên giấy: không phản ánh đặc tính quang học thật của ô chưa từng tô (vết tẩy, lõm giấy, bóng bút chì còn sót).
- Chỉ kiểm LOGIC hai kênh (bubble ↔ chữ viết tay) khi một cột bubble trống; không đo lại độ chính xác OMR / CNN.
- Một điện thoại (bộ ảnh đợt 2), 5 người viết.
- 20 ca KHÔNG độc lập: hai ảnh của cùng một phiếu (cùng nét viết, cùng tờ giấy).
- Chưa thay thế phép thử bằng giấy thật (để trống một cột bubble khi tô).
