# Lệnh BB – luật "đen đủ dày" cho ô tô gạch chéo (đăng ký tiêu chí TRƯỚC, 21/11/2026)

Tệp này được commit TRƯỚC mọi phép tính phân bố và mọi sửa đổi `cv_engine/omr.py`; không sửa sau. Kết quả ghi ở tệp khác (`docs/ket_qua_luat_den_day.md`).

## 1. Vấn đề

Phiếu 23535 (tệp `f231d104…`) câu 13C, 21B, 28C và phiếu 23536 (tệp `637e41f6…`) câu 10A tô đậm kiểu gạch chéo. Máy đọc đúng ô nhưng trả `mo` (`o_mo`) vì p(rõ | có tô) = 0,435 / 0,484 / 0,122 / 0,238 < `ro_min` 0,5, nên câu vào hàng đợi duyệt dù ô đen dày.

## 2. Luật được đăng ký

Hàm mới trong `cv_engine/omr.py`, gọi SAU `them_to_nhat`, ngưỡng là hằng số trong `omr.py` (KHÔNG sửa `models/*.json`, SHA mô hình không đổi).

Áp cho một câu khi và chỉ khi:
1. đúng một ô được chọn (`len(dap_an) == 1`), `trang_thai == "mo"` và `ly_do == ("o_mo",)` (câu có `vi_tri`, `vet_nho`, `tin_cay_thap`, `to_nhat` hay lý do khác thì KHÔNG áp);
2. ô được chọn có đồng thời `phu_dam ≥ 0,85`, `tuyet_doi ≥ 0,65` và `phu_nhe ≥ 0,95` (ba cột của `dac_trung_o`, tính trên đúng nguồn ảnh của mô hình).

Khi áp: `trang_thai = "ro"`, bỏ `o_mo`, `can_xem = False`, giữ nguyên `xac_suat` gốc. Không áp cho bubble chữ số.

**Ngưỡng ứng viên 0,85 / 0,65 / 0,95 là ngưỡng CUỐI**, đặt trước khi nhìn dữ liệu. Không chỉnh lại sau khi thấy kết quả. Nếu không đạt thì áp dụng mục (e), không thử ngưỡng khác.

## 3. Dữ liệu dùng, và dữ liệu cấm

- Phân bố và biên (b): ảnh train 0001–0028 và val 0029–0034 (nhãn `data/cell_labels.csv`), qua `tools/omr_du_lieu.ds_anh` và `cv_engine/tap_du_lieu` (không tự định nghĩa ranh giới). Val được dùng ở đây theo chỉ định của lệnh BB (21/11/2026), chỉ để ĐO phân bố; không có hệ số nào được khớp từ val.
- KHÔNG đọc ảnh / nhãn tập test 0035–0040. Không sửa `ground_truth.csv`. Không ghi vào CSDL.
- 4 ô gạch chéo và 4 ô nhạt thật ở mục (c) do người dùng đã nêu số đo từ trước nên KHÔNG phải dữ liệu giữ kín; (c) chỉ kiểm luật làm đúng điều lệnh yêu cầu, không phải bằng chứng tổng quát hoá.

## 4. Tiêu chí (tất cả phải đạt)

**(a) 56 ảnh dev (train).** Chạy `doc_phieu` trước / sau luật trên cùng ảnh nắn. Sau luật: 0 lỗi nặng (câu có nhãn đáp án khác đáp án máy mà `can_xem = False` – đúng định nghĩa của `tools/eval_omr.py`), 0 câu chấm sai không cờ so với nhãn, số câu cần xem KHÔNG tăng so với trước; mọi câu đổi trạng thái phải có nhãn ô tương ứng là `filled` và trùng đáp án máy; các câu khác giống hệt từng trường.

**(b) Biên với ô mờ, train + val.** Tập ô mờ = mọi ô nhãn `faint` thuộc câu có đúng một ô khác `blank` (`cell_labels.csv`), tính đặc trưng bằng `dac_trung_o` tại ô đó bất kể máy đọc gì. Với mỗi ô mờ c, biên `g(c) = max_f (t_f − f(c))` trên f ∈ {phu_dam, tuyet_doi, phu_nhe} (ô mờ bị loại nếu trượt ít nhất một điều kiện; g là mức trượt lớn nhất). Đạt khi: không ô mờ nào thoả cả ba điều kiện và `min_c g(c) ≥ 0,20`. Phụ: không câu nhãn `faint` nào bị đổi thành `ro` khi chạy `doc_phieu` trên train + val.

**(c) Bốn ô gạch chéo / bốn ô nhạt thật.** Chạy `cv_engine` trên tệp trong `storage/uploads/9696` (chỉ đọc tệp): 23535 `f231d104…` câu 13C, 21B, 28C và 23536 `637e41f6…` câu 10A phải thành `trang_thai = "ro"`, không còn `o_mo`; 23536 câu 1, 33 và 23535 câu 10D, 40C vẫn `mo` với `o_mo`. Nếu phiếu nào mang cờ `to_nhat` thì ghi rõ và luật không được áp cho câu đó (đúng thiết kế), kết luận (c) theo từng ô.

**(d) 13 ảnh giấy thật `data/anh_that_ag`.** Trước / sau luật; "lỗi im lặng mới" = câu mà sau luật máy đọc khác nhãn kịch bản (`data/_eval/ag/kich_ban.json`) và `can_xem = False`, nhưng trước luật không phải như vậy. Đạt khi số này = 0. Không dùng `tools/ag_cham_that.py cham` (khoá một lần theo `docs/tieu_chi_thu_giay_that.md`); dùng công cụ so sánh riêng của lệnh BB. Ghi thêm số câu thoát khỏi hàng đợi.

**(e) Không đạt bất kỳ mục nào** thì KHÔNG sửa `cv_engine/omr.py`, không gộp; báo cáo bảng số đo và dừng chờ quyết định.

## 5. Việc kèm theo (không phải tiêu chí chấp nhận)

- Test đơn vị: ô gạch chéo → rõ; ô nhạt → mờ; phiếu `to_nhat` vẫn đưa mọi câu vào duyệt; ô nhiều lý do không bị đổi; pytest cũ không vỡ.
- `cv_engine/omr.py` là tệp khung đóng băng: thêm bản ghi băm kế tiếp (ngày, lệnh, commit, lý do), cập nhật test so với bản ghi mới nhất, KHÔNG sửa `docs/dong_bang_ma_dot2.json`.
- Đo trước / sau trên 4 phiếu 23533–23536 (`fdcd3572…`, `43de3be6…`, `f231d104…`, `637e41f6…`), liệt kê câu cần xem trước / sau. Chỉ chạy `cv_engine` trên tệp, không ghi CSDL.
