#!/usr/bin/env python3
# ============================================================
#   DEKU VPS MANAGER — bot.py
#   Telegram ID admin : 1299831974 (@darkdeku225)
# ============================================================

import logging
import asyncio
import time as time_module
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
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
    handle_renew_callback, handle_renew_days_callback,
    handle_delete_account_callback, handle_confirm_delete_callback,
    handle_dl_config_callback,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("DekuVPS")

# ── Anti-spam ─────────────────────────────────────────────────
_last_action: dict = {}

def check_spam(user_id: int) -> bool:
    now = time_module.time()
    last = _last_action.get(user_id, 0)
    if now - last < SPAM_DELAY:
        return True
    _last_action[user_id] = now
    return False


# ── /start ────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    # Admin
    if db.is_admin(user.id):
        await admin_start(update, context)
        return

    # Bloqué
    if db.is_blocked(user.id):
        await update.message.reply_text(
            "🚫 <b>Accès refusé.</b>\nVotre compte a été suspendu.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Déjà inscrit
    if db.is_registered(user.id):
        await registered_user_start(update, context)
        return

    # Nouveau → demander le code
    await user_start(update, context)


# ── /myaccounts ───────────────────────────────────────────────
async def cmd_myaccounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _require_user(update):
        return
    await show_my_accounts(update, context)


async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db.is_admin(update.effective_user.id):
        await admin_create_account(update, context)
        return
    if not _require_user(update):
        return
    await start_create_account(update, context)


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _require_user(update):
        return
    await show_config(update, context)


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _require_user(update):
        return
    await show_support(update, context)


def _require_user(update: Update) -> bool:
    user = update.effective_user
    if db.is_blocked(user.id):
        asyncio.get_event_loop()
        return False
    if not db.is_registered(user.id):
        return False
    return True


# ── Handler principal des messages texte ─────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return

    text = update.message.text.strip()

    # Anti-spam
    if check_spam(user.id) and not db.is_admin(user.id):
        await update.message.reply_text("⏳ Attendez un instant...")
        return

    # ── ADMIN ──────────────────────────────────────────────
    if db.is_admin(user.id):
        db.update_user_last_action(user.id)

        # Attente broadcast
        if context.user_data.get("awaiting") == "broadcast":
            context.user_data.pop("awaiting", None)
            await do_broadcast(update, context, text)
            return

        # Attente réponse support admin
        if context.user_data.get("awaiting") == "reply_support":
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
                    await update.message.reply_text("✅ Réponse envoyée à l'utilisateur.")
                except Exception:
                    await update.message.reply_text("❌ Impossible d'envoyer la réponse.")
            return

        # Boutons admin menu
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
            "❓ Commande inconnue.",
            reply_markup=kb.admin_main_keyboard(),
        )
        return

    # ── BLOQUÉ ────────────────────────────────────────────
    if db.is_blocked(user.id):
        await update.message.reply_text("🚫 Votre compte est suspendu.")
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

    # ── UTILISATEUR INSCRIT ────────────────────────────────
    db.update_user_last_action(user.id)

    # Attente message support
    if context.user_data.get("awaiting") == "support_message":
        context.user_data.pop("awaiting", None)
        await send_support_message(update, context, text)
        return

    # Boutons user menu
    menu_map = {
        "📂 Mes comptes":   show_my_accounts,
        "➕ Créer compte":  start_create_account,
        "📄 Config":        show_config,
        "🔄 Renouveler":    show_renew_menu,
        "💬 Support":       show_support,
    }
    if text in menu_map:
        await menu_map[text](update, context)
        return

    await update.message.reply_text(
        "❓ Utilisez le menu ci-dessous.",
        reply_markup=kb.user_main_keyboard(),
    )


