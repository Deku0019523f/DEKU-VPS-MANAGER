# ============================================================
#   DEKU VPS MANAGER — VPS Utilities
#   ZiVPN      → /etc/zivpn/config.json   (UDP 5667)
#   HTTP Custom → /root/udp/config.json    (UDP 36712)
#   V2Ray      → /etc/v2ray/config.json   (TCP 443 + 80)
# ============================================================

import subprocess, os, json, random, string, socket, base64
from urllib.parse import urlencode, quote
from config import SCRIPTS_DIR, DEFAULT_PORT, VPS_IP
import database as db

ZIVPN_CONFIG     = "/etc/zivpn/config.json"
UDPCUSTOM_CONFIG = "/root/udp/config.json"
V2RAY_CONFIG     = "/etc/v2ray/config.json"

ZIVPN_UDP_PORT     = 5667
ZIVPN_UDP_RANGE    = "6000-19999"
UDPCUSTOM_UDP_PORT = 36712
V2RAY_WS_PATH      = "/deku"
SSH_PORTS = [443, 80, 8080, 8443, 22, 3128]


# ── Génération username SSH ───────────────────────────────────

def generate_username(base: str = "deku") -> str:
    base = "".join(c for c in base.lower() if c.isalnum())[:8] or "deku"
    suffix = "".join(random.choices(string.digits, k=4))
    candidate = f"{base}{suffix}"
    while db.username_exists(candidate):
        suffix = "".join(random.choices(string.digits, k=4))
        candidate = f"{base}{suffix}"
    return candidate


# ── Formats SSH ───────────────────────────────────────────────

def format_http_custom(ip, port, user, pw):
    return f"{ip}:{port}@{user}:{pw}"

def format_zivpn(ip, port, user, pw):
    return f"{user}:{pw}@{ip}:{port}"

def get_config_string(account: dict, account_type: str) -> str:
    ip, port = account["vps_ip"], account["port"]
    user, pw = account["ssh_user"], account["ssh_pass"]
    if account_type == "http":
        return format_http_custom(ip, port, user, pw)
    elif account_type == "zi":
        return format_zivpn(ip, port, user, pw)
    else:
        return (f"HTTP Custom:\n{format_http_custom(ip, port, user, pw)}\n\n"
                f"ZiVPN:\n{format_zivpn(ip, port, user, pw)}")


# ── Génération liens V2Ray ────────────────────────────────────

def _resolve_addresses(vps_ip: str, sni_host: str, sni_mode: str) -> dict:
    """
    Calcule les adresses et headers selon le mode SNI.
    Retourne dict avec address_443, address_80, ws_host, sni_val.
    """
    if sni_host and sni_mode == "reverse":
        # Bug as address : connexion vers le domaine SNI, host header = VPS IP
        return {
            "address_443": sni_host,
            "address_80":  sni_host,
            "ws_host":     vps_ip,
            "sni_val":     sni_host,
        }
    elif sni_host and sni_mode == "default":
        # Default : connexion vers VPS, SNI dans les headers
        return {
            "address_443": vps_ip,
            "address_80":  vps_ip,
            "ws_host":     sni_host,
            "sni_val":     sni_host,
        }
    else:
        # Pas de SNI
        return {
            "address_443": vps_ip,
            "address_80":  vps_ip,
            "ws_host":     "",
            "sni_val":     "",
        }


def make_vmess_link(name: str, address: str, port: int, uuid: str,
                    ws_host: str, sni_val: str, path: str,
                    tls: bool) -> str:
    cfg = {
        "v":    "2",
        "ps":   name,
        "add":  address,
        "port": str(port),
        "id":   uuid,
        "aid":  "0",
        "scy":  "auto",
        "net":  "ws",
        "type": "none",
        "host": ws_host,
        "path": path,
        "tls":  "tls" if tls else "",
        "sni":  sni_val if tls else "",
        "alpn": "",
    }
    return "vmess://" + base64.b64encode(
        json.dumps(cfg, separators=(",", ":")).encode()
    ).decode()


