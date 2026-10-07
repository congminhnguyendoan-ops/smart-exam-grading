

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

Preview nắn bằng cv_engine.preprocessing.preprocess() (Tuần 4 Bước 6 – thay align() cũ, vốn chọn nhầm marker mà không
  báo lỗi): ảnh bị từ chối ghi rõ mã lý do + thông báo (MA_LY_DO) và hiện 1/4 góc trên phải của ảnh GỐC (không nắn).
  Mặc định chỉ ảnh dev (`--split dev` -> preview_dev.html); cả 94 ảnh cần `--split tat_ca --xac-nhan-test` (-> preview.html).

Lệnh `measure`: đo ảnh chụp lại trước khi `replace` – preprocess() OK / từ chối, khoảng cách marker tới mép
  ảnh, "độ phối cảnh" = min(trên/dưới, trái/phải và nghịch đảo) của tứ giác 4 tâm marker
  (1,0 = chụp thẳng; ảnh C3 cần nhỏ như các ảnh C3 khác). `--ref` in khoảng C1/C3 của data/raw.
  Marker được tìm độc lập với find_markers(): mỗi góc ảnh dò khối đen vuông gần góc nhất, nhiều ngưỡng
  (nền bàn trắng làm 1 ngưỡng Otsu thất bại). Khối chạm mép vùng tìm -> coi như không có marker trọn vẹn.

Chạy (từ thư mục smart_exam_db/):
  python tools/prepare_photos.py plan
  python tools/prepare_photos.py preview                 # chỉ dev -> preview_dev.html
  python tools/prepare_photos.py apply
  python tools/prepare_photos.py replace --src data/raw_heic/IMG_4357.JPG --name 0028_C4.jpg --reason "..."
  python tools/prepare_photos.py measure data/raw_heic/IMG_4379.JPG --ref
  python tools/prepare_photos.py verify-ids

Lệnh `verify-ids`: đọc "Mã phiếu" in sẵn trên cả 80 ảnh data/raw, so với tên file (phát hiện ảnh tráo tên,
  vd 0002_C3 <-> 0003_C3 phát hiện 03/10/2026). Nắn bằng marker_centers() (không qua align()), thử 4
  chiều, so vùng 2 chữ số cuối với 40 trang phieu_danh_so.pdf -> data/_prepare/verify_ids.html.
  Mặc định chỉ ảnh dev; ảnh test 0035–0040 cần --xac-nhan-test (cv_engine/tap_du_lieu.py).
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
sys.path.insert(0, str(ROOT))
from cv_engine.preprocessing import MA_LY_DO, nap_layout, preprocess  # noqa: E402
from cv_engine.tap_du_lieu import chan_test, la_test, tap_cua  # noqa: E402

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
MARKER_CHECK_MM = 3.0       # nửa cạnh ô kiểm tra ở tâm marker (marker 8 mm) – marker_fill (eval phép 1)
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


def nan_anh(path: Path, loai: str) -> tuple:
    """preprocess() (Bước 6, thay check_align()/align() cũ) -> (anh_nan hoặc None, lý do – rỗng nếu OK).
    Lý do = mã + thông báo (MA_LY_DO); preprocess đã tự quyết chiều phiếu bằng nội dung, không cần thử 4 chiều."""
    kq = preprocess(path, nap_layout(loai))
    return (kq.anh_nan, "") if kq.ok else (None, f"TỪ CHỐI – {kq.ly_do} ({MA_LY_DO[kq.ly_do]})")


def cat_vung_ma(anh_nan, layout=None) -> np.ndarray:
    """Vùng chữ 'Mã phiếu'/'Mã trang' trên ảnh đã nắn."""
    px_per_mm = (layout or nap_layout())["dpi"] / 25.4
    x0, y0, x1, y1 = (round(v * px_per_mm) for v in CODE_BOX_MM)
    return anh_nan[y0:y1, x0:x1]


