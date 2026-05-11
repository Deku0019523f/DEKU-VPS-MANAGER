#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — install_v2ray.sh
#   Installe V2Ray avec VMess + VLESS sur ports 443 et 80
#   Usage: sudo bash install_v2ray.sh
# ============================================================

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[[ "$(whoami)" != "root" ]] && err "Lancez en root"

VPS_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
WS_PATH="/deku"

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════╗"
echo "  ║   DEKU VPS — Install V2Ray       ║"
echo "  ║   VMess + VLESS   Port 443 + 80  ║"
echo "  ╚══════════════════════════════════╝"
echo -e "${NC}"
info "IP VPS détectée : $VPS_IP"

# ── Dépendances ────────────────────────────────────────────
apt-get update -qq
apt-get install -y curl wget unzip openssl -qq

# ── Installer V2Ray officiel ───────────────────────────────
info "Installation de V2Ray (v2fly/v2ray-core)..."
bash <(curl -L https://raw.githubusercontent.com/v2fly/fhs-install-v2ray/master/install-release.sh) \
    --version v5.16.1 2>/dev/null

if ! command -v v2ray &>/dev/null; then
    err "Échec installation V2Ray. Vérifiez la connexion internet."
fi
log "V2Ray installé : $(v2ray version | head -1)"

# ── Générer les UUIDs de base ──────────────────────────────
UUID_VMESS=$(cat /proc/sys/kernel/random/uuid)
UUID_VLESS=$(cat /proc/sys/kernel/random/uuid)
info "UUID VMess (exemple) : $UUID_VMESS"
info "UUID VLESS (exemple) : $UUID_VLESS"

# ── Générer certificat TLS auto-signé ─────────────────────
mkdir -p /etc/v2ray/tls
info "Génération certificat TLS..."
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
    -subj "/C=US/ST=CA/L=LA/O=DekuVPS/CN=$VPS_IP" \
    -keyout /etc/v2ray/tls/server.key \
    -out    /etc/v2ray/tls/server.crt 2>/dev/null
log "Certificat TLS généré (valide 10 ans)"

# ── Config V2Ray ───────────────────────────────────────────
cat > /etc/v2ray/config.json << JSONEOF
{
  "log": {
    "loglevel": "warning",
    "access": "/var/log/v2ray/access.log",
    "error":  "/var/log/v2ray/error.log"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vmess",
      "settings": {
        "clients": []
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/etc/v2ray/tls/server.crt",
              "keyFile":         "/etc/v2ray/tls/server.key"
            }
          ]
        },
        "wsSettings": {
          "path": "$WS_PATH",
          "headers": {}
        }
      }
    },
    {
      "listen": "0.0.0.0",
      "port": 80,
      "protocol": "vmess",
      "settings": {
        "clients": []
      },
      "streamSettings": {
        "network": "ws",
        "security": "none",
        "wsSettings": {
          "path": "$WS_PATH",
          "headers": {}
        }
      }
    },
    {
      "listen": "0.0.0.0",
      "port": 8443,
      "protocol": "vless",
      "settings": {
        "clients": [],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/etc/v2ray/tls/server.crt",
              "keyFile":         "/etc/v2ray/tls/server.key"
            }
          ]
        },
        "wsSettings": {
          "path": "$WS_PATH",
          "headers": {}
        }
      }
    },
    {
      "listen": "0.0.0.0",
      "port": 8080,
      "protocol": "vless",
      "settings": {
        "clients": [],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "security": "none",
        "wsSettings": {
          "path": "$WS_PATH",
          "headers": {}
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "settings": {}
    }
  ]
}
JSONEOF
log "Config V2Ray créée — Inbounds : VMess 443/80 + VLESS 8443/8080"

# ── Firewall ────────────────────────────────────────────────
if ufw status | grep -q "active"; then
    ufw allow 80/tcp  2>/dev/null
    ufw allow 443/tcp 2>/dev/null
    ufw allow 8080/tcp 2>/dev/null
    ufw allow 8443/tcp 2>/dev/null
    log "Ports 80, 443, 8080, 8443 ouverts dans UFW"
fi

# ── Démarrer V2Ray ──────────────────────────────────────────
systemctl daemon-reload
systemctl enable v2ray
systemctl start  v2ray
sleep 2

if systemctl is-active --quiet v2ray; then
    log "V2Ray actif ✅"
else
    echo "⚠️ V2Ray ne démarre pas. Vérifiez :"
    echo "   journalctl -u v2ray -n 30"
fi

# ── Redémarrer bot Deku ─────────────────────────────────────
systemctl is-enabled --quiet deku-vps 2>/dev/null && \
    systemctl restart deku-vps && log "Bot Deku redémarré"

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ V2Ray installé et actif${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  VMess : ports 443 (TLS) et 80"
echo "  VLESS : ports 8443 (TLS) et 8080"
echo "  WS Path : $WS_PATH"
echo ""
echo "  Config : /etc/v2ray/config.json"
echo "  TLS    : /etc/v2ray/tls/"
echo ""
echo "  Logs   : journalctl -u v2ray -f"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
