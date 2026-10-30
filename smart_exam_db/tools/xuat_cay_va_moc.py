"""
xuat_cay_va_moc.py - Lệnh W3 (30/10/2026): sinh docs/cay_thu_muc.md (Bảng 3.13) và docs/moc_commit.md (Bảng 3.14) TỪ GIT – chỉ những gì có thật.

  python tools/xuat_cay_va_moc.py          # ghi lại hai tệp (chạy lại được; nội dung chỉ đổi khi git đổi)

Cây thư mục = các tệp git đang theo dõi (`git ls-files`, nhánh hiện tại) – tự nhiên không có .venv, .git, data/, __pycache__ (đều nằm trong .gitignore);
kèm một mục riêng liệt kê những gì CHỈ có trên máy này (bị .gitignore bỏ qua) trừ .venv / data / __pycache__, chỉ ghi tên + số tệp.
Mốc commit = `git log --all --date=short` (MỌI nhánh, lệnh Y), gom theo ngày (số commit, số commit chỉ ở nhánh khác, hash đầu / cuối, tiêu đề từng commit,
† = không nằm trong nhánh hiện tại) + bảng tag (ngày, commit, có nằm trong nhánh hiện tại không, các nhánh chứa tag).
Chỉ ĐỌC git, không ghi gì ngoài hai tệp docs.
"""
import subprocess
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent           # smart_exam_db/
BO = (".venv", ".git", "data", "__pycache__")


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def goc_repo() -> Path:
    return Path(git("rev-parse", "--show-toplevel").strip())


def cay(tep: list[str]) -> list[str]:
    """Cây kiểu `tree` từ danh sách đường dẫn (thư mục trước, tệp sau, theo tên); thư mục ghi số tệp bên trong."""
    nut: dict = {}
    for t in tep:
        d = nut
        for phan in t.split("/")[:-1]:
            d = d.setdefault(phan + "/", {})
        d[t.split("/")[-1]] = None

    def dem(d) -> int:
        return sum(1 if v is None else dem(v) for v in d.values())

    ra = []

    def ve(d, tien_to=""):
        muc = sorted(d.items(), key=lambda kv: (kv[1] is None, kv[0].lower()))
        for i, (ten, con) in enumerate(muc):
            cuoi = i == len(muc) - 1
            ra.append(f"{tien_to}{'└── ' if cuoi else '├── '}{ten}{f'  ({dem(con)} tệp)' if con is not None else ''}")
            if con is not None:
                ve(con, tien_to + ("    " if cuoi else "│   "))
    ve(nut)
    return ra


def _ds(*a) -> list[str]:
    """git ls-files -z ở GỐC repo (đường dẫn có dấu tiếng Việt không bị đặt trong nháy)."""
    return [p for p in git("-C", str(goc_repo()), "ls-files", "-z", *a).split("\0") if p]


def chi_tren_may() -> list[str]:
    """Tệp / thư mục bị .gitignore bỏ qua (chỉ có trên máy này), trừ .venv, data, __pycache__ – gom theo thư mục cấp 1 (cấp 2 trong smart_exam_db/)."""
    nhom: dict[str, int] = defaultdict(int)
    for p in _ds("--others", "--ignored", "--exclude-standard"):
        phan = p.split("/")
        if any(x in BO for x in phan):
            continue
        sau = 2 if phan[0] == "smart_exam_db" else 1
        nhom["/".join(phan[:sau]) + ("/" if len(phan) > sau else "")] += 1
    return [f"- `{k}` – {n} tệp" for k, n in sorted(nhom.items())]


def xuat_cay() -> str:
    g = goc_repo()
    theo_doi = _ds()
    moi = _ds("--others", "--exclude-standard")                                         # tệp mới, KHÔNG bị .gitignore (sẽ commit cùng)
    tep = [t for t in theo_doi + moi if not any(x in BO for x in t.split("/"))]
    nhanh, hash_ = git("rev-parse", "--abbrev-ref", "HEAD").strip(), git("rev-parse", "--short", "HEAD").strip()
    d = [f"# Cây thư mục dự án (Bảng 3.13)", "",
         f"Sinh bằng `python tools/xuat_cay_va_moc.py` từ `git ls-files` – nhánh `{nhanh}`, HEAD lúc sinh `{hash_}`.",
         f"Gốc repo: `{g.name}/`. Tệp **trong git**: {len(tep)} tệp ({len(theo_doi)} đã commit + {len(moi)} tệp mới chưa commit lúc sinh, không bị `.gitignore`)."
         " Không có `.venv/`, `.git/`, `data/`, `__pycache__/` (đều trong `.gitignore`).",
         "Số trong ngoặc = số tệp bên trong thư mục (kể cả thư mục con).", "", "```", f"{g.name}/"]
    d += cay(tep)
    d += ["```", "", "## Chỉ có trên máy này (không trong git)",
          "Bị `.gitignore` bỏ qua, ngoài `.venv/`, `data/`, `__pycache__/`; chỉ ghi tên và số tệp (không liệt kê nội dung – có thể chứa ảnh phiếu, cấu hình bí mật):", ""]
    d += chi_tren_may() or ["- (không có)"]
    return "\n".join(d) + "\n"


