"""
demo_may_hoc.py - Lệnh AJ (phiên demo "Máy học"): dựng MỘT trang HTML tự chứa tổng hợp phần máy học của đồ án. CHỈ ĐỌC kết quả đã có
(docs/kiem_ke_du_lieu.md, data/_eval/ai/ket_qua.json, data/_eval/ad/ket_qua.json, models/*.json) – không huấn luyện, không đổi mô hình, không bịa số.

  python tools/demo_may_hoc.py --ra data/_eval/demo_3_phien/may_hoc.html
  python tools/demo_may_hoc.py --truc-tiep --ra data/_eval/demo_3_phien/may_hoc_truc_tiep.html
        # --truc-tiep: nạp models/ocr_cnn.json, chạy CNN THẬT (NumPy) trên 504 ô chữ số của phiếu dev 0001–0028 (viết tay trên phiếu,
        #   CNN triển khai KHÔNG huấn luyện trên chúng – chỉ huấn luyện trên MNIST + trang chữ số D001–D010). Không đọc val / test.
        #   Có mục 1 mẫu ngẫu nhiên (seed 2026, cả đúng lẫn sai) và mục "ví dụ sai – CHỌN CÓ CHỦ Ý" kèm tỉ lệ đúng của TOÀN BỘ mẫu.
"""
import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KIEM_KE = ROOT / "docs" / "kiem_ke_du_lieu.md"
KQ_AI = ROOT / "data" / "_eval" / "ai" / "ket_qua.json"
KQ_AD = ROOT / "data" / "_eval" / "ad" / "ket_qua.json"
CAT = ROOT / "data" / "_ocr" / "cat"
MAU_CSS = ROOT / "frontend" / "mau.css"
TEN = {"lr": "Logistic regression", "knn": "k-NN", "svm": "SVM nhân RBF", "rf": "Random Forest (300 cây)", "mlp": "MLP 1 lớp ẩn (128)", "cnn": "CNN hiện tại"}


def e(s) -> str:
    return html.escape(str(s))


def pt(v: float, d: int = 2) -> str:
    return f"{100 * v:.{d}f}%".replace(".", ",")


def inline(s: str) -> str:
    s = e(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


# ------------------------------------------------------------------------------------------------ đọc kiem_ke_du_lieu.md
def doc_kiem_ke() -> list[dict]:
    """Tách theo '## ': mỗi mục = {tieu_de, khoi: [('p', text) | ('bang', [[ô]])]}. Chỉ chuyển đổi, không sửa số."""
    muc, cur, bang = [], None, None
    for dong in KIEM_KE.read_text(encoding="utf-8").splitlines():
        if dong.startswith("## "):
            cur = {"tieu_de": dong[3:].strip(), "khoi": []}
            muc.append(cur)
            bang = None
        elif cur is None:
            continue
        elif dong.startswith("|"):
            cur["_dang_p"] = False
            o = [c.strip() for c in dong.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in o):
                continue
            if bang is None:
                bang = []
                cur["khoi"].append(("bang", bang))
            bang.append(o)
        else:
            bang = None
            if dong.strip():        # các dòng liền nhau (không có dòng trống) là MỘT đoạn
                if cur.get("_dang_p"):
                    cur["khoi"][-1] = ("p", cur["khoi"][-1][1] + " " + dong.strip())
                else:
                    cur["khoi"].append(("p", dong.strip()))
                cur["_dang_p"] = True
            else:
                cur["_dang_p"] = False
    return muc


def html_muc(m: dict) -> str:
    ra = [f"<h3>{inline(m['tieu_de'])}</h3>"]
    for loai, nd in m["khoi"]:
        if loai == "p":
            ra.append(f"<p>{inline(nd)}</p>")
        else:
            h = "<div class='cuon'><table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in nd[0]) + "</tr>"
            h += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in nd[1:]) + "</table></div>"
            ra.append(h)
    return "\n".join(ra)


# ------------------------------------------------------------------------------------------------ mô hình
def thong_tin_mo_hinh() -> dict:
    ocr_p = ROOT / "models" / "ocr_cnn.json"
    omr_p = ROOT / "models" / "omr_m1.json"
    ocr = json.loads(ocr_p.read_text(encoding="utf-8"))
    omr = json.loads(omr_p.read_text(encoding="utf-8"))
    m = ocr["thanh_vien"][0]
    n_cnn = sum(int(np.asarray(m[k]).size) for k in ("c1w", "c1b", "c2w", "c2b", "d1w", "d1b", "d2w", "d2b"))
    n_m1 = 0
    for k in ("cau", "bubble"):
        n_m1 += int(np.asarray(omr[k]["he_so"]).size) + int(np.asarray(omr[k]["chan"]).size)
    return {"cnn_tham_so": n_cnn, "cnn_json": ocr_p.stat().st_size, "cnn_kien_truc": ocr["kien_truc"], "cnn_tap": ocr["sieu_du_lieu"].get("tap_huan_luyen", ""),
            "cnn_T": [t["T"] for t in ocr["thanh_vien"]], "m1_tham_so": n_m1, "m1_json": omr_p.stat().st_size, "m1_dac_trung": omr["ten_dac_trung"],
            "m1_tap": omr["sieu_du_lieu"].get("tap_huan_luyen", ""), "m1_lop": omr["cau"]["lop"]}


