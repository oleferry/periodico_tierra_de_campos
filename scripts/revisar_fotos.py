"""Revisión manual de las fotos que llegan por el bot de Telegram, antes de
publicarlas — mismo principio que el tablón de negocios: nada se publica
sin que alguien lo mire primero. Mueve cada foto de 'pendientes' a
'aprobadas' en el almacén compartido (o la descarta), una a una.

La cola vive en Supabase Storage (sitegen/almacen_fotos.py), no en disco:
el bot que recibe las fotos corre en Railway y esto corre en el portátil.

Abre cada foto procesada con el visor de imágenes por defecto del sistema
para que puedas verla antes de decidir.

Uso:
    python -m scripts.revisar_fotos
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sitegen import almacen_fotos  # noqa: E402

# La consola de Windows viene en cp1252 y revienta con las tildes de los pies.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _abrir_imagen(ruta: Path) -> None:
    try:
        if sys.platform == "win32":
            import os
            os.startfile(ruta)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(ruta)], check=False)
        else:
            subprocess.run(["xdg-open", str(ruta)], check=False)
    except OSError as exc:
        print(f"  (no se pudo abrir el visor automáticamente: {exc})")


def main() -> int:
    # La cola vive en Supabase, no en disco: el bot que recibe las fotos corre
    # en Railway y esto corre aquí — ver sitegen/almacen_fotos.py.
    if not almacen_fotos.disponible():
        print("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY en .env.", file=sys.stderr)
        return 1

    pendientes = almacen_fotos.listar_pendientes()
    if not pendientes:
        print("No hay fotos pendientes de revisión.")
        return 0

    revisadas = 0
    for foto in pendientes:
        print(f"\n{'=' * 60}")
        print(f"Pueblo: {foto['pueblo_nombre']}")
        print(f"Pie de foto propuesto: {foto['pie']}")
        if foto.get("texto_remitente"):
            print(f"Texto del remitente: {foto['texto_remitente']}")
        print(f"De: {foto.get('remitente_telegram', '?')} · {foto['fecha']}")

        # Se descarga a un temporal solo para poder verla con el visor.
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(almacen_fotos.descargar(f"pendientes/{foto['id']}.jpg"))
            ruta = Path(tmp.name)
        _abrir_imagen(ruta)

        resp = input("¿Aprobar? [s/N/e=editar pie/q=salir] ").strip().lower()
        ruta.unlink(missing_ok=True)
        if resp == "q":
            break
        if resp == "e":
            nuevo_pie = input(f"Nuevo pie de foto (enter para dejar '{foto['pie']}'): ").strip()
            if nuevo_pie:
                foto["pie"] = nuevo_pie
            resp = input("¿Aprobar con este pie? [s/N] ").strip().lower()

        if resp == "s":
            almacen_fotos.aprobar(foto["id"], foto)
            print("  → aprobada.")
        else:
            almacen_fotos.rechazar(foto["id"])
            print("  → descartada.")
        revisadas += 1

    print(f"\nListo. {revisadas} revisadas, "
          f"{len(almacen_fotos.listar_pendientes())} siguen pendientes.")
    print("Las aprobadas aparecerán en la web en el próximo `python -m sitegen.build`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
