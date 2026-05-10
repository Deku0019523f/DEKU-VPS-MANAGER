# ============================================================
#   DEKU VPS MANAGER — VPS Utilities
#   ZiVPN     → /etc/zivpn/config.json  (UDP port 5667)
#   HTTP Custom → /root/udp/config.json  (UDP port 36712)
#   SSH tunnel  → port 443 prioritaire
# ============================================================

import subprocess
import os
import json
import random
import string
from config import SCRIPTS_DIR, DEFAULT_PORT, VPS_IP
import database as db

# Paths réels sur le VPS
ZIVPN_CONFIG     = "/etc/zivpn/config.json"
UDPCUSTOM_CONFIG = "/root/udp/config.json"

# Ports UDP natifs
ZIVPN_UDP_PORT     = 5667
ZIVPN_UDP_RANGE    = "6000-19999"   # iptables redirige vers 5667
UDPCUSTOM_UDP_PORT = 36712

# Ports SSH valides par priorité
SSH_PORTS = [443, 80, 8080, 8443, 22, 3128]


# ── Génération username système ───────────────────────────────

def generate_username(base: str = "deku") -> str:
    base = "".join(c for c in base.lower() if c.isalnum())[:8] or "deku"
    suffix = "".join(random.choices(string.digits, k=4))
    candidate = f"{base}{suffix}"
    while db.username_exists(candidate):
        suffix = "".join(random.choices(string.digits, k=4))
        candidate = f"{base}{suffix}"
    return candidate


# ── Formats de config client ──────────────────────────────────

def format_http_custom(ip: str, port: int, user: str, pw: str) -> str:
    """Format HTTP Custom (SSH mode) : IP:PORT@USER:PASS"""
    return f"{ip}:{port}@{user}:{pw}"


def format_zivpn(ip: str, port: int, user: str, pw: str) -> str:
    """Format ZiVPN (SSH mode) : USER:PASS@IP:PORT"""
    return f"{user}:{pw}@{ip}:{port}"


def get_config_string(account: dict, account_type: str) -> str:
    ip   = account["vps_ip"]
    port = account["port"]
    user = account["ssh_user"]
    pw   = account["ssh_pass"]
    if account_type == "http":
        return format_http_custom(ip, port, user, pw)
    elif account_type == "zi":
        return format_zivpn(ip, port, user, pw)
    else:
        return (
            f"HTTP Custom:\n{format_http_custom(ip, port, user, pw)}\n\n"
            f"ZiVPN:\n{format_zivpn(ip, port, user, pw)}"
        )


# ── Exécution scripts shell ───────────────────────────────────

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


def create_ssh_user(username: str, password: str,
                    days: int, account_type: str = "both") -> bool:
    """Crée le compte SSH + ajoute le password aux configs UDP."""
    code, out, err = run_script(
        "create_user.sh", username, password, days, account_type
    )
    return code == 0


def delete_ssh_user(username: str, password: str = "") -> bool:
    """Supprime le compte SSH + retire les passwords UDP."""
    code, out, err = run_script("delete_user.sh", username, password)
    return code == 0


def renew_ssh_user(username: str, days: int) -> bool:
    """Renouvelle l'expiration SSH."""
    code, out, err = run_script("renew_user.sh", username, days)
    return code == 0


# ── Stats système ─────────────────────────────────────────────

def get_vps_stats() -> dict:
    stats = {
        "cpu": "N/A", "ram_used": "N/A", "ram_total": "N/A",
        "disk_used": "N/A", "disk_total": "N/A",
        "uptime": "N/A", "load": "N/A",
        "zivpn_status": "N/A", "udpcustom_status": "N/A",
    }
    cmds = {
        "cpu":      "top -bn1 | grep 'Cpu(s)' | awk '{print $2\"%\"}'",
        "ram":      "free -m | awk 'NR==2{printf \"%s/%s MB\",$3,$2}'",
        "disk":     "df -h / | awk 'NR==2{print $3\"/\"$2}'",
        "uptime":   "uptime -p",
        "load":     "cat /proc/loadavg | awk '{print $1,$2,$3}'",
        "zivpn":    "systemctl is-active zivpn.service 2>/dev/null || echo inactive",
        "udpcustom":"systemctl is-active udp-custom.service 2>/dev/null || echo inactive",
    }
    try:
        for key, cmd in cmds.items():
            r = subprocess.run(["bash","-c",cmd],
                               capture_output=True, text=True, timeout=5)
            v = r.stdout.strip()
            if not v:
                continue
            if key == "cpu":
                stats["cpu"] = v
            elif key == "ram":
                p = v.split("/")
                stats["ram_used"]   = p[0].strip()
                stats["ram_total"]  = p[1].strip() if len(p)>1 else "N/A"
            elif key == "disk":
                p = v.split("/")
                stats["disk_used"]  = p[0].strip()
                stats["disk_total"] = p[1].strip() if len(p)>1 else "N/A"
            elif key == "uptime":
                stats["uptime"] = v
            elif key == "load":
                stats["load"] = v
            elif key == "zivpn":
                stats["zivpn_status"] = "🟢 Actif" if v=="active" else "🔴 Inactif"
            elif key == "udpcustom":
                stats["udpcustom_status"] = "🟢 Actif" if v=="active" else "🔴 Inactif"
    except Exception:
        pass
    return stats


# ── Fichier config téléchargeable ─────────────────────────────

def make_config_file(account: dict, account_type: str) -> str:
    """Génère un fichier .txt complet et retourne son chemin."""
    ip   = account["vps_ip"]
    port = account["port"]
    user = account["ssh_user"]
    pw   = account["ssh_pass"]
    exp  = account.get("expires_at", "N/A")

    lines = [
        "═══════════════════════════════════",
        "     DEKU VPS MANAGER — CONFIG     ",
        "═══════════════════════════════════",
        f"IP       : {ip}",
        f"Port SSH : {port}",
        f"Username : {user}",
        f"Password : {pw}",
        f"Expire   : {exp}",
        "",
    ]

    if account_type in ("http", "both"):
        lines += [
            "── HTTP Custom (SSH Mode) ──────────",
            format_http_custom(ip, port, user, pw),
            "",
            "── HTTP Custom (UDP Mode) ──────────",
            f"Server   : {ip}",
            f"UDP Port : {UDPCUSTOM_UDP_PORT}",
            f"Password : {pw}",
            "",
        ]

    if account_type in ("zi", "both"):
        lines += [
            "── ZiVPN (SSH Mode) ────────────────",
            format_zivpn(ip, port, user, pw),
            "",
            "── ZiVPN (UDP Mode) ────────────────",
            f"Server   : {ip}",
            f"UDP Port : {ZIVPN_UDP_PORT}",
            f"UDP Range: {ZIVPN_UDP_RANGE}",
            f"Password : {pw}",
            "",
        ]

    lines.append("═══════════════════════════════════")

    path = f"/tmp/deku_config_{user}.txt"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path
