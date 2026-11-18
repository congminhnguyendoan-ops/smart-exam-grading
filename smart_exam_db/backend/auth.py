import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

N_SCRYPT, R_SCRYPT, P_SCRYPT = 2 ** 14, 8, 1
MAXMEM = 64 * 1024 * 1024
COOKIE = "se_session"
MAT_KHAU_TOI_THIEU = 8
SO_LAN_SAI_TOI_DA, CUA_SO_GIAY = 5, 15 * 60
THONG_BAO_SAI = "Sai tên đăng nhập hoặc mật khẩu."


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def bam_mat_khau(mat_khau: str, muoi: bytes | None = None) -> str:
    muoi = muoi or os.urandom(16)
    h = hashlib.scrypt(mat_khau.encode("utf-8"), salt=muoi, n=N_SCRYPT, r=R_SCRYPT, p=P_SCRYPT, maxmem=MAXMEM, dklen=32)
    return f"scrypt${N_SCRYPT}${R_SCRYPT}${P_SCRYPT}${_b64(muoi)}${_b64(h)}"


def kiem_mat_khau(mat_khau: str, bam: str | None) -> bool:
    try:
        ten, n, r, p, muoi, h = (bam or "").split("$")
        if ten != "scrypt":
            return False
        mong = _unb64(h)
        tinh = hashlib.scrypt(mat_khau.encode("utf-8"), salt=_unb64(muoi), n=int(n), r=int(r), p=int(p), maxmem=MAXMEM, dklen=len(mong))
        return hmac.compare_digest(tinh, mong)
    except (ValueError, TypeError):
        return False


_BAM_GIA = bam_mat_khau("mat-khau-gia-de-can-bang-thoi-gian", b"\x00" * 16)


def kiem_gia() -> None:
    kiem_mat_khau("x", _BAM_GIA)


def mat_khau_hop_le(mat_khau: str) -> str | None:
    if len(mat_khau) < MAT_KHAU_TOI_THIEU:
        return f"Mật khẩu phải có ít nhất {MAT_KHAU_TOI_THIEU} ký tự."
    if len(mat_khau) > 200:
        return "Mật khẩu quá dài."
    return None


def mat_khau_ngau_nhien(do_dai: int = 14) -> str:
    bang = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(bang) for _ in range(do_dai))


def _vet_mat_khau(bam: str) -> str:
    return hashlib.sha256(bam.encode()).hexdigest()[:12]


def _ky(khoa: str, payload: str) -> str:
    return _b64(hmac.new(khoa.encode(), payload.encode(), hashlib.sha256).digest())


def tao_token(khoa: str, user_id: int, bam_mat_khau_hien_tai: str, gio: float, bay_gio: float | None = None) -> str:
    payload = _b64(json.dumps({"u": user_id, "e": int((bay_gio or time.time()) + gio * 3600), "f": _vet_mat_khau(bam_mat_khau_hien_tai), "n": secrets.token_hex(8)},
                              separators=(",", ":")).encode())
    return f"v1.{payload}.{_ky(khoa, 'v1.' + payload)}"


def doc_token(khoa: str, token: str, bay_gio: float | None = None) -> dict | None:
    try:
        ver, payload, ky = token.split(".")
        if ver != "v1" or not hmac.compare_digest(ky, _ky(khoa, f"v1.{payload}")):
            return None
        d = json.loads(_unb64(payload))
        if not isinstance(d, dict) or int(d["e"]) < (bay_gio or time.time()):
            return None
        return d
    except (ValueError, KeyError, TypeError):
        return None


class GioiHanDangNhap:

    def __init__(self, toi_da: int = SO_LAN_SAI_TOI_DA, cua_so: int = CUA_SO_GIAY):
        self.toi_da, self.cua_so = toi_da, cua_so
        self._sai: dict[tuple, deque] = defaultdict(deque)

    def _don(self, khoa: tuple, bay_gio: float) -> deque:
        d = self._sai[khoa]
        while d and bay_gio - d[0] > self.cua_so:
            d.popleft()
        return d

    def bi_chan(self, khoa: tuple, bay_gio: float | None = None) -> bool:
        return len(self._don(khoa, bay_gio or time.time())) >= self.toi_da

    def ghi_sai(self, khoa: tuple, bay_gio: float | None = None) -> None:
        t = bay_gio or time.time()
        self._don(khoa, t).append(t)

    def xoa(self, khoa: tuple) -> None:
        self._sai.pop(khoa, None)


gioi_han = GioiHanDangNhap()


@dataclass(frozen=True)
class NguoiDung:
    user_id: int
    username: str
    full_name: str
    email: str
    role: str
    demo: bool = False

    @property
    def la_admin(self) -> bool:
        return self.role == "admin"
