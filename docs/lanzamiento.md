# Lanzamiento de El Terracampino — checklist

Estado a 2026-07-27. El producto está construido y desplegado; lo que queda no
es código, es ponerlo en marcha de cara al público y que la gente lo encuentre.
Ordenado por prioridad. Marca `[x]` según lo vayas cerrando.

Leyenda: 🟢 lo puedes hacer tú en minutos · 🔧 requiere una acción técnica ·
✍️ material ya preparado más abajo · 💶 tiene coste.

---

## 1. Antes de anunciar nada (que la web esté redonda para el visitante nuevo)

- [ ] 🔧 **Confirmar que MailerLite tiene el dominio verificado.** Quedó el
  registro DKIM (CNAME `litesrv._domainkey`) puesto en Dondominio; entra en
  MailerLite → dominios → "Check status" y comprueba que sale verificado. Sin
  esto, los correos de la newsletter pueden ir a spam.
- [ ] 🔧 **Montar la automatización de bienvenida en MailerLite.** Automations →
  Create workflow → disparador "Subscriber joins group" → un email por
  reportaje con 3-4 días de espera, en orden (los 3 de `docs/newsletter.md`).
- [ ] 🟢 **Activar Vercel Analytics.** En el proyecto `periodico-tierra-de-campos`
  (team gafasvan) → pestaña Analytics → Enable. El código ya está puesto.
- [ ] 🟢 **Pulsar "Run now" en las tareas programadas** (barra lateral →
  Scheduled) al menos una vez en `build-diario`, para pre-aprobar el permiso de
  `git push` y que las siguientes ejecuciones no se queden paradas.

## 2. Redes sociales (crearlas tú; el material está en la sección 5)

- [x] 🟢✍️ **Facebook** — CREADA y enlazada en el pie de la web
  (`facebook.com/profile.php?id=61592649658185`). Pendiente: asignar el nombre de
  usuario `@elterracampino` cuando Meta lo permita (y avisar para actualizar el
  enlace a la URL limpia).
- [ ] 🟢✍️ **Canal de WhatsApp** — la de mayor alcance real entre los mayores.
  Se crea desde la propia app de WhatsApp (pestaña Novedades → +).
- [x] 🟢✍️ **Instagram** — CREADA y enlazada (`instagram.com/elterracampino`).
  Imagen de lanzamiento (el palomar) y texto de primer post ya preparados.
- [ ] 🟢✍️ **X (Twitter)** — para más visibilidad y alcance (periodistas, cuentas
  de la España vaciada, difusión rápida). Usuario `@elterracampino`. Foto = logo,
  cabecera = un paisaje de la comarca; bio de la sección 5; enlace a
  elterracampino.es.
- [ ] 🔧 **Conectar el feed RSS a Facebook (y a X) con Zapier.** RSS by Zapier
  (`https://elterracampino.es/feed.xml`) → Facebook Pages "Create Page Post" y, con
  otro Zap, → X "Create Tweet". Así las investigaciones se publican solas. Zapier
  ya tiene sus apps aprobadas; solo autorizas tus cuentas.

## 3. Automatismos que ya funcionan pero dependen de una acción tuya

- [ ] 🔧 **Rotar el token del bot de Telegram.** Estuvo un momento en los logs de
  Railway. En @BotFather → /revoke → genera uno nuevo → cámbialo en el `.env`
  local y en las variables del servicio de Railway.
- [ ] 🔧 **Tablón de comentarios de Telegram** (ya está programado, falta
  encenderlo): Ajustes del canal → Discusión → crear/vincular grupo; añade el
  bot; en @BotFather /setprivacy → Disable; manda un mensaje al grupo, copia el
  `chat_id` que deja en los logs de Railway y ponlo como
  `TELEGRAM_DISCUSSION_CHAT_ID`.

## 4. Recomendaciones (no urgentes, mejoran el lanzamiento)

