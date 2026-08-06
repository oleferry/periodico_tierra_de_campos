# Publicación automática en Instagram

Cada investigación nueva del blog se publica sola en **@elterracampino**, con su
imagen y su titular. Lo hace un GitHub Action, igual que el build diario: no
depende de que haya ningún ordenador encendido.

**Publicador genérico dirigido por RSS** (`scripts/publish-instagram.mjs`, Node):
el mismo script sirve para varios sitios (elterracampino.es, y en el futuro
madapan.es / gafasvan.com), configurado por variables de entorno en el
workflow — no lee nada específico de este proyecto, solo el feed RSS público.

## Cómo funciona

```
build diario (06:10 UTC) → la web publica el artículo, su imagen y feed.xml
        ↓
Action "Instagram (mjs)" (lunes 08:15 UTC) → lee el feed, elige el más
        reciente con imagen que no esté ya publicado
        ↓
Graph API v21.0: 1) crear contenedor con image_url  2) media_publish
```

- **Una publicación por ejecución**, la más reciente del feed que tenga imagen
  utilizable y no esté ya en el registro.
- El feed (`feed.xml`) solo trae las **investigaciones**, no las noticias del
  día a día ni los plenos — igual que el resto de la difusión en redes.
- **Instagram descarga la imagen de una URL pública** (no se sube el fichero).
  Como el feed no incluye `<enclosure>`, se deriva la imagen transformando el
  `<link>` del artículo: `.../blog/<slug>.html` → `.../assets/blog/<slug>.jpg`
  (`IG_IMAGE_MODE=template` + `IG_IMAGE_REPLACEMENTS`). El script comprueba la
  imagen con `HEAD` antes de llamar a Meta; si no existe, salta ese artículo y
  prueba el siguiente.
- **Los artículos sin imagen se saltan automáticamente** — es el caso del
  homenaje a Mariano Haro, publicado sin foto a propósito (no se generan
  retratos de IA de personas reales). Instagram no admite publicaciones de
  solo texto.
- El pie usa el **titular y la descripción ya escritos y revisados** del propio
  feed — no se redacta nada nuevo ni se inventa.

## Credenciales (secrets del repo)

| Secret | Qué es |
|---|---|
| `META_IG_USER_ID` | Id de la cuenta de Instagram (se saca con `GET /{PAGE_ID}?fields=instagram_business_account`) |
| `META_IG_ACCESS_TOKEN` | Token con permiso `instagram_content_publish` |

**⚠️ Estado a 2026-08-06: estos dos secrets NO están configurados todavía.**
Sin ellos el workflow falla en el paso de publicar (no en el de leer el feed).
Requisitos de la cuenta: **Profesional** (Empresa o Creador) y **vinculada a la
Página de Facebook**. Con la app de Meta en modo desarrollo basta, siempre que
seas administrador de ambas — no hace falta revisión de Meta para publicar en
cuentas propias.

**Sobre la caducidad del token** (el fallo más típico de estas automatizaciones):
un token de Página de larga duración caduca a los ~60 días y entonces el Action
empieza a fallar en silencio salvo por la ejecución en rojo. Lo recomendable es
un **token de Usuario del Sistema** (Meta Business Suite → Configuración →
Usuarios del sistema), que no caduca.

## Configuración del sitio (bloque `env:` del workflow)

Ya está puesta para elterracampino.es en
`.github/workflows/instagram-publish.yml`:

| Variable | Valor de este sitio |
|---|---|
| `FEED_URL` | `https://elterracampino.es/feed.xml` |
| `IG_IMAGE_MODE` | `template` |
| `IG_IMAGE_REPLACEMENTS` | `[["/blog/","/assets/blog/"],[".html",".jpg"]]` |
| `IG_CTA` | "Lo contamos entero en elterracampino.es — enlace en la bio." |
| `IG_HASHTAGS` | `#TierraDeCampos #Palencia #Valladolid #León #Zamora #EspañaVaciada #PueblosDeEspaña` |

Para replicar el publicador en otro sitio (madapan.es, gafasvan.com): copiar
`scripts/publish-instagram.mjs` y `scripts/instagram-posted.json` (con `[]`), y
un workflow con su propio `FEED_URL` + secrets de esa cuenta. Si el feed de ese
sitio sí trae `<enclosure>`, usar `IG_IMAGE_MODE=enclosure` en vez de
`template`; si cada artículo tiene su propio `og:image`, usar `IG_IMAGE_MODE=og`.

## Operar

```
node scripts/publish-instagram.mjs --dry-run     # qué publicaría, sin publicar
node scripts/publish-instagram.mjs               # publica una
```

- **Lanzarlo a mano**: pestaña Actions → "Instagram (mjs)" → *Run workflow*
  (tiene una casilla `dry_run` para probar sin publicar).
- **Cron**: lunes 08:15 UTC (~10:15 verano / ~09:15 invierno), tras el build
  diario. GitHub programa en UTC, así que la hora local se desplaza una hora
  entre estaciones.
- **Registro de lo publicado**: `scripts/instagram-posted.json` (array de
  guids — la URL del artículo), se commitea desde el propio workflow. Sin él
  se republicaría lo mismo en cada ejecución.

## Qué NO hace

- No publica las noticias del día a día ni los plenos, solo lo que hay en el
  feed RSS (las investigaciones).
- No publica stories ni carruseles, solo una imagen.
- No responde comentarios ni mensajes.
