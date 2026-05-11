#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — v2ray_add_user.sh
#   Usage: ./v2ray_add_user.sh <uuid> <protocol> [max_sessions]
# ============================================================

UUID="$1"
PROTOCOL="${2:-vmess}"
MAX_SESSIONS="${3:-0}"
V2RAY_CONFIG="/etc/v2ray/config.json"

[[ -z "$UUID" ]] && { echo "[ERROR] UUID requis"; exit 1; }
[[ ! -f "$V2RAY_CONFIG" ]] && { echo "[ERROR] Config V2Ray introuvable : $V2RAY_CONFIG"; exit 1; }

# Trouver l'inbound qui correspond au protocole
python3 - "$UUID" "$PROTOCOL" "$MAX_SESSIONS" "$V2RAY_CONFIG" << 'PYEOF'
import json, sys

uuid, protocol, max_sessions, config_path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]

with open(config_path) as f:
    cfg = json.load(f)

modified = False
for inbound in cfg.get("inbounds", []):
    if inbound.get("protocol") != protocol:
        continue
    settings = inbound.setdefault("settings", {})
    clients  = settings.setdefault("clients", [])

    # Vérifier si UUID existe déjà
    if any(c.get("id") == uuid or c.get("password") == uuid for c in clients):
        print(f"[INFO] UUID déjà présent dans {protocol}")
        sys.exit(0)

    # Construire le client
    if protocol == "vmess":
        client = {"id": uuid, "alterId": 0}
    else:  # vless
        client = {"id": uuid, "flow": ""}

    if max_sessions > 0:
        client["maxConnections"] = max_sessions

    clients.append(client)
    modified = True
    print(f"[OK] UUID ajouté à {protocol}")

if not modified:
    print(f"[WARN] Aucun inbound {protocol} trouvé dans la config")
    sys.exit(1)

with open(config_path, "w") as f:
    json.dump(cfg, f, indent=2)
PYEOF

[[ $? -ne 0 ]] && exit 1

# Reload V2Ray sans interruption
systemctl reload v2ray 2>/dev/null || systemctl restart v2ray 2>/dev/null
echo "[OK] V2Ray rechargé"
exit 0
