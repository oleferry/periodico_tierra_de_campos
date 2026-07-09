# El Terracampino — README de proyecto MVP

## 0. Decisión de producto

Este proyecto no empieza como un periódico completo.

Empieza como una máquina de información local.

La función inicial es sencilla:

1. detectar información pública nueva;
2. extraer el texto;
3. clasificarlo;
4. resumirlo sin inventar;
5. marcar riesgos;
6. generar una pieza publicable;
7. pasarla por revisión cuando haga falta;
8. publicar en web, newsletter y Telegram.

No es opinión automática.

Es vigilancia local estructurada.

## 1. Objetivo del MVP

Construir un sistema que genere entre 10 y 20 piezas semanales útiles para Tierra de Campos usando fuentes públicas y verificables.

### Verticales iniciales

- Ayuntamientos: plenos, actas, bandos, sedes electrónicas.
- BOP/BOCYL: anuncios, ayudas, licitaciones, plazos.
- Deportes: resultados, clasificaciones, próxima jornada.
- Tiempo: resumen humano diario/semanal.
- Campo y huerta: riego, heladas, calor, calendario orientativo.
- Agenda: eventos, cultura, fiestas, actividades.

### Municipios piloto

Prioridad 1:

- Mayorga
- Villalón de Campos
- Villada
- Medina de Rioseco
- Sahagún
- Valderas

Prioridad 2:

- Paredes de Nava
- Becerril de Campos
- Carrión de los Condes
- Villalpando

Prioridad 3:

- Fuentes de Nava
- Villarramiel

El inventario completo está en:

`data/inventario_fuentes_tierra_de_campos.xlsx`

## 2. Qué no se construye en el MVP

No construir todavía:

- app móvil;
- login de usuarios;
- pagos;
- WhatsApp masivo;
- scraping de Instagram;
- scraping agresivo de Facebook;
- cobertura de 100 municipios;
- minuto a minuto deportivo;
- editorialización política automática;
- publicación automática de plenos sensibles;
- sistema de comentarios.

El riesgo de hacer demasiado pronto es alto.

Más código no significa más producto.

Significa más mantenimiento.

## 3. Arquitectura funcional

```text
Fuentes públicas
↓
Scrapers / APIs / RSS
↓
Normalizador
↓
Base de datos
↓
Detector de novedades
↓
Extractor de texto
↓
Clasificador
↓
Resumen factual JSON
↓
Detector de riesgo editorial/legal
↓
Redacción IA
↓
Revisión humana si procede
↓
Publicación web / newsletter / Telegram
```

## 4. Stack recomendado

### Opción recomendada

- Backend: Python.
- Scraping: Requests, BeautifulSoup, Playwright solo cuando sea necesario.
- Base de datos: Supabase/PostgreSQL.
- Jobs: Railway Cron, GitHub Actions o Supabase scheduled functions.
- Frontend: Next.js o Astro.
- Panel interno: Supabase Studio, Directus o herramienta propia mínima.
- IA: OpenAI/Claude con prompts versionados.
- Newsletter: MailerLite o Brevo.
- Alertas: Telegram bot.
- Logs: Sentry o tabla propia `scrape_runs`.

### Opción ultraligera

- Google Sheets como base inicial.
- Make/n8n para capturas simples.
- WordPress/Ghost para publicar.
- MailerLite para newsletter.

Esta opción sirve para validar audiencia, pero no para escalar bien.

## 5. Estructura del repositorio

```text
tierra-campos-mvp/
  README_PROYECTO.md
  .env.example
  data/
    inventario_fuentes_tierra_de_campos.xlsx
  docs/
    guia-estilo-gi.md
  config/
    municipios_piloto.yml
    fuentes_globales.yml
  database/
    schema.sql
  scrapers/
    README_SCRAPERS.md
  prompts/
    01_resumen_factual.md
    02_redaccion_local.md
    03_version_telegram.md
    04_detector_riesgo.md
    05_tiempo_humano.md
    06_huerta_campo.md
    07_deportes.md
  editorial/
    politica_editorial.md
```

## 6. Guía de estilo

La guía de estilo debe ir adjunta al repositorio.

Ruta recomendada:

`docs/guia-estilo-gi.md`

No hace falta pegarla a mano en cada prompt.

Pero sí debe cargarse como contexto cuando se generen piezas editoriales.

### Aplicación por tipo de contenido

