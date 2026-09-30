import asyncio
from playwright.async_api import async_playwright

CSS = """
*{box-sizing:border-box;font-family:Arial,Helvetica,sans-serif}
body{margin:0;background:#fff;color:#222;width:1200px}
.app{display:flex;min-height:720px;border:2px solid #333}
.side{width:200px;background:#e6e6e6;border-right:2px solid #333;padding:14px}
.side .logo{font-weight:bold;margin-bottom:18px;font-size:15px}
.side div.item{padding:8px 10px;margin:4px 0;border:1px solid #999;background:#f5f5f5;font-size:13px}
.side div.act{background:#bbb;font-weight:bold}
.main{flex:1;padding:18px}
h2{margin:0 0 12px;font-size:20px}
.row{display:flex;gap:12px;margin-bottom:12px}
.box{border:2px solid #555;background:#f2f2f2;padding:10px;font-size:13px}
.kpi{flex:1;text-align:center}.kpi b{display:block;font-size:24px;margin-top:4px}
.btn{display:inline-block;border:2px solid #333;background:#ccc;padding:6px 14px;font-size:13px;margin-right:6px}
.btn.p{background:#555;color:#fff}
.in{border:1px solid #555;background:#fff;padding:6px;font-size:12px;color:#777;margin:4px 0}
table{border-collapse:collapse;width:100%;font-size:12px}
td,th{border:1px solid #777;padding:5px;text-align:left}th{background:#d5d5d5}
.img{background:repeating-linear-gradient(45deg,#ddd,#ddd 10px,#eee 10px,#eee 20px);border:2px dashed #555;display:flex;align-items:center;justify-content:center;color:#555;font-size:13px}
.tag{border:1px solid #333;padding:1px 6px;font-size:11px;background:#fff}
.note{font-size:11px;color:#555;font-style:italic}
.bar{display:flex;align-items:flex-end;gap:10px;height:170px;border-left:2px solid #333;border-bottom:2px solid #333;padding:0 10px}
.bar div{flex:1;background:#999}
"""
MENU = ["Dashboard","Kỳ thi & đáp án","Sinh viên","Upload & chấm","Hàng đợi review","Thống kê","Cài đặt"]
def shell(active, body):
    items = "".join(f'<div class="item {"act" if m==active else ""}">{m}</div>' for m in MENU)
    return f'<div class="app"><div class="side"><div class="logo">SMART EXAM</div>{items}<div class="note" style="margin-top:30px">GV: Nguyễn Văn An<br>[Đăng xuất]</div></div><div class="main">{body}</div></div>'

