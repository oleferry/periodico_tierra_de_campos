# Estudio de viabilidad, fuentes y municipios piloto

> Origen: estudio encargado por el usuario (ChatGPT), aportado en PDF el 2026-07-11. Se conserva aquí íntegro en su contenido factual porque alimenta directamente la config de municipios/fuentes y la priorización de scrapers.

## Resumen ejecutivo

Viabilidad **alta** si se plantea en dos capas:
- **Capa estable/automatizable**: fuentes oficiales y semioficiales de calidad — webs municipales, BOPs, BOCyL, AEMET, InfoRiego, RFCYLF/FBCYL, portales turísticos.
- **Capa frágil**: eventos, carteles, redes sociales, blogs locales — requiere scraping defensivo y bastante revisión manual.

La dificultad principal no es técnica sino de **heterogeneidad de fuentes**: CMS distintos por ayuntamiento, plenos/actas mal expuestos, información local en PDF/carteles/Facebook.

Regla de oro que ya coincide con la política editorial del proyecto: **donde no haya dato fiable, la salida es "no disponible", nunca una inferencia optimista.**

## Alcance geográfico — decisión de delimitación

"Tierra de Campos" no tiene una delimitación única:
- Junta de Castilla y León (Programa Territorial de Fomento 2024-2031): **206 municipios**.
- Delimitación geográfica de Wikipedia: **191 municipios**.

**Decisión recomendada (adoptada como base operativa):** usar la lista Wikipedia de 191 municipios como base geográfica del MVP, documentando la discrepancia con la delimitación administrativa amplia de la Junta.

## ⚠️ Discrepancia a resolver con el usuario

`config/municipios_piloto.yml` del pack original define **6 municipios piloto** (Mayorga, Villalón de Campos, Villada, Medina de Rioseco, Sahagún, Valderas). Este estudio recomienda arrancar con **12 municipios piloto**, añadiendo: Carrión de los Condes, Paredes de Nava, Valderas *(ya estaba)*, Villalpando, Becerril de Campos, Fuentes de Nava, Villarramiel.

Pendiente de decidir: ¿ampliar `config/municipios_piloto.yml` de 6 a 12, o mantener 6 para el primer sprint y añadir el resto después?

## Municipios piloto (12) — datos verificados

| Municipio | Provincia | Población (2025) | Web municipal | Sede electrónica | Plenos/actas |
|---|---|---|---|---|---|
| Medina de Rioseco | Valladolid | 4617 | medinaderioseco.org | no disponible | no disponible |
| Sahagún | León | 2380 | aytosahagun.es | no disponible | no disponible |
| Carrión de los Condes | Palencia | 1997 | carriondeloscondes.org | no disponible | no disponible |
| Paredes de Nava | Palencia | 1927 | paredesdenava.es | no disponible | no disponible |
| Valderas | León | 1479 | aytovalderas.es | no disponible | no disponible |
| Villalón de Campos | Valladolid | 1473 | villalondecampos.ayuntamientosdevalladolid.es | no disponible | no disponible |
| Villalpando | Zamora | 1433 | villalpando.es | no disponible | no disponible |
| Mayorga | Valladolid | 1354 | mayorga.ayuntamientosdevalladolid.es | no disponible | no disponible |
| Villada | Palencia | 863 | villada.es | no disponible | no disponible |
| Villarramiel | Palencia | 782 | villarramiel.es | no disponible | no disponible |
| Becerril de Campos | Palencia | 737 | becerrildecampos.es | no disponible | no disponible |
| Fuentes de Nava | Palencia | 581 | fuentesdenava.es | no disponible | no disponible |

Nota: "sede electrónica" y "plenos/actas" no verificados para ninguno de los 12 en esta revisión — pendientes de una pasada de scraping/verificación manual dedicada.

## Fichas municipales — notas editoriales y de fuente

