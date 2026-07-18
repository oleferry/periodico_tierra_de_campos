# Newsletter (MailerLite) — estado y el paso que falta

## Qué hay construido (2026-07-18)

- **Formulario cableado** en la web (el del pie de portada y el popup): hacen
  POST a `/api/suscribir` con validación, honeypot anti-bots y mensaje de
  éxito/error. El popup sale una vez por visitante (localStorage), a los 15s.
- **Función serverless** `web/api/suscribir.js` (Vercel): habla con la API de
  MailerLite EN SERVIDOR — la clave nunca toca el navegador. Si la clave no
  está configurada responde "inténtalo más tarde" y la web no se rompe.

## El único paso manual que falta (5 minutos, lo tiene que hacer Daniel)

1. MailerLite → **Integrations → API** → genera/copia el token.
2. Vercel → proyecto de elterracampino → **Settings → Environment Variables**:
   - `MAILERLITE_API_KEY` = el token.
   - (Opcional) `MAILERLITE_GROUP_ID` = id del grupo donde meter a los
     suscriptores (créalo en MailerLite → Subscribers → Groups, p. ej.
     "El Terracampino"; el id sale en la URL). Sin esto, entran sin grupo.
3. **Redeploy** en Vercel (Deployments → ⋯ → Redeploy) para que la función
   coja las variables.
4. Pega también la clave en el `.env` local (`MAILERLITE_API_KEY`) para que
   los scripts puedan usarla en el futuro.

Prueba: en la web, meter un correo en el formulario del pie → "Hecho. Revisa
tu correo" → el correo aparece en MailerLite → Subscribers.

## La secuencia de bienvenida (idea aprobada, se monta en MailerLite)

Lo que pidió Daniel: al suscribirse, el lector entra en un bucle que le manda
los reportajes ya publicados **en orden, desde el primero**. Eso se configura
en MailerLite (no tiene API para crear automatizaciones):

MailerLite → **Automations → Create workflow** → disparador "subscriber joins
group" (el grupo de arriba) → un email por reportaje con 3-4 días de espera
entre cada uno. Hoy hay 2 reportajes publicados:

1. "Villada pierde casi cuatro de cada diez negocios..." —
   https://elterracampino.es/blog/villada-pierde-casi-cuatro-de-cada-diez-negocios-el-mapa-de-un-vaciado-que-no-espera.html
2. "Qué esconde el dinero público que llega a Tierra de Campos..." —
   https://elterracampino.es/blog/que-esconde-el-dinero-publico-que-llega-a-tierra-de-campos-32-ayudas-470-973-euros-y-un-solo-convenio-que-se-lleva-la-mayoria.html

Cada lunes que la tarea programada publique una investigación nueva, se añade
un paso más al final del workflow.
