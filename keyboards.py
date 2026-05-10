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
        persistent=True,
    )


def user_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📂 Mes comptes", "➕ Créer compte"],
            ["📄 Config", "🔄 Renouveler"],
            ["💬 Support"],
        ],
        resize_keyboard=True,
        persistent=True,
    )


# ── Inline — Création compte ─────────────────────────────────

def account_type_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 HTTP Custom", callback_data="type_http"),
            InlineKeyboardButton("🔒 ZiVPN", callback_data="type_zi"),
        ],
        [InlineKeyboardButton("🔀 Les deux", callback_data="type_both")],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


def port_choice_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 443 (Défaut)", callback_data="port_443")],
        [
            InlineKeyboardButton("🔁 80", callback_data="port_80"),
            InlineKeyboardButton("🔁 8080", callback_data="port_8080"),
            InlineKeyboardButton("🔁 8443", callback_data="port_8443"),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


# ── Inline — Actions sur un compte ──────────────────────────

def account_actions_keyboard(account_id: int, owner_id: int = None):
    btns = [
        [
            InlineKeyboardButton(
                "📥 Télécharger Config", callback_data=f"dl_config_{account_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Renouveler", callback_data=f"renew_{account_id}"
            ),
            InlineKeyboardButton(
                "🗑️ Supprimer", callback_data=f"delete_acc_{account_id}"
            ),
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_accounts")],
    ]
    return InlineKeyboardMarkup(btns)


def confirm_delete_keyboard(account_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Confirmer", callback_data=f"confirm_delete_{account_id}"
            ),
            InlineKeyboardButton("❌ Annuler", callback_data="cancel"),
        ]
    ])


def renew_days_keyboard(account_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "7 jours", callback_data=f"renewdays_{account_id}_7"
            ),
            InlineKeyboardButton(
                "15 jours", callback_data=f"renewdays_{account_id}_15"
            ),
            InlineKeyboardButton(
                "30 jours", callback_data=f"renewdays_{account_id}_30"
            ),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


# ── Inline — Admin users ─────────────────────────────────────

def user_management_keyboard(telegram_id: int, is_blocked: bool):
    block_label = "✅ Débloquer" if is_blocked else "🚫 Bloquer"
    block_cb = f"unblock_{telegram_id}" if is_blocked else f"block_{telegram_id}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(block_label, callback_data=block_cb),
            InlineKeyboardButton(
                "🗑️ Supprimer", callback_data=f"deluser_{telegram_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 Ses comptes", callback_data=f"useraccounts_{telegram_id}"
            )
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_users")],
    ])


# ── Inline — Codes ───────────────────────────────────────────

def code_actions_keyboard(code: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚫 Désactiver", callback_data=f"deactivate_code_{code}"
            )
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="back_codes")],
    ])


# ── Inline — Support ─────────────────────────────────────────

def support_reply_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💬 Répondre", callback_data=f"reply_support_{user_id}"
            )
        ]
    ])
