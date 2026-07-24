# Ideas de investigaciones (blog) — backlog

Lista recibida de Daniel el 2026-07-16. Se van marcando según se publiquen.
Cada investigación necesita un dossier de datos REALES antes de redactar
(ver `scripts/generar_articulo_blog.py`, función `dossier_despoblacion` como
modelo) — no se escribe nada sin cifras verificables detrás.

## Estado

- 🟢 dato ya disponible o fácil de conseguir (API pública, reutiliza scraper existente)
- 🟡 dato público pero requiere scraping/investigación nueva
- 🔴 requiere trabajo de campo (entrevistas, llamadas, visitas) — no es un dossier autogenerable

## Lista

1. **Hay casas. Pero no hay vivienda** 🔴 — inventario de vivienda vacía/disponible en Mayorga. Requiere trabajo de campo (catastro + contacto directo).
2. **El teletrabajo no va a salvar todos los pueblos** 🟡 — comparar con programas tipo Live in Ambroz. Dato disperso (fibra, colegios, transporte por pueblo), investigación más que scraping.
3. **El pueblo que te ayuda a llegar** 🔴 — pieza de diseño/propuesta, no de datos.
4. **Los trabajos que existen, pero nadie quiere cubrir** 🔴 — requiere preguntar directamente a empresas y cooperativas.
5. **¿Quién seguirá trabajando la tierra dentro de diez años?** 🟡 — censo agrario (edad de titulares) vía INE/MAPA, más entrevistas.
6. **Más hectáreas. Menos agricultores** 🟢 — superficie agraria, nº explotaciones y empleo agrario por comarca vía INE (censo agrario). Mismo patrón que el dossier de despoblación ya hecho.
7. **Cuánto cuesta mantener abierto un consultorio** 🟡 — datos de Sacyl (días de consulta, distancias), público pero no en una API fácil.
8. **El día que cierra una escuela** 🟢 — evolución de alumnado por centro, Junta de Castilla y León suele publicarlo.
9. **El autobús que decide dónde puedes vivir** 🔴 — requiere medir trayectos reales, trabajo de campo.
10. **¿Qué pueblo actúa como capital de los demás?** 🔴 — análisis/mapeo editorial, no dataset público directo.
11. **Nuevos vecinos: llegar es fácil, quedarse no tanto** 🔴 — entrevistas a quien ha llegado.
12. **Riace: el pueblo italiano que intentó repoblarse con migrantes** 🟡 — caso de fuera, documentado en prensa/informes, no dato propio.
13. **Casas a un euro, solares baratos y otras promesas** 🟡 — localizar solares/viviendas municipales vacías, requiere contactar ayuntamientos.
14. **La soledad de quien trabaja solo** 🔴 — entrevistas anónimas.
15. **Patrimonio que cuesta dinero y patrimonio que genera actividad** 🔴 — estudio de casos concretos, visitas.
16. **¿Cuánto dinero contra la despoblación llega realmente?** 🟢 — **ya tenemos la fuente**: el scraper de BDNS (`scrapers/bdns.py`) que alimenta las fichas de ayudas por pueblo. Es la investigación más barata de montar: es extender lo que ya existe a un "observatorio" agregado en vez de piezas sueltas.
17. **El agua también decide quién se queda** 🟡 — SIAR, AEMET, InfoRiego son públicos pero hay que scrapearlos, no los tenemos hoy. **Caso concreto detectado por el radar (2026-07-17)**: la CHD ha autorizado extraer ~117.000 m³/año del acuífero de las Lagunas de Villafáfila para una planta de hidrógeno verde en Granja de Moreruela (ambos pueblos de la comarca); Ecologistas Zamora habla de "ecocidio" y la CHD lo niega. Bien documentado en prensa (zamoranews, enfoquezamora, El Salto, Climática) y con documentos públicos de la CHD — da para dossier propio con las dos versiones.
18. **Servicios móviles frente a edificios vacíos** 🔴 — inventario que requiere contactar diputaciones/ayuntamientos.
19. **El negocio que cierra sin que nadie lo continúe** 🔴 — más un "radar" vivo (necesita fuentes que avisen de traspasos) que un artículo puntual.
20. **Cien años perdiendo habitantes** ✅ — **hecha (2026-07-22)**. La serie histórica 1900-1991 (operación 35 del INE, API Tempus, una tabla por provincia: León 3057, Palencia 3067, Valladolid 3080, Zamora 3082) ya está en `scripts/investigar_despoblacion.py` y combinada con la serie 1996-2025 en `dossier_cien_anos()`. Borrador en la rama `borrador/cien-anos-villarramiel`, pendiente de revisión.