| Tipo de contenido | Aplicación de guía |
|---|---|
| Tiempo contado | Alta |
| Huerta/campo | Alta |
| Boletín semanal | Alta |
| Crónica deportiva | Media |
| Agenda | Media |
| Plenos municipales | Baja-media |
| Ayudas públicas | Baja |
| Avisos urgentes | Muy baja |

Motivo:

La guía busca textos vivos.

Pero un pleno municipal o una ayuda pública necesitan claridad antes que estilo.

No se debe convertir un acuerdo municipal en una columna literaria.

## 7. Modelo de datos mínimo

El SQL inicial está en:

`database/schema.sql`

Tablas principales:

- `municipalities`
- `sources`
- `scrape_runs`
- `documents`
- `pieces`
- `editorial_reviews`
- `teams`
- `matches`
- `alerts`
- `subscribers`

## 8. Formato estándar de salida de scraper

Todo scraper debe devolver este objeto, aunque la fuente sea HTML, PDF, RSS o API.

```json
{
  "source_id": "mayorga_plenos",
  "municipality": "Mayorga",
  "source_type": "municipal_plenary",
  "title": "Acta del pleno ordinario...",
  "published_at": "2026-07-02",
  "detected_at": "2026-07-02T10:00:00+02:00",
  "url": "https://...",
  "file_url": "https://...",
  "raw_text": "...",
  "hash": "sha256...",
  "confidence": "high",
  "requires_review": true
}
```

## 9. Detección de novedades

Reglas:

1. Si aparece una URL nueva, procesar.
2. Si cambia el hash del documento, guardar nueva versión.
3. Si cambia solo la página índice pero no el documento, no generar pieza nueva.
4. Si el texto extraído es inferior a un umbral mínimo, marcar error.
5. Si hay OCR, marcar confianza media o baja.
6. Si hay datos personales, marcar revisión humana obligatoria.

## 10. Scrapers MVP

Orden de construcción recomendado:

1. `SCR-001`: crear tablas y cargar municipios/fuentes.
2. `SCR-002`: portales `ayuntamientosdevalladolid.es` para Mayorga y Villalón.
3. `SCR-003`: WordPress municipal para Villada y Becerril.
4. `SCR-006`: BOP Valladolid RSS.
5. `SCR-010`: AEMET predicción municipal.
6. `SCR-011`: InfoRiego/SIAR.
7. `SCR-012`: RFCYLF equipos locales.
8. `SCR-013`: RFCYLF resultados y clasificaciones.
9. `SCR-014`: generador de resumen factual.
10. `SCR-015`: panel de revisión humana.
11. `SCR-016`: publicador newsletter/Telegram.

No empezar por el scraper deportivo completo.

Primero hay que mapear equipos.

## 11. Fuentes globales iniciales

Ver:

`config/fuentes_globales.yml`

Fuentes clave:

- AEMET OpenData.
- InfoRiego.
- BOCYL datos abiertos.
- BOP Valladolid.
- BOP Palencia.
- BOP León.
- BOP Zamora.
- Real Federación de Castilla y León de Fútbol.
- Federación de Baloncesto de Castilla y León.
- BOE datos abiertos.

## 12. Flujo IA editorial

### Paso 1: resumen factual

Entrada:

- texto limpio;
- fuente;
- fecha;
- municipio;
- tipo de documento.

Salida:

```json
{
  "municipio": "Mayorga",
  "tipo": "pleno",
  "fecha_fuente": "2026-07-02",
  "hechos": [
    "Se aprobó...",
    "Se debatió..."
  ],
  "importes": [],
  "personas_mencionadas": [],
  "plazos": [],
  "dudas": [],
  "riesgo_editorial": "medio",
  "requiere_revision": true
}
```

### Paso 2: detección de riesgo

Marcar revisión obligatoria si aparecen:

- nombres de particulares;
- menores;
- sanciones;
- deudas;
- procesos judiciales;
- conflictos laborales;
- acusaciones políticas;
- contratación pública sensible;
- importes altos;
- OCR dudoso;
- fuente no oficial;
- contradicciones.

### Paso 3: redacción

Solo después del resumen factual.

Nunca generar directamente desde HTML sucio.

## 13. Estados editoriales

Cada pieza tendrá uno de estos estados:

- `draft`: generada, no revisada.
- `needs_review`: requiere revisión humana.
- `approved`: revisada y lista.
- `published`: publicada.
- `rejected`: descartada.
- `error`: error de fuente/extracción.

