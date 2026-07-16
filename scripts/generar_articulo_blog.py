"""Genera un artículo de blog/investigación completo:

1. arma un dossier factual a partir de datos reales ya recogidos;
2. lo redacta con IA siguiendo el sistema de marca v1.2
   (sitegen/ia.py:redactar_investigacion, ver editorial/sistema_marca_v1_2/);
3. genera la imagen de portada con OpenAI (sitegen/imagenes.py) si hay
   OPENAI_API_KEY — si no, el artículo se publica sin imagen;
4. escribe la página en web/blog/<slug>.html (una vez; no se regenera en
   cada `python -m sitegen.build`, es una pieza cara, no un boletín diario);
5. actualiza data/blog/articulos.json para que aparezca en portada;
6. si hay TELEGRAM_BOT_TOKEN y TELEGRAM_CHANNEL_ID, avisa en el canal.

Por ahora solo hay un dossier montado: "despoblacion", a partir de
data/poblacion_negocios.json (generar antes con
`python -m scripts.investigar_despoblacion` si no existe).

Uso:
    python -m scripts.generar_articulo_blog --tema despoblacion
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sitegen import ia, imagenes  # noqa: E402
from sitegen.build import E, render_blog_articulo, shell  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DATA = ROOT / "data"


def _slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def dossier_despoblacion() -> tuple[str, str]:
    """Dossier de población y empresas de los 12 pilotos, desde datos reales
    del INE (scripts/investigar_despoblacion.py). Devuelve (tema, dossier)."""
    path = DATA / "poblacion_negocios.json"
    if not path.exists():
        raise SystemExit(
            "Falta data/poblacion_negocios.json — ejecuta primero:\n"
            "  python -m scripts.investigar_despoblacion"
        )
    datos = json.loads(path.read_text(encoding="utf-8"))

    lineas = [
        "Fuente: INE (Instituto Nacional de Estadística), API pública Tempus.",
        "Población: 'Cifras Oficiales de Población de los Municipios Españoles: "
        "Revisión del Padrón Municipal', serie 1996-2025.",
        "Empresas: 'Explotación Estadística del Directorio Central de Empresas (DIRCE)', "
        "columna Total CNAE, serie 2012-2025.",
        "",
    ]
    for slug, d in datos.items():
        pob = d.get("poblacion", {})
        emp = d.get("empresas", {})
        if not pob and not emp:
            continue
        lineas.append(f"## {d['nombre']} ({d['provincia']})")
        if pob:
            anios = sorted(pob.keys())
            primero, ultimo = anios[0], anios[-1]
            cambio = pob[ultimo] - pob[primero]
            pct = (cambio / pob[primero] * 100) if pob[primero] else 0
            lineas.append(
                f"Población: {int(pob[primero])} habitantes en {primero} → "
                f"{int(pob[ultimo])} en {ultimo} ({pct:+.1f}%)."
            )
            # pico intermedio, si lo hay
            pico_anio = max(anios, key=lambda a: pob[a])
            if pico_anio not in (primero, ultimo):
                lineas.append(f"Máximo de la serie: {int(pob[pico_anio])} en {pico_anio}.")
        if emp:
            anios_e = sorted(emp.keys())
            primero_e, ultimo_e = anios_e[0], anios_e[-1]
            cambio_e = emp[ultimo_e] - emp[primero_e]
            pct_e = (cambio_e / emp[primero_e] * 100) if emp[primero_e] else 0
            lineas.append(
                f"Empresas: {int(emp[primero_e])} en {primero_e} → {int(emp[ultimo_e])} "
                f"en {ultimo_e} ({pct_e:+.1f}%)."
            )
        lineas.append("")

    tema = "la despoblación y el cierre de negocios en Tierra de Campos"
    return tema, "\n".join(lineas)


def dossier_ayudas() -> tuple[str, str]:
    """Dossier del dinero real en ayudas y subvenciones que ha llegado a los 12
    pilotos y a las 4 diputaciones, desde la BDNS (scrapers/bdns.py) — misma
    fuente que ya alimenta las fichas de ayudas de cada pueblo, aquí agregada
    para ver el conjunto en vez de convocatoria por convocatoria."""
    from scrapers.bdns import fetch_ayudas
    from scrapers.common import load_municipios
    from sitegen.build import PILOTS

    municipios = [(m.name, m.slug) for m in load_municipios() if m.slug in PILOTS]
    por_slug = fetch_ayudas(municipios)

    lineas = [
        "Fuente: Base de Datos Nacional de Subvenciones (BDNS), API pública "
        "(pap.hacienda.gob.es/bdnstrans/api). Registro obligatorio por ley "
        "(Ley 38/2003 General de Subvenciones) de toda ayuda pública española.",
        "Alcance: ayudas y convenios de los 12 ayuntamientos piloto, más las de "
        "las 4 diputaciones (Valladolid, Palencia, León, Zamora) que citan "
        "expresamente a uno de estos pueblos en el título.",
        "",
    ]
    total_n = 0
    total_importe = 0.0
    sin_importe = 0
    por_pueblo: dict[str, dict] = {}
    mayores: list[tuple[float, str, str]] = []  # (importe, titulo, entidad)

    for slug, docs in por_slug.items():
        for d in docs:
            total_n += 1
            nombre = d["municipality_name"] if slug != "comarca" else "Diputación (comarca)"
            reg = por_pueblo.setdefault(nombre, {"n": 0, "importe": 0.0})
            reg["n"] += 1
            importe = d.get("presupuesto_total")
            if importe:
                total_importe += importe
                reg["importe"] += importe
                mayores.append((importe, d["title"], nombre))
            else:
                sin_importe += 1

    lineas.append(f"Total de convocatorias encontradas: {total_n}.")
    lineas.append(
        f"Importe total sumado (solo las que publican presupuesto): {total_importe:,.0f} €. "
        f"{sin_importe} convocatorias no indican importe en la BDNS."
    )
    lineas.append("")
    lineas.append("## Desglose por entidad")
    for nombre, reg in sorted(por_pueblo.items(), key=lambda kv: -kv[1]["importe"]):
        lineas.append(f"{nombre}: {reg['n']} convocatoria(s), {reg['importe']:,.0f} € sumados.")
    lineas.append("")
    lineas.append("## Las convocatorias de mayor importe")
    for importe, titulo, nombre in sorted(mayores, key=lambda t: -t[0])[:10]:
        lineas.append(f"{importe:,.0f} € — {titulo} ({nombre}).")

    tema = "cuánto dinero público real llega a Tierra de Campos en ayudas y subvenciones"
    return tema, "\n".join(lineas)


DOSSIERS = {"despoblacion": dossier_despoblacion, "ayudas": dossier_ayudas}


def publicar_telegram(titular: str, entradilla: str, url: str) -> None:
    import os
    import requests

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    canal = os.getenv("TELEGRAM_CHANNEL_ID")
    if not token or token == "replace_me" or not canal or canal == "replace_me":
        print("  (sin TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID reales: no se publica en el canal)")
        return
    texto = f"*{titular}*\n\n{entradilla}\n\n{url}"
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": canal, "text": texto, "parse_mode": "Markdown"},
        timeout=15,
    )
    if r.status_code != 200:
        print(f"  aviso: fallo al publicar en Telegram: {r.text}", file=sys.stderr)
    else:
        print("  publicado en el canal de Telegram.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera un artículo de blog/investigación")
    ap.add_argument("--tema", required=True, choices=sorted(DOSSIERS))
    ap.add_argument("--sin-imagen", action="store_true", help="no generar imagen aunque haya clave de OpenAI")
    args = ap.parse_args()

    print(f"· Montando dossier de '{args.tema}'…")
    tema, dossier = DOSSIERS[args.tema]()
    print(f"  {len(dossier)} caracteres de dossier factual")

    print("· Redactando con IA (puede tardar 1-2 minutos)…")
    art = ia.redactar_investigacion(tema, dossier)
    slug = _slugify(art["titular"])
    print(f"  titular: {art['titular']}")
    print(f"  slug: {slug}")

    tiene_imagen = False
    if not args.sin_imagen and imagenes.disponible():
        print("· Generando imagen de portada (OpenAI)…")
        try:
            img = imagenes.generar_imagen(art["prompt_imagen"])
            (DATA / "blog" / "imagenes").mkdir(parents=True, exist_ok=True)
            (DATA / "blog" / "imagenes" / f"{slug}.jpg").write_bytes(img)
            tiene_imagen = True
        except Exception as exc:  # noqa: BLE001
            print(f"  aviso: fallo generando imagen ({exc}); se publica sin imagen", file=sys.stderr)
    else:
        print("  (sin OPENAI_API_KEY real, o --sin-imagen: se publica sin imagen)")

    print("· Escribiendo página…")
    (WEB / "blog").mkdir(parents=True, exist_ok=True)
    html = render_blog_articulo(slug, art, tema=args.tema, tiene_imagen=tiene_imagen)
    (WEB / "blog" / f"{slug}.html").write_text(html, encoding="utf-8")

    manifest_path = DATA / "blog" / "articulos.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    manifest = [a for a in manifest if a["slug"] != slug]  # regenerar = sustituir
    manifest.insert(0, {
        "slug": slug,
        "titular": art["titular"],
        "entradilla": art["entradilla"],
        "tema": args.tema,
        "fecha": date.today().isoformat(),
        "tiene_imagen": tiene_imagen,
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    url = f"https://elterracampino.es/blog/{slug}.html"
    print(f"\nListo: web/blog/{slug}.html")
    print(f"Telegram (versión corta): {art['version_telegram']}")
    if art["revision_humana"]:
        print("\nPendiente de revisión humana antes de difundir:")
        for punto in art["revision_humana"]:
            print(f"  - {punto}")

    publicar_telegram(art["titular"], art["entradilla"], url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
