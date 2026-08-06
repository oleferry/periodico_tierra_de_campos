"""Boletín diario en el canal de Telegram (@elterracampino).

Hasta ahora el canal solo recibía avisos de AEMET, que en una semana tranquila
son cero: el canal se quedaba mudo días enteros aunque el periódico publicara.

Esto manda un boletín SOLO cuando hay algo real que contar (noticias nuevas o
un aviso meteorológico vigente) — el tiempo NUNCA se manda solo, va siempre
acompañando a una noticia o a un aviso. Un día tranquilo sin nada nuevo, el
canal calla: es mejor silencio honesto que un mensaje de relleno diario que la
gente acabe silenciando.

De dónde salen los datos: de `data/boletin_hoy.json`, que escribe el build
(sitegen/build.py:escribir_resumen_dia) con los titulares YA redactados y
revisados por la cadena de sitegen/redactor.py. **Este script no llama a la IA**
— solo ordena y da formato — así que no puede inventar nada ni introducir texto
que no haya pasado por las reglas editoriales.

No repite: lo ya enviado se guarda en `data/boletin_enviados.json` por hash de
noticia, así que un día sin novedades no manda un mensaje vacío ni repetido.

Uso:
    python -m scripts.boletin_telegram --dry-run   # enseña el mensaje, no envía
    python -m scripts.boletin_telegram             # envía al canal
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RESUMEN = ROOT / "data" / "boletin_hoy.json"
ENVIADOS = ROOT / "data" / "boletin_enviados.json"
BASE = "https://elterracampino.es"
TIMEOUT = 30

# Cuántas noticias entran como mucho. Un boletín largo se lee peor y en Telegram
# se corta; si hay más, se remite a la web.
MAX_NOTICIAS = 5
EMOJI_AVISO = {"amarillo": "🟡", "naranja": "🟠", "rojo": "🔴"}


def cargar_enviados() -> set[str]:
    if not ENVIADOS.exists():
        return set()
    try:
        return set(json.loads(ENVIADOS.read_text(encoding="utf-8")).get("hashes", []))
    except (json.JSONDecodeError, OSError):
        return set()


def guardar_enviados(hashes: set[str]) -> None:
    # Se recorta para que el fichero no crezca sin fin; con 500 sobra de largo
    # para no repetir una noticia que siga en el feed varios días.
    ENVIADOS.write_text(
        json.dumps({"hashes": sorted(hashes)[-500:],
                    "actualizado": datetime.now(timezone.utc).isoformat()},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


def frase_tiempo(t: dict | None) -> str:
    if not t:
        return ""
    if t["tmin"] == t["tmax"]:
        return f"🌡️ Hoy en la comarca, {t['tmax']}° y {t['desc']}."
    return (f"🌡️ Hoy en la comarca: entre {t['tmin']}° y {t['tmax']}°, {t['desc']}. "
            f"El sitio más caluroso, {t['hot_name']} con {t['hot_t']}°.")


def componer(datos: dict, nuevas: list[dict]) -> str:
    partes: list[str] = [f"*El Terracampino* · {fecha_larga(datos['fecha'])}"]

    for a in datos.get("avisos", []):
        emoji = EMOJI_AVISO.get((a.get("nivel") or "").lower(), "⚠️")
        fen = f" por {a['fenomeno']}" if a.get("fenomeno") else ""
        partes.append(f"{emoji} *Aviso {a.get('nivel','')}*{fen} en {a.get('zona','')}.")

    t = frase_tiempo(datos.get("tiempo"))
    if t:
        partes.append(t)

    if nuevas:
        partes.append("\n📰 *Lo nuevo de hoy*")
        for n in nuevas[:MAX_NOTICIAS]:
            muni = f"{n['municipio']} · " if n.get("municipio") else ""
            if n.get("url"):
                partes.append(f"· {muni}[{n['titular']}]({n['url']})")
            else:
                partes.append(f"· {muni}{n['titular']}")
        if len(nuevas) > MAX_NOTICIAS:
            partes.append(f"…y {len(nuevas) - MAX_NOTICIAS} más en la web.")

    partes.append(f"\n👉 [Elige tu pueblo en elterracampino.es]({BASE}/)")
    return "\n".join(partes)


def fecha_larga(iso: str) -> str:
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} de {meses[d.month - 1]}"


def enviar(texto: str) -> None:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    canal = (os.getenv("TELEGRAM_CHANNEL_ID") or "").strip()
    if not token or not canal:
        raise SystemExit("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID")
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": canal, "text": texto, "parse_mode": "Markdown",
              "disable_web_page_preview": False},
        timeout=TIMEOUT,
    )
    if not r.ok:
        # Nunca imprimir r.url: lleva el token dentro.
        raise SystemExit(f"Telegram rechazó el boletín: HTTP {r.status_code} {r.text[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Boletín diario en el canal de Telegram")
    ap.add_argument("--dry-run", action="store_true", help="enseña el mensaje sin enviarlo")
    ap.add_argument("--forzar", action="store_true",
                    help="envía aunque no haya noticias nuevas (p. ej. solo el tiempo)")
    args = ap.parse_args()

    if not RESUMEN.exists():
        print("No hay data/boletin_hoy.json — ¿se ha ejecutado el build?", file=sys.stderr)
        return 0
    datos = json.loads(RESUMEN.read_text(encoding="utf-8"))

    enviados = cargar_enviados()
    nuevas = [n for n in datos.get("noticias", []) if n["hash"] not in enviados]

    if not nuevas and not datos.get("avisos") and not args.forzar:
        print("Nada nuevo que contar hoy: no se envía boletín.")
        return 0

    texto = componer(datos, nuevas)

    if args.dry_run:
        print("--- BOLETÍN QUE SE ENVIARÍA ---")
        print(texto)
        print("--- fin ---")
        print(f"({len(nuevas)} noticias nuevas de {len(datos.get('noticias', []))} del día)")
        return 0

    enviar(texto)
    guardar_enviados(enviados | {n["hash"] for n in nuevas})
    print(f"Boletín enviado al canal: {len(nuevas)} noticias nuevas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
