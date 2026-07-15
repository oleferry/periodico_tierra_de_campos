"""Revisión manual de las fotos que llegan por el bot de Telegram, antes de
publicarlas — mismo principio que el tablón de negocios: nada se publica
sin que alguien lo mire primero. Mueve entradas de data/fotos/pendientes.json
a data/fotos/aprobadas.json (o las descarta) una a una.

Abre cada foto procesada con el visor de imágenes por defecto del sistema
para que puedas verla antes de decidir.

Uso:
    python -m scripts.revisar_fotos
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOTOS_DIR = ROOT / "data" / "fotos"
PENDIENTES = FOTOS_DIR / "pendientes.json"
APROBADAS = FOTOS_DIR / "aprobadas.json"


def _cargar(path: Path) -> list | dict:
    if not path.exists():
        return [] if path is PENDIENTES else {}
    return json.loads(path.read_text(encoding="utf-8"))


def _guardar(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    pendientes = _cargar(PENDIENTES)
    if not pendientes:
        print("No hay fotos pendientes de revisión.")
        return 0

    aprobadas = _cargar(APROBADAS)
    restantes = []

    for foto in pendientes:
        print(f"\n{'=' * 60}")
        print(f"Pueblo: {foto['pueblo_nombre']}")
        print(f"Pie de foto propuesto: {foto['pie']}")
        if foto.get("texto_remitente"):
            print(f"Texto del remitente: {foto['texto_remitente']}")
        print(f"De: {foto.get('remitente_telegram', '?')} · {foto['fecha']}")
        ruta = FOTOS_DIR / "procesadas" / foto["archivo"]
        _abrir_imagen(ruta)

        resp = input("¿Aprobar? [s/N/e=editar pie/q=salir] ").strip().lower()
        if resp == "q":
            restantes.append(foto)
            continue
        if resp == "e":
            nuevo_pie = input(f"Nuevo pie de foto (enter para dejar '{foto['pie']}'): ").strip()
            if nuevo_pie:
                foto["pie"] = nuevo_pie
            resp = input("¿Aprobar con este pie? [s/N] ").strip().lower()

        if resp == "s":
            aprobadas.setdefault(foto["pueblo_slug"], []).append({
                "id": foto["id"], "archivo": foto["archivo"], "pie": foto["pie"], "fecha": foto["fecha"],
            })
            print("  → aprobada.")
        else:
            (FOTOS_DIR / "procesadas" / foto["archivo"]).unlink(missing_ok=True)
            print("  → descartada.")

    _guardar(PENDIENTES, restantes)
    _guardar(APROBADAS, aprobadas)
    print(f"\nListo. {len(restantes)} siguen pendientes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