def preview_images(jpg: Path, loai: str) -> tuple[str, str, str]:
    """(ảnh vùng mã đã cắt, ảnh thu nhỏ toàn trang, lý do nếu bị từ chối – rỗng nếu OK)."""
    bgr = cv2.imdecode(np.fromfile(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)   # fromfile: an toàn với đường dẫn Unicode
    thumb = to_b64(bgr, 320)
    aligned, problem = nan_anh(jpg, loai)
    if aligned is not None:
        return to_b64(cat_vung_ma(aligned), 640), thumb, ""
    # Bị từ chối: cắt 1/4 góc trên phải của ảnh GỐC (không nắn, không dựng đứng) để đọc mã bằng mắt
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    return to_b64(np.ascontiguousarray(gray[: h // 2, w // 2:]), 480), thumb, problem


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
    build_preview(work, "tat_ca", a.xac_nhan_test)     # nhận ảnh mới gồm cả phiếu test -> cần --xac-nhan-test


def build_preview(work: Path, split: str = "tat_ca", xac_nhan_test: bool = False) -> None:
    """Đọc mapping.csv (kể cả bản đã sửa tay) và tạo preview.html (tat_ca) / preview_dev.html (dev).
    split 'dev': chỉ dòng có tên mới thuộc dev (0001–0034, D001–D010); dòng ảnh đã bị thay (tên rỗng) bỏ qua.
    split 'tat_ca' đọc cả ảnh test -> bắt buộc xac_nhan_test (chặn TRƯỚC khi đọc ảnh)."""
    with (work / "mapping.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if split == "dev":
        n0 = len(rows)
        rows = [r for r in rows if r["new_name"] and tap_cua(r["new_name"]) == "dev"]
        print(f"Chỉ ảnh dev: {len(rows)}/{n0} dòng mapping (bỏ ảnh test và ảnh đã bị thay).")
        out = work / "preview_dev.html"
    else:
        chan_test([r["new_name"] for r in rows], xac_nhan_test, "preview --split tat_ca")
        out = work / "preview.html"
    print("Đang tạo ảnh preview (preprocess() từng ảnh)...")
    images = {}
    for r in rows:
        loai = "chu_so" if r["new_name"].upper().startswith("D") else "phieu"
        images[r["old_name"]] = preview_images(work / "jpg" / r["old_name"], loai)
        if images[r["old_name"]][2]:
            print(f"  #{r['order']:>2} {r['old_name']} ({r['new_name']}): {images[r['old_name']][2]}")
    write_preview(rows, images, out)
    n_bad = sum(1 for v in images.values() if v[2])
    print(f"\nXong. {len(rows)} ảnh | bị preprocess() từ chối: {n_bad} (đã cắt từ ảnh gốc)")
    print(f"  Preview : {out}  (mở bằng trình duyệt)")
    print("Chưa đổi tên/chép ảnh nào. Kiểm tra preview, sửa cột new_name trong mapping.csv nếu cần.")


def cmd_preview(a) -> None:
    build_preview(Path(a.work), a.split, a.xac_nhan_test)


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


# ---------------------------------------------------------------- lệnh measure (đo ảnh chụp lại)
def marker_centers(gray) -> dict:
    """Tâm + khung bao của marker ở mỗi góc ảnh, tìm độc lập với find_markers()."""
    H, W = gray.shape
    sx, sy = int(W * 0.35), int(H * 0.35)
    out = {}
    for c, (y0, x0) in {"tl": (0, 0), "tr": (0, W - sx), "bl": (H - sy, 0), "br": (H - sy, W - sx)}.items():
        patch = gray[y0:y0 + sy, x0:x0 + sx]
        for f in (0.5, 0.4, 0.3, 0.2):                 # ngưỡng = f × độ sáng trung vị của ảnh
            n, _, st, ct = cv2.connectedComponentsWithStats((patch < np.median(gray) * f).astype(np.uint8))
            best = None
            for i in range(1, n):
                x, y, w, h, a = st[i]
                inside = x > 0 and y > 0 and x + w < sx and y + h < sy
                if inside and 1500 < a < 60000 and a / (w * h) > 0.7 and 0.4 < w / h < 2.5:
                    d = np.hypot(x + w / 2 - (0 if c[1] == "l" else sx), y + h / 2 - (0 if c[0] == "t" else sy))
                    if best is None or d < best[0]:
                        best = (d, ct[i], (x0 + x, y0 + y, w, h))
            if best:
                out[c] = {"center": np.array([x0 + best[1][0], y0 + best[1][1]]), "box": best[2]}
                break
    return out


def perspective(m: dict) -> float:
    """min(trên/dưới, trái/phải và nghịch đảo): 1,0 = thẳng; càng nhỏ càng nghiêng."""
    d = lambda a, b: np.linalg.norm(m[a]["center"] - m[b]["center"])  # noqa: E731
    tb, lr = d("tl", "tr") / d("bl", "br"), d("tl", "bl") / d("tr", "br")
    return min(tb, 1 / tb, lr, 1 / lr)


def measure_one(gray) -> dict:
    m = marker_centers(gray)
    H, W = gray.shape
    res = {"found": len(m), "persp": perspective(m) if len(m) == 4 else None, "margins": {}}
    for c, v in m.items():
        x, y, w, h = v["box"]
        res["margins"][c] = min(x, y, W - x - w, H - y - h)
    res["min_margin"] = min(res["margins"].values()) if res["margins"] else None
    return res


def cmd_measure(a) -> None:
    out_dir = Path(a.work) / "measure"
    out_dir.mkdir(parents=True, exist_ok=True)
    (Path(a.work) / "jpg").mkdir(parents=True, exist_ok=True)
    for s in a.photos:
        src = Path(s)
        jpg = Path(a.work) / "jpg" / f"{src.stem}.jpg"
        if not jpg.exists():
            convert(src, jpg)
        gray = cv2.imdecode(np.fromfile(jpg, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        r = measure_one(gray)
        aligned, problem = nan_anh(jpg, "phieu")
        margins = " ".join(f"{CORNER_VI[c]}={r['margins'].get(c, '—')}" for c in CORNERS)
        persp = f"{r['persp']:.2f}" if r["persp"] is not None else "—"
        print(f"{src.name}: marker trọn vẹn {r['found']}/4 | cách mép (px) {margins} | "
              f"độ phối cảnh {persp} | preprocess(): {problem or 'OK'}")
        # Vùng mã phiếu để đọc bằng mắt: cắt từ ảnh đã nắn nếu OK, không thì 40% góc trên phải ảnh GỐC (không nắn)
        if aligned is not None:
            crop = cat_vung_ma(aligned)
        else:
            h, w = gray.shape
            crop = np.ascontiguousarray(gray[: int(h * 0.4), int(w * 0.4):])
        cv2.imencode(".jpg", crop)[1].tofile(out_dir / f"{src.stem}_vung_ma.jpg")
    print(f"Ảnh vùng mã phiếu để đọc bằng mắt: {out_dir}")
    if a.ref:
        print("\nKhoảng tham chiếu trong data/raw – CHỈ ảnh dev (bỏ ảnh nằm ngang, ảnh thiếu marker):")
        for cond in ("C1", "C3"):
            vals = []
            for p in sorted(Path(a.raw).glob(f"*_{cond}.jpg")):
                if la_test(p):
                    continue
                g = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                if g.shape[1] > g.shape[0]:
                    continue
                v = measure_one(g)["persp"]
                if v is not None:
                    vals.append(v)
            print(f"  {cond}: {len(vals)} ảnh | độ phối cảnh min {min(vals):.2f}  "
                  f"trung vị {np.median(vals):.2f}  max {max(vals):.2f}")


# ---------------------------------------------------------------- lệnh verify-ids (đọc mã phiếu in sẵn)
ID_SEARCH_MM = 6.0          # giấy cong / marker_centers lệch -> tìm mã phiếu trong ±6 mm
# Kết quả tự động chỉ tin khi: chữ 'Mã phiếu: 00' khớp tốt (nắn đúng chỗ) VÀ mỗi chữ số hơn hẳn chữ số thứ
# hai. Ngược lại (marker_centers bắt nhầm marker ở ảnh tối C2; ảnh C3 chữ quá nhỏ, nhầm 4/5) -> đọc bằng mắt.
ID_MIN_ANCHOR, ID_MIN_MARGIN = 0.70, 0.10


def id_templates(layout) -> dict:
    """Mẫu từ 40 trang phieu_danh_so.pdf (@ dpi của layout):
    - anchor: phần chữ chung 'Mã phiếu: 00' (giống nhau mọi trang) để định vị;
    - tens/units: ảnh chữ số hàng chục (0-4) và hàng đơn vị (0-9), tách đôi vùng các trang khác nhau.
    Nhận diện TỪNG chữ số: so cả cụm '0001' với '0011' chỉ chênh 0,02 (thử 03/10/2026), không phân biệt được."""
    doc = pymupdf.open(ANSWER_SHEET / "output" / "phieu_danh_so.pdf")
    px_mm = layout["dpi"] / 25.4
    x0, y0, x1, y1 = (round(v * px_mm) for v in CODE_BOX_MM)
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=layout["dpi"], colorspace=pymupdf.csGRAY)
        pages.append(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)[y0:y1, x0:x1].copy())
    diff = np.zeros_like(pages[0], dtype=bool)
    for p in pages[1:]:
        diff |= np.abs(p.astype(int) - pages[0]) > 60
    ys, xs = np.nonzero(diff)
    pad = round(0.3 * px_mm)
    dy0, dy1, dx0, dx1 = ys.min() - pad, ys.max() + pad, xs.min() - pad, xs.max() + pad
    mid = (dx0 + dx1) // 2                                   # chữ số DejaVu Bold rộng bằng nhau
    ink = np.nonzero((pages[0] < 128).any(axis=0))[0]         # cột có mực: từ chữ 'M' tới hết số
    anchor = (int(ink.min()) - pad, dy0, dx0, dy1)            # 'Mã phiếu: 00'
    blur = lambda im: cv2.GaussianBlur(im, (5, 5), 0)         # noqa: E731  ảnh chụp luôn hơi mờ
    return {
        "page_box": (x0, y0),
        "anchor_box": anchor,
        "anchor": blur(pages[0][anchor[1]:anchor[3], anchor[0]:anchor[2]]),
        "tens_box": (dx0, dy0, mid, dy1), "units_box": (mid, dy0, dx1, dy1),
        "tens": {t: blur(pages[max(t * 10, 1) - 1][dy0:dy1, dx0:mid]) for t in range(5)},
        "units": {u: blur(pages[(u or 10) - 1][dy0:dy1, mid:dx1]) for u in range(10)},
    }


def best_digit(win, temps: dict) -> tuple:
    """(chữ số khớp nhất, điểm, điểm chữ số thứ hai) – so trong cửa sổ nhỏ quanh vị trí chữ số."""
    sc = {d: float(cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED).max()) for d, t in temps.items()}
    order = sorted(sc, key=sc.get, reverse=True)
    return order[0], sc[order[0]], sc[order[1]]


def read_sheet_id(gray, layout, tp, sheet_template) -> dict:
    """Nắn bằng marker_centers() (KHÔNG dùng align()); chiều xoay chọn bằng NCC cả trang với mẫu phiếu
    (ảnh có thể nằm ngang/ngược); định vị bằng chữ 'Mã phiếu: 00' rồi đọc từng chữ số."""
    m = marker_centers(gray)
    if len(m) < 4:
        return {"error": f"chỉ tìm thấy {len(m)}/4 marker"}
    dst = np.float32([layout["markers"]["centers"][c] for c in CORNERS])
    best = None
    for k in range(4):
        src = np.float32([m[CORNERS[(i + k) % 4]]["center"] for i in range(4)])
        page = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(src, dst), tuple(layout["page_px"]))
        score = float((ncc_prep(page) * sheet_template).sum())
        if best is None or score > best[0]:
            best = (score, k, page)
    _, k, page = best
    px0, py0 = tp["page_box"]
    s = round(ID_SEARCH_MM * layout["dpi"] / 25.4)
    ax0, ay0, ax1, ay1 = tp["anchor_box"]
    wx0, wy0 = px0 + ax0 - s, py0 + ay0 - s
    win = page[wy0:py0 + ay1 + s, wx0:px0 + ax1 + s]
    res = cv2.matchTemplate(win, tp["anchor"], cv2.TM_CCOEFF_NORMED)
    _, anchor_score, _, (bx, by) = cv2.minMaxLoc(res)
    dx, dy = wx0 + bx - (px0 + ax0), wy0 + by - (py0 + ay0)     # độ lệch so với vị trí lý thuyết
    out = {"k": k, "anchor": anchor_score}
    e = 4                                                        # px tìm thêm quanh từng chữ số
    for key in ("tens", "units"):
        x0, y0, x1, y1 = tp[f"{key}_box"]
        sub = page[py0 + y0 + dy - e:py0 + y1 + dy + e, px0 + x0 + dx - e:px0 + x1 + dx + e]
        out[key] = best_digit(sub, tp[key])
    out["id"] = f"00{out['tens'][0]}{out['units'][0]}"
    out["margin"] = min(out["tens"][1] - out["tens"][2], out["units"][1] - out["units"][2])
    out["crop"] = page[py0 + ay0 + dy - s:py0 + ay1 + dy + s, px0 + ax0 + dx - s:px0 + tp["units_box"][2] + dx + s]
    return out


def cmd_verify_ids(a) -> None:
    layout = json.loads((ANSWER_SHEET / "output" / "layout.json").read_text(encoding="utf-8"))
    tp = id_templates(layout)
    sheet_template = load_templates()["sheet"]
    out_dir = Path(a.work) / "verify_ids"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    rows = []                                   # (tên, mã theo tên file, trạng thái, mô tả)
    anh = [p for p in sorted(Path(a.raw).glob("*.jpg")) if SHEET_NAME_RE.match(p.name)]
    if not a.xac_nhan_test:
        n_test = sum(la_test(p) for p in anh)
        anh = [p for p in anh if not la_test(p)]
        print(f"Chỉ ảnh dev: {len(anh)} ảnh (bỏ {n_test} ảnh test 0035–0040 – cần --xac-nhan-test).")
    for p in anh:
        mt = SHEET_NAME_RE.match(p.name)
        gray = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        r = read_sheet_id(gray, layout, tp, sheet_template)
        if "error" not in r and r["anchor"] >= ID_MIN_ANCHOR and r["margin"] >= ID_MIN_MARGIN:
            status = "khop" if r["id"] == mt.group(1) else "LECH"
            cv2.imencode(".jpg", r["crop"])[1].tofile(out_dir / p.name)
            info = (f"đọc {r['id']} (neo {r['anchor']:.2f}; chục {r['tens'][1]:.2f}, đơn vị {r['units'][1]:.2f}; "
                    f"hơn chữ số thứ hai ≥ {r['margin']:.2f})")
        else:
            status = "mat"
            why = r.get("error") or (f"tự động đọc {r['id']} nhưng không chắc (neo {r['anchor']:.2f}, "
                                     f"hơn chữ số thứ hai {r['margin']:.2f})")
            # Ảnh GỐC, không nắn: phần trên để đọc "Mã phiếu" bằng mắt. Ảnh nằm ngang (0006_C2/C3) không
            # biết dựng theo chiều nào -> ghép cả 2 chiều xoay 90° cạnh nhau.
            ups = [gray] if gray.shape[0] >= gray.shape[1] else [np.rot90(gray, 1), np.rot90(gray, -1)]
            crops = [u[: int(u.shape[0] * 0.3), int(u.shape[1] * 0.35):] for u in ups]
            cv2.imencode(".jpg", np.ascontiguousarray(np.hstack(crops)))[1].tofile(out_dir / p.name)
            info = f"CẦN ĐỌC BẰNG MẮT – {why}"
        print(f"{p.name}: {info}" + ("  -> LỆCH – NGHI TRÁO TÊN" if status == "LECH" else ""))
        rows.append((p.name, mt.group(1), status, info))

    count = {s: sum(r[2] == s for r in rows) for s in ("khop", "LECH", "mat")}
    print(f"\nTự động chắc chắn: {count['khop']} ảnh khớp tên file, {count['LECH']} ảnh LỆCH "
          f"({', '.join(r[0] for r in rows if r[2] == 'LECH') or 'không có'}); "
          f"{count['mat']} ảnh cần đọc bằng mắt: {', '.join(r[0] for r in rows if r[2] == 'mat')}")
    title = {"LECH": "LỆCH tên file – nghi tráo tên", "mat": "Cần đọc bằng mắt (ảnh gốc, không nắn)",
             "khop": "Tự động: khớp tên file"}
    parts = []
    for s in ("LECH", "mat", "khop"):
        cells = "".join(f"<div class='c {s}'><b>{n}</b><br><small>{html.escape(info)}</small>"
                        f"<img src='verify_ids/{n}'></div>" for n, _, st, info in rows if st == s)
        parts.append(f"<h3>{title[s]} ({count[s]} ảnh)</h3>{cells or '<p>Không có.</p>'}")
    page = Path(a.work) / "verify_ids.html"
    page.write_text(f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Mã phiếu 80 ảnh</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:16px}} .c{{display:inline-block;margin:6px;padding:4px;
border:1px solid #ccc;vertical-align:top;max-width:440px}} .LECH{{border:3px solid #c00}} .mat{{border:2px solid #d80}}
img{{max-width:430px;display:block}}</style>
</head><body><h2>Mã phiếu in trên {len(rows)} ảnh so với tên file (không qua preprocess)</h2>
<p>Tự động: nắn bằng marker_centers(), đọc từng chữ số. Chỉ tin khi neo 'Mã phiếu' ≥ {ID_MIN_ANCHOR} và mỗi
chữ số hơn chữ số thứ hai ≥ {ID_MIN_MARGIN}; còn lại cắt từ ảnh gốc để đọc bằng mắt.</p>
{''.join(parts)}</body></html>""", encoding="utf-8")
    print(f"Trang xem bằng mắt: {page}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Chuẩn bị ảnh dữ liệu từ HEIC")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="Bước 1: chuyển JPG, đề xuất tên, xuất mapping.csv + preview.html")
    p.add_argument("--src", default=ROOT / "data" / "raw_heic")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--ground-truth", default=ANSWER_SHEET / "output" / "ground_truth.csv")
    p.add_argument("--force", action="store_true", help="Chuyển lại JPG kể cả khi đã có")
    p.add_argument("--overwrite-mapping", action="store_true", help="Ghi đè mapping.csv đã có")
    p.add_argument("--xac-nhan-test", action="store_true", help="preview đọc cả ảnh test 0035–0040")
    p = sub.add_parser("preview", help="Tạo lại preview từ mapping.csv hiện có (mặc định chỉ dev -> preview_dev.html)")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--split", default="dev", choices=["dev", "tat_ca"])
    p.add_argument("--xac-nhan-test", action="store_true", help="bắt buộc với --split tat_ca (đọc ảnh test)")
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
    p = sub.add_parser("measure", help="Đo marker/độ phối cảnh của ảnh chụp lại (không chép, không đổi tên)")
    p.add_argument("photos", nargs="+", help="Ảnh trong data/raw_heic/ (HEIC hoặc JPG)")
    p.add_argument("--ref", action="store_true", help="In thêm khoảng độ phối cảnh C1/C3 của data/raw")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--raw", default=ROOT / "data" / "raw")
    p = sub.add_parser("verify-ids", help="Đọc 'Mã phiếu' in sẵn trên ảnh data/raw (mặc định dev), so với tên file")
    p.add_argument("--work", default=ROOT / "data" / "_prepare")
    p.add_argument("--raw", default=ROOT / "data" / "raw")
    p.add_argument("--xac-nhan-test", action="store_true", help="đọc cả ảnh test 0035–0040")
    a = ap.parse_args()
    {"plan": cmd_plan, "preview": cmd_preview, "apply": cmd_apply, "replace": cmd_replace,
     "measure": cmd_measure, "verify-ids": cmd_verify_ids}[a.cmd](a)


if __name__ == "__main__":
    main()
