# Publicación automática en Facebook

Cada investigación nueva del blog se publica sola en la Página de Facebook de
El Terracampino, con enlace directo al artículo. Lo hace un GitHub Action,
igual que el build diario y que el publicador de Instagram: no depende de que
haya ningún ordenador encendido.

**Publicador genérico dirigido por RSS** (`scripts/publish-facebook.mjs`,
Node): mismo patrón que `scripts/publish-instagram.mjs` — el mismo script vale
para varios sitios, configurado por variables de entorno en el workflow, sin
leer nada específico de este proyecto salvo el feed RSS público.

## Cómo funciona

```
build diario (06:10 UTC) → la web publica el artículo y feed.xml
        ↓
Action "Facebook (mjs)" (lunes 08:30 UTC) → lee el feed, elige el más
        reciente que no esté ya publicado
        ↓
Graph API v21.0: POST /{PAGE_ID}/feed  { message, link }  (un solo paso)
```

- **Una publicación por ejecución**, la más reciente del feed que no esté ya
  en el registro.
- El feed (`feed.xml`) solo trae las **investigaciones**, no las noticias del
  día a día ni los plenos — igual que el resto de la difusión en redes.
- **A diferencia de Instagram, aquí NO se resuelve ni se sube ninguna
  imagen.** Facebook arma su propia tarjeta de previsualización descargando el
  `link` y leyendo sus etiquetas Open Graph (`og:title`, `og:description`,
  `og:image`), que ya lleva cada artículo de blog desde el 2026-08-24
  (`sitegen/build.py:shell`, parámetros `url`/`image`/`og_title`, usados por
  `render_blog_articulo`). Si un artículo no tiene imagen (como el homenaje a
  Mariano Haro, publicado sin foto a propósito), la tarjeta sale sin imagen
  pero con título y descripción — Facebook, a diferencia de Instagram, sí
  admite publicaciones de solo enlace/texto.
- El mensaje usa el **titular y la descripción ya escritos y revisados** del
  propio feed, más un `FB_CTA` opcional — no se redacta nada nuevo ni se
  inventa. A propósito no se repite la URL como texto: el parámetro `link` ya
  hace que Facebook pinte la tarjeta clicable, y repetirla suele duplicar el
  enlace visible en el post.
- **Registro aparte del de Instagram**: `scripts/facebook-posted.json` (mismo
  formato, array de guids), porque cada plataforma puede llevar su propio
  ritmo de publicación.

## Credenciales (secrets del repo)

| Secret | Qué es |
|---|---|
| `META_FB_PAGE_ID` | Id numérico de la Página de Facebook (se saca con `GET /me/accounts` usando un token de usuario admin de la Página) |
| `META_FB_ACCESS_TOKEN` | Token de Página (Page Access Token) con permiso `pages_manage_posts` |

**⚠️ Estado a 2026-08-24: estos dos secrets NO están configurados todavía**
(mismo punto que bloquea hoy Instagram). Sin ellos el workflow falla en el
paso de publicar.

**No hace falta un trámite aparte del de Instagram.** El Usuario del Sistema
de Meta Business Suite que ya hace falta montar para Instagram
(`docs/instagram.md`) puede llevar TAMBIÉN el permiso `pages_manage_posts`
sobre esta misma Página — solo hay que añadirle ese permiso y generar el
token una vez, con los dos scopes a la vez. Un token de Usuario del Sistema no
caduca, a diferencia de un token de Página normal (~60 días).

## Configuración del sitio (bloque `env:` del workflow)

Ya está puesta para elterracampino.es en
`.github/workflows/facebook-publish.yml`:

| Variable | Valor de este sitio |
|---|---|
| `FEED_URL` | `https://elterracampino.es/feed.xml` |
| `FB_CTA` | "Lo contamos entero, con las fuentes, en elterracampino.es" |

Para replicar el publicador en otro sitio (madapan.es, gafasvan.com): copiar
`scripts/publish-facebook.mjs` y `scripts/facebook-posted.json` (con `[]`), y
un workflow con su propio `FEED_URL` + secrets de esa Página. Solo hace falta
que las páginas del feed traigan etiquetas Open Graph propias — si el sitio no
las tiene, Facebook arma una tarjeta genérica sin imagen ni título útil.

## Operar

```
node scripts/publish-facebook.mjs --dry-run     # qué publicaría, sin publicar
node scripts/publish-facebook.mjs               # publica una
```

- **Lanzarlo a mano**: pestaña Actions → "Facebook (mjs)" → *Run workflow*
  (tiene una casilla `dry_run` para probar sin publicar).
- **Cron**: lunes 08:30 UTC, quince minutos después del de Instagram (para no
  lanzar los dos a la vez contra la API de Meta, aunque son independientes).
- **Registro de lo publicado**: `scripts/facebook-posted.json` (array de
  guids — la URL del artículo), se commitea desde el propio workflow. Sin él
  se republicaría lo mismo en cada ejecución.

## Qué NO hace

- No publica las noticias del día a día ni los plenos, solo lo que hay en el
  feed RSS (las investigaciones).
- No sube fotos ni carruseles, solo enlaces con tarjeta de previsualización.
- No responde comentarios ni mensajes.
