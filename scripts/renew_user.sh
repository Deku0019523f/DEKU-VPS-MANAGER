#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — renew_user.sh
#   Usage: ./renew_user.sh <username> <days>
# ============================================================

USERNAME="$1"
DAYS="$2"

if [[ -z "$USERNAME" || -z "$DAYS" ]]; then
    echo "Usage: $0 <username> <days>"
    exit 1
fi

if ! id "$USERNAME" &>/dev/null; then
    echo "[ERROR] Utilisateur $USERNAME introuvable"
    exit 1
fi

# Calculer la nouvelle date d'expiration depuis aujourd'hui
NEW_EXPIRY=$(date -d "+${DAYS} days" +%Y-%m-%d)
chage -E "$NEW_EXPIRY" "$USERNAME"

if [[ $? -eq 0 ]]; then
    echo "[OK] $USERNAME renouvelé jusqu'au $NEW_EXPIRY"
    # Dé-locker le compte si bloqué
    usermod -U "$USERNAME" 2>/dev/null
    exit 0
else
    echo "[ERROR] Impossible de renouveler $USERNAME"
    exit 1
fi
