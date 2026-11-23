"""Investigación semanal automática: elige tema, lo investiga con búsqueda web
real, lo redacta y deja el artículo listo para proponerlo como PR.

Decisión del usuario (2026-09-17): las investigaciones dejan de depender de que
alguien lance scripts/generar_articulo_blog.py con un dossier escrito a mano.
Tres fases, todas con el modelo editorial (sitegen/ia.py):

  1. ELEGIR  — un tema investigable solo con fuentes públicas en línea, a partir
     del backlog (docs/ideas-blog.md, solo las 🟢 y 🟡: las 🔴 necesitan trabajo
     de campo y una IA que las "investiga" acaba inventando) y de lo que ha visto
     el radar, sin repetir lo publicado ni lo ya propuesto.
  2. INVESTIGAR — búsqueda y lectura web reales; dossier con fuente, fecha y URL
     de cada dato. Si los hechos no dan para una pieza honesta, se para aquí:
     mejor una semana sin investigación que una rellena.
  3. REDACTAR — ia.redactar_investigacion(), la misma de las piezas hechas a mano.

El dossier se guarda en data/blog/investigaciones/<slug>.investigacion.md y va
en la PR: sin él, las fuentes de cada artículo se perderían en cuanto caducara
el log del Action.

La publicación NO la hace este script. El workflow investigacion-semanal.yml
abre una PR; el build diario la fusiona sola pasadas 48 h si nadie la cierra
(ver build-diario.yml). Cerrar la PR = vetar la pieza.

Uso:
    python -m scripts.investigacion_semanal                       # las tres fases
    python -m scripts.investigacion_semanal --solo-tema           # solo elige (barato, para probar)
    python -m scripts.investigacion_semanal --evitar propuestas.json --github
    python -m scripts.investigacion_semanal --avisar "texto"      # mensaje privado al admin
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Sin envolver aquí stdout en UTF-8: ya lo hace generar_articulo_blog al
# importarse, y envolverlo dos veces cierra la salida en cuanto el primer
# envoltorio se libera ("I/O operation on closed file").
from scripts.generar_articulo_blog import escribir_articulo  # noqa: E402
from sitegen import ia  # noqa: E402
from sitegen.build import url_publica  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
IDEAS_PATH = ROOT / "docs" / "ideas-blog.md"
MANIFIESTO = DATA / "blog" / "articulos.json"
DOSSIERS_DIR = DATA / "blog" / "investigaciones"
PISTAS_PATH = DATA / "radar" / "pistas.json"

_ITEM = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)$")


def ideas_investigables() -> str:
    """Las ideas 🟢 y 🟡 del backlog, con su descripción (que a veces ocupa
    varias líneas). Las 🔴 y las ✅ se quedan fuera."""
    bloques: list[list[str]] = []
    for linea in IDEAS_PATH.read_text(encoding="utf-8").splitlines():
        if linea.startswith("## ") and bloques:
            break  # fin de la lista
        if _ITEM.match(linea):
            bloques.append([linea])
        elif bloques and linea.strip():
            bloques[-1].append(linea.strip())
    elegibles = []
    for b in bloques:
        texto = " ".join(b)
        if ("🟢" in texto or "🟡" in texto) and "✅" not in texto:
            elegibles.append(texto[:900])
    return "\n".join(elegibles)


def titulares_publicados() -> list[str]:
    if not MANIFIESTO.exists():
        return []
    return [f"{a['fecha']} · {a['titular']}" for a in json.loads(MANIFIESTO.read_text(encoding="utf-8"))]


def titulares_radar(dias: int = 14) -> list[str]:
    """Solo titulares, y sin los descartados como suceso: el radar sugiere
    ángulos, no temas en sí."""
    if not PISTAS_PATH.exists():
        return []
    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    return [
        f"{p['municipality_name']}: {p['titulo']}"
        for p in json.loads(PISTAS_PATH.read_text(encoding="utf-8"))
        if (p.get("detected_at") or "") >= limite and p.get("motivo_descarte") != "suceso"
    ][:60]


def avisar_admin(texto: str) -> None:
    """Mensaje privado al administrador (nunca al canal público)."""
    import requests

    token, admin = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("ADMIN_TELEGRAM_ID")
    if not token or not admin:
        print("aviso: sin TELEGRAM_BOT_TOKEN o ADMIN_TELEGRAM_ID, no se avisa por Telegram", file=sys.stderr)
        return
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": admin, "text": texto, "disable_web_page_preview": True}, timeout=20)
    if r.status_code != 200:
        print(f"aviso: Telegram respondió {r.status_code}: {r.text[:200]}", file=sys.stderr)


def _salida_github(**valores: str) -> None:
    ruta = os.getenv("GITHUB_OUTPUT")
    if not ruta:
        return
    with open(ruta, "a", encoding="utf-8") as f:
        for clave, valor in valores.items():
            f.write(f"{clave}={valor.replace(chr(10), ' ')}\n")


def cuerpo_pr(tema: dict, art: dict, slug: str, busquedas: int) -> str:
    revisar = "\n".join(f"- [ ] {p}" for p in art.get("revision_humana", [])) or "- (la IA no señaló ninguno)"
    fuentes = "\n".join(f"- {f}" for f in art.get("fuentes_usadas", [])) or "- (ver el dossier)"
    return f"""## {art['titular']}

