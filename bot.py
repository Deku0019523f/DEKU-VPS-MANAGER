#!/usr/bin/env python3
# ============================================================
#   DEKU VPS MANAGER — bot.py
#   Admin : 1299831974 (@darkdeku225)
#   VPS   : 192.162.71.61
# ============================================================

import logging
import time as time_module
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

import database as db
import keyboards as kb
from config import BOT_TOKEN, ADMIN_ID, SPAM_DELAY

from admin_handlers import (
    admin_start, cmd_gencode, show_codes, show_users,
    show_all_accounts, show_stats, show_logs,
    ask_broadcast, do_broadcast, show_settings,
    cmd_blockuser, cmd_deleteuser, admin_create_account,
    handle_manage_user, handle_block_user, handle_deactivate_code,
)
from user_handlers import (
    user_start, registered_user_start, handle_access_code,
    show_my_accounts, start_create_account, show_config,
    show_renew_menu, show_support, send_support_message,
    handle_account_type_callback, handle_port_callback,
    handle_ssh_sessions_callback,
    handle_renew_callback, handle_renew_days_callback,
    handle_delete_account_callback, handle_confirm_delete_callback,
    handle_dl_config_callback,
    handle_sessions_callback, handle_hist_callback, handle_test_callback,
)
from v2ray_handlers import (
    handle_v2ray_protocol, handle_v2ray_sni_text, handle_v2ray_sni_skip,
    handle_v2ray_sni_mode, handle_v2ray_sessions,
    handle_v2dl_callback, handle_v2test_callback,
    handle_v2renew_callback, handle_v2renewdays_callback,
    handle_v2del_callback, handle_v2confirmdelete_callback,
    handle_v2ray_username,
)
import utils

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DekuVPS")

# ── Anti-spam ──────────────────────────────────────────────
_last_action: dict = {}

def check_spam(user_id: int) -> bool:
    now  = time_module.time()
    last = _last_action.get(user_id, 0)
    if now - last < SPAM_DELAY:
        return True
    _last_action[user_id] = now
    return False


# ── /start ────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if db.is_admin(user.id):
        await admin_start(update, context)
    elif db.is_blocked(user.id):
        await update.message.reply_text("🚫 Votre compte est suspendu.")
    elif db.is_registered(user.id):
        await registered_user_start(update, context)
    else:
        await user_start(update, context)


# ── Handler texte principal ───────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return

    text = update.message.text.strip()

    # ── ADMIN ────────────────────────────────────────────
    if db.is_admin(user.id):
        awaiting = context.user_data.get("awaiting")

        if awaiting == "broadcast":
            context.user_data.pop("awaiting", None)
            await do_broadcast(update, context, text)
            return

        if awaiting == "reply_support":
            target_id = context.user_data.pop("reply_target", None)
            context.user_data.pop("awaiting", None)
            if target_id:
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            "📩 <b>Réponse du support</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━━\n"
                            f"{text}"
                        ),
                        parse_mode=ParseMode.HTML,
                    )
                    await update.message.reply_text("✅ Réponse envoyée.")
                except Exception:
                    await update.message.reply_text("❌ Impossible d'envoyer la réponse.")
            return

        menu_map = {
            "👥 Utilisateurs":  show_users,
            "🎫 Codes":         show_codes,
            "➕ Créer compte":  admin_create_account,
            "📋 Comptes":       show_all_accounts,
            "📊 Stats VPS":     show_stats,
            "📜 Logs":          show_logs,
            "📢 Broadcast":     ask_broadcast,
            "⚙️ Paramètres":   show_settings,
        }
        if text in menu_map:
            await menu_map[text](update, context)
            return

        await update.message.reply_text(
            "❓ Commande inconnue.", reply_markup=kb.admin_main_keyboard()
        )
        return

    # ── BLOQUÉ ───────────────────────────────────────────
    if db.is_blocked(user.id):
        await update.message.reply_text("🚫 Votre compte est suspendu.")
        return

    # Anti-spam
    if check_spam(user.id):
        await update.message.reply_text("⏳ Attendez un instant...")
        return

    # ── NON INSCRIT → code d'accès ────────────────────────
    if not db.is_registered(user.id):
        if context.user_data.get("awaiting") == "access_code":
            await handle_access_code(update, context)
        else:
            context.user_data["awaiting"] = "access_code"
            await update.message.reply_text(
                "🎫 Entrez votre <b>code d'accès</b> :",
                parse_mode=ParseMode.HTML,
            )
        return

    # ── INSCRIT ───────────────────────────────────────────
    db.update_user_last_action(user.id)
    awaiting = context.user_data.get("awaiting")

    if awaiting == "support_message":
        context.user_data.pop("awaiting", None)
        await send_support_message(update, context, text)
        return

    # Flux V2Ray : username saisi en texte
    if awaiting == "v2ray_username":
        context.user_data.pop("awaiting", None)
        await handle_v2ray_username(update, context)
        return

    # Flux V2Ray : SNI saisi en texte
    if awaiting == "v2ray_sni":
        context.user_data.pop("awaiting", None)
        await handle_v2ray_sni_text(update, context)
        return

    menu_map = {
        "📂 Mes comptes":  show_my_accounts,
        "➕ Créer compte": start_create_account,
        "📄 Config":       show_config,
        "🔄 Renouveler":   show_renew_menu,
        "💬 Support":      show_support,
    }
    if text in menu_map:
        await menu_map[text](update, context)
        return

    await update.message.reply_text(
        "❓ Utilisez le menu ci-dessous.",
        reply_markup=kb.user_main_keyboard(),
    )


