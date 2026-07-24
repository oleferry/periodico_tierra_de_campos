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
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# La consola de Windows viene en cp1252 y revienta si la IA usa un carácter
# que no está en esa tabla (guiones largos "−", comillas tipográficas...) —
# el artículo ya se ha escrito bien en disco para entonces, pero el script
# salía con error igualmente. Mismo fix que scripts/desarrollar_pista.py.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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


def dossier_cien_anos() -> tuple[str, str]:
    """Dossier del arco completo de población 1900-2025 de los 12 pilotos,
    combinando el censo histórico decenal (scripts/investigar_despoblacion.py,
    operación 35 del INE) con la serie moderna 1996-2025 (operación 22).
    Devuelve (tema, dossier). Ver docs/ideas-blog.md, idea #20."""
    path = DATA / "poblacion_negocios.json"
    if not path.exists():
        raise SystemExit(
            "Falta data/poblacion_negocios.json — ejecuta primero:\n"
            "  python -m scripts.investigar_despoblacion"
        )
    datos = json.loads(path.read_text(encoding="utf-8"))

    lineas = [
        "Fuente: INE (Instituto Nacional de Estadística), API pública Tempus.",
        "Población histórica: 'Poblaciones de hecho desde 1900 hasta 1991. Cifras "
        "oficiales sacadas de los Censos respectivos', un dato por censo decenal "
        "(1900, 1910, 1920... 1991).",
        "Población moderna: 'Cifras Oficiales de Población de los Municipios "
        "Españoles: Revisión del Padrón Municipal', serie 1996-2025 (casi anual).",
        "Aviso: entre 1991 y 1996 no hay dato (salto de fuente censo→padrón); "
        "el resto del siglo está cubierto.",
        "",
    ]
    for slug, d in datos.items():
        historica = d.get("poblacion_historica", {})
        moderna = d.get("poblacion", {})
        if not historica and not moderna:
            continue
        serie = {**historica, **moderna}  # une los dos tramos en una sola serie
        if not serie:
            continue
        anios = sorted(serie.keys())
        primero, ultimo = anios[0], anios[-1]
        pico_anio = max(anios, key=lambda a: serie[a])
        pico = serie[pico_anio]
        cambio_total = serie[ultimo] - pico
        pct_total = (cambio_total / pico * 100) if pico else 0

        lineas.append(f"## {d['nombre']} ({d['provincia']})")
        lineas.append(
            f"Serie completa {primero}-{ultimo}: {int(serie[primero])} habitantes en {primero}, "
            f"máximo de {int(pico)} en {pico_anio}, {int(serie[ultimo])} en {ultimo} "
            f"({pct_total:+.1f}% desde el máximo)."
        )
        # puntos intermedios legibles: uno por década disponible, para poder citar el detalle
        puntos = ", ".join(f"{a}: {int(serie[a])}" for a in anios)
        lineas.append(f"Serie completa por año: {puntos}.")
        lineas.append("")

    tema = "cien años de despoblación en Tierra de Campos, de 1900 a hoy"
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


