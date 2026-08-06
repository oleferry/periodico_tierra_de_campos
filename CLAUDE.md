# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

El Terracampino: periódico digital de la comarca de Tierra de Campos (Palencia,
Valladolid, León y Zamora). Genera un sitio estático a partir de fuentes
oficiales, redactando con IA bajo reglas editoriales estrictas.

Todo el generador es Python, **salvo el publicador de Instagram**
(`scripts/publish-instagram.mjs`, Node — ver `docs/instagram.md`): es
deliberadamente genérico y dirigido por RSS para poder reutilizarse en otros
sitios sin tocar código específico de este proyecto.

## Reglas editoriales (no negociables)

- **Nunca inventar** personas, declaraciones, muertes ni el estado de un
  negocio. Si un dato no es fiable, **se omite** en vez de rellenar.
- **Citar siempre la fuente** y enlazar el documento original.
- **Esquelas**: revisión humana obligatoria, nunca automáticas.
- **Sección "Acompañar"**: jamás publicar que una persona concreta vive sola,
  ni listas de mayores solos (riesgo de robo y abuso).
- **Verificar teléfonos y recursos** antes de publicarlos.
- **Repo público**: no subir texto de medios ajenos (por eso `data/radar/`
  está en `.gitignore`) ni claves.

## Comandos

```bash
python -m sitegen.build              # regenera TODO el sitio en web/ (~8-20 min)
python -m scrapers.<nombre> --dry-run # prueba un scraper aislado, sin escribir
python -m bot.telegram_bot           # bot en local — ¡parar antes el de Railway!
```

Revisión humana (cada uno es interactivo, uno a uno):

```bash
python -m scripts.revisar_esquelas   # obligatorio antes de publicar una esquela
python -m scripts.revisar_fotos
python -m scripts.revisar_archivo
python -m scripts.listar_chivatazos
python -m scripts.leer_notas         # bloc de notas del admin vía Telegram
```

Contenido y análisis:

```bash
python -m scripts.generar_articulo_blog --tema <tema>   # investigación larga
python -m scripts.desarrollar_pista --listar            # pistas del radar
python -m scripts.detectar_anomalias                    # datos que se salen de su media
node scripts/publish-instagram.mjs --dry-run  # ver docs/instagram.md
```

**No hay suite de tests.** La verificación es: `--dry-run` del scraper tocado,
o un build completo mirando los `aviso:` del log.

## Arquitectura

```
scrapers/*.py ──► doc (dict)  ──► sitegen/redactor.py ──► sitegen/build.py ──► web/
   fuentes            │              caché → IA → reglas        render HTML     (estático)
   oficiales          │
                      └─ sitegen/ia.py (prompts + elección de modelo)
```

**`sitegen/redactor.py` es la pieza central**, no `ia.py`: implementa la cadena
de degradación que hace que el build nunca falle — texto ya revisado por un
humano → caché por hash → IA → redactor por reglas (determinista). Todo pasa
por ahí; `ia.py` solo tiene los prompts y decide el modelo.

**Los scrapers degradan con gracia**: si una fuente falla se lanza
`ScraperError`, el build imprime `aviso: ...` y sigue sin ella. Nunca dejar que
un scraper tumbe el build. El precio es que **los fallos son silenciosos**:
revisar los `aviso:` del log, no solo que el build salga en verde.

**Caché de IA** (`sitegen/cache.py`, en `data/cache/`, gitignorada): un JSON por
namespace, clave por hash del contenido. Sin ella el build cuesta ~5× más, así
que el Action la persiste con `actions/cache`. **`ia.PROMPT_VERSION` forma parte
de la clave: subirlo invalida la caché entera y fuerza cientos de llamadas a la
IA en el siguiente build.** Cambiarlo solo a conciencia.

**Dos niveles de modelo** (`sitegen/ia.py`): `MODELO_MECANICO` (barato) para
transformar datos en texto — el tiempo, moderar comentarios — y el modelo
editorial para lo que lleva juicio: plenos, ayudas, investigaciones, pistas.
No abaratar lo segundo: es lo que diferencia al periódico. Ver `docs/costes-ia.md`.

**Supabase como estado compartido** (`sitegen/almacen_*.py`): el bot corre en
Railway (disco efímero) y la revisión y el build corren en otra máquina, así que
fotos, esquelas, archivo, chivatazos, comentarios y notas viven en buckets
privados de Supabase, un objeto JSON por elemento (evita que dos envíos
simultáneos se pisen). Nada es público hasta aprobarse.

## Despliegue

- **Web**: `git push` → **Vercel despliega solo** (raíz del proyecto = `web/`).
- **Build diario**: GitHub Action (`.github/workflows/build-diario.yml`), 24/7.
  Una ejecución cancelada por timeout **no avisa**: la web se queda sin
  actualizar en silencio y además se pierde la caché de ese día.
- **El bot NO se redespliega con `git push`**: su servicio de Railway no está
  conectado a GitHub. Hay que desplegarlo explícitamente. Tras desplegar aparece
  un conflicto 409 de long-polling mientras convive con la instancia vieja; se
  resuelve solo en segundos.
- **Nunca correr el bot en local** con el de Railway encendido (dos instancias
  con el mismo token = 409 permanente).
- `web/api/*.js` en **CommonJS** (`module.exports`). Con sintaxis ESM falla el
  despliegue **entero**, no solo esa función.
- Las **claves nunca en el navegador**: van en variables de entorno de
  Vercel/Railway. Mapa de qué existe y dónde: `docs/secretos.md` (sin valores).

## Documentación de referencia

`README_PROYECTO.md` (planteamiento y municipios piloto) ·
`docs/lanzamiento.md` (checklist) · `docs/newsletter.md` (MailerLite) ·
`docs/costes-ia.md` · `docs/instagram.md` · `docs/acompanar.md` ·
`docs/publicidad.md` · `docs/secretos.md` · `bot/README.md` ·
`docs/ideas-*.md` (backlog).

## Sincronización multi-dispositivo

Este repo se trabaja desde varios equipos Windows distintos.

- Al inicio de sesión: `git fetch origin` + `git pull --rebase` antes de tocar
  código. Si hay cambios locales sin commitear, avísame primero.
- Si hay conflictos, para y muéstramelos.
- Al terminar una tarea: `git add -A`, commit descriptivo en español y
  `git push`. Confirma que el push ha funcionado.
- Nunca commitear node_modules, .env, dist ni build.
