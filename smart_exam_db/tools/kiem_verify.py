"""
kiem_verify.py - Ảnh giả lỗi cố ý + khảo sát ngưỡng cho verify() (Tuần 4, Bước 4 – docs/ke_hoach_tuan4.md).

Ảnh giả CHỈ tạo từ ảnh dev (0001–0034, D001–D010); không đọc ảnh test 0035–0040. Mỗi ảnh giả có phép biến đổi
H biết trước (toạ độ ảnh nguồn -> ảnh giả) và KẾT QUẢ MONG ĐỢI chốt TRƯỚC khi chạy verify():
  - ok_hoac : ok như trên, HOẶC từ chối với mã thuộc tập mong đợi (không bao giờ được trả ảnh nắn sai).
  - ok      : phải trả ảnh nắn; 4 tâm marker trả về khớp H · (tâm marker v3_hinh_hoc của ảnh nguồn) và huong_xoay đúng.
  - tu_choi : phải từ chối với mã thuộc tập mong đợi. Nhóm khong_du_marker = {thieu_marker, marker_khong_dat}.
Tâm marker của ảnh nguồn lấy từ data/_eval/v3_hinh_hoc/diem_dev.csv: cả 78 ảnh dev v3 nắn đúng VÀ đúng chiều
(phép 2 bắt được xoay 180°, cộng xem bằng mắt) ⇒ thứ tự TL, TR, BR, BL ở đó là góc thật của trang.

huong_xoay = góc phiếu bị xoay trong ảnh (chiều kim đồng hồ, bội 90°), tính từ vectơ TL -> TR: 0 = đầu trang ở trên.

Chạy (từ thư mục smart_exam_db/):
  python tools/kiem_verify.py tao-gia     # -> data/_eval/_gia_v4/*.jpg, danh_sach.csv, ghep_*.jpg
  python tools/kiem_verify.py khao-sat    # -> data/_eval/v4_verify/khao_sat_dev.csv, khao_sat_mo.csv (dừng B)
Chỉ ghi vào data/_eval/_gia_v4/ và data/_eval/v4_verify/, không đụng data/raw/, data/raw_digits/.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_preprocessing import ANSWER_SHEET, EVAL_DIR, doc_nhan_o, list_images, render_pdf_page  # noqa: E402
from check_labels import SEARCH_MM, item_box, local_darkness, register  # noqa: E402
import cv_engine.preprocessing as pp  # noqa: E402
from cv_engine.preprocessing import GOC, load_image  # noqa: E402

GIA = EVAL_DIR / "_gia_v4"
FONT = ANSWER_SHEET / "fonts" / "DejaVuSans.ttf"
NHOM = {"khong_du_marker": ["thieu_marker", "marker_khong_dat"]}
NEN_BAN = 95                # nền bàn xám như ảnh giả của 3c (marker_that.anh_gia)
MM = 300 / 25.4             # px layout / mm


def nap_layout(loai: str) -> dict:
    ten = "layout.json" if loai == "phieu" else "digit_sheet_layout.json"
    return json.loads((ANSWER_SHEET / "output" / ten).read_text(encoding="utf-8"))


def tam_v3() -> dict[str, np.ndarray]:
    """4 tâm marker (TL, TR, BR, BL thật của trang) do v3_hinh_hoc chọn trên ảnh dev."""
    out = {}
    for r in csv.DictReader((EVAL_DIR / "v3_hinh_hoc" / "diem_dev.csv").open(encoding="utf-8-sig")):
        if r["tra_anh"] == "co":
            out[r["anh"]] = np.array([[float(r[f"marker_{g}_{c}"]) for c in "xy"] for g in GOC])
    return out


def huong(tam: np.ndarray) -> int:
    dx, dy = tam[1] - tam[0]
    return int(round(np.degrees(np.arctan2(dy, dx)) / 90.0)) % 4 * 90


def phoi_canh(t: np.ndarray) -> float:
    """Độ phối cảnh của 4 tâm (như K2 của 3c): min(trên/dưới, trái/phải và nghịch đảo)."""
    d = lambda i, j: float(np.hypot(*(t[i] - t[j])))
    tl = [d(0, 1) / d(3, 2), d(0, 3) / d(1, 2)]
    return min(min(r, 1 / r) for r in tl)


def bien_doi(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(np.asarray(pts, np.float64)[None], H)[0]


class Nguon:
    """Ảnh dev nguồn: ảnh xám + tâm marker v3 + H_L (toạ độ layout -> ảnh)."""

    def __init__(self, ten: str, duong_dan: Path, loai: str, tam: np.ndarray):
        self.ten, self.loai, self.tam = ten, loai, tam
        self.gray = load_image(duong_dan)
        self.layout = nap_layout(loai)
        tam_L = np.array([self.layout["markers"]["centers"][g] for g in GOC], np.float32)
        self.H_L = cv2.getPerspectiveTransform(tam_L, tam.astype(np.float32))

    def o_vuong(self, goc: int, nua_mm: float) -> np.ndarray:
        """Đa giác trên ảnh của ô vuông cạnh 2·nua_mm (mm) quanh tâm marker góc `goc` (0..3 = TL, TR, BR, BL)."""
        c = np.array(self.layout["markers"]["centers"][GOC[goc]])
        h = nua_mm * MM
        return bien_doi(self.H_L, c + np.array([[-h, -h], [h, -h], [h, h], [-h, h]]))

    def trang(self, H_them=np.eye(3)) -> np.ndarray:
        """Đa giác mép giấy (cả trang) trên ảnh, sau phép H_them."""
        w, h = self.layout["page_px"]
        return bien_doi(H_them @ self.H_L, [[0, 0], [w, 0], [w, h], [0, h]])


# ============================================================================ các phép tạo ảnh giả
def H_xoay(k: int, shape) -> tuple[np.ndarray, int]:
    """Xoay k·90° THEO chiều kim đồng hồ: (H nguồn -> giả, mã cv2.rotate)."""
    h, w = shape
    if k == 1:
        return np.array([[0, -1, h - 1], [1, 0, 0], [0, 0, 1]], float), cv2.ROTATE_90_CLOCKWISE
    if k == 2:
        return np.array([[-1, 0, w - 1], [0, -1, h - 1], [0, 0, 1]], float), cv2.ROTATE_180
    return np.array([[0, 1, 0], [-1, 0, w - 1], [0, 0, 1]], float), cv2.ROTATE_90_COUNTERCLOCKWISE


def T(dx, dy, s=1.0) -> np.ndarray:
    return np.array([[s, 0, dx], [0, s, dy], [0, 0, 1]], float)


def nen_ban(shape, rng) -> np.ndarray:
    return np.clip(NEN_BAN + rng.normal(0, 4, shape), 0, 255).astype(np.float32)


def dan(canvas: np.ndarray, src: np.ndarray, H: np.ndarray, mat_na_src: np.ndarray | None = None) -> np.ndarray:
    """Dán src (biến đổi H) lên canvas; chỉ phần mat_na_src > 0 (mặc định cả ảnh)."""
    h, w = canvas.shape
    anh = cv2.warpPerspective(src.astype(np.float32), H, (w, h), flags=cv2.INTER_LINEAR)
    m = mat_na_src if mat_na_src is not None else np.full(src.shape, 255, np.uint8)
    mw = cv2.warpPerspective(m, H, (w, h), flags=cv2.INTER_NEAREST)
    return np.where(mw > 0, anh, canvas)


def nen_giay_quanh(gray: np.ndarray, poly: np.ndarray) -> float:
    """Độ sáng giấy quanh một đa giác: trung vị vành rộng ~ nửa cạnh đa giác bên ngoài nó."""
    m = np.zeros(gray.shape, np.uint8)
    cv2.fillPoly(m, [poly.astype(np.int32)], 1)
    k = int(np.ptp(poly[:, 0]) * 0.5) | 1
    vanh = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))) - m
    return float(np.median(gray[vanh > 0]))


def mo_chuyen_dong(gray: np.ndarray, dai: int, goc_do: float = 0) -> np.ndarray:
    """Mờ chuyển động thẳng dài `dai` px (ảnh gốc) theo hướng goc_do (0 = ngang). goc_do = 0 giữ đúng nhân cũ
    (ảnh giả cũ tái tạo từng byte)."""
    if goc_do == 0:
        k = np.zeros((dai, dai), np.float32)
        k[dai // 2, :] = 1.0 / dai
    else:
        n = dai + 2 | 1
        k = np.zeros((n, n), np.float32)
        c, h = n // 2, (dai - 1) / 2
        dx, dy = h * np.cos(np.radians(goc_do)), h * np.sin(np.radians(goc_do))
        cv2.line(k, (round((c - dx) * 16), round((c - dy) * 16)), (round((c + dx) * 16), round((c + dy) * 16)), 1.0,
                 1, cv2.LINE_AA, shift=4)
        k /= k.sum()
    return cv2.filter2D(gray, -1, k, borderType=cv2.BORDER_REPLICATE)


def vet_muc(gray: np.ndarray, tam) -> tuple[np.ndarray, np.ndarray]:
    """(ys, xs) điểm ảnh của vết mực chứa tâm marker `tam` – mặt nạ mực cùng ngưỡng với preprocessing
    (xám / nền giấy cục bộ < MUC_TI_LE, nối 8 hướng)."""
    muc = (gray.astype(np.float32) / np.maximum(pp.uoc_luong_nen(gray), 1.0) < pp.MUC_TI_LE).astype(np.uint8)
    _, lab = cv2.connectedComponents(muc, connectivity=8)
    i = lab[int(round(tam[1])), int(round(tam[0]))]
    if i == 0:
        sys.exit(f"LỖI: tâm marker ({tam[0]:.0f}, {tam[1]:.0f}) không nằm trên mực")
    return np.nonzero(lab == i)


def mep_vet_muc(gray: np.ndarray, tam) -> dict:
    """Khoảng cách (px) từ vết mực của marker tới 4 mép ảnh; 0 = chạm mép."""
    ys, xs = vet_muc(gray, tam)
    H, W = gray.shape
    return {"tren": int(ys.min()), "duoi": int(H - 1 - ys.max()), "trai": int(xs.min()), "phai": int(W - 1 - xs.max())}


def tim_nghieng(n: Nguon, muc_tieu: float) -> np.ndarray:
    """H làm ảnh 'quá nghiêng': cạnh trên của ảnh co lại t lần (giữa), chiều cao còn 0,85; chọn t (chia đôi) để độ
    phối cảnh của 4 tâm marker = muc_tieu."""
    h, w = n.gray.shape
    goc = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    def H_t(t):
        y0 = 0.15 * h
        return cv2.getPerspectiveTransform(goc, np.float32([[w * (1 - t) / 2, y0], [w * (1 + t) / 2, y0], [w, h], [0, h]]))

    lo, hi = 0.05, 1.0
    for _ in range(50):
        t = (lo + hi) / 2
        if phoi_canh(bien_doi(H_t(t), n.tam)) < muc_tieu:
            lo = t
        else:
            hi = t
    return H_t((lo + hi) / 2)


# ============================================================================ lệnh tao-gia
def cmd_tao_gia(a) -> None:
    GIA.mkdir(parents=True, exist_ok=True)
    anh_dev = {x.ten: x for x in list_images("dev")}
    tam = tam_v3()
    ns = {t: Nguon(t, anh_dev[t].duong_dan, anh_dev[t].loai, tam[t])
          for t in ("0001_C1", "0005_C2", "0015_C3", "0008_C4", "D003", "0006_C2")}
    rows, anh_ghep = [], []

    def ghi(ten, nhom, img, nguon, bien_the, mong, H=None, ly_do=(), layout=None, ghi_chu=""):
        """mong = 'ok' (tâm + hướng mong đợi tính từ H và nguồn) hoặc 'tu_choi' (ly_do = tập mã chấp nhận)."""
        img = np.clip(img, 0, 255).astype(np.uint8)
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        buf.tofile(GIA / f"{ten}.jpg")
        n = ns.get(nguon.split("+")[0])
        tam_md, huong_md = "", ""
        if mong in ("ok", "ok_hoac"):
            t = bien_doi(H, n.tam)
            tam_md, huong_md = json.dumps(np.round(t, 2).tolist()), huong(t)
        rows.append({"ten": ten, "nhom": nhom, "nguon": nguon, "bien_the": bien_the,
                     "layout": layout or (n.loai if n else "phieu"), "mong_doi": mong, "huong_mong_doi": huong_md,
                     "ly_do_mong_doi": "|".join(ly_do), "tam_mong_doi": tam_md,
                     "H": json.dumps(np.round(H, 6).tolist()) if H is not None else "",
                     "rong": img.shape[1], "cao": img.shape[0], "ghi_chu": ghi_chu})
        anh_ghep.append((ten, img, mong, huong_md, "|".join(ly_do), tam_md))
        print(f"  {ten:28s} {mong:8s} {huong_md if mong == 'ok' else '|'.join(ly_do)}")

    KDM = ("khong_du_marker",)
    phieu4 = ("0001_C1", "0005_C2", "0015_C3", "0008_C4")
    nguon5 = phieu4 + ("D003",)

    # 1. Xoay 90 / 180 / 270 (theo chiều kim đồng hồ, không mất dữ liệu) – 6 nguồn
    print("1. xoay")
    for t, n in ns.items():
        for k in (1, 2, 3):
            H, ma = H_xoay(k, n.gray.shape)
            ghi(f"xoay{90 * k}_{t}", "xoay", cv2.rotate(n.gray, ma), t, f"{90 * k}°", "ok", H)

    # 2. Che 1 marker: màu giấy cục bộ / đĩa tối Ø20 mm (tròn -> không còn là tứ giác) – 5 nguồn, đổi góc
    print("2. che marker")
    for i, t in enumerate(nguon5):
        n = ns[t]
        goc = i % 4
        o_che = n.o_vuong(goc, 7.0)                          # che ô 14 mm quanh marker 8 mm
        img = n.gray.copy()
        cv2.fillPoly(img, [o_che.astype(np.int32)], int(nen_giay_quanh(n.gray, o_che)))
        ghi(f"che_giay_{GOC[goc]}_{t}", "che_marker", img, t, f"che {GOC[goc]} màu giấy", "tu_choi", ly_do=KDM)
        c = n.layout["markers"]["centers"][GOC[goc]]
        vong = bien_doi(n.H_L, [[c[0] + 10 * MM * np.cos(f), c[1] + 10 * MM * np.sin(f)]
                                for f in np.linspace(0, 2 * np.pi, 72, endpoint=False)])
        m = np.zeros(n.gray.shape, np.uint8)
        cv2.fillPoly(m, [vong.astype(np.int32)], 255)
        m = cv2.GaussianBlur(m, (31, 31), 0).astype(np.float32) / 255
        img = n.gray * (1 - m) + 0.45 * nen_giay_quanh(n.gray, o_che) * m
        ghi(f"che_toi_{GOC[goc]}_{t}", "che_marker", img, t, f"đĩa tối Ø20 mm che {GOC[goc]}", "tu_choi", ly_do=KDM)

    # 3. Khung hình cắt qua 1 marker (cắt thẳng theo trục ảnh) + đối chứng cắt lề – 3 nguồn.
    #    Tờ gần thẳng trục ảnh ⇒ đường cắt qua 1 marker cũng sượt marker cùng cạnh. Xoay ảnh nguồn ±5° trước (như cầm
    #    máy hơi lệch; thu 0,88 để 4 góc không ra ngoài khung) để marker cần cắt nhô ra ~16 mm so với marker kia; chọn chiều xoay để 3 marker còn lại nguyên vẹn.
    print("3. cắt qua marker")

    def cat(R, goc, canh, f, h, w):
        """(c, H cắt, cỡ ảnh sau cắt) – cắt theo cạnh `canh` qua marker `goc` (sau phép xoay R) mức f."""
        o = bien_doi(R, n.o_vuong(goc, 4.0))
        (x0, y0), (x1, y1) = o.min(0), o.max(0)
        if canh == "phai":
            c = int(x1) - 2 if f is None else (int(x0) - 20 if f == "het" else int(round(x1 - f * (x1 - x0))))
            return (slice(None), slice(None, c)), T(0, 0) @ R, (h, c)
        if canh == "tren":
            c = int(np.ceil(y0)) + 2 if f is None else (int(y1) + 20 if f == "het" else int(round(y0 + f * (y1 - y0))))
            return (slice(c, None), slice(None)), T(0, -c) @ R, (h - c, w)
        c = int(y1) - 2 if f is None else (int(y0) - 20 if f == "het" else int(round(y1 - f * (y1 - y0))))
        return (slice(None, c), slice(None)), T(0, 0) @ R, (c, w)

    def nguyen_ven(H, goc, co) -> bool:
        """3 marker còn lại nguyên vẹn, cách mép ảnh ≥ 1 mm (ô 10 mm quanh tâm nằm trong ảnh)."""
        for g in range(4):
            if g != goc:
                q = bien_doi(H, n.o_vuong(g, 5.0))
                if q.min() < 0 or (q[:, 0] >= co[1]).any() or (q[:, 1] >= co[0]).any():
                    return False
        return True

    MUC = (("2px", None), ("25", 0.25), ("50", 0.5), ("75", 0.75), ("het", "het"))
    CAT_MUC = {}                # nguồn -> (R, góc, cạnh, ảnh đã xoay) cho nhóm 13 (cắt theo MỰC)
    for t, goc, canh in (("0001_C1", 2, "phai"), ("0015_C3", 1, "tren"), ("D003", 3, "duoi")):
        n = ns[t]
        h, w = n.gray.shape
        for goc_do in (5, -5):
            R = np.vstack([cv2.getRotationMatrix2D((w / 2, h / 2), goc_do, 0.88), [0, 0, 1]])
            if all(nguyen_ven(cat(R, goc, canh, f, h, w)[1], goc, cat(R, goc, canh, f, h, w)[2]) for _, f in MUC):
                break
        else:
            sys.exit(f"LỖI: {t} – không chiều xoay ±5° nào cắt được {GOC[goc]} mà giữ nguyên 3 marker kia")
        xoay = cv2.warpAffine(n.gray, R[:2], (w, h), flags=cv2.INTER_LINEAR, borderValue=NEN_BAN)
        for nhan, f in MUC:
            sl, H, _ = cat(R, goc, canh, f, h, w)
            img = xoay[sl]
            mong, ghi_chu = "tu_choi", ""
            if f == "het":
                ld = KDM
            elif f == 0.75:
                ld = ("marker_cham_mep",) + KDM
            else:
                ld = ("marker_cham_mep",)
            if f is None:
                # Mức "2px" cắt 2 px qua ĐỈNH ô 8 mm dự đoán từ H, không đo trên mực. Sửa ca thử thiết kế sai (dừng C,
                # 06/10/2026, có bằng chứng): đo mặt nạ mực của marker trên ảnh đã cắt; mực KHÔNG chạm mép (≥ 1 px) ⇒
                # marker thực chất còn nguyên ⇒ mong đợi "ok hoặc marker_cham_mep". Mực chạm mép (0 px) ⇒ giữ nghiêm.
                kc = mep_vet_muc(img, bien_doi(H, n.tam)[goc])[canh]
                if kc >= 1:
                    mong, ghi_chu = "ok_hoac", f"mực marker cách mép {kc} px (không chạm) – sửa ca thử thiết kế sai"
                else:
                    ghi_chu = "mực marker chạm mép (0 px)"
            ghi(f"cat_{nhan}_{GOC[goc]}_{t}", "cat_marker", img, t, f"xoay {goc_do}°, cắt {canh} qua {GOC[goc]}: {nhan}",
                mong, H, ly_do=ld, ghi_chu=ghi_chu)
        CAT_MUC[t] = (R, goc, canh, xoay)
        # đối chứng: cắt lề, chừa ≥ 5 mm giấy quanh mọi marker (ô 18 mm quanh tâm)
        hop = np.vstack([n.o_vuong(g, 9.0) for g in range(4)])
        cx0, cy0 = np.floor(hop.min(0)).astype(int).clip(0)
        cx1, cy1 = np.ceil(hop.max(0)).astype(int)
        cx1, cy1 = min(cx1, w), min(cy1, h)
        ghi(f"cat_le_{t}", "cat_le", n.gray[cy0:cy1, cx0:cx1], t, "cắt lề, chừa 5 mm quanh marker", "ok",
            T(-cx0, -cy0))

    # 4. Hai tờ trên một ảnh (ảnh ngang 4032×3024, mỗi tờ thu 0,5)
    print("4. hai tờ")
    for i, (t1, t2, g1, g2) in enumerate((("0001_C1", "0008_C4", 0, 0), ("0001_C1", "D003", 0, 0),
                                          ("0005_C2", "0008_C4", 5, -5))):
        rng = np.random.default_rng(100 + i)
        canvas = nen_ban((3024, 4032), rng)
        Hs = []
        for t, goc_do, cx in ((t1, g1, 1008), (t2, g2, 3024)):
            h, w = ns[t].gray.shape
            R = cv2.getRotationMatrix2D((w / 2, h / 2), -goc_do, 0.5)
            R[:, 2] += (cx - w / 2, 1512 - h / 2)
            H = np.vstack([R, [0, 0, 1]])
            canvas = dan(canvas, ns[t].gray, H)
            Hs.append(H)
        ghi(f"hai_to_{i + 1}_{t1}+{t2}", "hai_to", canvas, f"{t1}+{t2}", f"xoay {g1}°/{g2}°", "tu_choi", Hs[0],
            ly_do=("nhieu_phieu",))

    # 5. Tờ khác lọt khung: tờ chính thu 0,8 giữa nền bàn; góc dưới-phải của tờ khác đặt cùng mặt phẳng,
    #    marker BR của nó cách marker TL tờ chính d mm theo mỗi trục (ra ngoài). Mong đợi ok (chấp nhận marker_mo_ho).
    print("5. tờ khác lọt khung")
    for i, (tc, tk, d, sat) in enumerate((("0001_C1", "0008_C4", 30, False), ("0001_C1", "0008_C4", 22, False),
                                          ("0001_C1", "0008_C4", 19, False), ("0015_C3", "0005_C2", 10, True))):
        rng = np.random.default_rng(200 + i)
        c, k = ns[tc], ns[tk]
        h, w = c.gray.shape
        S = T(w * 0.1, h * 0.1, 0.8)
        canvas = dan(nen_ban((h, w), rng), c.gray, S)
        ctl, kbr = c.layout["markers"]["centers"]["tl"], k.layout["markers"]["centers"]["br"]
        dich = T(ctl[0] - d * MM - kbr[0], ctl[1] - d * MM - kbr[1])      # layout tờ khác -> layout tờ chính
        H_k = S @ c.H_L @ dich @ np.linalg.inv(k.H_L)                     # ảnh tờ khác -> canvas
        pw, ph = k.layout["page_px"]
        x_het = kbr[0] + (6 * MM if sat else 99999)                       # 'đè sát': không có lề giấy ngoài marker
        y_het = kbr[1] + (6 * MM if sat else 99999)
        vung = bien_doi(k.H_L, [[pw * 0.7, ph * 0.8], [min(pw, x_het), ph * 0.8], [min(pw, x_het), min(ph, y_het)],
                                [pw * 0.7, min(ph, y_het)]])
        m = np.zeros(k.gray.shape, np.uint8)
        cv2.fillPoly(m, [vung.astype(np.int32)], 255)
        canvas = dan(canvas, k.gray, H_k, m)
        ghi(f"lot_khung_{d}mm{'_sat' if sat else ''}_{tc}", "lot_khung", canvas, f"{tc}+{tk}",
            f"góc BR tờ {tk} cách TL {d} mm/trục{' (không lề)' if sat else ''}", "ok_hoac", S,
            ly_do=("marker_mo_ho",), ghi_chu="KHÔNG được chọn marker tờ khác")

    # 6. Mờ Gauss / chuyển động (σ, độ dài: px trên ẢNH GỐC). Tập chấp nhận chốt ở dừng B (06/10/2026) theo
    #    `khao-sat` (mo_huong vs hậu quả filled/faint − blank; ngưỡng anh_mo 0,012 là ngưỡng TẠM, thận trọng)
    print("6. mờ")
    for t in nguon5:
        n = ns[t]
        for s in (1, 2, 3, 5, 8):
            mong, ld = ("ok", ()) if s <= 2 else (("ok_hoac", ("anh_mo",)) if s <= 3 else ("tu_choi", ("anh_mo",) + KDM))
            ghi(f"mo_gauss{s}_{t}", "mo", cv2.GaussianBlur(n.gray, (0, 0), s), t, f"Gauss σ = {s} px", mong, T(0, 0),
                ly_do=ld)
        for dai in (15, 30):
            mong = "ok_hoac" if dai == 15 else "tu_choi"
            ghi(f"mo_dong{dai}_{t}", "mo", mo_chuyen_dong(n.gray, dai), t, f"chuyển động ngang {dai} px", mong, T(0, 0),
                ly_do=("anh_mo",))

    # 7. Nhầm loại trang (ảnh giữ nguyên, chấm với layout của loại kia)
    print("7. nhầm loại trang")
    ghi("nham_loai_D003", "nham_loai", ns["D003"].gray, "D003", "trang D chấm theo layout phiếu", "tu_choi",
        layout="phieu", ly_do=("khong_khop_bo_cuc",))
    ghi("nham_loai_0001_C1", "nham_loai", ns["0001_C1"].gray, "0001_C1", "phiếu chấm theo layout trang D",
        "tu_choi", layout="chu_so", ly_do=("khong_khop_bo_cuc",))

    # 8. Tối + nhiễu (đối chứng: nhiễu không được làm từ chối / lọt anh_mo)
    print("8. tối + nhiễu")
    for i, t in enumerate(("0001_C1", "0008_C4")):
        rng = np.random.default_rng(300 + i)
        ghi(f"toi_nhieu_{t}", "toi_nhieu", ns[t].gray * 0.4 + rng.normal(0, 8, ns[t].gray.shape), t,
            "sáng × 0,4, nhiễu σ 8", "ok", T(0, 0))

    # 9. Quá nghiêng: độ phối cảnh 4 tâm ~0,45 / ~0,40 (< K2 0,50)
    print("9. quá nghiêng")
    for t in ("0001_C1", "0008_C4"):
        n = ns[t]
        for pc in (0.45, 0.40):
            H = tim_nghieng(n, pc)
            img = cv2.warpPerspective(n.gray, H, n.gray.shape[::-1], borderValue=NEN_BAN)
            ghi(f"qua_nghieng_{int(pc * 100)}_{t}", "qua_nghieng", img, t,
                f"độ phối cảnh {phoi_canh(bien_doi(H, n.tam)):.3f}", "tu_choi", H, ly_do=KDM)

    # 10. Không có phiếu: mặt bàn (dải nền phía trên tờ ở ảnh C3) / giấy trắng (lõi trang, xoá nét in bằng median)
    print("10. không có phiếu")
    dai = []
    for x in anh_dev.values():
        if x.dieu_kien == "C3" and x.ten in tam:
            n0 = Nguon(x.ten, x.duong_dan, x.loai, tam[x.ten])
            y_tren = int(n0.trang()[:, 1].min()) - 40
            dai.append((y_tren, x.ten, n0))
    for y_tren, t, n0 in sorted(dai, reverse=True)[:2]:
        if y_tren < 300:
            print(f"  (bỏ {t}: dải nền chỉ cao {y_tren} px)")
            continue
        ghi(f"khong_phieu_ban_{t}", "khong_phieu", n0.gray[:y_tren, :], t, f"dải nền trên tờ, cao {y_tren} px",
            "tu_choi", ly_do=("thieu_marker",) + KDM)
    for i, t in enumerate(("0005_C2", "0008_C4")):
        n = ns[t]
        rng = np.random.default_rng(400 + i)
        loi = bien_doi(n.H_L, [[300, 1700], [2180, 1700], [2180, 3200], [300, 3200]])
        x0, y0 = loi.min(0).astype(int)
        x1, y1 = loi.max(0).astype(int)
        nho = cv2.resize(n.gray[y0:y1, x0:x1], None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
        trang = cv2.medianBlur(cv2.medianBlur(nho, 41), 41)                # xoá ô tròn 5 mm / chữ, giữ độ sáng nền
        trang = cv2.resize(trang, (3024, 4032), interpolation=cv2.INTER_CUBIC) + rng.normal(0, 3, (4032, 3024))
        ghi(f"khong_phieu_giay_{t}", "khong_phieu", trang, t, "giấy trắng (lõi trang, median xoá nét)", "tu_choi",
            ly_do=("thieu_marker",) + KDM)

    # 11. Mờ chuyển động chéo 45° (thêm ở dừng B) – mo_huong lấy min của ∂²/∂x², ∂²/∂y²: hướng chéo làm nhoè cả hai
    print("11. mờ chuyển động chéo")
    for t in ("0001_C1", "0015_C3", "D003"):
        for dai in (15, 30):
            mong = "ok_hoac" if dai == 15 else "tu_choi"
            ghi(f"mo_cheo{dai}_{t}", "mo", mo_chuyen_dong(ns[t].gray, dai, 45), t, f"chuyển động chéo 45° {dai} px",
                mong, T(0, 0), ly_do=("anh_mo",))

    # 12. Mờ + tối + nhiễu: nhiễu làm tăng phương sai đạo hàm bậc hai – không được làm ảnh mờ lọt qua anh_mo
    print("12. mờ + tối + nhiễu")
    for i, t in enumerate(("0001_C1", "0008_C4")):
        rng = np.random.default_rng(500 + i)
        g = cv2.GaussianBlur(ns[t].gray, (0, 0), 5).astype(np.float32) * 0.4 + rng.normal(0, 8, ns[t].gray.shape)
        ghi(f"mo_toi_nhieu_{t}", "mo", g, t, "Gauss σ 5 + sáng × 0,4 + nhiễu σ 8", "tu_choi", T(0, 0),
            ly_do=("anh_mo",) + KDM)

    # 13. Cắt theo MỰC (thêm ở dừng C): mép ảnh đi vào phần mực của marker đúng 2 px, đo trên mặt nạ mực của ảnh đã
    #     xoay (cùng ngưỡng mực với preprocessing); kiểm lại trên ảnh đã cắt: mực phải chạm mép (0 px)
    print("13. cắt theo mực 2 px")
    for t, (R, goc, canh, xoay) in CAT_MUC.items():
        n = ns[t]
        h, w = xoay.shape
        ys, xs = vet_muc(xoay, bien_doi(R, n.tam)[goc])
        if canh == "phai":
            c = int(xs.max()) - 1                    # bỏ 2 cột mực ngoài cùng (xmax − 1, xmax)
            img, H = xoay[:, :c], R
        elif canh == "tren":
            c = int(ys.min()) + 2                    # bỏ 2 hàng mực trên cùng
            img, H = xoay[c:, :], T(0, -c) @ R
        else:
            c = int(ys.max()) - 1
            img, H = xoay[:c, :], R
        kc = mep_vet_muc(img, bien_doi(H, n.tam)[goc])[canh]
        if kc != 0:
            sys.exit(f"LỖI: cat_muc_2px {t} – mực marker không chạm mép sau khi cắt ({kc} px)")
        ghi(f"cat_muc_2px_{GOC[goc]}_{t}", "cat_marker", img, t, f"cắt {canh} vào mực marker {GOC[goc]} 2 px",
            "tu_choi", H, ly_do=("marker_cham_mep",), ghi_chu="mực marker chạm mép (0 px), đã cắt 2 px mực")

    # ---- ghi danh_sach.csv + ảnh ghép
    with (GIA / "danh_sach.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    so = viet_ghep(anh_ghep)
    from collections import Counter
    print(f"\nĐã ghi {len(rows)} ảnh giả + danh_sach.csv + {so} ảnh ghép vào {GIA}")
    print("Theo nhóm:", dict(Counter(r["nhom"] for r in rows)))
    print("Theo mong đợi:", dict(Counter(r["mong_doi"] for r in rows)))


def viet_ghep(anh_ghep: list, cot=6, rong=300, moi_trang=36) -> int:
    """Ảnh ghép xem nhanh: thu nhỏ, vẽ tứ giác 4 tâm mong đợi (xanh, chấm đỏ = TL), chú thích mong đợi."""
    font = ImageFont.truetype(str(FONT), 13)
    o_cao = 470
    so_trang = 0
    for p in range(0, len(anh_ghep), moi_trang):
        phan = anh_ghep[p:p + moi_trang]
        hang = (len(phan) + cot - 1) // cot
        tong = Image.new("RGB", (cot * rong, hang * o_cao), "white")
        ve = ImageDraw.Draw(tong)
        for i, (ten, img, mong, huong_md, ld, tam_md) in enumerate(phan):
            s = min(rong / img.shape[1], (o_cao - 60) / img.shape[0])
            nho = cv2.cvtColor(cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
            if tam_md:
                t = (np.array(json.loads(tam_md)) * s).astype(np.int32)
                cv2.polylines(nho, [t.reshape(-1, 1, 2)], True, (0, 200, 0), 2)
                cv2.circle(nho, tuple(int(v) for v in t[0]), 6, (0, 0, 255), -1)
            x, y = (i % cot) * rong, (i // cot) * o_cao
            tong.paste(Image.fromarray(cv2.cvtColor(nho, cv2.COLOR_BGR2RGB)), (x, y))
            mo_ta = {"ok": f"ok, hướng {huong_md}°", "ok_hoac": f"ok {huong_md}° hoặc " + ld.replace("|", " / ")}.get(
                mong, "từ chối: " + ld.replace("|", " / "))
            ve.text((x + 3, y + o_cao - 56), ten, fill="black", font=font)
            ve.text((x + 3, y + o_cao - 38), mo_ta[:44], fill={"ok": "darkgreen", "ok_hoac": "darkorange"}.get(mong, "darkred"), font=font)
            if len(mo_ta) > 44:
                ve.text((x + 3, y + o_cao - 20), mo_ta[44:88], fill="darkred", font=font)
        so_trang += 1
        tong.save(GIA / f"ghep_{so_trang}.jpg", quality=85)
    return so_trang


# ============================================================================ lệnh khao-sat (dừng B)
KS = EVAL_DIR / "v4_verify"
TRUNG_PX = 30               # phần tử phiếu mà sau xoay 180° rơi trong 30 px một phần tử khác (32/250)
GAUSS = (0, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 32)   # mức mờ (px trên ảnh gốc) – mịn hơn ảnh giả,
                            # kéo tới khi faint/blank gãy (lần chạy đầu tới σ 8 vẫn tách hết)
DONG = (10, 15, 20, 25, 30, 40, 60, 80, 120)


def phan_tu_trung(layout: dict) -> np.ndarray:
    """Mặt nạ (theo thứ tự của phan_tu_bo_cuc) các phần tử mà ảnh lật 180° của chúng rơi gần một phần tử khác."""
    W, H = layout["page_px"]
    tam = np.vstack([t for _, t in pp.phan_tu_bo_cuc(layout)])
    xoay = np.array([W - 1, H - 1]) - tam
    return np.linalg.norm(xoay[:, None] - tam[None], axis=2).min(1) <= TRUNG_PX


def hieu_nhan(anh_nan, layout, nhan: dict, phieu_trang=None) -> dict:
    """Theo nhãn (như phép 3 / dung-sai, CHỈ để chọn ngưỡng anh_mo – verify không gọi): mỗi hàng câu / cột chữ số,
    hiệu filled = min(filled) − max(blank), hiệu faint = min(faint) − max(blank) (local_darkness). phieu_trang ->
    dò lại từng hàng / khối ±4 mm (cách OMR Tuần 5 sẽ đọc); None -> đọc tại toạ độ layout."""
    ans = layout["answers"]
    nhom = [(("q", q), [ans["centers"][str(q)][o] for o in ans["options"]], ans["bubble_radius"],
             [nhan[(str(q), o)] for o in ans["options"]]) for q in range(1, ans["num_questions"] + 1)]
    for f in ("sbd", "exam_code"):
        for c, col in enumerate(layout[f]["bubbles"]):
            nhom.append(((f, 0), col, layout[f]["bubble_radius"], [nhan[(f"{f}{c + 1}", str(k))] for k in range(10)]))
    dich = {}
    if phieu_trang is not None:
        search = round(SEARCH_MM * layout["dpi"] / 25.4)
        dich = {it: register(anh_nan, phieu_trang, item_box(layout, it), search) for it in {g[0] for g in nhom}}
    h = {"filled": [], "faint": []}
    for it, tam, r, labs in nhom:
        if "blank" not in labs:
            continue
        sx, sy = dich.get(it, (0, 0))
        d = [local_darkness(anh_nan, cx + sx, cy + sy, r) for cx, cy in tam]
        nen = max(v for v, l in zip(d, labs) if l == "blank")
        for lop in h:
            if lop in labs:
                h[lop].append(min(v for v, l in zip(d, labs) if l == lop) - nen)
    return {f"{lop}_{k}": v for lop in h for k, v in (("so", len(h[lop])),
                                                     ("ti_le_duong", float(np.mean(np.array(h[lop]) > 0))),
                                                     ("hieu_min", float(min(h[lop]))))}


def do_mot_anh(gray, tam, layout, layout_khac) -> dict:
    t0 = time.perf_counter()
    anh_nan = pp.warp(gray, tam, layout)
    d = pp.anh_do_toi(anh_nan)
    S = pp.diem_bo_cuc(anh_nan, layout, d=d)
    r = {"S0": S["S0"], "S180": S["S180"], "bien": (S["S0"] - S["S180"]) / S["S0"] if S["S0"] > 0 else float("nan"),
         "mo_phan_tu": pp.blur_score(anh_nan, layout, "phan_tu"),
         "mo_toan_trang": pp.blur_score(anh_nan, layout, "toan_trang"),
         "mo_huong": pp.blur_score(anh_nan, layout, "phan_tu_huong"),
         "loi_marker_max": max(pp.den_loi_marker(anh_nan, layout))}
    r["ms_do"] = (time.perf_counter() - t0) * 1000
    if pp.loai_trang(layout) == "phieu":
        trung = phan_tu_trung(layout)
        n_da = len(pp.phan_tu_bo_cuc(layout)[0][1])
        r.update({"S0_bo_trung": float(np.median(S["v0"][~trung])), "S180_bo_trung": float(np.median(S["v180"][~trung])),
                  "S180_dap_an": float(np.median(S["v180"][:n_da])), "S180_sbd_ma": float(np.median(S["v180"][n_da:])),
                  "S0_dap_an": float(np.median(S["v0"][:n_da])), "S0_sbd_ma": float(np.median(S["v0"][n_da:]))})
        r["bien_bo_trung"] = (r["S0_bo_trung"] - r["S180_bo_trung"]) / r["S0_bo_trung"]
    else:
        doc, ngang = pp.diem_bo_cuc(anh_nan, layout, "doc", d), pp.diem_bo_cuc(anh_nan, layout, "ngang", d)
        v0, v180 = (doc["v0"] + ngang["v0"]) / 2, (doc["v180"] + ngang["v180"]) / 2
        r.update({"S0_rieng": float(np.median(v0)), "S180_rieng": float(np.median(v180)),
                  "S0_ngang": ngang["S0"], "S180_ngang": ngang["S180"], "S0_doc": doc["S0"], "S180_doc": doc["S180"]})
        r["bien_rieng"] = (r["S0_rieng"] - r["S180_rieng"]) / r["S0_rieng"]
    Sk = pp.diem_bo_cuc(anh_nan, layout_khac)
    r["S_nham_loai"] = max(Sk["S0"], Sk["S180"])
    return r


def cmd_khao_sat(a) -> None:
    KS.mkdir(parents=True, exist_ok=True)
    L = {"phieu": nap_layout("phieu"), "chu_so": nap_layout("chu_so")}
    khac = {"phieu": "chu_so", "chu_so": "phieu"}
    tam = tam_v3()

    # ---- A. 78 ảnh dev thật: S đúng chiều / lật 180°, nhầm loại trang, blur, lõi marker
    rows = []
    for n_, x in enumerate(list_images("dev"), 1):
        gray = load_image(x.duong_dan)
        m, ly_do, _ = pp.find_markers(gray, L["phieu"])
        if m is None or np.abs(m - tam[x.ten]).max() > 0.01:
            sys.exit(f"LỖI: {x.ten} find_markers khác v3_hinh_hoc ({ly_do})")
        r = {"anh": x.ten, "loai": x.loai, "dieu_kien": x.dieu_kien,
             **do_mot_anh(gray, m, L[x.loai], L[khac[x.loai]])}
        rows.append(r)
        print(f"[{n_:2d}/78] {x.ten:8s} S0 {r['S0']:.3f} S180 {r['S180']:.3f} biên {r['bien']:.3f} | mờ {r['mo_phan_tu']:.4f} "
              f"/ {r['mo_toan_trang']:.5f} | nhầm loại {r['S_nham_loai']:.3f} | lõi {r['loi_marker_max']:.3f}")
    ghi_csv_ks(KS / "khao_sat_dev.csv", rows)

    # ---- B. hậu quả của mờ: ảnh dev bị làm mờ (nắn bằng 4 tâm v3 – không phụ thuộc khâu tìm marker)
    nhan = doc_nhan_o()
    trang = render_pdf_page(ANSWER_SHEET / "output" / "phieu_trang.pdf", L["phieu"]["dpi"])
    dev = {x.ten: x for x in list_images("dev")}
    nguon = []
    for c, mac_dinh in (("C1", "0001_C1"), ("C2", "0005_C2"), ("C3", "0015_C3"), ("C4", "0008_C4")):
        # thêm ảnh cùng điều kiện có nhiều ô faint nhất (nhiều mẫu lớp hiếm nhất), không chọn theo kết quả đo
        ung = [t for t, x in dev.items() if x.dieu_kien == c and t != mac_dinh]
        nhieu = max(ung, key=lambda t: sum(v == "faint" for k, v in nhan[t[:4]].items() if k[0].isdigit()))
        nguon += [mac_dinh, nhieu]
    nguon.append("D003")
    rows_mo = []
    for t in nguon:
        x = dev[t]
        g0 = load_image(x.duong_dan)
        lay = L[x.loai]
        muc = [("gauss", s) for s in GAUSS] + [("dong", k) for k in DONG]
        for kieu, v in muc:
            g = g0 if v == 0 else (cv2.GaussianBlur(g0, (0, 0), v) if kieu == "gauss" else mo_chuyen_dong(g0, v))
            anh_nan = pp.warp(g, tam[t], lay)
            S = pp.diem_bo_cuc(anh_nan, lay)
            r = {"anh": t, "dieu_kien": x.dieu_kien, "kieu": kieu, "muc": v, "S0": S["S0"], "S180": S["S180"],
                 "bien": (S["S0"] - S["S180"]) / S["S0"] if S["S0"] > 0 else float("nan"),
                 "mo_phan_tu": pp.blur_score(anh_nan, lay, "phan_tu"),
                 "mo_toan_trang": pp.blur_score(anh_nan, lay, "toan_trang"),
                 "mo_huong": pp.blur_score(anh_nan, lay, "phan_tu_huong")}
            if x.loai == "phieu":
                r.update({f"cd_{k}": v2 for k, v2 in hieu_nhan(anh_nan, lay, nhan[t[:4]]).items()})
                r.update({f"dl_{k}": v2 for k, v2 in hieu_nhan(anh_nan, lay, nhan[t[:4]], trang).items()})
            rows_mo.append(r)
            print(f"  {t:8s} {kieu:5s} {v:4} mờ {r['mo_phan_tu']:.4f} S0 {r['S0']:.3f} biên {r['bien']:.3f}"
                  + (f" | dò lại: faint {r['dl_faint_ti_le_duong']:.2f} ({r['dl_faint_hieu_min']:+.3f}) "
                     f"filled {r['dl_filled_ti_le_duong']:.2f} ({r['dl_filled_hieu_min']:+.3f})" if x.loai == "phieu" else ""))
    ghi_csv_ks(KS / "khao_sat_mo.csv", rows_mo)
    print(f"\nĐã ghi {KS / 'khao_sat_dev.csv'}, {KS / 'khao_sat_mo.csv'}")


def ghi_csv_ks(path: Path, rows: list[dict]) -> None:
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6f}" if isinstance(v, float) else v) for k, v in r.items()})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("tao-gia", help="sinh ảnh giả lỗi cố ý từ ảnh dev + danh_sach.csv (kết quả mong đợi) + ảnh ghép")
    sub.add_parser("khao-sat", help="dừng B: S đúng/lật 180°, nhầm loại trang, blur, lõi marker trên dev + hậu quả mờ")
    a = ap.parse_args()
    {"tao-gia": cmd_tao_gia, "khao-sat": cmd_khao_sat}[a.lenh](a)


if __name__ == "__main__":
    main()
