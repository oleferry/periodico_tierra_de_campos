"""Desarrolla una pista del radar (scrapers/radar_noticias.py) en una pieza
NUESTRA, que se publica en la ficha de su pueblo — nunca en la portada.

Por qué existe: el radar solo da pistas (titular ajeno + enlace). Publicar eso
sería republicar el trabajo de otro medio. Este script cierra el circuito:
lee la noticia de origen, extrae los HECHOS y encarga a la IA una pieza propia
que cita a quien lo publicó primero (ver sitegen/ia.py:_SISTEMA_PISTA, que
prohíbe copiar y parafrasear).

Reparto (lo que pidió el usuario el 2026-07-17): cada noticia vive en la ficha
de su pueblo, no en la portada — a un vecino de Villada no le interesa mucho lo
que pasa en Sahagún, y la portada no debe convertirse en un cajón de sastre.

Nada se publica solo:
  · el resultado se guarda con estado 'borrador' en data/noticias/propias.json;
  · solo aparece en la web cuando se marca 'publicado' (--publicar);
  · la política editorial (editorial/politica_editorial.md) prohíbe publicar
    sucesos automáticamente, y buena parte del radar son sucesos.

A diferencia de la cola de pistas (data/radar/, en .gitignore por ser texto
ajeno), este fichero SÍ se versiona: es contenido nuestro.

Uso:
    python -m scripts.desarrollar_pista --listar
    python -m scripts.desarrollar_pista --indice 3
    python -m scripts.desarrollar_pista --listar-borradores
    python -m scripts.desarrollar_pista --publicar <hash>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

from scrapers.common import ROOT, ScraperError, fetch, sha256  # noqa: E402
from scrapers.radar_noticias import PISTAS_PATH  # noqa: E402
from sitegen import ia  # noqa: E402

PROPIAS_PATH = ROOT / "data" / "noticias" / "propias.json"

# Mínimo de texto para que una noticia dé para una pieza propia. Por debajo de
# esto el original es un teletipo de tres líneas: no hay hechos suficientes y
# lo único "desarrollable" sería su redacción — justo lo que no queremos.
MIN_CARACTERES = 400


def _cargar(path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _guardar(path, datos: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _pistas_pilotos() -> list[dict]:
    """Pistas pendientes de pueblos con ficha. Las de pueblos vecinos se quedan
    en la cola: no hay dónde publicarlas todavía."""
    from sitegen.build import PILOTS

    return [p for p in _cargar(PISTAS_PATH)
            if p.get("estado") == "pendiente" and p["municipality_slug"] in PILOTS]


def extraer_texto(url: str) -> str:
    """Texto del artículo de origen, como materia prima de hechos para la IA.
    No se guarda ni se publica: solo alimenta la redacción propia."""
    soup = BeautifulSoup(fetch(url), "html.parser")
    for basura in soup.select("script, style, nav, header, footer, aside, form"):
        basura.decompose()
    nodo = soup.select_one("article") or soup.select_one("main") or soup.body
    if not nodo:
        raise ScraperError("unexpected_structure", f"Sin cuerpo legible en {url}")
    # Con <p> (WordPress: La Mar de Campos, Palencia en la Red) se filtra por
    # párrafo. Folioepress (Sahagún Digital, Leonsur, InterBenavente) no usa <p>
    # en el cuerpo — sus únicos <p> son el aviso legal de los comentarios — así
    # que ahí se cae al texto del propio <article>, línea a línea.
    parrafos = [p.get_text(" ", strip=True) for p in nodo.select("p")]
    texto = "\n".join(p for p in parrafos if len(p) > 40)
    if len(texto) < MIN_CARACTERES:
        texto = "\n".join(l for l in nodo.get_text("\n", strip=True).splitlines() if len(l) > 40)
    return texto.strip()


def desarrollar(pista: dict) -> dict:
    """Pista -> doc con nuestra redacción dentro. Lanza si no hay material o IA."""
    if not ia.disponible():
        raise SystemExit("Falta OPENAI_API_KEY/ANTHROPIC_API_KEY real en .env: sin IA no hay pieza propia.")

    print(f"· Leyendo la fuente ({pista['fuente']})…")
    texto = extraer_texto(pista["url_original"])
    print(f"  {len(texto)} caracteres de material")
    if len(texto) < MIN_CARACTERES:
        raise SystemExit(
            f"El original solo tiene {len(texto)} caracteres (mínimo {MIN_CARACTERES}). "
            "No hay hechos suficientes para una pieza propia: lo único que podríamos "
            "'desarrollar' sería su redacción. Descártala o busca otra fuente."
        )

    doc = {
        "municipality_slug": pista["municipality_slug"],
        "municipality_name": pista["municipality_name"],
        "title": pista["titulo"],          # solo referencia interna, NO se publica
        "source_type": "radar_local",
        "url_original": pista["url_original"],
        "published_at": (pista.get("publicado") or datetime.now(timezone.utc).isoformat())[:10],
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "pista_texto": texto,
        "hash": sha256(f"propia-{pista['url_original']}"),
        "confidence": "medium",            # material de terceros: siempre revisar
        "requires_review": True,
        "estado": "borrador",
        "metadata": {"fuente": pista["fuente"], "fuente_slug": pista["fuente_slug"],
                     "scraper": "SCR-016"},
    }

    print("· Redactando pieza propia con IA…")
    doc["redaccion"] = ia.redactar_pista(doc)
    # El material ajeno ya cumplió su función (alimentar la redacción). No se
    # conserva: el fichero se versiona en un repo público.
    doc.pop("pista_texto")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description="SCR-016 — Desarrolla una pista en pieza propia")
    ap.add_argument("--listar", action="store_true", help="pistas pendientes de pueblos con ficha")
    ap.add_argument("--listar-borradores", action="store_true", help="piezas propias sin publicar")
    ap.add_argument("--indice", type=int, help="desarrolla la pista N de --listar")
    ap.add_argument("--publicar", metavar="HASH", help="marca una pieza como publicada")
    args = ap.parse_args()

    if args.listar:
        pistas = _pistas_pilotos()
        for i, p in enumerate(pistas):
            print(f"[{i:2}] {p['municipality_name']:22} [{p['fuente']}] {p['titulo'][:70]}")
        print(f"\n{len(pistas)} pistas pendientes de pueblos con ficha.")
        return 0

    if args.listar_borradores:
        for d in _cargar(PROPIAS_PATH):
            print(f"[{d['estado']:9}] {d['municipality_name']:22} {d['redaccion']['titular'][:65]}")
            print(f"            {d['hash']}")
        return 0

    if args.publicar:
        propias = _cargar(PROPIAS_PATH)
        for d in propias:
            if d["hash"].startswith(args.publicar):
                d["estado"] = "publicado"
                _guardar(PROPIAS_PATH, propias)
                print(f"Publicada: {d['redaccion']['titular']}")
                print("Aparecerá en la ficha de", d["municipality_name"],
                      "en el próximo `python -m sitegen.build`.")
                return 0
        print(f"No hay ninguna pieza con hash {args.publicar}", file=sys.stderr)
        return 1

    if args.indice is None:
        ap.error("indica --listar, --indice N, --listar-borradores o --publicar HASH")

    pistas = _pistas_pilotos()
    if not 0 <= args.indice < len(pistas):
        print(f"Índice fuera de rango (hay {len(pistas)} pistas)", file=sys.stderr)
        return 1
    pista = pistas[args.indice]

    doc = desarrollar(pista)
    propias = [d for d in _cargar(PROPIAS_PATH) if d["hash"] != doc["hash"]]
    propias.insert(0, doc)
    _guardar(PROPIAS_PATH, propias)

    # La pista queda marcada para no volver a ofrecerla.
    cola = _cargar(PISTAS_PATH)
    for p in cola:
        if p["hash"] == pista["hash"]:
            p["estado"] = "desarrollada"
    _guardar(PISTAS_PATH, cola)

    r = doc["redaccion"]
    print(f"\n== Borrador para {doc['municipality_name']} ==")
    print(f"{r['titular']}\n")
    print(f"{r['entradilla']}\n")
    for parrafo in r["cuerpo"]:
        print(f"{parrafo}\n")
    print(f"Fuente citada: {doc['metadata']['fuente']} — {doc['url_original']}")
    print(f"\nGuardado como BORRADOR (no está en la web). Revísalo y, si vale:")
    print(f"  python -m scripts.desarrollar_pista --publicar {doc['hash'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
