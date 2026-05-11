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
from config import VPS_IP, DEFAULT_PORT
from admin_handlers import send_admin_notification


# ── Résumé compte SSH ─────────────────────────────────────────

def _account_summary(acc) -> str:
    active     = "🟢 Actif" if acc["is_active"] else "🔴 Expiré"
    atype      = acc["account_type"].upper()
    cfg        = utils.get_config_string(dict(acc), acc["account_type"])
    mx         = acc["max_sessions"] if "max_sessions" in acc.keys() else 0
    sess_label = "Illimité" if mx == 0 else str(mx)
    return (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID       : #{acc['id']}\n"
        f"📡 Type     : {atype}\n"
        f"👤 User     : <code>{acc['ssh_user']}</code>\n"
        f"🔑 Pass     : <code>{acc['ssh_pass']}</code>\n"
        f"🌐 IP       : {acc['vps_ip']}\n"
        f"🔌 Port     : {acc['port']}\n"
        f"👥 Sessions : {sess_label}\n"
        f"📅 Expire   : {acc['expires_at'][:10]}\n"
        f"🚦 Statut   : {active}\n\n"
        f"📋 <b>Config :</b>\n<code>{cfg}</code>"
    )


# ── /start utilisateur ────────────────────────────────────────

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data["awaiting"] = "access_code"
    await update.message.reply_text(
        "🌟 <b>DEKU VPS MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Bienvenue, <b>{user.first_name}</b> !\n\n"
        "🎫 Entrez votre <b>code d'accès</b> pour continuer :",
        parse_mode=ParseMode.HTML,
    )


