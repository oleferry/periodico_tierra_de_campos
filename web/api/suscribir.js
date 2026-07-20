// Alta en la newsletter (MailerLite) — función serverless de Vercel.
//
// Existe porque la clave de la API de MailerLite NUNCA puede ir en el
// navegador: el formulario de la web hace POST aquí, y es este código de
// servidor quien habla con MailerLite usando la clave guardada como variable
// de entorno de Vercel (Settings → Environment Variables):
//
//   MAILERLITE_API_KEY   obligatoria — MailerLite → Integrations → API
//   MAILERLITE_GROUP_ID  opcional — id del grupo "El Terracampino"; si no
//                        está, el suscriptor entra sin grupo.
//
// Mientras la clave no esté puesta, responde 503 y el formulario muestra
// "inténtalo más tarde" — la web no se rompe, solo no da de alta.

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Método no permitido" });
  }

  const { email, web } = req.body || {};

  // Honeypot: el campo "web" está oculto para personas; si viene relleno es
  // un bot rellenando formularios. Se responde OK para no darle pistas.
  if (web) return res.status(200).json({ ok: true });

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
    return res.status(400).json({ error: "Ese correo no parece válido." });
  }

  const key = (process.env.MAILERLITE_API_KEY || "").trim();
  if (!key || key === "replace_me") {
    // Diagnóstico temporal (solo NOMBRES de variables, nunca valores): para
    // averiguar por qué la clave no llega — quitar cuando funcione el alta.
    const pistas = Object.keys(process.env).filter((k) => /MAIL/i.test(k));
    return res.status(503).json({
      error: "El alta no está disponible ahora mismo. Inténtalo más tarde.",
      diag: { variables_con_MAIL: pistas, total_variables: Object.keys(process.env).length },
    });
  }

  const cuerpo = { email };
  const grupo = (process.env.MAILERLITE_GROUP_ID || "").trim();
  if (grupo) cuerpo.groups = [grupo];

  try {
    const r = await fetch("https://connect.mailerlite.com/api/subscribers", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify(cuerpo),
    });
    // 200/201 = alta o ya existía (MailerLite hace upsert): para el vecino es lo mismo.
    if (r.ok) return res.status(200).json({ ok: true });
    const detalle = await r.json().catch(() => ({}));
    console.error("MailerLite error", r.status, detalle);
    return res.status(502).json({ error: "No se pudo completar el alta. Inténtalo más tarde." });
  } catch (e) {
    console.error("MailerLite excepción", e);
    return res.status(502).json({ error: "No se pudo completar el alta. Inténtalo más tarde." });
  }
}
