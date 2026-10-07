"""
check_labels.py - Kiểm tra nhãn từng câu trên ảnh thật trước khi sửa ground_truth.csv.

Với mỗi câu cần kiểm tra (vd 0032:33): đọc kịch bản trong ground_truth.csv, lấy mọi ảnh của phiếu
trong data/raw/, nắn phẳng bằng cv_engine.preprocessing.preprocess() (Tuần 4 Bước 6 – thay align()/check_align() cũ;
ảnh bị từ chối in rõ mã lý do), cắt hàng câu đó trên anh_nan, đo độ tối từng ô A-D bằng darkness() của check_layout.py,
xuất trang HTML để so với tờ giấy thật. Phiếu test 0035–0040 cần --xac-nhan-test (cv_engine/tap_du_lieu.py).

Gợi ý chỉ so độ tối trong cùng hàng (ô nào nổi bật) - CHỈ ĐỂ THAM KHẢO; rõ hay mờ phải xem bằng
mắt (ngưỡng cố định từng sai toàn bộ ở ô tô mờ). Không sửa ground_truth.csv.

Chạy (từ thư mục smart_exam_db/):
  python tools/check_labels.py 0032:33 0008:18 0021:5,6,11,12,14

Lệnh audit: quét các phiếu (40 câu + bubble SBD + mã đề), so với ground_truth.csv, xuất
data/_prepare/label_audit_<split>/label_audit.html + label_audit.csv. Chỉ dùng ảnh preprocess() trả ok (đo trên anh_nan
– cùng loại ảnh mà MARK_MIN / FILLED_MIN được chọn) và qua thêm STRICT_MARKER / MIN_SCALE; phiếu có 2 ảnh tốt thì đọc
cả 2 để đối chiếu chéo. Mặc định CHỈ DEV 0001–0034; phiếu test chỉ quét SAU đánh giá cuối (Bước 7):
  python tools/check_labels.py audit                                 # dev -> data/_prepare/label_audit_dev/
  python tools/check_labels.py audit --split test --xac-nhan-test    # sau Bước 7 -> label_audit_test/
  python tools/check_labels.py audit --split tat_ca --xac-nhan-test  # sau Bước 7 -> label_audit_tat_ca/
Chốt chặn nằm TRƯỚC khi đọc bất kỳ ảnh nào: dòng nhãn của phiếu test bị lọc bỏ ngay khi đọc ground_truth.csv.

  Đo tương đối, không dùng ngưỡng tuyệt đối của độ tối:
  - Mỗi ô: v = độ tối - độ tối nhỏ nhất trong cùng hàng (ô trống của hàng đó; mỗi câu tô tối đa 2 ô).
  - Chia cho S = trung vị v của các ô nhãn "tô rõ" trên CÙNG ảnh -> n ≈ 0 (trống) ... ≈ 1 (tô rõ).
    S lấy trung vị trên ~40 ô nên vài nhãn sai không làm lệch.
  - n < MARK_MIN: không tô; MARK_MIN..FILLED_MIN: mờ; >= FILLED_MIN: rõ.
  Nhóm A: tập ô được tô khác nhãn (nhầm ô / thiếu ô / thừa ô) hoặc SBD/mã đề lệch.
  Nhóm B: cùng tập ô, chỉ lệch rõ/mờ. Không sửa ground_truth.csv.
"""
import argparse
import csv
import html
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent          # smart_exam_db/
ANSWER_SHEET = ROOT / "answer_sheet"
sys.path.insert(0, str(ANSWER_SHEET))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from check_layout import darkness, render_pdf_page  # noqa: E402
from prepare_photos import marker_fill, nan_anh  # noqa: E402
from cv_engine.tap_du_lieu import PHIEU_DEV, PHIEU_TEST, ChamTapTest, chan_test  # noqa: E402

GAP = 0.15                        # ô nổi bật phải tối hơn ô thứ hai ít nhất bấy nhiêu
SCALE = 3                         # phóng to ảnh cắt
LEFT_MM, RIGHT_MM, HALF_H_MM = 12.0, 5.0, 4.5   # khung cắt quanh hàng ô (để thấy cả số câu)


def describe(a: str) -> str:
    """Diễn giải mã nhãn: chữ hoa = rõ, chữ thường = mờ, 2 chữ = tô nhiều ô, '-' = trống."""
    if a == "-":
        return "bỏ trống"
    if len(a) == 2:
        return f"tô nhiều ô {a[0]}+{a[1]} (rõ)"
    return f"{a.upper()} tô {'mờ' if a.islower() else 'rõ'}"


