"""Rehace la portada (web/index.html + web/datos/pueblos.json) en local, en un
segundo, a partir del volcado de un build de prueba: sin scrapers, sin IA y sin
esperar 30 minutos. Sirve para iterar el diseño de la portada con datos reales.

1. Lanza un build en una rama (no en main: en main no hay volcado y además
   salen el boletín y las pistas):
       gh workflow run build-diario.yml --ref <rama>
2. Descarga el volcado:
       gh run download <id> -n volcado-portada -D data/
3. Rehaz la portada y mírala con el servidor local (node scripts/serve.mjs):
       python -m scripts.previsualizar_portada

Ojo: escribe en web/index.html, que es un fichero generado. Antes de commitear,
`git checkout web/index.html web/datos/` si no quieres subir la versión local.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

from sitegen import build

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Rehace la portada desde un volcado")
    ap.add_argument("--volcado", default=str(ROOT / "data" / "volcado_portada.pkl"))
    args = ap.parse_args()

    ruta = Path(args.volcado)
    if not ruta.exists():
        print(f"No existe {ruta}. Descárgalo de un build de prueba (ver el docstring).", file=sys.stderr)
        return 1
    with open(ruta, "rb") as f:
        v = pickle.load(f)

    # La portada lee del disco y de Supabase lo que no viene por parámetro: se
    # sirve lo volcado, para que salga igual que en el build.
    build.cargar_blog_articulos = lambda: v["blog"]
    build.cargar_comentarios_aprobados = lambda limite=12: v["comentarios"][:limite]

    html = build.render_home(v["built"], v["pool"], v["hoy"], v["avisos"], v["cots"], v["paro"])
    (build.WEB / "index.html").write_text(html, encoding="utf-8")
    (build.WEB / "datos").mkdir(parents=True, exist_ok=True)
    (build.WEB / "datos" / "pueblos.json").write_text(
        json.dumps(build.datos_pueblos(v["built"], v["pool"], v["hoy"]), ensure_ascii=False,
                   separators=(",", ":")), encoding="utf-8")
    print(f"Portada rehecha con los datos del {v['hoy']}: web/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