# ── Handler callbacks inline ──────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    data = query.data

    # ── Annuler ──────────────────────────────────────────
    if data == "cancel":
        await query.answer("Annulé.")
        await query.edit_message_text("❌ Action annulée.")
        for k in ["awaiting", "account_type", "account_port", "account_sessions",
                  "v2_username", "v2_protocol", "v2_sni_host",
                  "v2_sni_mode", "v2_max_sessions"]:
            context.user_data.pop(k, None)
        return

    if data in ("back_accounts", "back_users", "back_codes"):
        await query.answer()
        await query.edit_message_text("🔙 Retour au menu.")
        return

    # ── Flux création SSH ────────────────────────────────
    if data.startswith("type_"):
        await handle_account_type_callback(update, context)
        return
    if data.startswith("port_"):
        await handle_port_callback(update, context)
        return
    if data.startswith("sess_"):
        await handle_ssh_sessions_callback(update, context)
        return

    # ── Actions comptes SSH ──────────────────────────────
    if data.startswith("dl_config_"):
        await handle_dl_config_callback(update, context)
        return
    if data.startswith("sessions_"):
        await handle_sessions_callback(update, context)
        return
    if data.startswith("hist_"):
        await handle_hist_callback(update, context)
        return
    if data.startswith("test_"):
        await handle_test_callback(update, context)
        return
    if data.startswith("renew_") and not data.startswith("renewdays_"):
        await handle_renew_callback(update, context)
        return
    if data.startswith("renewdays_"):
        await handle_renew_days_callback(update, context)
        return
    if data.startswith("delete_acc_"):
        await handle_delete_account_callback(update, context)
        return
    if data.startswith("confirm_delete_"):
        await handle_confirm_delete_callback(update, context)
        return

    # ── Flux création V2Ray ──────────────────────────────
    if data.startswith("v2proto_"):
        await handle_v2ray_protocol(update, context)
        return
    if data == "v2sni_skip":
        await handle_v2ray_sni_skip(update, context)
        return
    if data.startswith("v2snimode_"):
        await handle_v2ray_sni_mode(update, context)
        return
    if data.startswith("v2sess_"):
        await handle_v2ray_sessions(update, context)
        return

    # ── Actions comptes V2Ray ────────────────────────────
    if data.startswith("v2dl_"):
        await handle_v2dl_callback(update, context)
        return
    if data.startswith("v2test_"):
        await handle_v2test_callback(update, context)
        return
    if data.startswith("v2renew_") and not data.startswith("v2renewdays_"):
        await handle_v2renew_callback(update, context)
        return
    if data.startswith("v2renewdays_"):
        await handle_v2renewdays_callback(update, context)
        return
    if data.startswith("v2del_") and not data.startswith("v2confirmdelete_"):
        await handle_v2del_callback(update, context)
        return
    if data.startswith("v2confirmdelete_"):
        await handle_v2confirmdelete_callback(update, context)
        return

    # ── Admin callbacks ──────────────────────────────────
    if data.startswith("manage_user_"):
        await handle_manage_user(update, context)
        return
    if data.startswith("block_") or data.startswith("unblock_"):
        await handle_block_user(update, context)
        return
    if data.startswith("deactivate_code_"):
        await handle_deactivate_code(update, context)
        return
    if data.startswith("reply_support_"):
        user_id = int(data.split("_")[-1])
        context.user_data["awaiting"]      = "reply_support"
        context.user_data["reply_target"]  = user_id
        await query.answer()
        await query.edit_message_text(
            "💬 Écrivez votre réponse pour l'utilisateur :"
        )
        return
    if data.startswith("useraccounts_"):
        uid      = int(data.split("_")[-1])
        ssh_accs = db.get_user_accounts(uid)
        v2_accs  = db.get_user_v2ray_accounts(uid)
        lines    = [f"📋 <b>Comptes — {uid}</b>"]
        for a in ssh_accs:
            active = "🟢" if a["is_active"] else "🔴"
            lines.append(
                f"{active} SSH <code>{a['ssh_user']}</code> "
                f"[{a['account_type'].upper()}] — {a['expires_at'][:10]}"
            )
        for a in v2_accs:
            active = "🟢" if a["is_active"] else "🔴"
            lines.append(
                f"{active} V2Ray <code>{a['username']}</code> "
                f"[{a['protocol'].upper()}] — {a['expires_at'][:10]}"
            )
        if not ssh_accs and not v2_accs:
            lines.append("📭 Aucun compte.")
        await query.edit_message_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )
        return
    if data.startswith("deluser_"):
        uid      = int(data.split("_")[-1])
        ssh_accs = db.get_user_accounts(uid)
        v2_accs  = db.get_user_v2ray_accounts(uid)
        for a in ssh_accs:
            utils.delete_ssh_user(a["ssh_user"], a["ssh_pass"])
            db.delete_account(a["id"])
        for a in v2_accs:
            utils.v2ray_del_user(a["uuid"])
            db.delete_v2ray_account(a["id"])
        db.delete_user(uid)
        db.add_log(query.from_user.id, query.from_user.username or "",
                   "DELETE_USER", f"id={uid}")
        await query.edit_message_text(
            f"🗑️ Utilisateur <code>{uid}</code> supprimé "
            f"({len(ssh_accs)} SSH + {len(v2_accs)} V2Ray).",
            parse_mode=ParseMode.HTML,
        )
        return

    await query.answer("Action inconnue.", show_alert=True)