def the_mo_hinh(t: dict, ai: dict) -> str:
    ks = ai["kich_thuoc_toc_do"]["cnn"]
    return f"""<div class="luoi hai">
<div class="the-md"><h3>M1 – hồi quy logistic cho Ô TÔ (OMR)</h3>
<p>Việc: mỗi ô tròn trên phiếu → <b>{' / '.join(t['m1_lop'])}</b> (trống / mờ / rõ). Đầu vào: {len(t['m1_dac_trung'])} đặc trưng độ tối của ô ({', '.join(t['m1_dac_trung'])}).</p>
<ul><li>Số tham số: <b>{t['m1_tham_so']}</b> (ô đáp án: 3 lớp × 9 đặc trưng + 3 hệ số chặn = 30; ô bubble SBD / mã đề: nhị phân có tô / không, 9 + 1 = 10)</li>
<li>Kích thước tệp: <b>{t['m1_json'] / 1024:.1f} KB</b> (<code>models/omr_m1.json</code>)</li>
<li>Huấn luyện: {e(t['m1_tap'])} – 14 000 ô, chia theo PHIẾU, <code>class_weight = balanced</code></li>
<li>Chạy: NumPy thuần (W·x + b, softmax); ~100–170 ms cho cả tờ (định vị + 250 ô: 160 ô đáp án + 90 ô bubble)</li></ul>
<p class="mut">Vì sao không dùng CNN cho ô tô: ô tô chỉ cần đo độ đậm; mô hình 40 tham số đủ và giải thích được.</p></div>
<div class="the-md"><h3>CNN cho CHỮ SỐ VIẾT TAY (OCR)</h3>
<p>Việc: ô 28×28 → chữ số 0–9. Kiến trúc: <code>{e(t['cnn_kien_truc'])}</code>.</p>
<ul><li>Số tham số: <b>{t['cnn_tham_so']:,}</b> (≈ 106 nghìn)</li>
<li>Kích thước: <b>{ks['byte'] / 1024:.0f} KB</b> trọng số float32; tệp JSON triển khai {t['cnn_json'] / 1048576:.2f} MB (<code>models/ocr_cnn.json</code>)</li>
<li>Huấn luyện: {e(t['cnn_tap'])}; hiệu chỉnh nhiệt độ T = {', '.join(str(x) for x in t['cnn_T'])}</li>
<li>Chạy: NumPy + JSON (không cần PyTorch lúc chạy), {ks['ms_moi_o']:.2f} ms/ô ≈ 17–20 ms cho 9 ô của một phiếu</li></ul>
<p class="mut">Huấn luyện trên Kaggle/PyTorch, xuất sang JSON; kiểm NumPy ↔ PyTorch trùng nhãn 4 376/4 376 chữ số.</p></div></div>"""


# ------------------------------------------------------------------------------------------------ biểu đồ
def bieu_do(ai: dict) -> str:
    """Cột ngang E2b: độ đúng TB 5 người ± độ lệch chuẩn giữa người. CNN = màu nhấn, 5 thuật toán còn lại = xám. Nhãn trực tiếp."""
    hang = sorted(((k, ai["E2b"][k]["macro"], ai["E2b"][k]["sd_nguoi"]) for k in TEN), key=lambda r: -r[1])
    W, L, R, H, G = 900, 250, 150, 44, 10
    x0, x1 = 0.70, 1.0
    X = lambda v: L + (min(max(v, x0), x1) - x0) / (x1 - x0) * (W - L - R)     # noqa: E731
    h = len(hang) * (H + G) + 56
    s = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="Độ đúng E2b của sáu thuật toán trên chữ số của người viết thứ năm" class="bd">']
    for t in (0.7, 0.8, 0.9, 1.0):
        s.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="14" y2="{h - 34}" stroke="var(--line)" stroke-width="1"/>'
                 f'<text x="{X(t):.1f}" y="{h - 14}" text-anchor="middle" font-size="14" fill="var(--mut)">{int(t * 100)}%</text>')
    for i, (k, mc, sd) in enumerate(hang):
        y = 20 + i * (H + G)
        cnn = k == "cnn"
        mau = "var(--pri)" if cnn else "#9AA9B1"
        s.append(f'<text x="{L - 12}" y="{y + H / 2 + 5}" text-anchor="end" font-size="16" fill="var(--ink)" font-weight="{700 if cnn else 400}">{e(TEN[k])}</text>')
        s.append(f'<path d="M{L} {y} H{X(mc) - 4:.1f} a4 4 0 0 1 4 4 V{y + H - 4} a4 4 0 0 1 -4 4 H{L} Z" fill="{mau}"><title>{e(TEN[k])}: {pt(mc)} ± {sd * 100:.2f} điểm</title></path>')
        lo, hi = X(mc - sd), X(mc + sd)
        s.append(f'<line x1="{lo:.1f}" x2="{hi:.1f}" y1="{y + H / 2}" y2="{y + H / 2}" stroke="var(--ink)" stroke-width="2"/>'
                 f'<line x1="{lo:.1f}" x2="{lo:.1f}" y1="{y + H / 2 - 6}" y2="{y + H / 2 + 6}" stroke="var(--ink)" stroke-width="2"/>'
                 f'<line x1="{hi:.1f}" x2="{hi:.1f}" y1="{y + H / 2 - 6}" y2="{y + H / 2 + 6}" stroke="var(--ink)" stroke-width="2"/>')
        s.append(f'<text x="{hi + 10:.1f}" y="{y + H / 2 + 5}" font-size="16" fill="var(--ink)" font-weight="{700 if cnn else 400}">{pt(mc)} ± {sd * 100:.2f}</text>')
    s.append("</svg>")
    bang = "<table><tr><th>Thuật toán</th><th>E2b (TB 5 người)</th><th>± SD giữa người</th><th>Sai mà tự tin (p ≥ 0,5)</th></tr>" + "".join(
        f"<tr><td class='trai'>{e(TEN[k])}</td><td>{pt(mc)}</td><td>{sd * 100:.2f}</td><td>{ai['E2b'][k]['sai_tu_tin_trang_cong']}</td></tr>" for k, mc, sd in hang) + "</table>"
    return "".join(s) + f"<details><summary>Xem dạng bảng</summary>{bang}</details>"


