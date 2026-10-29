# Sai lệch giữa kế hoạch tô và giấy thật – đợt 2

**Nguồn:** nhóm người tô báo cho người dùng ngày **29/10/2026**. Người tô ghi lại ngay lúc tô, **không tẩy**.
**Tình trạng:** đây là **lời nhóm khai TRƯỚC khi máy đọc ảnh đợt 2**. **Chưa đối chiếu** với ảnh hay với giấy (chưa ai kiểm lại).
Tại thời điểm ghi tệp này, chưa có công cụ nào đọc SBD, mã đề hay ô tô của ảnh đợt 2. Ảnh đã khoá SHA ở `docs/sha_anh_dot2.txt`.

Chỉ phiếu **0103** có sai lệch (ảnh `0103_C3`, `0103_C4`). Theo lời nhóm, các phiếu 0101, 0102 và 0104–0110 tô đúng kế hoạch.

| # | Phiếu | Vị trí | Kế hoạch (nhãn đăng ký) | Thực tế trên giấy (nhóm khai) | Mục trong nhãn | Ai báo | Thời điểm |
|---|---|---|---|---|---|---|---|
| 1 | 0103 | SBD – bubble cột 4 | tô `9` (bubble `183954`) | tô `3` → bubble đọc `183354`; chữ **viết tay vẫn đúng `183954`** | `sbd_bubble`: `183954` → `183354` (`sbd` giữ `183954`) | nhóm | 29/10/2026 |
| 2 | 0103 | Câu 3 | bỏ trống (`-`) | tô **ĐẬM ô B** | `q3`: `-` → `B` | nhóm | 29/10/2026 |
| 3 | 0103 | Câu 5 | tô B (`B`) | tô **ô C** (tô nhầm B thành C; coi là tô đậm) | `q5`: `B` → `C` | nhóm | 29/10/2026 |

Ghi chú:
- Nhãn đăng ký gốc `answer_sheet/dot2/ground_truth_dot2.csv` / `cell_labels_dot2.csv` **KHÔNG sửa** (nằm trong danh sách SHA của đăng ký).
- Cách dùng hợp lệ (nếu người dùng quyết): người dùng kiểm **giấy thật** rồi ghi `data/dot2/sua_nhan.csv` → `python tools/eval_dot2.py ap-dung-sua` → ghi SHA 3 tệp vào `bo_sung` của
  `docs/dang_ky_test_dot2.json` (commit riêng) TRƯỚC khi chạy (`docs/ke_hoach_test_dot2.md` mục 4). Không sửa nhãn theo kết quả máy.
- Bản máy đọc: `docs/sai_lech_dot2.csv` (cùng cột với `sua_nhan.csv`, thêm cột nguồn / xác nhận).
