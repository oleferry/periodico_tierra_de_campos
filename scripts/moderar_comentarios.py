"""Moderación AUTÓNOMA del tablón de comentarios de Telegram — a diferencia
de scripts/revisar_fotos.py (revisión humana, uno a uno), aquí decide
sitegen/ia.py:moderar_comentario() sin que nadie mire después. Es una
decisión explícita del usuario del proyecto: "esto tiene que ser autónomo,
yo no quiero intervenir, tú eres el gestor de esto" (2026-07-23).

Por eso el criterio por defecto es conservador (ver _SISTEMA_MODERACION en
ia.py: "ante la duda, rechaza") y aquí, además:
  - si la llamada a la IA falla (red, límite de la API...) el comentario se
    trata como NO aprobado — nunca se publica algo que no se ha podido
    evaluar de verdad;
  - los rechazados se borran sin más (ver almacen_comentarios.rechazar): no
    hay cola de "para revisar más tarde", porque nadie la va a mirar.

Uso:
    python -m scripts.moderar_comentarios
"""

from __future__ import annotations

import io
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from sitegen import almacen_comentarios, ia  # noqa: E402


def main() -> int:
    if not almacen_comentarios.disponible():
        print("Sin credenciales de Supabase (SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY): nada que hacer.")
        return 0
    if not ia.disponible():
        print("Sin ANTHROPIC_API_KEY: no se puede moderar sin IA, no se toca nada pendiente.")
        return 0

    pendientes = almacen_comentarios.listar_pendientes()
    if not pendientes:
        print("Sin comentarios pendientes.")
        return 0

    aprobados = rechazados = fallidos = 0
    for c in pendientes:
        texto = (c.get("texto") or "").strip()
        if not texto:
            almacen_comentarios.rechazar(c["id"])
            rechazados += 1
            continue
        try:
            veredicto = ia.moderar_comentario(texto)
        except Exception as exc:  # red, límite de API, respuesta rara: nunca se publica a ciegas
            print(f"  aviso: fallo evaluando {c['id']} ({exc}); se descarta por precaución", file=sys.stderr)
            almacen_comentarios.rechazar(c["id"])
            fallidos += 1
            continue

        if veredicto.get("aprobar"):
            almacen_comentarios.aprobar(c["id"], c)
            aprobados += 1
            print(f"  ✓ aprobado [{c.get('autor', '?')}]: {texto[:70]}")
        else:
            almacen_comentarios.rechazar(c["id"])
            rechazados += 1
            print(f"  ✗ rechazado ({veredicto.get('motivo', 'sin motivo')}): {texto[:70]}")

    print(f"\n{len(pendientes)} comentarios evaluados: {aprobados} aprobados, "
          f"{rechazados} rechazados, {fallidos} descartados por fallo técnico.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