- [ ] 🔧 **Fiabilidad del build diario.** Ahora `build-diario` solo corre si
  tienes la app de Claude Code abierta en el portátil. Para un medio ya lanzado
  conviene moverlo a un GitHub Action (cron en el servidor de GitHub, que hace
  push y Vercel despliega solo) — así la web se actualiza aunque el portátil
  esté apagado. El bot de Telegram sí está 24/7 en Railway; esto es solo para el
  build del sitio. Dímelo y lo monto.
- [ ] 💶 **Pacto con una funeraria de la comarca** para las esquelas: que te
  pasen los avisos. Es lo que hace despegar esa sección (la más visitada de la
  prensa local), en vez de depender de que la familia encuentre el formulario.
- [ ] ☎️ **Ronda telefónica del directorio**: confirmar los ~35 negocios
  "dudosos" y cerrar las discrepancias de datos que quedaron sin tocar.
- [ ] 🖼️ **Sembrar el archivo y Gente de Campos.** Ambas secciones están
  vacías. Un puñado de fotos antiguas tuyas o de conocidos, y una primera
  entrevista (que redactamos juntos), les dan vida para el día del lanzamiento.

---

## 5. Material de redes, listo para copiar y pegar

**Nombre de usuario en todas (si está libre):** `elterracampino`
(coincide con el canal de Telegram `t.me/elterracampino` y el dominio).

**Foto de perfil:** el logo (pastor + oveja + espiga), en
`brand/logos/`. **Portada/cabecera:** un paisaje de campos de la comarca.

### Biografía corta (Instagram, WhatsApp — ~150 caracteres)

> El periódico de los pueblos de Tierra de Campos. El tiempo, las noticias y las
> historias de tu pueblo, contadas claro. 🌾 elterracampino.es

Versión sin emoji, por si prefieres el tono más sobrio del proyecto:

> El periódico de los pueblos de Tierra de Campos. El tiempo, las noticias y las
> historias de tu pueblo, contadas claro. elterracampino.es

### Facebook — descripción de la Página

> El Terracampino es el periódico de la comarca de Tierra de Campos. Contamos lo
> que pasa en cada pueblo —el tiempo, los plenos, las ayudas, el fútbol, las
> fiestas y las historias de siempre— con la fuente al lado y sin ruido de
> fuera. Para quien vive aquí y para quien se fue pero no olvida.
>
> Web: elterracampino.es · Telegram: t.me/elterracampino

### Canal de WhatsApp — descripción

> Lo que pasa en los pueblos de Tierra de Campos, directo al móvil. El tiempo,
> las noticias del día, las esquelas y alguna historia de aquí. Un par de
> mensajes al día, sin agobiar.

### Primer post / mensaje fijado (para las tres)

> Arrancamos. **El Terracampino** es el periódico de los pueblos de Tierra de
> Campos: el tiempo de tu pueblo cada día, los plenos y las ayudas en limpio, el
> fútbol de la comarca, las leyendas, las esquelas y las fotos de siempre.
>
> Todo está en 👉 elterracampino.es, y elijas el pueblo que elijas, tiene su
> propia página.
>
> Si eres de aquí —o te fuiste pero sigues siendo—, este periódico es tuyo.
> Cuéntanos lo que pasa en tu pueblo, mándanos una foto antigua o el aviso de un
> fallecimiento: se hace entre todos.

### Ideas de contenido para las primeras semanas (para no quedarse en blanco)

- La foto antigua de la semana ("¿reconoces la plaza? ¿de qué año es?").
- El parte del tiempo del finde, con la coletilla de huerta.
- Cada investigación nueva (la del blog) — esto Facebook lo publica solo vía
  Zapier.
- "Gente de Campos" cuando haya el primer perfil.
- El precio del cereal los viernes (día de lonja) para el público agrario.
- Una leyenda por pueblo, ilustrada con su foto de cabecera.

---

*Recordatorio: no puedo crear las cuentas por ti (son tu identidad y tus
credenciales). Este documento es para que hacerlo te lleve un rato. Cuando las
tengas creadas, dime los nombres de usuario finales y actualizo los enlaces del
pie de la web y los botones para que apunten a ellas.*