def xuat_moc() -> str:
    """Lệnh Y: lấy commit từ MỌI nhánh (`git log --all`: nhánh cục bộ, remote, tag); đánh dấu commit KHÔNG nằm trong nhánh hiện tại."""
    dong = git("log", "--all", "--date=short", "--format=%ad%x09%h%x09%s").splitlines()[::-1]          # cũ -> mới
    trong_head = set(git("log", "--format=%h").split())
    theo_ngay: "OrderedDict[str, list]" = OrderedDict()
    for x in dong:
        ngay, h, s = x.split("\t", 2)
        theo_ngay.setdefault(ngay, []).append((h, s.lstrip("﻿")))
    nhanh = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    ds_nhanh = git("branch", "-a", "--format=%(refname:short)").split()
    trong = set(git("tag", "--merged", "HEAD").split())
    tag = [t.split("\t") for t in git("tag", "-l", "--sort=creatordate", "--format=%(refname:short)%09%(creatordate:short)%09%(objectname:short)%09%(subject)").splitlines()]
    chua = {t[0]: ", ".join(f"`{b}`" for b in git("branch", "-a", "--contains", t[0], "--format=%(refname:short)").split()) or "–" for t in tag}
    ngoai = sum(1 for x in dong if x.split("\t")[1] not in trong_head)
    d = ["# Các mốc commit (Bảng 3.14)", "",
         f"Sinh bằng `python tools/xuat_cay_va_moc.py` từ `git log --all --date=short` – **mọi nhánh**: {', '.join(f'`{b}`' for b in ds_nhanh)}"
         f" (nhánh hiện tại `{nhanh}`, HEAD lúc sinh `{git('rev-parse', '--short', 'HEAD').strip()}`).",
         f"Tổng **{len(dong)} commit**, từ {dong[0].split(chr(9))[0] if dong else '–'} đến {dong[-1].split(chr(9))[0] if dong else '–'}, trong **{len(theo_ngay)} ngày có commit**;"
         f" {len(dong) - ngoai} commit nằm trong `{nhanh}`, **{ngoai}** commit chỉ có ở nhánh khác (đánh dấu † ở mục 3). **{len(tag)} tag.**",
         "Ngày = ngày tác giả (author date). Chỉ liệt kê đúng những gì git ghi lại.", "",
         "## 1. Tóm tắt theo ngày", "", "| Ngày | Số commit | Chỉ ở nhánh khác | Commit đầu | Commit cuối |", "|---|---|---|---|---|"]
    d += [f"| {n} | {len(c)} | {sum(h not in trong_head for h, _ in c)} | `{c[0][0]}` | `{c[-1][0]}` |" for n, c in theo_ngay.items()]
    d += ["", f"## 2. Tag ({len(tag)})", "", f"| Tag | Ngày | Commit | Trong `{nhanh}` | Nhánh chứa tag | Tiêu đề commit |", "|---|---|---|---|---|---|"]
    d += [f"| `{t[0]}` | {t[1]} | `{t[2]}` | {'có' if t[0] in trong else 'không'} | {chua[t[0]]} | {t[3].lstrip(chr(0xFEFF)).replace('|', '/')} |" for t in tag] \
        or ["| – | | | | | |"]
    d += ["", f"## 3. Toàn bộ commit theo ngày (cũ → mới; † = không nằm trong `{nhanh}`)"]
    for n, c in theo_ngay.items():
        d += ["", f"### {n} ({len(c)} commit)", ""]
        d += [f"- `{h}`{' †' if h not in trong_head else ''} {s.replace('|', '/')}" for h, s in c]
    return "\n".join(d) + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for ten, nd in (("cay_thu_muc.md", xuat_cay()), ("moc_commit.md", xuat_moc())):
        p = ROOT / "docs" / ten
        p.write_text(nd, encoding="utf-8", newline="\n")
        print(f"Đã ghi {p.relative_to(ROOT)} ({len(nd.splitlines())} dòng)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
