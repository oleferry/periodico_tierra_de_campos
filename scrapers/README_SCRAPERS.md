# Scrapers — instrucciones MVP

## 1. Principio general

Cada scraper debe ser pequeño, trazable y fácil de reparar.

No construir un mega-scraper.

Construir familias de scrapers:

- portales municipales Valladolid;
- WordPress municipal;
- BOP/RSS;
- AEMET;
- InfoRiego;
- RFCYLF.

## 2. Reglas técnicas

- Respetar `robots.txt`.
- Usar `User-Agent` identificable.
- Limitar frecuencia.
- Cachear HTML/PDF.
- Guardar hash SHA-256 del contenido.
- No generar pieza si no hay novedad real.
- Guardar errores en `scrape_runs`.
- No depender de redes sociales en MVP.

## 3. Contrato de salida

Todo scraper devuelve una lista de documentos con este contrato:

```json
{
  "source_id": "mayorga_plenos",
  "municipality": "Mayorga",
  "source_type": "municipal_plenary",
  "title": "Acta del pleno ordinario",
  "published_at": "2026-07-02",
  "detected_at": "2026-07-02T10:00:00+02:00",
  "url": "https://...",
  "file_url": "https://...",
  "raw_text": "...",
  "hash": "sha256...",
  "confidence": "high",
  "requires_review": true,
  "metadata": {}
}
```

## 4. Errores

Tipos mínimos:

- `network_error`
- `parse_error`
- `pdf_download_failed`
- `pdf_extract_failed`
- `ocr_required`
- `empty_text`
- `blocked`
- `unexpected_structure`

## 5. Prioridad

### SCR-002 Portales ayuntamientosdevalladolid.es

Municipios:

- Mayorga
- Villalón de Campos

Objetivo:

- detectar actas nuevas;
- extraer título, fecha y enlace;
- descargar PDF si existe;
- guardar documento.

### SCR-003 WordPress municipal

Municipios:

- Villada
- Becerril de Campos
- Villarramiel

Objetivo:

- leer categoría de actas;
- leer noticias/eventos;
- detectar PDFs.

### SCR-006 BOP Valladolid RSS

Objetivo:

- descargar RSS;
- filtrar por municipios objetivo;
- guardar anuncios relevantes.

### SCR-010 AEMET

Objetivo:

- obtener predicción por municipio;
- guardar datos estructurados;
- generar pieza de tiempo.

### SCR-011 InfoRiego/SIAR

Objetivo:

- obtener datos agroclimáticos;
- generar orientación para campo y huerta;
- no convertir orientación en asesoramiento técnico cerrado.

### SCR-012/SCR-013 RFCYLF

Objetivo:

- primero mapear equipos;
- después resultados y clasificaciones;
- no scrapear toda la federación sin filtro.