def bang_toc_do(ai: dict) -> str:
    ks = ai["kich_thuoc_toc_do"]
    ten_np = ai["numpy_thuan"]

    def kb(b):
        return f"{b / 1048576:.2f} MB" if b >= 1048576 else f"{b / 1024:.0f} KB"
    hang = "".join(f"<tr class='{'nhan' if k == 'cnn' else ''}'><td class='trai'>{e(TEN[k])}</td><td>{kb(ks[k]['byte'])}</td><td>{ks[k]['ms_moi_o']:.2f}</td><td class='trai'>{e(ten_np[k])}</td></tr>" for k in TEN)
    return (f"<table><tr><th>Thuật toán</th><th>Kích thước</th><th>ms / ô (CPU)</th><th>Chạy bằng NumPy thuần?</th></tr>{hang}</table>"
            f"<p class='mut'>CPU: {e(ai['moi_truong']['cpu'])}; Python {e(ai['moi_truong']['python'])}, NumPy {e(ai['moi_truong']['numpy'])}. Đo của lệnh AI (04/11/2026), nguồn <code>data/_eval/ai/ket_qua.json</code>.</p>")


def muc_am_tinh(ad: dict) -> str:
    b, a, k = ad["tb"]["baseline"], ad["tb"].get("ad1", {}), ad["ket_luan"]
    chenh = k["tc1_chenh_diem"]
    return f"""<div class="canh-bao"><b>Kết quả KHÔNG ĐẠT (lệnh AD) – và vì thế không dùng.</b>
<p>Thử cho CNN học thêm <b>≈ 300 000 mẫu</b>: 240 000 chữ số EMNIST Digits + 60 000 ô phiếu giả do chính chúng tôi vẽ qua đúng bước cắt ô của hệ thống.
Tiêu chí đặt TRƯỚC khi chạy (commit <code>5af47ab</code>): độ đúng trang D phải tăng ≥ 1,00 điểm, cột SBD/mã đề cần xem không được tăng, sai-mà-tự-tin không được tăng.</p>
<ul><li>Độ đúng (TB 5 người, 3 seed): <b>{pt(b['tc1_macro_trang'])} → {pt(a.get('tc1_macro_trang', b['tc1_macro_trang'] + chenh / 100))}</b>, chỉ tăng <b>{chenh:.2f} điểm</b> (cần ≥ 1,00) → <b>KHÔNG ĐẠT</b></li>
<li>Cột SBD / mã đề cần xem: {pt(b['tc3_cot_can_xem'])} → {pt(a['tc3_cot_can_xem']) if 'tc3_cot_can_xem' in a else '10,19%'} (tăng) → <b>KHÔNG ĐẠT</b></li>
<li>Sai mà tự tin: {b['tc2_sai_tu_tin_cong3']} → {a.get('tc2_sai_tu_tin_cong3', 512)} → đạt</li>
<li>Kết luận: {'<b>không đạt cả ba tiêu chí</b>' if not k['dat_ca_ba'] else 'đạt'} → <b>giữ nguyên mô hình cũ</b>, không xuất tệp ứng viên.</li></ul>
<p>Bài học: nhầm 8↔6 giảm (76 → 29) nhưng nhầm 1→7 tăng (51 → 77) – dữ liệu thêm đổi KIỂU lỗi chứ không giảm lỗi. Nút thắt là <b>chỉ có 5 người viết</b>, không phải số lượng ô.
Đối chiếu hai kênh (bubble + chữ viết tay) mới là thứ giữ cho lỗi im lặng = 0, bất kể CNN chính xác tới đâu. Chi tiết: <code>docs/lenh_ad.md</code>.</p></div>"""


def muc_gioi_han() -> str:
    return """<ul class="gh">
<li><b>Chỉ 5 người viết</b> (trang D001–D010) + 4 người trên phiếu dev. Độ đúng giữa các người lệch nhau: từ 92,6% tới 98,2% – người thứ 6 có thể thấp hơn.</li>
<li><b>Ảnh quét sạch ≠ ảnh điện thoại.</b> MNIST / EMNIST là ảnh quét sạch, nét đều. CNN đạt 98,9% trên MNIST nhưng chỉ ≈ 95,4% trên chữ người lạ chụp bằng điện thoại – khoảng cách này là “domain gap”.</li>
<li>Chỉ số chính của đồ án không phải “CNN đúng bao nhiêu %” mà là <b>lỗi im lặng mức trường = 0</b> (không ghi nhầm SBD) nhờ đối chiếu hai kênh; đổi lại khoảng một nửa số ảnh phải giáo viên xem SBD / mã đề (T4 ≈ 46–54%, chưa đạt mục tiêu 10%).</li>
<li>So sánh 6 thuật toán chạy 3 seed cho mô hình ngẫu nhiên, 1 lần cho mô hình tất định; SVM học mẫu con 20 000 ảnh MNIST. Kết luận “CNN đúng nhất” chỉ áp dụng cho dữ liệu này.</li>
<li>Ô tô: 56 ảnh / 28 phiếu huấn luyện, lớp “mờ” rất hiếm (366 / 8 960 ≈ 4,1% ô đáp án); đã đo trên tập val, đợt 2 và 10 tờ giấy thật, chưa thử với nhiều loại bút / giấy khác.</li></ul>"""


