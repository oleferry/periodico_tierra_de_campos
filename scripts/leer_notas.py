"""Lee las notas privadas que el administrador ha ido mandando al bot
(sitegen/almacen_notas.py, bucket 'notas' de Supabase) y las imprime de la
más reciente a la más antigua. Con --md las vuelca en formato lista para
pegarlas donde quieras (p. ej. en docs/ideas-*.md).

Uso:
    python -m scripts.leer_notas
    python -m scripts.leer_notas --md
"""

from __future__ import annotations

import argparse
import io
import sys

from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from sitegen import almacen_notas  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Lee las notas del bloc de notas del bot")
    ap.add_argument("--md", action="store_true", help="formato lista Markdown")
    args = ap.parse_args()

    if not almacen_notas.disponible():
        print("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en .env", file=sys.stderr)
        return 1

    notas = almacen_notas.listar()
    if not notas:
        print("No hay notas todavía.")
        return 0

    print(f"# {len(notas)} notas\n" if args.md else f"{len(notas)} notas:\n")
    for n in notas:
        fecha = (n.get("fecha") or "")[:16].replace("T", " ")
        if args.md:
            print(f"- {n['texto']}  \n  _({fecha})_")
        else:
            print(f"[{fecha}] {n['texto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
