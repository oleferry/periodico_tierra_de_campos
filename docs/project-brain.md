# El Terracampino — project brain

Documento de referencia único y exhaustivo del proyecto: qué es, cómo está
construido, qué decisiones se tomaron y por qué, qué trampas ya se pagaron,
qué queda pendiente y dónde vive cada cosa. Pensado para dar contexto completo
de una sentada — a una persona nueva o a una sesión de IA que no ha visto el
resto del repo.

Última actualización: 2026-08-26.

---

## Índice

1. [Qué es y por qué existe](#1-qué-es-y-por-qué-existe)
2. [Arquitectura de alto nivel](#2-arquitectura-de-alto-nivel)
3. [Estructura del repositorio](#3-estructura-del-repositorio)
4. [El pipeline editorial](#4-el-pipeline-editorial)
5. [Reglas editoriales no negociables](#5-reglas-editoriales-no-negociables)
6. [Voz editorial](#6-voz-editorial)
7. [Las nueve secciones](#7-las-nueve-secciones)
8. [Infraestructura y despliegue](#8-infraestructura-y-despliegue)
9. [Canales de distribución](#9-canales-de-distribución)
10. [Coste de la IA y las dos optimizaciones](#10-coste-de-la-ia-y-las-dos-optimizaciones)
11. [Mapa de secretos](#11-mapa-de-secretos)
12. [Trampas ya pagadas — no repetirlas](#12-trampas-ya-pagadas--no-repetirlas)
13. [Estado actual (cifras reales)](#13-estado-actual-cifras-reales)
14. [Pendiente activo](#14-pendiente-activo)
15. [Cómo se trabaja en este repo](#15-cómo-se-trabaja-en-este-repo)
16. [Documentación de referencia](#16-documentación-de-referencia)

---

## 1. Qué es y por qué existe

El Terracampino es un periódico digital para **Tierra de Campos**, la comarca
agrícola repartida entre cuatro provincias — Palencia, Valladolid, León y
Zamora — que ha perdido más población que casi ninguna otra zona de España en
el último siglo. Ningún diario provincial cubre estos pueblos pueblo a pueblo:
cuando pasa algo en Villalón, en Mayorga o en Villarramiel, se pierde entre
las noticias de la capital.

No nace como periódico completo, sino como **máquina de información local**
(ver `README_PROYECTO.md`, el documento fundacional del MVP): un sistema que
detecta información pública nueva, la extrae, la clasifica, la resume sin
inventar, marca los riesgos editoriales/legales, genera una pieza publicable,
la pasa por revisión humana cuando toca, y publica en web, Telegram y
newsletter. **No es opinión automática. Es vigilancia local estructurada.**

Propiedad: **María Vega Blanco**. Desarrollado por **NARAYA SERVICES CLOUD
CONSULTING SL** (NIF B42792101), declarado en el aviso legal del sitio.

Dominio: **elterracampino.es**. Fundado 2026, sede editorial en Becerril de
Campos.

### Principio de cierre (README_PROYECTO.md §21)

> Si algo no se puede trazar a una fuente, no se publica.
> Si algo puede dañar a una persona, no se automatiza.
> Si algo requiere interpretación legal, no se maquilla como noticia.
> El sistema debe ahorrar tiempo. No crear otro trabajo.

---

## 2. Arquitectura de alto nivel

```
Fuentes públicas (BOP/BOCyL, sedes electrónicas, AEMET, prensa local, deporte…)
        │
        ▼
   scrapers/*.py  ──►  doc (dict normalizado)
        │                    si una fuente falla: ScraperError, "aviso: ..." en
        │                    el log, el build SIGUE sin ella (nunca tumba nada)
        ▼
   sitegen/redactor.py  ──►  cadena de degradación:
        │                    texto ya revisado por humano
        │                    → caché por hash (sitegen/cache.py)
        │                    → IA (sitegen/ia.py)
        │                    → redactor por reglas (determinista, nunca falla)
        ▼
   sitegen/build.py  ──►  render de TODO el sitio estático (web/)
        │
        ▼
   git push  ──►  Vercel despliega solo (raíz del proyecto = web/)
```

**Todo el generador es Python**, salvo los publicadores de redes sociales
(`scripts/publish-instagram.mjs`, `scripts/publish-facebook.mjs`, Node):
deliberadamente genéricos y dirigidos por RSS para poder reutilizarse en otros
sitios del propio Daniel (madapan.es, gafasvan.com) sin tocar código
específico de este proyecto. Ver §9.4.

### Piezas que corren en máquinas distintas, con Supabase como estado compartido

- **El bot de Telegram** corre 24/7 en **Railway** (disco efímero).
- **El build y la revisión humana** corren en el/los ordenadores de Daniel
  (varios equipos Windows, ver §15) — pero desde 2026-08-01 el build diario
  **también** corre solo en GitHub Actions, sin depender de que haya un
  portátil encendido.
- Fotos, esquelas, archivo, chivatazos, comentarios y notas del admin viven en
  **buckets privados de Supabase**, un objeto JSON por elemento (evita que dos
  envíos simultáneos se pisen). **Nada es público hasta que se aprueba.**

---

## 3. Estructura del repositorio

```
CLAUDE.md                 instrucciones para Claude Code — reglas no negociables,
                           comandos, arquitectura resumida
README_PROYECTO.md         documento fundacional del MVP (2026, aún vigente)

scrapers/                  una fuente por fichero, todas degradan con ScraperError
  aemet_avisos.py           avisos meteorológicos oficiales
  bdns.py                   subvenciones (Base de Datos Nacional de Subvenciones)
  bocyl.py                  Boletín Oficial de Castilla y León
  bop_valladolid.py         Boletín Oficial de la Provincia de Valladolid
  embalses.py                nivel de embalses (contexto agro/huerta)
  futbolme.py / siguetuliga.py   resultados y clasificaciones de fútbol/baloncesto local
  lonja.py                   precio del cereal
  municipal_wp.py            noticias de ayuntamientos con web WordPress
  paro_sepe.py                datos de paro (SEPE)
  plenos_sedelectronica.py    actas de plenos (Playwright para Mayorga — JS-heavy)
  radar_noticias.py           vigila prensa local de la comarca → cola de "pistas"
  ruralgo_checker.py          huerta/riego
  weather_openmeteo.py        el tiempo

sitegen/                   el generador del sitio
  build.py                   pieza central: arma TODO el HTML de web/
  redactor.py                 cadena de degradación (humano → caché → IA → reglas)
  ia.py                       prompts + elección de modelo (MODELO_MECANICO vs editorial)
  cache.py                     caché de textos IA por hash (data/cache/, gitignorada)
  contenido.py / imagenes.py / fotos.py    utilidades de contenido e imágenes
  almacen_*.py                 acceso a los buckets de Supabase (fotos, esquelas,
                                archivo, chivatazos, comentarios, notas)

scripts/                   comandos operativos (todos con --help)
  generar_articulo_blog.py    investigación larga (dossier IA con búsqueda web
                               real + redacción). Publica también en el canal.
  desarrollar_pista.py         SCR-016: convierte una pista del radar en pieza
                               propia para la ficha de SU pueblo — nunca portada
  empaquetar_newsletter.py     NUEVO (2026-08): investigación → zip para MailerLite
                               + envío automático por Telegram (ver §9.3)
  boletin_telegram.py          boletín diario al canal — solo si hay algo real
  avisar_meteo.py               avisos meteorológicos puntuales
  detectar_anomalias.py         datos que se salen de su media
  moderar_comentarios.py        moderación IA de comentarios (modelo barato)
  buscar_fotos_libres.py        fotos de banco libre de derechos
  generate_santoral.py          santoral diario
  revisar_esquelas.py           revisión humana OBLIGATORIA antes de publicar
  revisar_fotos.py / revisar_archivo.py    cola de revisión (fotos, archivo histórico)
  listar_chivatazos.py          bandeja de chivatazos recibidos
  leer_notas.py                  bloc de notas del admin (vía Telegram)
  refrescar_blog.py              re-envuelve web/blog/*.html con el shell() actual
  publish-instagram.mjs / publish-facebook.mjs (Node)   publicadores RSS→redes
  instagram-posted.json / facebook-posted.json           registro de publicados

bot/telegram_bot.py        bot 24/7 en Railway: fotos, esquelas, chivatazos,
                            notas privadas del admin (/id, /notas)

brand/                     identidad visual
  web/brand-tokens.css       tokens de marca (colores, tipografías, espaciado)
  hermanos/                   NUEVO: banners de proyectos hermanos (§9.3)
  anunciantes/                 preparado, vacío — a la espera de la 1ª lista (§9.5)
  logos/, sistema_marca_v1_2/  logo, guía de marca completa

editorial/
  politica_editorial.md       reglas no negociables (§5)
  sistema_marca_v1_2/          brand content book, checklist de publicación,
                                guía de storytelling, prompt maestro, regla de párrafo

docs/                       toda la documentación de referencia (§16)
data/                        estado persistente (parte gitignorada, parte no — ver
                              cada fichero, el criterio siempre está comentado ahí)
web/                         EL SITIO ESTÁTICO GENERADO — no se edita a mano
config/, database/, prompts/  configuración base y prompts del MVP original
.github/workflows/            build-diario.yml, instagram-publish.yml,
                               facebook-publish.yml
```

---

## 4. El pipeline editorial

### 4.1. Detección y extracción

Cada scraper devuelve un `doc` normalizado (municipio, tipo de fuente, texto,
URL original, hash, fecha, nivel de confianza). Si una fuente falla se lanza
`ScraperError`; el build imprime `aviso: ...` y sigue sin ella. **Los fallos
son silenciosos por diseño** — lo cual significa que hay que **leer los
`aviso:` del log**, no solo comprobar que el build salió en verde.

### 4.2. Redacción — la cadena de degradación (`sitegen/redactor.py`)

Es la pieza central del proyecto, más que `ia.py`. Para cada `doc`, en orden:

1. **Texto ya revisado por un humano** (si existe) — máxima prioridad.
2. **Caché por hash** (`sitegen/cache.py`, `data/cache/`, gitignorada) — si el
   contenido no cambió, no se vuelve a pagar la llamada a la IA.
3. **IA** (`sitegen/ia.py`) — con los prompts y el modelo que toque.
4. **Redactor por reglas** (determinista) — si todo lo anterior falla, esto
   NUNCA falla. Es lo que garantiza que **el build nunca se cae**.

### 4.3. Dos niveles de modelo (`sitegen/ia.py`)

- **`MODELO_MECANICO`** (Haiku 4.5, barato): tareas mecánicas sin criterio
  editorial que proteger — el parte del tiempo, la moderación de comentarios.
- **Modelo editorial** (Opus, vía `_model()`): todo lo que lleva juicio —
  `redactar_pleno()`, `redactar_ayuda()`, `redactar_investigacion()`,
  `redactar_pista()`. **Esto nunca se abarata** — es lo que diferencia al
  periódico de un generador de contenido genérico. Ver §10.
- **`ESFUERZO_BAJO`** (`{"effort": "low"}`): solo para titulares/entradillas
  de feed (~100 llamadas cortas y acotadas por build), no para piezas largas.
- **`PROMPT_VERSION`** forma parte de la clave de caché: subirlo invalida la
  caché ENTERA y fuerza cientos de llamadas a la IA en el siguiente build.
  Cambiarlo solo a conciencia.

### 4.4. Investigaciones largas (`scripts/generar_articulo_blog.py`)

Distinto del resto del pipeline: es **manual**, no se dispara solo. Fase de
investigación con búsqueda web real (jerarquía de fuentes: oficiales → casos
primarios → prensa de calidad contrastada), luego redacción a partir
**solo** del dossier (nunca de memoria). Publica el resultado en
`web/blog/<slug>.html` y avisa en el canal de Telegram.

**Esto llevaba dos semanas parado en algún momento de agosto** (última entre
el 4 y el 24 de agosto) — no es un fallo técnico, es que nadie lo lanzó: no
hay disparador automático, hay que ejecutarlo a mano eligiendo tema.

### 4.5. El radar de pistas (`scrapers/radar_noticias.py` + `scripts/desarrollar_pista.py`)

El radar vigila la prensa local de la comarca y guarda titulares+enlaces como
**pistas** en `data/radar/` (gitignorado — es texto ajeno, el repo es
público). `desarrollar_pista.py` (SCR-016) convierte una pista en **pieza
propia**: lee la fuente original, extrae los HECHOS, y encarga a la IA una
redacción propia que **cita siempre** a quien lo publicó primero — nunca
copia ni parafrasea.

- Vive en la ficha de **su pueblo**, nunca en portada (decisión del
  2026-07-17: a un vecino de Villada no le interesa tanto lo de Sahagún).
- **Decisión del 2026-08-24: se publica directo, sin paso de revisión
  manual.** Antes quedaba como `borrador` hasta `--publicar HASH`; ahora
  `--indice N` publica ya. Fue una decisión explícita de Daniel tras que se
  le planteara el trade-off (el material es de terceros, confianza `medium`)
  — no un cambio unilateral.
- Mínimo de 400 caracteres de material en la fuente para "desarrollarse" —
  por debajo de eso no hay hechos suficientes, solo redacción.

### 4.6. Esquelas — la única pieza 100% manual del sistema

`scripts/revisar_esquelas.py`: **revisión humana obligatoria, nunca
automática**. Es una regla de `CLAUDE.md` de máxima prioridad.

---

## 5. Reglas editoriales no negociables

De `CLAUDE.md` + `editorial/politica_editorial.md`. Estas reglas **no se
tocan ni se configuran por prisa ni por volumen**:

- **Nunca inventar** personas, declaraciones, muertes ni el estado de un
  negocio. Si un dato no es fiable, **se omite**, no se rellena.
- **Citar siempre la fuente** y enlazar el documento original.
- **Esquelas**: revisión humana obligatoria, nunca automáticas.
- **Sección Acompañar**: jamás publicar que una persona concreta vive sola,
  ni listas de mayores solos (riesgo real de robo y abuso).
- **Verificar teléfonos y recursos** antes de publicarlos.
- **Repo público**: no subir texto de medios ajenos (`data/radar/` en
  `.gitignore`) ni claves.
- **Revisión humana obligatoria** si aparecen: nombres de particulares,
  menores, sanciones, deudas, conflictos laborales, procesos judiciales,
  acusaciones políticas, datos sanitarios, importes relevantes, contratación
  pública sensible, OCR dudoso, fuente no oficial, contradicciones.
- **Se puede automatizar sin revisión**: tiempo, resultados deportivos,
  clasificaciones, próxima jornada, agenda básica con fuente clara, avisos
  meteorológicos, orientación de huerta, recordatorios de plazo sin
  interpretación jurídica.
- **Aviso editorial fijo** (debe aparecer en web y newsletter):

  > Este medio resume información pública procedente de fuentes oficiales y
  > abiertas. Los resúmenes no sustituyen al documento original. Ante
  > cualquier trámite, plazo, ayuda o acuerdo municipal, consulta siempre la
  > fuente oficial enlazada.

---

## 6. Voz editorial

De `docs/voz-editorial.md` (sustituye a `docs/guia-estilo-gi.md`, que es de
blog/opinión personal y no encaja aquí).

**La idea en una frase:** que el lector piense que se lo cuenta **un vecino
que se entera de todo** — no una institución, no una IA, no un BOE con
maquillaje. Cercano pero serio, de fiar: no exagera, no rellena, y si no sabe
algo lo dice.

**Cuatro trampas a evitar:** sonar a BOE (traducir, no resumir el trámite),
sonar a IA genérica ("cabe destacar", "en resumen" — fuera), sonar a folclore
(nada de "nuestra querida tierra" ni exclamaciones), sonar campechano forzado
(nada de "¡hola, vecino!" ni tacos ni chistes).

**Intensidad de la voz por tipo de contenido** (`politica_editorial.md` §5):
alta en tiempo/huerta/newsletter (hay margen narrativo), moderada en
plenos/ayudas/BOP (pesa más el dato exacto que el estilo — la precisión legal
importa más que el gancho).

Lo que **nunca cambia**, sea cual sea el tono: no se inventa nada fuera del
texto oficial, se enlaza siempre la fuente, cero interpretación jurídica
disfrazada de hecho, el aviso editorial fijo se mantiene siempre.

---

## 7. Las nueve secciones

De `docs/secciones-editoriales.md` — consolida el kit de marca, el enum
`source_type` de `database/schema.sql` y el brainstorming original.

| Sección | Color de marca | Qué cubre | Automatización |
|---|---|---|---|
| **Hoy** | Terrón | Portada: agregador del resto de secciones | Automático (hereda el riesgo de lo que agrega) |
| **Ayuntamiento en limpio** | Azul BOP | Plenos, acuerdos, sede electrónica, BOP/BOCyL | Auto + revisión humana obligatoria |
| **El marcador** | Tinta Tierra | Fútbol y baloncesto local | Automático |
| **A ras de tierra** | Cielo Bajo | El tiempo y avisos meteorológicos | Automático |
| **Campo y huerta** | Verde Regadío | Agro profesional + huerta familiar (sección diferencial, ver abajo) | Automático |
| **Agenda** | Trigo Seco | Fiestas, ferias, eventos, cultura | Automático |
| **Ayudas y plazos** | Azul BOP | Subvenciones (BDNS, Junta, diputaciones), empleo público | Revisión si hay importe o requisito legal |
| **Negocios de aquí** | Terrón | Directorio de comercios, aperturas, traspasos | Curación manual (no hay fuente automatizable) |
| **Historias del terrón** | Tinta Tierra | Patrimonio, relatos, memoria local | Curación manual |

**Campo y huerta** tiene dos públicos que **nunca se mezclan en la misma
pieza** aunque compartan sección: **agro profesional** (cereal, PAC, precio de
lonja) y **huerta familiar/hortelanos aficionados** — este segundo ángulo no
existe en ningún otro medio de la comarca, es terreno libre y da contenido
evergreen (calendario mensual adaptado a la meseta, reutilizable cada año).

**Huecos sin sección propia todavía:** Empleo (vive dentro de "Ayudas y
plazos" por ahora) y Vivienda/traspasos (fusionado en "Negocios de aquí").
Decisión deliberada: no añadir una sección nueva por cada cosa desde el
principio, complica el kit de marca.

---

## 8. Infraestructura y despliegue

| Servicio | Qué hace | Notas |
|---|---|---|
| **Vercel** | Hosting del sitio estático (`web/`) + funciones serverless (`web/api/*.js`, CommonJS obligatorio) | `git push` a `main` → despliega solo. Con sintaxis ESM en `web/api/` **falla el despliegue entero**, no solo esa función |
| **GitHub Actions** | `build-diario.yml` (cron `10 6 * * *`, 24/7, `timeout-minutes: 40`) reconstruye el sitio, manda el boletín de Telegram y la newsletter, y publica | Una ejecución cancelada por timeout **no avisa** — la web se queda sin actualizar en silencio y se pierde la caché de ese día |
| **Railway** | Bot de Telegram 24/7 (disco efímero) | **No se redespliega con `git push`** — su servicio no está conectado a GitHub, hay que desplegar a mano. Tras desplegar, hay un 409 de long-polling normal mientras convive con la instancia vieja (se resuelve solo en segundos) |
| **Supabase** | Estado compartido entre Railway (bot) y el build: fotos, esquelas, archivo, chivatazos, comentarios, notas — buckets privados, un JSON por elemento | Nada es público hasta que se aprueba |

**Reglas duras de despliegue:**
- Nunca correr el bot en local con el de Railway encendido (dos instancias +
  mismo token = 409 permanente).
- Las claves nunca en el navegador — van en variables de entorno de
  Vercel/Railway, nunca en código ni en el repo.

### GitHub Actions activos

1. **`build-diario.yml`** — reconstruye todo el sitio. Pasos, en orden:
   scrapers → radar → `sitegen.build` (con `ANTHROPIC_API_KEY`,
   `SUPABASE_*`, `LLM_PROVIDER/MODEL`) → boletín de Telegram
   (`continue-on-error`) → **newsletter por Telegram** (`--auto`,
   `continue-on-error`, nuevo desde 2026-08) → publicar (git add/commit/push
   con manejo explícito de conflictos de rebase, ver §12).
2. **`instagram-publish.yml`** — semanal (lunes), publica la investigación
   más reciente con imagen. **Bloqueado**: faltan `META_IG_USER_ID` /
   `META_IG_ACCESS_TOKEN`.
3. **`facebook-publish.yml`** — semanal (lunes, 15 min después de
   Instagram), publica enlace + tarjeta Open Graph de la investigación más
   reciente. **Bloqueado**: faltan `META_FB_PAGE_ID` / `META_FB_ACCESS_TOKEN`.

---

## 9. Canales de distribución

### 9.1. Web — elterracampino.es

Ficha propia por municipio (32 activas a día de hoy, ver §13), tipografía
accesible (Atkinson Hyperlegible — pensada para lectores mayores, 16px mínimo
en formularios para no disparar el zoom de iOS Safari), menú móvil de
pantalla completa, popup de doble vía de suscripción (email + Telegram).

### 9.2. Telegram — @elterracampino

Canal público con boletín diario (`scripts/boletin_telegram.py`): **solo
manda algo si hay noticia real**, nunca solo el tiempo. Reglas duras
aprendidas a base de bugs reales (ver §12): ordena por fecha antes que por
relevancia, agrupa por hash (un anuncio multi-pueblo no cuenta como N
noticias), y limita a 2 piezas por pueblo por día para que uno no monopolice
el boletín.

El bot (Railway) también gestiona en privado: fotos, esquelas, chivatazos, y
el bloc de notas del administrador (`/id`, `/notas` — solo responde a
`ADMIN_TELEGRAM_ID`).

### 9.3. Newsletter — MailerLite

**Secuencia de bienvenida** (6 pasos, funcionando de punta a punta, probada
con suscripción real el 2026-08-01): al suscribirse, el lector recibe la
bienvenida y luego, uno a uno con 2-4 días de espera, los reportajes ya
publicados en orden. Se configura a mano en MailerLite (su API no crea
automatizaciones). Texto completo en `docs/newsletter.md`.

**Newsletter de investigaciones nuevas** (`scripts/empaquetar_newsletter.py`,
2026-08, la pieza más reciente construida):

- Cada investigación nueva se empaqueta como **email HTML completo** (todos
  los párrafos y subtítulos, más la caja de fuentes citadas — no un teaser)
  con su portada reescalada a 536px, listo para importar en MailerLite vía
  **Campaigns → Create campaign → Regular → editor HTML → Import zip**.
- Por qué a mano y no por API: meter contenido de campaña por API exige el
  plan **Advanced** de MailerLite; el gratuito no lo permite.
- El zip lleva **banner rotativo de un proyecto hermano**
  (`brand/hermanos/hermanos.json`: Madapan, Dame Perras Perro, Gafasvan),
  colocado tras el primer párrafo. La rotación cuenta por **investigación
  empaquetada**, no por semana del calendario — si dos investigaciones salen
  la misma semana o una semana no hay ninguna, el reparto sigue siendo uno
  cada uno. Estado en `data/newsletter_banners_estado.json` (versionado a
  propósito).
- **`--auto` corre en el build diario**: si hay una investigación que no se
  haya mandado ya, la empaqueta y la manda **por Telegram al administrador
  en privado** (nunca al canal público — es un borrador de trabajo, no
  contenido publicado). `continue-on-error` para no bloquear el resto del
  build si falla.
- El HTML lleva `{$unsubscribe}` **literal** en el pie — MailerLite rechaza
  el import si no lo encuentra.

**Publicidad/anunciantes** (`docs/publicidad.md`): mecanismo y plantilla
listos, `data/anunciantes.json` con la estructura ya definida, pero **vacío**
— a la espera de que Daniel pase la primera lista de negocios locales.
Reglas: solo negocios reales verificados, siempre marcado "Con el apoyo de",
nunca disfrazado de contenido editorial.

### 9.4. Instagram y Facebook — publicadores genéricos RSS (Node)

`scripts/publish-instagram.mjs` y `scripts/publish-facebook.mjs`: mismo
patrón, deliberadamente genéricos y configurados por variables de entorno del
workflow para poder copiarse tal cual a madapan.es y gafasvan.com sin tocar
código específico de este proyecto. Leen `feed.xml` (solo investigaciones,
nunca noticias del día a día ni plenos), publican **una pieza por ejecución**,
la más reciente no publicada, y llevan su propio registro
(`instagram-posted.json` / `facebook-posted.json`) para no repetirse.

- **Instagram**: necesita imagen (Meta la descarga de una URL pública, no
  admite solo texto); se resuelve transformando la URL del artículo
  (`/blog/<slug>.html` → `/assets/blog/<slug>.jpg`). Si un artículo no tiene
  imagen (como el homenaje a Mariano Haro, sin foto a propósito — no se
  generan retratos de IA de personas reales), se salta.
- **Facebook**: NO sube ninguna imagen — deja que Facebook arme su propia
  tarjeta leyendo las etiquetas Open Graph del artículo (`og:title`,
  `og:description`, `og:image`, presentes desde 2026-08-24). Si no hay
  imagen, la tarjeta sale sin ella pero con título y descripción (Facebook,
  a diferencia de Instagram, sí admite publicaciones de solo enlace).
- **Bloqueados ambos** por falta de credenciales de Meta (ver §14). El mismo
  Usuario del Sistema de Meta Business Suite sirve para los dos —
  `instagram_content_publish` + `pages_manage_posts` en el mismo token, que
  no caduca (a diferencia de un token de Página normal, ~60 días).

### 9.5. WhatsApp

Planeado, no construido — "queda para fase posterior por coste, permisos,
entregabilidad y riesgo de bloqueo" (`README_PROYECTO.md`). Es el canal de
mayor alcance real entre los mayores, según el propio checklist de
lanzamiento — sigue en la lista de pendientes de creación manual por Daniel.

---

## 10. Coste de la IA y las dos optimizaciones

De `docs/costes-ia.md` (medido 2026-08-01, verificado contra la consola real
de Anthropic).

**Antes:** el build diario costaba del orden de **90-100 $/mes**, porque
`data/cache/` estaba en `.gitignore` y el Action arrancaba en blanco cada
día, volviendo a redactar ~215 textos que no habían cambiado (incluidos
plenos de semanas atrás).

**Las tres optimizaciones aplicadas** (por orden de impacto):

1. **Persistir la caché de IA en el Action** (`actions/cache@v4`, clave
   `ia-cache-${{ github.run_id }}`) — con diferencia la de mayor impacto,
   ~80-90% del gasto. En un día normal solo hay unas pocas noticias nuevas
   que pagar.
2. **Modelo barato para lo mecánico** — `MODELO_MECANICO` (Haiku 4.5) para el
   parte del tiempo y la moderación de comentarios: transformaciones de datos
   a texto sin criterio editorial que proteger.
3. **Esfuerzo bajo en titulares del feed** — `ESFUERZO_BAJO`, ~100 llamadas
   cortas por build.

**La regla que no se rompe:** los textos con juicio editorial
(`redactar_pleno`, `redactar_ayuda`, `redactar_investigacion`,
`redactar_pista`) siguen en el modelo editorial con esfuerzo normal. Ahí es
donde se decide qué se cuenta y cómo — abaratar eso sería ahorrar en lo único
que diferencia al periódico.

**Si hay que volver a medirlo:** los precios oficiales cambian (consultar
Anthropic, no fiarse de cifras pasadas); los tokens se miden con la API de
conteo (gratis), no a ojo; el gasto **real facturado** está en la consola de
Anthropic, es la única fuente de verdad — lo demás es estimación con ±30% de
margen.

---

## 11. Mapa de secretos

De `docs/secretos.md` (el documento **nunca lleva valores**, solo el mapa de
qué existe y dónde se configura — los valores van en el gestor de
contraseñas).

| Secret | Para qué | Dónde | Estado |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Redacción con IA | GitHub Actions · `.env` | ✅ |
| `OPENAI_API_KEY` | Imágenes de portada/banners | `.env` local | ✅ |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Almacenes (fotos, esquelas, archivo, comentarios) | Vercel · GitHub Actions · Railway · `.env` | ✅ |
| `SUPABASE_ANON_KEY` | Acceso de cliente | `.env` local | ✅ |
| `TELEGRAM_BOT_TOKEN` | Bot (fotos, esquelas, chivatazos, boletín, newsletter) | Railway · GitHub Actions · `.env` | ✅ (⚠️ rotación pendiente, ver §14) |
| `TELEGRAM_CHANNEL_ID` | Canal público | Railway · GitHub Actions · `.env` | ✅ |
| `ADMIN_TELEGRAM_ID` | Id numérico de Daniel — notas privadas + envío de newsletter | Railway · GitHub Actions · `.env` | ✅ (añadido 2026-08-25) |
| `MAILERLITE_API_KEY` / `MAILERLITE_GROUP_ID` | Alta en newsletter | Vercel | ✅ — **anotar de qué cuenta de MailerLite es** (bug histórico, ver §12) |
| `META_IG_USER_ID` / `META_IG_ACCESS_TOKEN` | Publicador Instagram | GitHub Actions | ❌ sin configurar |
| `META_FB_PAGE_ID` / `META_FB_ACCESS_TOKEN` | Publicador Facebook | GitHub Actions | ❌ sin configurar |
| `AEMET_API_KEY` | Datos AEMET | `.env` local | ✅ |
| `LLM_PROVIDER` / `LLM_MODEL` | Qué modelo de IA usar | GitHub Actions · `.env` | ✅ |

---

## 12. Trampas ya pagadas — no repetirlas

Bugs reales, encontrados y resueltos en producción, no hipotéticos:

1. **Git rebase dejaba el repo en detached HEAD.** El patrón
   `git pull --rebase origin main || true` en el paso de publicar del build
   tragaba conflictos pero dejaba el repo a medio rebase; el `git push`
   posterior fallaba con "You are not currently on a branch" — **el build
   salía en verde pero la web nunca se publicaba, en silencio.** Ocurrió al
   menos 3 veces (la Action + 2 veces en local). Arreglado con resolución
   explícita de conflictos (`git fetch` + `git rebase` +
   `git checkout --theirs -- web/ data/` ya que los conflictos siempre eran
   en ficheros generados + `--continue` o `--abort` y salir con error).

2. **AI cache no persistida en CI** — ver §10. Reducía el gasto ~5×.

3. **Timeouts silenciosos del build diario.** 3 de 7 builds programados
   cancelados al límite antiguo de 20 min; subido a 40. Una ejecución
   cancelada no avisa por sí sola — hay que mirar la pestaña Actions.

4. **Telegram mandaba siempre las mismas noticias.** Tres bugs distintos,
   encontrados uno tras otro al probar en producción real:
   - Ordenaba por `relevancia()` (score de palabras clave) en vez de por
     fecha → anuncios viejos con muchas keywords siempre ganaban a lo nuevo.
   - Un anuncio BOCyL multi-pueblo contaba como N noticias distintas (una por
     pueblo afectado) → "8 noticias" eran en realidad 3 piezas.
   - Un pueblo con 5 piezas el mismo día monopolizaba todo el boletín →
     arreglado con `MAX_POR_PUEBLO = 2`.

5. **`weather_block()` devolvía `""` si no había dato de tiempo** — pérdida
   silenciosa de contenido. Ahora devuelve un aviso explícito
   ("no podemos darte el tiempo ahora mismo...").

6. **Fichas de municipio huérfanas.** La lista de slugs a regenerar era
   dinámica (pilotos + pueblos con noticia HOY), así que un pueblo que
   apareció una vez en el BOP dejaba de regenerarse en cuanto no tenía más
   noticias ese día — página congelada para siempre (8 páginas encontradas,
   la más vieja de 6 semanas atrás, sin bloque de tiempo ni avisos de
   privacidad actuales). Arreglado uniendo `ya_publicados` (páginas ya
   existentes en `web/municipio/`) a la lista de slugs — la cobertura solo
   crece, nunca se encoge.

7. **Popup de suscripción con el campo de email de 200px de ALTO en móvil.**
   `flex: 1 1 200px` se interpretaba en el eje vertical al cambiar el
   formulario a `flex-direction: column` en el breakpoint móvil. Arreglado
   con `flex: 0 0 auto; width: 100%` explícito dentro del media query.

8. **MailerLite 422 "grupo inválido"** — no era un problema de ID de grupo,
   sino que la `MAILERLITE_API_KEY` de Vercel pertenecía a **otra cuenta**
   distinta de la que se estaba mirando. Síntoma: los suscriptores
   "desaparecen".

9. **Suscriptor "unconfirmed" con doble opt-in** — no es un bug, es el
   comportamiento esperado hasta que la persona pincha el enlace de
   confirmación; hasta entonces la secuencia de bienvenida no se dispara.

10. **Scraper de plenos de Mayorga fallaba en CI** ("aviso: sin actas de
    pleno para Mayorga") porque la sede electrónica es JS-heavy y faltaba
    Playwright instalado en el runner de GitHub Actions. Arreglado con
    `playwright install --with-deps chromium` como paso del workflow.

11. **Portadas de investigación (1024×1024, ~2MB) demasiado pesadas para un
    email** — `empaquetar_newsletter.py` las reescala a 536px antes de
    meterlas en el zip.

**Trampas conocidas de la integración con Meta (Instagram/Facebook), aunque
aún no aplicadas por falta de credenciales — documentadas en
`docs/instagram.md`/`docs/facebook.md` para cuando se desbloqueen:** el token
va SIEMPRE en la cabecera `Authorization: Bearer`, nunca en el JSON (la
documentación de Meta induce a error); tras crear el contenedor de Instagram
hay que sondear `status_code` hasta `FINISHED` antes de publicar (publicar
inmediatamente falla); un token de Página caduca a los ~60 días, usar
Usuario del Sistema.

---

## 13. Estado actual (cifras reales)

Verificado contra el sistema en producción a 2026-08-26, no una estimación:

| Cifra | Valor |
|---|---|
| Fichas de municipio activas | **32** |
| Provincias cubiertas | 4 (Palencia, Valladolid, León, Zamora) |
| Secciones editoriales | 9 |
| Fuentes/scrapers automatizados | 14 |
| Investigaciones largas publicadas | **6** |
| Build diario | 24/7 en GitHub Actions, ~20-25 min, en verde las últimas 10 ejecuciones |
| Coste de IA | por debajo de 1 €/día (partía de 90-100 €/mes antes de optimizar) |
| Vercel Analytics | **activado** (comprobado con datos reales: 12 visitantes / 12 pageviews la semana del 18-25 ago) |
| Newsletter — secuencia de bienvenida | funcionando de punta a punta, probada con suscripción real |
| Newsletter — investigaciones nuevas | funcionando, probado de punta a punta (zip → Telegram → import manual en MailerLite) |
| Instagram / Facebook | cuentas creadas, publicadores construidos y probados en dry-run, **bloqueados por falta de credenciales de Meta** |
| Radar de pistas | activo, decenas de pistas pendientes en cola en cada momento (cifra cambia a diario, no se fija aquí) |

---

## 14. Pendiente activo

Por prioridad:

1. **Credenciales de Meta (Instagram + Facebook).** Falta crear en Meta
   Business Suite un Usuario del Sistema con `instagram_content_publish` +
   `pages_manage_posts`, y sacar `META_IG_USER_ID` / `META_FB_PAGE_ID`. Sin
   esto los dos publicadores ya construidos no pueden hacer nada. Guía paso a
   paso en `docs/instagram.md` y `docs/facebook.md`.
2. **Rotar el token del bot de Telegram** — estuvo expuesto un momento en
   logs de Railway hace tiempo; sigue en la lista de checklist de
   lanzamiento sin marcar. Vía @BotFather → `/revoke`.
3. **Tablón de comentarios de Telegram** — programado pero no encendido
   (falta vincular el grupo de discusión y sacar el `chat_id`).
4. **Contenido que necesita criterio local de Daniel, no código:**
   - Agenda "Dónde encontrarse" de la sección Acompañar (`docs/acompanar.md`)
     — hogares del jubilado, actividades de CEAS por pueblo.
   - Primera entrevista de "Gente de Campos".
   - Semilla del archivo fotográfico.
   - Primera lista de anunciantes locales para el banner de publicidad
     (`docs/publicidad.md`).
   - Pacto con una funeraria de la comarca para agilizar las esquelas.
5. **Fase 2 de Acompañar** — red de acompañamiento con protocolo (Cruz Roja
   "Siempre Acompañados" o Amigos de los Mayores); requiere un socio externo,
   el periódico solo recluta y da visibilidad, nunca gestiona el trato
   directo.
6. **Replicar Instagram/Facebook en madapan.es y gafasvan.com** — los
   scripts ya son genéricos y están listos para copiarse; falta el feed URL
   e imagen-por-artículo de cada sitio (`INSTAGRAM-RSS-SETUP.md`).
7. **6 hallazgos de usabilidad sin cerrar** (de 25 originales, 19 ya
   corregidos): buscador/search, cabecera fija, manejo de secciones vacías
   (Esquelas, Archivo, Gente de Campos, directorio de negocios) — dejados
   deliberadamente como decisión editorial de Daniel, no fallos técnicos.
8. **WhatsApp** — canal sin crear todavía (ver §9.5).

**Explícitamente descartado, no pendiente:** replicar el sistema completo de
generación-por-PR de Gafasvan (Astro + PR de revisión + auto-merge) en este
repo — decisión consciente de no duplicar el generador de investigaciones que
ya existe aquí en Python, para no romper la regla de "todo Python salvo
publicadores de redes" de `CLAUDE.md`.

---

## 15. Cómo se trabaja en este repo

De `CLAUDE.md` — el repo se toca desde varios equipos Windows distintos:

- Al empezar sesión: `git fetch origin` + `git pull --rebase origin main`
  antes de tocar código. Si hay cambios locales sin commitear, avisar
  primero.
- Si hay conflictos, parar y mostrarlos — nunca resolverlos a ciegas.
- Al terminar una tarea: `git add -A` (o específico), commit descriptivo en
  español, `git push`, y **confirmar que el push ha funcionado**.
- Nunca commitear `node_modules`, `.env`, `dist` ni `build`.
- **No hay suite de tests.** La verificación es: `--dry-run` del scraper
  tocado, o un build completo mirando los `aviso:` del log.

### Comandos más usados

```bash
python -m sitegen.build                       # regenera TODO el sitio (~8-20 min)
python -m scrapers.<nombre> --dry-run          # prueba un scraper aislado
python -m bot.telegram_bot                     # bot en local — ¡parar antes el de Railway!

python -m scripts.revisar_esquelas             # obligatorio antes de publicar una esquela
python -m scripts.revisar_fotos
python -m scripts.revisar_archivo
python -m scripts.listar_chivatazos
python -m scripts.leer_notas

python -m scripts.generar_articulo_blog --tema <tema>
python -m scripts.desarrollar_pista --listar
python -m scripts.detectar_anomalias
python -m scripts.empaquetar_newsletter --auto  # lo que corre solo en el build diario

node scripts/publish-instagram.mjs --dry-run
node scripts/publish-facebook.mjs --dry-run
```

---

## 16. Documentación de referencia

Todo vive en `docs/` salvo lo indicado. Un mapa de qué mirar según la
pregunta:

| Pregunta | Documento |
|---|---|
| ¿Qué es el proyecto y qué NO se construye en el MVP? | `README_PROYECTO.md` |
| ¿Qué reglas editoriales hay? | `editorial/politica_editorial.md` |
| ¿Cómo debe sonar un texto? | `docs/voz-editorial.md` |
| ¿Qué secciones hay y qué cubre cada una? | `docs/secciones-editoriales.md` |
| ¿Cuánto cuesta la IA y por qué? | `docs/costes-ia.md` |
| ¿Cómo funciona la newsletter (bienvenida + investigaciones)? | `docs/newsletter.md` |
| ¿Cómo publica en Instagram / Facebook? | `docs/instagram.md` / `docs/facebook.md` |
| ¿Qué hace la sección Acompañar y cómo se diseñó? | `docs/acompanar.md` |
| ¿Cómo funciona el banner de anunciantes? | `docs/publicidad.md` |
| ¿Dónde está cada secreto y en qué máquina? | `docs/secretos.md` |
| Checklist de lanzamiento, qué queda | `docs/lanzamiento.md` |
| Estudio de fuentes/viabilidad original | `docs/estudio-fuentes-y-viabilidad.md` |
| Backlog de ideas | `docs/ideas-blog.md`, `docs/ideas-mundo.md` |
| Guía de marca completa | `editorial/sistema_marca_v1_2/`, `brand/` |
| Cómo opera el bot de Telegram | `bot/README.md` |

---

*Este documento se mantiene a mano — no lo regenera ningún build. Si algo de
aquí queda desactualizado, es responsabilidad de quien haga el siguiente
cambio grande actualizarlo, igual que con `CLAUDE.md`.*
