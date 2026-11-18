import ipaddress
import os
import socket
from dataclasses import dataclass

CONG_MAC_DINH = 8000
TU_KHOA_AO = ("vethernet", "wsl", "hyper-v", "docker", "virtualbox", "vmware", "vpn", "tap-", "tap ", "tun", "tailscale", "zerotier",
              "hamachi", "bluetooth", "loopback", "npcap")
TEN_LUAT_TUONG_LUA = "SmartExam-{cong}-LAN"


@dataclass(frozen=True)
class UngVien:
    ip: str
    card: str
    ao: bool = False
    mac_dinh: bool = False
    hotspot: bool = False


def la_ip_lan(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and a.is_private and not a.is_loopback and not a.is_link_local and not a.is_unspecified


def la_card_ao(ten: str) -> bool:
    t = ten.lower()
    if "wi-fi direct" in t:
        return False
    return any(k in t for k in TU_KHOA_AO)


def chon_ung_vien(cap: list[tuple[str, str]], ip_mac_dinh: str | None = None) -> list[UngVien]:
    ra, da = [], set()
    for card, ip in cap:
        if ip in da or not la_ip_lan(ip):
            continue
        da.add(ip)
        ra.append(UngVien(ip=ip, card=card, ao=la_card_ao(card), mac_dinh=ip == ip_mac_dinh, hotspot=ip.startswith("192.168.137.")))
    thu_tu = {"192": 0, "10": 1, "172": 2}
    return sorted(ra, key=lambda u: (u.ao, not u.mac_dinh, thu_tu.get(u.ip.split(".")[0], 3), u.ip))


def _ip_tuyen_mac_dinh() -> str | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _liet_ke_card() -> list[tuple[str, str]]:
    try:
        import ifaddr
        return [(a.nice_name, i.ip) for a in ifaddr.get_adapters() for i in a.ips if isinstance(i.ip, str)]
    except ImportError:
        try:
            return [("?", x[4][0]) for x in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
        except OSError:
            return []


def ung_vien_ip() -> list[UngVien]:
    return chon_ung_vien(_liet_ke_card(), _ip_tuyen_mac_dinh())


def url_dien_thoai(ip: str, cong: int = CONG_MAC_DINH) -> str:
    return f"http://{ip}:{cong}/m"


def qr_svg(noi_dung: str, ti_le: int = 6) -> str:
    try:
        import segno
    except ImportError:
        return ""
    import io
    b = io.BytesIO()
    segno.make(noi_dung, error="m").save(b, kind="svg", scale=ti_le, border=2, xmldecl=False, svgns=True)
    return b.getvalue().decode("utf-8")


def qr_terminal(noi_dung: str) -> str:
    try:
        import segno
    except ImportError:
        return ""
    import io
    b = io.StringIO()
    segno.make(noi_dung, error="m").terminal(out=b, compact=True, border=2)
    return b.getvalue()


def lenh_tuong_lua(cong: int = CONG_MAC_DINH) -> dict[str, str]:
    ten = TEN_LUAT_TUONG_LUA.format(cong=cong)
    return {"mo": f'New-NetFirewallRule -DisplayName "{ten}" -Direction Inbound -Protocol TCP -LocalPort {cong} -Action Allow '
                  f'-Profile Public,Private -RemoteAddress LocalSubnet',
            "go": f'Remove-NetFirewallRule -DisplayName "{ten}"'}


def dang_mo_lan() -> bool:
    return os.environ.get("SMART_EXAM_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost", "::1")


def thong_tin_ket_noi(cong: int = CONG_MAC_DINH) -> dict:
    uv = ung_vien_ip()
    chinh = next((u for u in uv if not u.ao), uv[0] if uv else None)
    url = url_dien_thoai(chinh.ip, cong) if chinh else None
    return {"lan_bat": dang_mo_lan(), "cong": cong, "url": url, "qr_svg": qr_svg(url) if url else "",
            "ung_vien": [{"ip": u.ip, "card": u.card, "ao": u.ao, "mac_dinh": u.mac_dinh, "hotspot": u.hotspot, "url": url_dien_thoai(u.ip, cong)} for u in uv]}
