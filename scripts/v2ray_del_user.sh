#!/bin/bash
# ============================================================
#   DEKU VPS MANAGER — v2ray_del_user.sh
#   Usage: ./v2ray_del_user.sh <uuid>
# ============================================================

UUID="$1"
V2RAY_CONFIG="/etc/v2ray/config.json"

[[ -z "$UUID" ]] && { echo "[ERROR] UUID requis"; exit 1; }
[[ ! -f "$V2RAY_CONFIG" ]] && { echo "[DEMO] Config V2Ray absente — mode démo"; exit 0; }

python3 - "$UUID" "$V2RAY_CONFIG" << 'PYEOF'
import json, sys

uuid, config_path = sys.argv[1], sys.argv[2]

with open(config_path) as f:
    cfg = json.load(f)

removed = 0
for inbound in cfg.get("inbounds", []):
    clients = inbound.get("settings", {}).get("clients", [])
    before  = len(clients)
    clients[:] = [c for c in clients
                  if c.get("id") != uuid and c.get("password") != uuid]
    removed += before - len(clients)

if removed:
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"[OK] UUID supprimé ({removed} entrée(s))")
else:
    print("[INFO] UUID non trouvé dans la config V2Ray")
PYEOF

systemctl reload v2ray 2>/dev/null || systemctl restart v2ray 2>/dev/null
echo "[OK] V2Ray rechargé"
exit 0
