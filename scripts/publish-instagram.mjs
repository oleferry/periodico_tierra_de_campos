// Publica en Instagram la entrada más reciente de un feed RSS que tenga imagen
// utilizable y que aún no se haya publicado. Genérico y dirigido por el feed:
// el MISMO script vale para varios sitios (madapan.es, gafasvan.com,
// elterracampino.es); solo cambia la configuración por variables de entorno.
//
// Publicación por Graph API en dos pasos encadenados:
//   1) POST /{IG_USER_ID}/media          { image_url, caption } -> { id: creationId }
//   2) POST /{IG_USER_ID}/media_publish  { creation_id }        -> { id: publishedId }
//
// TRAMPA (documentada): el token va SIEMPRE en la cabecera Authorization: Bearer,
// nunca en el cuerpo JSON. La documentación de Meta induce a error en esto.
//
// La imagen: Instagram la DESCARGA de una URL pública (no se sube el fichero) y
// no admite publicaciones solo-texto. Los feeds RSS no suelen traer la imagen,
// así que se resuelve por IG_IMAGE_MODE (ver abajo). Si un ítem no tiene imagen
// utilizable (HEAD != 200), se salta y se prueba el siguiente.
//
// Sin duplicados: el registro (IG_REGISTRY, array JSON de guids ya publicados)
// se commitea desde el workflow. Sin él se republicaría lo mismo.
//
// -------- Configuración por entorno --------
//   IG_USER_ID           (req) ID numérico de la cuenta de Instagram de ESTE sitio
//   IG_ACCESS_TOKEN      (req) token de Usuario del Sistema (no caduca) de ESTE sitio
//   FEED_URL             (req) URL del RSS del sitio (p. ej. https://elterracampino.es/feed.xml)
//   IG_IMAGE_MODE        cómo obtener la imagen de cada ítem:
//                          "template"  -> transforma el <link> con IG_IMAGE_REPLACEMENTS
//                          "enclosure" -> usa <enclosure url> o <media:content url> del feed
//                          "og"        -> descarga la página del <link> y lee og:image
//                        (por defecto "enclosure")
//   IG_IMAGE_REPLACEMENTS  (modo template) JSON de pares [desde,hasta] aplicados al link.
//                          Ej. elterracampino: [["/blog/","/assets/blog/"],[".html",".jpg"]]
//   IG_HASHTAGS          (opc) línea de hashtags para el pie
//   IG_CTA               (opc) llamada a la acción (p. ej. "Más en la web — enlace en la bio.")
//   IG_REGISTRY          (opc) ruta del registro (por defecto scripts/instagram-posted.json)
//
// Uso:
//   node scripts/publish-instagram.mjs            # publica 1 (el más reciente pendiente con imagen)
//   node scripts/publish-instagram.mjs --dry-run  # enseña qué publicaría, sin publicar

import { readFile, writeFile, appendFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const DRY_RUN = process.argv.includes("--dry-run");
const GRAPH = "v21.0";
const API = `https://graph.facebook.com/${GRAPH}`;
const TIMEOUT_MS = 60_000;
const UA = "instagram-rss-bot/1.0";

class PublicarError extends Error {}

function env(nombre, req = false, def = "") {
  const v = (process.env[nombre] ?? "").trim();
  if (!v && req) throw new PublicarError(`Falta la variable de entorno ${nombre}`);
  return v || def;
}

const CFG = {
  uid: env("IG_USER_ID", true),
  token: env("IG_ACCESS_TOKEN", true),
  feedUrl: env("FEED_URL", true),
  imageMode: env("IG_IMAGE_MODE", false, "enclosure"),
  hashtags: env("IG_HASHTAGS"),
  cta: env("IG_CTA"),
  registry: resolve(process.cwd(), env("IG_REGISTRY", false, "scripts/instagram-posted.json")),
};

function replacementsDeEntorno() {
  const raw = env("IG_IMAGE_REPLACEMENTS");
  if (!raw) return [];
  let pares;
  try {
    pares = JSON.parse(raw);
  } catch {
    throw new PublicarError("IG_IMAGE_REPLACEMENTS no es JSON válido (esperado [[desde,hasta],...])");
  }
  if (!Array.isArray(pares)) throw new PublicarError("IG_IMAGE_REPLACEMENTS debe ser un array de pares");
  return pares;
}

async function conTimeout(fn) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    return await fn(ctrl.signal);
  } finally {
    clearTimeout(t);
  }
}

