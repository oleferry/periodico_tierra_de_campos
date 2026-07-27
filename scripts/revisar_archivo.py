"""Revisión humana de las fotos antiguas que llegan al archivo comunitario.

Obligatoria: una foto antigua puede tener derechos de un tercero (un estudio
fotográfico, una editorial) o mostrar a personas identificables que quizá no
quieran salir. Eso lo valora una persona, no un automatismo. Mismo patrón que
scripts/revisar_esquelas.py: muestra cada foto y sus datos, y Daniel aprueba o
rechaza.

Uso:
    python -m scripts.revisar_archivo
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

from sitegen import almacen_archivo  # noqa: E402


def _abrir(datos: bytes) -> None:
    try:
        f = Path(tempfile.gettempdir()) / "archivo_revision.jpg"
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
    if not almacen_archivo.disponible():
        print("Sin credenciales de Supabase.")
        return 1

    pendientes = almacen_archivo.listar_pendientes()
    if not pendientes:
        print("No hay fotos del archivo pendientes de revisión.")
        return 0

    print(f"{len(pendientes)} foto(s) pendiente(s).\n")
    for f in pendientes:
        print("=" * 60)
        print(f"  Pueblo: {f.get('pueblo_slug')}")
        print(f"  Año: {f.get('anio') or '—'}")
        print(f"  Descripción: {f.get('descripcion') or '—'}")
        print(f"  Aporta (crédito, SÍ se publica): {f.get('autor') or '—'}")
        print(f"  Contacto (no se publica): {f.get('contacto') or '—'}")
        foto = almacen_archivo.descargar_foto_pendiente(f["id"])
        if foto:
            print("  (abriendo foto…)")
            _abrir(foto)
        print("\n  Comprueba derechos y personas identificables antes de aprobar.")
        resp = input("  ¿[a]probar / [r]echazar / [s]altar? ").strip().lower()
        if resp == "a":
            f["aprobada_en"] = datetime.now(timezone.utc).isoformat()
            almacen_archivo.aprobar(f["id"], f)
            print("  → Aprobada. Aparecerá en el archivo en el próximo build.")
        elif resp == "r":
            almacen_archivo.rechazar(f["id"])
            print("  → Rechazada y borrada.")
        else:
            print("  → Saltada.")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
