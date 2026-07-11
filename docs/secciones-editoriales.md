# Secciones editoriales de El Terracampino

Consolida tres piezas que ya existían sueltas: las 9 secciones con color del kit de marca (`brand/el_terracampino_kit_visual.md` §14), el enum `source_type` de `database/schema.sql`, y las "capas de información" de la sesión de brainstorming del usuario. Sirve de referencia única para nombrar navegación, escribir prompts nuevos y decidir qué scraper alimenta qué sección.

## 1. Mapa de secciones

| Sección | Color | Qué cubre | `source_type` | Prompt | Automatización |
|---|---|---|---|---|---|
| Hoy | Terrón | Portada / resumen del día, mezcla de piezas de las demás secciones | — (agregador) | `02_redaccion_local` | Auto, sin revisión adicional (hereda el riesgo de cada pieza que agrega) |
| Ayuntamiento en limpio | Azul BOP | Plenos, acuerdos, sede electrónica, BOP/BOCyL | `municipal_plenary`, `electronic_office`, `bop`, `bocyl` | `01_resumen_factual` | Auto + revisión humana obligatoria (política editorial §3) |
| El marcador | Tinta Tierra | Resultados y clasificaciones de fútbol y baloncesto locales | `sports` | `07_deportes` | Auto, sin revisión salvo incidencia |
| A ras de tierra | Cielo Bajo | Tiempo y avisos meteorológicos | `weather` | `05_tiempo_humano` | Auto, sin revisión |
| Campo y huerta | Verde Regadío | Agro profesional + huerta familiar (ver §3, desarrollo aparte) | `agriculture` | `06_huerta_campo` | Auto, sin revisión (política editorial §4: "orientación de huerta" está explícitamente permitida) |
| Agenda | Trigo Seco | Fiestas, ferias, eventos, agenda cultural | `agenda` | — (pendiente de escribir) | Auto, sin revisión |
| Ayudas y plazos | Azul BOP | Subvenciones (BDNS, Junta, diputaciones), plazos, empleo público | `bop`, `bocyl`, `other` | — (pendiente) | Revisión humana si hay importe o requisito legal |
| Negocios de aquí | Terrón | Directorio de comercios, aperturas, traspasos | `commerce` | — (pendiente) | Manual / curación (no hay fuente automatizable de origen) |
| Historias del terrón | Tinta Tierra | Patrimonio, relatos, memoria local | `other` | — (pendiente, ver `docs/estudio-fuentes-y-viabilidad.md` §Blogs e historia local) | Manual, curación |

## 2. Huecos detectados frente al brainstorming y al schema

La sesión de brainstorming y el enum `source_type` mencionan dos capas que **no tienen sección asignada todavía** en el kit de marca:

- **Empleo** (`employment` en el enum; SEPE, ECYL, portales oficiales). Puede vivir dentro de "Ayudas y plazos" al principio (ya cubre BOE/BOP/subvenciones, es contenido hermano), y separarse en su propia sección más adelante si genera volumen propio. No se propone nombre nuevo todavía para no añadir una sección más sin necesidad — el kit de marca ya avisa (§14): "no usar un color distinto para cada [cosa] al principio, eso complica demasiado".
- **Vivienda y traspasos** (mencionado en el brainstorming, no está en el enum `source_type` ni en el kit). Es contenido de curación manual (nadie publica un feed de "casas en venta en Mayorga"), así que encaja mejor fusionado en "Negocios de aquí" que como sección propia, al menos en el MVP.

Si en algún momento quieres separarlas, es un cambio pequeño (nueva fila en el enum + nuevo color de la paleta ya definida, hay margen: Rojo Aviso está reservado para alertas, pero quedan combinaciones de las 8 sin asignar a una sección fija).

## 3. Campo y huerta — desarrollo

Es la sección diferencial del proyecto (así la llamó el propio brainstorm: "una capa diferencial de agricultura") y la que tiene detrás más trabajo ya hecho: prompt escrito (`prompts/06_huerta_campo.md`), fuente agroclimática ya en el seed (InfoRiego) y permiso editorial explícito para publicar sin revisión humana.

Tiene dos públicos distintos que **no deben mezclarse en la misma pieza**, aunque compartan sección, color y fuente de datos:

### 3.1. Agro profesional

Tierra de Campos es tierra cerealista — trigo, cebada, girasol — y ese es el lector que vive de esto. Contenido:
- Ventanas de siembra y cosecha según AEMET/InfoRiego (heladas tardías, lluvia acumulada, riesgo de granizo).
- Recordatorios de plazos PAC/ayudas agrarias (se apoya en "Ayudas y plazos", no se duplica).
- Precio de cereal — **fuente pendiente de identificar y verificar** (candidata: Lonja de Valladolid); no se inventa la URL hasta comprobarla, siguiendo la disciplina del proyecto de no publicar fuentes sin verificar.

### 3.2. Huerta familiar / hortelanos aficionados

Este es el ángulo que pediste y que **no existe todavía en ningún medio de la comarca** — es terreno libre. Tierra de Campos tiene mucha población que ya no vive de la tierra pero mantiene huerto familiar (jubilados, segunda residencia de fin de semana, huerto de recreo). Es lectura de hábito, no de urgencia: exactamente el tipo de contenido que fideliza una newsletter.

Propuesta de formato, dentro de las reglas ya fijadas por `prompts/06_huerta_campo.md` y la política editorial (nunca asesoramiento fitosanitario cerrado, nunca asegurar cosecha, nunca generalizar toda la comarca a partir de una estación meteorológica):

- **Pieza fija semanal o quincenal**, no diaria — la huerta no cambia cada día, y publicar de más aquí es ruido.
- **Calendario mensual adaptado a la meseta**: qué sembrar/trasplantar/recolectar cada mes, con el matiz propio de Tierra de Campos (heladas tardías hasta bien entrado mayo, veranos secos y calurosos, suelo arcilloso). Esto es contenido evergreen: se escribe 12 piezas una vez y se reutiliza cada año con el dato meteo del momento encima.
- **Traducción de avisos meteo a huerto pequeño**: cuando AEMET avisa de helada o de ola de calor, la pieza de "A ras de tierra" (tiempo) da el dato; la de "Campo y huerta" da la lectura práctica ("cubre los semilleros esta noche", "riega temprano, no al mediodía"). Ya está soportado por el prompt 06 tal cual está escrito.
- **Ángulo comunitario** (fase 2, no MVP): buzón de fotos de hortelanos por Telegram — encaja con la fotografía documental que pide el kit de marca ("manos trabajando", "botas con barro") y da contenido real de la comarca sin depender de banco de imágenes. Requiere consentimiento explícito de quien manda la foto (política de fotografía del kit: "gente solo con permiso").
- **Nunca mezclar con el agro profesional en la misma pieza** — quien tiene 200 hectáreas de cereal y quien tiene un huerto de 100 metros no necesitan la misma pieza, aunque compartan tiempo y sección.

### Siguiente paso concreto

Si quieres, el siguiente paso natural es escribir el calendario mensual de huerta (12 piezas evergreen, una por mes) adaptado al clima de Tierra de Campos, listo para que el pipeline lo combine con el dato meteo real cuando exista. Es contenido que se puede escribir ya, sin esperar a tener scrapers ni maqueta web.
