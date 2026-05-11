# ============================================================
#   DEKU VPS MANAGER — V2Ray Handlers
#   Flux complet : username → protocole → SNI → sessions → création
# ============================================================

import os
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
import keyboards as kb
import utils
from config import VPS_IP
from admin_handlers import send_admin_notification


# ── Étape 1 : Démarrer le flux V2Ray ─────────────────────────

async def start_v2ray_flow(query, context: ContextTypes.DEFAULT_TYPE):
    """Appelé quand l'utilisateur choisit type_v2ray."""
    await query.edit_message_text(
        "🔷 <b>CRÉER UN COMPTE V2RAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Entrez le <b>nom d'utilisateur</b> souhaité\n"
        "<i>(ex : darkdeku, monvpn, user01)</i>",
        parse_mode=ParseMode.HTML,
    )
    context.user_data["awaiting"] = "v2ray_username"


# ── Étape 2 : Réception du username ──────────────────────────

async def handle_v2ray_username(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    raw     = update.message.text.strip()
    cleaned = "".join(c for c in raw if c.isalnum() or c in "-_")[:20]

    if len(cleaned) < 2:
        await update.message.reply_text(
            "❌ Username trop court ou invalide.\n"
            "Min 2 caractères alphanumériques."
        )
        return

    context.user_data["v2_username"] = cleaned
    context.user_data["awaiting"]    = "v2ray_protocol"

    await update.message.reply_text(
        f"✅ Username : <b>{cleaned}</b>\n\n"
        "🔵 Choisissez le <b>protocole</b> :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.v2ray_protocol_keyboard(),
    )


# ── Étape 3 : Protocole VMess / VLESS ────────────────────────

async def handle_v2ray_protocol(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    protocol = query.data.split("_")[1]  # vmess | vless
    context.user_data["v2_protocol"] = protocol
    context.user_data["awaiting"]    = "v2ray_sni"

    label = "VMess" if protocol == "vmess" else "VLESS"
    await query.edit_message_text(
        f"✅ Protocole : <b>{label}</b>\n\n"
        "🌐 Entrez votre <b>SNI / Bug Host</b>\n"
        "<i>Optionnel — ex : example.com</i>\n\n"
        "Ou appuyez sur <b>Passer</b> pour continuer sans SNI :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.v2ray_sni_skip_keyboard(),
    )


# ── Étape 4a : SNI entré (texte) ─────────────────────────────

async def handle_v2ray_sni_text(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    sni = update.message.text.strip().lower()
    # Validation basique domaine
    if len(sni) < 3 or "." not in sni:
        await update.message.reply_text(
            "❌ Domaine invalide.\nEx : example.com\n\nRéessayez :"
        )
        return

    context.user_data["v2_sni_host"] = sni
    context.user_data["awaiting"]    = None

    await update.message.reply_text(
        f"✅ SNI/Bug Host : <b>{sni}</b>\n\n"
        "🔧 Choisissez le <b>mode SNI</b> :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.v2ray_sni_mode_keyboard(),
    )


# ── Étape 4b : Skip SNI ───────────────────────────────────────

async def handle_v2ray_sni_skip(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["v2_sni_host"] = ""
    context.user_data["v2_sni_mode"] = "none"
    context.user_data["awaiting"]    = None

    await query.edit_message_text(
        "⏭️ Sans SNI — connexion directe au VPS\n\n"
        "👥 Choisissez la <b>limite de connexions simultanées</b> :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.sessions_keyboard("v2sess"),
    )


# ── Étape 5 : Mode SNI ───────────────────────────────────────

async def handle_v2ray_sni_mode(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode  = query.data.split("_")[1]  # reverse | default
    context.user_data["v2_sni_mode"] = mode

    mode_label = (
        "🔄 Reverse SNI (Bug as address)" if mode == "reverse"
        else "📍 Default SNI location"
    )
    sni = context.user_data.get("v2_sni_host", "")

    await query.edit_message_text(
        f"✅ Mode : <b>{mode_label}</b>\n"
        f"   SNI  : <code>{sni}</code>\n\n"
        "👥 Choisissez la <b>limite de connexions simultanées</b> :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.sessions_keyboard("v2sess"),
    )


# ── Étape 6 : Limite de sessions V2Ray ───────────────────────

async def handle_v2ray_sessions(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query       = update.callback_query
    await query.answer()
    max_sessions = int(query.data.split("_")[1])  # 0=illimité
    sess_label   = "Illimité" if max_sessions == 0 else str(max_sessions)

    context.user_data["v2_max_sessions"] = max_sessions
    await query.edit_message_text(
        f"✅ Sessions max : <b>{sess_label}</b>\n\n"
        "⏳ Création du compte V2Ray en cours...",
        parse_mode=ParseMode.HTML,
    )
    await _finalize_v2ray_creation(query, context)


# ── Étape 7 : Finalisation ────────────────────────────────────

async def _finalize_v2ray_creation(query, context: ContextTypes.DEFAULT_TYPE):
    user = query.from_user

    # Vérifier quota
    quota_max, accounts_used = db.get_user_quota(user.id)
    if accounts_used >= quota_max:
        await query.edit_message_text("❌ Quota atteint. Opération annulée.")
        return

    # Récupérer les données du flow
    username     = context.user_data.get("v2_username", f"user{user.id}")
    protocol     = context.user_data.get("v2_protocol", "vmess")
    sni_host     = context.user_data.get("v2_sni_host", "")
    sni_mode     = context.user_data.get("v2_sni_mode", "none")
    max_sessions = context.user_data.get("v2_max_sessions", 0)

    # Validité depuis le code
    user_data = db.get_user(user.id)
    code_data = db.validate_code(user_data["code_used"]) if user_data else None
    validity_days = code_data["validity_days"] if code_data else 30

    # Créer en base
    acc_info = db.create_v2ray_account(
        owner_id=user.id,
        username=username,
        protocol=protocol,
        sni_host=sni_host,
        sni_mode=sni_mode,
        max_sessions=max_sessions,
        vps_ip=VPS_IP,
        validity_days=validity_days,
        path=utils.V2RAY_WS_PATH,
    )

    # Ajouter l'UUID dans la config V2Ray sur le VPS
    utils.v2ray_add_user(acc_info["uuid"], protocol, max_sessions)

    # Nettoyer user_data
    for k in ["v2_username", "v2_protocol", "v2_sni_host",
               "v2_sni_mode", "v2_max_sessions", "awaiting"]:
        context.user_data.pop(k, None)

    # Récupérer l'ID du compte créé
    all_acc = db.get_user_v2ray_accounts(user.id)
    new_id  = all_acc[0]["id"] if all_acc else 0

    # Générer les liens
    links = utils.generate_v2ray_links(acc_info)

    # Infos affichage
    proto_label = "VMess" if protocol == "vmess" else "VLESS"
    sess_label  = "Illimité" if max_sessions == 0 else str(max_sessions)
    sni_info    = ""
    if sni_host:
        mode_txt = "Reverse SNI" if sni_mode == "reverse" else "Default SNI"
        sni_info = f"🌐 SNI      : <code>{sni_host}</code>\n🔧 Mode     : {mode_txt}\n"

    quota_max, accounts_used = db.get_user_quota(user.id)
    remaining = quota_max - accounts_used

    text = (
        "✅ <b>COMPTE V2RAY CRÉÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Username  : <code>{username}</code>\n"
        f"🔷 Protocole : {proto_label}\n"
        f"🔑 UUID      : <code>{acc_info['uuid']}</code>\n"
        f"🌐 IP VPS    : {VPS_IP}\n"
        f"🛤️ WS Path   : {utils.V2RAY_WS_PATH}\n"
        f"{sni_info}"
        f"👥 Sessions  : {sess_label}\n"
        f"📅 Expiration: {validity_days} jours\n"
        f"📋 Quota restant : {remaining}/{quota_max}\n\n"
        f"🔗 <b>Port 443 (TLS) :</b>\n<code>{links['link_443']}</code>\n\n"
        f"🔗 <b>Port 80 :</b>\n<code>{links['link_80']}</code>"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.v2ray_account_actions_keyboard(new_id),
    )

    db.add_log(user.id, user.username or "", "CREATE_V2RAY",
               f"proto={protocol} sni={sni_host} sess={max_sessions}")

    await send_admin_notification(
        context, "Création V2Ray", user,
        f"Proto={proto_label} | UUID={acc_info['uuid'][:8]}... | SNI={sni_host or 'non'}"
    )


# ── Afficher les comptes V2Ray ────────────────────────────────

async def show_v2ray_accounts(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    accounts = db.get_user_v2ray_accounts(user.id)
    if not accounts:
        return False  # Aucun compte V2Ray

    await update.message.reply_text(
        f"🔷 <b>MES COMPTES V2RAY ({len(accounts)})</b>",
        parse_mode=ParseMode.HTML,
    )
    for acc in accounts:
        links      = utils.generate_v2ray_links(dict(acc))
        active     = "🟢 Actif" if acc["is_active"] else "🔴 Expiré"
        proto      = acc["protocol"].upper()
        sess_label = "Illimité" if acc["max_sessions"] == 0 else str(acc["max_sessions"])
        sni_info   = ""
        if acc["sni_host"]:
            mode_txt = "Reverse" if acc["sni_mode"] == "reverse" else "Default"
            sni_info = f"🌐 SNI  : <code>{acc['sni_host']}</code> ({mode_txt})\n"

        text = (
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID      : #{acc['id']}\n"
            f"👤 User    : <code>{acc['username']}</code>\n"
            f"🔷 Proto   : {proto}\n"
            f"🔑 UUID    : <code>{acc['uuid'][:16]}...</code>\n"
            f"{sni_info}"
            f"👥 Sessions: {sess_label}\n"
            f"📅 Expire  : {acc['expires_at'][:10]}\n"
            f"🚦 Statut  : {active}\n\n"
            f"🔗 <b>443 :</b> <code>{links['link_443'][:60]}...</code>\n"
            f"🔗 <b>80  :</b> <code>{links['link_80'][:60]}...</code>"
        )
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.v2ray_account_actions_keyboard(acc["id"]),
        )
    return True


# ── Télécharger config V2Ray ──────────────────────────────────

async def handle_v2dl_callback(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer("Génération...")
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_v2ray_account_by_id(acc_id)
    if not acc:
        await query.answer("❌ Compte introuvable.", show_alert=True)
        return

    links = utils.generate_v2ray_links(dict(acc))
    path  = utils.make_v2ray_config_file(dict(acc), links)

    with open(path, "rb") as f:
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=f,
            filename=f"deku_v2ray_{acc['username']}.txt",
            caption=(
                f"🔷 Config V2Ray — <code>{acc['username']}</code>\n"
                f"📡 {acc['protocol'].upper()} | 🔌 443 + 80"
            ),
            parse_mode=ParseMode.HTML,
        )
    try:
        os.remove(path)
    except Exception:
        pass


# ── Tester connectivité V2Ray ─────────────────────────────────

async def handle_v2test_callback(update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer("Test en cours...")
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_v2ray_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    results = utils.test_v2ray_connectivity(dict(acc))
    v443 = "✅" if results["v2ray_443"] else "❌"
    v80  = "✅" if results["v2ray_80"]  else "❌"

    text = (
        f"🧪 <b>Test connectivité V2Ray</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <code>{acc['username']}</code> | {acc['protocol'].upper()}\n\n"
        f"{v443} Port 443 (TLS) : {'Accessible' if results['v2ray_443'] else 'Inaccessible'}\n"
        f"{v80}  Port 80        : {'Accessible' if results['v2ray_80']  else 'Inaccessible'}\n"
    )
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=kb.v2ray_account_actions_keyboard(acc_id),
    )


# ── Renouveler V2Ray ──────────────────────────────────────────

async def handle_v2renew_callback(update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_v2ray_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    await query.edit_message_text(
        f"🔄 <b>Renouveler V2Ray #{acc_id}</b>\n\nChoisissez la durée :",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.renew_days_keyboard(acc_id, prefix="v2renewdays"),
    )


async def handle_v2renewdays_callback(update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_")
    acc_id = int(parts[1])
    days   = int(parts[2])

    db.renew_v2ray_account(acc_id, days)
    acc = db.get_v2ray_account_by_id(acc_id)
    db.add_log(query.from_user.id, query.from_user.username or "",
               "RENEW_V2RAY", f"id={acc_id} days={days}")

    await query.edit_message_text(
        f"✅ Compte V2Ray renouvelé de <b>{days} jours</b> !\n"
        f"👤 <code>{acc['username'] if acc else acc_id}</code>",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_notification(
        context, f"Renouvellement V2Ray {days}j", query.from_user,
        f"ID #{acc_id}"
    )


# ── Supprimer V2Ray ───────────────────────────────────────────

async def handle_v2del_callback(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_v2ray_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    await query.edit_message_text(
        f"⚠️ <b>Supprimer le compte V2Ray</b>\n\n"
        f"👤 <code>{acc['username']}</code> [{acc['protocol'].upper()}]\n"
        "Cette action est <b>irréversible</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.v2ray_confirm_delete_keyboard(acc_id),
    )


async def handle_v2confirmdelete_callback(update: Update,
                                          context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    acc_id = int(query.data.split("_")[1])
    acc    = db.get_v2ray_account_by_id(acc_id)
    if not acc:
        await query.edit_message_text("❌ Compte introuvable.")
        return

    utils.v2ray_del_user(acc["uuid"])
    db.delete_v2ray_account(acc_id)
    db.add_log(query.from_user.id, query.from_user.username or "",
               "DELETE_V2RAY", f"user={acc['username']} uuid={acc['uuid'][:8]}")

    await query.edit_message_text(
        f"🗑️ Compte V2Ray <code>{acc['username']}</code> supprimé.",
        parse_mode=ParseMode.HTML,
    )
    await send_admin_notification(
        context, "Suppression V2Ray", query.from_user,
        f"{acc['username']} ({acc['protocol'].upper()})"
    )
