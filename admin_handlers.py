# ============================================================
#   DEKU VPS MANAGER — Admin Handlers
# ============================================================

import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
import keyboards as kb
import utils


# ── Helpers ──────────────────────────────────────────────────

async def notify_admin(context: ContextTypes.DEFAULT_TYPE,
                       admin_id: int, text: str):
    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


async def send_admin_notification(context, action: str, user,
                                  detail: str = ""):
    username = f"@{user.username}" if user.username else user.first_name
    msg = (
        "🔔 <b>Nouvelle action</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User : {username}\n"
        f"🆔 ID   : <code>{user.id}</code>\n"
        f"⚡ Action : {action}\n"
    )
    if detail:
        msg += f"📝 Détail : {detail}\n"
    msg += f"🕒 Heure : {datetime.now().strftime('%H:%M:%S')}"

    for admin in db.get_all_admins():
        await notify_admin(context, admin["telegram_id"], msg)


# ── /start admin ─────────────────────────────────────────────

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        "👑 <b>DEKU VPS MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Bienvenue, <b>{user.first_name}</b> !\n\n"
        "🛡️ Vous êtes connecté en tant qu'<b>Admin</b>.\n"
        "Utilisez le menu ci-dessous pour gérer le panel."
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.admin_main_keyboard(),
    )


# ── /gencode ─────────────────────────────────────────────────

