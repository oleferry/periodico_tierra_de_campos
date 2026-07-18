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
20. **Cien años perdiendo habitantes** 🟡 — ya tenemos población 1996-2025 (`data/poblacion_negocios.json`); para el siglo completo hace falta la serie histórica de censos INE (1900-1991), que no tenemos todavía pero es dato público descargable.

## Recomendación de orden

Los dos más baratos de montar ya, reutilizando lo que existe:
- **#16** (dinero real contra la despoblación) — extiende el scraper de BDNS que ya corre.
- **#6** (hectáreas vs. agricultores) — mismo patrón que el dossier de despoblación, solo cambia la fuente INE.

Después, **#20** (cien años) y **#8** (escuelas) con una ronda de scraping nueva pero de fuentes públicas conocidas.

El resto (🔴) necesita reporteo humano — llamadas, entrevistas, visitas — que Daniel (o quien escriba) tendría que hacer; la IA puede ayudar a estructurar el dossier una vez haya datos/entrevistas reales, pero no puede generarlos solo.
