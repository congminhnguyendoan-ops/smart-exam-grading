"""
demo_xu_ly_anh.py - Lệnh AJ (phiên demo "Xử lý ảnh"): chạy pipeline THẬT trên MỘT ảnh phiếu và dựng MỘT trang HTML tự chứa (ảnh nhúng base64)
cho từng bước. OFFLINE: không CSDL, không server, không ghi gì ngoài tệp HTML --ra. Không viết lại thuật toán: chỉ gọi
cv_engine.preprocessing.preprocess_anh -> omr.doc_phieu -> ocr.doc_chu_so -> ocr.doi_chieu_dinh_danh rồi VẼ kết quả.

  python tools/demo_xu_ly_anh.py --anh data/anh_that_ag/T05.JPG --ra data/_eval/demo_3_phien/xu_ly_anh_T05.html
  python tools/demo_xu_ly_anh.py --anh data/anh_that_ag/T03_kho.JPG --ra data/_eval/demo_3_phien/xu_ly_anh_T03_kho.html
  (tuỳ chọn) --khong-danh-sach : không dùng danh sách thí sinh của kịch bản AG khi đối chiếu SBD / mã đề (kết quả "chưa biết danh sách")

Ảnh bị từ chối: trang vẫn dựng tới bước bị chặn, ghi rõ mã + lời khuyên chụp lại, KHÔNG chấm.
Các bước: 1 ảnh gốc · 2 kiểm tra chất lượng (độ mờ) · 3 4 góc · 4 nắn phối cảnh · 5 lưới ô định vị · 6 OMR tô màu · 7 ô viết tay -> CNN · 8 hai kênh.
"""
import argparse
import base64
import html
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KICH_BAN = ROOT / "data" / "_eval" / "ag" / "kich_ban.json"
MAU_CSS = ROOT / "frontend" / "mau.css"

# màu vẽ (BGR)
XANH, CAM, XAM, DO, XANH_DUONG, VANG = (80, 160, 60), (0, 140, 255), (150, 150, 150), (50, 50, 210), (190, 110, 30), (0, 210, 240)


