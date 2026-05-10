#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — setup_udp_services.sh
#   Installe HTTP Custom + ZiVPN sur Ubuntu 20.04+ amd64
#   Usage: sudo bash setup_udp_services.sh
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[[ "$(whoami)" != "root" ]] && err "Lancez en root : sudo bash setup_udp_services.sh"

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════╗"
echo "  ║   DEKU VPS — UDP Services Setup  ║"
echo "  ║   HTTP Custom + ZiVPN            ║"
echo "  ╚══════════════════════════════════╝"
echo -e "${NC}"

# ── Détection architecture ─────────────────────────────────
ARCH=$(uname -m)
info "Architecture détectée : $ARCH"
if [[ "$ARCH" != "x86_64" ]]; then
    warn "HTTP Custom ne supporte que amd64. ZiVPN sera installé (arm support)."
fi

# ── Dépendances ────────────────────────────────────────────
info "Mise à jour et dépendances..."
apt-get update -qq
apt-get install -y wget curl openssl python3 iptables -qq
log "Dépendances prêtes"

# ════════════════════════════════════════════════
#   1. HTTP CUSTOM (UDP Custom)
# ════════════════════════════════════════════════
install_http_custom() {
    echo ""
    echo -e "${CYAN}━━━━ Installation HTTP Custom ━━━━${NC}"

    # Arrêter l'ancien service
    systemctl stop udp-custom 2>/dev/null
    systemctl stop udpgw 2>/dev/null

    # Créer les dossiers
    mkdir -p /root/udp /etc/UDPCustom

    # Télécharger le binaire
    info "Téléchargement du binaire HTTP Custom..."
    wget -q "https://raw.github.com/http-custom/udp-custom/main/bin/udp-custom-linux-amd64" \
         -O /root/udp/udp-custom || {
        warn "Téléchargement GitHub échoué, tentative alternative..."
        curl -sL "https://github.com/http-custom/udp-custom/raw/main/bin/udp-custom-linux-amd64" \
             -o /root/udp/udp-custom || err "Impossible de télécharger HTTP Custom"
    }
    chmod +x /root/udp/udp-custom
    log "Binaire HTTP Custom téléchargé"

    # Télécharger udpgw (gateway BadVPN)
    info "Téléchargement udpgw..."
    wget -q "https://raw.github.com/http-custom/udp-custom/main/module/udpgw" \
         -O /bin/udpgw 2>/dev/null || true
    chmod +x /bin/udpgw 2>/dev/null || true

    # Config HTTP Custom
    cat > /root/udp/config.json << 'EOF'
{
  "listen": ":36712",
  "stream_buffer": 33554432,
  "receive_buffer": 83886080,
  "auth": {
    "mode": "passwords",
    "passwords": []
  }
}
EOF
    log "Config HTTP Custom créée : /root/udp/config.json"

    # Service udpgw
    cat > /etc/systemd/system/udpgw.service << 'EOF'
[Unit]
Description=UDP Gateway (BadVPN)
After=network.target

[Service]
Type=simple
User=root
ExecStart=/bin/udpgw --listen-addr 127.0.0.1:7300 --max-clients 500 --max-connections-for-client 10
Restart=always
RestartSec=2s

[Install]
WantedBy=multi-user.target
EOF

    # Service HTTP Custom
    cat > /etc/systemd/system/udp-custom.service << 'EOF'
[Unit]
Description=UDP Custom by ePro Dev. Team
After=network.target

[Service]
User=root
Type=simple
ExecStart=/root/udp/udp-custom server
WorkingDirectory=/root/udp/
Restart=always
RestartSec=2s

[Install]
WantedBy=default.target
EOF

    systemctl daemon-reload
    systemctl enable udpgw 2>/dev/null
    systemctl start udpgw 2>/dev/null
    systemctl enable udp-custom
    systemctl start udp-custom

    sleep 2
    if systemctl is-active --quiet udp-custom; then
        log "HTTP Custom actif sur le port 36712 ✅"
    else
        warn "HTTP Custom ne démarre pas. Vérifiez : journalctl -u udp-custom -n 20"
    fi
}

