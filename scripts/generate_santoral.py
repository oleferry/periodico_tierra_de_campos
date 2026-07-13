"""Genera data/santoral.json: un santo por día del año.

Fuente: Wikipedia en español, "Anexo:Santoral católico"
(https://es.wikipedia.org/wiki/Anexo:Santoral_cat%C3%B3lico), contenido bajo
licencia CC BY-SA 4.0. El santoral en sí (qué santo corresponde a qué día) es
información de referencia pública (Calendarium Romanum Generale); lo que
tomamos de Wikipedia es solo la lista ya ordenada por día, para no tener que
teclear 365 fechas a mano. Se guarda el nombre del PRIMER santo mencionado
en la entrada de cada día (normalmente el de mayor rango litúrgico).

Esto es un generador de UNA VEZ (dato evergreen, no cambia año a año salvo
el santoral se revise oficialmente). Re-ejecutar solo si hace falta refrescar:

    python -m scripts.generate_santoral

No se llama en cada build — data/santoral.json se commitea y sitegen lo lee
como fichero estático, igual que data/municipios_tierra_de_campos.csv.
"""

from __future__ import annotations

import calendar
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
URL = "https://es.wikipedia.org/wiki/Anexo:Santoral_cat%C3%B3lico"
USER_AGENT = "ElTerracampinoBot/0.1 (+https://elterracampino.es)"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MESES_LIST = list(MESES.keys())

# Wikipedia no fija un santo propio para el 29 de febrero (día extra del año
# bisiesto) y el parser automático falla en el 29 de diciembre por un
# formato de lista distinto ahí; se completan a mano tras comprobar la fuente.
PARCHES = {
    (12, 29): "Santo Tomás Becket",
}
SIN_SANTO_FIJO = {(2, 29)}


def _saint_name(ul_text: str) -> str | None:
    m = re.search(r"(San(?:t[oa]s?)? [A-ZÁÉÍÓÚÑ][^.(*,]+)", ul_text)
    return m.group(1).strip() if m else None


def parse_santoral(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    result: dict[tuple[int, int], str] = {}

    for mes_id, mes_num in MESES.items():
        h2 = soup.find("h2", id=mes_id.capitalize())
        if not h2:
            continue
        h2_next = (soup.find("h2", id=MESES_LIST[mes_num % 12].capitalize())
                   if mes_num < 12 else soup.find("h2", id="Véase también"))
        start = h2.find_parent("div")
        end = h2_next.find_parent("div") if h2_next else None

        cur = start.find_next_sibling()
        pending_day = None
        while cur and cur is not end:
            if cur.name == "p":
                m = re.match(rf"^(\d{{1,2}}) de {mes_id}$", cur.get_text(" ", strip=True))
                if m:
                    pending_day = int(m.group(1))
            elif cur.name == "ul" and pending_day:
                nombre = _saint_name(cur.get_text(" ", strip=True))
                if nombre and (mes_num, pending_day) not in result:
                    result[(mes_num, pending_day)] = nombre
                    pending_day = None
            cur = cur.find_next_sibling()

    result.update(PARCHES)

    out: dict[str, str] = {}
    for mes_num in range(1, 13):
        dias_mes = calendar.monthrange(2024, mes_num)[1]  # 2024 = año bisiesto, cubre el 29-feb
        for d in range(1, dias_mes + 1):
            key = f"{mes_num:02d}-{d:02d}"
            if (mes_num, d) in SIN_SANTO_FIJO:
                continue
            nombre = result.get((mes_num, d))
            if not nombre:
                raise SystemExit(f"Falta santo para {key}: revisar el parser o añadir a PARCHES")
            out[key] = nombre
    return out


def main() -> int:
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=25)
    resp.raise_for_status()
    santoral = parse_santoral(resp.text)

    dest = ROOT / "data" / "santoral.json"
    dest.write_text(
        json.dumps(santoral, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Escritos {len(santoral)} días en {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
