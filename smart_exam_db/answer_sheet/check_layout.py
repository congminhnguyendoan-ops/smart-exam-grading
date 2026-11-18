import csv
import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")


def render_pdf_page(pdf_path, dpi=300):
    try:
        import fitz
        page = fitz.open(pdf_path)[0]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    except ImportError:
        from pdf2image import convert_from_path
        img = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)[0]
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)


def fake_fill(img, layout, gt, rng):
    out = img.copy()
    r = layout["answers"]["bubble_radius"]

    def blot(cx, cy, rad, dark, cover):
        jitter = rng.normal(0, rad * 0.08, 2)
        cv2.circle(out, (int(cx + jitter[0]), int(cy + jitter[1])), int(rad * cover), int(dark), -1, cv2.LINE_AA)

    for q in range(1, 41):
        a = gt[f"q{q}"]
        centers = layout["answers"]["centers"][str(q)]
        if a == "-":
            continue
        for opt in (a.upper() if len(a) == 1 else a):
            cx, cy = centers[opt]
            if a.islower():
                blot(cx, cy, r, rng.integers(135, 175), rng.uniform(0.75, 0.95))
            else:
                blot(cx, cy, r, rng.integers(20, 70), rng.uniform(0.88, 1.02))

    for field, value in (("sbd", gt["sbd"]), ("exam_code", gt["exam_code"])):
        f = layout[field]
        for col, ch in enumerate(value):
            x, y, w, h = f["handwriting_boxes"][col]
            cv2.putText(out, ch, (int(x + w * 0.18), int(y + h * 0.82)), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
                        2.6, 30, 5, cv2.LINE_AA)
            cx, cy = f["bubbles"][col][int(ch)]
            blot(cx, cy, f["bubble_radius"], rng.integers(20, 70), 0.95)
    return out