def suggest(d: dict) -> str:
    """So trong cùng hàng: ô trống in sẵn viền + chữ A-D nên tự nó đã tối ~0,27-0,38 trên ảnh thật,
    ngưỡng tuyệt đối 0,25 của baseline sẽ báo nhầm mọi ô trống là 'mờ'."""
    ranked = sorted(d.items(), key=lambda kv: kv[1], reverse=True)
    (o1, v1), (o2, v2) = ranked[0], ranked[1]
    if v1 - v2 < GAP:
        return f"không có ô nổi bật (chênh {v1 - v2:.2f}) – xem bằng mắt"
    return f"{o1} nổi bật (cao hơn ô thứ hai {v1 - v2:.2f}); rõ hay mờ: xem bằng mắt"


def parse_items(items: list[str]) -> list[tuple[str, int]]:
    out = []
    for it in items:
        sid, qs = it.split(":")
        out += [(sid.zfill(4), int(q)) for q in qs.split(",")]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Cắt + đo các câu cần kiểm tra nhãn")
    ap.add_argument("items", nargs="+", help="mã_phiếu:câu[,câu...] vd 0021:5,6,11")
    ap.add_argument("--ground-truth", default=ANSWER_SHEET / "output" / "ground_truth.csv")
    ap.add_argument("--raw", default=ROOT / "data" / "raw")
    ap.add_argument("--out", default=ROOT / "data" / "_prepare")
    ap.add_argument("--xac-nhan-test", action="store_true", help="cho phép phiếu test 0035–0040 (chỉ sau Bước 7)")
    a = ap.parse_args()
    items = parse_items(a.items)
    try:
        chan_test([sid for sid, _ in items], a.xac_nhan_test, "check_labels")
    except ChamTapTest as e:
        sys.exit(str(e))

    with Path(a.ground_truth).open(encoding="utf-8-sig", newline="") as f:
        gt = {r["sheet_id"]: r for r in csv.DictReader(f)}
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    ans = layout["answers"]
    r = ans["bubble_radius"]
    px_mm = layout["dpi"] / 25.4
    img_dir = Path(a.out) / "label_check"
    img_dir.mkdir(parents=True, exist_ok=True)

    aligned_cache, blocks = {}, []
    for sid, q in items:
        row = gt[sid]
        scen = row[f"q{q}"]
        conds = [c.strip() for c in row["conditions"].split("+")]
        conds.sort(key=lambda c: c != "C1")                    # ảnh C1 (rõ nhất) lên trước
        print(f"\nPhiếu {sid} câu {q}: kịch bản '{scen}' = {describe(scen)}")
        shots = []
        for c in conds:
            photo = Path(a.raw) / f"{sid}_{c}.jpg"
            if photo not in aligned_cache:
                aligned_cache[photo] = nan_anh(photo, "phieu")
            aligned, problem = aligned_cache[photo]
            if aligned is None:
                print(f"   {photo.name}: BỎ QUA – {problem}")
                shots.append((photo.name, None, None, problem))
                continue
            d = {o: darkness(aligned, *ans["centers"][str(q)][o], r) for o in ans["options"]}
            xs = [ans["centers"][str(q)][o][0] for o in ans["options"]]
            cy = ans["centers"][str(q)]["A"][1]
            x0, x1 = int(min(xs) - LEFT_MM * px_mm), int(max(xs) + RIGHT_MM * px_mm)
            y0, y1 = int(cy - HALF_H_MM * px_mm), int(cy + HALF_H_MM * px_mm)
            crop = cv2.resize(aligned[y0:y1, x0:x1], None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
            name = f"{sid}_q{q:02d}_{c}.png"
            cv2.imencode(".png", crop)[1].tofile(img_dir / name)
            vals = "  ".join(f"{o}={v:.2f}" for o, v in d.items())
            print(f"   {photo.name}: độ tối {vals} | {suggest(d)}")
            shots.append((photo.name, name, d, ""))
        blocks.append((sid, q, scen, shots))

    parts = []
    for sid, q, scen, shots in blocks:
        cells = []
        for pname, img, d, problem in shots:
            if img is None:
                cells.append(f"<div class='shot'><b>{pname}</b><p class='warn'>Bỏ qua: {html.escape(problem)}</p></div>")
                continue
            vals = "".join(f"<td>{o}<br><b>{v:.2f}</b></td>" for o, v in d.items())
            cells.append(f"<div class='shot'><b>{pname}</b><br><img src='label_check/{img}'>"
                         f"<table><tr>{vals}</tr></table>"
                         f"<small>{html.escape(suggest(d))}</small></div>")
        parts.append(f"<section><h3>Phiếu {sid} – câu {q}</h3>"
                     f"<p>Kịch bản: <code>{html.escape(scen)}</code> = <b>{html.escape(describe(scen))}</b></p>"
                     f"{''.join(cells)}</section>")
    page = Path(a.out) / "label_check.html"
    page.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Kiểm tra nhãn</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:16px;background:#fafafa;color:#222}}
section{{background:#fff;border:1px solid #ccc;padding:10px 14px;margin-bottom:14px}}
.shot{{display:inline-block;vertical-align:top;margin-right:24px}} img{{border:1px solid #888;display:block}}
table{{border-collapse:collapse;margin:4px 0}} td{{border:1px solid #ccc;padding:3px 10px;text-align:center}}
.warn{{color:#a40}} code{{font-size:16px}}
</style></head><body><h2>Kiểm tra nhãn trước khi sửa ground_truth.csv</h2>
<p>Độ tối = tỉ lệ pixel tối trong 75% bán kính ô (0 = trắng, 1 = đen). Ô trống cũng có độ tối
~0,3 vì viền và chữ A–D in sẵn – hãy so các ô <b>trong cùng hàng</b>, và so với <b>tờ giấy thật</b>.</p>
{''.join(parts)}</body></html>""", encoding="utf-8")
    print(f"\nTrang kiểm tra: {page}")


# ============================================================================ audit cả 40 phiếu
# Ngưỡng trên thang tương đối n (0 = ô trống, 1 = tô rõ điển hình). Đo 03/10/2026 trên 56 ảnh:
# ô trống p99 = 0,06, ô mờ p1 = 0,26 -> MARK_MIN 0,25. Mờ/rõ chồng lấn (mờ p95 0,85, rõ p5 0,88);
# 0,80 là điểm cân bằng: 34/367 ô mờ đo >= 0,80 và 34/1848 ô rõ đo < 0,80.
MARK_MIN, FILLED_MIN = 0.25, 0.80
# Kiểm tra cấp ảnh – chốt chặn PHỤ sau preprocess() (chọn 03/10/2026 trên 62 ảnh qua check_align() cũ; giữ ở Bước 6):
STRICT_MARKER = 0.95   # ảnh nắn đúng: độ đen tâm marker đều = 1,00; 0013_C2/0018_C2 nắn sai: 0,68/0,83
MIN_SCALE = 0.15       # S của ảnh đúng 0,30-0,62; ảnh sai tên/nắn sai 0,01-0,05 (ô "tô rõ" theo nhãn lại trống)
SEARCH_MM = 4.0        # dò lại vị trí từng hàng trong ±4 mm (< nửa khoảng cách hàng 11 mm)
FIELD_VI = {"sbd": "SBD", "exam_code": "Mã đề"}
LEVEL_VI = {"blank": "trống", "faint": "mờ", "filled": "rõ"}


def label_cells(code: str) -> dict:
    """Mã nhãn -> {ô: 'filled'/'faint'}; ô không có trong dict là trống."""
    if code == "-":
        return {}
    if len(code) == 2:
        return {o: "filled" for o in code}
    return {code.upper(): "faint" if code.islower() else "filled"}


def level(n: float) -> str:
    return "blank" if n < MARK_MIN else ("faint" if n < FILLED_MIN else "filled")


def read_code(lv: dict) -> str:
    """Ngược với label_cells: {ô: mức} -> mã kiểu ground_truth (chữ thường = mờ)."""
    marked = [o for o, l in lv.items() if l != "blank"]
    if not marked:
        return "-"
    return "".join(o if lv[o] == "filled" else o.lower() for o in marked)


def local_darkness(aligned, cx, cy, r) -> float:
    """Như darkness() nhưng so với nền giấy NGAY QUANH ô (vành 1,15r-1,45r, ngoài viền in sẵn):
    bóng đổ / vệt sáng ngang qua hàng (vd 0032_C4) làm ô trống ở vùng tối trông như 'mờ'."""
    x0, y0 = int(cx - 1.5 * r), int(cy - 1.5 * r)
    patch = aligned[y0:int(cy + 1.5 * r), x0:int(cx + 1.5 * r)].astype(np.float32)
    yy, xx = np.ogrid[:patch.shape[0], :patch.shape[1]]
    d2 = (xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2
    paper = np.median(patch[(d2 >= (1.15 * r) ** 2) & (d2 <= (1.45 * r) ** 2)])
    return float(np.clip(1 - patch[d2 <= (0.75 * r) ** 2].mean() / max(paper, 1.0), 0, 1))


def item_box(layout, item) -> tuple:
    """Khung (x0, y0, x1, y1) trên phiếu chuẩn: 1 hàng câu (kèm số câu), hoặc cả khối SBD/mã đề."""
    px_mm = layout["dpi"] / 25.4
    kind, idx = item
    if kind == "q":
        ans = layout["answers"]
        c = ans["centers"][str(idx)]
        xs = [c[o][0] for o in ans["options"]]
        cy = c["A"][1]
        return (int(min(xs) - LEFT_MM * px_mm), int(cy - HALF_H_MM * px_mm),
                int(max(xs) + RIGHT_MM * px_mm), int(cy + HALF_H_MM * px_mm))
    f = layout[kind]
    r = f["bubble_radius"]
    hx, hy, hw, _ = f["handwriting_boxes"][0]
    last = f["bubbles"][-1]
    return (int(min(hx, f["bubbles"][0][0][0] - r) - 6 * px_mm), int(hy - 2 * px_mm),
            int(max(f["handwriting_boxes"][-1][0] + hw, last[0][0] + r) + 3 * px_mm),
            int(last[-1][1] + r + 2 * px_mm))


def register(aligned, blank, box, search: int) -> tuple[int, int]:
    """Độ lệch (dx, dy) của vùng box trên ảnh so với phiếu trắng gốc (giấy cong -> align() lệch cục bộ
    tới ~3 mm, vd 0014_C2). Tìm trong ±search px bằng so khớp mẫu."""
    x0, y0, x1, y1 = box
    region = aligned[max(0, y0 - search):y1 + search, max(0, x0 - search):x1 + search]
    res = cv2.matchTemplate(region, blank[y0:y1, x0:x1], cv2.TM_CCOEFF_NORMED)
    bx, by = cv2.minMaxLoc(res)[3]
    return bx - min(search, x0), by - min(search, y0)


def measure_image(aligned, layout, row, blank) -> dict:
    """Độ tối tương đối n của mọi ô trên 1 ảnh đã nắn (xem docstring đầu file)."""
    ans = layout["answers"]
    r = ans["bubble_radius"]
    search = round(SEARCH_MM * layout["dpi"] / 25.4)
    nq = ans["num_questions"]
    shift = {item: register(aligned, blank, item_box(layout, item), search)
             for item in [("q", q) for q in range(1, nq + 1)] + [(f, 0) for f in FIELD_VI]}
    raw = np.array([[local_darkness(aligned, ans["centers"][str(q)][o][0] + shift[("q", q)][0],
                              ans["centers"][str(q)][o][1] + shift[("q", q)][1], r) for o in ans["options"]]
                    for q in range(1, nq + 1)])
    v = raw - raw.min(axis=1, keepdims=True)
    filled = np.array([[label_cells(row[f"q{q}"]).get(o) == "filled" for o in ans["options"]]
                       for q in range(1, nq + 1)])
    scale = float(np.median(v[filled]))
    out = {"raw": raw, "n": v / scale, "scale": scale, "shift": shift}
    for field in FIELD_VI:
        f = layout[field]
        dx, dy = shift[(field, 0)]
        d = np.array([[local_darkness(aligned, cx + dx, cy + dy, f["bubble_radius"]) for cx, cy in col]
                      for col in f["bubbles"]])
        # nền = trung vị 10 ô của cột (9 ô trống); thang = trung vị (ô tối nhất - nền) qua các cột
        # của khối (ô bubble nhỏ hơn ô đáp án nên không dùng chung S); 1 cột sai không làm lệch thang.
        # Sàn 0,5·S: khối không tô ô nào (vd mã đề 0035) thì thang không co về ~0 rồi khuếch đại nhiễu.
        v = d - np.median(d, axis=1, keepdims=True)
        out[field] = v / max(float(np.median(v.max(axis=1))), 0.5 * scale)
    return out


def judge_question(n_row, code, options) -> tuple:
    """(nhóm 'A'/'B'/None, mức chắc chắn, mô tả, mã đọc được) của 1 câu trên 1 ảnh."""
    lab = label_cells(code)
    lv = {o: level(v) for o, v in zip(options, n_row)}
    nv = dict(zip(options, n_row))
    got = {o for o, l in lv.items() if l != "blank"}
    if got != set(lab):
        missing, extra = set(lab) - got, got - set(lab)
        kind = "tô nhầm ô" if missing and extra else ("thiếu ô" if missing else "thừa ô")
        score = sum(min(1.0, abs(nv[o] - MARK_MIN)) for o in missing | extra)
        return "A", score, kind, read_code(lv)
    diff = [o for o in lab if lv[o] != lab[o]]
    if diff:
        kind = ", ".join(f"{o}: nhãn {LEVEL_VI[lab[o]]}, ảnh {LEVEL_VI[lv[o]]}" for o in diff)
        return "B", sum(abs(nv[o] - FILLED_MIN) for o in diff), kind, read_code(lv)
    return None, 0.0, "", read_code(lv)


def judge_digit(n_col, label: str) -> tuple:
    """label = 1 ký tự của cột sbd_bubble/exam_code_bubble: chữ số được tô, '-' = cột không tô ô nào."""
    marked = {k for k in range(10) if n_col[k] >= MARK_MIN}
    read = "".join(str(k) for k in sorted(marked)) or "-"
    want = set() if label == "-" else {int(label)}
    if marked != want:
        wrong = marked ^ want
        kind = "đọc ra " + (f"{read}" if marked else "không ô nào") + f", nhãn {label}"
        return "A", sum(min(1.0, abs(n_col[k] - MARK_MIN)) for k in wrong), kind, read
    if not want:
        return None, 0.0, "", read
    digit = int(label)
    if n_col[digit] < FILLED_MIN:
        return "B", FILLED_MIN - n_col[digit], f"ô {digit} chỉ mờ", read
    return None, 0.0, "", read


def color_crop(aligned, x0, y0, x1, y1, boxes, r, scale) -> np.ndarray:
    """Cắt vùng, khoanh xanh dương quanh các ô theo NHÃN (không đè lên mực trong ô)."""
    img = cv2.cvtColor(aligned[y0:y1, x0:x1], cv2.COLOR_GRAY2BGR)
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    pad = r + 8
    for cx, cy in boxes:
        p0 = (int((cx - pad - x0) * scale), int((cy - pad - y0) * scale))
        p1 = (int((cx + pad - x0) * scale), int((cy + pad - y0) * scale))
        cv2.rectangle(img, p0, p1, (220, 90, 0), 2)
    return img


def crop_item(aligned, layout, row, item, shift) -> np.ndarray:
    """Ảnh cắt đã bù độ lệch cục bộ: 1 hàng câu, hoặc 1 cột SBD/mã đề kèm ô viết tay."""
    px_mm = layout["dpi"] / 25.4
    kind, idx = item
    if kind == "q":
        dx, dy = shift[item]
        x0, y0, x1, y1 = item_box(layout, item)
        c = layout["answers"]["centers"][str(idx)]
        boxes = [(c[o][0] + dx, c[o][1] + dy) for o in label_cells(row[f"q{idx}"])]
        return color_crop(aligned, x0 + dx, y0 + dy, x1 + dx, y1 + dy, boxes, layout["answers"]["bubble_radius"], SCALE)
    dx, dy = shift[(kind, 0)]
    f = layout[kind]
    col = f["bubbles"][idx]
    hx, hy, hw, _ = f["handwriting_boxes"][idx]
    r = f["bubble_radius"]
    x0 = int(min(hx, col[0][0] - r) - 6 * px_mm) + dx
    x1 = int(max(hx + hw, col[0][0] + r) + 6 * px_mm) + dx
    label = row[f"{kind}_bubble"][idx]
    boxes = [] if label == "-" else [(col[int(label)][0] + dx, col[int(label)][1] + dy)]
    return color_crop(aligned, x0, int(hy - 2 * px_mm) + dy, x1, int(col[-1][1] + r + 2 * px_mm) + dy,
                      boxes, r, 1.5)


def item_name(item) -> str:
    kind, idx = item
    return f"câu {idx}" if kind == "q" else f"{FIELD_VI[kind]} chữ số {idx + 1}"


def item_label(row, item) -> str:
    kind, idx = item
    if kind == "q":
        code = row[f"q{idx}"]
        return f"<code>{html.escape(code)}</code> = {html.escape(describe(code))}"
    return (f"ô tô <code>{row[f'{kind}_bubble'][idx]}</code> (viết tay <code>{row[kind][idx]}</code>; "
            f"cả {FIELD_VI[kind]}: viết {row[kind]}, tô {row[f'{kind}_bubble']})")


def values_table(item, n, raw=None) -> str:
    kind, _ = item
    heads = "ABCD" if kind == "q" else "0123456789"
    tds = "".join(f"<td>{h}<br><b>{v:.2f}</b>" + (f"<br><small>{w:.2f}</small>" if raw is not None else "") + "</td>"
                  for h, v, w in zip(heads, n, raw if raw is not None else n))
    return f"<table><tr>{tds}</tr></table>"


def cmd_audit(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(prog="check_labels.py audit",
                                 description="Quét nhãn các phiếu so với ảnh (không sửa nhãn); mặc định chỉ dev")
    ap.add_argument("--ground-truth", default=ANSWER_SHEET / "output" / "ground_truth.csv")
    ap.add_argument("--raw", default=ROOT / "data" / "raw")
    ap.add_argument("--split", default="dev", choices=["dev", "test", "tat_ca"],
                    help="dev = 0001–0034; test = 0035–0040; tat_ca = cả 40 phiếu (test / tat_ca chỉ SAU đánh giá cuối "
                         "Bước 7, cần --xac-nhan-test)")
    ap.add_argument("--xac-nhan-test", action="store_true")
    ap.add_argument("--out", default=None, help="mặc định data/_prepare/label_audit_<split>/")
    a = ap.parse_args(argv)
    out_dir = Path(a.out) if a.out else ROOT / "data" / "_prepare" / f"label_audit_{a.split}"

    # Chốt chặn tập test – TRƯỚC khi đọc bất kỳ ảnh nào; dòng nhãn phiếu test bị bỏ ngay (dev) hoặc phải có cờ (tat_ca)
    with Path(a.ground_truth).open(encoding="utf-8-sig", newline="") as f:
        gt = {r["sheet_id"]: r for r in csv.DictReader(f)}
    if a.split == "dev":
        gt = {sid: r for sid, r in gt.items() if int(sid) in PHIEU_DEV}
    elif a.split == "test":
        gt = {sid: r for sid, r in gt.items() if int(sid) in PHIEU_TEST}
    chan_test(gt, a.xac_nhan_test, f"check_labels.py audit --split {a.split}")
    print(f"Quét {len(gt)} phiếu ({a.split}): {min(gt)}–{max(gt)} -> {out_dir}")
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    options = layout["answers"]["options"]
    blank = render_pdf_page(ANSWER_SHEET / "output" / "phieu_trang.pdf", layout["dpi"])
    img_dir = out_dir / "label_audit"
    img_dir.mkdir(parents=True, exist_ok=True)
    for old in img_dir.glob("*.png"):       # chỉ xoá ảnh cắt của CHÍNH thư mục audit này (bản cũ ở chỗ khác giữ nguyên)
        old.unlink()

    skipped, suspect, unscannable, coverage, scales = [], [], [], {}, []
    findings = []                         # mỗi phần tử: 1 mục (câu / chữ số) bị nghi trên 1 phiếu
    pooled = {"blank": [], "faint": [], "filled": []}
    for sid, row in gt.items():
        conds = sorted((c.strip() for c in row["conditions"].split("+")), key=lambda c: c != "C1")
        good = []
        for c in conds:
            photo = Path(a.raw) / f"{sid}_{c}.jpg"
            aligned, problem = nan_anh(photo, "phieu")
            if aligned is None:
                skipped.append((photo.name, problem))
                print(f"  {photo.name}: BỎ QUA – {problem}")
                continue
            fill = min(marker_fill(aligned, layout).values())
            if fill < STRICT_MARKER:
                suspect.append((photo.name, f"nghi nắn sai: tâm marker chỉ đen {fill:.0%} (preprocess() cho qua)"))
                continue
            m = measure_image(aligned, layout, row, blank)
            if m["scale"] < MIN_SCALE:
                suspect.append((photo.name, f"ô tô rõ theo nhãn gần như trống cả phiếu (S = {m['scale']:.3f}) "
                                            f"– nghi ảnh của phiếu khác (sai tên)"))
                continue
            good.append((c, aligned, m))
            scales.append(m["scale"])
        coverage[sid] = [c for c, _, _ in good]
        print(f"Phiếu {sid}: ảnh nắn đúng {'+'.join(coverage[sid]) or 'KHÔNG CÓ'}")
        if not good:
            unscannable.append(sid)
            continue
        for _, _, m in good:
            for q in range(1, 41):
                lab = label_cells(row[f"q{q}"])
                for i, o in enumerate(options):
                    pooled[lab.get(o, "blank")].append(m["n"][q - 1, i])

        items = [("q", q) for q in range(1, 41)]
        items += [(fld, i) for fld in FIELD_VI for i in range(len(row[fld]))]
        for item in items:
            kind, idx = item
            per = []
            for c, aligned, m in good:
                if kind == "q":
                    nvals, rawvals = m["n"][idx - 1], m["raw"][idx - 1]
                    res = judge_question(nvals, row[f"q{idx}"], options)
                else:
                    nvals, rawvals = m[kind][idx], None
                    res = judge_digit(nvals, row[f"{kind}_bubble"][idx])
                per.append((c, aligned, nvals, rawvals, res, m["shift"]))
            groups = [p[4][0] for p in per]
            if not any(groups):
                continue
            grp = "A" if "A" in groups else "B"
            hits = [p for p in per if p[4][0] == grp]
            findings.append({
                "sid": sid, "item": item, "group": grp, "row": row,
                "score": sum(p[4][1] for p in hits) / len(per),   # ảnh không thấy lỗi kéo điểm xuống
                "agree": f"{len(hits)}/{len(per)}",
                "kind": "; ".join(dict.fromkeys(p[4][2] for p in hits)),
                "shots": per,
            })

    # ---- phân bố n theo nhãn: để kiểm tra ngưỡng MARK_MIN / FILLED_MIN có hợp lý
    print(f"\nPhân bố độ tối tương đối n theo nhãn (ngưỡng: mờ >= {MARK_MIN}, rõ >= {FILLED_MIN}):")
    for k, vals in pooled.items():
        p = np.percentile(vals, [1, 5, 50, 95, 99])
        print(f"  {k:6s} ({len(vals):5d} ô): p1={p[0]:.2f} p5={p[1]:.2f} trung vị={p[2]:.2f} "
              f"p95={p[3]:.2f} p99={p[4]:.2f}")

    print(f"  Thang S của {len(scales)} ảnh dùng được: {min(scales):.2f}–{max(scales):.2f} (loại ảnh nếu < {MIN_SCALE})")

    findings.sort(key=lambda f: (f["group"], -f["score"]))
    # ---- ảnh cắt + CSV + HTML
    csv_path = out_dir / "label_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["group", "score", "sheet_id", "item", "label", "kind", "agree", "reads"])
        for f in findings:
            kind, idx = f["item"]
            lab = f["row"][f"q{idx}"] if kind == "q" else f["row"][kind][idx]
            reads = " ".join(f"{s[0]}:{s[4][3]}" for s in f["shots"])
            w.writerow([f["group"], f"{f['score']:.2f}", f["sid"], item_name(f["item"]), lab,
                        f["kind"], f["agree"], reads])

    def section(f) -> str:
        kind, idx = f["item"]
        cells = []
        for c, aligned, nvals, rawvals, res, shift in f["shots"]:
            name = f"{f['sid']}_{kind}{idx:02d}_{c}.png"
            cv2.imencode(".png", crop_item(aligned, layout, f["row"], f["item"], shift))[1].tofile(img_dir / name)
            verdict = "khớp nhãn" if res[0] is None else html.escape(res[2])
            cells.append(f"<div class='shot'><b>{f['sid']}_{c}.jpg</b> – đọc <code>{html.escape(res[3])}</code> "
                         f"({verdict})<br><img src='label_audit/{name}'>{values_table(f['item'], nvals, rawvals)}</div>")
        return (f"<section><h3>Phiếu {f['sid']} – {item_name(f['item'])}: {html.escape(f['kind'])} "
                f"<span class='sc'>điểm nghi {f['score']:.2f} · {f['agree']} ảnh</span></h3>"
                f"<p>Nhãn: {item_label(f['row'], f['item'])}</p>{''.join(cells)}</section>")

    grp_a = [f for f in findings if f["group"] == "A"]
    grp_b = [f for f in findings if f["group"] == "B"]
    two = sum(len(v) == 2 for v in coverage.values())
    one = [s for s, v in coverage.items() if len(v) == 1]
    skip_li = "".join(f"<li>{html.escape(n)}: {html.escape(p)}</li>" for n, p in skipped)
    sus_li = "".join(f"<li><b>{html.escape(n)}</b>: {html.escape(p)}</li>" for n, p in suspect)
    page = out_dir / "label_audit.html"
    page.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Quét nhãn {len(coverage)} phiếu</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:16px;background:#fafafa;color:#222}}
section{{background:#fff;border:1px solid #ccc;padding:10px 14px;margin-bottom:14px}}
.shot{{display:inline-block;vertical-align:top;margin-right:24px}} img{{border:1px solid #888;display:block}}
table{{border-collapse:collapse;margin:4px 0}} td{{border:1px solid #ccc;padding:2px 7px;text-align:center}}
.sc{{font-weight:normal;color:#666;font-size:14px}} .warn{{color:#a40}} code{{font-size:16px}}
summary{{font-size:20px;font-weight:bold;cursor:pointer;margin:10px 0}}
</style></head><body><h2>Quét nhãn {len(coverage)} phiếu ({a.split}: {min(gt)}–{max(gt)}) so với ảnh
(không sửa nhãn) – nắn bằng preprocess(), đo trên anh_nan</h2>
<p><b>Cách đọc:</b> khung <span style="color:#005adc">xanh dương</span> = ô theo NHÃN trong ground_truth.csv.
Số in đậm = độ tối tương đối n (0 = như ô trống cùng hàng, 1 = như ô tô rõ điển hình trên cùng ảnh);
số nhỏ = độ tối thô. n &lt; {MARK_MIN}: coi là không tô; {MARK_MIN}–{FILLED_MIN}: mờ; ≥ {FILLED_MIN}: rõ.
Mục sắp theo điểm nghi giảm dần (cao = càng chắc là nhãn sai); "1/2 ảnh" = chỉ 1 trong 2 ảnh thấy lệch.
<b>Luôn so với tờ giấy thật trước khi sửa.</b></p>
<p>Quét được {len(coverage) - len(unscannable)}/{len(coverage)} phiếu: {two} phiếu đối chiếu 2 ảnh,
{len(one)} phiếu chỉ 1 ảnh ({', '.join(one)}).
<span class="warn">Không quét được: {', '.join(unscannable) or 'không có'}</span>.</p>
<h2 class="warn">Ảnh đáng ngờ – preprocess() trả ok nhưng bị loại ở kiểm tra phụ ({len(suspect)} ảnh)</h2>
<ul>{sus_li or '<li>Không có.</li>'}</ul>
<details><summary style="font-size:15px">{len(skipped)} ảnh bị preprocess() từ chối</summary><ul>{skip_li or '<li>Không có.</li>'}</ul></details>
<h2>Nhóm A – nghi tô nhầm / thiếu / thừa ô, SBD hoặc mã đề lệch ({len(grp_a)} mục)</h2>
{''.join(section(f) for f in grp_a) or '<p>Không có.</p>'}
<details><summary>Nhóm B – chỉ lệch rõ/mờ ({len(grp_b)} mục, dễ báo nhầm)</summary>
{''.join(section(f) for f in grp_b) or '<p>Không có.</p>'}</details>
</body></html>""", encoding="utf-8")

    print("\nẢnh đáng ngờ (bị loại):")
    for n, p in suspect:
        print(f"  {n}: {p}")
    print(f"\nNhóm A: {len(grp_a)} mục | Nhóm B: {len(grp_b)} mục | không quét được: {unscannable or 'không'}")
    for f in grp_a:
        print(f"  A {f['score']:.2f} {f['agree']}  {f['sid']} {item_name(f['item'])}: {f['kind']}")
    print(f"\nTrang báo cáo: {page}\nBảng: {csv_path}")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "audit":
            cmd_audit(sys.argv[2:])
        else:
            main()
    except ChamTapTest as e:
        sys.exit(str(e))
