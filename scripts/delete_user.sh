#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — delete_user.sh
#   Usage: ./delete_user.sh <username> <password>
# ============================================================

USERNAME="$1"
PASSWORD="$2"

ZIVPN_CONFIG="/etc/zivpn/config.json"
UDP_CUSTOM_CONFIG="/root/udp/config.json"

if [[ -z "$USERNAME" ]]; then
    echo "Usage: $0 <username> [password]"
    exit 1
fi

# ── 1. Supprimer l'utilisateur SSH ───────────────────────────
if id "$USERNAME" &>/dev/null; then
    # Tuer les sessions actives
    pkill -u "$USERNAME" 2>/dev/null
    sleep 1
    userdel -f "$USERNAME" 2>/dev/null
    echo "[OK] Utilisateur SSH $USERNAME supprimé"
else
    echo "[INFO] Utilisateur $USERNAME n'existe pas sur le système"
fi

# ── 2. Retirer password de ZiVPN ─────────────────────────────
if [[ -n "$PASSWORD" && -f "$ZIVPN_CONFIG" ]]; then
    python3 -c "
import json
with open('$ZIVPN_CONFIG') as f:
    cfg = json.load(f)
passwords = cfg.get('auth', {}).get('config', [])
if '$PASSWORD' in passwords:
    passwords.remove('$PASSWORD')
    cfg['auth']['config'] = passwords
    with open('$ZIVPN_CONFIG', 'w') as f:
        json.dump(cfg, f, indent=2)
    print('[OK] Password retiré de ZiVPN config')
else:
    print('[INFO] Password non trouvé dans ZiVPN config')
"
    systemctl restart zivpn.service 2>/dev/null
fi

# ── 3. Retirer password de HTTP Custom ───────────────────────
if [[ -n "$PASSWORD" && -f "$UDP_CUSTOM_CONFIG" ]]; then
    python3 -c "
import json
with open('$UDP_CUSTOM_CONFIG') as f:
    cfg = json.load(f)
passwords = cfg.get('auth', {}).get('passwords', [])
if '$PASSWORD' in passwords:
    passwords.remove('$PASSWORD')
    cfg['auth']['passwords'] = passwords
    with open('$UDP_CUSTOM_CONFIG', 'w') as f:
        json.dump(cfg, f, indent=2)
    print('[OK] Password retiré de HTTP Custom config')
else:
    print('[INFO] Password non trouvé dans HTTP Custom config')
"
    systemctl restart udp-custom.service 2>/dev/null
fi

echo "[DONE] Suppression terminée : $USERNAME"
exit 0
