"""SCR-017 — Comprobador ligero de RuralGo (ruralgoespana.es).

RuralGo es un directorio de pueblos que deja gestionar el municipio a quien
se active (ayuntamiento, asociación o particular) — hoy los 12 pilotos
aparecen SIN gestionar. No es un scraper de contenido: solo vigila si eso
cambia, para no perdernos el día que alguno se active. robots.txt lo permite
(solo bloquea /admin, /api, /app, /login, /perfil).

No sabemos si algún pueblo llegará a activarse nunca — por eso "ligero":
una comprobación mensual basta, no hace falta nada más fino.

Uso:
    python -m scrapers.ruralgo_checker --dry-run
"""

from __future__ import annotations

import argparse
import sys

from scrapers.common import ScraperError, fetch

FRASE_SIN_GESTIONAR = "todavía no está gestionado en RuralGo"

# slug-INE de cada piloto en ruralgoespana.es (verificado a mano contra su
# sitemap el 2026-07-22 — no hay una API, solo estas páginas públicas).
PUEBLOS = {
    "villada": "villada-34206",
    "mayorga": "mayorga-47084",
    "sahagun": "sahagun-24139",
    "valderas": "valderas-24181",
    "villalpando": "villalpando-49250",
    "villarramiel": "villarramiel-34232",
    "villalon-de-campos": "villalondecampos-47214",
    "becerril-de-campos": "becerrildecampos-34029",
    "medina-de-rioseco": "medinaderioseco-47086",
    "carrion-de-los-condes": "carriondeloscondes-34047",
    "paredes-de-nava": "paredesdenava-34123",
    "fuentes-de-nava": "fuentesdenava-34076",
}

BASE = "https://www.ruralgoespana.es"


def comprobar(slug: str) -> bool:
    """True si el municipio SIGUE sin gestionar (nada que contar)."""
    html = fetch(f"{BASE}/{PUEBLOS[slug]}")
    return FRASE_SIN_GESTIONAR in html


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-017 — Comprobador de RuralGo")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime")
    ap.parse_args()

    activados = []
    for slug, ruta in PUEBLOS.items():
        try:
            sin_gestionar = comprobar(slug)
        except ScraperError as exc:
            print(f"  aviso: {slug} falló ({exc.error_type}: {exc})", file=sys.stderr)
            continue
        estado = "sin gestionar" if sin_gestionar else "¡ACTIVADO!"
        print(f"  {slug:24} {estado}  ({BASE}/{ruta})")
        if not sin_gestionar:
            activados.append(slug)

    if activados:
        print(f"\n¡Novedad! {len(activados)} pueblo(s) ya tienen RuralGo activado: {', '.join(activados)}")
        print("Merece la pena mirar qué han publicado y si conviene enlazarlo desde su ficha.")
    else:
        print(f"\nSin novedad: los {len(PUEBLOS)} pilotos siguen sin gestionar en RuralGo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