21. **Lo que la inmigración está tapando** 🟢 — **ES LA MEJOR IDEA DEL BACKLOG
    AHORA MISMO, y los datos ya están descargados** en
    `data/migraciones_comarca.json`. Salió el 2026-07-24 investigando una pista
    del detector de anomalías (Villada rompía 11 años de caída). Al comprobar si
    Villada era excepcional, apareció algo mucho mayor:

    **En 2024, los 12 pueblos piloto ganaron 278 personas por migración —197 de
    ellas venidas del extranjero— pero el padrón solo creció en 39. Los otros
    239 se los llevó la diferencia entre defunciones y nacimientos.**

    Es decir: la inmigración no está haciendo crecer a la comarca, está tapando
    casi exactamente el agujero demográfico. Sin esas 278 personas, Tierra de
    Campos habría perdido 239 habitantes en un solo año.

    Datos por municipio (saldo migratorio 2024 → cambio de padrón 24/25):
    Medina de Rioseco +95 → +80 · Villalpando +70 → +34 · Paredes de Nava
    +42 → +16 · Sahagún +35 → −18 · Villada +33 → +29 · Carrión +31 → −2 ·
    Fuentes de Nava +18 → +14 · Villarramiel +9 → −6. En negativo: Mayorga −27,
    Villalón −11, Becerril −11, Valderas −6.
    Casos que hablan solos: **Sahagún ganó 35 personas por migración y aun así
    perdió 18 habitantes**; **Carrión ganó 31 y perdió 2**.

    Fuente: INE, Estadística de Migraciones y Cambios de Residencia (operación
    455, tabla 69767, saldos por municipio, año y tipo). El saldo vegetativo es
    implícito (cambio de padrón menos saldo migratorio), y conviene contrastarlo
    con el Movimiento Natural de la Población antes de publicar.

    Lo que falta para la pieza: quiénes son esas 197 personas llegadas de fuera
    y en qué trabajan. Eso ya no está en ninguna API — son llamadas al
    ayuntamiento, a las empresas agroalimentarias de la zona y, sobre todo, a
    ellos mismos. Encaja con la idea #11 (nuevos vecinos) y con la #12 (Riace).

    ✅ **PUBLICADA el 2026-07-24**: "Los 278 vecinos que llegaron y los 239 que
    faltan". Queda abierta la segunda parte, la del "por qué", con estas pistas
    ya localizadas en la búsqueda de prensa del mismo día:

    · **Explicación oficial ya publicada, para Villada**: el alcalde Manuel
      Gañán la dio en pleno y la recogió *Palencia en la Red* el 1-4-2025
      ("Villada crece en población tras décadas de caída"). Atribuye el
      repunte a negocios reabiertos, dos años de talleres de empleo y al
      trabajo de la ampliación de la base del AVE. Ojo: **no aporta ni una
      cifra**, son atribuciones suyas. Y no cuadran bien con la aritmética
      (haría falta bastante más entrada neta de la que mueve reabrir dos o
      tres negocios).
    · **Base de mantenimiento de Adif en Villada** (LAV Madrid-Norte): contrato
      de 67,9 M€ a la UTE Copasa-Sacyr Neopul-CSF, 2023-2027. Es el hecho
      material más sólido y encaja en el tiempo. Falta acreditar cuántos
      trabajadores se empadronaron: preguntar a Adif o a la UTE.
    · **Hipótesis no verificada pero de mucho peso aritmético**: Villada tiene
      la Residencia Fundación Casado del Alisal, con **113 plazas en un pueblo
      de 863 habitantes** (el 13% del padrón). Una variación de ocupación de
      25-30 plazas explicaría el +29 entero sin repoblación real. Nadie lo ha
      comprobado; hay que llamar a la residencia y pedir ocupación 2023/24/25.
    · **Contexto provincial que refuerza la tesis del reportaje**: en Palencia,
      2º trimestre de 2025, los españoles bajan en 204 y los extranjeros suben
      en 479 (*Palencia en la Red*).
    · **Descartado**: la adaptación de los padrones de los 190 ayuntamientos de
      la Diputación es de junio-septiembre de 2025, posterior al dato del
      1-1-2025, así que no puede explicarlo.
    · **Dato a cotejar antes de repetir la cifra**: el padrón oficial a
      1-1-2025 lo fija el Real Decreto 1117/2025 (BOE de 11-12-2025); el código
      INE de Villada es 34206.
    · **Vía rápida pendiente**: la tabla 33571 del INE ("Población por sexo,
      municipios, nacionalidad y edad") da el desglose español/extranjero por
      municipio. Resolvería en minutos cuánto de esto es inmigración.

## Recomendación de orden

Los dos más baratos de montar ya, reutilizando lo que existe:
- **#16** (dinero real contra la despoblación) — extiende el scraper de BDNS que ya corre.
- **#6** (hectáreas vs. agricultores) — mismo patrón que el dossier de despoblación, solo cambia la fuente INE.

Después, **#20** (cien años) y **#8** (escuelas) con una ronda de scraping nueva pero de fuentes públicas conocidas.

El resto (🔴) necesita reporteo humano — llamadas, entrevistas, visitas — que Daniel (o quien escriba) tendría que hacer; la IA puede ayudar a estructurar el dossier una vez haya datos/entrevistas reales, pero no puede generarlos solo.
