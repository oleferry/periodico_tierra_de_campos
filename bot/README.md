# Bot de Telegram — El Terracampino

Recibe fotos de vecinos por Telegram (@Elterracampinobot), las procesa (recorte +
marco de marca) y les pone pie de foto con IA. Las fotos quedan **pendientes de
revisión** en Supabase Storage, no se publican solas.

**Estado: DESPLEGADO en Railway (proyecto `elterracampino-bot`, servicio `bot`)
desde el 2026-07-18.** Corre 24/7; no depende de ningún ordenador encendido.

## Arquitectura (por qué Supabase en medio)

```
vecino → @Elterracampinobot (Railway) → Supabase Storage (bucket 'fotos', privado)
                                              │  pendientes/<id>.jpg + .json
   revisor (portátil) ── scripts/revisar_fotos.py ──┤
                                              │  aprobadas/<id>.jpg + .json
   web ── python -m sitegen.build ── descarga aprobadas → web/assets/fotos/
```

El disco de Railway es efímero (se borra en cada redespliegue) y la revisión y
el build corren en otra máquina — por eso las fotos viven en Supabase
(`sitegen/almacen_fotos.py`), un objeto por foto para que dos envíos
simultáneos no se pisen. El bucket es privado: nada es público hasta aprobarse.

El bot hace además un **latido diario contra Supabase** para que el plan
gratuito no pause el proyecto por 7 días de inactividad (pasó el 2026-07-17).

## Variables de entorno (en Railway, servicio `bot`)

```
TELEGRAM_BOT_TOKEN          token de @BotFather
TELEGRAM_CHANNEL_ID         @elterracampino (avisos de artículos; opcional)
SUPABASE_URL                proyecto de Supabase
SUPABASE_SERVICE_ROLE_KEY   clave service_role (solo servidor, nunca en repo)
ANTHROPIC_API_KEY           pies de foto con IA
```

Las mismas van en el `.env` local (gitignorado) para revisión y build.

## Operar el bot

- **Redesplegar tras cambiar código**: `railway up --detach --project 2b6aad7c-25fe-4e15-bcac-1f865d264542 --environment 36605291-eed7-4a4d-9cb8-6e39e7a1b068 --service bot` (respeta `.railwayignore`; el arranque lo define `railway.json`: `python -m bot.telegram_bot`, deps de `bot/requirements.txt`).
- **Ver logs**: `railway logs --service bot ...` (mismos flags). httpx está
  silenciado a WARNING a propósito: a nivel INFO escribía el token del bot en
  cada línea de log.
- **Probar en local**: `python -m bot.telegram_bot` — ¡OJO! para el servicio de
  Railway antes (dos instancias con el mismo token entran en conflicto de
  long-polling y Telegram da 409).

## Flujo del vecino

1. Le escribe a @Elterracampinobot: `/foto`.
2. El bot pregunta el pueblo (botones con los 12 pilotos).
3. Manda la foto (con texto opcional — la IA lo usa para el pie, no inventa).
4. El bot confirma que queda pendiente de revisión.

## Revisar y publicar (en el portátil)

```
python -m scripts.revisar_fotos     # aprueba/edita pie/descarta, una a una
python -m sitegen.build             # las aprobadas aparecen en su ficha
```

## Publicar un artículo de blog en el canal

`python -m scripts.generar_articulo_blog --tema <tema>` avisa solo en el canal
@elterracampino (el bot es administrador con permiso de publicar — verificado).

## Pendiente / fuera de alcance

- **Canal de difusión diaria** (tiempo/noticias del día a día): sin construir.
- **Facebook**: crear la Página es manual (Meta no lo permite automatizar);
  la publicación automática necesita revisión de app de Meta — empezar a mano.