> {art['entradilla']}

**Pregunta central:** {tema['pregunta_central']}
**Por qué ahora:** {tema['por_que_ahora']}
**Búsquedas web realizadas:** {busquedas}

### Se publica sola en 48 horas
Esta pieza la ha elegido, investigado y redactado la IA sin intervención humana.
**Si no cierras esta PR, el build diario la publica pasadas 48 h** (y con ella salen
la newsletter por Telegram y el aviso al canal). **Para vetarla: cierra la PR.**
Vercel deja un enlace de previsualización en los comentarios de abajo para leerla entera.

### Puntos que la IA pide revisar
{revisar}

### Fuentes que dice haber usado
{fuentes}

Dossier completo de la investigación, con URL de cada dato:
`data/blog/investigaciones/{slug}.investigacion.md`

Página: {url_publica(f'blog/{slug}')} (tras publicarse)
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Investigación semanal automática")
    ap.add_argument("--solo-tema", action="store_true", help="solo elige el tema y lo muestra")
    ap.add_argument("--evitar", metavar="JSON", help="lista JSON de títulos ya propuestos (de gh pr list)")
    ap.add_argument("--github", action="store_true", help="escribe slug y cuerpo de la PR para el workflow")
    ap.add_argument("--sin-imagen", action="store_true")
    ap.add_argument("--avisar", metavar="TEXTO", help="solo manda TEXTO al admin por Telegram")
    args = ap.parse_args()

    if args.avisar:
        avisar_admin(args.avisar)
        return 0
    if not ia.disponible():
        print("ERROR: falta ANTHROPIC_API_KEY", file=sys.stderr)
        return 1

    hoy = date.today().isoformat()
    propuestas: list[str] = []
    if args.evitar and Path(args.evitar).exists():
        propuestas = [p.get("title", "") for p in json.loads(Path(args.evitar).read_text(encoding="utf-8"))]

    print("· Fase 1: eligiendo tema…")
    tema = ia.elegir_tema_investigacion(
        ideas=ideas_investigables(), publicadas=titulares_publicados(),
        propuestas=propuestas, pistas=titulares_radar(), hoy=hoy,
    )
    print(f"  {tema['titulo_de_trabajo']}")
    print(f"  pregunta: {tema['pregunta_central']}")
    print(f"  idea del backlog: {tema['idea_backlog']}")
    if args.solo_tema:
        print(json.dumps(tema, ensure_ascii=False, indent=2))
        return 0

    print("· Fase 2: investigando con búsqueda web (puede tardar 5-15 minutos)…")
    inv = ia.investigar_tema(tema, hoy)
    print(f"  {inv['busquedas']} búsquedas · dossier de {len(inv['dossier'])} caracteres")
    if not inv["suficiente"]:
        motivo = inv["motivo"] or "sin motivo"
        print(f"  PARADA: no hay hechos suficientes ({motivo})")
        avisar_admin(
            f"Investigación semanal: esta semana no sale ninguna.\n\n"
            f"Tema intentado: {tema['titulo_de_trabajo']}\n"
            f"Motivo: {motivo}\n\n"
            f"Mejor una semana sin pieza que una rellena. La semana que viene se prueba otro tema."
        )
        if args.github:
            _salida_github(slug="", titular="")
        return 0

    print("· Fase 3: redactando…")
    art = ia.redactar_investigacion(tema["titulo_de_trabajo"], inv["dossier"])
    slug, tiene_imagen = escribir_articulo(art, tema["tema_clave"], sin_imagen=args.sin_imagen)
    print(f"  {art['titular']}  (imagen: {'sí' if tiene_imagen else 'no'})")

    DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
    (DOSSIERS_DIR / f"{slug}.investigacion.md").write_text(
        f"# Dossier: {tema['titulo_de_trabajo']}\n\n"
        f"- Fecha de la investigación: {hoy}\n"
        f"- Pregunta central: {tema['pregunta_central']}\n"
        f"- Por qué ahora: {tema['por_que_ahora']}\n"
        f"- Idea del backlog: {tema['idea_backlog']}\n"
        f"- Búsquedas web: {inv['busquedas']}\n\n"
        f"{inv['dossier']}\n",
        encoding="utf-8",
    )

    if args.github:
        cuerpo = Path(os.getenv("RUNNER_TEMP", str(DATA))) / "cuerpo-pr.md"
        cuerpo.write_text(cuerpo_pr(tema, art, slug, inv["busquedas"]), encoding="utf-8")
        _salida_github(slug=slug, titular=art["titular"], cuerpo=str(cuerpo))
    print(f"\nListo: web/blog/{slug}.html + dossier en data/blog/investigaciones/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
