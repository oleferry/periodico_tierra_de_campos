# Qué funciona en medios hiperlocales del mundo — backlog de ideas

Investigación del 2026-07-24: cuatro barridos en paralelo (hiperlocales EEUU/UK,
proximidad Europa/España, automatización/IA, comunidad/diáspora) cruzados con lo
que El Terracampino ya tiene construido. Este documento es el backlog de
desarrollo: se va tachando/actualizando según se construyen las ideas.

Regla de lectura: cada idea lleva [esfuerzo] y qué la hace valiosa AQUÍ (comarca
envejecida, en despoblación, con diáspora urbana grande). Fuentes citadas al
final de cada bloque.

---

## Los 4 patrones en los que TODO converge

Las cuatro investigaciones, hechas por separado, coinciden en esto:

1. **Las esquelas son el generador de hábito nº 1** de la prensa local española
   y salieron por separado en las cuatro investigaciones. En pueblos donde todos
   se conocen, saber quién ha fallecido ES la noticia, y para la diáspora es la
   razón número uno de visita (enterarse a tiempo del entierro).
2. **La diáspora es el mercado que paga**, no el residente. Quien se fue tiene
   más renta, paga por nostalgia y por vigilar su pueblo (modelo "porte pago"
   portugués: décadas de suscripciones postales a emigrantes). Se activa en dos
   momentos: agosto y las muertes.
3. **Los mayores participan por voz y WhatsApp, no por formularios.** Los
   canales municipales de WhatsApp baten récords en España (Medina del Campo,
   aquí al lado, acaba de lanzar el suyo); el buzón de voz telefónico es la
   interfaz que un octogenario ya domina.
4. **La cita fija vence al goteo.** El 9 Nou es bisemanal desde 1978 y es líder
   comarcal en Cataluña; Naptown Scoop llegó a ~$200K/año con UNA newsletter
   curada. El valor es el filtro y el ritual ("los viernes sale el número"), no
   el volumen.

---

## Fase 1 — Generadores de hábito automatizables (coste casi cero, sin permisos)

Verticales de datos con fuente pública española verificada, siguiendo el modelo
RADAR/United Robots/Newsworthy ("un dataset nacional → una pieza por municipio"):

