# Newsletter (MailerLite)

**Estado: FUNCIONANDO de punta a punta, probado con una suscripción real el
2026-08-01.** Cadena completa: popup/formulario → `/api/suscribir` (Vercel) →
MailerLite → grupo "El Terracampino" → doble opt-in → secuencia de bienvenida.

## Qué hay construido

- **Formulario cableado** en la web (el del pie de portada y el popup): hacen
  POST a `/api/suscribir` con validación, honeypot anti-bots y mensaje de
  éxito/error. El popup sale una vez por visitante (localStorage), a los 3s.
- **Función serverless** `web/api/suscribir.js` (Vercel): habla con la API de
  MailerLite EN SERVIDOR — la clave nunca toca el navegador. Si la clave no
  está configurada responde "inténtalo más tarde" y la web no se rompe.
- **Variables en Vercel**: `MAILERLITE_API_KEY` y `MAILERLITE_GROUP_ID`. Tras
  cambiar cualquiera hay que **redesplegar** para que la función las coja.
- **Autenticación del dominio verificada** (2026-08-01): SPF
  (`include:_spf.mlsend.com`), DKIM (CNAME `litesrv._domainkey` → mlsend, clave
  válida) y DMARC (`p=none` con informes). Los tres comprobados por DNS.

## Dos trampas que costaron horas (no volver a caer)

1. **Un 422 "The selected groups is invalid" NO suele ser el group id**: era que
   la `MAILERLITE_API_KEY` de Vercel pertenecía a **otra cuenta** de MailerLite
   distinta de la que se estaba mirando. La clave y el grupo tienen que ser de
   la MISMA cuenta. Síntoma delator: los suscriptores "desaparecen" (se crean
   en la otra cuenta) y cualquier grupo nuevo sale inválido.
2. **Con doble opt-in, un alta por API queda "unconfirmed"** y no aparece en la
   vista por defecto de Subscribers hasta que la persona pincha el enlace del
   correo. No es un fallo, y hasta ese momento **la secuencia no se dispara**.

## La secuencia de bienvenida — TEXTO LISTO PARA PEGAR (act. 2026-07-27)

Lo que pidió Daniel: al suscribirse, el lector entra en un bucle que le manda
los reportajes ya publicados **en orden, desde el primero**. Se configura a mano
en MailerLite (su API no crea automatizaciones):

MailerLite → **Automations → Create workflow** → disparador **"subscriber joins
group"** (el grupo del apartado anterior) → un email por paso, con **3-4 días de
espera** entre cada uno. El paso 0 (bienvenida) sale nada más suscribirse; los
demás, con su espera.

Cada correo es un teaser corto que lleva a la web (el reportaje entero se lee
allí, no en el email). Pega el **asunto**, el **preheader** (texto de vista
previa) y el **cuerpo**; el enlace ponlo como botón hacia la URL indicada.

---

### Paso 0 — Bienvenida (inmediato, al suscribirse)

**Asunto:** Bienvenido a El Terracampino
**Preheader:** El periódico de tu pueblo. Esto es lo que vas a recibir.

> Gracias por suscribirte. El Terracampino es el periódico de los pueblos de
> Tierra de Campos: el tiempo de tu pueblo cada día, los plenos y las ayudas en
> limpio, el campo, las esquelas y las historias de siempre.
>
> Una vez por semana te llegará lo que pasa cerca, contado claro. Y estos días,
> además, te iremos mandando —uno a uno— los reportajes que ya hemos publicado,
> empezando por el primero. Son investigaciones con datos oficiales y la fuente
> siempre al lado.
>
> Mientras tanto, tu pueblo ya tiene su propia página en elterracampino.es. Si
> eres de aquí, o te fuiste pero sigues siendo, esto es tuyo.
>
> El primero te llega en un par de días.

### Paso 1 — Villada (espera 2 días) · tema: despoblación

**Asunto:** Villada ha perdido casi cuatro de cada diez negocios
**Preheader:** El mapa de un vaciado que no espera.

> Empezamos por aquí. Contamos, uno a uno, los negocios que han cerrado en
> Villada y los que aguantan: el resultado es un mapa que enseña, sin
> dramatismo, cómo se vacía un pueblo por dentro.
>
> **[Leer el reportaje →]**

Enlace: https://elterracampino.es/blog/villada-pierde-casi-cuatro-de-cada-diez-negocios-el-mapa-de-un-vaciado-que-no-espera.html

### Paso 2 — El dinero público (espera 3-4 días) · tema: ayudas

**Asunto:** 470.973 euros en ayudas: ¿a dónde va el dinero público de la comarca?
**Preheader:** 32 ayudas, y un solo convenio se lleva la mayoría.

> Repasamos las 32 subvenciones que han llegado a Tierra de Campos —de dónde
> salen, a quién van— y encontramos que un único convenio se lleva la mayor
> parte. Todo con la fuente oficial enlazada, para que lo compruebes tú mismo.
>
> **[Leer el reportaje →]**

Enlace: https://elterracampino.es/blog/que-esconde-el-dinero-publico-que-llega-a-tierra-de-campos-32-ayudas-470-973-euros-y-un-solo-convenio-que-se-lleva-la-mayoria.html

### Paso 3 — Villarramiel (espera 3-4 días) · tema: cien años

**Asunto:** Villarramiel perdió ocho de cada diez vecinos en un siglo
**Preheader:** Y nadie firmó la orden.

> Un siglo de padrones para contar cómo un pueblo se queda en la quinta parte de
> lo que fue. No hubo una decisión, ni una fecha: pasó despacio, casa a casa.
> Esta es la historia de ese vaciado lento.
>
> **[Leer el reportaje →]**

Enlace: https://elterracampino.es/blog/villarramiel-perdio-ocho-de-cada-diez-vecinos-en-un-siglo-y-nadie-firmo-la-orden.html

### Paso 4 — Migraciones (espera 3-4 días) · tema: migraciones

**Asunto:** Los 278 que llegaron y los 239 que faltan
**Preheader:** Qué sostiene hoy a Tierra de Campos.

> No todo es marcharse. Miramos quién llega a la comarca y quién se va, y el
> saldo cuenta algo menos sabido: quién está sosteniendo hoy estos pueblos. Con
> los datos de migraciones del INE.
>
> **[Leer el reportaje →]**

Enlace: https://elterracampino.es/blog/los-278-vecinos-que-llegaron-y-los-239-que-faltan-que-sostiene-hoy-a-tierra-de-campos.html

### Paso 5 — Homenaje a Mariano Haro (espera 3-4 días) · tema: memoria

*Cierre emotivo de la secuencia. Redactado para que no dependa de la fecha (no
dice "hoy se cumplen dos años"), así funciona aunque el lector lo reciba semanas
después.*

**Asunto:** El vecino de Becerril que fue el segundo más rápido del mundo
**Preheader:** Mariano Haro, el león de Becerril.

> Para terminar, una historia de las que dan orgullo. Un vecino de Becerril de
> Campos —alcalde de su pueblo durante veinticuatro años— fue cuatro veces
> subcampeón del mundo de cross y rozó la medalla olímpica. Se llamaba Mariano
> Haro. Esto es un homenaje.
>
> **[Leer el homenaje →]**

Enlace: https://elterracampino.es/blog/dos-anos-sin-mariano-haro-el-leon-de-becerril.html

---

**Mantenimiento:** cada vez que se publique una investigación nueva, se añade un
paso más al final del workflow (mismo formato: asunto + preheader + teaser +
botón). El homenaje (paso 5) conviene dejarlo siempre como último paso, de
cierre.