// --------- Parseo de RSS (sin dependencias) ---------

function desCData(s) {
  if (s == null) return "";
  const m = s.match(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/);
  return (m ? m[1] : s)
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&")
    .trim();
}

function tag(bloque, nombre) {
  const m = bloque.match(new RegExp(`<${nombre}(?:\\s[^>]*)?>([\\s\\S]*?)</${nombre}>`, "i"));
  return m ? desCData(m[1]) : "";
}

function attr(bloque, nombre, atributo) {
  const m = bloque.match(new RegExp(`<${nombre}\\b[^>]*\\b${atributo}\\s*=\\s*"([^"]+)"`, "i"));
  return m ? m[1] : "";
}

function parsearFeed(xml) {
  const texto = xml.replace(/\r\n/g, "\n"); // por si el feed viene de Windows
  const items = [...texto.matchAll(/<item\b[\s\S]*?<\/item>/gi)].map((m) => m[0]);
  return items.map((b) => {
    const link = tag(b, "link");
    const guid = tag(b, "guid") || link;
    const enclosure =
      attr(b, "enclosure", "url") ||
      attr(b, "media:content", "url") ||
      attr(b, "media:thumbnail", "url");
    return {
      title: tag(b, "title"),
      link,
      guid,
      description: tag(b, "description"),
      pubDate: tag(b, "pubDate"),
      enclosure,
    };
  });
}

function ordenarPorFechaDesc(items) {
  return [...items].sort((a, b) => {
    const ta = Date.parse(a.pubDate) || 0;
    const tb = Date.parse(b.pubDate) || 0;
    return tb - ta;
  });
}

// --------- Imagen por ítem ---------

async function existeImagen(url) {
  if (!url) return false;
  try {
    return await conTimeout(async (signal) => {
      const r = await fetch(url, { method: "HEAD", redirect: "follow", headers: { "User-Agent": UA }, signal });
      return r.ok;
    });
  } catch {
    return false;
  }
}