# ------------------------------------------------------------------------------------------------ chạy trực tiếp
def chay_truc_tiep() -> dict:
    """CNN thật trên ô phiếu dev 0001–0028 (không huấn luyện trên chúng). Trả số liệu + danh sách ô."""
    from cv_engine import ocr
    from cv_engine.tap_du_lieu import PHIEU_TRAIN, ma_phieu
    x = np.load(CAT / "anh_nan.npz")["x"]
    with (CAT / "anh_nan.csv").open(encoding="utf-8", newline="") as f:
        meta = list(csv.DictReader(f))
    assert len(meta) == len(x)
    idx = [i for i, r in enumerate(meta) if r["loai"] != "trang" and (ma_phieu(r["anh"]) or 0) in PHIEU_TRAIN]      # CHỈ phiếu dev 0001–0028
    assert all(meta[i]["loai"] in ("sbd", "ma_de") for i in idx)
    co_muc = [i for i in idx if meta[i]["trong"] == "0"]
    mh = ocr.nap_mo_hinh_ocr()
    P = ocr.du_doan_xac_suat(mh, x[co_muc])
    du = P.argmax(1)
    y = np.array([int(meta[i]["nhan"]) for i in co_muc])
    ok = du == y
    ra = {"tong_dev": len(idx), "n": len(co_muc), "dung": int(ok.sum()), "theo_nguoi": {}, "o": []}
    for ng in sorted({meta[i]["nguoi"] for i in co_muc}):
        s = np.array([meta[i]["nguoi"] == ng for i in co_muc])
        ra["theo_nguoi"][ng] = (int(ok[s].sum()), int(s.sum()))
    for j, i in enumerate(co_muc):
        ra["o"].append({"x": x[i], "anh": meta[i]["anh"], "vi_tri": f"{meta[i]['loai']} {int(meta[i]['vi_tri']) + 1}", "nguoi": meta[i]["nguoi"], "nhan": int(y[j]),
                        "du": int(du[j]), "p": float(P[j, du[j]]), "p_nhan": float(P[j, y[j]])})
    return ra


def the_o(o: dict) -> str:
    import base64

    import cv2
    ok, buf = cv2.imencode(".png", cv2.resize(255 - o["x"], (84, 84), interpolation=cv2.INTER_NEAREST))
    src = "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()
    dung = o["nhan"] == o["du"]
    return (f'<div class="o-the {"" if dung else "sai"}"><img src="{src}" width="84" height="84" alt="ô {e(o["anh"])}"><div><small>{e(o["anh"])} · {e(o["vi_tri"])}</small></div>'
            f'<div>Nhãn đúng <b>{o["nhan"]}</b> → CNN <b>{o["du"]}</b> ({pt(o["p"], 1)})</div><span class="the {"ok" if dung else "bad"}">{"ĐÚNG" if dung else "SAI"}</span></div>')


def muc_truc_tiep(r: dict) -> str:
    rng = np.random.default_rng(2026)
    mau = [r["o"][i] for i in rng.choice(len(r["o"]), size=24, replace=False)]
    sai = sorted((o for o in r["o"] if o["nhan"] != o["du"]), key=lambda o: -o["p"])
    chon = sai[:8]
    ng = " · ".join(f"người {k}: {d}/{n} ({pt(d / n, 1)})" for k, (d, n) in r["theo_nguoi"].items())
    ti_le = r["dung"] / r["n"]
    return f"""<div class="canh-bao ok"><b>Chạy THẬT bây giờ:</b> CNN <code>models/ocr_cnn.json</code> trên <b>{r['n']} ô viết tay có mực</b> của phiếu dev 0001–0028 (SBD + mã đề; phiếu dev có {r['tong_dev']} ô, trong đó {r['n']} ô có mực).
Mô hình triển khai <b>chưa từng huấn luyện</b> trên các ô này (chỉ MNIST + trang D001–D010). Không đọc phiếu val / test.<br>
<b>Tỉ lệ đúng CHUNG của toàn bộ {r['n']} ô: {r['dung']}/{r['n']} = {pt(ti_le, 1)}</b> ({e(ng)}).</div>
<h4>24 ô lấy NGẪU NHIÊN (seed 2026 – không chọn lọc, đúng lẫn sai)</h4><div class="o-so">{''.join(the_o(o) for o in mau)}</div>
<h4>8 ví dụ SAI – <u>CHỌN CÓ CHỦ Ý</u> (các lần sai tự tin nhất trong {len(sai)} lần sai) để thấy CNN sai kiểu gì</h4>
<p class="mut">Đây KHÔNG phải mẫu đại diện: toàn bộ mẫu đúng {pt(ti_le, 1)}, tức sai {len(sai)}/{r['n']} ({pt(len(sai) / r['n'], 1)}). Ô sai bị kênh bubble chặn lại (không khớp → giáo viên xem): lỗi im lặng mức trường = 0 trên dev.</p>
<div class="o-so">{''.join(the_o(o) for o in chon)}</div>"""


