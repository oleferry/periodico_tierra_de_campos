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
        "timezone": "Europe/Madrid", "forecast_days": 3,
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
    for i, iso in enumerate(d["time"]):
        y, mo, dd = (int(x) for x in iso.split("-"))
        dias.append({
            "fecha": iso,
            "dia": DIAS[date(y, mo, dd).weekday()],
            "max": round(d["temperature_2m_max"][i]),
            "min": round(d["temperature_2m_min"][i]),
            "desc": WMO.get(d["weather_code"][i], "tiempo variable"),
        })

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
