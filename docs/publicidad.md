# Publicidad — banner de anunciantes en la newsletter

Estado: **preparado, a la espera de la primera lista de anunciantes** (la pasará
Daniel). Aquí queda el mecanismo, la plantilla y las reglas para que meterlos sea
un rato.

## Idea

Un bloque de patrocinio al pie de cada correo de la newsletter (y, si se quiere,
también en la web), con los primeros anunciantes de la comarca. Es la vía natural
de sostener el medio sin romper la confianza: negocios de aquí, marcados con
claridad como publicidad, sin ruido.

## Reglas (para que no se nos vaya de las manos)

- **Solo negocios reales de la comarca o de cercanía.** Verificar que existe y
  sigue abierto antes de publicarlo (igual que el directorio de servicios;
  mismo criterio que ya aplicamos con las bajas de Mayorga).
- **Siempre marcado como publicidad.** Etiqueta visible "Con el apoyo de" /
  "Publicidad". Nunca disfrazado de contenido editorial.
- **Nada engañoso ni de fuera del encaje del medio** (nada de apuestas,
  créditos rápidos, clickbait). Si un anuncio no lo pondríamos al lado de una
  esquela, no va.
- **Separación clara** entre lo que es periodismo y lo que es anuncio. La
  credibilidad es el único activo que tenemos.
- **Precios y acuerdos**: fuera de este documento (es material público del
  repo). Los datos de facturación no se guardan aquí.

## Dónde se guardan los anunciantes

`data/anunciantes.json` — ya creado con la estructura. Cada anunciante:

- `nombre`, `pueblo`, `texto` (una línea), `url`/`telefono` (opcionales),
- `imagen`: banner en `brand/anunciantes/<slug>.png` — **600 × 150 px**, PNG/JPG,
  < 80 KB (los correos pesados van a spam),
- `activo`: true/false, `desde`/`hasta` (vigencia), `_verificado` (fecha).

## Plantilla del banner para MailerLite (bloque HTML)

En MailerLite, dentro del correo: bloque **HTML personalizado** → pegar esto y
cambiar el enlace, la imagen y el texto. Es HTML de correo (tablas + estilos en
línea) para que se vea bien en Gmail, Outlook y móvil:

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;border-top:1px solid #D8B15A;">
  <tr>
    <td style="padding:14px 0 6px;font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#7a7a7a;">
      Con el apoyo de
    </td>
  </tr>
  <tr>
    <td align="center" style="padding:4px 0 0;">
      <a href="URL_DEL_ANUNCIANTE" target="_blank" style="text-decoration:none;">
        <img src="URL_DE_LA_IMAGEN_600x150" alt="NOMBRE DEL ANUNCIANTE" width="600" style="max-width:100%;height:auto;border-radius:6px;display:block;">
      </a>
    </td>
  </tr>
  <tr>
    <td align="center" style="padding:8px 0 0;font-family:Georgia,'PT Serif',serif;font-size:14px;color:#131313;">
      <strong>NOMBRE</strong> · <span style="color:#5a5a5a;">Pueblo · una línea de texto</span>
    </td>
  </tr>
</table>
```

Versión **solo texto** (si un anunciante no tiene banner): quitar la fila de la
imagen y dejar la última fila con el nombre + línea.

### Colocación
- **Un solo anunciante por correo** al principio (rotación entre correos), o
  una fila de 2-3 logos pequeños al pie. Recomendado empezar con **uno**, grande
  y limpio, para no saturar.
- Va **debajo del contenido**, antes del pie legal de MailerLite.

## Cuando llegue la lista

1. Meter cada anunciante en `data/anunciantes.json` (+ su banner en
   `brand/anunciantes/`).
2. Verificar cada negocio (existe y abierto).
3. Pegar la plantilla en el correo de MailerLite con sus datos.
4. (Opcional, fase 2) Automatizar: que el build genere el bloque de anunciantes
   activos para reutilizarlo en la web y/o en un HTML que se copie al correo.