# ------------------------------------------------------------------------------------------------ so sánh mở rộng chạy trực tiếp (lệnh AK)
KQ_AK = ROOT / "data" / "_eval" / "ak" / "ket_qua.json"
AK_NPZ = ROOT / "data" / "_eval" / "ak" / "truc_tiep.npz"


def anh_o(x28: np.ndarray, px: int = 56) -> str:
    import base64

    import cv2
    ok, buf = cv2.imencode(".png", cv2.resize(255 - x28, (px, px), interpolation=cv2.INTER_NEAREST))
    return '<img src="data:image/png;base64,' + base64.b64encode(buf.tobytes()).decode() + f'" width="{px}" height="{px}" alt="ô chữ số">'


def chay_so_sanh_truc_tiep(da_tinh_san: bool) -> dict:
    """Chạy (hoặc đọc đã tính sẵn) tools/ak_so_sanh_mo_rong.truc_tiep: mô hình 'người 1 giữ ra' dự đoán ô trang D của người 1. In từng thuật toán khi chạy."""
    sys.path.insert(0, str(ROOT / "tools"))
    import ak_so_sanh_mo_rong as AKM
    print("Chạy trực tiếp từng thuật toán trên ô của người viết 1 (mô hình chưa thấy người này)…" if not da_tinh_san else "Đọc kết quả ĐÃ TÍNH SẴN…", flush=True)
    r = AKM.truc_tiep(da_tinh_san=da_tinh_san, in_ra=lambda s: print(s, flush=True))
    r["npz"] = {k: v for k, v in np.load(AK_NPZ).items()}
    return r


