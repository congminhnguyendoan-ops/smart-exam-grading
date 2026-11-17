# Lệnh AM – kết quả CNN sâu `sau_2x2` so với CNN hiện tại

Ngày: 16/11/2026 · nhánh `cnn-sau` · tiêu chí ĐÃ đăng ký trước: `docs/tieu_chi_cnn_sau.md` (commit `4f97e6f`), KHÔNG sửa · công cụ `tools/am_cnn_sau.py` (`huan-luyen`, `do`) · số liệu thô `data/_eval/am/ket_qua.json` (ngoài git).
Mô hình ứng viên: `data/_eval/am/ocr_cnn_sau_seed{2026,1,2}.json` (ngoài git, ngoài `models/`). **`models/ocr_cnn.json` không bị ghi.**

Giao thức: tiền huấn luyện MNIST 55 000 (10 epoch, lr 2e-3, Adam + cosine) → tinh chỉnh trang D (6 epoch, lr 3e-4, lô 64); 3 seed (2026, 1, 2), không bỏ / thay seed; τ = 0,9995, δ = 0,99 giữ nguyên; T cực tiểu NLL trên OOF trang D (cả 3 seed T = 1,80).
(a) dùng OOF 5-fold theo người viết; mô hình ứng viên = tinh chỉnh trên toàn bộ trang D. Baseline = CNN hiện tại đo cùng cách (OOF `g0_goc` + CNN triển khai trên ô AG). Cả 3 seed huấn luyện xong, không lỗi (344 / 362 / 370 giây).

## Bảng tiêu chí

| Tiêu chí | Ngưỡng đăng ký | Kết quả | |
|---|---|---|---|
| (a) trường đọc đúng cả chuỗi, 112 trường dev, TB 3 seed | tăng ≥ 5 điểm | CNN sâu **83,63%** (82,14 / 83,93 / 84,82; SD 1,36) so với baseline **67,56%** → **+16,07 điểm** | **ĐẠT** |
| (b) lỗi im lặng, dev | 0 | 0 ở cả 3 seed (baseline 0) | **ĐẠT** |
| (b) lỗi im lặng, 13 ảnh AG (26 trường) | 0 | 0 ở cả 3 seed (baseline 0); đọc đúng cả chuỗi 92,31% ở cả 3 seed = baseline | **ĐẠT** |
| (c) cùng nhãn NumPy / PyTorch (2 504 ô: 2 000 MNIST test + 504 ô phiếu dev) | ≥ 99,9% | 100% ở cả 3 seed | **ĐẠT** |
| (c) logit lệch tối đa | ≤ 1e-4 | 7,6e-6 / 1,1e-5 / 1,1e-5 (logit lớn nhất ≈ 40–43) | **ĐẠT** |
| (d) tốc độ NumPy từng ô, trung vị (3 lần đo × 500 ô, đã làm nóng) | ≤ 5 ms | seed 2026: 3,34 / 3,62 / 3,72 · seed 1: 3,50 / 3,34 / 3,66 · seed 2: 3,29 / 3,38 / 3,32 ms | **ĐẠT** |
| (d) pytest | không giảm | 570 đạt + 1 bỏ qua có chủ đích (mốc trước lệnh: 567 + 1; +3 test mới) | **ĐẠT** |
| (e) quyết định | không đạt → giữ CNN hiện tại | (a)–(d) đều đạt nên điều kiện "giữ" **không bị kích hoạt**; nhưng KHÔNG triển khai trong lệnh này (xem Kết luận) | — |

Tham khảo (không thuộc tiêu chí): p95 tốc độ từng ô của CNN sâu 12–25 ms (đuôi chậm; CNN hiện tại 0,8–0,9 ms, trung vị 0,63–0,69 ms). Hệ thống cần xem (cả 112 trường, TB 3 seed): 42,3 → 22,7 trường (seed 2026: 24, seed 1: 23, seed 2: 21). Ca nhận sai không cờ: 0.
Lần chạy AK trước (cùng cấu hình, huấn luyện lại) cho 81,25%; lần này 83,63% – chênh do huấn luyện không tất định trên máy này (AK `kiem-tat-dinh`); dùng số lần này làm kết quả, số AK chỉ để đối chiếu.

## Kết luận
Theo đúng ngưỡng đã đăng ký, CNN sâu đạt (a)–(d): đọc đúng cả chuỗi nhiều hơn 16 điểm ở dev, không có lỗi im lặng, NumPy khớp PyTorch, chậm hơn ~5 lần nhưng còn xa giới hạn 5 ms. Điều kiện (e) "giữ CNN hiện tại" không kích hoạt. **Chưa nên coi đây là bằng chứng đủ để thay mô hình triển khai**: xem giới hạn. Việc thay `models/ocr_cnn.json` (và `OCR_MODEL`) cần đăng ký + kiểm thử riêng (tiêu chí §4.5), nằm ngoài lệnh AM.

## Giới hạn
1. **Dev lạc quan**: 4 người viết của phiếu dev có trong huấn luyện (trang D); OOF theo người viết giảm nhưng không loại bỏ. Mức +16 điểm là cận lạc quan.
2. **Giấy thật không phân biệt được**: 13 ảnh AG (26 trường, 1 trường = 3,8 điểm) cho kết quả y hệt baseline (92,31%; cùng 2 trường mã đề sai chuỗi). AG đã bị nhìn thấy, chỉ dùng kiểm (b); với 26 trường, (b) = 0 chỉ là "không thấy lỗi", không phải bằng chứng lỗi im lặng = 0.
3. Lỗi im lặng được giữ ở 0 nhờ đối chiếu hai kênh (bubble + CNN), không nhờ mạng sâu; mạng sâu chỉ đổi số trường cần xem.
4. Huấn luyện không tất định: 3 seed dao động 82,1–84,8 (SD 1,36); baseline CNN hiện tại là một mô hình (bộ đệm), không có dao động tương ứng.
5. Tốc độ: trung vị đạt nhưng đuôi (p95) tới 25 ms/ô; trung vị 3,3–3,7 ms sát hơn 5 ms so với mạng cũ (0,65 ms). Đo trên máy phát triển.
6. Chưa chạy val 0029–0034, test 0035–0040, đợt 2, không đo trên người viết lạ.