# ── Handler callbacks inline ──────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Annulation
    if data == "cancel":
        await query.answer("Annulé.")
        await query.edit_message_text("❌ Action annulée.")
        context.user_data.pop("awaiting", None)
        return

    # Retours
    if data in ("back_accounts", "back_users", "back_codes"):
        await query.answer()
        await query.edit_message_text("🔙 Retour au menu.")
        return

    # Créer compte — type
    if data.startswith("type_"):
        await handle_account_type_callback(update, context)
        return

    # Créer compte — port
    if data.startswith("port_"):
        await handle_port_callback(update, context)
        return

    # Télécharger config
    if data.startswith("dl_config_"):
        await handle_dl_config_callback(update, context)
        return

    # Renouveler — sélection compte
    if data.startswith("renew_") and not data.startswith("renewdays_"):
        await handle_renew_callback(update, context)
        return

    # Renouveler — durée
    if data.startswith("renewdays_"):
        await handle_renew_days_callback(update, context)
        return

    # Supprimer compte
    if data.startswith("delete_acc_"):
        await handle_delete_account_callback(update, context)
        return

    # Confirmer suppression
    if data.startswith("confirm_delete_"):
        await handle_confirm_delete_callback(update, context)
        return

    # Admin — gérer user
    if data.startswith("manage_user_"):
        await handle_manage_user(update, context)
        return

    # Admin — bloquer/débloquer
    if data.startswith("block_") or data.startswith("unblock_"):
        await handle_block_user(update, context)
        return

    # Admin — désactiver code
    if data.startswith("deactivate_code_"):
        await handle_deactivate_code(update, context)
        return

    # Support — répondre à user
    if data.startswith("reply_support_"):
        user_id = int(data.split("_")[-1])
        context.user_data["awaiting"] = "reply_support"
        context.user_data["reply_target"] = user_id
        await query.answer()
        await query.edit_message_text(
            "💬 Écrivez votre réponse à envoyer à l'utilisateur :"
        )
        return

    # Admin — comptes d'un user
    if data.startswith("useraccounts_"):
        uid = int(data.split("_")[-1])
        accounts = db.get_user_accounts(uid)
        if not accounts:
            await query.edit_message_text("📭 Cet utilisateur n'a aucun compte.")
        else:
            lines = [f"📋 <b>Comptes de l'utilisateur {uid}</b>"]
            for a in accounts:
                active = "🟢" if a["is_active"] else "🔴"
                lines.append(
                    f"{active} <code>{a['ssh_user']}</code> "
                    f"[{a['account_type'].upper()}] — Exp: {a['expires_at'][:10]}"
                )
            await query.edit_message_text(
                "\n".join(lines), parse_mode=ParseMode.HTML
            )
        return

    # Admin — supprimer user via inline
    if data.startswith("deluser_"):
        uid = int(data.split("_")[-1])
        accounts = db.get_user_accounts(uid)
        import utils
        for acc in accounts:
            utils.delete_ssh_user(acc["ssh_user"], acc["ssh_pass"])
            db.delete_account(acc["id"])
        db.delete_user(uid)
        db.add_log(query.from_user.id, query.from_user.username or "",
                   "DELETE_USER", f"id={uid}")
        await query.edit_message_text(
            f"🗑️ Utilisateur <code>{uid}</code> supprimé "
            f"avec {len(accounts)} compte(s).",
            parse_mode=ParseMode.HTML,
        )
        return

    await query.answer("Action inconnue.", show_alert=True)


# ── Tâche planifiée : nettoyage des comptes expirés ──────────
async def job_expire_check(context: ContextTypes.DEFAULT_TYPE):
    """Vérifie et désactive les comptes expirés toutes les heures."""
    import utils
    expired = db.get_expired_accounts()
    if not expired:
        return

    logger.info(f"[CRON] {len(expired)} compte(s) expiré(s) trouvé(s)")
    for acc in expired:
        utils.delete_ssh_user(acc["ssh_user"], acc["ssh_pass"])
        db.add_log(0, "SYSTEM", "AUTO_EXPIRE", acc["ssh_user"])

    db.deactivate_expired()

    # Notifier l'admin
    if expired:
        msg = (
            "⏰ <b>Comptes expirés automatiquement</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for acc in expired:
            msg += f"🔴 <code>{acc['ssh_user']}</code> [{acc['account_type'].upper()}]\n"

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=msg,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


# ── Main ──────────────────────────────────────────────────────
def main():
    # Initialiser la base de données
    db.init_db()
    logger.info("Base de données initialisée.")

    # Construire l'application
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Commandes ──
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("gencode", cmd_gencode))
    app.add_handler(CommandHandler("users", show_users))
    app.add_handler(CommandHandler("accounts", show_all_accounts))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("logs", show_logs))
    app.add_handler(CommandHandler("broadcast", ask_broadcast))
    app.add_handler(CommandHandler("blockuser", cmd_blockuser))
    app.add_handler(CommandHandler("deleteuser", cmd_deleteuser))
    app.add_handler(CommandHandler("create", cmd_create))
    app.add_handler(CommandHandler("myaccounts", cmd_myaccounts))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("support", cmd_support))

    # ── Messages texte ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ── Callbacks inline ──
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Job planifié : expire check toutes les heures ──
    job_queue = app.job_queue
    job_queue.run_repeating(job_expire_check, interval=3600, first=60)

    logger.info("🚀 DEKU VPS MANAGER démarré !")
    logger.info(f"   Admin principal : {ADMIN_ID} (@darkdeku225)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