def make_vless_link(name: str, address: str, port: int, uuid: str,
                    ws_host: str, sni_val: str, path: str,
                    tls: bool) -> str:
    params = {
        "encryption": "none",
        "type":       "ws",
        "host":       ws_host,
        "path":       path,
    }
    if tls:
        params["security"] = "tls"
        params["sni"]      = sni_val
    else:
        params["security"] = "none"
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return f"vless://{uuid}@{address}:{port}?{query}#{quote(name)}"


def generate_v2ray_links(acc: dict) -> dict:
    """
    Génère les 2 liens (port 443 et port 80) pour VMess ou VLESS.
    acc = dict depuis v2ray_accounts.
    Retourne {"link_443": "vmess://...", "link_80": "vmess://..."}.
    """
    vps_ip    = acc["vps_ip"]
    uuid      = acc["uuid"]
    protocol  = acc["protocol"]  # vmess | vless
    sni_host  = acc.get("sni_host", "") or ""
    sni_mode  = acc.get("sni_mode", "none") or "none"
    path      = acc.get("path", V2RAY_WS_PATH) or V2RAY_WS_PATH
    name      = f"DEKU-{acc['username']}"

    addr = _resolve_addresses(vps_ip, sni_host, sni_mode)

    make_fn = make_vmess_link if protocol == "vmess" else make_vless_link

    link_443 = make_fn(
        f"{name}-443", addr["address_443"], 443, uuid,
        addr["ws_host"], addr["sni_val"], path, tls=True
    )
    link_80 = make_fn(
        f"{name}-80", addr["address_80"], 80, uuid,
        addr["ws_host"], "", path, tls=False
    )
    return {"link_443": link_443, "link_80": link_80}


# ── Scripts shell ─────────────────────────────────────────────

def run_script(script_name: str, *args) -> tuple:
    path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.isfile(path):
        return (0, f"[DEMO] {script_name} args={args}", "")
    try:
        result = subprocess.run(
            ["bash", path, *[str(a) for a in args]],
            capture_output=True, text=True, timeout=30,
        )
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (1, "", "Timeout 30s")
    except Exception as e:
        return (1, "", str(e))


def create_ssh_user(username, password, days, account_type="both",
                    max_sessions=0) -> bool:
    code, _, _ = run_script(
        "create_user.sh", username, password, days, account_type, max_sessions
    )
    return code == 0


def delete_ssh_user(username, password="") -> bool:
    code, _, _ = run_script("delete_user.sh", username, password)
    return code == 0


def renew_ssh_user(username, days) -> bool:
    code, _, _ = run_script("renew_user.sh", username, days)
    return code == 0


def v2ray_add_user(uuid, protocol, max_sessions=0) -> bool:
    code, _, _ = run_script("v2ray_add_user.sh", uuid, protocol, max_sessions)
    return code == 0


def v2ray_del_user(uuid) -> bool:
    code, _, _ = run_script("v2ray_del_user.sh", uuid)
    return code == 0


# ── Connexions actives ────────────────────────────────────────

def get_active_sessions(ssh_user: str) -> list:
    """
    Retourne la liste des sessions SSH actives pour un user.
    Format : [{"ip": "x.x.x.x", "since": "HH:MM", "pts": "pts/0"}, ...]
    """
    try:
        r = subprocess.run(
            ["bash", "-c",
             f"who | grep '^{ssh_user} ' | awk '{{print $2, $3, $4, $(NF)}}'"],
            capture_output=True, text=True, timeout=5
        )
        sessions = []
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            pts   = parts[0] if len(parts) > 0 else "?"
            date  = parts[1] if len(parts) > 1 else "?"
            heure = parts[2] if len(parts) > 2 else "?"
            ip    = parts[3].strip("()") if len(parts) > 3 else "?"
            sessions.append({"pts": pts, "date": date, "heure": heure, "ip": ip})
        return sessions
    except Exception:
        return []


