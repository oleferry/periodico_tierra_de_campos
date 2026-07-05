# El Palomar — Kit de marca

## 1. Identidad

**Nombre de marca:** El Palomar

**Subtítulo / claim (usar siempre junto al nombre, no solo el nombre solo):**

> El Palomar — Tierra de Campos al día

El subtítulo no es decorativo: "Tierra de Campos" es el término que la gente busca en Google y el que da contexto inmediato a quien no conoce la marca. En SEO, redes y cabecera de la web, el nombre "El Palomar" debe aparecer casi siempre acompañado de "Tierra de Campos" (title tag, bio de redes, encabezado de newsletter, etc.). Solo "El Palomar" a secas vale para elementos ya contextualizados (icono de app, favicon, membrete interno).

**Por qué el palomar:** el palomar de adobe es el icono arquitectónico más reconocible de la comarca, y la paloma mensajera es la metáfora natural de un medio que recoge información dispersa por los pueblos y la hace volar hasta el lector. Encaja con el principio fundacional del proyecto: no es opinión, es vigilancia informativa estructurada — el palomar recoge, no inventa.

**Claims secundarios** (usar según canal, no todos a la vez):
- "La comarca, contada de cerca."
- "Información pública, verificada, sin ruido."
- "Lo que pasa en tus pueblos, cada semana."

## 2. Logo

Archivos en `brand/logo/`:
- `palomar-icon.svg` — icono solo (favicon, avatar de Telegram, app icon, redes sociales).
- `palomar-logo.svg` — lockup horizontal (icono + nombre + subtítulo), para cabecera web y newsletter.

Ambos son una v1 vectorial hecha a mano con formas planas y la paleta oficial. Sirven para arrancar el MVP; si el proyecto avanza, conviene encargar una revisión a un diseñador para afinar el trazo del ave y las proporciones del palomar.

**Reglas de uso:**
- No deformar ni recolorear el icono. No añadir sombras, degradados ni efectos de brillo.
- Tamaño mínimo: icono 24px de alto; lockup horizontal 120px de ancho. Por debajo, usar solo el icono.
- Espacio de respeto: dejar alrededor del logo un margen mínimo igual a la altura de una de las circunferencias del palomar (el hueco de la paloma).
- Fondos: usar sobre Papel (#FAF6EE) o Adobe claro (#D9C7A7). Sobre foto, usar siempre sobre una franja sólida de Papel o Tierra, nunca directamente sobre imagen sin contraste garantizado.

## 3. Paleta de color

| Nombre | Hex | Rol | Uso |
|---|---|---|---|
| Barro | `#9C5B33` | Primario | Icono, títulos de sección, botones principales, subtítulo del logo |
| Tierra | `#3A3530` | Texto/tinta | Texto principal, tejado del icono, texto sobre fondos claros |
| Adobe claro | `#D9C7A7` | Secundario | Fondos suaves, tarjetas, separadores, huecos del palomar |
| Cielo | `#7FA8C9` | Acento | Enlaces, CTA secundario, la paloma del icono, etiquetas de "novedad" |
| Papel | `#FAF6EE` | Fondo base | Fondo general de la web (blanco cálido, no blanco puro) |

**Contraste de texto (obligatorio):**
- Texto oscuro (Tierra) sobre Papel, Adobe claro y Cielo.
- Texto claro (Papel) sobre Barro y Tierra.
- No usar Cielo como fondo de bloques grandes de texto largo (solo para acentos, badges o iconografía).

## 4. Tipografía

- **Cabecera / editorial:** Playfair Display (600 para titulares, 500 para subtítulos). Uso: nombre de marca, títulos de pieza, titulares de portada.
- **UI / cuerpo de texto:** Source Sans 3 (400 cuerpo, 500 énfasis/navegación). Uso: cuerpo de artículo, menús, formularios, metadatos.

**Jerarquía web orientativa:**
| Elemento | Fuente | Tamaño | Peso |
|---|---|---|---|
| H1 (titular pieza) | Playfair Display | 32–40px | 600 |
| H2 (sección) | Playfair Display | 24–28px | 500 |
| H3 (subsección) | Source Sans 3 | 18–20px | 500 |
| Cuerpo | Source Sans 3 | 16–17px, interlineado 1.6 | 400 |
| Meta / fecha / fuente | Source Sans 3 | 13px, color Tierra al 70% | 400 |

## 5. Voz y tono

Hereda directamente de `editorial/politica_editorial.md` y `docs/guia-estilo-gi.md` — no se duplica aquí, solo se referencia:

- Toda pieza responde a: qué ha pasado / a quién afecta / por qué importa / qué falta por saber. Enlaza siempre la fuente original.
- Factual y sobrio, nunca editorializado. Sin alarmismo, sin urgencia artificial, sin firma de opinión disfrazada de noticia.
- Intensidad de estilo alta en tiempo/huerta/boletín, media en deportes/agenda, baja en plenos/ayudas, muy baja en avisos urgentes.
- El aviso editorial fijo (ver README_PROYECTO.md §19) debe aparecer siempre en web y newsletter.

## 6. Imaginería y fotografía

- Preferir fotografía documental real de la comarca (adobe, trigales, palomares reales, plazas de los pueblos piloto) frente a banco de imágenes genérico de "redacción moderna".
- Si no hay foto real disponible, usar ilustración plana en los tonos de la paleta (mismo estilo que el icono) antes que stock genérico.
- Nunca iconografía corporativa de periódico (micrófonos, gente con auriculares en redacción, etc.) — no es la identidad del proyecto.

## 7. Aplicación por canal

- **Web:** cabecera con `palomar-logo.svg`; favicon = `palomar-icon.svg`.
- **Telegram:** avatar de canal = icono solo sobre fondo Papel.
- **Newsletter:** cabecera con lockup horizontal; pie con aviso editorial fijo en Source Sans 3, 13px.
- **Redes sociales:** foto de perfil = icono solo; portada/banner = lockup horizontal sobre Papel o Adobe claro.
