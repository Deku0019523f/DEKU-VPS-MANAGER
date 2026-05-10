# ============================================================
#   DEKU VPS MANAGER — User Handlers
# ============================================================

import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
import keyboards as kb
import utils
from config import VPS_IP, DEFAULT_PORT, ADMIN_ID
from admin_handlers import send_admin_notification


# ── Helpers ───────────────────────────────────────────────────

def _account_summary(acc) -> str:
    active = "🟢 Actif" if acc["is_active"] else "🔴 Expiré"
    atype = acc["account_type"].upper()
    port = acc["port"]
    exp = acc["expires_at"][:10]
    cfg = utils.get_config_string(dict(acc), acc["account_type"])
    return (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID      : #{acc['id']}\n"
        f"📡 Type    : {atype}\n"
        f"👤 User    : <code>{acc['ssh_user']}</code>\n"
        f"🔑 Pass    : <code>{acc['ssh_pass']}</code>\n"
        f"🌐 IP      : {acc['vps_ip']}\n"
        f"🔌 Port    : {port}\n"
        f"📅 Expire  : {exp}\n"
        f"🚦 Statut  : {active}\n\n"
        f"📋 <b>Config :</b>\n<code>{cfg}</code>"
    )


# ── /start utilisateur ────────────────────────────────────────

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        "🌟 <b>DEKU VPS MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Bienvenue, <b>{user.first_name}</b> !\n\n"
        "🎫 Entrez votre <b>code d'accès</b> pour continuer :"
    )
    context.user_data["awaiting"] = "access_code"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def registered_user_start(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    quota_max, accounts_used = db.get_user_quota(user.id)
    text = (
        "🏠 <b>MENU PRINCIPAL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.first_name}\n"
        f"📋 Comptes : {accounts_used}/{quota_max}\n\n"
        "Choisissez une option :"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_main_keyboard(),
    )


# ── Validation code d'accès ───────────────────────────────────

async def handle_access_code(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    user = update.effective_user

    code_data = db.validate_code(code)
    if not code_data:
        await update.message.reply_text(
            "❌ <b>Code invalide ou expiré.</b>\n\n"
            "Vérifiez votre code et réessayez.\n"
            "Contactez un admin pour obtenir un code.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Enregistrer l'utilisateur
    db.register_user(
        telegram_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        code=code,
        quota_max=code_data["quota_max"],
    )
    db.consume_code(code)
    db.add_log(user.id, user.username or "", "REGISTER", f"code={code}")
    context.user_data.pop("awaiting", None)

    await send_admin_notification(
        context, "Nouvelle inscription", user,
        f"Code utilisé : {code}"
    )

    await update.message.reply_text(
        "✅ <b>Accès accordé !</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Code       : <code>{code}</code>\n"
        f"📋 Quota      : {code_data['quota_max']} comptes\n"
        f"📅 Validité   : {code_data['validity_days']} jours\n\n"
        "Bienvenue sur <b>DEKU VPS MANAGER</b> !",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_main_keyboard(),
    )


# ── Mes comptes ───────────────────────────────────────────────

async def show_my_accounts(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    accounts = db.get_user_accounts(user.id)

    if not accounts:
        await update.message.reply_text(
            "📭 Vous n'avez aucun compte.\n\n"
            "Utilisez <b>➕ Créer compte</b> pour en créer un.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text(
        f"📂 <b>MES COMPTES ({len(accounts)})</b>",
        parse_mode=ParseMode.HTML,
    )

    for acc in accounts:
        text = _account_summary(acc)
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.account_actions_keyboard(acc["id"]),
        )


# ── Créer compte ──────────────────────────────────────────────

async def start_create_account(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    quota_max, accounts_used = db.get_user_quota(user.id)

    if accounts_used >= quota_max:
        await update.message.reply_text(
            "⚠️ <b>Quota atteint</b>\n\n"
            f"Vous avez utilisé {accounts_used}/{quota_max} comptes.\n"
            "Contactez l'admin pour augmenter votre quota.",
            parse_mode=ParseMode.HTML,
        )
        return

    remaining = quota_max - accounts_used
    context.user_data["awaiting"] = "create_type"
    await update.message.reply_text(
        "➕ <b>CRÉER UN COMPTE VPS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Quota restant : {remaining}/{quota_max}\n\n"
        "Choisissez le type de compte :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.account_type_keyboard(),
    )


async def handle_account_type_callback(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    type_map = {
        "type_http": "http",
        "type_zi": "zi",
        "type_both": "both",
    }
    account_type = type_map.get(query.data)
    if not account_type:
        return

    context.user_data["account_type"] = account_type
    context.user_data["awaiting"] = "create_port"

    type_labels = {"http": "HTTP Custom", "zi": "ZiVPN", "both": "HTTP Custom + ZiVPN"}
    await query.edit_message_text(
        f"✅ Type sélectionné : <b>{type_labels[account_type]}</b>\n\n"
        "🔌 Choisissez le port :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.port_choice_keyboard(),
    )


async def handle_port_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    port = int(query.data.split("_")[1])
    context.user_data["account_port"] = port
    context.user_data["awaiting"] = None

    await query.edit_message_text(
        "⏳ Création du compte en cours...",
        parse_mode=ParseMode.HTML,
    )
    await _finalize_account_creation(query, context)


async def _finalize_account_creation(query, context: ContextTypes.DEFAULT_TYPE):
    user = query.from_user
    account_type = context.user_data.get("account_type", "http")
    port = context.user_data.get("account_port", DEFAULT_PORT)

    # Vérifier quota à nouveau
    quota_max, accounts_used = db.get_user_quota(user.id)
    if accounts_used >= quota_max:
        await query.edit_message_text("❌ Quota atteint. Opération annulée.")
        return

    # Générer username unique
    base = (user.username or user.first_name or "user").lower()[:6]
    base = "".join(c for c in base if c.isalnum())
    ssh_user = utils.generate_username(base or "deku")

    # Récupérer validité depuis le code
    user_data = db.get_user(user.id)
    code_data = db.validate_code(user_data["code_used"]) if user_data else None
    validity_days = code_data["validity_days"] if code_data else 30

    # Créer l'utilisateur SSH sur VPS
    acc_info = db.create_account(
        owner_id=user.id,
        ssh_user=ssh_user,
        vps_ip=VPS_IP,
        port=port,
        account_type=account_type,
        validity_days=validity_days,
    )

    utils.create_ssh_user(ssh_user, acc_info["ssh_pass"], validity_days)

    quota_max, accounts_used = db.get_user_quota(user.id)
    remaining = quota_max - accounts_used

    db.add_log(user.id, user.username or "", "CREATE_ACCOUNT",
               f"type={account_type} port={port} user={ssh_user}")

    type_labels = {"http": "HTTP Custom", "zi": "ZiVPN", "both": "HTTP Custom + ZiVPN"}
    cfg = utils.get_config_string(acc_info, account_type)

    # Obtenir l'ID du compte créé
    accounts = db.get_user_accounts(user.id)
    new_acc_id = accounts[0]["id"] if accounts else 0

    text = (
        "✅ <b>COMPTE CRÉÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Type       : {type_labels[account_type]}\n"
        f"👤 Username   : <code>{ssh_user}</code>\n"
        f"🔑 Mot de passe : <code>{acc_info['ssh_pass']}</code>\n"
        f"🌐 IP         : {VPS_IP}\n"
        f"🔌 Port       : {port}\n"
        f"📅 Expiration : {validity_days} jours\n"
        f"📋 Quota restant : {remaining}/{quota_max}\n\n"
        f"📄 <b>Config :</b>\n<code>{cfg}</code>"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.account_actions_keyboard(new_acc_id),
    )

    # Notifier admin
    await send_admin_notification(
        context, "Création compte", user,
        f"Type={account_type.upper()} | IP={VPS_IP}:{port} | User={ssh_user}"
    )


# ── Config ────────────────────────────────────────────────────

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    accounts = db.get_user_accounts(user.id)
    active = [a for a in accounts if a["is_active"]]

    if not active:
        await update.message.reply_text(
            "📭 Aucun compte actif.\nCréez un compte d'abord.",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text(
        "📄 <b>VOS CONFIGS</b>\n━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML,
    )

    for acc in active:
        atype = acc["account_type"]
        cfg = utils.get_config_string(dict(acc), atype)
        type_label = {
            "http": "HTTP Custom", "zi": "ZiVPN", "both": "HTTP Custom + ZiVPN"
        }.get(atype, atype.upper())
        text = (
            f"📡 <b>{type_label}</b>\n"
            f"<code>{cfg}</code>\n"
            f"📅 Expire : {acc['expires_at'][:10]}"
        )
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.account_actions_keyboard(acc["id"]),
        )


# ── Renouveler ────────────────────────────────────────────────

async def show_renew_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    accounts = db.get_user_accounts(user.id)

    if not accounts:
        await update.message.reply_text("📭 Aucun compte à renouveler.")
        return

    buttons = []
    for acc in accounts:
        label = f"#{acc['id']} {acc['ssh_user']} [{acc['account_type'].upper()}]"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"renew_{acc['id']}"
        )])

    await update.message.reply_text(
        "🔄 <b>RENOUVELER UN COMPTE</b>\n\nChoisissez le compte :",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_renew_callback(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    account_id = int(query.data.split("_")[1])
    acc = db.get_account_by_id(account_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    await query.edit_message_text(
        f"🔄 <b>Renouveler #{account_id}</b>\n\nChoisissez la durée :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.renew_days_keyboard(account_id),
    )


async def handle_renew_days_callback(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    account_id = int(parts[1])
    days = int(parts[2])

    acc = db.get_account_by_id(account_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    db.renew_account(account_id, days)
    utils.renew_ssh_user(acc["ssh_user"], days)
    db.add_log(query.from_user.id, query.from_user.username or "",
               "RENEW_ACCOUNT", f"id={account_id} days={days}")

    await query.edit_message_text(
        f"✅ <b>Compte renouvelé de {days} jours !</b>\n"
        f"👤 Username : <code>{acc['ssh_user']}</code>",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_notification(
        context, f"Renouvellement {days}j", query.from_user,
        f"Compte #{account_id} ({acc['ssh_user']})"
    )


# ── Supprimer compte ──────────────────────────────────────────

async def handle_delete_account_callback(update: Update,
                                         context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    account_id = int(query.data.split("_")[-1])
    acc = db.get_account_by_id(account_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    await query.edit_message_text(
        f"⚠️ <b>Confirmer la suppression</b>\n\n"
        f"Compte : <code>{acc['ssh_user']}</code>\n"
        "Cette action est <b>irréversible</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.confirm_delete_keyboard(account_id),
    )


async def handle_confirm_delete_callback(update: Update,
                                         context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    account_id = int(query.data.split("_")[-1])
    acc = db.get_account_by_id(account_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    utils.delete_ssh_user(acc["ssh_user"], acc["ssh_pass"])
    db.delete_account(account_id)
    db.add_log(query.from_user.id, query.from_user.username or "",
               "DELETE_ACCOUNT", f"user={acc['ssh_user']}")

    await query.edit_message_text(
        f"🗑️ Compte <code>{acc['ssh_user']}</code> supprimé.",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_notification(
        context, "Suppression compte", query.from_user,
        acc["ssh_user"]
    )


# ── Télécharger config ────────────────────────────────────────

async def handle_dl_config_callback(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Génération du fichier...")
    account_id = int(query.data.split("_")[-1])
    acc = db.get_account_by_id(account_id)
    if not acc:
        await query.answer("❌ Compte introuvable.", show_alert=True)
        return

    path = utils.make_config_file(dict(acc), acc["account_type"])
    with open(path, "rb") as f:
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=f,
            filename=f"deku_config_{acc['ssh_user']}.txt",
            caption=(
                f"📄 Config — <code>{acc['ssh_user']}</code>\n"
                f"📡 {acc['account_type'].upper()} | 🔌 Port {acc['port']}"
            ),
            parse_mode=ParseMode.HTML,
        )
    try:
        os.remove(path)
    except Exception:
        pass


# ── Support ───────────────────────────────────────────────────

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting"] = "support_message"
    await update.message.reply_text(
        "💬 <b>SUPPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Décrivez votre problème et votre message sera transmis à l'admin :",
        parse_mode=ParseMode.HTML,
    )


async def send_support_message(update: Update,
                               context: ContextTypes.DEFAULT_TYPE,
                               message_text: str):
    user = update.effective_user
    name = f"@{user.username}" if user.username else user.first_name

    db.add_log(user.id, user.username or "", "SUPPORT", message_text[:100])

    # Envoyer aux admins
    for admin in db.get_all_admins():
        try:
            from keyboards import support_reply_keyboard
            await context.bot.send_message(
                chat_id=admin["telegram_id"],
                text=(
                    "💬 <b>Message Support</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 User   : {name}\n"
                    f"🆔 ID     : <code>{user.id}</code>\n\n"
                    f"📝 Message :\n{message_text}"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=support_reply_keyboard(user.id),
            )
        except Exception:
            pass

    context.user_data.pop("awaiting", None)
    await update.message.reply_text(
        "✅ <b>Message envoyé !</b>\n\nL'admin vous répondra bientôt.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_main_keyboard(),
    )
