import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AG = ROOT / "data" / "_eval" / "ag"
KICH_BAN = AG / "kich_ban.json"
PDF_PHIEU = AG / "phieu_trang_in_10.pdf"
PDF_GIAO = AG / "phieu_giao_viec_ag.pdf"
MAU_PNG = ROOT / "answer_sheet" / "output" / "phieu_trang_300dpi.png"
LAYOUT = ROOT / "answer_sheet" / "output" / "layout.json"
FONT = ROOT / "answer_sheet" / "fonts" / "DejaVuSans.ttf"
FONT_DAM = ROOT / "answer_sheet" / "fonts" / "DejaVuSans-Bold.ttf"

HAT_GIONG = 20261101
SO_TO, SO_CAU = 10, 40
DS_SBD = ("220006", "220007", "220008", "220009")
DS_MA = ("103", "104")
LOAI_DAC_BIET = ("nhat", "hai_o", "te", "bo_trong", "vet")
SO_DAC_BIET = {"bi": {"nhat": 2, "hai_o": 2, "bo_trong": 2, "vet": 2},
               "chi": {"te": 4, "nhat": 1, "hai_o": 1, "bo_trong": 1, "vet": 2}}
THIEU_BUBBLE = {"T03": ("sbd", 2), "T06": ("ma_de", 3), "T10": ("sbd", 5)}
CHAP_NHAN = {"binh_thuong": ["doc_dung", "can_xem"], "bo_trong": ["doc_dung", "can_xem"], "nhat": ["doc_dung", "can_xem"],
             "hai_o": ["can_xem"], "te": ["doc_dung", "can_xem"], "vet": ["doc_dung", "can_xem"]}
O = "ABCD"


def but_cua(i: int) -> tuple[str, str]:
    if i >= 8:
        return "chi", "bút chì 2B"
    return "bi", ("bút bi xanh" if i < 4 else "bút bi đen")


def huong_dan(n: int, c: dict) -> str:
    l = c["loai"]
    if l == "binh_thuong":
        return f"Câu {n}: tô đậm {c['dap_an']}"
    if l == "bo_trong":
        return f"Câu {n}: ĐỂ TRỐNG (không tô ô nào)"
    if l == "nhat":
        return f"Câu {n}: tô NHẸ ô {c['dap_an']} (như tô vội, không tô kín)"
    if l == "hai_o":
        return f"Câu {n}: tô ĐẬM 2 ô {c['dap_an'][0]} và {c['dap_an'][1]}"
    if l == "te":
        return f"Câu {n}: tô {c['to_truoc']}, rồi TẨY bằng tẩy bút chì, tô lại {c['dap_an']}"
    if l == "vet":
        if c["thoi_diem"] == "truoc":
            return f"Câu {n}: chấm nhẹ MỘT chấm nhỏ vào ô {c['cham']} trước, rồi tô đậm {c['dap_an']}"
        return f"Câu {n}: tô đậm {c['dap_an']}, rồi chấm nhẹ MỘT chấm nhỏ vào ô {c['cham']}"
    raise ValueError(l)