# ── Job planifié : expire check ───────────────────────────
async def job_expire_check(context: ContextTypes.DEFAULT_TYPE):
    # SSH
    expired_ssh = db.get_expired_accounts()
    for acc in expired_ssh:
        utils.delete_ssh_user(acc["ssh_user"], acc["ssh_pass"])
        db.add_log(0, "SYSTEM", "AUTO_EXPIRE_SSH", acc["ssh_user"])
    db.deactivate_expired()

    # V2Ray
    expired_v2 = db.get_expired_v2ray_accounts()
    for acc in expired_v2:
        utils.v2ray_del_user(acc["uuid"])
        db.add_log(0, "SYSTEM", "AUTO_EXPIRE_V2RAY", acc["username"])
    db.deactivate_expired_v2ray()

    total = len(expired_ssh) + len(expired_v2)
    if total > 0:
        logger.info(f"[CRON] {total} compte(s) expiré(s) désactivés")
        msg = (
            f"⏰ <b>{total} compte(s) expirés automatiquement</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for a in expired_ssh:
            msg += f"🔴 SSH <code>{a['ssh_user']}</code>\n"
        for a in expired_v2:
            msg += f"🔴 V2Ray <code>{a['username']}</code>\n"
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID, text=msg, parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


# ── Main ──────────────────────────────────────────────────
def main():
    db.init_db()
    logger.info("✅ Base de données initialisée")
    logger.info("🚀 DEKU VPS MANAGER démarré — VPS : 192.162.71.61")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commandes
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("gencode",    cmd_gencode))
    app.add_handler(CommandHandler("users",      show_users))
    app.add_handler(CommandHandler("accounts",   show_all_accounts))
    app.add_handler(CommandHandler("stats",      show_stats))
    app.add_handler(CommandHandler("logs",       show_logs))
    app.add_handler(CommandHandler("broadcast",  ask_broadcast))
    app.add_handler(CommandHandler("blockuser",  cmd_blockuser))
    app.add_handler(CommandHandler("deleteuser", cmd_deleteuser))
    app.add_handler(CommandHandler("create",     start_create_account))
    app.add_handler(CommandHandler("myaccounts", show_my_accounts))
    app.add_handler(CommandHandler("config",     show_config))
    app.add_handler(CommandHandler("support",    show_support))

    # Messages texte
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_text
    ))

    # Callbacks inline
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Job expire check toutes les heures
    app.job_queue.run_repeating(job_expire_check, interval=3600, first=120)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