def get_total_active_sessions() -> dict:
    """
    Retourne le nombre total de sessions SSH actives sur le VPS.
    Format: {"total": N, "users": {"user1": N1, ...}}
    """
    try:
        r = subprocess.run(
            ["bash", "-c", "who | awk '{print $1}' | sort | uniq -c | sort -rn"],
            capture_output=True, text=True, timeout=5
        )
        users = {}
        for line in r.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                count, user = int(parts[0]), parts[1]
                users[user] = count
        return {"total": sum(users.values()), "users": users}
    except Exception:
        return {"total": 0, "users": {}}


# ── Historique connexions ─────────────────────────────────────

def fetch_login_history(ssh_user: str) -> list:
    """
    Lit le dernier historique SSH depuis 'last'.
    Retourne liste de dicts.
    """
    try:
        r = subprocess.run(
            ["bash", "-c",
             f"last {ssh_user} -n 10 --time-format iso 2>/dev/null "
             f"| grep -v 'wtmp\\|btmp\\|^$'"],
            capture_output=True, text=True, timeout=5
        )
        entries = []
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            src_ip   = parts[2] if len(parts) > 2 else "?"
            login_at = parts[3] if len(parts) > 3 else "?"
            entries.append({
                "user":     ssh_user,
                "ip":       src_ip,
                "login_at": login_at,
            })
        return entries[:10]
    except Exception:
        return []


# ── Test de connectivité ──────────────────────────────────────

def test_tcp_port(ip: str, port: int, timeout: float = 4.0) -> bool:
    """Teste si le port TCP répond."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def test_udp_listening(port: int) -> bool:
    """Vérifie si un process écoute sur le port UDP."""
    try:
        r = subprocess.run(
            ["bash", "-c", f"ss -ulnp | grep ':{port} '"],
            capture_output=True, text=True, timeout=5
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def test_account_connectivity(acc: dict) -> dict:
    """
    Teste la connectivité d'un compte SSH.
    Retourne dict avec résultats.
    """
    ip   = acc["vps_ip"]
    port = acc["port"]
    atype = acc.get("account_type", "")

    results = {"ssh_tcp": False, "udp_custom": False, "zivpn_udp": False}
    results["ssh_tcp"] = test_tcp_port(ip, port)

    if atype in ("http", "both"):
        results["udp_custom"] = test_udp_listening(UDPCUSTOM_UDP_PORT)
    if atype in ("zi", "both"):
        results["zivpn_udp"] = test_udp_listening(ZIVPN_UDP_PORT)

    return results


def test_v2ray_connectivity(acc: dict) -> dict:
    """Teste la connectivité d'un compte V2Ray."""
    ip = acc["vps_ip"]
    return {
        "v2ray_443": test_tcp_port(ip, 443),
        "v2ray_80":  test_tcp_port(ip, 80),
    }


# ── Stats système ─────────────────────────────────────────────

def get_vps_stats() -> dict:
    stats = {
        "cpu": "N/A", "ram_used": "N/A", "ram_total": "N/A",
        "disk_used": "N/A", "disk_total": "N/A",
        "uptime": "N/A", "load": "N/A",
        "zivpn_status": "N/A", "udpcustom_status": "N/A",
        "v2ray_status": "N/A", "active_sessions": 0,
    }
    cmds = {
        "cpu":       "top -bn1 | grep 'Cpu(s)' | awk '{print $2\"%\"}'",
        "ram":       "free -m | awk 'NR==2{printf \"%s/%s MB\",$3,$2}'",
        "disk":      "df -h / | awk 'NR==2{print $3\"/\"$2}'",
        "uptime":    "uptime -p",
        "load":      "cat /proc/loadavg | awk '{print $1,$2,$3}'",
        "zivpn":     "systemctl is-active zivpn.service 2>/dev/null || echo inactive",
        "udpcustom": "systemctl is-active udp-custom.service 2>/dev/null || echo inactive",
        "v2ray":     "systemctl is-active v2ray.service 2>/dev/null || echo inactive",
        "sessions":  "who | wc -l",
    }
    try:
        for key, cmd in cmds.items():
            r = subprocess.run(["bash", "-c", cmd],
                               capture_output=True, text=True, timeout=5)
            v = r.stdout.strip()
            if not v:
                continue
            if key == "cpu":
                stats["cpu"] = v
            elif key == "ram":
                p = v.split("/")
                stats["ram_used"]   = p[0].strip()
                stats["ram_total"]  = p[1].strip() if len(p) > 1 else "N/A"
            elif key == "disk":
                p = v.split("/")
                stats["disk_used"]  = p[0].strip()
                stats["disk_total"] = p[1].strip() if len(p) > 1 else "N/A"
            elif key == "uptime":
                stats["uptime"] = v
            elif key == "load":
                stats["load"] = v
            elif key == "zivpn":
                stats["zivpn_status"] = "🟢 Actif" if v == "active" else "🔴 Inactif"
            elif key == "udpcustom":
                stats["udpcustom_status"] = "🟢 Actif" if v == "active" else "🔴 Inactif"
            elif key == "v2ray":
                stats["v2ray_status"] = "🟢 Actif" if v == "active" else "🔴 Inactif"
            elif key == "sessions":
                stats["active_sessions"] = int(v) if v.isdigit() else 0
    except Exception:
        pass
    return stats