def lap_kich_ban(hat: int = HAT_GIONG) -> dict:
    rng = random.Random(hat)
    to = {}
    for i in range(SO_TO):
        ma = f"T{i + 1:02d}"
        but, mo_ta = but_cua(i)
        dem = SO_DAC_BIET[but]
        so = rng.sample(range(1, SO_CAU + 1), sum(dem.values()))
        loai_cau = {}
        k = 0
        for l, n in dem.items():
            for _ in range(n):
                loai_cau[so[k]] = l
                k += 1
        cau = {}
        for n in range(1, SO_CAU + 1):
            l = loai_cau.get(n, "binh_thuong")
            y = rng.choice(O)
            c = {"loai": l, "chap_nhan": CHAP_NHAN[l]}
            if l == "bo_trong":
                c["dap_an"] = ""
            elif l == "hai_o":
                c["dap_an"] = "".join(sorted(rng.sample(O, 2)))
            else:
                c["dap_an"] = y
            if l == "te":
                c["to_truoc"] = rng.choice([x for x in O if x != y])
            if l == "vet":
                c["cham"] = rng.choice([x for x in O if x != y])
                c["thoi_diem"] = rng.choice(["truoc", "sau"])
            c["huong_dan"] = huong_dan(n, c)
            cau[str(n)] = c
        tb = THIEU_BUBBLE.get(ma)
        to[ma] = {"but": but, "but_mo_ta": mo_ta, "sbd": DS_SBD[i % len(DS_SBD)], "ma_de": DS_MA[i % len(DS_MA)],
                  "thieu_bubble": [{"truong": tb[0], "vi_tri": tb[1]}] if tb else [], "cau": cau}
    return {"phien_ban": 1, "hat_giong": hat, "tieu_chi": "docs/tieu_chi_thu_giay_that.md (commit 18fd340)", "ky_thi_danh_sach": {"sbd": list(DS_SBD), "ma_de": list(DS_MA)},
            "quy_uoc": "doc_dung = máy không cờ và đọc đúng tập ô; can_xem = máy gắn cờ; sai âm thầm = không cờ mà đọc sai (chac_chan_sai)", "to": to}


def kiem_kich_ban(kb: dict) -> list[str]:
    loi = []
    dem = Counter()
    for ma, t in kb["to"].items():
        dac = [c["loai"] for c in t["cau"].values() if c["loai"] != "binh_thuong"]
        if not 8 <= len(dac) <= 10:
            loi.append(f"{ma}: {len(dac)} câu đặc biệt (cần 8–10)")
        if t["but"] != "chi" and "te" in dac:
            loi.append(f"{ma}: câu 'te' trên tờ bút bi")
        dem.update(dac)
        if len(t["cau"]) != SO_CAU:
            loi.append(f"{ma}: {len(t['cau'])} câu")
        for n, c in t["cau"].items():
            if c["loai"] == "hai_o" and (len(c["dap_an"]) != 2 or c["chap_nhan"] != ["can_xem"]):
                loi.append(f"{ma} câu {n}: hai_o sai")
            if c["loai"] == "te" and c["to_truoc"] == c["dap_an"]:
                loi.append(f"{ma} câu {n}: te tô lại cùng ô")
            if c["loai"] == "vet" and c["cham"] == c["dap_an"]:
                loi.append(f"{ma} câu {n}: vết trùng ô chọn")
            if c["loai"] == "bo_trong" and c["dap_an"]:
                loi.append(f"{ma} câu {n}: bỏ trống có đáp án")
        if t["sbd"] not in DS_SBD or t["ma_de"] not in DS_MA:
            loi.append(f"{ma}: SBD / mã đề ngoài danh sách 1633")
    for l in LOAI_DAC_BIET:
        if dem[l] < 6:
            loi.append(f"loại {l}: {dem[l]} lần (cần ≥ 6)")
    so_but = Counter(t["but"] for t in kb["to"].values())
    if so_but != Counter({"bi": 8, "chi": 2}):
        loi.append(f"phân bố bút {dict(so_but)} (cần 8 bi, 2 chì)")
    if sum(len(t["thieu_bubble"]) for t in kb["to"].values()) < 1:
        loi.append("không có cột thiếu bubble (H3b)")
    return loi


def cmd_kich_ban(a=None) -> dict:
    kb = lap_kich_ban()
    loi = kiem_kich_ban(kb)
    if loi:
        sys.exit("DỪNG: kịch bản sai: " + "; ".join(loi))
    AG.mkdir(parents=True, exist_ok=True)
    KICH_BAN.write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    dem = Counter(c["loai"] for t in kb["to"].values() for c in t["cau"].values())
    print(f"Ghi {KICH_BAN}: {len(kb['to'])} tờ; số câu theo loại: {dict(dem)}; cột thiếu bubble: "
          + ", ".join(f"{m} {t['thieu_bubble'][0]['truong']} cột {t['thieu_bubble'][0]['vi_tri']}" for m, t in kb["to"].items() if t["thieu_bubble"]))
    return kb


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT)))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DAM)))