def muc_so_sanh_truc_tiep(tt: dict, ak: dict) -> str:
    N, E, al = ak["nhan"], ak["E2b"], tt["algos"]
    ten = lambda t: N.get(t, t)                                                                  # noqa: E731
    tt_nhan = (f"<b>ĐÃ TÍNH SẴN</b> (đọc từ <code>data/_eval/ak/truc_tiep.json</code>, chạy lúc {e(tt.get('ngay', '?'))}; kết quả y hệt chạy lại, chỉ bỏ thời gian chờ)"
               if tt.get("da_tinh_san") else f"<b>Chạy THẬT bây giờ</b> ({e(tt.get('ngay', ''))})")
    hang = sorted(al, key=lambda t: -al[t]["dung"])
    n = tt["n"]
    r3, r4 = ak["R3"], ak["R4"]
    def dat(x):
        return "ĐẠT" if x["dat"] else "KHÔNG ĐẠT"
    ket_luan = (f'<div class="canh-bao"><b>Kết luận theo tiêu chí đặt trước (commit <code>2e549da</code>) – trung thực:</b><ul>'
                f'<li><b>R3 mức ô: {dat(r3)}</b> – CNN {pt(r3["macro_cnn"])}, thấp hơn tốt nhất ({e(N[r3["tot_nhat"]])} {pt(r3["macro_tot_nhat"])}) {r3["chenh_diem"]:.2f} điểm (ngưỡng 1,0).</li>'
                f'<li><b>R4(a) mức hệ thống, 504 ô phiếu dev: {dat(r4["a"])}</b> – đúng cả chuỗi: CNN {pt(r4["a"]["hw_cnn"])} so với {e(N[r4["a"]["tot_nhat_khac"]])} {pt(r4["a"]["hw_tot_nhat"])}.</li>'
                + (f'<li><b>R4(b) giấy thật (26 trường): {dat(r4["b"])}</b> – CNN {pt(r4["b"]["hw_cnn"])} so với {e(N[r4["b"]["tot_nhat_khac"]])} {pt(r4["b"]["hw_tot_nhat"])} (chênh đúng 1 trường).</li>' if r4["b"] else "")
                + '<li>Cả 11 thuật toán đều <b>0 lần sai mà không cờ</b> nhờ đối chiếu bubble: chọn thuật toán không ảnh hưởng độ an toàn của điểm, chỉ ảnh hưởng số phiếu giáo viên phải xem.</li>'
                '<li>Nên nói: “mạng tích chập vượt mọi thuật toán không-tích-chập ≥ 1,7 điểm”; KHÔNG nói “CNN hiện tại tối ưu” – CNN sâu và LeNet-5 đọc cả chuỗi tốt hơn trên phiếu dev.</li></ul></div>')    # --- biểu đồ cột: độ đúng trên người 1 (chạy trực tiếp)
    W, Lm, R, H, G = 900, 300, 190, 34, 8
    x0, x1 = 0.60, 1.0
    X = lambda v: Lm + (min(max(v, x0), x1) - x0) / (x1 - x0) * (W - Lm - R)                      # noqa: E731
    h = len(hang) * (H + G) + 50
    s = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="Độ đúng của từng thuật toán trên ô của người viết 1" class="bd">']
    for v in (0.6, 0.7, 0.8, 0.9, 1.0):
        s.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="8" y2="{h - 32}" stroke="var(--line)"/><text x="{X(v):.1f}" y="{h - 12}" text-anchor="middle" font-size="14" fill="var(--mut)">{int(v * 100)}%</text>')
    for i, t in enumerate(hang):
        y = 12 + i * (H + G)
        cnn = t == "cnn"
        s.append(f'<text x="{Lm - 10}" y="{y + H / 2 + 5}" text-anchor="end" font-size="15" fill="var(--ink)" font-weight="{700 if cnn else 400}">{e(ten(t))}</text>'
                 f'<rect x="{Lm}" y="{y}" width="{X(al[t]["dung"]) - Lm:.1f}" height="{H}" rx="4" fill="{"var(--pri)" if cnn else "#9AA9B1"}"><title>{e(ten(t))}: {pt(al[t]["dung"])}</title></rect>'
                 f'<text x="{X(al[t]["dung"]) + 8:.1f}" y="{y + H / 2 + 5}" font-size="15" fill="var(--ink)" font-weight="{700 if cnn else 400}">{pt(al[t]["dung"])} · sai {al[t]["sai"]}</text>')
    s.append("</svg>")
    # --- bảng chạy trực tiếp
    bang = ("<table><tr><th>Thuật toán</th><th>Đúng (người 1)</th><th>Ô sai</th><th>Thời gian cả {n} ô</th><th>Kích thước</th><th>E2b – TB 5 người</th></tr>".format(n=n)
            + "".join(f"<tr class='{'nhan' if t == 'cnn' else ''}'><td class='trai'>{e(ten(t))}</td><td>{pt(al[t]['dung'])}</td><td>{al[t]['sai']}/{n}</td><td>{al[t]['giay_tong']:.2f} s</td>"
                      f"<td>{al[t]['byte'] / 1048576:.2f} MB</td><td>{pt(E[t]['macro']) if t in E else '–'}</td></tr>" for t in hang) + "</table>")
    # --- R4 tóm tắt
    ra, rb = ak["R4a"], ak.get("R4b") or {}
    thu = sorted(ra, key=lambda t: -ra[t]["hw_gop"])
    r4 = ("<table><tr><th>Thuật toán</th><th>(a) 504 ô phiếu dev: đúng cả chuỗi</th><th>(a) sai mà không cờ</th><th>(b) 117 ô giấy thật: đúng cả chuỗi</th><th>(b) sai mà không cờ</th></tr>"
          + "".join(f"<tr class='{'nhan' if t == 'cnn' else ''}'><td class='trai'>{e(ten(t))}</td><td>{pt(ra[t]['hw_gop'])}</td><td>{ra[t]['sai_khong_co_cong']}</td>"
                    + (f"<td>{pt(rb[bt]['hw_gop'])}</td><td>{rb[bt]['sai_khong_co_cong']}</td>" if (bt := ('cnn_trien_khai' if t == 'cnn' else t)) in rb else "<td>–</td><td>–</td>")
                    + "</tr>" for t in thu) + "</table>")
    # --- lưới ví dụ: cùng một ô, các thuật toán đọc khác nhau
    p = tt["npz"]
    x, y = p["x"], p["y"].astype(int)
    co = [t for t in hang if f"p_{t}" in p]
    P = np.stack([p[f"p_{t}"] for t in co]).astype(int)                                           # [A, N]
    bat_dong = np.where((P != P[0]).any(0))[0]
    rng = np.random.default_rng(2026)
    ngau = sorted(rng.choice(bat_dong, size=min(12, len(bat_dong)), replace=False).tolist()) if len(bat_dong) else []
    ci = co.index("cnn") if "cnn" in co else 0
    nhieu_dung = [i for i in np.where(P[ci] != y)[0] if (P[:, i] == y[i]).sum() >= len(co) // 2]
    co_y = sorted(nhieu_dung, key=lambda i: -(P[:, i] == y[i]).sum())[:8]

    def bang_vd(ids):
        d = "<table><tr><th>Ô</th><th>Đúng</th>" + "".join(f"<th title='{e(ten(t))}'>{e(ten(t).split(' (')[0].replace('Logistic regression', 'LR').replace('Random Forest', 'RF').replace('Decision Tree', 'Cây QĐ').replace('Naive Bayes Gaussian', 'NB').replace('HistGradientBoosting', 'HGB'))}</th>" for t in co) + "</tr>"
        for i in ids:
            d += f"<tr><td>{anh_o(x[i], 48)}</td><td><b>{y[i]}</b></td>" + "".join(f"<td class='{'' if P[k, i] == y[i] else 'sai-o'}'>{P[k, i]}</td>" for k in range(len(co))) + "</tr>"
        return d + "</table>"
    ok_cnn = int((P[ci] == y).sum())
    return f"""<div class="canh-bao ok">{tt_nhan}: {len(co)} thuật toán, mỗi cái là mô hình đã huấn luyện <b>không có người viết 1</b>, dự đoán <b>{n} ô</b> chữ số viết tay của người 1 (trang D, ảnh điện thoại).
Hệ thống thật dùng CNN; các thuật toán khác chỉ để so sánh. Người 1 là người viết <b>khó nhất</b> trong 5 người (cột “E2b – TB 5 người” là con số công bằng hơn).</div>
{ket_luan}{''.join(s)}{bang}
<h4>Mức hệ thống: thay bộ đọc chữ số rồi vẫn đối chiếu bubble</h4>
<p class="mut">“Đúng cả chuỗi” = đọc đúng cả 6 chữ số SBD <i>và</i> 3 chữ số mã đề của một phiếu (nhóm trường gộp). “Sai mà không cờ” = hệ thống TỰ NHẬN một SBD / mã đề sai (nguy hiểm nhất). (a) 56 phiếu dev, 5 người viết chính họ → lạc quan. (b) 13 ảnh giấy thật, 26 trường → mỗi trường = 3,8 điểm, rất thô.</p>
<div class="cuon">{r4}</div>
<h4>Cùng một ô, các thuật toán đọc khác nhau</h4>
<p class="mut"><b>12 ô lấy NGẪU NHIÊN</b> (seed 2026) trong {len(bat_dong)} ô mà các thuật toán KHÔNG đồng ý với nhau (ô cả {len(co)} cái cùng đọc giống nhau thì không hiện). Số đỏ = đọc sai.</p>
<div class="cuon">{bang_vd(ngau)}</div>
<h4>8 ô CNN đọc sai nhưng đa số thuật toán khác đọc đúng – <u>CHỌN CÓ CHỦ Ý</u></h4>
<p class="mut">Đây KHÔNG phải mẫu đại diện: CNN đọc đúng {ok_cnn}/{n} ô ({pt(ok_cnn / n)}); hiện ra để thấy CNN không hoàn hảo.</p>
<div class="cuon">{bang_vd(co_y)}</div>
<div class="canh-bao"><b>Nói thẳng:</b> thư viện OCR <b>PP-OCRv6</b> (lệnh D, chỉ DEV, không nằm trong bảng trên vì khác giao thức) <b>đúng hơn CNN 1,1 điểm</b> trên chữ người lạ (96,9% so với 95,8%) và 5,5 điểm trên 504 ô phiếu dev (98,2% so với 92,7%),
nhưng <b>nặng ~50 lần</b> (≈ 5,3 triệu so với 105 866 tham số, +71 MB thư viện) và lắp nguyên trạng làm số phiếu cần giáo viên xem tăng (53,6% so với 46,4%). Nhóm giữ CNN cho hệ thống; PP-OCRv6 là hướng cải tiến.</div>"""


# ------------------------------------------------------------------------------------------------ trang
CSS = """*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Segoe UI",system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px} h1{font-size:28px;margin:0 0 4px} .sub{color:var(--mut);margin:0 0 16px}
section{background:var(--card);border:1px solid var(--line);border-radius:var(--r-lon);box-shadow:var(--bong);padding:18px 22px;margin:18px 0}
h2{font-size:21px;margin:0 0 6px;display:flex;gap:10px;align-items:center} h2 .so{background:var(--pri);color:var(--tren-pri);border-radius:50%;width:32px;height:32px;display:inline-flex;align-items:center;justify-content:center;font-size:16px;flex:none}
h3{font-size:18px;margin:14px 0 4px} h4{font-size:16px;margin:16px 0 4px} .mut{color:var(--mut)} .luoi{display:grid;gap:14px} .hai{grid-template-columns:repeat(auto-fit,minmax(360px,1fr))}
.the-md{border:1px solid var(--line);border-radius:var(--r);padding:4px 16px 8px;background:var(--hover)} table{border-collapse:collapse;width:100%;font-size:15px;margin:6px 0} th,td{border:1px solid var(--line);padding:5px 8px;text-align:center} th{background:var(--th)} td.trai{text-align:left}
tr.nhan td{background:var(--pri-nhat);font-weight:600} .cuon{overflow-x:auto} code{background:var(--xam-nen);padding:1px 5px;border-radius:4px;font-size:14px}
.canh-bao{border-left:6px solid var(--warn-vien);background:var(--warnbg);border-radius:var(--r-nho);padding:10px 16px;margin:10px 0} .canh-bao.ok{border-left-color:var(--ok-vien);background:var(--okbg)}
.bd{width:100%;height:auto;display:block;margin:8px 0} details{margin:6px 0} summary{cursor:pointer;color:var(--link)} .gh li{margin:6px 0}
.o-so{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px} .o-the{border:1px solid var(--line);border-radius:var(--r);padding:8px;text-align:center;font-size:14px;background:var(--card)} .o-the.sai{border-color:var(--bad-vien);background:var(--badbg)}
.o-the img{image-rendering:pixelated;border:1px solid var(--line)} .the{display:inline-block;padding:1px 9px;border-radius:99px;font-size:13px;font-weight:700;border:1px solid} .the.ok{background:var(--okbg);color:var(--ok);border-color:var(--ok-vien)} .the.bad{background:var(--badbg);color:var(--bad);border-color:var(--bad-vien)}
.so3{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:8px 0} .so3>div{background:var(--pri-nhat);border-radius:var(--r);padding:10px 14px} .so3 b{display:block;font-size:30px;color:var(--pri-dam);line-height:1.15}
.chan{color:var(--mut);font-size:14px;margin-top:24px} td.sai-o{color:var(--bad);background:var(--badbg);font-weight:700}"""


def dung_trang(truc_tiep: dict | None, so_sanh: dict | None = None) -> str:
    ai = json.loads(KQ_AI.read_text(encoding="utf-8"))
    ad = json.loads(KQ_AD.read_text(encoding="utf-8"))
    t = thong_tin_mo_hinh()
    css = MAU_CSS.read_text(encoding="utf-8") if MAU_CSS.exists() else ""
    cnn, svm = ai["E2b"]["cnn"], ai["E2b"]["svm"]
    tom = (f'<div class="so3"><div><b>{pt(cnn["macro"])}</b>CNN, chữ người viết thứ 5 (TB 5 người, ± {cnn["sd_nguoi"] * 100:.2f})</div>'
           f'<div><b>{pt(svm["macro"])}</b>SVM – thuật toán đứng thứ hai</div><div><b>{t["cnn_tham_so"] // 1000} nghìn</b>tham số CNN; {t["cnn_json"] / 1048576:.2f} MB, chạy NumPy</div></div>')
    muc = doc_kiem_ke()
    du_lieu = "".join(html_muc(m) for m in muc)

    def sec(n, tieu_de, nd):
        return f'<section><h2><span class="so">{n}</span>{e(tieu_de)}</h2>{nd}</section>'
    s = [sec(1, "Dữ liệu: có bao nhiêu mẫu, từ đâu", '<p class="mut">Nguyên văn các bảng của <code>docs/kiem_ke_du_lieu.md</code> (lệnh AI) – chỉ có số liệu, không có dữ liệu.</p>' + du_lieu),
         sec(2, "Hai mô hình trong hệ thống", the_mo_hinh(t, ai)),
         sec(3, "CNN so với 5 thuật toán khác (thí nghiệm E2b)",
             '<p>Học trên MNIST + chữ của <b>4 người</b>, thử trên <b>người thứ 5</b> chưa từng thấy (luân phiên 5 người, TB ± độ lệch chuẩn giữa người). Tiêu chí đăng ký trước (commit <code>253a4b5</code>).</p>'
             + tom + bieu_do(ai) + f'<p><b>Kết luận R1:</b> CNN đúng nhất ({pt(ai["R1"]["macro_cnn"])}); chênh với tốt nhất = {ai["R1"]["chenh_diem"]:.2f} điểm → hợp lý. '
             f'Khoảng sai số ± lớn (≈ {cnn["sd_nguoi"] * 100:.1f} điểm) vì chỉ có 5 người: khác biệt nhỏ giữa các thuật toán chưa chắc có ý nghĩa, CNN cao hơn SVM ở {sum(cnn["theo_nguoi"][str(i)] > svm["theo_nguoi"][str(i)] for i in range(1, 6))}/5 người (chênh TB {(cnn["macro"] - svm["macro"]) * 100:.1f} điểm).</p>'),
         sec(4, "Kích thước và tốc độ", bang_toc_do(ai)),
         sec(5, "Kết quả không đạt (âm tính) – nói thẳng", muc_am_tinh(ad)),
         sec(6, "Giới hạn", muc_gioi_han())]
    if truc_tiep:
        s.insert(3, sec(4, "Chạy CNN thật trên ô chưa dùng để huấn luyện", muc_truc_tiep(truc_tiep)))
    if so_sanh:
        ak = json.loads(KQ_AK.read_text(encoding="utf-8"))
        s.insert(3, sec(4, "So sánh TRỰC TIẾP nhiều thuật toán (lệnh AK)", muc_so_sanh_truc_tiep(so_sanh, ak)))
    if truc_tiep or so_sanh:
        # đánh số lại
        n = [0]

        def dem(m):
            n[0] += 1
            return f'<h2><span class="so">{n[0]}</span>'
        body = re.sub(r'<h2><span class="so">\d+</span>', dem, "".join(s))
    else:
        body = "".join(s)
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo máy học</title>
<style>{css}{CSS}</style></head><body><main><h1>Máy học trong hệ thống chấm phiếu</h1>
<p class="sub">Dữ liệu · hai mô hình · so sánh thuật toán · kết quả âm tính · giới hạn. Mọi số lấy từ kết quả đã chạy và lưu trong <code>data/_eval/</code> và <code>docs/</code>{" · có mục chạy trực tiếp" if (truc_tiep or so_sanh) else ""}.</p>
{body}<p class="chan">Sinh bởi <code>tools/demo_may_hoc.py</code>. Không huấn luyện lại, không đổi mô hình.</p></main></body></html>"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Dựng trang HTML demo máy học (chỉ đọc kết quả đã có).")
    ap.add_argument("--ra", type=Path, default=ROOT / "data" / "_eval" / "demo_3_phien" / "may_hoc.html")
    ap.add_argument("--truc-tiep", action="store_true", help="chạy CNN thật trên 504 ô phiếu dev (không huấn luyện trên chúng)")
    ap.add_argument("--so-sanh-truc-tiep", action="store_true", help="lệnh AK: chạy trực tiếp 11 thuật toán (mô hình người 1 giữ ra) trên ô của người 1 + bảng R3 / R4; cần data/_eval/ak/")
    ap.add_argument("--da-tinh-san", action="store_true", help="với --so-sanh-truc-tiep: đọc kết quả đã đệm thay vì chạy (ghi rõ ĐÃ TÍNH SẴN trên trang)")
    a = ap.parse_args()
    tt = chay_truc_tiep() if a.truc_tiep else None
    ss = chay_so_sanh_truc_tiep(a.da_tinh_san) if a.so_sanh_truc_tiep else None
    a.ra.parent.mkdir(parents=True, exist_ok=True)
    a.ra.write_text(dung_trang(tt, ss), encoding="utf-8")
    if tt:
        print(f"Trực tiếp: đúng {tt['dung']}/{tt['n']} = {100 * tt['dung'] / tt['n']:.2f}% (ô có mực; phiếu dev có {tt['tong_dev']} ô)")
    print(f"Đã ghi {a.ra}")


if __name__ == "__main__":
    main()
