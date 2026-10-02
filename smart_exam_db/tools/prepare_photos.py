"""
prepare_photos.py - Chuẩn bị bộ ảnh dữ liệu từ ảnh HEIC chụp bằng iPhone.

Bước 1 (lệnh `plan`):
  - Chuyển data/raw_heic/*.HEIC -> data/_prepare/jpg/IMG_xxxx.jpg (JPEG 95, giữ độ phân giải,
    ảnh được xoay đúng chiều theo EXIF). KHÔNG sửa, KHÔNG xoá file gốc.
  - Sắp xếp ảnh theo thời gian chụp trong EXIF (DateTimeOriginal), KHÔNG dùng ngày sửa file.
    Ảnh thiếu EXIF được xếp theo số trong tên IMG_xxxx.
  - Đề xuất tên mới: 80 ảnh đầu -> NNNN_Ck.jpg (điều kiện lấy từ ground_truth.csv),
    10 ảnh sau -> DNNN.jpg.
  - Xuất data/_prepare/mapping.csv và data/_prepare/preview.html để kiểm tra bằng mắt.

Lệnh `preview`: chỉ tạo lại preview.html từ mapping.csv hiện có (giữ nguyên chỗ bạn đã sửa).

Bước 2 (lệnh `apply`): chép data/_prepare/jpg/<old_name> -> data/raw/<new_name> (ảnh phiếu) hoặc
  data/raw_digits/<new_name> (trang chữ số). Kiểm tra TOÀN BỘ mapping trước, có lỗi thì không chép gì.
  Không bao giờ ghi đè file đã có, không xoá ảnh nguồn. Dòng có new_name rỗng (ảnh đã bị thay) bị bỏ qua.

Lệnh `replace`: thay 1 ảnh đã chép bằng ảnh chụp lại. Ảnh cũ được DI CHUYỂN sang data/raw_rejected/
  (không xoá), ảnh mới chép vào đúng chỗ, mapping.csv ghi lại cả hai.

Preview tự kiểm tra kết quả align() (find_markers() có thể chọn nhầm marker mà không báo lỗi):
  - Sau khi nắn, tâm 6x6 mm của mỗi marker phải gần như đen kín; nếu không -> chọn nhầm marker.
  - So ảnh nắn với mẫu phiếu ở 4 chiều xoay (NCC); chiều khác 0° tốt hơn rõ -> ảnh nằm ngang.
  Ảnh không đạt: cắt 1/4 góc trên phải của ảnh GỐC (đã dựng đứng), không dùng align().

Chạy (từ thư mục smart_exam_db/):
  python tools/prepare_photos.py plan
  python tools/prepare_photos.py preview
  python tools/prepare_photos.py apply
  python tools/prepare_photos.py replace --src data/raw_heic/IMG_4357.JPG --name 0028_C4.jpg --reason "..."
"""
import argparse
import base64
import csv
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

ROOT = Path(__file__).resolve().parent.parent          # smart_exam_db/
ANSWER_SHEET = ROOT / "answer_sheet"
sys.path.insert(0, str(ANSWER_SHEET))
from check_layout import align  # noqa: E402  (dùng lại hàm nắn phẳng, KHÔNG sửa ở đây)

register_heif_opener()                                  # cho phép Image.open() đọc HEIC

N_SHEETS = 40
N_DIGIT_PAGES = 10
JPEG_QUALITY = 95
IMG_RE = re.compile(r"IMG_(\d+)", re.I)
SHEET_NAME_RE = re.compile(r"^(\d{4})_(C[1-4])\.jpg$")    # giống check_photos.py
DIGIT_NAME_RE = re.compile(r"^D\d{3}\.jpg$")

# Thẻ EXIF
EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL = 36867
TAG_SUBSEC_ORIGINAL = 37521
TAG_ORIENTATION = 274