async def cmd_gencode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "❌ Usage : <code>/gencode &lt;jours&gt; &lt;quota&gt; &lt;utilisations&gt;</code>\n"
            "Exemple : <code>/gencode 30 5 3</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        days = int(args[0])
        quota = int(args[1])
        uses = int(args[2])
        if any(v <= 0 for v in [days, quota, uses]):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valeurs invalides. Utilisez des entiers positifs.")
        return

    code = db.create_code(days, quota, uses, update.effective_user.id)
    db.add_log(
        update.effective_user.id,
        update.effective_user.username or "",
        "GENCODE",
        f"validité={days}j quota={quota} uses={uses}"
    )

    text = (
        "✅ <b>Code d'accès généré</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Code     : <code>{code}</code>\n"
        f"📅 Validité : {days} jours\n"
        f"📋 Quota    : {quota} comptes max\n"
        f"🔁 Usages   : {uses} utilisations\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Bouton Codes ─────────────────────────────────────────────

async def show_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codes = db.get_all_codes()
    if not codes:
        await update.message.reply_text("📭 Aucun code créé.")
        return

    lines = ["🎫 <b>CODES D'ACCÈS</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for c in codes:
        status = "✅" if c["is_active"] and c["uses_left"] > 0 else "❌"
        lines.append(
            f"{status} <code>{c['code']}</code>\n"
            f"   📅 {c['validity_days']}j | 📋 {c['quota_max']} comptes | "
            f"🔁 {c['uses_left']}/{c['max_uses']} restants"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# ── Bouton Utilisateurs ──────────────────────────────────────

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    if not users:
        await update.message.reply_text("📭 Aucun utilisateur enregistré.")
        return

    lines = [f"👥 <b>UTILISATEURS ({len(users)})</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for u in users:
        name = f"@{u['username']}" if u["username"] else u["first_name"] or "N/A"
        blocked = " 🚫" if u["is_blocked"] else ""
        lines.append(
            f"• {name}{blocked}\n"
            f"  🆔 <code>{u['telegram_id']}</code> | "
            f"📋 {u['accounts_used']}/{u['quota_max']} comptes"
        )
        if len(lines) > 25:
            lines.append("... (tronqué)")
            break

    # Boutons inline pour gérer chaque user
    buttons = []
    for u in users[:10]:
        name = f"@{u['username']}" if u["username"] else str(u["telegram_id"])
        buttons.append([InlineKeyboardButton(
            f"⚙️ {name}", callback_data=f"manage_user_{u['telegram_id']}"
        )])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )


# ── Bouton Comptes ───────────────────────────────────────────

async def show_all_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = db.get_all_accounts()
    if not accounts:
        await update.message.reply_text("📭 Aucun compte créé.")
        return

    lines = [f"📋 <b>TOUS LES COMPTES ({len(accounts)})</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for a in accounts[:20]:
        owner = f"@{a['username']}" if a["username"] else str(a["owner_id"])
        active = "🟢" if a["is_active"] else "🔴"
        lines.append(
            f"{active} <code>{a['ssh_user']}</code> [{a['account_type'].upper()}]\n"
            f"   👤 {owner} | 🌐 {a['vps_ip']}:{a['port']}\n"
            f"   📅 Exp: {a['expires_at'][:10]}"
        )

    if len(accounts) > 20:
        lines.append(f"\n...et {len(accounts) - 20} autres comptes.")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Bouton Stats VPS ─────────────────────────────────────────

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_stats = db.get_stats()
    vps_stats = utils.get_vps_stats()

    from config import VPS_IP, DEFAULT_PORT
    text = (
        "📊 <b>STATS VPS — DEKU MANAGER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🖥️ <b>Système</b>\n"
        f"  CPU      : {vps_stats['cpu']}\n"
        f"  RAM      : {vps_stats['ram_used']} / {vps_stats['ram_total']}\n"
        f"  Disque   : {vps_stats['disk_used']} / {vps_stats['disk_total']}\n"
        f"  Uptime   : {vps_stats['uptime']}\n"
        f"  Load     : {vps_stats['load']}\n\n"
        "🔌 <b>Services UDP</b>\n"
        f"  HTTP Custom : {vps_stats['udpcustom_status']} (port 36712)\n"
        f"  ZiVPN       : {vps_stats['zivpn_status']} (port 5667)\n\n"
        "🌐 <b>VPS</b>\n"
        f"  IP         : <code>{VPS_IP}</code>\n"
        f"  Port SSH   : <code>{DEFAULT_PORT}</code>\n\n"
        "📋 <b>Panel</b>\n"
        f"  👥 Utilisateurs   : {db_stats['total_users']}\n"
        f"  🟢 Comptes actifs : {db_stats['total_accounts']}\n"
        f"  🔴 Expirés        : {db_stats['expired_accounts']}\n"
        f"  🎫 Codes actifs   : {db_stats['total_codes']}\n"
        f"  🚫 Bloqués        : {db_stats['blocked_users']}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Bouton Logs ──────────────────────────────────────────────

async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logs = db.get_logs(30)
    if not logs:
        await update.message.reply_text("📭 Aucun log.")
        return

    lines = ["📜 <b>LOGS RÉCENTS (30)</b>\n━━━━━━━━━━━━━━━━━━━━━"]
    for lg in logs:
        name = f"@{lg['username']}" if lg["username"] else str(lg["telegram_id"])
        ts = lg["timestamp"][:16]
        lines.append(f"[{ts}] {name} → {lg['action']}")
        if lg["detail"]:
            lines.append(f"  └ {lg['detail']}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# ── Bouton Broadcast ─────────────────────────────────────────

async def ask_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting"] = "broadcast"
    await update.message.reply_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Envoyez le message à diffuser à tous les utilisateurs :",
        parse_mode=ParseMode.HTML,
    )


async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       message_text: str):
    users = db.get_all_users()
    sent = 0
    failed = 0
    for u in users:
        if u["is_blocked"]:
            continue
        try:
            await context.bot.send_message(
                chat_id=u["telegram_id"],
                text=f"📢 <b>Message de l'admin</b>\n━━━━━━━━━━━━━━━━━━━━━\n{message_text}",
                parse_mode=ParseMode.HTML,
            )
            sent += 1
        except Exception:
            failed += 1

    db.add_log(
        update.effective_user.id,
        update.effective_user.username or "",
        "BROADCAST",
        f"envoyé={sent} échec={failed}"
    )
    await update.message.reply_text(
        f"✅ Broadcast terminé\n📤 Envoyé : {sent}\n❌ Échec : {failed}",
        reply_markup=kb.admin_main_keyboard(),
    )


# ── Bouton Paramètres ─────────────────────────────────────────

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import VPS_IP, DEFAULT_PORT
    text = (
        "⚙️ <b>PARAMÈTRES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 IP VPS    : <code>{VPS_IP}</code>\n"
        f"🔌 Port défaut : <code>{DEFAULT_PORT}</code>\n\n"
        "<i>Modifiez config.py pour changer ces valeurs.</i>\n\n"
        "📌 Commandes admin :\n"
        "/gencode — Créer un code\n"
        "/users — Voir utilisateurs\n"
        "/accounts — Tous les comptes\n"
        "/stats — Statistiques\n"
        "/logs — Journaux\n"
        "/broadcast — Message groupé\n"
        "/blockuser &lt;id&gt; — Bloquer un user\n"
        "/deleteuser &lt;id&gt; — Supprimer un user"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── /blockuser /deleteuser ───────────────────────────────────

async def cmd_blockuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /blockuser <telegram_id>")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID invalide.")
        return
    db.block_user(uid)
    db.add_log(update.effective_user.id, update.effective_user.username or "",
               "BLOCK_USER", f"id={uid}")
    await update.message.reply_text(f"🚫 Utilisateur {uid} bloqué.")


async def cmd_deleteuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /deleteuser <telegram_id>")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID invalide.")
        return

    # Supprimer ses comptes SSH
    accounts = db.get_user_accounts(uid)
    for acc in accounts:
        utils.delete_ssh_user(acc["ssh_user"])
        db.delete_account(acc["id"])

    db.delete_user(uid)
    db.add_log(update.effective_user.id, update.effective_user.username or "",
               "DELETE_USER", f"id={uid}")
    await update.message.reply_text(
        f"🗑️ Utilisateur {uid} supprimé avec {len(accounts)} compte(s)."
    )


# ── Création compte (Admin) ───────────────────────────────────

async def admin_create_account(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    """Admin crée un compte pour lui-même ou pour un user via /create."""
    context.user_data["creating_for"] = update.effective_user.id
    context.user_data["awaiting"] = "create_type"
    await update.message.reply_text(
        "➕ <b>CRÉER UN COMPTE</b>\n\nChoisissez le type :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.account_type_keyboard(),
    )


# ── Callbacks inline admin ───────────────────────────────────

async def handle_manage_user(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[-1])
    user = db.get_user(uid)
    if not user:
        await query.edit_message_text("❌ Utilisateur introuvable.")
        return

    name = f"@{user['username']}" if user["username"] else user["first_name"] or "N/A"
    is_blocked = user["is_blocked"] == 1
    text = (
        f"⚙️ <b>Gestion : {name}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID       : <code>{uid}</code>\n"
        f"📋 Comptes  : {user['accounts_used']}/{user['quota_max']}\n"
        f"🎫 Code     : <code>{user['code_used']}</code>\n"
        f"📅 Inscrit  : {user['joined_at'][:10]}\n"
        f"🚦 Statut   : {'🚫 Bloqué' if is_blocked else '✅ Actif'}"
    )
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.user_management_keyboard(uid, is_blocked),
    )


async def handle_block_user(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[-1])
    action = query.data.split("_")[0]

    if action == "block":
        db.block_user(uid)
        msg = f"🚫 Utilisateur {uid} bloqué."
    else:
        db.unblock_user(uid)
        msg = f"✅ Utilisateur {uid} débloqué."

    db.add_log(
        query.from_user.id, query.from_user.username or "",
        action.upper() + "_USER", f"id={uid}"
    )
    await query.edit_message_text(msg)


async def handle_deactivate_code(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = "_".join(query.data.split("_")[2:])
    db.deactivate_code(code)
    db.add_log(
        query.from_user.id, query.from_user.username or "",
        "DEACTIVATE_CODE", code
    )
    await query.edit_message_text(f"🚫 Code <code>{code}</code> désactivé.",
                                  parse_mode=ParseMode.HTML)
