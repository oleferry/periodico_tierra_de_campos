"""Utilidades compartidas por los scrapers de El Terracampino.

Reglas del proyecto (scrapers/README_SCRAPERS.md):
  · respetar robots.txt        · User-Agent identificable
  · limitar frecuencia         · hash SHA-256 del contenido
  · registrar errores en scrape_runs
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

USER_AGENT = os.getenv("SCRAPER_USER_AGENT", "ElTerracampinoBot/0.1 (+https://elterracampino.es)")
REQUEST_TIMEOUT = 25
REQUEST_PAUSE = 1.0  # segundos entre peticiones al mismo dominio

# Tipos de error del contrato (README_SCRAPERS §4)
ERR_NETWORK = "network_error"
ERR_PARSE = "parse_error"
ERR_BLOCKED = "blocked"
ERR_STRUCTURE = "unexpected_structure"
ERR_EMPTY = "empty_text"


class ScraperError(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


# ---------------------------------------------------------------- texto

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slugify(name: str) -> str:
    s = strip_accents(name).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def normalize_for_match(s: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(s).upper()).strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- HTTP

_robots_cache: dict[str, RobotFileParser] = {}


def robots_allows(url: str) -> bool:
    """Comprueba robots.txt para el dominio. Si no se puede leer, se asume permitido."""
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    rp = _robots_cache.get(base)
    if rp is None:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:
            return True
        _robots_cache[base] = rp
    return rp.can_fetch(USER_AGENT, url)


def fetch(url: str, *, check_robots: bool = True) -> str:
    """GET con User-Agent identificable, pausa y comprobación de robots.txt."""
    if check_robots and not robots_allows(url):
        raise ScraperError(ERR_BLOCKED, f"robots.txt prohíbe {url}")
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise ScraperError(ERR_NETWORK, f"{type(exc).__name__}: {exc}") from exc
    if resp.status_code >= 400:
        raise ScraperError(ERR_NETWORK, f"HTTP {resp.status_code} en {url}")
    resp.encoding = resp.encoding or "utf-8"
    time.sleep(REQUEST_PAUSE)
    if not resp.text.strip():
        raise ScraperError(ERR_EMPTY, f"respuesta vacía en {url}")
    return resp.text


# ------------------------------------------------------------ municipios

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


@dataclass(frozen=True)
class Municipio:
    name: str
    slug: str
    province: str
    pattern: re.Pattern = field(compare=False, repr=False, default=None)


def load_municipios(province: str | None = None) -> list[Municipio]:
    """Carga la base maestra desde data/municipios_tierra_de_campos.csv.

    Funciona sin base de datos, lo que permite ejecutar los scrapers en dry-run.
    """
    path = ROOT / "data" / "municipios_tierra_de_campos.csv"
    out: list[Municipio] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if province and row["province"] != province:
                continue
            norm = normalize_for_match(row["name"])
            out.append(
                Municipio(
                    name=row["name"],
                    slug=row["slug"],
                    province=row["province"],
                    pattern=re.compile(rf"(?<![A-Z0-9]){re.escape(norm)}(?![A-Z0-9])"),
                )
            )
    # Nombres largos primero: evita que "Villalba de la Loma" gane contra
    # "Villalba de la Lampreana" por un prefijo común.
    out.sort(key=lambda m: len(m.name), reverse=True)
    return out


def match_municipio(text: str, municipios: list[Municipio]) -> Municipio | None:
    """Devuelve el municipio citado en `text` (p.ej. 'AYUNTAMIENTO DE MAYORGA')."""
    norm = normalize_for_match(text)
    for m in municipios:
        if m.pattern.search(norm):
            return m
    return None


# ------------------------------------------------------------ Supabase

class Supabase:
    """Cliente mínimo sobre PostgREST. Evita dependencias pesadas.

    Usa la service_role key: solo se ejecuta en servidor/CLI, nunca en cliente.
    """

    def __init__(self):
        self.url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not self.url or self.key in ("", "replace_me"):
            raise ScraperError(
                ERR_NETWORK,
                "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env "
                "(usa --dry-run para probar sin base de datos)",
            )
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        })

    def _req(self, method: str, table: str, **kw) -> list[dict]:
        resp = self.session.request(method, f"{self.url}/rest/v1/{table}", timeout=REQUEST_TIMEOUT, **kw)
        if resp.status_code >= 400:
            raise ScraperError(ERR_NETWORK, f"Supabase {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content and resp.text.strip() else []

    def source_by_slug(self, slug: str) -> dict:
        rows = self._req("GET", "sources", params={"slug": f"eq.{slug}", "select": "id,name,url"})
        if not rows:
            raise ScraperError(ERR_STRUCTURE, f"No existe la fuente '{slug}' en sources")
        return rows[0]

    def municipality_ids(self) -> dict[str, str]:
        rows = self._req("GET", "municipalities", params={"select": "id,slug", "limit": "1000"})
        return {r["slug"]: r["id"] for r in rows}

    def insert_documents(self, docs: list[dict]) -> int:
        """Inserta ignorando duplicados por unique(source_id, hash)."""
        if not docs:
            return 0
        headers = {"Prefer": "resolution=ignore-duplicates,return=representation"}
        rows = self._req("POST", "documents", json=docs, headers=headers,
                         params={"on_conflict": "source_id,hash"})
        return len(rows)

    def start_run(self, source_id: str) -> str:
        rows = self._req("POST", "scrape_runs", json={"source_id": source_id, "status": "running"},
                         headers={"Prefer": "return=representation"})
        return rows[0]["id"]

    def finish_run(self, run_id: str, *, status: str, found: int = 0, new: int = 0,
                   error_type: str | None = None, error_message: str | None = None) -> None:
        self._req("PATCH", "scrape_runs", params={"id": f"eq.{run_id}"}, json={
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "documents_found": found,
            "documents_new": new,
            "error_type": error_type,
            "error_message": error_message,
        })


def parse_spanish_date(year: str, month_name: str, day: str) -> date:
    month = MESES.get(strip_accents(month_name).lower())
    if not month:
        raise ScraperError(ERR_PARSE, f"Mes desconocido: {month_name}")
    return date(int(year), month, int(day))
