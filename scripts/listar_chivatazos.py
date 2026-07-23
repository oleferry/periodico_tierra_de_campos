"""Lee el buzón de chivatazos anónimos (web/api/chivatazo.js guarda ahí,
sitegen/almacen_chivatazos.py). NO publica nada — solo lista, para que Daniel
(con o sin ayuda de Claude en el chat) decida si algo da pie a investigar,
igual que con las pistas del radar: el chivatazo en sí nunca se publica tal
cual, como mucho alimenta hechos que luego se verifican aparte.

Uso:
    python -m scripts.listar_chivatazos              # lista los pendientes
    python -m scripts.listar_chivatazos --archivar ID  # marca uno como visto
"""

from __future__ import annotations

import argparse
import io
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from sitegen import almacen_chivatazos  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Buzón de chivatazos anónimos")
    ap.add_argument("--archivar", metavar="ID", help="marca un chivatazo como ya visto/valorado")
    args = ap.parse_args()

    if not almacen_chivatazos.disponible():
        print("Sin credenciales de Supabase: nada que hacer.")
        return 0

    if args.archivar:
        pendientes = almacen_chivatazos.listar_pendientes()
        match = next((c for c in pendientes if c["id"].startswith(args.archivar)), None)
        if not match:
            print(f"No hay ningún chivatazo pendiente con id {args.archivar}", file=sys.stderr)
            return 1
        almacen_chivatazos.archivar(match["id"], match)
        print(f"Archivado {match['id']}.")
        return 0

    pendientes = almacen_chivatazos.listar_pendientes()
    if not pendientes:
        print("Sin chivatazos pendientes.")
        return 0

    for c in pendientes:
        print(f"\n[{c['id']}] {c.get('recibido_en', '?')[:16]} — pueblo: {c.get('pueblo') or 'sin especificar'}")
        print(f"  {c['texto']}")
    print(f"\n{len(pendientes)} chivatazo(s) pendiente(s). Para archivar uno ya valorado:")
    print("  python -m scripts.listar_chivatazos --archivar <ID>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
