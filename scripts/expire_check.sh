#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — expire_check.sh
#   Appelé par cron toutes les heures
#   Usage: ./expire_check.sh
# ============================================================

ZIVPN_CONFIG="/etc/zivpn/config.json"
UDP_CUSTOM_CONFIG="/root/udp/config.json"
LOG_FILE="/var/log/deku_vps.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Vérification des comptes expirés ==="

# ── Lire la liste des utilisateurs expirés depuis SQLite ─────
# Ce script est appelé avec les usernames expirés en argument
# Format: ./expire_check.sh user1 user2 user3...

if [[ $# -gt 0 ]]; then
    EXPIRED_USERS=("$@")
    log "Comptes à supprimer reçus : ${EXPIRED_USERS[*]}"

    RESTART_ZIVPN=0
    RESTART_UDP=0

    for USERNAME in "${EXPIRED_USERS[@]}"; do
        log "Traitement expiration : $USERNAME"

        # Bloquer l'accès SSH (lock le compte)
        if id "$USERNAME" &>/dev/null; then
            usermod -L "$USERNAME" 2>/dev/null
            pkill -u "$USERNAME" 2>/dev/null
            log "[OK] Compte SSH $USERNAME verrouillé"
        fi

        # Retirer de ZiVPN (on essaie même sans password connu)
        if [[ -f "$ZIVPN_CONFIG" ]]; then
            BEFORE=$(python3 -c "
import json
with open('$ZIVPN_CONFIG') as f:
    cfg = json.load(f)
print(len(cfg.get('auth', {}).get('config', [])))
" 2>/dev/null)
            # La suppression par username est gérée par le bot (qui passe le password)
            log "[INFO] ZiVPN config : vérification manuelle requise pour $USERNAME"
            RESTART_ZIVPN=1
        fi

        # Retirer de HTTP Custom
        if [[ -f "$UDP_CUSTOM_CONFIG" ]]; then
            log "[INFO] UDP Custom config : vérification manuelle requise pour $USERNAME"
            RESTART_UDP=1
        fi
    done

    [[ $RESTART_ZIVPN -eq 1 ]] && systemctl restart zivpn.service 2>/dev/null
    [[ $RESTART_UDP -eq 1 ]] && systemctl restart udp-custom.service 2>/dev/null

else
    # Mode autonome : chercher les utilisateurs système expirés
    log "Mode autonome : recherche des comptes expirés..."

    while IFS=: read -r user _; do
        # Ignorer les comptes système
        [[ "$user" =~ ^(root|daemon|bin|sys|sync|games|man|lp|mail|news|uucp|proxy|www-data|backup|list|irc|gnats|nobody|_apt|systemd.*|messagebus|sshd|ubuntu|admin)$ ]] && continue

        EXPIRY=$(chage -l "$user" 2>/dev/null | grep "Account expires" | cut -d: -f2 | xargs)

        if [[ "$EXPIRY" != "never" && -n "$EXPIRY" ]]; then
            EXPIRY_TS=$(date -d "$EXPIRY" +%s 2>/dev/null)
            NOW_TS=$(date +%s)

            if [[ -n "$EXPIRY_TS" && "$EXPIRY_TS" -lt "$NOW_TS" ]]; then
                log "Compte expiré détecté : $user (expiré le $EXPIRY)"
                usermod -L "$user" 2>/dev/null
                pkill -u "$user" 2>/dev/null
                log "[OK] $user verrouillé"
            fi
        fi
    done < /etc/passwd

    log "Vérification autonome terminée."
fi

log "=== expire_check.sh terminé ==="
exit 0