- [x] **Precios de lonja semanal** — HECHO el 2026-07-24 (`scrapers/lonja.py`,
  página `/lonja.html` + resumen en portada). La web de la Lonja de Valladolid
  y Palencia sirve la serie histórica completa en un atributo `data-data`, así
  que además del precio de hoy se compara con la sesión anterior y con hace un
  año. Contempla productos estacionales (el girasol se marca "último precio,
  <fecha>" fuera de campaña en vez de darlo como actual).
- [x] **Avisos meteorológicos adversos** — HECHO el 2026-07-24
  (`scrapers/aemet_avisos.py`, banda de alerta en portada y en la ficha de cada
  pueblo). RSS oficial del Plan Meteoalerta por provincia, filtrado por las
  zonas "Meseta de…" (las de Cordillera Cantábrica, Bierzo y Sanabria son
  montaña y no afectan a la comarca). Pendiente: empujarlo también al canal de
  Telegram.
- [x] **Paro municipal mensual** — HECHO el 2026-07-24 (`scrapers/paro_sepe.py`,
  bloque en portada). Excel mensual del SEPE por provincia, cruzado por nombre
  con los 191 municipios de la comarca. Tres cosas que hubo que resolver: se
  excluye Palencia capital (con 3.184 parados era el 72% del total y tapaba a
  los pueblos); los municipios con menos de 5 parados salen como "<5" por
  secreto estadístico y NO se suman (se dice cuántos son); y la mitad de los
  ficheros del SEPE traen mal un campo de la cabecera OLE2, que hay que
  corregir para poder abrirlos. La comparativa interanual se hace solo sobre
  los municipios con cifra en ambos meses. Cacheado en `data/paro_comarca.json`
  para no bajar ocho Excel en cada build.
- [x] **Agua y sequía semanal** — HECHO el 2026-07-24 (`scrapers/embalses.py`,
  bloque en `/campo.html`). SAIH Duero, filtrando los tres sistemas que riegan
  la comarca (Esla-Órbigo, Carrión y Pisuerga) y descartando los de Burgos,
  Soria, Segovia, Ávila y Salamanca, que están en la cuenca pero no riegan
  aquí. Da el % de llenado y, sobre todo, la comparación con el año pasado y
  con la media de diez años.
- ⏸️ **Aperturas y cierres de empresas (BORME)** — APARCADA el 2026-07-24
  tras medirlo de verdad, no por intuición. Datos de la prueba (6 días hábiles,
  las 4 provincias): **198 actos publicados, 58 con domicilio, y solo 1 en la
  comarca** — y ese era de Grijota, alfoz de Palencia, no de Tierra de Campos
  profunda. Extrapolado: ~4 al mes en 191 municipios; en los 12 pilotos, casi
  ninguno. Tres pegas más que lo desaconsejan hoy:
    · El municipio SOLO aparece en las constituciones y cambios de domicilio.
      En nombramientos, ceses o revocaciones (la mayoría) no hay forma de
      ubicar la empresa, así que ni siquiera se pueden filtrar.
    · Coste desproporcionado: habría que bajar ~40 PDFs semanales del BOE para
      encontrar una sola noticia.
    · Privacidad: los actos llevan nombres y apellidos de administradores y
      apoderados. La política editorial prohíbe dar nombres de particulares, así
      que habría que limpiarlos uno a uno.
  Cuándo retomarla: si libreBORME concede credenciales de su API (hoy devuelve
  401), el coste bajaría a una consulta por municipio y entonces sí compensa.
  El robots.txt del BOE prohíbe `/diario_borme/xml.php` pero permite los PDF y
  la API de sumarios, por si se retoma.
- ~~**Incidencias de tráfico N-601/N-610/A-6**~~ — DESCARTADA el 2026-07-24.
  Técnicamente se podía (DGT DATEX II, cada 5 minutos), pero aquí casi no hay
  tráfico: la sección estaría vacía la mayor parte del tiempo y el lector
  aprendería a ignorarla. Una sección permanentemente vacía resta credibilidad
  en vez de sumar servicio.
- [ ] **Beneficiarios PAC por pueblo** [fácil-media, pieza anual]. FEGA publica
  ficheros por municipio. Complementa la BDNS ya integrada. Ojo anonimización.
- [ ] **Mercado inmobiliario trimestral** [media]. Transacciones por municipio
  del Ministerio de Vivienda. En pueblos de 200 hab. hay 0-3 operaciones →
  pieza trimestral comarcal, no por pueblo.
- [x] **Detector de "leads" estadísticos** — HECHO el 2026-07-24
  (`scripts/detectar_anomalias.py` + tarea mensual `detector-anomalias-mensual`).
  Cuatro tipos de anomalía: récord de la serie, cruce de cifra redonda, cambio
  brusco para ese municipio (z-score sobre su propia historia) y
  "contracorriente" (va al revés que la comarca). No publica nada: da pistas
  para mirar, como el radar de noticias.
  Dos filtros anti-ruido que resultaron imprescindibles al probarlo:
    · En una comarca que se vacía, "otro mínimo histórico" es el paisaje de
      fondo, no una noticia. Si el municipio lleva 3+ años encadenando mínimos,
      la pista baja a relevancia 4 y no dispara aviso (Mayorga lleva 10 años
      seguidos; Valderas, 9).
    · Si más de un tercio de los pueblos va "a contracorriente", no es una
      anomalía: significa que el signo del total lo marcan uno o dos municipios
      grandes. En la primera prueba salían 7 de 12, todos falsos positivos.
  **Primera pista real encontrada**: Villada llevaba 11 años seguidos perdiendo
  población (1.042 en 2014 → 834 en 2024) y en 2025 gana 29 habitantes. Serie
  verificada a mano. Pendiente de averiguar la causa antes de escribir nada.

Fuentes: RADAR/PA Media, Newsworthy.se, United Robots (Press Gazette, CJR,
Global Project Oasis). Advertencia Hoodline: firmas falsas de IA y una acusación
falsa de asesinato — la transparencia sobre IA y la revisión humana que ya
practica este proyecto son la línea que separa esto del "pink slime".

## Fase 2 — Comunidad y hábito (requieren pactos o acción del usuario)

- [ ] **Esquelas dignas y gratuitas** [media, EDITORIALMENTE SENSIBLE, la más
  valiosa de todo el backlog]. VTDigger montó autoservicio de esquelas: ingreso
  directo modesto pero disparó afecto y donaciones. No hay dataset público:
  pacto manual con tanatorios/funerarias/parroquias de la comarca, alta por
  WhatsApp/teléfono para la familia, sección sobria SIN publicidad alrededor,
  aviso por Telegram por pueblo. Contraparte alegre: nacimientos, bodas, bodas
  de oro. Nunca scraper puro: acuerdo manual-asistido.
- [ ] **Canal de WhatsApp de El Terracampino** [fácil técnica, la crea Daniel].
  1-3 envíos/día máx: esquelas, bandos, titular. Tono "mensaje de un amigo", no
  tablón. Valorar audio de 60 segundos ("buenos días, hoy en la comarca...")
  para mayores con vista cansada.
- [ ] **Red de corresponsales-vecinos, uno por pueblo** [reclutamiento en
  persona]. Modelo Lokal (India, empezó con UN grupo de WhatsApp) y actu.fr
  (88 semanarios con corresponsales). El corresponsal NO escribe: manda un
  audio o foto por WhatsApp y la IA lo convierte en pieza con revisión. Crédito
  fijo ("corresponsal en X") y carné simbólico. Pagar en visibilidad y
  agradecimiento explícito — no simular empleo (crítica a Publihebdos).
- [ ] **Serie mensual "Gente de Campos"** [barata, máximo reenvío]. Perfiles:
  el último pastor, la panadera, el hijo del pueblo que triunfó fuera. Es el
  contenido original que más tráfico genera a Nub News ("Up Close"). Los
  nombres propios de vecinos disparan aperturas y reenvíos (Naptown).
- [ ] **Bandos municipales agregados** [media]. Bandomóvil sirve a 500+
  ayuntamientos; nadie agrega a escala comarcal. Sección "Bandos de hoy".
- [ ] **Buzón de voz telefónico** [fácil, ~5 €/mes Twilio]. "Cuéntenos qué pasa
  en su pueblo": transcripción con IA, revisión, sección "Lo cuentan los
  vecinos". Doble uso: chivatazos por voz y memoria oral. Modelo America
  Amplified/NPR.
- [ ] **Archivo fotográfico "antes y ahora"** [media]. Modelo Historypin.
  Campaña "trae tu caja de fotos" (escaneo en fiestas, foto-de-la-foto por
  Telegram). "Foto del jueves" con pregunta abierta ("¿quién es esta señora en
  la plaza, 1962?") — identificar retratados es participación masiva de
  mayores. PACTO con los grupos de Facebook "Eres de X si..." — pedir permiso,
  citar al grupo y autor, darles primicia. Nunca depredar.
- [ ] **Newsletter con secciones fijas y campo "tu pueblo"** [fácil]. Formato
  Smart Brevity (Axios): etiquetas repetidas que el lector mayor reconoce ("El
  dato", "Qué se cuece en el pleno", "Foto de la semana"). Email de bienvenida
  que pide RESPUESTA ("¿de qué pueblo eres o es tu familia?") — mejora
  entregabilidad, crea vínculo y segmenta gratis. Cadencia sagrada semanal.

## Fase 3 — Diáspora y mundo físico (lanzadera: fiestas de agosto)

Agosto es cuando la diáspora está físicamente en los pueblos. Un solo evento
alimenta varias ideas a la vez:

- [ ] **Captación en fiestas: QR en carteles** [fácil]. "¿Vives fuera? Llévate
  el pueblo contigo" → alta newsletter con campo pueblo.
- [ ] **Streaming de fiestas patronales** [fácil: móvil + trípode + YouTube
  Live]. La procesión del santo es el pico de añoranza. El vídeo queda de
  archivo. Avisar hora exacta a los emigrados por newsletter.
- [ ] **Concurso de fotos → calendario impreso** [media, para Navidad]. 12
  fotos de vecinos + santoral + fiestas de cada pueblo. Se vende (5-8 €) en
  panaderías y a la diáspora; la imprenta/comercios patrocinan la tirada.
  Objeto físico en la cocina = marca presente 365 días en hogares mayores.
- [ ] **"Fiesta del Terracampino" anual rotatoria** [organización]. Un vermú
  anual en un pueblo distinto cada año: entrega de premios del concurso,
  escaneo de fotos antiguas in situ, captación de corresponsales. Un medio de
  una persona necesita cara.
- [ ] **PDF semanal imprimible para bares** [fácil de generar]. Modelo
  Wochenblätter alemán (28M ejemplares gratuitos) + The Continent (África,
  periódico PDF nativo para reenviar por WhatsApp). A4/A5 autogenerado:
  portada + esquelas + agenda + anuncio del patrocinador. Los bares lo
  imprimen y lo dejan en la barra. Llega al vecino no-digital a coste cero.
- [ ] **Membresía "hijos del pueblo" (3-5 €/mes, voluntaria, sin muro)**
  [media]. Modelo The Mill (£7/mes, rentable en 2 años) + El Salto + Amedia:
  membresía identitaria, se paga por orgullo y pertenencia, no por acceso. El
  gancho noruego: más deporte local (crónicas y galerías de cada jornada).

## Ingresos (cuando haya audiencia medible)

- [ ] **Patrocinio por secciones a precio fijo** ("El tiempo, patrocinado por
  la ferretería X"): factura simple, sin programática. Modelo Nub News/Village
  Media (70% ingresos de publicidad local).
- [ ] **Un "inquilino ancla" primero**: UNA cooperativa agraria, correduría o
  funeraria comarcal como patrocinador fundacional antes de vender nada más.
- [ ] **Directorio como producto**: ficha destacada 10-20 €/mes (el directorio
  gratuito ya existe; el destacado es el upgrade).
- [ ] **Publicidad institucional con transparencia**: convenios de las
  diputaciones/Junta tarifados públicamente + página "quién nos financia"
  (riesgo de autocensura: mitigarlo con transparencia). Unirse a la Red de
  Periodistas Rurales para visibilidad y convocatorias.
- [ ] **Programa de recomendación simbólico**: "trae a 3 vecinos y saludamos a
  tu pueblo/tu quinta" — el primer escalón concentra el 98% del efecto
  (Naptown).

## Qué NO hacer (aprendido de fracasos documentados)

- **Foros/comentarios abiertos sin moderación** (Nextdoor): derivan en
  desinformación. Lo nuestro: moderación IA estricta, ya montada.
- **Escalar o gastar antes de tener ingresos** (Patch quemó $300M).
- **Contenido "regional" difuso que no es de ningún pueblo**: los lectores lo
  detectan y se van. Cada pieza, a la ficha de SU pueblo (ya es política).
- **Depender de redes sociales**: Naptown ingresaba $170K por email vs $3K por
  Instagram con más seguidores. El email/WhatsApp es el canal, la red social
  es el escaparate.
- **IA sin transparencia ni revisión** (Hoodline): firmas falsas y una
  acusación falsa de asesinato. Mantener el sello "Automático" visible y la
  revisión humana en lo sensible.
- **Hiperlocal centralizado sin arraigo** (Dichtbij.nl, cerrado 2017): la
  ventaja de este proyecto es ser del territorio con costes casi cero.

---

*Fuentes principales: Side Hustle Nation y The Tilt (Naptown Scoop), Press
Gazette (6AM City, Nub News, United Robots, Amedia), Poynter (The Mill),
Nieman Lab (Village Media, VTDigger, Amedia), Editor & Publisher (Axios Local),
La Revue des Médias (actu.fr/Publihebdos), El 9 Nou, Reuters Institute (The
Continent), GIJN (WhatsApp Global South), YourStory (Lokal), Historypin,
CJR/Global Project Oasis (Newsworthy), PA Media (RADAR), CNN/Techdirt
(Hoodline), FAPE (Mapa de la Comunicación Rural), AlmaNatura, Lenfest
Institute. URLs completas en los informes de investigación de la sesión del
2026-07-24.*
