"""SCR-010 (variante MVP) — Tiempo por municipio vía Open-Meteo.

Open-Meteo es gratis y sin API key, con datos reales por coordenadas. Se usa como
fuente del MVP mientras no esté la clave de AEMET (fuente oficial, futura).

Genera, además de los datos, un texto "en modo artículo" (tiempo humano) de forma
determinista y basada en reglas — no inventa nada, solo redacta los números reales.
No es asesoramiento: es orientación, en la línea de prompts/05_tiempo_humano.md.
"""

from __future__ import annotations

from datetime import date

import requests

from scrapers.common import ERR_NETWORK, REQUEST_TIMEOUT, USER_AGENT, ScraperError

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Códigos WMO → (descripción corta, ¿es lluvia/nieve/tormenta?)
WMO = {
    0: "despejado", 1: "casi despejado", 2: "nubes y claros", 3: "nublado",
    45: "niebla", 48: "niebla helada",
    51: "llovizna débil", 53: "llovizna", 55: "llovizna intensa",
    61: "lluvia débil", 63: "lluvia", 65: "lluvia fuerte",
    66: "lluvia helada", 67: "lluvia helada fuerte",
    71: "nieve débil", 73: "nieve", 75: "nieve intensa",
    77: "aguanieve", 80: "chubascos", 81: "chubascos", 82: "chubascos fuertes",
    85: "chubascos de nieve", 86: "chubascos de nieve",
    95: "tormenta", 96: "tormenta con granizo", 99: "tormenta fuerte con granizo",
}

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _get(url: str, params: dict) -> dict:
    try:
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ScraperError(ERR_NETWORK, f"{type(exc).__name__}: {exc}") from exc
    if r.status_code >= 400:
        raise ScraperError(ERR_NETWORK, f"HTTP {r.status_code} en {url}")
    return r.json()


def geocode(name: str) -> tuple[float, float] | None:
    """Devuelve (lat, lon) del municipio, o None. Para municipios sin coords en el CSV."""
    data = _get(GEOCODE_URL, {"name": name, "count": 5, "language": "es", "country": "ES"})
    for res in data.get("results", []):
        if res.get("country_code") == "ES":
            return round(res["latitude"], 6), round(res["longitude"], 6)
    return None


def fetch_forecast(lat: float, lon: float) -> dict:
    data = _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max,weather_code",
        "timezone": "Europe/Madrid", "forecast_days": 4,
    })
    if "current" not in data or "daily" not in data:
        raise ScraperError(ERR_NETWORK, "Respuesta de Open-Meteo sin 'current'/'daily'")
    return data


def _viento(kmh: float) -> str:
    if kmh < 12:
        return "viento flojo"
    if kmh < 25:
        return "viento moderado"
    if kmh < 40:
        return "viento fuerte"
    return "viento muy fuerte"


def _titular_dia(dia_nombre: str, d: dict, prev_max: int | None) -> str:
    """Titular corto con gancho para un día, al estilo 'El tiempo de Javimo'
    ('Finde en seco', 'Puente pasado por agua'): describe el rasgo del día, no el pueblo."""
    nombre = dia_nombre.capitalize()
    if d["prob_lluvia"] >= 50 and d["mm"] >= 1:
        return f"{nombre} pasado por agua"
    if d["prob_lluvia"] >= 40:
        return f"{nombre} con opciones de lluvia"
    if "tormenta" in d["desc"]:
        return f"{nombre} con riesgo de tormenta"
    if prev_max is not None and d["max"] - prev_max >= 4:
        return f"{nombre}, sube el calor"
    if prev_max is not None and prev_max - d["max"] >= 4:
        return f"{nombre}, refresca"
    if d["desc"] in ("despejado", "casi despejado"):
        return f"{nombre} de sol"
    return f"{nombre}, tiempo tranquilo"