async function ogImage(pageUrl) {
  try {
    return await conTimeout(async (signal) => {
      const r = await fetch(pageUrl, { redirect: "follow", headers: { "User-Agent": UA }, signal });
      if (!r.ok) return "";
      const html = await r.text();
      const m =
        html.match(/<meta[^>]+property=["']og:image(?::url)?["'][^>]*content=["']([^"']+)["']/i) ||
        html.match(/<meta[^>]+content=["']([^"']+)["'][^>]*property=["']og:image["']/i);
      return m ? m[1] : "";
    });
  } catch {
    return "";
  }
}

async function imagenDeItem(item, replacements) {
  if (CFG.imageMode === "enclosure") return item.enclosure || "";
  if (CFG.imageMode === "og") return await ogImage(item.link);
  if (CFG.imageMode === "template") {
    let url = item.link;
    for (const [desde, hasta] of replacements) url = url.split(desde).join(hasta);
    return url;
  }
  throw new PublicarError(`IG_IMAGE_MODE desconocido: ${CFG.imageMode}`);
}

// --------- Registro ---------

async function cargarRegistro() {
  if (!existsSync(CFG.registry)) return [];
  const datos = JSON.parse(await readFile(CFG.registry, "utf8"));
  if (!Array.isArray(datos)) throw new PublicarError(`${CFG.registry} debe ser un array JSON de guids.`);
  return datos;
}

async function guardarRegistro(guids) {
  const ordenado = [...new Set(guids)].sort((a, b) => a.localeCompare(b));
  await writeFile(CFG.registry, JSON.stringify(ordenado, null, 2) + "\n", "utf8");
}

// --------- Pie de publicación ---------

function pie(item) {
  const partes = [item.title, item.description].filter(Boolean);
  if (CFG.cta) partes.push(CFG.cta);
  if (CFG.hashtags) partes.push(CFG.hashtags);
  return partes.join("\n\n");
}

// --------- Publicación ---------

async function publicar(item, imageUrl) {
  const cabeceras = { Authorization: `Bearer ${CFG.token}`, "Content-Type": "application/json" };

  const crear = await conTimeout((signal) =>
    fetch(`${API}/${CFG.uid}/media`, {
      method: "POST",
      headers: cabeceras,
      body: JSON.stringify({ image_url: imageUrl, caption: pie(item) }),
      signal,
    }).then(async (r) => ({ ok: r.ok, status: r.status, text: await r.text() }))
  );
  let creationId;
  try {
    creationId = JSON.parse(crear.text).id;
  } catch {
    /* noop */
  }
  if (!crear.ok || !creationId) {
    throw new PublicarError(`creando el contenedor: HTTP ${crear.status} ${crear.text.slice(0, 400)}`);
  }

  const pub = await conTimeout((signal) =>
    fetch(`${API}/${CFG.uid}/media_publish`, {
      method: "POST",
      headers: cabeceras,
      body: JSON.stringify({ creation_id: creationId }),
      signal,
    }).then(async (r) => ({ ok: r.ok, status: r.status, text: await r.text() }))
  );
  let publishedId;
  try {
    publishedId = JSON.parse(pub.text).id;
  } catch {
    /* noop */
  }
  if (!pub.ok || !publishedId) {
    throw new PublicarError(`publicando: HTTP ${pub.status} ${pub.text.slice(0, 400)}`);
  }
  return publishedId;
}

// --------- Main ---------

async function main() {
  const replacements = replacementsDeEntorno();

  const xml = await conTimeout(async (signal) => {
    const r = await fetch(CFG.feedUrl, { redirect: "follow", headers: { "User-Agent": UA }, signal });
    if (!r.ok) throw new PublicarError(`no se pudo leer el feed (${CFG.feedUrl} → HTTP ${r.status})`);
    return await r.text();
  });

  const items = ordenarPorFechaDesc(parsearFeed(xml));
  if (items.length === 0) {
    console.log("El feed no tiene entradas.");
    return 0;
  }

  const publicados = new Set(await cargarRegistro());

  // El más reciente, no publicado y con imagen utilizable.
  let elegido = null;
  let imagen = "";
  for (const item of items) {
    if (publicados.has(item.guid)) continue;
    const url = await imagenDeItem(item, replacements);
    if (await existeImagen(url)) {
      elegido = item;
      imagen = url;
      break;
    }
  }

  if (!elegido) {
    console.log("Nada nuevo con imagen que publicar.");
    return 0;
  }

  if (DRY_RUN) {
    console.log(`PUBLICARÍA: ${elegido.guid}`);
    console.log(`imagen: ${imagen}`);
    console.log("---");
    console.log(pie(elegido));
    console.log("---");
    return 0;
  }

  const publishedId = await publicar(elegido, imagen);

  const nuevos = [...publicados, elegido.guid];
  await guardarRegistro(nuevos);
  if (process.env.GITHUB_OUTPUT) {
    await appendFile(process.env.GITHUB_OUTPUT, `guid=${elegido.guid}\n`);
    await appendFile(process.env.GITHUB_OUTPUT, `published_id=${publishedId}\n`);
  }

  console.log(`Publicado en Instagram: ${elegido.guid} (media ${publishedId})`);
  return 0;
}

main()
  .then((code) => process.exit(code ?? 0))
  .catch((err) => {
    const msg = err instanceof PublicarError ? err.message : err?.stack || String(err);
    console.error(`ERROR: ${msg}`);
    process.exit(1);
  });
