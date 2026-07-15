# Bot de Telegram — El Terracampino

Recibe fotos de vecinos por Telegram, las procesa (recorte + marco de marca) y les pone
pie de foto con IA. Las fotos quedan **pendientes de revisión**, no se publican solas.

## 1. Crear el bot (una sola vez, lo hace una persona con cuenta de Telegram)

1. Abre Telegram, busca **@BotFather**, escríbele `/newbot`.
2. Dale un nombre visible (ej. `El Terracampino`) y un usuario único acabado en `bot`
   (ej. `ElTerracampinoBot`).
3. BotFather te da un **token** tipo `123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.
   Guárdalo — es la contraseña del bot, no lo compartas en ningún sitio público.
4. Pon el token en `.env` (en la raíz del repo, ese fichero está en `.gitignore` — nunca
   se sube al repo):

   ```
   TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

## 2. Arrancar el bot

```
pip install -r requirements.txt
python -m bot.telegram_bot
```

Tiene que quedarse corriendo (no es un script de una vez, como los `scrapers/*.py` —
es un proceso que escucha mensajes todo el rato). Para probarlo en local basta con
dejarlo corriendo en una terminal; para que funcione de verdad para los vecinos hace
falta que corra en algún sitio siempre encendido (un servidor pequeño, p.ej. Railway,
que ya tienes conectado a este proyecto — pendiente de decidir cuándo desplegarlo ahí).

## 3. Cómo funciona para quien manda la foto

1. Le escribe al bot `/foto`.
2. El bot le pregunta de qué pueblo es (botones con los 12 pilotos).
3. Manda la foto (puede añadir un texto explicando qué es — la IA lo usa para el pie
   de foto, no inventa lo que no se ve en la imagen ni lo que no le han contado).
4. El bot confirma que la ha recibido y que queda pendiente de revisión.

## 4. Revisar y publicar

```
python -m scripts.revisar_fotos
```

Te enseña cada foto pendiente (la abre con el visor de imágenes del sistema), el pie
de foto que propuso la IA, y te deja aprobarla (puedes editar el pie antes), rechazarla,
o dejarla para más tarde. Las aprobadas aparecen en la ficha del pueblo correspondiente
en la siguiente vez que se ejecute `python -m sitegen.build`.

## 5. Publicar un artículo de blog en el canal de Telegram

```
python -m scripts.generar_articulo_blog --tema despoblacion
```

Redacta el artículo largo con IA, genera la imagen de portada (si hay `OPENAI_API_KEY`
real) y, si además hay `TELEGRAM_CHANNEL_ID` en `.env`, avisa en el canal con titular +
entradilla + enlace. Para tener el `TELEGRAM_CHANNEL_ID`:

1. Crea el canal en Telegram (aparte del bot) y hazlo público con un `@usuario`.
2. Añade el bot como administrador del canal (Ajustes del canal → Administradores).
3. El `TELEGRAM_CHANNEL_ID` es ese `@usuario` tal cual (con la arroba), por ejemplo:

   ```
   TELEGRAM_CHANNEL_ID=@elterracampino
   ```

Si no está puesto (o sigue en `replace_me`), el artículo se genera y publica en la web
igual, solo que no se avisa en ningún canal.

## Pendiente / fuera de este alcance todavía

- **Canal de difusión diaria** (tiempo/noticias del día a día, no solo los artículos de
  blog): el bot de arriba recibe fotos y el punto 5 publica artículos largos, pero
  publicar automáticamente el resumen diario de cada pueblo en su canal es una pieza
  aparte, sin construir todavía.
- **Facebook**: crear la Página de El Terracampino es un paso manual (Meta no permite
  automatizarlo) — pendiente de que la crees. La publicación automática en Facebook
  necesita además que Meta apruebe la app (revisión que puede tardar días), así que
  conviene empezar publicando ahí a mano con lo que genere este bot, no automatizarlo
  desde el primer día.
- **Dónde vive el bot 24/7**: en local solo funciona mientras tengas la terminal
  abierta. Para producción hace falta desplegarlo (Railway es la opción más a mano,
  ya conectada a este proyecto).