## 14. Publicación automática permitida

Puede automatizarse con menos riesgo:

- tiempo;
- resultados deportivos;
- clasificaciones;
- próxima jornada;
- agenda básica con fuente clara;
- avisos meteorológicos;
- calendario de huerta orientativo;
- recordatorios de plazo sin interpretación.

## 15. Publicación automática prohibida

No publicar sin revisión:

- plenos con conflicto político;
- sanciones;
- deudas;
- particulares identificables;
- menores;
- temas sanitarios;
- procesos judiciales;
- acusaciones;
- licitaciones relevantes;
- ayudas con interpretación jurídica;
- textos de OCR dudoso.

## 16. Canales de distribución

### Web

Estructura mínima:

```text
/
  hoy
  municipios
    mayorga
    villalon-de-campos
    villada
    medina-de-rioseco
  deportes
  tiempo
  campo-y-huerta
  agenda
  ayudas-y-bop
```

### Newsletter

Frecuencia inicial:

- semanal.

No diaria.

La diaria solo cuando haya contenido suficiente.

### Telegram

Canal inicial:

- El Terracampino.

Canales posteriores:

- Deportes.
- Campo y huerta.
- Ayudas y plazos.
- Municipios concretos.

### WhatsApp

No en MVP.

WhatsApp queda para fase posterior por coste, permisos, entregabilidad y riesgo de bloqueo.

## 17. Monetización

### Fase 1: sin monetización directa

Objetivo:

- validar contenido;
- medir lecturas;
- medir retorno semanal;
- conseguir primeros suscriptores.

### Fase 2: patrocinio local

Formatos:

- sección del tiempo patrocinada;
- deportes patrocinados;
- agenda del fin de semana;
- boletín agrícola;
- patrocinio por municipio.

Precios orientativos iniciales:

| Producto | Precio mensual |
|---|---:|
| Patrocinio sección | 50-150 € |
| Patrocinio municipio | 75-200 € |
| Newsletter semanal | 50-150 € |
| Banner local | 30-80 € |

### Fase 3: premium

Solo si hay uso real.

Posibles pagos:

- alertas de ayudas;
- alertas BOP por municipio;
- seguimiento de equipo deportivo;
- alertas agrícolas;
- dashboard para negocios;
- servicio para ayuntamientos.

## 18. Métricas de validación

Durante 4 semanas medir:

- piezas generadas;
- piezas publicadas;
- piezas descartadas;
- tiempo medio de revisión;
- errores de scraper;
- usuarios newsletter;
- aperturas;
- clics;
- visitas por municipio;
- reenvíos/compartidos;
- respuestas recibidas;
- comercios interesados.

### Criterio para seguir

Seguir si en 4 semanas se consigue:

- 10-20 piezas útiles por semana;
- menos de 30 minutos de revisión semanal por cada 10 piezas simples;
- al menos 100 suscriptores o usuarios recurrentes reales;
- interés de 3-5 negocios locales.

### Criterio para parar o reducir

Parar si:

- los scrapers se rompen todas las semanas;
- hay menos de 5 piezas útiles semanales;
- la revisión humana consume demasiado;
- nadie lee ni se suscribe;
- el coste técnico supera claramente el ahorro o retorno.

## 19. Aviso editorial fijo

Debe aparecer en web y newsletter:

```text
Este medio resume información pública procedente de fuentes oficiales y abiertas.

Los resúmenes no sustituyen al documento original.

Ante cualquier trámite, plazo, ayuda o acuerdo municipal, consulta siempre la fuente oficial enlazada.
```

## 20. Tareas inmediatas

1. Crear repositorio.
2. Subir este paquete.
3. Crear proyecto Supabase.
4. Ejecutar `database/schema.sql`.
5. Cargar municipios y fuentes desde Excel.
6. Programar scraper de Mayorga/Villalón.
7. Programar scraper de Villada.
8. Programar AEMET.
9. Programar resumen factual.
10. Crear vista interna de revisión.
11. Generar primer boletín semanal manual-asistido.

## 21. Regla de cierre

Si algo no se puede trazar a una fuente, no se publica.

Si algo puede dañar a una persona, no se automatiza.

Si algo requiere interpretación legal, no se maquilla como noticia.

El sistema debe ahorrar tiempo.

No crear otro trabajo.
