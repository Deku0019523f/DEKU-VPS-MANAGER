#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — create_user.sh
#   Usage: ./create_user.sh <username> <password> <days> <type>
#   type: http | zi | both
# ============================================================

USERNAME="$1"
PASSWORD="$2"
DAYS="$3"
TYPE="${4:-both}"

ZIVPN_CONFIG="/etc/zivpn/config.json"
UDP_CUSTOM_CONFIG="/root/udp/config.json"

if [[ -z "$USERNAME" || -z "$PASSWORD" || -z "$DAYS" ]]; then
    echo "Usage: $0 <username> <password> <days> [type]"
    exit 1
fi

# ── 1. Créer l'utilisateur SSH système ───────────────────────
if id "$USERNAME" &>/dev/null; then
    echo "[INFO] Utilisateur $USERNAME existe déjà, mise à jour..."
else
    useradd -M -s /bin/false "$USERNAME"
    if [[ $? -ne 0 ]]; then
        echo "[ERROR] Impossible de créer l'utilisateur SSH $USERNAME"
        exit 1
    fi
fi

# Définir le mot de passe
echo "$USERNAME:$PASSWORD" | chpasswd
if [[ $? -ne 0 ]]; then
    echo "[ERROR] Impossible de définir le mot de passe pour $USERNAME"
    exit 1
fi

# Définir la date d'expiration
EXPIRY_DATE=$(date -d "+${DAYS} days" +%Y-%m-%d)
chage -E "$EXPIRY_DATE" "$USERNAME"

echo "[OK] Compte SSH créé : $USERNAME | Expiration : $EXPIRY_DATE"

# ── 2. Ajouter password à ZiVPN (UDP) ────────────────────────
add_zivpn_password() {
    if [[ ! -f "$ZIVPN_CONFIG" ]]; then
        echo "[WARN] Config ZiVPN introuvable : $ZIVPN_CONFIG"
        return 1
    fi

    # Vérifier si le password existe déjà
    if python3 -c "
import json, sys
with open('$ZIVPN_CONFIG') as f:
    cfg = json.load(f)
passwords = cfg.get('auth', {}).get('config', [])
sys.exit(0 if '$PASSWORD' in passwords else 1)
" 2>/dev/null; then
        echo "[INFO] Password ZiVPN déjà présent"
        return 0
    fi

    # Ajouter le password
    python3 -c "
import json
with open('$ZIVPN_CONFIG') as f:
    cfg = json.load(f)
if 'auth' not in cfg:
    cfg['auth'] = {'mode': 'passwords', 'config': []}
if 'config' not in cfg['auth']:
    cfg['auth']['config'] = []
cfg['auth']['config'].append('$PASSWORD')
with open('$ZIVPN_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('[OK] Password ajouté à ZiVPN config')
"
    # Redémarrer le service ZiVPN
    systemctl restart zivpn.service 2>/dev/null && \
        echo "[OK] Service ZiVPN redémarré" || \
        echo "[WARN] Impossible de redémarrer zivpn.service"
}

# ── 3. Ajouter password à HTTP Custom (UDP) ──────────────────
add_udpcustom_password() {
    if [[ ! -f "$UDP_CUSTOM_CONFIG" ]]; then
        echo "[WARN] Config HTTP Custom introuvable : $UDP_CUSTOM_CONFIG"
        return 1
    fi

    # Vérifier si le password existe déjà
    if python3 -c "
import json, sys
with open('$UDP_CUSTOM_CONFIG') as f:
    cfg = json.load(f)
passwords = cfg.get('auth', {}).get('passwords', [])
sys.exit(0 if '$PASSWORD' in passwords else 1)
" 2>/dev/null; then
        echo "[INFO] Password HTTP Custom déjà présent"
        return 0
    fi

    python3 -c "
import json
with open('$UDP_CUSTOM_CONFIG') as f:
    cfg = json.load(f)
if 'auth' not in cfg:
    cfg['auth'] = {'mode': 'passwords', 'passwords': []}
if 'passwords' not in cfg['auth']:
    cfg['auth']['passwords'] = []
cfg['auth']['passwords'].append('$PASSWORD')
with open('$UDP_CUSTOM_CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2)
print('[OK] Password ajouté à HTTP Custom config')
"
    systemctl restart udp-custom.service 2>/dev/null && \
        echo "[OK] Service UDP Custom redémarré" || \
        echo "[WARN] Impossible de redémarrer udp-custom.service"
}

# ── Application selon le type ────────────────────────────────
case "$TYPE" in
    http)
        add_udpcustom_password
        ;;
    zi)
        add_zivpn_password
        ;;
    both|*)
        add_udpcustom_password
        add_zivpn_password
        ;;
esac

echo "[DONE] Création compte terminée : $USERNAME ($TYPE)"
exit 0
