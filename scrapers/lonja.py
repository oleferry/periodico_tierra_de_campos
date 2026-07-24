"""SCR-018 — Precios de cereal de la Lonja de Valladolid y Palencia.

Por qué esta sección: Tierra de Campos es tierra cerealista, y el precio del
trigo o la cebada es "el mercado bursátil" del que vive media comarca. Ningún
medio de la zona lo publica en limpio y con contexto — es el contenido de más
fidelización posible para el lector agrario (ver docs/ideas-mundo.md, Fase 1).

Fuente: lonjavalladolidpalencia.com. Su robots.txt solo bloquea /wp-admin/.
Publica una página por producto (/productos/trigo/, /productos/cebada/...) y,
mejor todavía, el HTML lleva la SERIE HISTÓRICA completa en el atributo
`data-data` del gráfico: unas 115 sesiones desde 2024. Eso permite no solo dar
el precio de hoy, sino compararlo con la semana pasada y con hace un año, que
es lo que convierte un número suelto en una noticia.

Formato de esa serie:
    [["Fecha","Valladolid","Palencia"], ["2024-05-17",220,218], ...]

Dos trampas del dato, ya contempladas abajo:
  · Un 0 no es "vale cero euros": es que esa semana no hubo cotización de ese
    producto. Se descartan esas filas por producto y plaza, no globalmente.
  · Hay productos ESTACIONALES: el girasol se cotiza en campaña y el resto del
    año su último precio se queda congelado meses. Publicar "el girasol está a
    435 €/t" en julio, con un dato de octubre, sería falso. Por eso cada
    cotización lleva su fecha y `vigente` (ver DIAS_VIGENCIA).

Uso:
    python -m scrapers.lonja --dry-run
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from datetime import date, datetime, timedelta

from scrapers.common import ERR_STRUCTURE, ScraperError, fetch

BASE = "https://lonjavalladolidpalencia.com/productos"

# Productos que interesan aquí: cereal y oleaginosas de secano de la meseta.
# (La lonja también cotiza forrajes —alfalfa, veza, paja—, en otra sección.)
#
# Se guarda el artículo y la terminación del adjetivo con el nombre porque las
# frases se redactan solas ("la cebada está más cara", "los guisantes están más
# caros"): sin esto salía "el cebada está más caro", que en un periódico
# agrario canta muchísimo.
PRODUCTOS = {
    "trigo": {"nombre": "Trigo", "art": "el", "adj": "o", "verbo": "está"},
    "cebada": {"nombre": "Cebada", "art": "la", "adj": "a", "verbo": "está"},
    "avena": {"nombre": "Avena", "art": "la", "adj": "a", "verbo": "está"},
    "centeno": {"nombre": "Centeno", "art": "el", "adj": "o", "verbo": "está"},
    "maiz": {"nombre": "Maíz", "art": "el", "adj": "o", "verbo": "está"},
    "guisantes": {"nombre": "Guisantes", "art": "los", "adj": "os", "verbo": "están"},
    "girasol": {"nombre": "Girasol", "art": "el", "adj": "o", "verbo": "está"},
    "colza": {"nombre": "Colza", "art": "la", "adj": "a", "verbo": "está"},
}

# Una cotización de más de 3 semanas no se presenta como precio "de ahora":
# la lonja sesiona semanalmente, así que ese margen absorbe un par de semanas
# sin sesión (agosto, Navidad) sin llegar a dar por buena una de otra campaña.
DIAS_VIGENCIA = 21

_DATA_RE = re.compile(r'data-data="([^"]+)"')


def _serie(slug: str) -> list[list]:
    """Serie histórica [[fecha, valladolid, palencia], ...] de un producto."""
    html = fetch(f"{BASE}/{slug}/")
    m = _DATA_RE.search(html)
    if not m:
        raise ScraperError(ERR_STRUCTURE, f"Sin atributo data-data en {slug}")
    try:
        datos = json.loads(html_lib.unescape(m.group(1)))
    except ValueError as exc:
        raise ScraperError(ERR_STRUCTURE, f"data-data ilegible en {slug}: {exc}") from exc
    if not datos or datos[0][:1] != ["Fecha"]:
        raise ScraperError(ERR_STRUCTURE, f"Cabecera inesperada en {slug}: {datos[:1]}")
    return datos[1:]


def _sesiones_validas(serie: list[list], columna: int) -> list[tuple[date, float]]:
    """(fecha, precio) de las sesiones con cotización real en esa plaza.
    Un 0 significa 'sin cotización ese día', no un precio de cero euros."""
    out = []
    for fila in serie:
        try:
            precio = float(fila[columna])
            fecha = datetime.strptime(fila[0], "%Y-%m-%d").date()
        except (IndexError, TypeError, ValueError):
            continue
        if precio > 0:
            out.append((fecha, precio))
    out.sort(key=lambda p: p[0])
    return out


def _variacion(actual: float, referencia: float | None) -> dict | None:
    if not referencia:
        return None
    dif = actual - referencia
    return {
        "euros": round(dif, 2),
        "porcentaje": round(dif / referencia * 100, 1),
        "sube": dif > 0,
    }


def _cotizacion_producto(slug: str, hoy: date) -> dict | None:
    """Último precio de un producto en las dos plazas, con su comparativa.
    None si el producto no tiene ninguna cotización utilizable."""
    serie = _serie(slug)
    plazas = {}
    for nombre, columna in (("Valladolid", 1), ("Palencia", 2)):
        sesiones = _sesiones_validas(serie, columna)
        if not sesiones:
            continue
        fecha, precio = sesiones[-1]
        anterior = sesiones[-2][1] if len(sesiones) > 1 else None
        # Referencia de hace un año: la sesión más cercana a 365 días atrás,
        # aceptando un mes de margen (no todas las semanas hay sesión).
        objetivo = fecha - timedelta(days=365)
        candidatas = [p for f, p in sesiones if abs((f - objetivo).days) <= 30]
        plazas[nombre] = {
            "precio": precio,
            "fecha": fecha.isoformat(),
            "vigente": (hoy - fecha).days <= DIAS_VIGENCIA,
            "vs_anterior": _variacion(precio, anterior),
            "vs_hace_un_ano": _variacion(precio, candidatas[len(candidatas) // 2] if candidatas else None),
        }
    if not plazas:
        return None
    return {"slug": slug, **PRODUCTOS[slug], "plazas": plazas}


def cotizaciones(hoy: date | None = None) -> list[dict]:
    """Cotizaciones de todos los productos. El fallo de un producto no tumba
    al resto: se avisa por stderr y se sigue, como en el resto de scrapers."""
    hoy = hoy or date.today()
    out = []
    for slug in PRODUCTOS:
        try:
            cot = _cotizacion_producto(slug, hoy)
        except ScraperError as exc:
            print(f"  aviso: lonja/{slug} falló ({exc.error_type}: {exc})", file=sys.stderr)
            continue
        if cot:
            out.append(cot)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-018 — Precios de la Lonja de Valladolid y Palencia")
    ap.add_argument("--dry-run", action="store_true", help="solo imprime")
    ap.parse_args()

    datos = cotizaciones()
    for c in datos:
        print(f"\n== {c['nombre']} ==")
        for plaza, d in c["plazas"].items():
            estado = "" if d["vigente"] else "  (FUERA DE CAMPAÑA, dato antiguo)"
            linea = f"  {plaza:12} {d['precio']:>7.2f} €/t   {d['fecha']}{estado}"
            if d["vs_anterior"]:
                v = d["vs_anterior"]
                linea += f"   sesión anterior: {'+' if v['sube'] else ''}{v['euros']} €"
            print(linea)
    print(f"\n{len(datos)} productos con cotización.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
