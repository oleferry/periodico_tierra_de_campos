// Buzón de chivatazos anónimos — función serverless de Vercel.
//
// Guarda el mensaje directamente en Supabase Storage (bucket "chivatazos",
// privado) en servidor: la clave de servicio nunca toca el navegador.
// Deliberadamente NO se guarda IP, user-agent ni ningún dato de quien envía
// — es un buzón anónimo de verdad, no solo de nombre.
//
// Nadie publica esto automáticamente: solo alimenta una cola que revisa
// Daniel con scripts/listar_chivatazos.py (mismo criterio editorial que las
// pistas del radar — nunca se publica un chivatazo sin verificar).
//
// CommonJS a propósito, ver web/api/suscribir.js para el porqué (ESM rompió
// el build entero una vez).

const crypto = require("crypto");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Método no permitido" });
  }

  const { texto, pueblo, web } = req.body || {};

  // Honeypot: el campo "web" está oculto para personas.
  if (web) return res.status(200).json({ ok: true });

  const limpio = (texto || "").trim();
  if (!limpio || limpio.length < 20) {
    return res.status(400).json({ error: "Cuéntanos un poco más — con una frase suelta no hay mucho que investigar." });
  }
  if (limpio.length > 4000) {
    return res.status(400).json({ error: "Eso es demasiado largo. Resúmelo un poco, por favor." });
  }

  const url = (process.env.SUPABASE_URL || "").trim().replace(/\/$/, "");
  const key = (process.env.SUPABASE_SERVICE_ROLE_KEY || "").trim();
  if (!url || !key || key === "replace_me") {
    return res.status(503).json({ error: "El buzón no está disponible ahora mismo. Inténtalo más tarde." });
  }

  const id = crypto.randomBytes(6).toString("hex");
  const cuerpo = {
    texto: limpio,
    pueblo: (pueblo || "").trim() || null,
    recibido_en: new Date().toISOString(),
  };

  try {
    const r = await fetch(`${url}/storage/v1/object/chivatazos/pendientes/${id}.json`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: key,
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify(cuerpo),
    });
    if (r.ok) return res.status(200).json({ ok: true });
    const detalle = await r.text().catch(() => "");
    console.error("Supabase chivatazo error", r.status, detalle.slice(0, 200));
    return res.status(502).json({ error: "No se pudo enviar. Inténtalo más tarde." });
  } catch (e) {
    console.error("Supabase chivatazo excepción", e);
    return res.status(502).json({ error: "No se pudo enviar. Inténtalo más tarde." });
  }
};
