// Aviso de esquela desde la web — función serverless de Vercel.
//
// Un familiar o allegado rellena el formulario (web/esquela.html) y esto guarda
// el aviso en Supabase (bucket "esquelas", privado), en la carpeta de
// PENDIENTES. No se publica nada: cada esquela pasa por revisión humana
// (scripts/revisar_esquelas.py) antes de aparecer en la web. Es el contenido
// más sensible del proyecto y no admite automatismo en la publicación.
//
// La clave de servicio de Supabase vive solo en variables de entorno de Vercel
// (las mismas que usa web/api/chivatazo.js); nunca llega al navegador.
//
// CommonJS a propósito, igual que las otras funciones (ver web/api/suscribir.js
// para el porqué: ESM rompió el build entero una vez).

const crypto = require("crypto");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Método no permitido" });
  }

  const b = req.body || {};
  // Honeypot: campo oculto para personas; si viene relleno es un bot.
  if (b.web) return res.status(200).json({ ok: true });

  const nombre = (b.nombre || "").trim();
  const pueblo = (b.pueblo || "").trim();
  if (nombre.length < 3 || nombre.length > 120) {
    return res.status(400).json({ error: "Falta el nombre de la persona fallecida." });
  }
  if (!pueblo) {
    return res.status(400).json({ error: "Indica de qué pueblo era." });
  }

  // Foto opcional (data URL). Cap de tamaño: el navegador ya la reduce antes de
  // enviarla, pero se vuelve a comprobar aquí. Todo pasa por revisión humana,
  // así que una imagen inapropiada como mucho se queda en la cola y se rechaza.
  let fotoBuf = null;
  if (b.foto_base64) {
    const m = /^data:image\/(jpe?g|png|webp);base64,([A-Za-z0-9+/=]+)$/.exec(b.foto_base64);
    if (!m) return res.status(400).json({ error: "La foto no tiene un formato válido." });
    fotoBuf = Buffer.from(m[2], "base64");
    if (fotoBuf.length > 3 * 1024 * 1024) {
      return res.status(400).json({ error: "La foto es demasiado grande." });
    }
  }

  const url = (process.env.SUPABASE_URL || "").trim().replace(/\/$/, "");
  const key = (process.env.SUPABASE_SERVICE_ROLE_KEY || "").trim();
  if (!url || !key || key === "replace_me") {
    return res.status(503).json({ error: "El envío no está disponible ahora mismo. Inténtalo más tarde." });
  }

  const id = crypto.randomBytes(6).toString("hex");
  const meta = {
    nombre,
    pueblo_slug: pueblo,
    edad: (b.edad || "").toString().trim() || null,
    fecha_fallecimiento: (b.fecha_fallecimiento || "").trim() || null,
    funeral: (b.funeral || "").trim() || null,
    texto: (b.texto || "").trim().slice(0, 1000) || null,
    // Contacto de quien envía el aviso: SOLO para que la redacción pueda
    // verificarlo con la familia. Nunca se publica.
    remitente_contacto: (b.contacto || "").trim().slice(0, 200) || null,
    tiene_foto: Boolean(fotoBuf),
    recibido_en: new Date().toISOString(),
  };

  async function subir(ruta, cuerpo, contentType) {
    return fetch(`${url}/storage/v1/object/esquelas/${ruta}`, {
      method: "POST",
      headers: { "Content-Type": contentType, apikey: key, Authorization: `Bearer ${key}` },
      body: cuerpo,
    });
  }

  try {
    const r = await subir(`pendientes/${id}.json`,
      Buffer.from(JSON.stringify(meta), "utf-8"), "application/json");
    if (!r.ok) {
      const detalle = await r.text().catch(() => "");
      console.error("Supabase esquela error", r.status, detalle.slice(0, 200));
      return res.status(502).json({ error: "No se pudo enviar. Inténtalo más tarde." });
    }
    if (fotoBuf) {
      const rf = await subir(`pendientes/${id}.jpg`, fotoBuf, "image/jpeg");
      if (!rf.ok) console.error("Supabase esquela foto error", rf.status);
    }
    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error("Supabase esquela excepción", e);
    return res.status(502).json({ error: "No se pudo enviar. Inténtalo más tarde." });
  }
};
