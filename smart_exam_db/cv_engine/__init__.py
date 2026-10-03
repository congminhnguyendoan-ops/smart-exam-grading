"""
cv_engine - lõi xử lý ảnh của hệ thống chấm thi (Tuần 4 trở đi).

Dự kiến (theo HUONG_DAN.md, Phần C):
    preprocessing.py  nắn phẳng ảnh phiếu, kiểm tra kết quả nắn (Tuần 4)
    roi.py            cắt ô đáp án / bubble SBD / ô chữ số viết tay
    omr.py            phân loại ô blank / filled / faint (Tuần 5)
    ocr.py            CNN nhận diện chữ số (Tuần 6)

Toạ độ phiếu KHÔNG khai báo ở đây: luôn đọc từ answer_sheet/output/layout.json
(sinh từ answer_sheet/sheet_layout.py).
"""
