"""Publica en el canal de Telegram los avisos meteorológicos NUEVOS que afectan
a la comarca (scrapers/aemet_avisos.py).

Es el único contenido del proyecto que se publica solo y sin pasar por
revisión, y hay una razón para la excepción: es un dato oficial de AEMET que se
reproduce literalmente (nivel, fenómeno, zona y horas), no una redacción propia
ni una interpretación. Publicar tarde un aviso naranja de tormenta no sirve de
nada. Aun así, se aplican tres cautelas:

  · Solo avisos de las zonas de la comarca (ya filtrado en el scraper).
  · Solo una vez por aviso: se recuerda lo enviado en data/cache/, para que
    ejecutarlo cada hora no repita el mismo aviso una y otra vez.
  · Nunca se adorna ni se dramatiza: se dice lo que dice AEMET y se enlaza a
    AEMET. La política editorial prohíbe el alarmismo.

Uso:
    python -m scripts.avisar_meteo --dry-run   # enseña qué enviaría
    python -m scripts.avisar_meteo
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
from dotenv import load_dotenv

load_dotenv()

from scrapers.aemet_avisos import avisos, clave, mensaje_telegram  # noqa: E402
from scrapers.common import ROOT  # noqa: E402

# En data/cache/ (ya en .gitignore): es estado local, no contenido del sitio.
# Si se perdiera, lo peor que pasa es que se reenvíe un aviso ya enviado.
ENVIADOS = ROOT / "data" / "cache" / "avisos_enviados.json"


def _cargar_enviados() -> set[str]:
    if not ENVIADOS.exists():
        return set()
    try:
        return set(json.loads(ENVIADOS.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return set()


def _guardar_enviados(claves: set[str]) -> None:
    ENVIADOS.parent.mkdir(parents=True, exist_ok=True)
    # Se guardan solo las últimas 200: la lista no debe crecer sin fin.
    ENVIADOS.write_text(json.dumps(sorted(claves)[-200:], ensure_ascii=False, indent=2),
                        encoding="utf-8")


def _publicar(texto: str) -> bool:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    canal = (os.getenv("TELEGRAM_CHANNEL_ID") or "").strip()
    if not token or not canal:
        print("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID en .env", file=sys.stderr)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": canal, "text": texto, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"  error de red publicando: {exc}", file=sys.stderr)
        return False
    if not r.ok:
        # Nunca imprimir r.url: lleva el token del bot dentro.
        print(f"  Telegram respondió HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Avisa por Telegram de alertas meteorológicas nuevas")
    ap.add_argument("--dry-run", action="store_true", help="enseña qué enviaría, sin enviar nada")
    args = ap.parse_args()

    vigentes = avisos()
    if not vigentes:
        print("Sin avisos vigentes en la comarca.")
        return 0

    enviados = _cargar_enviados()
    nuevos = [a for a in vigentes if clave(a) not in enviados]
    if not nuevos:
        print(f"{len(vigentes)} aviso(s) vigentes, todos ya avisados anteriormente.")
        return 0

    for a in nuevos:
        texto = mensaje_telegram(a)
        if args.dry_run:
            print("--- se enviaría ---")
            print(texto)
            continue
        if _publicar(texto):
            enviados.add(clave(a))
            print(f"Avisado: {a['nivel']} por {a['fenomeno']} en {a['zona']}")

    if not args.dry_run:
        _guardar_enviados(enviados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
