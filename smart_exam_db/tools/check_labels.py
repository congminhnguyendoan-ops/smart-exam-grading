"""
check_labels.py - Kiểm tra nhãn từng câu trên ảnh thật trước khi sửa ground_truth.csv.

Với mỗi câu cần kiểm tra (vd 0032:33): đọc kịch bản trong ground_truth.csv, lấy mọi ảnh của phiếu
trong data/raw/, nắn phẳng bằng align() (bỏ ảnh mà check_align() báo nắn sai), cắt hàng câu đó,
đo độ tối từng ô A-D bằng darkness() của check_layout.py, xuất trang HTML để so với tờ giấy thật.

Gợi ý chỉ so độ tối trong cùng hàng (ô nào nổi bật) - CHỈ ĐỂ THAM KHẢO; rõ hay mờ phải xem bằng
mắt (ngưỡng cố định từng sai toàn bộ ở ô tô mờ). Không sửa ground_truth.csv.

Chạy (từ thư mục smart_exam_db/):
  python tools/check_labels.py 0032:33 0008:18 0021:5,6,11,12,14
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
from check_layout import darkness  # noqa: E402
from prepare_photos import check_align, load_templates  # noqa: E402

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
    a = ap.parse_args()

    with Path(a.ground_truth).open(encoding="utf-8-sig", newline="") as f:
        gt = {r["sheet_id"]: r for r in csv.DictReader(f)}
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    template = load_templates()["sheet"]
    ans = layout["answers"]
    r = ans["bubble_radius"]
    px_mm = layout["dpi"] / 25.4
    img_dir = Path(a.out) / "label_check"
    img_dir.mkdir(parents=True, exist_ok=True)

    aligned_cache, blocks = {}, []
    for sid, q in parse_items(a.items):
        row = gt[sid]
        scen = row[f"q{q}"]
        conds = [c.strip() for c in row["conditions"].split("+")]
        conds.sort(key=lambda c: c != "C1")                    # ảnh C1 (rõ nhất) lên trước
        print(f"\nPhiếu {sid} câu {q}: kịch bản '{scen}' = {describe(scen)}")
        shots = []
        for c in conds:
            photo = Path(a.raw) / f"{sid}_{c}.jpg"
            if photo not in aligned_cache:
                gray = cv2.imdecode(np.fromfile(photo, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                aligned_cache[photo] = check_align(gray, layout, template)
            aligned, _, problem = aligned_cache[photo]
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


if __name__ == "__main__":
    main()