def fake_photo(img, rng):
    h, w = img.shape
    canvas = np.full((int(h * 1.25), int(w * 1.3)), 95, np.uint8)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    ox, oy = w * 0.15, h * 0.12
    d = lambda s: rng.uniform(-s, s)
    dst = np.float32([[ox + d(120), oy + d(90)], [ox + w + d(160), oy + 60 + d(90)],
                      [ox + w - 80 + d(120), oy + h + d(120)], [ox + 40 + d(120), oy + h - 30 + d(90)]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (canvas.shape[1], canvas.shape[0]), borderValue=95)
    mask = cv2.warpPerspective(np.full_like(img, 255), M, (canvas.shape[1], canvas.shape[0]))
    photo = np.where(mask > 0, warped, canvas).astype(np.float32)
    gx = np.linspace(0.65, 1.05, photo.shape[1])[None, :]
    photo = photo * gx
    photo = cv2.GaussianBlur(photo, (7, 7), 1.6)
    photo += rng.normal(0, 6, photo.shape)
    photo = np.clip(photo, 0, 255).astype(np.uint8)
    return cv2.resize(photo, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)


def find_markers(gray):
    th = cv2.adaptiveThreshold(cv2.GaussianBlur(gray, (5, 5), 0), 255,
                               cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 15)
    cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    area_img = gray.shape[0] * gray.shape[1]
    cands = []
    for c in cnts:
        a = cv2.contourArea(c)
        if not (area_img * 0.00015 < a < area_img * 0.004):
            continue
        x, y, w, h = cv2.boundingRect(c)
        if not (0.7 < w / h < 1.4):
            continue
        hull = cv2.contourArea(cv2.convexHull(c))
        if hull == 0 or a / hull < 0.9:
            continue
        approx = cv2.approxPolyDP(c, 0.06 * cv2.arcLength(c, True), True)
        if len(approx) != 4:
            continue
        m = cv2.moments(c)
        cands.append((m["m10"] / m["m00"], m["m01"] / m["m00"]))
    if len(cands) < 4:
        raise RuntimeError(f"Chỉ tìm thấy {len(cands)} marker")
    pts = np.array(cands)
    corners = [(0, 0), (gray.shape[1], 0), (gray.shape[1], gray.shape[0]), (0, gray.shape[0])]
    return np.float32([pts[np.argmin(np.hypot(*(pts - c).T))] for c in corners])


def align(gray, layout):
    src = find_markers(gray)
    m = layout["markers"]["centers"]
    dst = np.float32([m["tl"], m["tr"], m["br"], m["bl"]])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(gray, M, tuple(layout["page_px"]))


def darkness(aligned, cx, cy, r):
    x0, y0, x1, y1 = int(cx - r), int(cy - r), int(cx + r), int(cy + r)
    patch = aligned[y0:y1, x0:x1]
    yy, xx = np.ogrid[:patch.shape[0], :patch.shape[1]]
    inside = (xx - r) ** 2 + (yy - r) ** 2 <= (r * 0.75) ** 2
    return float((255 - patch[inside].astype(np.float32)).mean() / 255)


def read_sheet(aligned, layout):
    r = layout["answers"]["bubble_radius"]
    res = {}
    for q in range(1, 41):
        d = {o: darkness(aligned, *layout["answers"]["centers"][str(q)][o], r) for o in "ABCD"}
        filled = [o for o, v in d.items() if v > 0.55]
        faint = [o for o, v in d.items() if 0.25 < v <= 0.55]
        if len(filled) >= 2:
            res[q] = "".join(filled)
        elif len(filled) == 1:
            res[q] = filled[0]
        elif len(faint) == 1:
            res[q] = faint[0].lower()
        else:
            res[q] = "-"
    digits = {}
    for field in ("sbd", "exam_code"):
        f = layout[field]
        s = ""
        for col in f["bubbles"]:
            vals = [darkness(aligned, cx, cy, f["bubble_radius"]) for cx, cy in col]
            s += str(int(np.argmax(vals)))
        digits[field] = s
    return res, digits


def main():
    layout = json.load(open(os.path.join(OUT, "layout.json"), encoding="utf-8"))
    gt = next(csv.DictReader(open(os.path.join(OUT, "ground_truth.csv"), encoding="utf-8-sig")))
    blank = render_pdf_page(os.path.join(OUT, "phieu_danh_so.pdf"))
    if blank.shape[::-1] != tuple(layout["page_px"]):
        blank = cv2.resize(blank, tuple(layout["page_px"]), interpolation=cv2.INTER_AREA)

    ov = cv2.cvtColor(blank, cv2.COLOR_GRAY2BGR)
    r = layout["answers"]["bubble_radius"]
    for q, opts in layout["answers"]["centers"].items():
        for cx, cy in opts.values():
            cv2.circle(ov, (int(cx), int(cy)), int(r), (0, 0, 255), 2)
    for field in ("sbd", "exam_code"):
        f = layout[field]
        for col in f["bubbles"]:
            for cx, cy in col:
                cv2.circle(ov, (int(cx), int(cy)), int(f["bubble_radius"]), (0, 0, 255), 2)
        for x, y, w, h in f["handwriting_boxes"]:
            cv2.rectangle(ov, (int(x), int(y)), (int(x + w), int(y + h)), (255, 0, 0), 2)
    for cx, cy in layout["markers"]["centers"].values():
        s = layout["markers"]["size"] / 2
        cv2.rectangle(ov, (int(cx - s), int(cy - s)), (int(cx + s), int(cy + s)), (0, 200, 0), 3)
    cv2.imwrite(os.path.join(OUT, "overlay_check.png"), ov)

    rng = np.random.default_rng(1)
    filled = fake_fill(blank, layout, gt, rng)
    photo = fake_photo(filled, rng)
    cv2.imwrite(os.path.join(OUT, "synthetic_photo.jpg"), photo, [cv2.IMWRITE_JPEG_QUALITY, 85])

    aligned = align(photo, layout)
    cv2.imwrite(os.path.join(OUT, "synthetic_aligned.jpg"), aligned, [cv2.IMWRITE_JPEG_QUALITY, 85])
    passed = kiem_layout(aligned, layout, gt, "align() bản đầu")
    ans, _ = read_sheet(aligned, layout)

    ok = sum(ans[q] == gt[f"q{q}"] for q in range(1, 41))
    wrong = [(q, gt[f"q{q}"], ans[q]) for q in range(1, 41) if ans[q] != gt[f"q{q}"]]
    print(f"[Tham khảo] rule-based đúng trạng thái {ok}/40; sai (câu, đúng, đoán): {wrong}")
    print("            -> lỗi tập trung ở ô tô mờ khi ánh sáng không đều: lý do cần OMR classifier (Tuần 5)")

    sys.path.insert(0, os.path.dirname(HERE))
    from cv_engine.preprocessing import MA_LY_DO, preprocess_anh
    kq = preprocess_anh(photo, layout)
    if not kq.ok:
        print(f"[preprocess] TỪ CHỐI ảnh chụp giả – {kq.ly_do} ({MA_LY_DO[kq.ly_do]})")
        passed_pp = False
    else:
        cv2.imwrite(os.path.join(OUT, "synthetic_aligned_preprocess.jpg"), kq.anh_nan, [cv2.IMWRITE_JPEG_QUALITY, 85])
        passed_pp = kiem_layout(kq.anh_nan, layout, gt, f"preprocess(), huong_xoay {kq.huong_xoay}°")
    print("KẾT QUẢ LAYOUT:", "KHỚP - có thể in hàng loạt" if passed and passed_pp
          else "CÓ SAI LỆCH - kiểm tra overlay_check.png và 2 dòng kết quả ở trên")
    return 0 if passed and passed_pp else 1


def kiem_layout(aligned, layout, gt, ten) -> bool:
    _, digits = read_sheet(aligned, layout)
    r = layout["answers"]["bubble_radius"]
    pos_ok = 0
    for q in range(1, 41):
        a = gt[f"q{q}"]
        d = {o: darkness(aligned, *layout["answers"]["centers"][str(q)][o], r) for o in "ABCD"}
        if a == "-":
            pos_ok += (max(d.values()) - min(d.values())) < 0.12
        else:
            k = len(a)
            top = "".join(sorted(sorted(d, key=d.get, reverse=True)[:k]))
            pos_ok += top == a.upper()
    print(f"[{ten}] vị trí ô tô đúng: {pos_ok}/40")
    print(f"[{ten}] SBD tô đọc được: {digits['sbd']} (đúng: {gt['sbd']}) | "
          f"mã đề: {digits['exam_code']} (đúng: {gt['exam_code']})")
    passed = pos_ok == 40 and digits["sbd"] == gt["sbd"] and digits["exam_code"] == gt["exam_code"]
    print(f"  -> {ten}: {'KHỚP' if passed else 'CÓ SAI LỆCH'}")
    return passed


if __name__ == "__main__":
    sys.exit(main())
