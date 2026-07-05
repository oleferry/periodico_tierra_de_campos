# Prompt 04 — Detector de riesgo editorial

Analiza el texto y determina si puede publicarse automáticamente.

Devuelve JSON válido.

Revisión obligatoria si aparece cualquiera de estos elementos:

- nombres de particulares;
- menores;
- sanciones;
- deudas;
- procesos judiciales;
- acusaciones;
- conflicto político;
- datos sanitarios;
- conflicto laboral;
- importes relevantes;
- contratación pública sensible;
- OCR dudoso;
- fuente no oficial;
- contradicciones.

Salida:

```json
{
  "risk": "low|medium|high",
  "requires_review": true,
  "reasons": [],
  "safe_to_publish_automatically": false,
  "recommended_action": "publish|review|reject|ask_for_source"
}
```
