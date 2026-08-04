"""Vuelve a envolver los reportajes ya publicados con la plantilla ACTUAL.

Por qué hace falta: `python -m sitegen.build` NO regenera web/blog/*.html. Cada
reportaje se escribe una sola vez (scripts/generar_articulo_blog.py) porque es
una pieza cara, y desde entonces se queda con la cabecera y el pie que había el
día que se creó. Resultado detectado en la revisión de usabilidad del
2026-08-04: los reportajes enseñaban un menú de 4 secciones (frente a las 10 del
resto del sitio) y un pie con un solo enlace — y son justo la puerta de entrada
de quien llega desde redes.

Este script conserva el CUERPO tal cual (no toca ni una palabra del texto
publicado: no pasa por la IA) y solo cambia el envoltorio: cabecera, pie y el
bloque de compartir.

Uso:
    python -m scripts.refrescar_blog --dry-run
    python -m scripts.refrescar_blog
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sitegen.build import bloque_compartir, shell  # noqa: E402

BLOG = ROOT / "web" / "blog"
BASE = "https://elterracampino.es"


def cuerpo_de(html: str) -> str | None:
    """El <article> completo, que es lo publicado. Todo lo demás es envoltorio."""
    m = re.search(r"<article\b.*?</article>", html, re.S)
    return m.group(0) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresca el envoltorio de los reportajes")
    ap.add_argument("--dry-run", action="store_true", help="dice qué cambiaría, sin escribir")
    args = ap.parse_args()

    manifest = json.loads((ROOT / "data" / "blog" / "articulos.json").read_text(encoding="utf-8"))
    por_slug = {a["slug"]: a for a in manifest}

    tocados = 0
    for f in sorted(BLOG.glob("*.html")):
        slug = f.stem
        art = por_slug.get(slug)
        if not art:
            print(f"  aviso: {slug} no está en articulos.json; lo dejo como está", file=sys.stderr)
            continue

        html = f.read_text(encoding="utf-8")
        cuerpo = cuerpo_de(html)
        if not cuerpo:
            print(f"  aviso: no encuentro el <article> en {slug}; lo dejo como está", file=sys.stderr)
            continue

        # Bloque de compartir, justo antes del "volver a portada".
        if "tc-compartir" not in cuerpo:
            compartir = bloque_compartir(f"{BASE}/blog/{slug}.html", art["titular"])
            volver = '<p class="tc-item-meta"><a href="../index.html">'
            if volver in cuerpo:
                cuerpo = cuerpo.replace(volver, compartir + "\n  " + volver, 1)
            else:
                cuerpo = cuerpo.replace("</div></article>", compartir + "\n</div></article>", 1)

        nuevo = shell(f"{art['titular']} — El Terracampino", cuerpo, depth=1,
                      desc=art["entradilla"][:150])
        if nuevo == html:
            print(f"  = {slug} (ya estaba al día)")
            continue

        tocados += 1
        if args.dry_run:
            print(f"  ~ {slug}: se actualizaría el envoltorio")
        else:
            f.write_text(nuevo, encoding="utf-8")
            print(f"  ✓ {slug}")

    print(f"\n{tocados} reportaje(s) {'se actualizarían' if args.dry_run else 'actualizados'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
