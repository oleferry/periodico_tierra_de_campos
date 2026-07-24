"""Olfato estadístico: busca en las series municipales lo que MERECE UNA MIRADA.

Inspirado en Newsworthy.se (ver docs/ideas-mundo.md): su idea no es generar
piezas automáticas, sino avisar de que "este dato de tu municipio es raro".
Eso es justo lo que le falta a un medio de una sola persona: nadie puede
revisar a mano 12 series de 29 años cada mes buscando lo que ha cambiado.

Qué NO hace esto, a propósito:
  · No publica nada. Devuelve pistas para que un humano decida si hay pieza,
    igual que scrapers/radar_noticias.py con las noticias ajenas.
  · No redacta la noticia. El texto que genera es una frase de aviso interna;
    si la pista prospera, la pieza se escribe aparte con su contexto.
  · No afirma causas. Detecta QUE algo cambió, nunca POR QUÉ.

Cuatro tipos de anomalía, elegidos por su valor periodístico real:
  · record        — el valor más alto o más bajo de toda la serie.
  · umbral        — cruzar una cifra redonda que la gente nota (1.000, 500…).
  · cambio_brusco — variación muy fuera de lo normal PARA ESE municipio.
  · contracorriente — va al revés que la comarca. Suele ser la mejor historia:
    "X gana vecinos mientras la comarca pierde" es una pieza; "la comarca
    pierde vecinos" ya no es noticia, es el paisaje.

Cuidado con el ruido: en un pueblo de 200 habitantes, cinco personas son un
2,5%. Por eso un cambio brusco exige a la vez ser estadísticamente raro y
tener tamaño suficiente en términos absolutos (ver MIN_ABSOLUTO).

Uso:
    python -m scripts.detectar_anomalias
    python -m scripts.detectar_anomalias --serie poblacion
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from scrapers.common import ROOT  # noqa: E402

DATOS = ROOT / "data" / "poblacion_negocios.json"

SERIES = {
    "poblacion": {"etiqueta": "habitantes", "singular": "habitante"},
    "empresas": {"etiqueta": "empresas", "singular": "empresa"},
}

# Cifras redondas cuyo cruce la gente del pueblo nota y comenta.
UMBRALES = {
    "poblacion": [5000, 2000, 1000, 500, 300, 200, 100, 50],
    "empresas": [100, 50, 25, 10],
}

# Un cambio tiene que ser raro (z) Y grande de verdad (absoluto y relativo):
# con solo el z-score, en pueblos pequeños salta cualquier cosa.
Z_MINIMO = 2.0
MIN_ABSOLUTO = {"poblacion": 8, "empresas": 3}
MIN_RELATIVO = 2.5  # %


def _serie_ordenada(bruto: dict) -> list[tuple[int, float]]:
    out = []
    for anio, valor in bruto.items():
        try:
            out.append((int(anio), float(valor)))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def _anios_seguidos_en_minimo(serie: list[tuple[int, float]]) -> int:
    """Cuántos años lleva la serie marcando mínimo histórico año tras año."""
    seguidos = 0
    for i in range(len(serie) - 1, 0, -1):
        if serie[i][1] < min(v for _, v in serie[:i]):
            seguidos += 1
        else:
            break
    return seguidos


def _record(nombre: str, serie: list[tuple[int, float]], clave: str) -> dict | None:
    """Máximo o mínimo de toda la serie, si toca justo en el último año."""
    if len(serie) < 10:
        return None
    anio, valor = serie[-1]
    valores = [v for _, v in serie]
    etiqueta = SERIES[clave]["etiqueta"]
    if valor == min(valores) and valores.count(valor) == 1:
        # En una comarca que se vacía, "otro mínimo histórico" es lo esperable:
        # si lleva años encadenándolos, es el paisaje de fondo y no una noticia.
        # Se sigue registrando, pero con relevancia baja para que no tape lo
        # que de verdad rompe la tendencia.
        seguidos = _anios_seguidos_en_minimo(serie)
        rutinario = seguidos >= 3
        matiz = (f" Es el {seguidos}º año seguido marcando mínimo, así que confirma la tendencia "
                 f"más que romperla.") if rutinario else ""
        return {
            "tipo": "record", "municipio": nombre, "serie": clave, "anio": anio,
            "valor": valor, "relevancia": 4 if rutinario else 9,
            "texto": (f"{nombre}: {valor:.0f} {etiqueta} en {anio}, el mínimo de toda la serie "
                      f"({serie[0][0]}-{anio}).{matiz}"),
        }
    if valor == max(valores) and valores.count(valor) == 1:
        return {
            "tipo": "record", "municipio": nombre, "serie": clave, "anio": anio,
            "valor": valor, "relevancia": 8,
            "texto": (f"{nombre}: {valor:.0f} {etiqueta} en {anio}, el máximo de toda la serie "
                      f"({serie[0][0]}-{anio})."),
        }
    return None


def _umbral(nombre: str, serie: list[tuple[int, float]], clave: str) -> dict | None:
    """Cruce de una cifra redonda entre los dos últimos años con dato."""
    if len(serie) < 2:
        return None
    (_, antes), (anio, ahora) = serie[-2], serie[-1]
    etiqueta = SERIES[clave]["etiqueta"]
    for u in UMBRALES[clave]:
        if antes >= u > ahora:
            return {
                "tipo": "umbral", "municipio": nombre, "serie": clave, "anio": anio,
                "valor": ahora, "relevancia": 8,
                "texto": (f"{nombre} baja de {u} {etiqueta} en {anio}: {antes:.0f} → {ahora:.0f}."),
            }
        if antes < u <= ahora:
            return {
                "tipo": "umbral", "municipio": nombre, "serie": clave, "anio": anio,
                "valor": ahora, "relevancia": 7,
                "texto": (f"{nombre} supera los {u} {etiqueta} en {anio}: {antes:.0f} → {ahora:.0f}."),
            }
    return None


def _cambio_brusco(nombre: str, serie: list[tuple[int, float]], clave: str) -> dict | None:
    """Variación del último año muy fuera de lo habitual en ese municipio."""
    if len(serie) < 8:
        return None
    variaciones = [serie[i][1] - serie[i - 1][1] for i in range(1, len(serie))]
    ultima = variaciones[-1]
    previas = variaciones[:-1]
    if len(previas) < 5:
        return None
    desviacion = statistics.pstdev(previas)
    if desviacion == 0:
        return None
    z = abs(ultima - statistics.mean(previas)) / desviacion
    anterior = serie[-2][1]
    relativo = abs(ultima) / anterior * 100 if anterior else 0
    if (z < Z_MINIMO or abs(ultima) < MIN_ABSOLUTO[clave] or relativo < MIN_RELATIVO):
        return None
    anio = serie[-1][0]
    etiqueta = SERIES[clave]["etiqueta"]
    verbo = "gana" if ultima > 0 else "pierde"
    return {
        "tipo": "cambio_brusco", "municipio": nombre, "serie": clave, "anio": anio,
        "valor": serie[-1][1], "relevancia": 7 if ultima > 0 else 6,
        "texto": (f"{nombre} {verbo} {abs(ultima):.0f} {etiqueta} en {anio} "
                  f"({relativo:.1f}%".replace(".", ",") + f"), un salto inusual para este "
                  f"municipio (z={z:.1f} frente a su propia historia)."),
    }


def _contracorriente(datos: dict, clave: str) -> list[dict]:
    """Municipios que el último año fueron en dirección contraria a la comarca.

    Es la anomalía con más valor periodístico: que la comarca pierda población
    no es noticia, es el paisaje de fondo; que UN pueblo la gane, sí."""
    variaciones: dict[str, float] = {}
    ultimo_anio = None
    for slug, m in datos.items():
        serie = _serie_ordenada(m.get(clave) or {})
        if len(serie) < 2:
            continue
        variaciones[m["nombre"]] = serie[-1][1] - serie[-2][1]
        ultimo_anio = serie[-1][0]
    if len(variaciones) < 5:
        return []
    total = sum(variaciones.values())
    if total == 0:
        return []
    direccion_comarca = 1 if total > 0 else -1
    etiqueta = SERIES[clave]["etiqueta"]
    palabra = "gana" if direccion_comarca < 0 else "pierde"

    discrepantes = {n: v for n, v in variaciones.items()
                    if v != 0 and (1 if v > 0 else -1) != direccion_comarca}
    # Si media comarca va "a la contra", ir a la contra no es ninguna anomalía:
    # significa que el signo del total lo marcan uno o dos pueblos grandes, no
    # una tendencia común. Solo interesa cuando es de verdad una excepción.
    if len(discrepantes) > len(variaciones) / 3:
        return []

    a_favor = len(variaciones) - len(discrepantes)
    out = []
    for nombre, var in discrepantes.items():
        if abs(var) < MIN_ABSOLUTO[clave]:
            continue
        out.append({
            "tipo": "contracorriente", "municipio": nombre, "serie": clave,
            "anio": ultimo_anio, "valor": var, "relevancia": 9,
            "texto": (f"{nombre} {palabra} {abs(var):.0f} {etiqueta} en {ultimo_anio}, "
                      f"a contracorriente: de los {len(variaciones)} pueblos con serie, "
                      f"{a_favor} fueron en sentido contrario ({total:+.0f} en total)."),
        })
    return out


def detectar(series: list[str] | None = None) -> list[dict]:
    """Todas las pistas encontradas, de más a menos relevante."""
    if not DATOS.exists():
        raise SystemExit(f"Falta {DATOS}. Genéralo con scripts/investigar_despoblacion.py")
    datos = json.loads(DATOS.read_text(encoding="utf-8"))
    claves = series or list(SERIES)

    pistas: list[dict] = []
    for clave in claves:
        if clave not in SERIES:
            continue
        for m in datos.values():
            serie = _serie_ordenada(m.get(clave) or {})
            if not serie:
                continue
            for deteccion in (_record, _umbral, _cambio_brusco):
                pista = deteccion(m["nombre"], serie, clave)
                if pista:
                    pistas.append(pista)
        pistas.extend(_contracorriente(datos, clave))

    pistas.sort(key=lambda p: (-p["relevancia"], p["municipio"]))
    return pistas


def main() -> int:
    ap = argparse.ArgumentParser(description="Detector de anomalías en las series municipales")
    ap.add_argument("--serie", choices=list(SERIES), help="analiza solo una serie")
    args = ap.parse_args()

    pistas = detectar([args.serie] if args.serie else None)
    if not pistas:
        print("Sin anomalías destacables en las series analizadas.")
        return 0

    por_tipo: dict[str, list[dict]] = {}
    for p in pistas:
        por_tipo.setdefault(p["tipo"], []).append(p)

    for tipo, grupo in por_tipo.items():
        print(f"\n== {tipo.replace('_', ' ').upper()} ({len(grupo)}) ==")
        for p in grupo:
            print(f"  [{p['relevancia']}] {p['texto']}")

    print(f"\n{len(pistas)} pista(s). Ninguna se publica sola: son avisos para mirar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
