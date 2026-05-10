#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — install.sh
#   Script d'installation rapide sur VPS Ubuntu 20.04+
#   Usage: sudo bash install.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="/root/deku_vps_manager"

banner() {
    echo -e "${CYAN}"
    echo "  ██████╗ ███████╗██╗  ██╗██╗   ██╗"
    echo "  ██╔══██╗██╔════╝██║ ██╔╝██║   ██║"
    echo "  ██║  ██║█████╗  █████╔╝ ██║   ██║"
    echo "  ██║  ██║██╔══╝  ██╔═██╗ ██║   ██║"
    echo "  ██████╔╝███████╗██║  ██╗╚██████╔╝"
    echo "  ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ "
    echo -e "        ${BOLD}VPS MANAGER — INSTALLER${NC}"
    echo ""
}

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Root check ────────────────────────────────────────────────
[[ "$(whoami)" != "root" ]] && err "Lancez ce script en tant que root : sudo bash install.sh"

banner

# ── Python 3.10+ check ───────────────────────────────────────
info "Vérification Python..."
PY=$(python3 --version 2>&1 | awk '{print $2}')
PY_MAJOR=$(echo "$PY" | cut -d. -f1)
PY_MINOR=$(echo "$PY" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || "$PY_MINOR" -lt 10 ]]; then
    warn "Python $PY détecté, 3.10+ recommandé."
    apt-get install -y python3.10 python3.10-pip 2>/dev/null
else
    log "Python $PY"
fi

# ── Dépendances système ───────────────────────────────────────
info "Installation des dépendances système..."
apt-get update -qq
apt-get install -y python3-pip openssl 2>/dev/null
log "Dépendances installées"

# ── Pip packages ─────────────────────────────────────────────
info "Installation des packages Python..."
pip3 install -q "python-telegram-bot[job-queue]==21.6"
if [[ $? -ne 0 ]]; then
    err "Impossible d'installer python-telegram-bot"
fi
log "python-telegram-bot[job-queue] installé"

# ── Déplacer vers /root si besoin ────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" != "$INSTALL_DIR" ]]; then
    info "Copie vers $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/. "$INSTALL_DIR/"
    log "Fichiers copiés vers $INSTALL_DIR"
fi

# ── Permissions scripts ───────────────────────────────────────
chmod +x "$INSTALL_DIR/scripts/"*.sh
log "Scripts shell rendus exécutables"

# ── Demander le token bot ─────────────────────────────────────
echo ""
echo -e "${BOLD}Configuration du bot${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
read -p "🤖 Token Telegram Bot (BotFather) : " BOT_TOKEN
if [[ -z "$BOT_TOKEN" ]]; then
    err "Token vide. Annulation."
fi

# ── Détecter l'IP publique ────────────────────────────────────
DETECTED_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s api.ipify.org 2>/dev/null || echo "")
if [[ -n "$DETECTED_IP" ]]; then
    echo -e "🌐 IP détectée : ${CYAN}$DETECTED_IP${NC}"
    read -p "   Utiliser cette IP ? [O/n] : " USE_IP
    if [[ "$USE_IP" =~ ^[Nn]$ ]]; then
        read -p "🌐 IP VPS manuellement : " VPS_IP
    else
        VPS_IP="$DETECTED_IP"
    fi
else
    read -p "🌐 IP publique du VPS : " VPS_IP
fi
[[ -z "$VPS_IP" ]] && err "IP vide. Annulation."

# ── Écrire config.py ──────────────────────────────────────────
cat > "$INSTALL_DIR/config.py" << PYEOF
# ============================================================
#   DEKU VPS MANAGER — Configuration
# ============================================================

BOT_TOKEN = "$BOT_TOKEN"

# Admin principal
ADMIN_ID = 1299831974
ADMIN_USERNAME = "@darkdeku225"

# VPS
VPS_IP = "$VPS_IP"
DEFAULT_PORT = 443

# Base de données
DB_PATH = "deku_vps.db"

# Scripts shell
SCRIPTS_DIR = "./scripts"

# Anti-spam : délai minimum entre actions (secondes)
SPAM_DELAY = 3

# Longueur max message support
MAX_MSG_LENGTH = 1000
PYEOF
log "config.py configuré (IP: $VPS_IP)"

# ── Cron expire_check ─────────────────────────────────────────
info "Configuration du cron expire_check..."
CRON_LINE="0 * * * * bash $INSTALL_DIR/scripts/expire_check.sh >> /var/log/deku_vps.log 2>&1"
(crontab -l 2>/dev/null | grep -v "expire_check"; echo "$CRON_LINE") | crontab -
log "Cron expire_check ajouté (toutes les heures)"

# ── Service systemd ───────────────────────────────────────────
info "Installation du service systemd..."
cp "$INSTALL_DIR/deku-vps.service" /etc/systemd/system/deku-vps.service
sed -i "s|/root/deku_vps_manager|$INSTALL_DIR|g" /etc/systemd/system/deku-vps.service
systemctl daemon-reload
systemctl enable deku-vps.service
log "Service systemd installé et activé"

# ── Lancer le bot ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}Démarrage du bot...${NC}"
systemctl restart deku-vps.service
sleep 3

STATUS=$(systemctl is-active deku-vps.service)
if [[ "$STATUS" == "active" ]]; then
    log "Bot démarré avec succès !"
else
    warn "Le bot n'est pas actif. Vérifiez les logs :"
    echo "  journalctl -u deku-vps -n 30"
fi

# ── Résumé final ─────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  ✅ DEKU VPS MANAGER installé${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  📁 Répertoire  : $INSTALL_DIR"
echo -e "  🌐 IP VPS      : $VPS_IP"
echo -e "  👑 Admin ID    : 1299831974"
echo -e "  📜 Logs        : journalctl -u deku-vps -f"
echo -e "  ⏹  Stop        : systemctl stop deku-vps"
echo -e "  ▶  Start       : systemctl start deku-vps"
echo ""
echo -e "  👉 Ouvrez Telegram et envoyez ${BOLD}/start${NC} à votre bot !"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