# Vùng chữ "Mã phiếu"/"Mã trang" trên ảnh đã nắn (mm, gốc góc trên trái) - xem generate_sheets.py
CODE_BOX_MM = (120.0, 20.0, 200.0, 32.0)               # x0, y0, x1, y1
MARKER_CHECK_MM = 3.0       # nửa cạnh ô kiểm tra ở tâm marker (marker 8 mm)
MIN_MARKER_FILL = 0.5       # marker thật ~1.0; ô tròn / chữ số bị chọn nhầm 0.03-0.43 (đo trên 90 ảnh)
MIN_ROTATE_GAIN = 0.10      # NCC chiều xoay khác phải hơn chiều 0° ít nhất bấy nhiêu
NCC_SIZE = (124, 175)       # ảnh thu nhỏ để so với mẫu
CORNERS = ("tl", "tr", "br", "bl")
CORNER_VI = {"tl": "trên trái", "tr": "trên phải", "br": "dưới phải", "bl": "dưới trái"}
CONDITION_TEXT = {"C1": "C1 – đủ sáng, thẳng", "C2": "C2 – thiếu sáng", "C3": "C3 – nghiêng",
                  "C4": "C4 – đèn vàng, có bóng"}


# ---------------------------------------------------------------- chuyển HEIC -> JPG
def convert(src: Path, dst: Path) -> None:
    """Xoay pixel theo EXIF rồi ghi JPEG; đặt lại Orientation = 1 để không bị xoay 2 lần."""
    with Image.open(src) as im:
        exif = im.getexif()
        icc = im.info.get("icc_profile")
        upright = ImageOps.exif_transpose(im).convert("RGB")
    exif[TAG_ORIENTATION] = 1
    upright.save(dst, "JPEG", quality=JPEG_QUALITY, subsampling=0,
                 exif=exif.tobytes(), icc_profile=icc)


def capture_time(path: Path):
    """Trả về (datetime, nguồn) từ EXIF DateTimeOriginal (+ phần lẻ giây), hoặc (None, ...)."""
    with Image.open(path) as im:
        sub = im.getexif().get_ifd(EXIF_IFD)
    raw = sub.get(TAG_DATETIME_ORIGINAL)
    if not raw:
        return None, "thiếu EXIF"
    t = datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    subsec = str(sub.get(TAG_SUBSEC_ORIGINAL, "")).strip("\x00 ")
    if subsec.isdigit():
        t = t.replace(microsecond=int(subsec.ljust(6, "0")[:6]))
    return t, "EXIF"


def img_number(path: Path) -> int:
    m = IMG_RE.search(path.stem)
    return int(m.group(1)) if m else 10**9


def sort_photos(items: list[dict]) -> list[dict]:
    """Sắp theo giờ chụp EXIF. Ảnh thiếu EXIF mượn giờ của ảnh có số IMG liền trước nó,
    nên vẫn nằm đúng chỗ theo số trong tên."""
    by_num = sorted(items, key=lambda it: it["num"])
    last = datetime.min
    for it in by_num:
        if it["time"] is not None:
            last = it["time"]
        it["sort_time"] = it["time"] or last
    return sorted(items, key=lambda it: (it["sort_time"], it["num"]))


# ---------------------------------------------------------------- tên đề xuất
def proposed_names(ground_truth: Path) -> list[str]:
    with ground_truth.open(encoding="utf-8-sig", newline="") as f:
        rows = {r["sheet_id"]: r for r in csv.DictReader(f)}
    names = []
    for i in range(1, N_SHEETS + 1):
        sid = f"{i:04d}"
        conds = rows[sid]["conditions"].split("+")
        names += [f"{sid}_{c.strip()}.jpg" for c in conds]
    names += [f"D{i:03d}.jpg" for i in range(1, N_DIGIT_PAGES + 1)]
    return names