screens = {}
screens["01_login"] = '''<div style="height:600px;border:2px solid #333;display:flex;align-items:center;justify-content:center;background:#eee">
<div class="box" style="width:380px;background:#fff;padding:24px"><h2 style="text-align:center">SMART EXAM GRADING</h2>
<div>Tên đăng nhập</div><div class="in">username</div><div>Mật khẩu</div><div class="in">••••••</div>
<div style="margin:8px 0;font-size:12px">☐ Ghi nhớ đăng nhập</div><div class="btn p" style="width:100%;text-align:center">ĐĂNG NHẬP</div>
<div class="note" style="margin-top:10px">Sau đăng nhập: Admin/GV → Dashboard; SV → Tra cứu điểm</div></div></div>'''
screens["02_dashboard"] = shell("Dashboard", '''<h2>Dashboard – Giữa kỳ CSDL HK1 2026</h2>
<div class="row"><div class="box kpi">SV dự thi<b>120</b></div><div class="box kpi">Phiếu đã upload<b>115</b></div><div class="box kpi">Đã chấm tự động<b>102</b></div><div class="box kpi">Chờ review<b>13</b></div><div class="box kpi">Tỉ lệ match tự động<b>88.7%</b></div></div>
<div class="row"><div class="box" style="flex:2"><b>Phổ điểm</b><div class="bar" style="margin-top:8px"><div style="height:10%"></div><div style="height:25%"></div><div style="height:45%"></div><div style="height:70%"></div><div style="height:95%"></div><div style="height:80%"></div><div style="height:50%"></div><div style="height:30%"></div><div style="height:15%"></div><div style="height:8%"></div></div><div class="note">0 → 10 điểm</div></div>
<div class="box" style="flex:1"><b>Kỳ thi gần đây</b><table style="margin-top:8px"><tr><th>Kỳ thi</th><th>Trạng thái</th></tr><tr><td>Giữa kỳ CSDL</td><td>grading</td></tr><tr><td>Cuối kỳ AI</td><td>draft</td></tr><tr><td>Quiz 1 CSDL</td><td>closed</td></tr></table><div class="btn p" style="margin-top:10px">+ Tạo kỳ thi</div></div></div>''')
screens["03_exam"] = shell("Kỳ thi & đáp án", '''<h2>Kỳ thi: Giữa kỳ CSDL HK1 2026</h2>
<div class="row"><div class="box" style="flex:1"><b>Thông tin</b><div>Môn</div><div class="in">IT3080 – Cơ sở dữ liệu ▼</div><div>Mẫu phiếu</div><div class="in">Phiếu chuẩn 40 câu A4 ▼</div><div>Số câu / Thang điểm</div><div class="in">40 / 10</div><div>Ngày thi</div><div class="in">15/10/2026</div></div>
<div class="box" style="flex:2"><b>Đáp án gốc</b> <span class="note">(nhập nhanh: ABCDABCD...)</span><div class="in">ABCDABCDABDCCABDA...</div>
<table style="margin-top:6px"><tr><th>Câu</th><th>A</th><th>B</th><th>C</th><th>D</th><th>Câu</th><th>A</th><th>B</th><th>C</th><th>D</th></tr><tr><td>1</td><td>●</td><td>○</td><td>○</td><td>○</td><td>21</td><td>○</td><td>●</td><td>○</td><td>○</td></tr><tr><td>2</td><td>○</td><td>●</td><td>○</td><td>○</td><td>22</td><td>○</td><td>○</td><td>●</td><td>○</td></tr><tr><td>…</td><td></td><td></td><td></td><td></td><td>…</td><td></td><td></td><td></td><td></td></tr></table></div></div>
<div class="box"><b>Mã đề</b> <span class="btn">Sinh 4 mã đề (đảo câu)</span><span class="btn">Tải phiếu PDF</span><span class="btn">Sửa đáp án & chấm lại</span>
<table style="margin-top:8px"><tr><th>Mã đề</th><th>Seed</th><th>File PDF</th><th></th></tr><tr><td>101</td><td>–</td><td>de_101.pdf</td><td>[Xem đáp án]</td></tr><tr><td>102</td><td>42</td><td>de_102.pdf</td><td>[Xem đáp án]</td></tr></table></div>''')
screens["04_upload"] = shell("Upload & chấm", '''<h2>Upload & chấm phiếu</h2>
<div class="row"><div class="box" style="flex:1"><div>Kỳ thi</div><div class="in">Giữa kỳ CSDL HK1 2026 ▼</div>
<div class="img" style="height:150px;margin-top:8px">Kéo thả ảnh phiếu (JPG/PNG) vào đây<br>hoặc [Chọn file]</div><div style="margin-top:8px"><span class="btn p">Bắt đầu chấm (25 ảnh)</span></div>
<div class="note" style="margin-top:6px">Đang xử lý: 18/25 ▓▓▓▓▓▓▓░░░</div></div>
<div class="box" style="flex:1"><b>Import danh sách SV</b><div class="in">danh_sach_K22.xlsx [Chọn file]</div><div class="note">Cột bắt buộc: SBD, Họ tên, Lớp</div><span class="btn">Import</span><div style="margin-top:8px;font-size:12px">Kết quả: 118 OK · 2 lỗi [Xem]</div></div></div>
<div class="box"><b>Kết quả lô vừa chấm</b><table style="margin-top:6px"><tr><th>Ảnh</th><th>SBD nhận diện</th><th>Conf.</th><th>Mã đề</th><th>Sinh viên</th><th>Điểm</th><th>Trạng thái</th></tr>
<tr><td>s01.jpg</td><td>220001</td><td>0.99</td><td>101</td><td>Lê Minh Khoa</td><td>9.0</td><td><span class="tag">graded</span></td></tr>
<tr><td>s03.jpg</td><td>220003</td><td>0.72</td><td>101</td><td>–</td><td>(9.0)</td><td><span class="tag">review: conf. thấp</span></td></tr>
<tr><td>s04.jpg</td><td>220099</td><td>0.95</td><td>101</td><td>–</td><td>(9.0)</td><td><span class="tag">review: không có SBD</span></td></tr></table></div>''')
screens["05_review"] = shell("Hàng đợi review", '''<h2>Hàng đợi review (13)</h2>
<div class="row"><div class="box" style="width:300px"><b>Danh sách</b><table style="margin-top:6px"><tr><th>Ưu tiên</th><th>SBD</th><th>Lý do</th></tr><tr style="background:#ccc"><td>1</td><td>220099</td><td>không có SBD</td></tr><tr><td>1</td><td>220001</td><td>trùng SBD</td></tr><tr><td>2</td><td>220003</td><td>conf. thấp</td></tr><tr><td>3</td><td>220004</td><td>ô tô mờ</td></tr></table></div>
<div class="box" style="flex:1"><b>Phiếu s04.jpg</b><div class="row" style="margin-top:8px"><div class="img" style="width:260px;height:340px">Ảnh phiếu gốc<br>(zoom vùng SBD)</div>
<div style="flex:1"><div>SBD nhận diện: <b>2 2 0 0 9 9</b> <span class="note">(conf. từng số 0.99 … 0.95)</span></div><div>Mã đề: <b>101</b> · Điểm tạm: <b>9.0</b></div>
<div style="margin-top:8px"><b>Gợi ý sinh viên</b></div><table><tr><th></th><th>SBD</th><th>Họ tên</th><th>Lớp</th><th>Lệch</th></tr><tr><td>◉</td><td>220009</td><td>Lý Hoài Nam</td><td>K22B</td><td>1 số</td></tr><tr><td>○</td><td colspan=4>Tìm SV khác… [ô tìm kiếm]</td></tr></table>
<div style="margin-top:8px"><b>Đáp án tô</b> <span class="note">(bấm để sửa)</span><div class="in">1A 2B 3C 4A 5A 6B 7C 8D 9A 10B</div></div>
<div>Ghi chú</div><div class="in">OCR đọc sai số thứ 5</div>
<div style="margin-top:10px"><span class="btn p">Xác nhận & ghi điểm</span><span class="btn">Loại phiếu</span></div></div></div></div></div>''')
screens["06_stats"] = shell("Thống kê", '''<h2>Thống kê kỳ thi</h2>
<div class="row"><div class="box kpi">Điểm TB<b>6.85</b></div><div class="box kpi">Cao nhất<b>10</b></div><div class="box kpi">Thấp nhất<b>2.5</b></div><div class="box kpi">Tỉ lệ đạt<b>78%</b></div></div>
<div class="row"><div class="box" style="flex:1"><b>Phổ điểm</b><div class="bar" style="margin-top:8px"><div style="height:8%"></div><div style="height:20%"></div><div style="height:40%"></div><div style="height:65%"></div><div style="height:90%"></div><div style="height:75%"></div><div style="height:45%"></div><div style="height:20%"></div></div></div>
<div class="box" style="flex:1"><b>Độ khó từng câu (tỉ lệ đúng)</b><table style="margin-top:6px"><tr><th>Câu gốc</th><th>Tỉ lệ đúng</th><th>Mức</th></tr><tr><td>7</td><td>0.12</td><td>Khó</td></tr><tr><td>15</td><td>0.28</td><td>Khó</td></tr><tr><td>3</td><td>0.55</td><td>TB</td></tr><tr><td>1</td><td>0.96</td><td>Dễ</td></tr></table></div></div>
<div class="box"><b>Bảng điểm</b> <span class="btn">Xuất Excel</span> <span class="in" style="display:inline-block;width:200px">Lọc lớp ▼</span><table style="margin-top:6px"><tr><th>SBD</th><th>Họ tên</th><th>Lớp</th><th>Mã đề</th><th>Số câu đúng</th><th>Điểm</th><th>Nguồn</th></tr><tr><td>220001</td><td>Lê Minh Khoa</td><td>K22A</td><td>101</td><td>36/40</td><td>9.0</td><td>auto</td></tr><tr><td>220003</td><td>Đỗ Quang Huy</td><td>K22A</td><td>101</td><td>32/40</td><td>8.0</td><td>confirmed</td></tr></table></div>''')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width":1200,"height":700}, device_scale_factor=1)
        for name, body in screens.items():
            await pg.set_content(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>")
            await pg.locator("body > div").first.screenshot(path=f"{name}.png")
        await b.close()
asyncio.run(main())
