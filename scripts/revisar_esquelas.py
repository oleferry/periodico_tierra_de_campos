"""Revisión humana de las esquelas que llegan por el formulario de la web.

Es OBLIGATORIA y no delegable en una IA: una esquela publicada con un error, o
de quien no debía, hiere a una familia de verdad. Este script muestra cada
aviso pendiente (y su foto, si la hay) para que Daniel lo apruebe o lo rechace
uno a uno, como en scripts/revisar_fotos.py.

Antes de aprobar, lo suyo es VERIFICAR el aviso con la familia o la funeraria
usando el contacto que dejó quien lo envió (campo 'contacto', que no se
publica). Un formulario abierto puede traer bromas crueles: la revisión es la
red de seguridad.

Uso:
    python -m scripts.revisar_esquelas
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from sitegen import almacen_esquelas  # noqa: E402


def _abrir_foto(datos: bytes) -> None:
    try:
        f = Path(tempfile.gettempdir()) / "esquela_revision.jpg"
        f.write_bytes(datos)
        if sys.platform == "win32":
            os.startfile(f)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(f)], check=False)
        else:
            subprocess.run(["xdg-open", str(f)], check=False)
    except Exception as exc:  # noqa: BLE001
        print(f"  (no se pudo abrir la foto: {exc})")


def main() -> int:
    if not almacen_esquelas.disponible():
        print("Sin credenciales de Supabase (SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY).")
        return 1

    pendientes = almacen_esquelas.listar_pendientes()
    if not pendientes:
        print("No hay esquelas pendientes de revisión.")
        return 0

    print(f"{len(pendientes)} esquela(s) pendiente(s).\n")
    for e in pendientes:
        print("=" * 60)
        print(f"  {e['nombre']}" + (f", {e['edad']} años" if e.get("edad") else ""))
        print(f"  Pueblo: {e.get('pueblo_slug')}")
        if e.get("fecha_fallecimiento"):
            print(f"  Fallecimiento: {e['fecha_fallecimiento']}")
        if e.get("funeral"):
            print(f"  Funeral: {e['funeral']}")
        if e.get("texto"):
            print(f"  Texto: {e['texto']}")
        print(f"  Contacto de quien lo envía (NO se publica): {e.get('remitente_contacto') or '—'}")
        print(f"  Recibida: {e.get('recibido_en', '')[:16]}")
        if e.get("tiene_foto"):
            foto = almacen_esquelas.descargar_foto_pendiente(e["id"])
            if foto:
                print("  (abriendo foto para revisión…)")
                _abrir_foto(foto)

        print("\n  VERIFICA el aviso antes de aprobar (llama al contacto si hace falta).")
        resp = input("  ¿[a]probar / [r]echazar / [s]altar? ").strip().lower()
        if resp == "a":
            e["aprobada_en"] = datetime.now(timezone.utc).isoformat()
            almacen_esquelas.aprobar(e["id"], e)
            print("  → Aprobada. Aparecerá en la ficha de su pueblo en el próximo build.")
        elif resp == "r":
            almacen_esquelas.rechazar(e["id"])
            print("  → Rechazada y borrada.")
        else:
            print("  → Saltada, sigue pendiente.")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