def _texto_dia(d: dict) -> str:
    frases = [f"Máxima de {d['max']}° y mínima de {d['min']}°, con {d['desc']}."]
    if d["mm"] and d["mm"] >= 1.0 and d["prob_lluvia"] >= 40:
        frases.append(f"Puede llover (hasta {d['mm']} mm), con un {d['prob_lluvia']}% de probabilidad.")
    elif d["prob_lluvia"] and d["prob_lluvia"] >= 40:
        frases.append(f"Hay un {d['prob_lluvia']}% de probabilidad de lluvia, aunque poca cosa.")
    if d["viento_kmh"] >= 25:
        frases.append(f"Sopla {_viento(d['viento_kmh'])}.")
    return " ".join(frases)


def build_article(municipio: str, fc: dict) -> dict:
    """Redacta el parte del tiempo desde los datos reales. Determinista, sin invenciones."""
    cur = fc["current"]
    d = fc["daily"]
    code = cur["weather_code"]
    desc = WMO.get(code, "tiempo variable")
    t_now = round(cur["temperature_2m"])
    tmax = round(d["temperature_2m_max"][0])
    tmin = round(d["temperature_2m_min"][0])
    viento = _viento(cur["wind_speed_10m"])
    prob = d["precipitation_probability_max"][0]
    mm = d["precipitation_sum"][0]

    frases = [f"Ahora mismo en {municipio}, {desc} y {t_now} grados."]
    frases.append(f"Hoy la máxima ronda los {tmax} y la mínima baja hasta {tmin}.")

    if mm and mm >= 1.0 and prob >= 40:
        frases.append(f"Se espera lluvia (hasta {mm} mm), con un {prob}% de probabilidad.")
    elif prob and prob >= 40:
        frases.append(f"Hay un {prob}% de probabilidad de lluvia, aunque de poca cantidad.")
    else:
        frases.append("No se espera lluvia.")

    frases.append(f"Sopla {viento}.")

    # Aviso propio de la meseta, solo si el dato lo justifica (no se generaliza a la comarca).
    if tmax >= 34:
        frases.append("Con este calor, riega la huerta a primera hora o al anochecer, nunca al mediodía.")
    elif tmin <= 1:
        frases.append("Riesgo de helada de madrugada: protege los semilleros y las plantas delicadas.")

    # Mañana
    dmax = round(d["temperature_2m_max"][1])
    dcode = d["weather_code"][1]
    frases.append(f"Mañana, {WMO.get(dcode, 'tiempo variable')} y hasta {dmax} grados.")

    dias = []
    prev_max = None
    for i, iso in enumerate(d["time"]):
        y, mo, dd = (int(x) for x in iso.split("-"))
        dia_nombre = DIAS[date(y, mo, dd).weekday()]
        item = {
            "fecha": iso,
            "dia": dia_nombre,
            "max": round(d["temperature_2m_max"][i]),
            "min": round(d["temperature_2m_min"][i]),
            "desc": WMO.get(d["weather_code"][i], "tiempo variable"),
            "prob_lluvia": d["precipitation_probability_max"][i],
            "mm": d["precipitation_sum"][i],
            "viento_kmh": round(d["wind_speed_10m_max"][i]),
        }
        item["titular"] = _titular_dia(dia_nombre, item, prev_max)
        item["texto"] = _texto_dia(item)
        prev_max = item["max"]
        dias.append(item)

    return {
        "municipio": municipio,
        "ahora": {"temp": t_now, "desc": desc, "code": code},
        "hoy": {"max": tmax, "min": tmin, "prob_lluvia": prob, "mm": mm, "viento_kmh": round(cur["wind_speed_10m"])},
        "manana": {"max": dmax, "desc": WMO.get(dcode, "tiempo variable")},
        "dias": dias,
        "articulo": " ".join(frases),
        "fuente": "Open-Meteo",
    }


def weather_for(name: str, lat: float, lon: float) -> dict:
    return build_article(name, fetch_forecast(lat, lon))
