"""SCR-021 — Paro registrado por municipio (SEPE), agregado a la comarca.

El SEPE publica cada mes un Excel por provincia con el paro registrado de todos
sus municipios. Aquí se cruzan los cuatro que tocan Tierra de Campos y se
agrega la cifra comarcal, comparándola con el mismo mes del año anterior — que
es lo que convierte un número en noticia en una comarca que se vacía.

Fuente: sepe.es (robots.txt solo bloquea páginas sueltas de convocatorias). Las
URLs de los ficheros llevan un UUID que cambia cada mes, así que hay que leer
la página del mes y localizar en ella el enlace de cada provincia; no se pueden
construir a mano.

Dos límites del dato, importantes para no publicar de más:
  · SECRETO ESTADÍSTICO: en los municipios donde hay menos de 5 parados, el
    SEPE escribe "<5" en vez de la cifra. En esta comarca eso afecta a más de
    la mitad de los pueblos (95 de 180 en junio de 2026). Esos municipios NO se
    suman ni se inventan: se cuentan aparte y se dice cuántos son.
  · El paro registrado no es la EPA: mide quien se apunta a la oficina de
    empleo, no todo el desempleo real. Se nombra así siempre, sin llamarlo
    "tasa de paro", que sería otra cosa.

Uso:
    python -m scrapers.paro_sepe --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

import requests
from bs4 import BeautifulSoup

from scrapers.common import (
    ERR_NETWORK,
    ROOT,
    ERR_STRUCTURE,
    REQUEST_TIMEOUT,
    USER_AGENT,
    ScraperError,
    fetch,
    load_municipios,
    strip_accents,
)

BASE = "https://www.sepe.es"
INDICE = f"{BASE}/HomeSepe/que-es-el-sepe/estadisticas/datos-estadisticos/municipios.html"
PAGINA_MES = f"{BASE}/HomeSepe/que-es-el-sepe/estadisticas/datos-estadisticos/municipios/{{anio}}/{{mes}}.html"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Nombre del fichero por provincia dentro de la página del mes.
PROVINCIAS = {"León": "MUNI_LEON", "Palencia": "MUNI_PALENCIA",
              "Valladolid": "MUNI_VALLADOLID", "Zamora": "MUNI_ZAMORA"}

# La capital de Palencia figura en el CSV maestro de la comarca, pero con sus
# ~78.000 habitantes y más de 3.000 parados se comería el dato: sería el 72% del
# total comarcal y taparía por completo lo que pasa en los pueblos, que es de lo
# que va esto. Mismo criterio que scrapers/radar_noticias.py (SLUGS_EXCLUIDOS).
EXCLUIDOS = {"PALENCIA"}


def _municipios_comarca() -> dict[str, str]:
    """{NOMBRE EN MAYÚSCULAS SIN TILDES: nombre real} de los de la comarca.
    El SEPE no da el slug ni un código que compartamos, así que el cruce es por
    nombre normalizado."""
    return {strip_accents(m.name).upper(): m.name
            for m in load_municipios() if strip_accents(m.name).upper() not in EXCLUIDOS}


def _enlaces_del_mes(anio: int, mes: int) -> dict[str, str]:
    """{provincia: url del .xls} de la página de ese mes. Vacío si no existe."""
    try:
        html = fetch(PAGINA_MES.format(anio=anio, mes=MESES[mes - 1]))
    except ScraperError:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, str] = {}
    for a in soup.select("a[href]"):
        href = a["href"]
        if not href.lower().endswith(".xls"):
            continue
        for prov, prefijo in PROVINCIAS.items():
            if prefijo in href.upper():
                out[prov] = href if href.startswith("http") else BASE + href
    return out


_FIRMA_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _arreglar_ole2(datos: bytes) -> bytes:
    """Corrige una cabecera mal escrita en parte de los Excel del SEPE.

    Buena parte de sus ficheros (los de ~92 KB; los de ~111 KB están bien)
    llevan 0xFFFF en el campo "byte order" de la cabecera OLE2, donde el
    formato exige 0xFFFE (little-endian). Excel y LibreOffice lo pasan por
    alto, pero xlrd es estricto y se niega a abrirlos: sin esto, más de la
    mitad de los meses son ilegibles y no habría comparativa interanual.

    El arreglo es deliberadamente quirúrgico: solo se tocan esos dos bytes, y
    solo si la firma OLE2 es correcta y el valor es exactamente el erróneo
    conocido. Cualquier otro fichero se devuelve intacto."""
    if len(datos) < 32 or not datos.startswith(_FIRMA_OLE2):
        return datos
    if datos[28:30] != b"\xff\xff":
        return datos
    return datos[:28] + b"\xfe\xff" + datos[30:]


def _leer_xls(url: str) -> list[tuple[str, object]]:
    """[(municipio, total)] del Excel del SEPE. El total puede ser un número o
    la cadena '<5' cuando el SEPE lo oculta por secreto estadístico."""
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise ScraperError(ERR_STRUCTURE, "Falta la librería xlrd (pip install xlrd)") from exc
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT * 2)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise ScraperError(ERR_NETWORK, f"{type(exc).__name__}: {exc}") from exc
    try:
        hoja = xlrd.open_workbook(file_contents=_arreglar_ole2(r.content)).sheet_by_index(0)
    except Exception as exc:  # noqa: BLE001 — xlrd lanza tipos variados
        raise ScraperError(ERR_STRUCTURE, f"Excel del SEPE ilegible: {exc}") from exc

    filas = []
    for i in range(hoja.nrows):
        fila = hoja.row_values(i)
        if len(fila) < 3:
            continue
        nombre = str(fila[1]).strip()
        # Las filas de datos empiezan con el código INE del municipio.
        if not nombre or not re.match(r"^\d{4,5}(\.0)?$", str(fila[0]).strip()):
            continue
        filas.append((nombre.upper(), fila[2]))
    if not filas:
        raise ScraperError(ERR_STRUCTURE, f"Sin filas de municipio en {url}")
    return filas


def _total_mes(anio: int, mes: int, *, exigir_todas: bool = True) -> dict | None:
    """Agrega el paro de la comarca en ese mes, o None si aún no está publicado.

    `exigir_todas` pide las cuatro provincias para dar el mes por bueno (es lo
    que se quiere para la cifra principal). Para el mes de comparación se pone
    en False: si una provincia no se puede leer se sigue con las demás y luego
    la comparativa se hace solo sobre los municipios comunes a ambos meses."""
    enlaces = _enlaces_del_mes(anio, mes)
    if len(enlaces) < len(PROVINCIAS):
        return None

    comarca = _municipios_comarca()
    total = 0
    municipios: dict[str, int] = {}
    ocultos = 0
    provincias_ok = []
    for prov, url in enlaces.items():
        try:
            filas = _leer_xls(url)
        except ScraperError as exc:
            # Pasa de verdad: el Excel de León de junio de 2025 viene corrupto
            # desde el propio SEPE y xlrd no puede abrirlo.
            print(f"  aviso: paro de {prov} {mes}/{anio} no legible ({exc})", file=sys.stderr)
            if exigir_todas:
                return None
            continue
        provincias_ok.append(prov)
        for nombre, valor in filas:
            if nombre not in comarca:
                continue
            if isinstance(valor, float):
                municipios[comarca[nombre]] = int(valor)
                total += int(valor)
            else:
                ocultos += 1  # "<5": no se suma ni se estima
    if not municipios:
        return None
    return {
        "anio": anio, "mes": mes, "mes_nombre": MESES[mes - 1],
        "total": total, "municipios": municipios,
        "con_dato": len(municipios), "ocultos": ocultos,
        "provincias": provincias_ok,
    }


def paro_comarca(hoy: date | None = None) -> dict | None:
    """Último mes publicado, con la comparativa interanual.

    Se busca hacia atrás desde el mes en curso porque el SEPE publica con unas
    semanas de retraso y no siempre el mismo día."""
    hoy = hoy or date.today()
    anio, mes = hoy.year, hoy.month
    for _ in range(4):  # como mucho, cuatro meses atrás
        actual = _total_mes(anio, mes)
        if actual:
            hace_un_anio = _total_mes(anio - 1, mes, exigir_todas=False)
            if hace_un_anio:
                # Comparar SOLO los municipios con cifra en ambos meses. Si no,
                # se estaría comparando un conjunto con otro distinto (por una
                # provincia ilegible, o por pueblos que un mes tienen "<5" y
                # otro no) y la variación sería mentira.
                comunes = set(actual["municipios"]) & set(hace_un_anio["municipios"])
                if comunes:
                    ahora = sum(actual["municipios"][m] for m in comunes)
                    antes = sum(hace_un_anio["municipios"][m] for m in comunes)
                    dif = ahora - antes
                    actual["vs_hace_un_ano"] = {
                        "total_entonces": antes,
                        "total_ahora_comparable": ahora,
                        "municipios_comparados": len(comunes),
                        "diferencia": dif,
                        "porcentaje": round(dif / antes * 100, 1) if antes else None,
                        "baja": dif < 0,
                    }
            return actual
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return None


CACHE = ROOT / "data" / "paro_comarca.json"


def paro_comarca_cacheado(hoy: date | None = None) -> dict | None:
    """Igual que paro_comarca(), pero sin descargar ocho Excel en cada build.

    El paro es un dato MENSUAL y el sitio se reconstruye a diario, así que se
    guarda el resultado en data/paro_comarca.json y solo se vuelve a bajar
    cuando el SEPE publica un mes nuevo. Para saberlo basta con pedir la página
    del mes siguiente al que tenemos (una petición ligera) en vez de los ocho
    ficheros. Como efecto secundario útil, si el SEPE está caído el sitio sigue
    mostrando el último dato bueno en lugar de quedarse sin sección."""
    hoy = hoy or date.today()
    guardado = None
    if CACHE.exists():
        try:
            guardado = json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            guardado = None

    if guardado:
        anio, mes = guardado["anio"], guardado["mes"]
        siguiente = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        # Si el mes siguiente aún no está publicado, lo que tenemos es lo último.
        if not _enlaces_del_mes(*siguiente):
            return guardado

    nuevo = paro_comarca(hoy)
    if nuevo:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(nuevo, ensure_ascii=False, indent=2), encoding="utf-8")
        return nuevo
    return guardado


def main() -> int:
    # La consola de Windows viene en cp1252 y revienta al imprimir tildes o
    # flechas; el scraper en sí no depende de esto, solo su salida por pantalla.
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="SCR-021 — Paro registrado en Tierra de Campos (SEPE)")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime")
    ap.parse_args()

    d = paro_comarca()
    if not d:
        print("No se pudo obtener el paro registrado de la comarca.")
        return 1
    print(f"Paro registrado en Tierra de Campos — {d['mes_nombre']} de {d['anio']}")
    print(f"  Total: {d['total']} personas en {d['con_dato']} municipios")
    print(f"  ({d['ocultos']} municipios sin cifra pública: menos de 5 parados)")
    v = d.get("vs_hace_un_ano")
    if v:
        print(f"  Frente a hace un año: {v['diferencia']:+} ({v['porcentaje']:+}%), "
              f"comparando los {v['municipios_comparados']} municipios con cifra en ambos meses "
              f"({v['total_entonces']} → {v['total_ahora_comparable']})")
    top = sorted(d["municipios"].items(), key=lambda kv: -kv[1])[:8]
    print("\n  Municipios con más paro registrado:")
    for nombre, n in top:
        print(f"    {nombre:26} {n:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