- **Mayorga** (Valladolid, 1354 hab., 42.1666301,-5.2626995): sin sede/plenos verificados, sin club federado identificado. Monitorizar RFCYLF por nombre de club.
- **Villalón de Campos** (Valladolid, 1473 hab., 42.0984494,-5.0347132): fiestas Virgen de Fuentes (8 sept.), San Juan y San Pedro (23 y 29 junio).
- **Villada** (Palencia, 863 hab., 42.25056,-4.96694): Feria de la Matanza documentada en agenda cultural.
- **Medina de Rioseco** (Valladolid, 4617 hab., 41.883056,-5.042778): mayor piloto por población, nodo patrimonial/turístico, prioridad alta por volumen institucional.
- **Paredes de Nava** (Palencia, 1927 hab., 42.152778,-4.694444): San Sebastián (20 enero), Benditos Novillos, Virgen de Carejas (~8 sept.), Jornadas Vacceas. Deporte: Carrera Vaccea "La Ciudad" (C.D. Villa de Paredes + ayuntamiento) — fuente local válida no federativa.
- **Becerril de Campos** (Palencia, 737 hab., 42.108333,-4.641667): CD Becerril (fútbol, vía RFCYLF). Patrimonio fuerte: Santa María y San Pedro Cultural.
- **Fuentes de Nava** (Palencia, 581 hab., 42.083056,-4.783056): Laguna de la Nava — línea editorial propia (aves, humedad agrícola, calendario estacional). Fiesta: San Agustín.
- **Sahagún** (León, 2380 hab., 42.371111,-5.033056): nodo potente — Camino de Santiago, patrimonio mudéjar, portal turístico propio. Fiesta principal: San Juan de Sahagún (12 junio) + Virgen Peregrina. Prioridad alta en agenda/audiovisual.
- **Valderas** (León, 1479 hab., 42.0775,-5.4425): conjunto histórico. Ferias y fiestas de julio; fiestas patronales de septiembre (Virgen del Socorro). Sin fuente deportiva federativa clara.
- **Villalpando** (Zamora, 1433 hab., 41.864722,-5.413056): capital comarcal de la Tierra de Campos zamorana — priorizar pese a verificación incompleta. Fiestas: San Roque, Inmaculada Concepción.
- **Carrión de los Condes** (Palencia, 1997 hab., 42.338889,-4.601944): ayuntamiento + patrimonio + Camino. Feria de Antigüedades Almoneda y Coleccionismo (julio). Instalaciones deportivas (fútbol, fútbol-7, pabellón) sin club federado verificado.
- **Villarramiel** (Palencia, 782 hab., 42.0425,-4.913056): candidato claro para segunda ronda de investigación manual — nada verificado (sede, plenos, deporte, ferias).

## Comparativa de fuentes por tipo

| Tipo de fuente | Ejemplos | Método recomendado | Prioridad | Riesgo técnico | Riesgo legal |
|---|---|---|---|---|---|
| API / estructurada | AEMET, InfoRiego | API/feed | Alta | Bajo | Bajo |
| Web oficial deportiva | RFCYLF, FBCYL | Scraping HTML defensivo | Alta | Medio | Bajo-Medio |
| Web municipal | Noticias, agendas, plenos, transparencia | Scraping HTML + revisión manual | Alta | Medio-Alto | Medio |
| BOP / BOCyL | Anuncios, presupuestos, convocatorias | Scraping HTML/PDF | Alta | Medio | Bajo |
| Carteles e imágenes | Fiestas, ferias, mercados | OCR solo si no hay texto | Media | Alto | Medio |
| RRSS | Facebook, Instagram, X, YouTube | Manual / scraping mínimo | Media | Alto | Medio-Alto |
| Blogs e historia local | Patrimonio, relatos, fotos antiguas | Curación manual | Media-Baja | Medio | Medio |

Base legal: transparencia activa y acceso a información pública (Ley 19/2013); reutilización de información del sector público (Ley 37/2007). No cubre reutilización libre de fotos/vídeos de redes, carteles o YouTube — revisar condiciones caso a caso. Revisar `robots.txt` y límites por dominio antes de scraping intensivo.

## Scrapers recomendados (SCR-ID)