# ---------------------------------------------------------------- ảnh cho preview
def to_b64(bgr_or_gray, max_w: int) -> str:
    h, w = bgr_or_gray.shape[:2]
    if w > max_w:
        bgr_or_gray = cv2.resize(bgr_or_gray, (max_w, round(h * max_w / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", bgr_or_gray, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf.tobytes()).decode("ascii")


def ncc_prep(gray):
    s = cv2.resize(gray, NCC_SIZE, interpolation=cv2.INTER_AREA)
    s = cv2.GaussianBlur(s, (3, 3), 0).astype(np.float32)
    s -= s.mean()
    return s / (np.linalg.norm(s) + 1e-6)


def load_templates() -> dict:
    """Mẫu để so chiều xoay: trang 1 của PDF phiếu và PDF trang chữ số."""
    out = {}
    for key, pdf in (("sheet", "phieu_danh_so.pdf"), ("digit", "trang_chu_so.pdf")):
        pix = pymupdf.open(ANSWER_SHEET / "output" / pdf)[0].get_pixmap(dpi=60, colorspace=pymupdf.csGRAY)
        out[key] = ncc_prep(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width))
    return out


def marker_fill(aligned, layout) -> dict:
    """Tỉ lệ pixel tối ở tâm mỗi marker trên ảnh đã nắn (marker thật ~ 1.0)."""
    th = cv2.threshold(aligned, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    r = round(MARKER_CHECK_MM * layout["dpi"] / 25.4)
    out = {}
    for c in CORNERS:
        cx, cy = (round(v) for v in layout["markers"]["centers"][c])
        out[c] = th[cy - r:cy + r, cx - r:cx + r].mean() / 255
    return out


def check_align(gray, layout, template) -> tuple:
    """Trả về (ảnh đã nắn hoặc None, số lần xoay 90° để dựng đứng ảnh gốc, lý do nếu align() sai)."""
    try:
        aligned = align(gray, layout)
    except Exception as e:  # noqa: BLE001
        return None, 0, f"align() lỗi: {e}"
    fill = marker_fill(aligned, layout)
    bad = [c for c in CORNERS if fill[c] < MIN_MARKER_FILL]
    if bad:
        detail = ", ".join(f"{CORNER_VI[c]} (đen {fill[c]:.0%})" for c in bad)
        k = 0 if gray.shape[0] >= gray.shape[1] else best_rotation(gray, layout, template)[0]
        return None, k, f"align() chọn nhầm marker góc {detail}"
    k, gain = best_rotation(gray, layout, template, aligned)
    if k and gain >= MIN_ROTATE_GAIN:
        return None, k, f"đủ 4 marker nhưng ảnh bị xoay {k * 90}° – align() gán sai góc"
    return aligned, 0, ""


def best_rotation(gray, layout, template, aligned0=None) -> tuple[int, float]:
    """Chiều xoay (k lần 90° ngược kim đồng hồ) cho ảnh nắn giống mẫu nhất, và mức hơn chiều 0°."""
    scores = []
    for k in range(4):
        try:
            al = aligned0 if (k == 0 and aligned0 is not None) else align(np.ascontiguousarray(np.rot90(gray, k)), layout)
            scores.append(float((ncc_prep(al) * template).sum()))
        except Exception:  # noqa: BLE001
            scores.append(-1.0)
    k = int(np.argmax(scores))
    return k, scores[k] - scores[0]


def preview_images(jpg: Path, layout: dict, template) -> tuple[str, str, str]:
    """(ảnh vùng mã đã cắt, ảnh thu nhỏ toàn trang, lý do nếu align() sai – rỗng nếu OK)."""
    bgr = cv2.imdecode(np.fromfile(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)   # fromfile: an toàn với đường dẫn Unicode
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    thumb = to_b64(bgr, 320)
    aligned, k, problem = check_align(gray, layout, template)
    if aligned is not None:
        px_per_mm = layout["dpi"] / 25.4
        x0, y0, x1, y1 = (round(v * px_per_mm) for v in CODE_BOX_MM)
        return to_b64(aligned[y0:y1, x0:x1], 640), thumb, ""
    # Không tin align(): dựng đứng ảnh gốc rồi cắt 1/4 góc trên phải (nửa phải x nửa trên)
    up = np.rot90(gray, k)
    h, w = up.shape
    return to_b64(np.ascontiguousarray(up[: h // 2, w // 2:]), 480), thumb, problem


def write_preview(rows: list[dict], images: dict, out: Path) -> None:
    trs = []
    for r in rows:
        crop, thumb, problem = images[r["old_name"]]
        name = r["new_name"] or "(không có tên đề xuất)"
        m = re.match(r"\d{4}_(C\d)", name)
        hint = CONDITION_TEXT.get(m.group(1), "") if m else ("Trang chữ số (chụp C1)" if name.startswith("D") else "")
        flags = [f"{problem} → đang hiện 1/4 góc trên phải ảnh gốc (không nắn)"] if problem else []
        if r["note"]:
            flags.append(r["note"])
        cls = ' class="warn"' if flags else ""
        trs.append(
            f"<tr{cls}><td>{r['order']}</td>"
            f"<td><img src='data:image/jpeg;base64,{thumb}' class='thumb'></td>"
            f"<td><b class='new'>{html.escape(name)}</b><div class='cond'>{html.escape(hint)}</div></td>"
            f"<td><img src='data:image/jpeg;base64,{crop}' class='crop'></td>"
            f"<td>{html.escape(r['old_name'])}<br><small>{html.escape(r['capture_time'])}"
            f"<br>{html.escape(r['time_source'])}</small>"
            f"{''.join(f'<div class=flag>⚠ {html.escape(x)}</div>' for x in flags)}</td></tr>")
    out.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Kiểm tra tên ảnh</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:16px;background:#fafafa;color:#222}}
table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:6px;vertical-align:middle;background:#fff}}
th{{position:sticky;top:0;background:#eee;z-index:1}} .new{{font-size:20px}} .crop{{border:1px solid #888}}
.thumb{{border:1px solid #888;display:block}} .cond{{font-size:16px;margin-top:6px;color:#0a4}}
tr.warn td{{background:#fff3cd}} .flag{{color:#a40;font-size:13px;margin-top:4px}}
</style></head><body>
<h2>Kiểm tra tên đề xuất ({len(rows)} ảnh)</h2>
<p>So <b>tên đề xuất</b> với chữ <b>"Mã phiếu"/"Mã trang"</b> trong ảnh cắt, và nhìn ảnh nhỏ để xem
điều kiện chụp có đúng không (C1 đủ sáng · C2 tối · C3 nghiêng · C4 đèn vàng/bóng).
Sai ở đâu thì sửa cột <code>new_name</code> trong <code>mapping.csv</code>.</p>
<table><tr><th>#</th><th>Toàn bộ ảnh</th><th>Tên đề xuất + điều kiện</th><th>Vùng mã trên ảnh</th><th>Ảnh gốc</th></tr>
{''.join(trs)}</table></body></html>""", encoding="utf-8")


# ---------------------------------------------------------------- lệnh plan
def cmd_plan(a) -> None:
    src, work = Path(a.src), Path(a.work)
    jpg_dir = work / "jpg"
    jpg_dir.mkdir(parents=True, exist_ok=True)
    heics = sorted(p for p in src.iterdir() if p.suffix.lower() in (".heic", ".heif"))
    print(f"Tìm thấy {len(heics)} file HEIC trong {src}")

    items = []
    for i, p in enumerate(heics, 1):
        jpg = jpg_dir / f"{p.stem}.jpg"
        if a.force or not jpg.exists():
            convert(p, jpg)
            print(f"  [{i:>2}/{len(heics)}] chuyển {p.name} -> {jpg.name}")
        t, source = capture_time(p)
        items.append({"heic": p, "jpg": jpg, "num": img_number(p), "time": t, "source": source})

    ordered = sort_photos(items)
    names = proposed_names(Path(a.ground_truth))
    expected = N_SHEETS * 2 + N_DIGIT_PAGES
    if len(ordered) != expected:
        print(f"CẢNH BÁO: có {len(ordered)} ảnh, cần {expected}. Tên đề xuất sẽ lệch - kiểm tra kỹ preview.")

    # Đánh dấu chỗ thứ tự theo giờ chụp khác thứ tự số IMG (gợi ý có thể bị lộn)
    by_num_rank = {it["heic"].name: k for k, it in enumerate(sorted(items, key=lambda it: it["num"]))}
    rows = []
    for k, it in enumerate(ordered):
        note = ""
        if it["time"] is not None and by_num_rank[it["heic"].name] != k:
            note = "thứ tự theo giờ chụp khác thứ tự số IMG"
        rows.append({
            "order": k + 1,
            "old_name": it["jpg"].name,
            "heic_name": it["heic"].name,
            "capture_time": it["time"].isoformat(sep=" ") if it["time"] else "",
            "time_source": it["source"] if it["time"] else "thiếu EXIF – xếp theo số IMG",
            "new_name": names[k] if k < len(names) else "",
            "note": note,
        })

    mapping = work / "mapping.csv"
    if mapping.exists() and not a.overwrite_mapping:
        sys.exit(f"DỪNG: {mapping} đã tồn tại (có thể bạn đã sửa tay). Muốn tạo lại preview thì chạy lệnh "
                 f"`preview`; muốn ghi đè mapping thì thêm --overwrite-mapping.")
    with mapping.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    n_missing = sum(1 for r in rows if not r["capture_time"])
    n_swap = sum(1 for r in rows if r["note"])
    print(f"\n{len(rows)} ảnh | thiếu EXIF: {n_missing} | lệch thứ tự IMG: {n_swap}")
    print(f"  Mapping : {mapping}")
    build_preview(work)


def build_preview(work: Path) -> None:
    """Đọc mapping.csv (kể cả bản đã sửa tay) và tạo preview.html."""
    with (work / "mapping.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print("Đang tạo ảnh preview (nắn phẳng + kiểm tra marker từng ảnh)...")
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    templates = load_templates()
    images = {}
    for r in rows:
        tpl = templates["digit" if r["new_name"].upper().startswith("D") else "sheet"]
        images[r["old_name"]] = preview_images(work / "jpg" / r["old_name"], layout, tpl)
        if images[r["old_name"]][2]:
            print(f"  #{r['order']:>2} {r['old_name']} ({r['new_name']}): {images[r['old_name']][2]}")
    write_preview(rows, images, work / "preview.html")
    n_bad = sum(1 for v in images.values() if v[2])
    print(f"\nXong. {len(rows)} ảnh | align() không tin cậy: {n_bad} (đã cắt từ ảnh gốc)")
    print(f"  Preview : {work / 'preview.html'}  (mở bằng trình duyệt)")
    print("Chưa đổi tên/chép ảnh nào. Kiểm tra preview, sửa cột new_name trong mapping.csv nếu cần.")


def cmd_preview(a) -> None:
    build_preview(Path(a.work))


# ---------------------------------------------------------------- lệnh apply (Bước 2)
def cmd_apply(a) -> None:
    work, raw, raw_digits = Path(a.work), Path(a.raw), Path(a.raw_digits)
    with (work / "mapping.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with Path(a.ground_truth).open(encoding="utf-8-sig", newline="") as f:
        expected_conds = {r["sheet_id"]: sorted(c.strip() for c in r["conditions"].split("+"))
                          for r in csv.DictReader(f)}

    errors, plan, seen, conds = [], [], set(), {}
    for r in rows:
        old, new = r["old_name"].strip(), r["new_name"].strip()
        if not new:                     # ảnh đã bị thay (lệnh replace) -> bỏ qua
            continue
        m = SHEET_NAME_RE.match(new)
        if m:
            dst = raw / new
            conds.setdefault(m.group(1), []).append(m.group(2))
        elif DIGIT_NAME_RE.match(new):
            dst = raw_digits / new
        else:
            errors.append(f"#{r['order']} {old}: tên mới '{new}' sai định dạng (cần NNNN_Ck.jpg hoặc DNNN.jpg)")
            continue
        src = work / "jpg" / old
        if new in seen:
            errors.append(f"#{r['order']} {old}: tên mới '{new}' bị trùng")
        seen.add(new)
        if not src.exists():
            errors.append(f"#{r['order']}: không thấy ảnh nguồn {src}")
        if dst.exists():
            errors.append(f"#{r['order']}: {dst} đã tồn tại – không ghi đè")
        plan.append((src, dst))

    # Mỗi phiếu phải có đúng các điều kiện ghi trong ground_truth.csv
    for sid, want in expected_conds.items():
        got = sorted(conds.get(sid, []))
        if got != want:
            errors.append(f"Phiếu {sid}: có ảnh {got or 'không có'}, ground_truth.csv cần {want}")
    for sid in sorted(set(conds) - set(expected_conds)):
        errors.append(f"Phiếu {sid}: không có trong ground_truth.csv")
    n_sheet = sum(1 for _, d in plan if d.parent == raw)
    n_digit = len(plan) - n_sheet
    if n_digit != N_DIGIT_PAGES:
        errors.append(f"Có {n_digit} trang chữ số, cần {N_DIGIT_PAGES}")

    if errors:
        print("DỪNG – chưa chép ảnh nào. Sửa mapping.csv rồi chạy lại:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    raw.mkdir(parents=True, exist_ok=True)
    raw_digits.mkdir(parents=True, exist_ok=True)
    for src, dst in plan:
        shutil.copy2(src, dst)          # copy2: giữ nguyên nội dung + EXIF + thời gian file
    print(f"Đã chép {n_sheet} ảnh phiếu -> {raw}")
    print(f"Đã chép {n_digit} trang chữ số -> {raw_digits}")
    print("Ảnh nguồn (raw_heic/, _prepare/jpg/) giữ nguyên.")


# ---------------------------------------------------------------- lệnh replace (thay ảnh chụp lại)
def cmd_replace(a) -> None:
    src, name, work = Path(a.src), a.name.strip(), Path(a.work)
    if SHEET_NAME_RE.match(name):
        dst = Path(a.raw) / name
    elif DIGIT_NAME_RE.match(name):
        dst = Path(a.raw_digits) / name
    else:
        sys.exit(f"DỪNG: tên '{name}' sai định dạng (cần NNNN_Ck.jpg hoặc DNNN.jpg)")
    rejected = Path(a.rejected) / name
    if rejected.exists():
        sys.exit(f"DỪNG: {rejected} đã tồn tại – không ghi đè ảnh đã loại trước đó")
    if not dst.exists():
        sys.exit(f"DỪNG: không thấy ảnh cũ {dst} để thay")
    if not src.exists():
        sys.exit(f"DỪNG: không thấy ảnh mới {src}")

    mapping = work / "mapping.csv"
    with mapping.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    old_rows = [r for r in rows if r["new_name"].strip() == name]
    if len(old_rows) != 1:
        sys.exit(f"DỪNG: mapping.csv có {len(old_rows)} dòng new_name = {name}, cần đúng 1")

    jpg = work / "jpg" / f"{src.stem}.jpg"
    if not jpg.exists():
        convert(src, jpg)
    t, source = capture_time(src)

    rejected.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(dst, rejected)          # DI CHUYỂN ảnh cũ, không xoá
    shutil.copy2(jpg, dst)

    old = old_rows[0]
    old["new_name"] = ""
    old["note"] = (f"ĐÃ THAY bằng {src.name} – ảnh cũ ở {rejected.relative_to(ROOT).as_posix()} "
                   f"({a.reason})")
    rows.append({
        "order": max(int(r["order"]) for r in rows) + 1,
        "old_name": jpg.name,
        "heic_name": src.name,
        "capture_time": t.isoformat(sep=" ") if t else "",
        "time_source": source if t else "thiếu EXIF",
        "new_name": name,
        "note": f"chụp lại thay {old['heic_name']}",
    })
    with mapping.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {old['heic_name']} -> {rejected.relative_to(ROOT).as_posix()} | "
          f"{src.name} -> {dst.relative_to(ROOT).as_posix()} | mapping.csv đã cập nhật")


def main() -> None:
    ap = argparse.ArgumentParser(description="Chuẩn bị ảnh dữ liệu từ HEIC")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="Bước 1: chuyển JPG, đề xuất tên, xuất mapping.csv + preview.html")
    p.add_argument("--src", default=ROOT / "data" / "raw_heic")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--ground-truth", default=ANSWER_SHEET / "output" / "ground_truth.csv")
    p.add_argument("--force", action="store_true", help="Chuyển lại JPG kể cả khi đã có")
    p.add_argument("--overwrite-mapping", action="store_true", help="Ghi đè mapping.csv đã có")
    p = sub.add_parser("preview", help="Chỉ tạo lại preview.html từ mapping.csv hiện có")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p = sub.add_parser("apply", help="Bước 2: chép ảnh sang data/raw và data/raw_digits theo mapping.csv")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--raw", default=ROOT / "data" / "raw")
    p.add_argument("--raw-digits", default=ROOT / "data" / "raw_digits")
    p.add_argument("--ground-truth", default=ANSWER_SHEET / "output" / "ground_truth.csv")
    p = sub.add_parser("replace", help="Thay 1 ảnh đã chép bằng ảnh chụp lại (ảnh cũ -> data/raw_rejected/)")
    p.add_argument("--src", required=True, help="Ảnh chụp lại (HEIC hoặc JPG), vd data/raw_heic/IMG_4357.JPG")
    p.add_argument("--name", required=True, help="Tên cần thay, vd 0028_C4.jpg hoặc D007.jpg")
    p.add_argument("--reason", required=True, help="Lý do loại ảnh cũ (ghi vào mapping.csv)")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--raw", default=ROOT / "data" / "raw")
    p.add_argument("--raw-digits", default=ROOT / "data" / "raw_digits")
    p.add_argument("--rejected", default=ROOT / "data" / "raw_rejected")
    a = ap.parse_args()
    {"plan": cmd_plan, "preview": cmd_preview, "apply": cmd_apply, "replace": cmd_replace}[a.cmd](a)


if __name__ == "__main__":
    main()
