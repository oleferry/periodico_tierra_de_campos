# Salida al mercado — "lectores primero"

Decisión del usuario (2026-11-23): primero lectores, después anunciantes, y
vender el sistema a otras comarcas cuando haya audiencia que enseñar. Sin
lectores no hay a quién venderle un banner ni nada que demostrar a una
diputación.

## Dónde está de verdad la gente de la comarca

No buscando un periódico en Google. Está en cuatro sitios, y el plan es estar
en los cuatro:

1. **Los grupos de Facebook de cada pueblo** ("Eres de X si…", "Fiestas de X",
   el del ayuntamiento). Es donde se comenta todo, sobre todo entre los de 45 a
   75 años y los que se fueron y siguen el pueblo desde fuera.
2. **WhatsApp**: los grupos de familia y de cuadrilla reenvían enlaces. Un
   enlace bueno que se reenvía vale más que cualquier anuncio.
3. **Los sitios físicos donde se para la gente**: el bar, la farmacia, el
   consultorio, la tienda, el tablón del ayuntamiento, la puerta de la iglesia.
4. **El ayuntamiento**: si el alcalde comparte o enlaza, el pueblo entero se
   entera.

## Herramientas ya construidas

| Para qué | Dónde |
|---|---|
| Cartel A4 con QR por pueblo, para colgar | `elterracampino.es/carteles` (uno por pueblo, botón de imprimir) |
| Hoja de Acompañar con los teléfonos | `elterracampino.es/acompanar-hoja` |
| Ficha propia de cada pueblo, para enlazar | `elterracampino.es/municipio/<pueblo>` |
| La portada recuerda el pueblo del lector | automático: quien entra por la ficha de su pueblo, la ve primero al volver |
| Correo semanal | los viernes llega el zip por Telegram para importar en MailerLite |
| Canal de Telegram | `t.me/elterracampino` |

## Las cuatro semanas

**Semana 1 — los 12 pueblos piloto.**
- Imprimir y colgar los carteles de los 12 pilotos (dos por pueblo: bar y
  farmacia o consultorio). Pedir permiso siempre; nadie quita un cartel que
  le han pedido colgar.
- Mandar la carta a los 12 ayuntamientos (abajo).
- Crear el **canal de WhatsApp** (sigue pendiente del checklist de
  lanzamiento) y ponerlo en el pie de la web.

**Semana 2 — Facebook, pueblo a pueblo.**
- Entrar en los grupos de los 12 pilotos y publicar una sola vez en cada uno
  el enlace a la ficha del pueblo, con el texto de abajo. Nunca el mismo
  mensaje pegado en todos el mismo día: se marca como spam.
- A partir de ahí, solo cuando haya algo de ese pueblo que interese de verdad
  (un pleno con chicha, una ayuda, una fiesta): compartir la pieza, no la
  portada.

**Semana 3 — lo que se reenvía.**
- Cada investigación nueva se comparte en los grupos de los pueblos que
  salen en ella. Las investigaciones son lo que se reenvía en WhatsApp.
- Las esquelas son la sección más leída de la prensa local: el pacto con una
  funeraria (pendiente) es lo que más audiencia puede traer de golpe.

**Semana 4 — medir y decidir.**
- Comparar visitas por pueblo (ver "Medir") y doblar esfuerzo donde ha
  funcionado.
- Con cifras en la mano, preparar la primera oferta a anunciantes locales
  (`docs/publicidad.md`).

## Textos listos para usar

### Carta a los ayuntamientos

> Asunto: El Terracampino, el periódico de los pueblos de Tierra de Campos
>
> Buenos días:
>
> Les escribo desde El Terracampino (elterracampino.es), un periódico digital
> dedicado a los pueblos de Tierra de Campos. Cada pueblo tiene su propia
> página con el tiempo, las ayudas públicas, lo que publican los boletines
> oficiales y las noticias del municipio, siempre con el enlace al documento
> original. La de [PUEBLO] está en elterracampino.es/municipio/[slug].
>
> Les pedimos dos cosas, si les parece bien:
>
> 1. Que enlacen esa página desde la web o las redes del ayuntamiento, para
>    que los vecinos —y los que viven fuera— la encuentren.
> 2. Permiso para resumir las actas de pleno que publican en su sede
>    electrónica, como ya hacemos con las de Mayorga con permiso de su
>    alcalde. Siempre enlazando el acta original.
>
> También les dejamos un cartel con un código QR para el tablón, por si
> quieren colgarlo.
>
> Un saludo,
> [nombre] — El Terracampino

### Mensaje para el grupo de Facebook del pueblo

> Para los de [PUEBLO] y los que lo seguís desde fuera: [PUEBLO] tiene su
> propia página en El Terracampino, con el tiempo de cada día, lo que publica
> el ayuntamiento en los boletines, las ayudas y las noticias del pueblo,
> siempre con el enlace al documento original. Es gratis y sin registrarse:
> elterracampino.es/municipio/[slug]

(Corto, sin exclamaciones y con el nombre del pueblo delante: es la voz de la
casa, `docs/voz-editorial.md`.)

## Medir

**Hoy no se puede medir nada**: la API de Vercel Analytics responde "Web
Analytics not found" (comprobado el 2026-11-23). Hay que volver a activarlo en
Vercel → proyecto `periodico-tierra-de-campos` → pestaña Analytics. El código
ya está puesto en todas las páginas.

Con Analytics activo, cada lunes mirar:

- visitas totales y por pueblo (`/municipio/<slug>`): dónde ha prendido;
- de dónde vienen (`facebook.com`, `l.facebook.com`, `t.me`, `wa.me`, directo):
  qué canal funciona;
- qué piezas se leen más: eso dice qué contar.

Objetivo de las cuatro semanas: **1.000 visitas al mes** y que al menos 5 de
los 12 pilotos traigan visitas propias. Con eso se puede ir a por el primer
anunciante por pueblo.

## Después: anunciantes y vender el sistema

- **Anunciantes** (`docs/publicidad.md`): patrocinio por pueblo y por sección,
  con las cifras de visitas de ese pueblo delante. El primer anunciante (Super
  Recreativa) sirve de ejemplo.
- **Vender el sistema**: el periódico se hace casi solo por menos de 30 €/mes
  de IA. Con un medio con audiencia que enseñar, se puede ofrecer a otras
  comarcas, diputaciones y grupos de acción local (LEADER). El argumento no
  es la tecnología: es "información pública de cada pueblo, contada claro,
  sin redacción".
