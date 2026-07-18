"""Bot de Telegram de El Terracampino: recibe fotos de vecinos, las procesa
(recorte + marco de marca, sitegen/fotos.py) y les pone pie de foto con IA
(sitegen/ia.py:pie_de_foto) — pero NO las publica solas. Quedan en
data/fotos/pendientes.json a la espera de que alguien las revise a mano
(scripts/revisar_fotos.py), igual que el tablón de negocios: "los anuncios
los envían vecinos... y se publican tras revisión. No se inventan."

Es un proceso APARTE del generador del sitio (sitegen.build): este bot tiene
que estar corriendo todo el rato para poder recibir mensajes (long polling),
no se lanza como parte de `python -m sitegen.build`. Necesita
TELEGRAM_BOT_TOKEN en el .env (ver bot/README.md para cómo crear el bot con
@BotFather — no hay forma de crear el bot automáticamente, lo tiene que
hacer una persona con una cuenta de Telegram).

Uso:
    python -m bot.telegram_bot
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from scrapers.common import load_municipios
from sitegen import almacen_fotos, fotos, ia

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")
# httpx (el cliente HTTP de python-telegram-bot) loguea a INFO cada petición
# CON LA URL COMPLETA — y la URL de la API de Telegram lleva el token dentro.
# Sin esto, el token acaba escrito en los logs de Railway en texto plano.
logging.getLogger("httpx").setLevel(logging.WARNING)

# PILOTS está en sitegen.build, pero importar ese módulo aquí arrastraría todos
# los scrapers de la web (BOP, BOCyL, Playwright...) solo para leer una lista
# de slugs — se repite la lista mínima aquí a propósito, es solo texto plano.
PUEBLOS = {m.slug: m.name for m in load_municipios() if m.slug in {
    "mayorga", "villalon-de-campos", "villada", "medina-de-rioseco", "sahagun",
    "valderas", "carrion-de-los-condes", "paredes-de-nava", "villalpando",
    "becerril-de-campos", "fuentes-de-nava", "villarramiel",
}}

ELIGIENDO_PUEBLO, ESPERANDO_FOTO = range(2)


async def foto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    botones = [[InlineKeyboardButton(nombre, callback_data=slug)] for slug, nombre in sorted(PUEBLOS.items(), key=lambda kv: kv[1])]
    await update.message.reply_text(
        "¿De qué pueblo es la foto?", reply_markup=InlineKeyboardMarkup(botones)
    )
    return ELIGIENDO_PUEBLO


async def pueblo_elegido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["pueblo_slug"] = query.data
    context.user_data["pueblo_nombre"] = PUEBLOS[query.data]
    await query.edit_message_text(
        f"Vale, {PUEBLOS[query.data]}. Manda la foto (puedes añadir un texto contando qué es)."
    )
    return ESPERANDO_FOTO


async def foto_recibida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pueblo_slug = context.user_data.get("pueblo_slug")
    pueblo_nombre = context.user_data.get("pueblo_nombre")
    if not pueblo_slug:
        await update.message.reply_text("Antes dime de qué pueblo es con /foto.")
        return ConversationHandler.END

    archivo_tg = await update.message.photo[-1].get_file()
    original = await archivo_tg.download_as_bytearray()
    texto_remitente = update.message.caption or ""

    try:
        procesada = fotos.procesar(bytes(original), pueblo=pueblo_nombre)
        pie = ia.pie_de_foto(procesada, pueblo=pueblo_nombre, texto_remitente=texto_remitente)
    except Exception:
        log.exception("Fallo procesando foto de %s", pueblo_nombre)
        await update.message.reply_text(
            "No he podido procesar la foto (fallo técnico). Prueba otra vez en un rato."
        )
        return ConversationHandler.END

    id_foto = uuid.uuid4().hex[:12]
    meta = {
        "id": id_foto,
        "pueblo_slug": pueblo_slug,
        "pueblo_nombre": pueblo_nombre,
        "archivo": f"{id_foto}.jpg",
        "pie": pie,
        "texto_remitente": texto_remitente,
        "remitente_telegram": update.effective_user.username or update.effective_user.first_name,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "recibida_en": datetime.now(timezone.utc).isoformat(),
    }

    # A Supabase, no al disco: el bot corre en Railway (disco efímero) y la
    # revisión corre en otra máquina — ver sitegen/almacen_fotos.py.
    try:
        almacen_fotos.guardar_pendiente(id_foto, procesada, meta)
    except Exception:
        log.exception("Fallo guardando foto de %s en el almacén", pueblo_nombre)
        await update.message.reply_text(
            "He procesado la foto pero no he podido guardarla (fallo técnico). "
            "Prueba otra vez en un rato, por favor."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f'Recibida. Pie de foto propuesto: "{pie}"\n\n'
        "Queda pendiente de revisión antes de publicarse — gracias."
    )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Vale, cancelado.")
    return ConversationHandler.END


def _latido_supabase() -> None:
    """Ping diario a Supabase para que el plan gratuito no pause el proyecto
    por inactividad (lo hace a los 7 días sin peticiones — le pasó al usuario
    el 2026-07-17 y tardó minutos en despausar). Como este bot corre 24/7 en
    Railway, es el sitio natural para el latido: una petición al día basta."""
    import time

    while True:
        try:
            almacen_fotos.listar("pendientes")
            log.info("Latido Supabase OK")
        except Exception as exc:  # noqa: BLE001 — el latido nunca tumba el bot
            log.warning("Latido Supabase falló: %s", exc)
        time.sleep(24 * 3600)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en .env — ver bot/README.md")

    import threading

    threading.Thread(target=_latido_supabase, daemon=True, name="latido-supabase").start()

    app = Application.builder().token(token).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("foto", foto_cmd)],
        states={
            ELIGIENDO_PUEBLO: [CallbackQueryHandler(pueblo_elegido)],
            ESPERANDO_FOTO: [MessageHandler(filters.PHOTO, foto_recibida)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    app.add_handler(conv)
    log.info("Bot arrancado, esperando mensajes…")
    app.run_polling()


if __name__ == "__main__":
    main()
