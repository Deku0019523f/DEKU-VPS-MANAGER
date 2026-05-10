# 🚀 DEKU VPS MANAGER

Telegram bot panel pour gérer des comptes SSH compatibles **HTTP Custom** et **ZiVPN**.

---

## 📦 Prérequis

- Python 3.10+
- VPS Ubuntu 20.04+ (amd64)
- ZiVPN installé (`/etc/zivpn/config.json`)
- HTTP Custom installé (`/root/udp/config.json`)
- Token bot Telegram (via @BotFather)

---

## ⚡ Installation

```bash
# 1. Cloner / uploader le projet
cd /root
git clone ... deku_vps_manager
cd deku_vps_manager

# 2. Installer les dépendances Python
pip install -r requirements.txt

# 3. Rendre les scripts exécutables
chmod +x scripts/*.sh

# 4. Configurer
nano config.py
# → BOT_TOKEN = "votre_token"
# → VPS_IP    = "votre_ip"

# 5. Lancer
python3 bot.py
```

---

## ⚙️ Configuration (`config.py`)

| Variable | Valeur |
|----------|--------|
| `BOT_TOKEN` | Token @BotFather |
| `ADMIN_ID` | 1299831974 |
| `VPS_IP` | IP publique du VPS |
| `DEFAULT_PORT` | 443 |
| `SCRIPTS_DIR` | `./scripts` |
| `SPAM_DELAY` | 3 (secondes) |

---

## 🔌 Ports & Services

| Service | Protocole | Port |
|---------|-----------|------|
| SSH tunnel | TCP | 443 (défaut) |
| ZiVPN UDP | UDP | 5667 (natif) |
| ZiVPN UDP | UDP | 6000-19999 (iptables) |
| HTTP Custom UDP | UDP | 36712 |

---

## 📋 Formats de config générés

**HTTP Custom (SSH mode)**
```
IP:PORT@USER:PASS
31.207.34.118:443@darkdeku:darkdeku225
```

**ZiVPN (SSH mode)**
```
USER:PASS@IP:PORT
darkdeku:darkdeku225@31.207.34.118:443
```

---

## 🤖 Commandes bot

### Admin
| Commande | Description |
|----------|-------------|
| `/start` | Menu admin |
| `/gencode <jours> <quota> <uses>` | Créer un code d'accès |
| `/users` | Liste utilisateurs |
| `/accounts` | Tous les comptes |
| `/stats` | Stats VPS + panel |
| `/logs` | Journaux d'activité |
| `/broadcast` | Message groupé |
| `/blockuser <id>` | Bloquer un user |
| `/deleteuser <id>` | Supprimer un user |

### Utilisateur
| Commande | Description |
|----------|-------------|
| `/start` | Saisir le code d'accès |
| `/create` | Créer un compte |
| `/myaccounts` | Mes comptes |
| `/config` | Voir mes configs |
| `/support` | Contacter l'admin |

---

## 📁 Structure du projet

```
deku_vps_manager/
├── bot.py              ← Point d'entrée principal
├── config.py           ← Configuration
├── database.py         ← SQLite (users, codes, comptes, logs)
├── keyboards.py        ← Claviers Telegram
├── admin_handlers.py   ← Handlers admin
├── user_handlers.py    ← Handlers utilisateurs
├── utils.py            ← VPS utilities + formatage configs
├── requirements.txt
├── scripts/
│   ├── create_user.sh  ← Crée compte SSH + passwords UDP
│   ├── delete_user.sh  ← Supprime compte SSH + passwords UDP
│   ├── renew_user.sh   ← Renouvelle expiration SSH
│   └── expire_check.sh ← Nettoyage automatique (cron)
└── README.md
```

---

## ⏰ Cron (expire_check automatique)

```bash
# Crontab pour vérifier toutes les heures
crontab -e
# Ajouter :
0 * * * * /root/deku_vps_manager/scripts/expire_check.sh >> /var/log/deku_vps.log 2>&1
```

Le bot lance aussi ce check en interne toutes les heures via `job_queue`.

---

## 🔧 Lancer en service systemd

```ini
# /etc/systemd/system/deku-vps.service
[Unit]
Description=Deku VPS Manager Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/deku_vps_manager
ExecStart=/usr/bin/python3 /root/deku_vps_manager/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable deku-vps
systemctl start deku-vps
systemctl status deku-vps
```

---

## 👑 Admin principal

- **Telegram ID** : `1299831974`
- **Username** : `@darkdeku225`
- Accès total sans restriction.