async def registered_user_start(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    quota_max, accounts_used = db.get_user_quota(user.id)
    await update.message.reply_text(
        "🏠 <b>MENU PRINCIPAL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.first_name}\n"
        f"📋 Comptes : {accounts_used}/{quota_max}\n\n"
        "Choisissez une option :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_main_keyboard(),
    )


# ── Validation code d'accès ───────────────────────────────────

async def handle_access_code(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    code      = update.message.text.strip().upper()
    user      = update.effective_user
    code_data = db.validate_code(code)

    if not code_data:
        await update.message.reply_text(
            "❌ <b>Code invalide ou expiré.</b>\n\n"
            "Vérifiez votre code et réessayez.\n"
            "Contactez un admin pour obtenir un code.",
            parse_mode=ParseMode.HTML,
        )
        return

    db.register_user(user.id, user.username or "", user.first_name or "",
                     code, code_data["quota_max"])
    db.consume_code(code)
    db.add_log(user.id, user.username or "", "REGISTER", f"code={code}")
    context.user_data.pop("awaiting", None)

    await send_admin_notification(context, "Nouvelle inscription", user,
                                  f"Code : {code}")
    await update.message.reply_text(
        "✅ <b>Accès accordé !</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Code     : <code>{code}</code>\n"
        f"📋 Quota    : {code_data['quota_max']} comptes\n"
        f"📅 Validité : {code_data['validity_days']} jours\n\n"
        "Bienvenue sur <b>DEKU VPS MANAGER</b> !",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_main_keyboard(),
    )


# ── Mes comptes ───────────────────────────────────────────────

async def show_my_accounts(update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
    from v2ray_handlers import show_v2ray_accounts
    user     = update.effective_user
    ssh_accs = db.get_user_accounts(user.id)
    v2_accs  = db.get_user_v2ray_accounts(user.id)

    if not ssh_accs and not v2_accs:
        await update.message.reply_text(
            "📭 Vous n'avez aucun compte.\n\n"
            "Utilisez <b>➕ Créer compte</b> pour en créer un.",
            parse_mode=ParseMode.HTML,
        )
        return

    total = len(ssh_accs) + len(v2_accs)
    await update.message.reply_text(
        f"📂 <b>MES COMPTES ({total})</b>",
        parse_mode=ParseMode.HTML,
    )

    # Comptes SSH
    for acc in ssh_accs:
        await update.message.reply_text(
            _account_summary(acc),
            parse_mode=ParseMode.HTML,
            reply_markup=kb.account_actions_keyboard(acc["id"]),
        )

    # Comptes V2Ray
    await show_v2ray_accounts(update, context)


# ── Créer compte (SSH) ────────────────────────────────────────

async def start_create_account(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    quota_max, accounts_used = db.get_user_quota(user.id)

    if accounts_used >= quota_max:
        await update.message.reply_text(
            "⚠️ <b>Quota atteint</b>\n\n"
            f"{accounts_used}/{quota_max} comptes utilisés.\n"
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


# ── Callbacks type de compte ──────────────────────────────────

async def handle_account_type_callback(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
    from v2ray_handlers import start_v2ray_flow
    query = update.callback_query
    await query.answer()

    if query.data == "type_v2ray":
        await start_v2ray_flow(query, context)
        return

    type_map = {"type_http": "http", "type_zi": "zi", "type_both": "both"}
    account_type = type_map.get(query.data)
    if not account_type:
        return

    context.user_data["account_type"] = account_type
    type_labels = {"http": "HTTP Custom", "zi": "ZiVPN", "both": "HTTP Custom + ZiVPN"}
    await query.edit_message_text(
        f"✅ Type : <b>{type_labels[account_type]}</b>\n\n"
        "🔌 Choisissez le <b>port SSH</b> :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.port_choice_keyboard(),
    )


async def handle_port_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    port = int(query.data.split("_")[1])
    context.user_data["account_port"] = port
    account_type = context.user_data.get("account_type", "http")
    type_labels  = {"http": "HTTP Custom", "zi": "ZiVPN", "both": "HTTP Custom + ZiVPN"}

    await query.edit_message_text(
        f"✅ Port : <b>{port}</b>\n\n"
        "👥 Choisissez la <b>limite de connexions simultanées</b> :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.sessions_keyboard("sess"),
    )


async def handle_ssh_sessions_callback(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
    query        = update.callback_query
    await query.answer()
    max_sessions = int(query.data.split("_")[1])
    sess_label   = "Illimité" if max_sessions == 0 else str(max_sessions)
    context.user_data["account_sessions"] = max_sessions

    await query.edit_message_text(
        f"✅ Sessions max : <b>{sess_label}</b>\n\n"
        "⏳ Création du compte SSH en cours...",
        parse_mode=ParseMode.HTML,
    )
    await _finalize_account_creation(query, context)


async def _finalize_account_creation(query, context: ContextTypes.DEFAULT_TYPE):
    user         = query.from_user
    account_type = context.user_data.get("account_type", "http")
    port         = context.user_data.get("account_port", DEFAULT_PORT)
    max_sessions = context.user_data.get("account_sessions", 0)

    quota_max, accounts_used = db.get_user_quota(user.id)
    if accounts_used >= quota_max:
        await query.edit_message_text("❌ Quota atteint. Opération annulée.")
        return

    base     = "".join(c for c in (user.username or user.first_name or "deku").lower()
                       if c.isalnum())[:6]
    ssh_user = utils.generate_username(base or "deku")

    user_data = db.get_user(user.id)
    code_data = db.validate_code(user_data["code_used"]) if user_data else None
    validity_days = code_data["validity_days"] if code_data else 30

    acc_info = db.create_account(
        owner_id=user.id, ssh_user=ssh_user,
        vps_ip=VPS_IP, port=port,
        account_type=account_type,
        validity_days=validity_days,
        max_sessions=max_sessions,
    )
    utils.create_ssh_user(ssh_user, acc_info["ssh_pass"], validity_days,
                          account_type, max_sessions)

    # Nettoyage
    for k in ["account_type", "account_port", "account_sessions", "awaiting"]:
        context.user_data.pop(k, None)

    all_accs = db.get_user_accounts(user.id)
    new_id   = all_accs[0]["id"] if all_accs else 0

    quota_max, accounts_used = db.get_user_quota(user.id)
    remaining  = quota_max - accounts_used
    sess_label = "Illimité" if max_sessions == 0 else str(max_sessions)
    cfg        = utils.get_config_string(acc_info, account_type)
    type_labels = {"http": "HTTP Custom", "zi": "ZiVPN", "both": "HTTP Custom + ZiVPN"}

    await query.edit_message_text(
        "✅ <b>COMPTE SSH CRÉÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Type       : {type_labels[account_type]}\n"
        f"👤 Username   : <code>{ssh_user}</code>\n"
        f"🔑 Password   : <code>{acc_info['ssh_pass']}</code>\n"
        f"🌐 IP         : {VPS_IP}\n"
        f"🔌 Port SSH   : {port}\n"
        f"👥 Sessions   : {sess_label}\n"
        f"📅 Expiration : {validity_days} jours\n"
        f"📋 Quota rest : {remaining}/{quota_max}\n\n"
        f"📄 <b>Config :</b>\n<code>{cfg}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.account_actions_keyboard(new_id),
    )
    db.add_log(user.id, user.username or "", "CREATE_SSH",
               f"type={account_type} port={port} sess={max_sessions} user={ssh_user}")
    await send_admin_notification(
        context, "Création SSH", user,
        f"Type={account_type.upper()} | {VPS_IP}:{port} | User={ssh_user} | Sess={sess_label}"
    )


# ── Config ────────────────────────────────────────────────────

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    ssh_accs = [a for a in db.get_user_accounts(user.id) if a["is_active"]]
    v2_accs  = [a for a in db.get_user_v2ray_accounts(user.id) if a["is_active"]]

    if not ssh_accs and not v2_accs:
        await update.message.reply_text(
            "📭 Aucun compte actif.", parse_mode=ParseMode.HTML
        )
        return

    await update.message.reply_text(
        "📄 <b>VOS CONFIGS</b>\n━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML,
    )
    for acc in ssh_accs:
        cfg = utils.get_config_string(dict(acc), acc["account_type"])
        label = {"http": "HTTP Custom", "zi": "ZiVPN",
                 "both": "HTTP Custom + ZiVPN"}.get(acc["account_type"], "SSH")
        await update.message.reply_text(
            f"🔌 <b>{label}</b>\n<code>{cfg}</code>\n"
            f"📅 Expire : {acc['expires_at'][:10]}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.account_actions_keyboard(acc["id"]),
        )
    for acc in v2_accs:
        links = utils.generate_v2ray_links(dict(acc))
        await update.message.reply_text(
            f"🔷 <b>V2Ray — {acc['protocol'].upper()}</b>\n"
            f"🔗 443 : <code>{links['link_443'][:80]}...</code>\n"
            f"🔗 80  : <code>{links['link_80'][:80]}...</code>\n"
            f"📅 Expire : {acc['expires_at'][:10]}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.v2ray_account_actions_keyboard(acc["id"]),
        )


# ── Connexions actives (compte SSH) ──────────────────────────

async def handle_sessions_callback(update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer("Vérification...")
    acc_id    = int(query.data.split("_")[1])
    acc       = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    sessions   = utils.get_active_sessions(acc["ssh_user"])
    mx         = acc["max_sessions"] if "max_sessions" in acc.keys() else 0
    sess_limit = "Illimité" if mx == 0 else str(mx)

    if not sessions:
        txt = (
            f"📡 <b>Connexions actives — {acc['ssh_user']}</b>\n"
            f"👥 Limite : {sess_limit}\n\n"
            "✅ Aucune session active en ce moment."
        )
    else:
        lines = [
            f"📡 <b>Connexions actives — {acc['ssh_user']}</b>\n"
            f"👥 {len(sessions)}/{sess_limit} sessions\n"
        ]
        for i, s in enumerate(sessions, 1):
            lines.append(
                f"  {i}. 📍 {s['ip']} | {s['pts']} | {s['heure']}"
            )
        txt = "\n".join(lines)

    await query.edit_message_text(
        txt, parse_mode=ParseMode.HTML,
        reply_markup=kb.account_actions_keyboard(acc_id),
    )


# ── Historique de connexion ───────────────────────────────────

async def handle_hist_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer("Chargement...")
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    entries = utils.fetch_login_history(acc["ssh_user"])
    if not entries:
        txt = (
            f"🕐 <b>Historique — {acc['ssh_user']}</b>\n\n"
            "📭 Aucun historique disponible.\n"
            "<i>(La commande 'last' peut être vide si le VPS vient d'être réinstallé)</i>"
        )
    else:
        lines = [f"🕐 <b>Historique connexions — {acc['ssh_user']}</b>\n"]
        for e in entries:
            ip  = e["ip"]
            lat = e["login_at"]
            lines.append(f"  📍 {ip} — {lat}")
        txt = "\n".join(lines)

    await query.edit_message_text(
        txt, parse_mode=ParseMode.HTML,
        reply_markup=kb.account_actions_keyboard(acc_id),
    )


# ── Test de connectivité SSH ──────────────────────────────────

async def handle_test_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer("Test en cours...")
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    results = utils.test_account_connectivity(dict(acc))
    ssh_ok  = "✅" if results["ssh_tcp"]    else "❌"
    udp_ok  = "✅" if results["udp_custom"] else "❌"
    zi_ok   = "✅" if results["zivpn_udp"]  else "❌"
    atype   = acc["account_type"]

    lines = [
        f"🧪 <b>Test connectivité</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <code>{acc['ssh_user']}</code> [{atype.upper()}]\n\n"
        f"{ssh_ok} SSH TCP port {acc['port']} : "
        f"{'Accessible' if results['ssh_tcp'] else 'Inaccessible'}"
    ]
    if atype in ("http", "both"):
        lines.append(
            f"{udp_ok} HTTP Custom UDP {utils.UDPCUSTOM_UDP_PORT} : "
            f"{'En écoute' if results['udp_custom'] else 'Inactif'}"
        )
    if atype in ("zi", "both"):
        lines.append(
            f"{zi_ok} ZiVPN UDP {utils.ZIVPN_UDP_PORT} : "
            f"{'En écoute' if results['zivpn_udp'] else 'Inactif'}"
        )

    await query.edit_message_text(
        "\n".join(lines), parse_mode=ParseMode.HTML,
        reply_markup=kb.account_actions_keyboard(acc_id),
    )


# ── Renouveler ────────────────────────────────────────────────

async def show_renew_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    ssh_accs = db.get_user_accounts(user.id)
    v2_accs  = db.get_user_v2ray_accounts(user.id)

    if not ssh_accs and not v2_accs:
        await update.message.reply_text("📭 Aucun compte à renouveler.")
        return

    buttons = []
    for acc in ssh_accs:
        buttons.append([InlineKeyboardButton(
            f"🔌 #{acc['id']} {acc['ssh_user']} [{acc['account_type'].upper()}]",
            callback_data=f"renew_{acc['id']}"
        )])
    for acc in v2_accs:
        buttons.append([InlineKeyboardButton(
            f"🔷 #{acc['id']} {acc['username']} [{acc['protocol'].upper()}]",
            callback_data=f"v2renew_{acc['id']}"
        )])

    await update.message.reply_text(
        "🔄 <b>RENOUVELER UN COMPTE</b>\n\nChoisissez le compte :",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_renew_callback(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return
    await query.edit_message_text(
        f"🔄 <b>Renouveler #{acc_id}</b>\n\nChoisissez la durée :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.renew_days_keyboard(acc_id),
    )


async def handle_renew_days_callback(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")
    acc_id = int(parts[1])
    days   = int(parts[2])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    db.renew_account(acc_id, days)
    utils.renew_ssh_user(acc["ssh_user"], days)
    db.add_log(query.from_user.id, query.from_user.username or "",
               "RENEW_SSH", f"id={acc_id} days={days}")
    await query.edit_message_text(
        f"✅ <b>Compte renouvelé de {days} jours !</b>\n"
        f"👤 <code>{acc['ssh_user']}</code>",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_notification(
        context, f"Renouvellement SSH {days}j", query.from_user,
        f"#{acc_id} ({acc['ssh_user']})"
    )


# ── Supprimer compte SSH ──────────────────────────────────────

async def handle_delete_account_callback(update: Update,
                                         context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    acc_id = int(query.data.split("_")[-1])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return
    await query.edit_message_text(
        f"⚠️ <b>Confirmer la suppression</b>\n\n"
        f"Compte : <code>{acc['ssh_user']}</code>\n"
        "Cette action est <b>irréversible</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.confirm_delete_keyboard(acc_id),
    )


async def handle_confirm_delete_callback(update: Update,
                                         context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    acc_id = int(query.data.split("_")[-1])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    utils.delete_ssh_user(acc["ssh_user"], acc["ssh_pass"])
    db.delete_account(acc_id)
    db.add_log(query.from_user.id, query.from_user.username or "",
               "DELETE_SSH", f"user={acc['ssh_user']}")
    await query.edit_message_text(
        f"🗑️ Compte <code>{acc['ssh_user']}</code> supprimé.",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_notification(
        context, "Suppression SSH", query.from_user, acc["ssh_user"]
    )


# ── Télécharger config SSH ────────────────────────────────────

async def handle_dl_config_callback(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer("Génération du fichier...")
    acc_id = int(query.data.split("_")[-1])
    acc    = db.get_account_by_id(acc_id)
    if not acc:
        await query.answer("❌ Compte introuvable.", show_alert=True)
        return

    path = utils.make_config_file(dict(acc), acc["account_type"])
    with open(path, "rb") as f:
        await context.bot.send_document(
            chat_id=query.from_user.id, document=f,
            filename=f"deku_ssh_{acc['ssh_user']}.txt",
            caption=(
                f"📄 Config SSH — <code>{acc['ssh_user']}</code>\n"
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
        "Décrivez votre problème :",
        parse_mode=ParseMode.HTML,
    )


async def send_support_message(update: Update,
                               context: ContextTypes.DEFAULT_TYPE,
                               message_text: str):
    user = update.effective_user
    name = f"@{user.username}" if user.username else user.first_name
    db.add_log(user.id, user.username or "", "SUPPORT", message_text[:100])

    for admin in db.get_all_admins():
        try:
            await context.bot.send_message(
                chat_id=admin["telegram_id"],
                text=(
                    "💬 <b>Message Support</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {name} | 🆔 <code>{user.id}</code>\n\n"
                    f"{message_text}"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=kb.support_reply_keyboard(user.id),
            )
        except Exception:
            pass

    context.user_data.pop("awaiting", None)
    await update.message.reply_text(
        "✅ <b>Message envoyé !</b>\nL'admin vous répondra bientôt.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_main_keyboard(),
    )
