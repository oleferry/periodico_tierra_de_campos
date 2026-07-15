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

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
from sitegen import fotos, ia

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

ROOT = Path(__file__).resolve().parents[1]
FOTOS_DIR = ROOT / "data" / "fotos"
PENDIENTES = FOTOS_DIR / "pendientes.json"

# PILOTS está en sitegen.build, pero importar ese módulo aquí arrastraría todos
# los scrapers de la web (BOP, BOCyL, Playwright...) solo para leer una lista
# de slugs — se repite la lista mínima aquí a propósito, es solo texto plano.
PUEBLOS = {m.slug: m.name for m in load_municipios() if m.slug in {
    "mayorga", "villalon-de-campos", "villada", "medina-de-rioseco", "sahagun",
    "valderas", "carrion-de-los-condes", "paredes-de-nava", "villalpando",
    "becerril-de-campos", "fuentes-de-nava", "villarramiel",
}}

ELIGIENDO_PUEBLO, ESPERANDO_FOTO = range(2)


def _cargar_pendientes() -> list[dict]:
    if not PENDIENTES.exists():
        return []
    return json.loads(PENDIENTES.read_text(encoding="utf-8"))


def _guardar_pendientes(items: list[dict]) -> None:
    PENDIENTES.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


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
    nombre_archivo = f"{id_foto}.jpg"
    (FOTOS_DIR / "procesadas").mkdir(parents=True, exist_ok=True)
    (FOTOS_DIR / "procesadas" / nombre_archivo).write_bytes(procesada)

    pendientes = _cargar_pendientes()
    pendientes.append({
        "id": id_foto,
        "pueblo_slug": pueblo_slug,
        "pueblo_nombre": pueblo_nombre,
        "archivo": nombre_archivo,
        "pie": pie,
        "texto_remitente": texto_remitente,
        "remitente_telegram": update.effective_user.username or update.effective_user.first_name,
        "fecha": datetime.now(timezone.utc).isoformat(),
    })
    _guardar_pendientes(pendientes)

    await update.message.reply_text(
        f'Recibida. Pie de foto propuesto: "{pie}"\n\n'
        "Queda pendiente de revisión antes de publicarse — gracias."
    )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Vale, cancelado.")
    return ConversationHandler.END


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en .env — ver bot/README.md")

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
