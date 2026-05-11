# ============================================================
#   DEKU VPS MANAGER — Keyboards
# ============================================================

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


# ── Reply Keyboards ──────────────────────────────────────────

def admin_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["👥 Utilisateurs", "🎫 Codes"],
            ["➕ Créer compte", "📋 Comptes"],
            ["📊 Stats VPS", "📜 Logs"],
            ["📢 Broadcast", "⚙️ Paramètres"],
        ],
        resize_keyboard=True,
    )


def user_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📂 Mes comptes", "➕ Créer compte"],
            ["📄 Config", "🔄 Renouveler"],
            ["💬 Support"],
        ],
        resize_keyboard=True,
    )


# ── Inline — Sélection type de compte ─────────────────────────

def account_type_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 HTTP Custom", callback_data="type_http"),
            InlineKeyboardButton("🔒 ZiVPN",       callback_data="type_zi"),
        ],
        [InlineKeyboardButton("🔀 Les deux (SSH)", callback_data="type_both")],
        [InlineKeyboardButton("🔷 V2Ray",          callback_data="type_v2ray")],
        [InlineKeyboardButton("❌ Annuler",         callback_data="cancel")],
    ])


# ── Inline — Port SSH ─────────────────────────────────────────

def port_choice_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 443 (Défaut)", callback_data="port_443")],
        [
            InlineKeyboardButton("🔁 80",   callback_data="port_80"),
            InlineKeyboardButton("🔁 8080", callback_data="port_8080"),
            InlineKeyboardButton("🔁 8443", callback_data="port_8443"),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


# ── Inline — Limite de sessions ───────────────────────────────

def sessions_keyboard(prefix: str = "sess"):
    """prefix = 'sess' (SSH) ou 'v2sess' (V2Ray)"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣  1 connexion",  callback_data=f"{prefix}_1"),
            InlineKeyboardButton("2️⃣  2 connexions", callback_data=f"{prefix}_2"),
        ],
        [
            InlineKeyboardButton("5️⃣  5 connexions", callback_data=f"{prefix}_5"),
            InlineKeyboardButton("♾️  Illimité",     callback_data=f"{prefix}_0"),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


# ── Inline — V2Ray protocole ──────────────────────────────────

def v2ray_protocol_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔵 VMess", callback_data="v2proto_vmess"),
            InlineKeyboardButton("🟣 VLESS", callback_data="v2proto_vless"),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


# ── Inline — V2Ray mode SNI ───────────────────────────────────

def v2ray_sni_mode_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🔄 Reverse SNI (Bug as address)",
            callback_data="v2snimode_reverse"
        )],
        [InlineKeyboardButton(
            "📍 Default SNI location",
            callback_data="v2snimode_default"
        )],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


def v2ray_sni_skip_keyboard():
    """Affiché quand on attend le SNI (avec bouton passer)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Passer (sans SNI)", callback_data="v2sni_skip")],
        [InlineKeyboardButton("❌ Annuler",            callback_data="cancel")],
    ])


# ── Inline — Actions compte SSH ───────────────────────────────

def account_actions_keyboard(account_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📥 Télécharger Config", callback_data=f"dl_config_{account_id}"
        )],
        [
            InlineKeyboardButton(
                "📡 Connexions actives", callback_data=f"sessions_{account_id}"
            ),
            InlineKeyboardButton(
                "🕐 Historique",        callback_data=f"hist_{account_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🧪 Tester",  callback_data=f"test_{account_id}"
            ),
            InlineKeyboardButton(
                "🔄 Renouveler", callback_data=f"renew_{account_id}"
            ),
        ],
        [InlineKeyboardButton(
            "🗑️ Supprimer", callback_data=f"delete_acc_{account_id}"
        )],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_accounts")],
    ])


def confirm_delete_keyboard(account_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Confirmer", callback_data=f"confirm_delete_{account_id}"
            ),
            InlineKeyboardButton("❌ Annuler", callback_data="cancel"),
        ]
    ])


def renew_days_keyboard(account_id: int, prefix: str = "renewdays"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("7j",  callback_data=f"{prefix}_{account_id}_7"),
            InlineKeyboardButton("15j", callback_data=f"{prefix}_{account_id}_15"),
            InlineKeyboardButton("30j", callback_data=f"{prefix}_{account_id}_30"),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


# ── Inline — Actions compte V2Ray ─────────────────────────────

def v2ray_account_actions_keyboard(acc_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📥 Liens de config", callback_data=f"v2dl_{acc_id}"
        )],
        [
            InlineKeyboardButton(
                "🧪 Tester",        callback_data=f"v2test_{acc_id}"
            ),
            InlineKeyboardButton(
                "🔄 Renouveler",    callback_data=f"v2renew_{acc_id}"
            ),
        ],
        [InlineKeyboardButton(
            "🗑️ Supprimer", callback_data=f"v2del_{acc_id}"
        )],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_accounts")],
    ])


def v2ray_confirm_delete_keyboard(acc_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Confirmer", callback_data=f"v2confirmdelete_{acc_id}"
            ),
            InlineKeyboardButton("❌ Annuler", callback_data="cancel"),
        ]
    ])


# ── Inline — Admin users ─────────────────────────────────────

def user_management_keyboard(telegram_id: int, is_blocked: bool):
    block_label = "✅ Débloquer" if is_blocked else "🚫 Bloquer"
    block_cb    = f"unblock_{telegram_id}" if is_blocked else f"block_{telegram_id}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(block_label, callback_data=block_cb),
            InlineKeyboardButton(
                "🗑️ Supprimer", callback_data=f"deluser_{telegram_id}"
            ),
        ],
        [InlineKeyboardButton(
            "📋 Ses comptes", callback_data=f"useraccounts_{telegram_id}"
        )],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_users")],
    ])


# ── Inline — Codes ───────────────────────────────────────────

def code_actions_keyboard(code: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🚫 Désactiver", callback_data=f"deactivate_code_{code}"
        )],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_codes")],
    ])


# ── Inline — Support ─────────────────────────────────────────

def support_reply_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "💬 Répondre", callback_data=f"reply_support_{user_id}"
        )]
    ])