# ════════════════════════════════════════════════
#   2. ZIVPN
# ════════════════════════════════════════════════
install_zivpn() {
    echo ""
    echo -e "${CYAN}━━━━ Installation ZiVPN ━━━━${NC}"

    systemctl stop zivpn 2>/dev/null
    mkdir -p /etc/zivpn

    # Choisir le bon binaire selon l'architecture
    if [[ "$ARCH" == "x86_64" ]]; then
        ZIVPN_URL="https://github.com/zahidbd2/udp-zivpn/releases/download/udp-zivpn_1.4.9/udp-zivpn-linux-amd64"
    else
        ZIVPN_URL="https://github.com/zahidbd2/udp-zivpn/releases/download/udp-zivpn_1.4.9/udp-zivpn-linux-arm64"
    fi

    info "Téléchargement du binaire ZiVPN..."
    wget -q "$ZIVPN_URL" -O /usr/local/bin/zivpn || \
    curl -sL "$ZIVPN_URL" -o /usr/local/bin/zivpn || \
    err "Impossible de télécharger ZiVPN"
    chmod +x /usr/local/bin/zivpn
    log "Binaire ZiVPN téléchargé"

    # Générer certificat TLS auto-signé (requis par ZiVPN)
    info "Génération du certificat TLS..."
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
        -subj "/C=US/ST=California/L=LA/O=DekuVPS/CN=zivpn" \
        -keyout /etc/zivpn/zivpn.key \
        -out /etc/zivpn/zivpn.crt 2>/dev/null
    log "Certificat TLS généré (valide 10 ans)"

    # Config ZiVPN
    cat > /etc/zivpn/config.json << 'EOF'
{
  "listen": ":5667",
  "cert": "/etc/zivpn/zivpn.crt",
  "key": "/etc/zivpn/zivpn.key",
  "obfs": "zivpn",
  "auth": {
    "mode": "passwords",
    "config": []
  }
}
EOF
    log "Config ZiVPN créée : /etc/zivpn/config.json"

    # Optimisation réseau
    sysctl -w net.core.rmem_max=16777216 2>/dev/null
    sysctl -w net.core.wmem_max=16777216 2>/dev/null

    # Service ZiVPN
    cat > /etc/systemd/system/zivpn.service << 'EOF'
[Unit]
Description=ZiVPN UDP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/local/bin/zivpn server -c /etc/zivpn/config.json
Restart=always
RestartSec=3
Environment=ZIVPN_LOG_LEVEL=info
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable zivpn
    systemctl start zivpn

    sleep 2
    if systemctl is-active --quiet zivpn; then
        log "ZiVPN actif sur le port 5667 ✅"
    else
        warn "ZiVPN ne démarre pas. Vérifiez : journalctl -u zivpn -n 20"
    fi
}

# ════════════════════════════════════════════════
#   3. IPTABLES — Redirection ports
# ════════════════════════════════════════════════
setup_firewall() {
    echo ""
    echo -e "${CYAN}━━━━ Configuration Firewall / iptables ━━━━${NC}"

    # Interface réseau principale
    IFACE=$(ip -4 route ls | grep default | grep -Po '(?<=dev )(\S+)' | head -1)
    info "Interface réseau : $IFACE"

    # ZiVPN : rediriger plage 6000-19999 → port 5667
    info "Redirection UDP 6000-19999 → 5667 (ZiVPN)"
    iptables -t nat -D PREROUTING -i "$IFACE" -p udp --dport 6000:19999 \
             -j DNAT --to-destination :5667 2>/dev/null || true
    iptables -t nat -A PREROUTING -i "$IFACE" -p udp --dport 6000:19999 \
             -j DNAT --to-destination :5667

    # Ouvrir les ports dans ufw si actif
    if ufw status | grep -q "active"; then
        ufw allow 5667/udp 2>/dev/null
        ufw allow 6000:19999/udp 2>/dev/null
        ufw allow 36712/udp 2>/dev/null
        log "Ports ouverts dans UFW"
    fi

    # Sauvegarder les règles iptables
    if command -v iptables-save &>/dev/null; then
        iptables-save > /etc/iptables.rules 2>/dev/null
        # Ajouter restore au démarrage
        cat > /etc/network/if-pre-up.d/iptables 2>/dev/null << 'IPRULES'
#!/bin/sh
iptables-restore < /etc/iptables.rules
IPRULES
        chmod +x /etc/network/if-pre-up.d/iptables 2>/dev/null
        log "Règles iptables sauvegardées"
    fi
}

# ════════════════════════════════════════════════
#   Exécution
# ════════════════════════════════════════════════
if [[ "$ARCH" == "x86_64" ]]; then
    install_http_custom
fi
install_zivpn
setup_firewall

# ── Résumé ─────────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Services UDP installés et actifs${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  🔌 HTTP Custom → UDP port 36712"
echo "  🔌 ZiVPN       → UDP port 5667 (plage 6000-19999)"
echo ""
echo "  Statut services :"
echo -n "    udp-custom : "
systemctl is-active udp-custom 2>/dev/null || echo "inactif"
echo -n "    zivpn      : "
systemctl is-active zivpn 2>/dev/null || echo "inactif"
echo ""
echo "  En cas d'erreur :"
echo "    journalctl -u udp-custom -n 30"
echo "    journalctl -u zivpn -n 30"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Redémarrer le bot Deku pour qu'il détecte les services
if systemctl is-enabled --quiet deku-vps 2>/dev/null; then
    info "Redémarrage du bot Deku VPS Manager..."
    systemctl restart deku-vps
    log "Bot redémarré"
fi