# ------------------------------------------------------------------------------------------------ tiện ích ảnh
def uri(img: np.ndarray, rong_toi_da: int | None = None, png: bool = False, nearest: bool = False) -> str:
    """Ảnh -> data URI (JPEG q85, hoặc PNG cho ô nhỏ). Thu nhỏ khi hiển thị nếu rong_toi_da."""
    if rong_toi_da and img.shape[1] > rong_toi_da:
        k = rong_toi_da / img.shape[1]
        img = cv2.resize(img, (rong_toi_da, int(round(img.shape[0] * k))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png" if png else ".jpg", img, [] if png else [cv2.IMWRITE_JPEG_QUALITY, 85])
    return f"data:image/{'png' if png else 'jpeg'};base64,{base64.b64encode(buf.tobytes()).decode()}"


def bgr(xam: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(xam, cv2.COLOR_GRAY2BGR)


def e(s) -> str:
    return html.escape(str(s))


def pt(v: float) -> str:
    return f"{100 * v:.1f}%".replace(".", ",")


# ------------------------------------------------------------------------------------------------ vẽ từng bước
def ve_goc(gray: np.ndarray, kq) -> np.ndarray:
    """Bước 3: ứng viên marker (vàng, nhỏ) + 4 góc được chọn (xanh lá) + tứ giác, trên ảnh gốc."""
    im = bgr(gray)
    t = max(2, gray.shape[1] // 700)
    for (x, y) in kq.chi_tiet.get("ung_vien", []):
        cv2.circle(im, (int(x), int(y)), 6 * t, VANG, t)
    if kq.marker is not None:
        m = np.asarray(kq.marker, float)
        cv2.polylines(im, [np.round(m).astype(np.int32)], True, XANH, 2 * t)
        for ten, (x, y) in zip(("TL", "TR", "BR", "BL"), m):
            cv2.circle(im, (int(x), int(y)), 9 * t, XANH, 3 * t)
            cv2.putText(im, ten, (int(x) + 12 * t, int(y) - 12 * t), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * t, XANH, 2 * t)
    return im


def vi_tri_o(lay: dict, omr) -> tuple:
    """Toạ độ ô ĐÃ định vị = toạ độ layout + dịch của hàng / cột (omr.dich_chuyen_mm, mm -> px)."""
    k = lay["dpi"] / 25.4
    dich = {n: (v[0] * k, v[1] * k) for n, v in omr.dich_chuyen_mm.items()}
    dap_an = {}
    for q, ds in lay["answers"]["centers"].items():
        dx, dy = dich.get(f"q{q}", (0.0, 0.0))
        dap_an[int(q)] = {o: (xy[0] + dx, xy[1] + dy) for o, xy in ds.items()}
    chu_so = {}
    for kh, truong in (("sbd", "sbd"), ("ma_de", "exam_code")):
        chu_so[kh] = []
        for i, cot in enumerate(lay[truong]["bubbles"]):
            dx, dy = dich.get(f"{kh}{i + 1}", (0.0, 0.0))
            chu_so[kh].append([(xy[0] + dx, xy[1] + dy) for xy in cot])
    return dap_an, chu_so


def cat_khoi(lay: dict, khoi: str):
    from cv_engine.omr import hop_khoi
    return hop_khoi(lay, khoi)


def ve_luoi(nan: np.ndarray, lay: dict, omr) -> tuple[np.ndarray, np.ndarray]:
    """Bước 5: (a) cả trang với 3 khối; (b) khối đáp án phóng to: chấm xanh dương = vị trí LÝ THUYẾT trong layout,
    vòng xanh lá = vị trí SAU định vị theo hàng (dịch tới vài px đến vài chục px)."""
    dap_an, chu_so = vi_tri_o(lay, omr)
    r = int(round(lay["answers"]["bubble_radius"]))
    tong = bgr(nan)
    for kh in ("dap_an", "sbd", "ma_de"):
        x0, y0, x1, y1 = cat_khoi(lay, kh)
        cv2.rectangle(tong, (x0, y0), (x1, y1), XANH_DUONG, 6)
        cv2.putText(tong, {"dap_an": "40 CAU", "sbd": "SBD", "ma_de": "MA DE"}[kh], (x0, y0 - 14), cv2.FONT_HERSHEY_SIMPLEX, 2.2, XANH_DUONG, 6)
    x0, y0, x1, y1 = cat_khoi(lay, "dap_an")
    ct = bgr(nan[y0:y1, x0:x1]).copy()
    for q, ds in lay["answers"]["centers"].items():
        for o, xy in ds.items():
            cv2.circle(ct, (int(xy[0] - x0), int(xy[1] - y0)), 4, XANH_DUONG, -1)
            nx, ny = dap_an[int(q)][o]
            cv2.circle(ct, (int(round(nx - x0)), int(round(ny - y0))), r, XANH, 3)
    return tong, ct


def ve_omr(nan: np.ndarray, lay: dict, omr) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bước 6: tô màu từng ô theo trạng thái máy đọc: xanh lá đặc = rõ, cam đặc = mờ, vòng xám = trống; số câu đỏ = CẦN XEM."""
    dap_an, chu_so = vi_tri_o(lay, omr)
    r = int(round(lay["answers"]["bubble_radius"]))
    x0, y0, x1, y1 = cat_khoi(lay, "dap_an")
    ct = bgr(nan[y0:y1, x0:x1]).copy()
    for c in omr.cau:
        for o, p in c.xac_suat.items():
            cx, cy = dap_an[c.cau][o]
            ctr = (int(round(cx - x0)), int(round(cy - y0)))
            kind = max(p, key=p.get)
            if kind == "filled":
                cv2.circle(ct, ctr, r, XANH, -1)
            elif kind == "faint":
                cv2.circle(ct, ctr, r, CAM, -1)
            else:
                cv2.circle(ct, ctr, r, XAM, 2)
        if c.can_xem:           # khung đỏ quanh cả hàng 4 ô = câu máy không chắc
            xs = [dap_an[c.cau][o][0] for o in "ABCD"]
            cy = dap_an[c.cau]["A"][1]
            cv2.rectangle(ct, (int(min(xs) - x0 - r - 8), int(cy - y0 - r - 8)), (int(max(xs) - x0 + r + 8), int(cy - y0 + r + 8)), DO, 5)
    ra = []
    for kh, cot_list in (("sbd", omr.sbd_cot), ("ma_de", omr.ma_de_cot)):
        a, b, c_, d = cat_khoi(lay, kh)
        im = bgr(nan[b:d, a:c_]).copy()
        rb = int(round(lay["sbd"]["bubble_radius"]))
        for i, cot in enumerate(cot_list):
            for dgt, (cx, cy) in enumerate(chu_so[kh][i]):
                p = cot.xac_suat_to[dgt]
                ctr = (int(round(cx - a)), int(round(cy - b)))
                if p >= 0.5:
                    cv2.circle(im, ctr, rb, XANH, -1)
                elif p >= 0.2:
                    cv2.circle(im, ctr, rb, CAM, -1)
                else:
                    cv2.circle(im, ctr, rb, XAM, 2)
        ra.append(im)
    return ct, ra[0], ra[1]


# ------------------------------------------------------------------------------------------------ HTML
def the_buoc(so: int, tieu_de: str, mo_ta: str, noi_dung: str, ms: float | None = None, lop: str = "") -> str:
    t = f'<span class="ms">{ms:.0f} ms</span>' if ms is not None else ""
    return (f'<section class="buoc {lop}"><h2><span class="so">{so}</span>{e(tieu_de)}{t}</h2><p class="mo-ta">{mo_ta}</p>{noi_dung}</section>')


def anh_tag(src: str, chu: str = "", cls: str = "") -> str:
    return f'<figure class="{cls}"><img src="{src}" alt="{e(chu)}"><figcaption>{e(chu)}</figcaption></figure>'


def dung_trang(ctx: dict) -> str:
    css = MAU_CSS.read_text(encoding="utf-8") if MAU_CSS.exists() else ""
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demo xử lý ảnh – {e(ctx['ten'])}</title><style>{css}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:20px 16px 60px}} h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--mut);margin:0 0 16px}}
.buoc{{background:var(--card);border:1px solid var(--line);border-radius:var(--r-lon);box-shadow:var(--bong);padding:18px 20px;margin:18px 0}}
.buoc h2{{font-size:20px;margin:0 0 4px;display:flex;align-items:center;gap:10px}} .so{{background:var(--pri);color:var(--tren-pri);border-radius:50%;width:32px;height:32px;display:inline-flex;align-items:center;justify-content:center;font-size:16px;flex:none}}
.ms{{margin-left:auto;font-size:14px;color:var(--mut);font-weight:400}} .mo-ta{{margin:2px 0 12px;color:var(--mut)}}
figure{{margin:0}} figure img{{max-width:100%;height:auto;border:1px solid var(--line);border-radius:var(--r-nho);display:block;background:#fff}} figcaption{{font-size:14px;color:var(--mut);margin-top:4px}}
.luoi{{display:grid;gap:14px}} .hai{{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
.the{{display:inline-block;padding:2px 10px;border-radius:99px;font-size:14px;font-weight:600;border:1px solid}} .ok{{background:var(--okbg);color:var(--ok);border-color:var(--ok-vien)}}
.can{{background:var(--warnbg);color:var(--warn);border-color:var(--warn-vien)}} .bad{{background:var(--badbg);color:var(--bad);border-color:var(--bad-vien)}}
.canh-bao{{border-left:6px solid var(--warn-vien);background:var(--warnbg);border-radius:var(--r-nho);padding:10px 14px;margin:10px 0}} .canh-bao.bad{{border-left-color:var(--bad-vien);background:var(--badbg)}} .canh-bao.ok{{border-left-color:var(--ok-vien);background:var(--okbg)}}
.canh-bao ul{{margin:4px 0 0 18px;padding:0}} table{{border-collapse:collapse;width:100%;font-size:15px}} th,td{{border:1px solid var(--line);padding:5px 8px;text-align:center}} th{{background:var(--th)}} td.trai{{text-align:left}}
tr.xem td{{background:var(--warnbg)}} .thanh{{height:18px;background:var(--xam-nen);border-radius:9px;position:relative;margin:6px 0 2px;overflow:hidden}} .thanh i{{display:block;height:100%;background:var(--pri)}}
.vach{{position:absolute;top:0;bottom:0;width:3px;background:var(--bad)}}
.o-so{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}} .o-the{{border:1px solid var(--line);border-radius:var(--r);padding:8px;text-align:center;background:var(--card)}}
.o-the.xem{{border-color:var(--warn-vien);background:var(--warnbg)}} .o-the img{{image-rendering:pixelated;border:1px solid var(--line);margin:2px;max-width:100%}} .o-the .an img{{image-rendering:auto}}
.doc{{font-size:34px;font-weight:700;color:var(--pri-dam);line-height:1.1}} .tk{{font-size:13px;display:grid;grid-template-columns:20px 1fr 48px;gap:4px;align-items:center;text-align:left}} .tk b{{display:block;height:9px;background:var(--pri2);border-radius:4px}}
.ocr-ban{{background:var(--pri2-nhat);border:2px solid var(--pri2);border-radius:var(--r);padding:8px 12px;margin-bottom:12px;color:var(--ink)}}
.chu{{display:inline-block;width:14px;height:14px;border-radius:50%;vertical-align:middle;margin-right:4px}} code{{background:var(--xam-nen);padding:1px 5px;border-radius:4px}}
.chan{{color:var(--mut);font-size:14px;margin-top:24px}}
</style></head><body><main>
<h1>Pipeline xử lý ảnh phiếu – từng bước</h1>
<p class="sub">Ảnh: <code>{e(ctx['ten'])}</code> · chạy OFFLINE bằng đúng hàm của hệ thống (không viết lại thuật toán, không ghi CSDL) · tổng {ctx['tong_ms']:.0f} ms</p>
{ctx['canh_bao']}
{ctx['buoc']}
<p class="chan">Trang này do <code>tools/demo_xu_ly_anh.py</code> sinh ra; mọi số trong trang là kết quả chạy thật trên ảnh trên, không lấy từ nơi khác.
Ngưỡng và mô hình: <code>cv_engine/preprocessing.py</code>, <code>models/omr_m1.json</code>, <code>models/ocr_cnn.json</code> (không sửa).</p>
</main></body></html>"""


def tom_tat_canh_bao(kq, omr, dc, blur_gan_nguong: bool) -> str:
    from cv_engine.preprocessing import MA_LY_DO
    if not kq.ok:
        return (f'<div class="canh-bao bad"><b>Ảnh bị TỪ CHỐI – không chấm.</b> Mã <code>{e(kq.ly_do)}</code>: {e(MA_LY_DO.get(kq.ly_do, ""))}'
                f'<br>Đây là hành vi đúng: nắn sai mà vẫn chấm = ghi nhầm điểm; từ chối thì giáo viên chụp lại.</div>')
    cx = [c for c in omr.cau if c.can_xem]
    ds = []
    if cx:
        ds.append(f"{len(cx)}/40 câu cần giáo viên xem (câu {', '.join(str(c.cau) for c in cx)}) – máy KHÔNG chấm tự động các câu này")
    if omr.to_nhat:
        ds.append("phiếu tô nhạt cả tờ (cờ <code>to_nhat</code>)")
    for ten, k in (("SBD", "sbd"), ("Mã đề", "ma_de")):
        gt, chac, ly = dc[k]
        if not chac:
            ds.append(f"{ten} <code>{e(gt)}</code> chưa chắc: {e(', '.join(ly))}")
    if blur_gan_nguong:
        ds.append("độ mờ gần ngưỡng từ chối – nên chụp lại nếu có thể")
    if not ds:
        return '<div class="canh-bao ok"><b>Không có cờ cảnh báo.</b> 40 câu, SBD và mã đề đều được máy tự nhận.</div>'
    return '<div class="canh-bao"><b>Cờ cảnh báo (phiếu sẽ vào hàng đợi giáo viên):</b><ul>' + "".join(f"<li>{x}</li>" for x in ds) + "</ul></div>"


def chay(anh: Path, ra: Path, dung_ds: bool = True) -> dict:
    from cv_engine import ocr
    from cv_engine.omr import MA_LY_DO_OMR, doc_phieu, nap_mo_hinh
    from cv_engine.preprocessing import MA_LY_DO, MO_MIN, doc_anh, nap_layout, preprocess_anh

    lay, mh, mh_ocr = nap_layout("phieu"), nap_mo_hinh(), ocr.nap_mo_hinh_ocr()
    t_tong = time.perf_counter()
    gray, exif = doc_anh(anh)
    ms = {}
    t = time.perf_counter()
    kq = preprocess_anh(gray, lay, exif)
    ms["tien_xu_ly"] = (time.perf_counter() - t) * 1000
    buoc = []
    # 1 ảnh gốc
    buoc.append(the_buoc(1, "Ảnh gốc từ điện thoại", f"Đọc file, áp EXIF (xoay đúng chiều xem), chuyển xám. Cỡ {gray.shape[1]}×{gray.shape[0]} px · EXIF Orientation = {exif}.",
                         anh_tag(uri(gray, 1100), f"{anh.name} (xám, thu nhỏ khi hiển thị)")))
    # 2 chất lượng
    bs = kq.blur_score
    if bs is not None:
        tl = min(bs / (MO_MIN * 6), 1.0)
        noi = (f'<p>Độ nét <code>blur_score</code> = <b>{bs:.4f}</b> · ngưỡng từ chối <code>MO_MIN</code> = {MO_MIN} → '
               f'{"<span class=\"the ok\">đủ nét</span>" if bs >= MO_MIN else "<span class=\"the bad\">quá mờ</span>"} '
               f'(bằng {bs / MO_MIN:.2f} lần ngưỡng).</p><div class="thanh"><i style="width:{100 * tl:.0f}%"></i><span class="vach" style="left:{100 / 6:.1f}%"></span></div>'
               f'<small>Thanh: 0 → 6×ngưỡng; vạch đỏ = ngưỡng. Đo trên ảnh đã nắn (hướng mờ theo trục x/y), không phải trên ảnh gốc.</small>')
    else:
        noi = '<p>Chưa đo được độ nét vì chưa nắn được ảnh (dừng ở bước tìm góc).</p>'
    gan_nguong = bs is not None and kq.ok and bs < 2 * MO_MIN
    buoc.append(the_buoc(2, "Kiểm tra chất lượng (độ mờ)", "Ảnh rung tay / lấy nét sai thì ô tô và chữ số bị nhoè → đọc sai. Quá ngưỡng thì TỪ CHỐI và yêu cầu chụp lại.", noi))
    # 3 góc
    mo_ta3 = "Tìm 4 ô vuông đen ở góc phiếu: vòng vàng = mọi ứng viên, vòng xanh + tứ giác = bộ 4 hợp hình học được chọn (lồi, cỡ, hình dạng, độ phối cảnh)."
    if kq.marker is not None or kq.chi_tiet.get("ung_vien"):
        n_uv = len(kq.chi_tiet.get("ung_vien", []))
        buoc.append(the_buoc(3, "Phát hiện 4 góc (marker)", mo_ta3, anh_tag(uri(ve_goc(gray, kq), 1100), f"{n_uv} ứng viên → 4 góc TL, TR, BR, BL · phiếu bị xoay {kq.huong_xoay}° trong ảnh gốc" if kq.marker is not None else f"{n_uv} ứng viên, không chọn được bộ 4")))
    else:
        buoc.append(the_buoc(3, "Phát hiện 4 góc (marker)", mo_ta3, "<p>Không tìm thấy ứng viên marker nào.</p>"))
    omr = hv = dc = None
    ten_ds = ""
    if kq.anh_nan is not None:
        lop = "" if kq.ok else "tu-choi"
        ghi = "" if kq.ok else '<p><span class="the bad">Chỉ để xem – ảnh bị từ chối, KHÔNG được chấm.</span></p>'
        buoc.append(the_buoc(4, "Nắn phối cảnh về A4 chuẩn 2480×3508", "Biến đổi phối cảnh (homography) từ 4 góc về khung chuẩn @300 DPI; toạ độ mọi ô khi đó trùng <code>layout.json</code>." + ghi,
                             anh_tag(uri(kq.anh_nan, 900), f"Ảnh nắn {kq.anh_nan.shape[1]}×{kq.anh_nan.shape[0]} px (thu nhỏ khi hiển thị)"), ms["tien_xu_ly"], lop))
    else:
        buoc.append(the_buoc(4, "Nắn phối cảnh", "Không nắn được vì ảnh bị từ chối ở bước trước.", "<p><span class='the bad'>Dừng tại đây.</span></p>"))
    if kq.ok:
        t = time.perf_counter()
        omr = doc_phieu(kq, lay, mh)
        ms["omr"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        hv = ocr.doc_chu_so(kq, lay, mh_ocr)
        ms["ocr"] = (time.perf_counter() - t) * 1000
        sbd_ds = ma_ds = None
        if dung_ds and KICH_BAN.exists():
            ds = json.loads(KICH_BAN.read_text(encoding="utf-8"))["ky_thi_danh_sach"]
            sbd_ds, ma_ds = set(ds["sbd"]), set(ds["ma_de"])
            ten_ds = "Danh sách dự thi lấy từ kịch bản AG (kỳ thi 1633), giống cách công cụ chấm AG làm."
        sbd_trong = None if (sbd_ds is None or "?" in omr.sbd) else omr.sbd in sbd_ds
        ma_trong = None if (ma_ds is None or "?" in omr.ma_de) else omr.ma_de in ma_ds
        dc = ocr.doi_chieu_dinh_danh(omr, hv, sbd_trong, ma_trong, mo_hinh=mh_ocr)
        # 5 lưới
        tong, ct = ve_luoi(kq.anh_nan, lay, omr)
        dmax = max((max(abs(v[0]), abs(v[1])) for v in omr.dich_chuyen_mm.values()), default=0.0)
        buoc.append(the_buoc(5, "Lưới ô định vị", f"Layout cho biết ô nằm đâu trên phiếu chuẩn. Giấy cong / in lệch làm ô lệch vài mm, nên máy khớp mẫu để <b>dò lại từng hàng</b>. Dịch lớn nhất trên phiếu này: <b>{dmax:.2f} mm</b>.",
                             '<div class="luoi hai">' + anh_tag(uri(tong, 700), "3 khối: 40 câu, SBD, mã đề") +
                             anh_tag(uri(ct, 1000), "Khối đáp án: chấm xanh dương = vị trí lý thuyết; vòng xanh lá = sau khi dò từng hàng") + "</div>", None))
        # 6 OMR
        ct6, sb6, md6 = ve_omr(kq.anh_nan, lay, omr)
        n_ro = sum(c.trang_thai == "ro" for c in omr.cau)
        n_mo = sum(c.trang_thai == "mo" for c in omr.cau)
        n_nh = sum(c.trang_thai == "nhieu" for c in omr.cau)
        n_tr = sum(c.trang_thai == "trong" for c in omr.cau)
        leg = ('<p><span class="chu" style="background:#50a03c"></span>rõ &nbsp; <span class="chu" style="background:#ff8c00"></span>mờ &nbsp; '
               '<span class="chu" style="background:#fff;border:2px solid #969696"></span>trống &nbsp; <b style="color:#d23232">khung đỏ quanh hàng</b> = máy KHÔNG chắc, chuyển giáo viên</p>')
        hang = []
        for c in omr.cau:
            if c.can_xem or c.trang_thai in ("mo", "nhieu"):
                lyd = "; ".join(MA_LY_DO_OMR.get(x, x) for x in c.ly_do)
                hang.append(f'<tr class="{"xem" if c.can_xem else ""}"><td>{c.cau}</td><td>{e(c.trang_thai)}</td><td>{e(c.dap_an or "–")}</td><td>{c.do_tin_cay:.2f}</td><td>{"CẦN XEM" if c.can_xem else "chắc"}</td><td class="trai">{e(lyd)}</td></tr>')
        bang = ('<table><tr><th>Câu</th><th>Trạng thái</th><th>Đáp án đọc</th><th>Độ tin cậy</th><th>Quyết định</th><th>Lý do</th></tr>' + "".join(hang) + "</table>") if hang else "<p>Không có câu mờ / nhiều ô / cần xem.</p>"
        buoc.append(the_buoc(6, "OMR: tô màu từng ô", f"Mỗi ô được phân 3 lớp (trống / mờ / rõ) bằng hồi quy logistic trên đặc trưng độ tối, rồi luật cấp câu (0 ô → trống, 1 ô → đáp án, ≥2 ô → nhiều ô). "
                             f"Phiếu này: {n_ro} câu rõ · {n_mo} mờ · {n_nh} nhiều ô · {n_tr} trống · {sum(c.can_xem for c in omr.cau)} cần xem.",
                             leg + '<div class="luoi hai">' + anh_tag(uri(ct6, 1000), "40 câu × 4 ô") +
                             '<div>' + anh_tag(uri(sb6, 420), f"Bubble SBD: máy đọc {omr.sbd}") + anh_tag(uri(md6, 420), f"Bubble mã đề: máy đọc {omr.ma_de}") + '</div></div>'
                             + "<h3>Các câu mờ / nhiều ô / cần xem</h3>" + bang, ms["omr"]))
        # 7 ô chữ số
        cards = []
        for ten, ds_cot in (("SBD", hv.sbd), ("Mã đề", hv.ma_de)):
            for h in ds_cot:
                xem = bool(h.loi_o) or (not h.o_trong and h.chu_so == "?")
                if h.anh28 is not None and h.chu_so != "?":
                    nho = cv2.resize(h.anh28, (112, 112), interpolation=cv2.INTER_NEAREST)
                    tk = "".join(f'<div class="tk"><span>{d}</span><b style="width:{max(2, int(100 * p))}%"></b><span>{pt(p)}</span></div>' for d, p in h.top_k)
                    mid = f'<div class="doc">{e(h.chu_so)}</div>{tk}'
                    a28 = f'<img src="{uri(nho, png=True)}" width="112" height="112" alt="28x28">'
                else:
                    a28 = ""
                    mid = f'<div class="doc">?</div><small>{"ô trống – không qua CNN" if h.o_trong else e(MA_LY_DO_OCR_TEXT(h.loi_o))}</small>'
                ao = uri(h.anh_o, png=True) if h.anh_o is not None else ""
                cards.append(f'<div class="o-the {"xem" if xem else ""}"><b>{ten} · vị trí {h.vi_tri + 1}</b><div class="an"><img src="{ao}" alt="ô cắt" width="{h.anh_o.shape[1] // 2 if h.anh_o is not None else 0}"></div>'
                             f'<small>ô cắt (bỏ viền)</small><br>{a28}<br><small>28×28 vào CNN</small>{mid}</div>')
        buoc.append(the_buoc(7, "Ô viết tay → CNN nhận diện chữ số (nơi OCR hoạt động)",
                             "Chín ô viết tay (SBD 6 + mã đề 3) được cắt bỏ viền in sẵn, chuẩn hoá về 28×28 kiểu MNIST rồi đưa vào CNN SÂU (hai khối × hai lớp tích chập, Dense 128; mô hình triển khai từ lệnh AN) chạy bằng NumPy. "
                             "Ô trống / ít mực / bôi đen thì KHÔNG qua CNN.",
                             '<div class="ocr-ban"><b>Đây là bước máy học nhận diện chữ số.</b> Phần bubble ở bước 6 chỉ là đo độ tối, không có CNN. Xác suất đã hiệu chỉnh nhiệt độ (T = ' + f"{mh_ocr.thanh_vien[0]['T']:.2f}".replace(".", ",") + ').</div>'
                             '<div class="o-so">' + "".join(cards) + "</div>", ms["ocr"]))
        # 8 hai kênh
        hangs = []
        for ten, k, cot_bub, cot_hv in (("SBD", "sbd", omr.sbd_cot, hv.sbd), ("Mã đề", "ma_de", omr.ma_de_cot, hv.ma_de)):
            for b, h, d in zip(cot_bub, cot_hv, dc["cot"][k]):
                if h.chu_so == "?":
                    cnn = "ô trống" if h.o_trong else "không đọc được"
                else:
                    cnn = f"{h.chu_so} ({pt(h.p)})"
                kqc = '<span class="the ok">chắc</span>' if d.chac else '<span class="the can">cần xem</span>'
                ly = "; ".join(f"{x}" for x in d.ly_do) or ("chỉ nhờ bubble (ô viết tay trống)" if d.chi_trong_bubble else "hai kênh cùng chữ số")
                hangs.append(f'<tr class="{"" if d.chac else "xem"}"><td>{ten} {b.vi_tri}</td><td><b>{e(b.chu_so)}</b></td><td>{e(cnn)}</td><td>{e(d.chu_so)}</td><td>{kqc}</td><td class="trai">{e(ly)}</td></tr>')
        tr = []
        for ten, k in (("SBD", "sbd"), ("Mã đề", "ma_de")):
            gt, chac, ly = dc[k]
            tr.append(f'<li><b>{ten} chốt: {e(gt)}</b> – {"<span class=\"the ok\">chắc, tự nhận</span>" if chac else "<span class=\"the can\">cần giáo viên xem</span>"} {e(", ".join(ly))}</li>')
        buoc.append(the_buoc(8, "Đối chiếu hai kênh: bubble ↔ chữ viết tay",
                             "Hai kênh độc lập: <b>bubble</b> (OMR, thí sinh tô) và <b>chữ viết tay</b> (CNN). Chỉ khi hai kênh cùng chữ số (CNN p ≥ 0,5) cột mới được tự nhận; lệch → giáo viên xem. Đây là cách tránh ghi nhầm điểm vì đọc sai SBD.",
                             f'<p class="mo-ta">{e(ten_ds)}</p><table><tr><th>Cột</th><th>Bubble</th><th>CNN (xác suất)</th><th>Chốt</th><th>Kết quả</th><th>Lý do</th></tr>' + "".join(hangs) + "</table><ul>" + "".join(tr) + "</ul>"))
    tong_ms = (time.perf_counter() - t_tong) * 1000
    ctx = {"ten": anh.name, "tong_ms": tong_ms, "buoc": "\n".join(buoc), "canh_bao": tom_tat_canh_bao(kq, omr, dc, gan_nguong)}
    ra.parent.mkdir(parents=True, exist_ok=True)
    ra.write_text(dung_trang(ctx), encoding="utf-8")
    ket = {"anh": anh.name, "ok": kq.ok, "ly_do": kq.ly_do, "blur_score": bs, "ms": {k: round(v, 1) for k, v in ms.items()}}
    if omr:
        ket.update(cau_can_xem=sum(c.can_xem for c in omr.cau), sbd=dc["sbd"][0], sbd_chac=dc["sbd"][1], ma_de=dc["ma_de"][0], ma_de_chac=dc["ma_de"][1])
    return ket


def MA_LY_DO_OCR_TEXT(ma: str) -> str:
    from cv_engine.ocr import MA_LY_DO_OCR
    return MA_LY_DO_OCR.get(ma, ma or "không đọc được")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Dựng trang HTML từng bước xử lý ảnh phiếu (offline, chỉ đọc).")
    ap.add_argument("--anh", required=True, type=Path, help="ảnh phiếu (JPG/PNG/HEIC)")
    ap.add_argument("--ra", type=Path, default=None, help="tệp HTML ra (mặc định data/_eval/demo_3_phien/xu_ly_anh_<tên ảnh>.html)")
    ap.add_argument("--khong-danh-sach", action="store_true", help="không dùng danh sách thí sinh của kịch bản AG")
    a = ap.parse_args()
    anh = a.anh if a.anh.is_absolute() else (Path.cwd() / a.anh)
    if not anh.is_file():
        sys.exit(f"Không thấy ảnh: {anh}")
    ra = a.ra or (ROOT / "data" / "_eval" / "demo_3_phien" / f"xu_ly_anh_{anh.stem}.html")
    ket = chay(anh, ra, not a.khong_danh_sach)
    print(json.dumps(ket, ensure_ascii=False))
    print(f"Đã ghi {ra}")


if __name__ == "__main__":
    main()

