// Aportación al archivo fotográfico comunitario — función serverless de Vercel.
//
// Un vecino sube una foto antigua de su pueblo desde web/archivo-enviar.html.
// Se guarda en Supabase (bucket "archivo", privado), carpeta PENDIENTES. No se
// publica nada: pasa por revisión humana (scripts/revisar_archivo.py) antes de
// aparecer, porque una foto antigua puede tener derechos de un tercero o
// mostrar a personas identificables.
//
// CommonJS a propósito, como el resto de funciones (ver web/api/suscribir.js).

const crypto = require("crypto");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Método no permitido" });
  }

  const b = req.body || {};
  if (b.web) return res.status(200).json({ ok: true }); // honeypot

  const pueblo = (b.pueblo || "").trim();
  if (!pueblo) return res.status(400).json({ error: "Indica de qué pueblo es la foto." });

  if (!b.foto_base64) return res.status(400).json({ error: "Falta la foto." });
  const m = /^data:image\/(jpe?g|png|webp);base64,([A-Za-z0-9+/=]+)$/.exec(b.foto_base64);
  if (!m) return res.status(400).json({ error: "La foto no tiene un formato válido." });
  const fotoBuf = Buffer.from(m[2], "base64");
  if (fotoBuf.length > 5 * 1024 * 1024) {
    return res.status(400).json({ error: "La foto es demasiado grande." });
  }

  const url = (process.env.SUPABASE_URL || "").trim().replace(/\/$/, "");
  const key = (process.env.SUPABASE_SERVICE_ROLE_KEY || "").trim();
  if (!url || !key || key === "replace_me") {
    return res.status(503).json({ error: "El envío no está disponible ahora mismo. Inténtalo más tarde." });
  }

  const id = crypto.randomBytes(6).toString("hex");
  const meta = {
    pueblo_slug: pueblo,
    anio: (b.anio || "").toString().trim().slice(0, 30) || null,
    descripcion: (b.descripcion || "").trim().slice(0, 600) || null,
    // El nombre de quien la aporta SÍ se publica, como crédito.
    autor: (b.autor || "").trim().slice(0, 120) || null,
    // Contacto opcional para dudas; no se publica.
    contacto: (b.contacto || "").trim().slice(0, 200) || null,
    recibido_en: new Date().toISOString(),
  };

  async function subir(ruta, cuerpo, contentType) {
    return fetch(`${url}/storage/v1/object/archivo/${ruta}`, {
      method: "POST",
      headers: { "Content-Type": contentType, apikey: key, Authorization: `Bearer ${key}` },
      body: cuerpo,
    });
  }

  try {
    const r1 = await subir(`pendientes/${id}.json`,
      Buffer.from(JSON.stringify(meta), "utf-8"), "application/json");
    if (!r1.ok) {
      const det = await r1.text().catch(() => "");
      console.error("Supabase archivo json error", r1.status, det.slice(0, 200));
      return res.status(502).json({ error: "No se pudo enviar. Inténtalo más tarde." });
    }
    const r2 = await subir(`pendientes/${id}.jpg`, fotoBuf, "image/jpeg");
    if (!r2.ok) {
      console.error("Supabase archivo foto error", r2.status);
      return res.status(502).json({ error: "No se pudo enviar la foto. Inténtalo más tarde." });
    }
    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error("Supabase archivo excepción", e);
    return res.status(502).json({ error: "No se pudo enviar. Inténtalo más tarde." });
  }
};
