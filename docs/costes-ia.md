# Coste de las llamadas a la IA

Medido el 2026-08-01. Sirve para no volver a calcularlo desde cero y para saber
dónde tocar si el gasto se dispara.

## Qué se paga

El build diario redacta con **Claude Opus 4.8** (**$5** por millón de tokens de
entrada, **$25** de salida). Volumen por build, contado del sitio generado:

| Qué | Llamadas | Modelo |
|---|---|---|
| Tiempo por pueblo (parte de hoy + días) | 2 × 27 = 54 | Haiku 4.5 (mecánico) |
| Titular + entradilla de cada noticia del feed | ~100 | Opus, esfuerzo bajo |
| Artículos completos (plenos y ayudas) | ~59 | Opus, esfuerzo normal |

Las imágenes de reportaje (OpenAI) son aparte, pero se generan **una vez por
artículo**: unos 3-4 céntimos cada una, irrelevante en el total.

## Las tres optimizaciones aplicadas (2026-08-01)

Antes de esto el build diario costaba del orden de **90-100 $/mes**.

1. **Persistir la caché de IA en el Action** — la de mayor impacto con
   diferencia (~80-90% del gasto). `sitegen/cache.py` guarda por hash lo ya
   redactado, pero `data/cache/` está en `.gitignore`, así que el Action
   arrancaba **cada día en blanco** y volvía a redactar ~215 textos que no
   habían cambiado, incluidos plenos de hace semanas. Resuelto con
   `actions/cache` en `.github/workflows/build-diario.yml`. En un día normal
   solo hay unas pocas noticias nuevas, así que ahora solo se paga eso.
2. **Modelo barato para lo mecánico** — el parte del tiempo y la moderación de
   comentarios usan `MODELO_MECANICO` (Haiku 4.5, $1/$5): son transformaciones
   de datos a texto, sin criterio editorial que proteger. Verificado que la
   calidad del parte se mantiene.
3. **Esfuerzo bajo en los titulares del feed** (`ESFUERZO_BAJO` en `ia.py`) —
   unas 100 llamadas por build de una tarea corta y acotada.

## La regla que NO hay que romper

**Los textos con juicio editorial siguen en Opus y con esfuerzo normal**:
`redactar_pleno()`, `redactar_ayuda()`, `redactar_investigacion()` y
`redactar_pista()`. Ahí es donde se decide qué se cuenta y cómo, y es
exactamente lo que diferencia al periódico. Abaratar eso sería ahorrar en lo
único que no se debe.

## Si hay que volver a medirlo

- Los precios oficiales cambian: consultar la documentación de Anthropic, no
  fiarse de estas cifras pasado un tiempo.
- Los tokens de un prompt se miden con la API de conteo (es gratis), no a ojo.
- El gasto **real facturado** está en la consola de Anthropic — es la única
  fuente de verdad; lo de aquí es una estimación con ±30% de margen.