# ── Fichiers config téléchargeables ──────────────────────────

def make_config_file(account: dict, account_type: str) -> str:
    ip, port = account["vps_ip"], account["port"]
    user, pw = account["ssh_user"], account["ssh_pass"]
    exp = account.get("expires_at", "N/A")
    mx  = account.get("max_sessions", 0)
    sess_label = "Illimité" if mx == 0 else str(mx)

    lines = [
        "═══════════════════════════════════",
        "     DEKU VPS MANAGER — CONFIG     ",
        "═══════════════════════════════════",
        f"IP           : {ip}",
        f"Port SSH     : {port}",
        f"Username     : {user}",
        f"Password     : {pw}",
        f"Expire       : {exp}",
        f"Sessions max : {sess_label}",
        "",
    ]
    if account_type in ("http", "both"):
        lines += [
            "── HTTP Custom (SSH Mode) ──────────",
            format_http_custom(ip, port, user, pw), "",
            "── HTTP Custom (UDP Mode) ──────────",
            f"Server   : {ip}",
            f"UDP Port : {UDPCUSTOM_UDP_PORT}",
            f"Password : {pw}", "",
        ]
    if account_type in ("zi", "both"):
        lines += [
            "── ZiVPN (SSH Mode) ────────────────",
            format_zivpn(ip, port, user, pw), "",
            "── ZiVPN (UDP Mode) ────────────────",
            f"Server   : {ip}",
            f"UDP Port : {ZIVPN_UDP_PORT}",
            f"Range    : {ZIVPN_UDP_RANGE}",
            f"Password : {pw}", "",
        ]
    lines.append("═══════════════════════════════════")
    path = f"/tmp/deku_ssh_{user}.txt"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def make_v2ray_config_file(acc: dict, links: dict) -> str:
    """Génère un fichier .txt avec les liens V2Ray."""
    exp  = acc.get("expires_at", "N/A")
    mx   = acc.get("max_sessions", 0)
    sess = "Illimité" if mx == 0 else str(mx)
    sni_info = ""
    if acc.get("sni_host"):
        mode = "Reverse SNI" if acc["sni_mode"] == "reverse" else "Default SNI"
        sni_info = f"SNI Host     : {acc['sni_host']}\nSNI Mode     : {mode}\n"

    lines = [
        "═══════════════════════════════════",
        "    DEKU VPS MANAGER — V2RAY      ",
        "═══════════════════════════════════",
        f"Username     : {acc['username']}",
        f"Protocol     : {acc['protocol'].upper()}",
        f"UUID         : {acc['uuid']}",
        f"VPS IP       : {acc['vps_ip']}",
        f"WS Path      : {acc.get('path', V2RAY_WS_PATH)}",
        sni_info,
        f"Expire       : {exp}",
        f"Sessions max : {sess}",
        "",
        f"── Lien Port 443 (TLS) ─────────────",
        links["link_443"],
        "",
        f"── Lien Port 80 (Sans TLS) ─────────",
        links["link_80"],
        "",
        "═══════════════════════════════════",
    ]
    path = f"/tmp/deku_v2ray_{acc['username']}.txt"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path
