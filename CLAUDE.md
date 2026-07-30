# El Terracampino — guía para trabajar en este repo

Periódico digital de la comarca de Tierra de Campos (Palencia, Valladolid, León
y Zamora). Generador de sitio estático en Python (`sitegen/`), scrapers de
fuentes oficiales (`scrapers/`), bot de Telegram (`bot/`) y funciones
serverless (`web/api/`, CommonJS).

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

## Cómo funciona

- `python -m sitegen.build` regenera todo el sitio en `web/`. Tarda varios
  minutos (habla con las fuentes y la IA).
- Los **scrapers degradan con gracia**: si una fuente falla, se lanza
  `ScraperError` y el build sigue sin ella. Nunca dejar que un scraper tumbe
  el build entero.
- **Build diario**: GitHub Action (`.github/workflows/build-diario.yml`), 24/7.
  Al hacer push, **Vercel despliega solo**.
- **El bot NO se redespliega con `git push`**: su servicio de Railway no está
  conectado a GitHub. Hay que desplegarlo explícitamente. Tras desplegar
  aparece un conflicto 409 de long-polling durante el solapamiento con la
  instancia vieja; se resuelve solo.
- **Nunca correr el bot en local** con el servicio de Railway encendido (dos
  instancias con el mismo token = conflicto 409).
- `web/api/*.js` en **CommonJS** (`module.exports`). Con sintaxis ESM falla el
  despliegue **entero**, no solo esa función.
- Las **claves nunca en el navegador**: van en variables de entorno de
  Vercel/Railway. Mapa de qué existe y dónde: `docs/secretos.md` (sin valores).

## Documentación de referencia

`docs/lanzamiento.md` (checklist) · `docs/newsletter.md` (MailerLite) ·
`docs/acompanar.md` · `docs/publicidad.md` · `docs/secretos.md` ·
`bot/README.md` · `docs/ideas-*.md` (backlog).

## Sincronización multi-dispositivo

Este repo se trabaja desde varios equipos Windows distintos.

- Al inicio de sesión: `git fetch origin` + `git pull --rebase` antes de tocar
  código. Si hay cambios locales sin commitear, avísame primero.
- Si hay conflictos, para y muéstramelos.
- Al terminar una tarea: `git add -A`, commit descriptivo en español y
  `git push`. Confirma que el push ha funcionado.
- Nunca commitear node_modules, .env, dist ni build.
