# Lệnh AN – kết quả: thay mô hình triển khai bằng CNN sâu

Ngày: 16/11/2026 · nhánh `cnn-sau` · tiêu chí đăng ký TRƯỚC: `docs/tieu_chi_thay_mo_hinh_an.md` (commit `3c2942c`), không sửa · công cụ đo `tools/an_do_thay_mo_hinh.py` (commit `04a7ee1`, chạy MỘT lần) · số liệu thô `data/_eval/an/ket_qua.json` (ngoài git).

**Kết luận: (i)–(v) đều ĐẠT → ĐÃ THAY** `models/ocr_cnn.json` bằng CNN sâu `sau_2x2` seed 2026 (trọng số đúng như tệp đã đo).
- SHA cũ `6d87205c83a29fccc4eb450f0aec0c9d51ba56e1bb141664060041ab0f2fcad5` (sao lưu `data/_eval/an/ocr_cnn_hien_tai_sao_luu.json` + `.sha256`, trùng SHA).
- SHA tệp ứng viên đã đo `9e84b909…eb048` (`data/_eval/am/ocr_cnn_sau_seed2026.json`); SHA mới của `models/ocr_cnn.json` `a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8` (= tệp ứng viên + siêu dữ liệu; mảng `thanh_vien` giống từng giá trị, kiểm trong `xuat_ocr.py --tu-tep`).

## Dữ liệu đo (đã nêu trước khi đo)
Val 0029–0034 + test 0035–0040 = 24 ảnh, 48 trường (24 SBD + 24 mã đề), 0 ảnh bị từ chối. Người viết: người 4 (8 ảnh, val 0029–0032) và người 5 (16 ảnh: val 0033–0034 + test 0035–0040); cả hai đều có trong dữ liệu huấn luyện (trang D), người 4 còn có phiếu dev → chỉ đo "nét chữ đã gặp". Val và test đã được dùng cho CNN hiện tại trước đó.

## Bảng điều kiện
| Điều kiện | Ngưỡng đăng ký | Kết quả | |
|---|---|---|---|
| (i) lỗi im lặng, val+test | 0 | ứng viên **0** (CNN cũ 0); trường "nhận" 39/48 (cũ 35/48) | **ĐẠT** |
| (ii) trường đúng cả chuỗi | ứng viên ≥ hiện tại | **41/48** so với **39/48** (+2) | **ĐẠT** |
| (iii) trường cần xem | ứng viên ≤ hiện tại | **9/48** so với **13/48** (−4) | **ĐẠT** |
| (iv) pytest sau khi thay | ≥ 570 đạt, 1 bỏ qua | **571 đạt, 1 bỏ qua** (209 s) | **ĐẠT** |
| (v) đầu-cuối backend, 56 ảnh dev, mô hình mới | 0 lỗi im lặng | câu chấm sai không cờ 0 / 1 680 câu chắc; SBD sai im lặng 0; mã đề sai im lặng 0; điểm chính thức khớp 56/56; ảnh có SBD / mã đề cần xem **20/56** (cũ 26/56) | **ĐẠT** |

Chi tiết (i)–(iii): val: đúng cả chuỗi 21/24 (ứng viên) so với 22/24 (cũ), cần xem 3 so với 3; test: 20/24 so với 17/24, cần xem 6 so với 10. Theo người: xem `ket_qua.json`. Ca duy nhất ứng viên kém hơn: 0031_C3 mã đề (đọc sai chuỗi nhưng cùng cờ "cần xem" như cũ). Bốn trường cải thiện đều ở test (0035_C4 SBD, 0038_C3 mã đề được bỏ cờ, 0039_C3 SBD, 0039_C4 SBD).

## Thay đổi để thay mô hình
- `models/ocr_cnn.json` (SHA mới). `tools/xuat_ocr.py --tu-tep` (ghi từ tệp đã đo, KHÔNG huấn luyện lại – chệch có chủ đích so với "xuat_ocr huấn luyện", đã đăng ký ở mục 1 của tiêu chí).
- Test ghim mô hình được cập nhật CÓ CHỦ ĐÍCH (chỉ `tests/test_ocr_suy_luan.py`): `test_numpy_khop_pytorch_tren_moi_chu_so_dev` dựng đúng mạng theo `kien_truc`; `test_mo_hinh_cu_van_nap_nhu_truoc` → `test_mo_hinh_trien_khai_la_cnn_sau`; thêm `test_nhanh_mo_hinh_co_ban_van_nap_va_chay` (nhánh mô hình cũ vẫn chạy bằng tệp tạm). Không test nào bị nới hoặc xoá kiểm tra; `test_sieu_du_lieu_mo_hinh` giữ nguyên và vẫn đạt (siêu dữ liệu `git_sach`, `tuong_duong_numpy_torch`, `do_luong.IL = 0`).
- `tools/demo_may_hoc.py`: đếm tham số CNN theo mọi khoá (trước đây khoá `c1w…` cố định → `KeyError`). Không đổi gì khác.

## Giới hạn
1. 48 trường, 1 trường = 2,1 điểm; chênh +2 / −4 trường là số đếm, không có ý nghĩa thống kê. Điều kiện (ii)/(iii) chỉ đòi "không kém hơn".
2. "Nét chữ đã gặp": cả hai người viết đã có trong huấn luyện; test toàn một người. Lợi ích với người viết lạ chỉ có ở OOF 5-fold (67,56% → 83,63%, lệnh AM).
3. Val và test đã dùng cho CNN cũ; lần này dùng lại để ra quyết định chọn mô hình ⇒ không còn "chưa thấy" tuyệt đối; giữ nguyên tắc: không chỉnh gì thêm theo kết quả này.
4. Lỗi im lặng = 0 nhờ đối chiếu hai kênh, không nhờ mạng sâu; "không thấy lỗi" trên 39 trường nhận không chứng minh lỗi = 0.
5. Chi phí: mô hình ~5,9 MB (cũ 1,3 MB), 467 818 tham số (cũ 105 866), ≈ 5 lần chậm hơn mỗi ô (trung vị 3,3–3,7 ms); `test_thoi_gian_cat_9_o_va_suy_luan` (≤ 50 ms / phiếu) vẫn đạt.