def cmd_in_phieu(a=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    AG.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_PHIEU), pagesize=A4)
    c.setTitle("Phiếu trống thử giấy thật (lệnh AG) – in A4, tỉ lệ 100%")
    for _ in range(SO_TO):
        c.drawImage(str(MAU_PNG), 0, 0, width=210 * mm, height=297 * mm)
        c.showPage()
    c.save()
    print(f"Ghi {PDF_PHIEU} ({SO_TO} trang A4)")


def o_bang(cc: dict) -> str:
    l, d = cc["loai"], cc["dap_an"]
    if l == "bo_trong":
        return "TRỐNG"
    if l == "nhat":
        return f"{d} nhẹ"
    if l == "hai_o":
        return f"{d[0]} + {d[1]}"
    if l == "te":
        return f"{cc['to_truoc']}→tẩy→{d}"
    if l == "vet":
        return f"{d} + chấm {cc['cham']}"
    return d


def cmd_giao_viec(a=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    kb = json.loads(KICH_BAN.read_text(encoding="utf-8"))
    _font()
    W, H = A4
    c = canvas.Canvas(str(PDF_GIAO), pagesize=A4)
    c.setTitle("Phiếu giao việc – thử giấy thật (lệnh AG)")

    def dong(x, y, s, co=11, dam=False):
        c.setFont("DejaVu-Bold" if dam else "DejaVu", co)
        c.drawString(x, y, s)

    y = H - 25 * mm
    dong(20 * mm, y, "THỬ GIẤY THẬT – PHIẾU GIAO VIỆC (lệnh AG)", 18, True)
    for s in ["In phiếu trống (phieu_trang_in_10.pdf) khổ A4, tỉ lệ 100% / Actual size – KHÔNG chọn 'vừa trang' / 'Fit'.",
              "Mỗi tờ trong tệp này ứng với MỘT phiếu trống. Ghi số tờ (ví dụ T03) vào ô 'Họ và tên' của phiếu trống – KHÔNG ghi tên thật.",
              "Làm đúng như trang của tờ đó: viết SBD + mã đề bằng chữ số tay vào 6 + 3 ô VÀ tô ô tròn tương ứng,",
              "rồi tô 40 câu đúng bảng. Câu in ĐẬM có nền xám là câu đặc biệt – làm đúng cách ghi.",
              "Tô ĐẬM = tô kín ô tròn. Tô NHẸ = tô nhạt, không kín, như tô vội. Chấm nhỏ = một chấm đầu bút, KHÔNG tô.",
              "Câu 'tẩy' chỉ có ở tờ bút chì: tô ô đầu, tẩy bằng tẩy bút chì (như thí sinh đổi ý), rồi tô ô sau.",
              "Cột 'KHÔNG tô ô tròn' (tờ T03, T06, T10): chỉ VIẾT chữ số vào ô, để trống cột ô tròn đó (kiểm H3).",
              "Làm SAI so với giấy thì GHI LẠI ngay dưới trang của tờ đó (không tô thêm để sửa).",
              "Chụp: đặt phẳng, đủ sáng, thấy đủ 4 ô vuông đen ở 4 góc. Tên ảnh T01.jpg … T10.jpg.",
              "Thêm 3 ảnh khó (cùng tờ, chụp lần 2): bóng đổ / nghiêng ~10° / đèn vàng – tên T0X_kho.jpg.",
              "Chép ảnh vào data/anh_that_ag/ rồi chạy:  python tools/ag_cham_that.py cham",
              "Hướng dẫn đầy đủ: docs/huong_dan_thu_giay_that.md. Tiêu chí: docs/tieu_chi_thu_giay_that.md."]:
        y -= 8.5 * mm
        dong(20 * mm, y, s, 10.5)
    y -= 14 * mm
    dong(20 * mm, y, "Phân công (khuyến khích 5 người, mỗi người 2 tờ):", 12, True)
    for i in range(5):
        y -= 9 * mm
        dong(25 * mm, y, f"Người {i + 1}: tờ T{2 * i + 1:02d} và T{2 * i + 2:02d}     Tên (giả / viết tắt): ____________________", 11)
    c.showPage()

    for ma, t in kb["to"].items():
        y = H - 18 * mm
        dong(15 * mm, y, f"Tờ {ma}   –   Người tô: ______________   –   Bút: {t['but_mo_ta']}", 16, True)
        y -= 11 * mm
        tb = {(x["truong"], x["vi_tri"]) for x in t["thieu_bubble"]}
        def mo_ta(ten, so, truong):
            ra = []
            for i, d in enumerate(so):
                ra.append(f"{d}*" if (truong, i + 1) in tb else d)
            return " ".join(ra)
        dong(15 * mm, y, f"Viết SBD  {t['sbd']}  và mã đề  {t['ma_de']}  bằng chữ số tay vào 6 + 3 ô,", 12)
        y -= 6.5 * mm
        dong(15 * mm, y, "đồng thời tô ô tròn tương ứng của từng chữ số.", 12)
        if tb:
            y -= 9 * mm
            x = t["thieu_bubble"][0]
            ten = "SBD" if x["truong"] == "sbd" else "Mã đề"
            so = t["sbd"] if x["truong"] == "sbd" else t["ma_de"]
            c.setFillGray(0.85); c.rect(14 * mm, y - 8.5 * mm, 182 * mm, 14 * mm, stroke=0, fill=1); c.setFillGray(0)
            dong(15 * mm, y, f"ĐẶC BIỆT: {ten} cột {x['vi_tri']} (chữ số {so[x['vi_tri'] - 1]}): VIẾT chữ số vào ô,", 11.5, True)
            y -= 6 * mm
            dong(15 * mm, y, "nhưng KHÔNG tô ô tròn của cột này (các cột khác tô bình thường).", 11.5, True)
        y -= 10 * mm
        cot_w, dong_h = 45 * mm, 9.2 * mm
        x0 = 15 * mm
        for n in range(1, SO_CAU + 1):
            cc = t["cau"][str(n)]
            col, row = (n - 1) // 10, (n - 1) % 10
            xx, yy = x0 + col * cot_w, y - row * dong_h
            dac = cc["loai"] != "binh_thuong"
            if dac:
                c.setFillGray(0.82); c.rect(xx - 1 * mm, yy - 2.6 * mm, cot_w - 2 * mm, dong_h - 1.2 * mm, stroke=0, fill=1); c.setFillGray(0)
            c.rect(xx - 1 * mm, yy - 2.6 * mm, cot_w - 2 * mm, dong_h - 1.2 * mm, stroke=1, fill=0)
            nd = o_bang(cc)
            dong(xx + 1 * mm, yy, f"Câu {n:>2}:", 10.5, dac)
            dong(xx + 19 * mm, yy, nd, 12 if not dac else 9.5, True)
        y -= 10 * dong_h + 4 * mm
        dong(15 * mm, y, "Câu đặc biệt – làm đúng cách sau:", 12, True)
        for n in range(1, SO_CAU + 1):
            cc = t["cau"][str(n)]
            if cc["loai"] != "binh_thuong":
                y -= 6.6 * mm
                dong(20 * mm, y, "• " + cc["huong_dan"], 11, True)
        y -= 11 * mm
        dong(15 * mm, y, "Đèn:  □ sáng đều    □ có bóng    □ đèn vàng          Điện thoại: ____________________", 11)
        y -= 8 * mm
        dong(15 * mm, y, "Ghi chú nếu tô khác kịch bản (câu nào, tô gì): ____________________________________________", 10)
        c.showPage()
    c.save()
    print(f"Ghi {PDF_GIAO} (1 bìa + {len(kb['to'])} trang)")


def do_marker(xam) -> dict:
    import cv2
    import numpy as np
    L = json.loads(LAYOUT.read_text(encoding="utf-8"))
    s = L["markers"]["size"]
    n, _, st, tam = cv2.connectedComponentsWithStats((xam < 100).astype(np.uint8), connectivity=8)
    ung = [tam[i] for i in range(1, n) if abs(st[i, 2] - s) <= 8 and abs(st[i, 3] - s) <= 8 and st[i, 4] > 0.8 * s * s]
    ra = {}
    for k, (cx, cy) in L["markers"]["centers"].items():
        if ung:
            b = min(ung, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
            ra[k] = (float(b[0]), float(b[1]), float(np.hypot(b[0] - cx, b[1] - cy)))
    return ra


def cmd_kiem_in(a=None) -> dict:
    import numpy as np
    import pymupdf
    import cv2
    L = json.loads(LAYOUT.read_text(encoding="utf-8"))
    mau = cv2.imdecode(np.fromfile(MAU_PNG, np.uint8), cv2.IMREAD_GRAYSCALE)
    doc = pymupdf.open(str(PDF_PHIEU))
    kq = {"so_trang": doc.page_count, "trang": []}
    for i, pg in enumerate(doc):
        w_mm, h_mm = pg.rect.width / 72 * 25.4, pg.rect.height / 72 * 25.4
        pix = pg.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
        xam = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
        m = do_marker(xam)
        lech = max((v[2] for v in m.values()), default=999.0)
        h, w = min(xam.shape[0], mau.shape[0]), min(xam.shape[1], mau.shape[1])
        kq["trang"].append({"trang": i + 1, "kho_mm": [round(w_mm, 2), round(h_mm, 2)], "anh_px": [pix.width, pix.height], "so_marker": len(m),
                            "lech_marker_px_max": round(lech, 2),
                            "lech_so_png_tb": round(float(np.abs(xam[:h, :w].astype(np.int16) - mau[:h, :w].astype(np.int16)).mean()), 3)})
    kq["dat"] = kq["so_trang"] == SO_TO and all(abs(t["kho_mm"][0] - 210) < 0.5 and abs(t["kho_mm"][1] - 297) < 0.5
                                                 and all(abs(a - b) <= 1 for a, b in zip(t["anh_px"], L["page_px"]))
                                                 and t["so_marker"] == 4 and t["lech_marker_px_max"] <= 2.0 for t in kq["trang"])
    (AG / "kiem_in.json").write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    t0 = kq["trang"][0]
    print(f"Kiểm PDF in: {kq['so_trang']} trang, khổ {t0['kho_mm']} mm, ảnh {t0['anh_px']} px, 4 ô vuông lệch tối đa "
          f"{max(t['lech_marker_px_max'] for t in kq['trang'])} px, chênh trung bình với PNG {t0['lech_so_png_tb']} -> {'ĐẠT' if kq['dat'] else 'KHÔNG ĐẠT'}")
    return kq


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", nargs="?", default="tat-ca", choices=["tat-ca", "kich-ban", "in-phieu", "giao-viec", "kiem-in"])
    a = ap.parse_args()
    if a.lenh in ("tat-ca", "kich-ban"):
        cmd_kich_ban()
    if a.lenh in ("tat-ca", "in-phieu"):
        cmd_in_phieu()
    if a.lenh in ("tat-ca", "giao-viec"):
        cmd_giao_viec()
    if a.lenh in ("tat-ca", "kiem-in"):
        if not cmd_kiem_in()["dat"]:
            sys.exit(1)