| ID | Objetivo | Fuente | Método | Frecuencia | Complejidad |
|---|---|---|---|---|---|
| SCR-MUN-VA-AYT | Webs municipales Valladolid (plataforma común) | ayuntamientosdevalladolid.es | Scraping HTML | diaria | Media |
| SCR-MUN-PA-WEB | Webs municipales Palencia | dominios propios | Scraping HTML | diaria | Media |
| SCR-MUN-LE-WEB | Webs municipales León (piloto) | aytosahagun.es, aytovalderas.es | Scraping HTML | diaria | Media |
| SCR-MUN-ZA-WEB | Webs municipales Zamora (piloto) | villalpando.es | Scraping HTML | diaria | Media |
| SCR-BOP-VA | BOP Valladolid | oficial BOP | HTML/PDF | diaria | Media |
| SCR-BOP-PA | BOP Palencia | oficial BOP | HTML/PDF | diaria | Media |
| SCR-BOP-LE-ZA | BOP León y Zamora | oficiales BOP | HTML/PDF | diaria | Media |
| SCR-BOCYL-TC | BOCyL (normas/anuncios regionales) | BOCyL | HTML/PDF | diaria | Baja |
| SCR-SPORT-RFCYLF | Resultados fútbol/fútbol sala | RFCYLF | Scraping HTML | diaria en temporada | Media |
| SCR-SPORT-FBCYL | Resultados baloncesto | FBCYL | Scraping HTML | diaria en temporada | Media |
| SCR-WEATHER-AEMET | Predicción/avisos meteo | AEMET | API | 2x/día | Baja |
| SCR-AGRO-INFORIEGO | Riego y contexto agro | InfoRiego | API | diaria | Baja |
| SCR-EVENT-CARTEL | Carteles de fiestas/ferias | webs municipales / RRSS | OCR + manual | semanal | Alta |
| SCR-PATRIMONIO-TUR | Turismo y patrimonio | turismo provincial/municipal | Scraping HTML | semanal | Baja |

**Orden de implantación recomendado:** primero base municipal (SCR-MUN-*) + publicación oficial (BOP/BOCyL) + meteo/agro (AEMET/InfoRiego) en paralelo → después deporte federativo (RFCYLF/FBCYL) → por último la capa difícil (carteles/eventos, patrimonio-turismo).

## Medios de contraste (no fuente primaria, sirven para detectar eventos)

Radio Palencia, Radio Zamora, La Opinión-El Correo de Zamora, y cabeceras provinciales equivalentes en Valladolid y León. Útiles para detectar eventos/cambios institucionales que luego se verifican en fuente oficial — nunca como fuente primaria de una pieza.

## Monetización

**Evitar publicidad programática como primera vía** (ingresos bajos, tráfico volátil en pueblos pequeños). Ruta recomendada:
1. Patrocinios locales
2. Suscripción WhatsApp/Telegram premium
3. Directorios patrocinados
4. Agenda comercial
5. (Fase 2) Servicios B2B: ayuntamientos, asociaciones, cooperativas, clubes, casas rurales

Advertencia explícita del estudio: no intentar "Sofascore + periódico + guía comercial + agenda + IA climática + OCR social" desde el día uno — el riesgo de mantenimiento supera el beneficio. MVP estrecho.

## Limitaciones abiertas del estudio

- No se ha verificado exhaustivamente, municipio por municipio, la publicación efectiva de plenos/actas/sede/transparencia para los 191 municipios — solo hipótesis para los 12 pilotos, y ahí tampoco (todo "no disponible" salvo web y población).
- No existe aún ordenación completa por población de los 191 municipios (requeriría extracción INE/Wikidata).
- El estudio menciona 3 archivos adjuntos (CSV principal de municipios, GeoJSON de municipios piloto, mapa PNG) que **no llegaron con el PDF** — pendiente pedírselos al usuario si los tiene en algún otro sitio, porque el CSV en particular sería la base ideal para el seed de los 191 municipios.

**Siguiente paso recomendado por el propio estudio:** usar este documento como base maestra, automatizar primero AEMET + InfoRiego + BOP/BOCyL + noticias municipales + deporte federativo, y dejar como sprint siguiente un scraper específico de sedes electrónicas/plenos solo para los 12 pilotos.