def dossier_migraciones() -> tuple[str, str]:
    """Dossier de saldos migratorios frente a cambio real de padrón, 2024.

    Salió investigando una pista del detector de anomalías (Villada rompía 11
    años de caída) y resultó ser un fenómeno comarcal: la migración tapa casi
    exactamente el agujero demográfico. Ver docs/ideas-blog.md, idea #21.

    Aviso metodológico que va DENTRO del dossier, no solo aquí: la diferencia
    entre el saldo migratorio y el cambio de padrón NO es un dato oficial, es
    una resta. El INE no publica nacimientos ni defunciones por municipio en
    pueblos de este tamaño (secreto estadístico), así que esa diferencia se
    explica sobre todo por defunciones menos nacimientos, pero también puede
    incluir ajustes del padrón. La pieza tiene que decirlo así."""
    path = DATA / "migraciones_comarca.json"
    if not path.exists():
        raise SystemExit(
            "Falta data/migraciones_comarca.json — se generó el 2026-07-24 desde el INE "
            "(operación 455, tabla 69767). Ver docs/ideas-blog.md idea #21."
        )
    datos = json.loads(path.read_text(encoding="utf-8"))
    municipios = datos["municipios"]
    # Los nombres bien escritos (con tildes) están en el fichero de población;
    # derivarlos del slug daría "Sahagun" y "Carrion De Los Condes".
    nombres = {}
    pob_path = DATA / "poblacion_negocios.json"
    if pob_path.exists():
        nombres = {k: v["nombre"] for k, v in
                   json.loads(pob_path.read_text(encoding="utf-8")).items()}

    lineas = [
        "TEMA: qué sostiene hoy la población de Tierra de Campos.",
        "",
        "Fuente de los saldos migratorios: INE, Estadística de Migraciones y Cambios "
        "de Residencia (operación 455, tabla 69767: saldos por municipio, año y tipo "
        "de saldo). Año de referencia: 2024.",
        "Fuente del padrón: INE, Cifras Oficiales de Población (revisión del Padrón "
        "Municipal), series 1996-2025.",
        "",
        "AVISO METODOLÓGICO IMPORTANTE, hay que reflejarlo en el texto:",
        "  · El saldo migratorio (cuánta gente llega menos cuánta se va) es dato "
        "oficial del INE, por municipio.",
        "  · El cambio de padrón también es dato oficial.",
        "  · La DIFERENCIA entre ambos NO es un dato publicado: es una resta que "
        "hacemos nosotros. Se explica sobre todo por defunciones menos nacimientos, "
        "pero puede incluir además ajustes y bajas del padrón. El INE no publica "
        "nacimientos ni defunciones por municipio en pueblos de este tamaño, por "
        "secreto estadístico. NO llamarlo 'saldo vegetativo' como si fuera oficial: "
        "decir que es la diferencia que queda y explicar a qué se debe.",
        "",
        "DATOS POR MUNICIPIO (saldo migratorio 2024 y cambio de padrón 2024→2025):",
    ]

    tot_mig = tot_ext = tot_int = tot_pad = 0
    for slug, d in sorted(municipios.items()):
        st = d.get("saldo_total", {}).get("2024")
        se = d.get("saldo_exterior", {}).get("2024")
        si = d.get("saldo_interior", {}).get("2024")
        pob = d.get("poblacion", {})
        if st is None or "2025" not in pob or "2024" not in pob:
            continue
        cambio = pob["2025"] - pob["2024"]
        nombre = nombres.get(slug) or slug.replace("-", " ").title()
        lineas.append(
            f"  {nombre}: saldo migratorio {st:+.0f} (del extranjero {se:+.0f}, "
            f"de otros municipios españoles {si:+.0f}); padrón {pob['2024']:.0f} → "
            f"{pob['2025']:.0f} ({cambio:+.0f}); diferencia por explicar {cambio - st:+.0f}"
        )
        tot_mig += st
        tot_ext += se or 0
        tot_int += si or 0
        tot_pad += cambio

    lineas += [
        "",
        "TOTALES DE LOS 12 PUEBLOS:",
        f"  Saldo migratorio 2024: {tot_mig:+.0f} personas.",
        f"    · De ellas, llegadas del extranjero: {tot_ext:+.0f}.",
        f"    · De otros municipios españoles: {tot_int:+.0f}.",
        f"  Cambio real del padrón 2024→2025: {tot_pad:+.0f} habitantes.",
        f"  Diferencia que se pierde por el camino: {tot_pad - tot_mig:+.0f}.",
        "",
        "LECTURA DE FONDO (el ángulo de la pieza): la migración no está haciendo "
        "crecer la comarca; está tapando su agujero demográfico. Sin esas personas, "
        f"los doce pueblos habrían perdido en torno a {abs(tot_pad - tot_mig):.0f} "
        "habitantes en un solo año.",
        "",
        "CASOS QUE LO ILUSTRAN BIEN:",
        "  · Sahagún ganó 35 personas por migración y aun así perdió 18 habitantes.",
        "  · Carrión de los Condes ganó 31 por migración y perdió 2 habitantes.",
        "  · Medina de Rioseco es el que más recibió: +95, de ellas 90 del extranjero.",
        "  · Villada rompió once años seguidos de caída (+29 habitantes), con un "
        "saldo migratorio de +33 repartido casi a partes iguales entre extranjero "
        "e interior.",
        "  · No todos suben: Mayorga (-27), Villalón de Campos (-11), Becerril (-11) "
        "y Valderas (-6) tuvieron saldo migratorio negativo.",
        "",
        "CÓMO TRATAR ESTO EDITORIALMENTE (innegociable):",
        "  · Las personas que llegan no son un instrumento demográfico ni 'la "
        "solución' a nada: son vecinos. Escribir sobre ellas con el mismo respeto "
        "con el que se escribiría sobre cualquier otro vecino del pueblo.",
        "  · Nada de tono alarmista ni de 'invasión', y tampoco el paternalismo de "
        "presentarlas como salvadoras que vienen a rescatar el pueblo.",
        "  · No se sabe de qué países vienen ni en qué trabajan: el INE no lo "
        "publica a este nivel. NO INVENTARLO NI INSINUARLO. Decir abiertamente que "
        "es lo que falta por averiguar y que exige preguntar en los pueblos.",
        "  · No atribuir intenciones ni causas que no estén en los datos: sabemos "
        "QUÉ pasó, no POR QUÉ.",
    ]
    return "migraciones", "\n".join(lineas)


DOSSIERS = {
    "despoblacion": dossier_despoblacion,
    "ayudas": dossier_ayudas,
    "cien_anos": dossier_cien_anos,
    "migraciones": dossier_migraciones,
}


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
