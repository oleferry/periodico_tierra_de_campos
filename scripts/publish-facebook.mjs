// Publica en la Página de Facebook la entrada más reciente de un feed RSS que
// aún no se haya publicado. Genérico y dirigido por el feed, mismo patrón que
// scripts/publish-instagram.mjs: el MISMO script vale para varios sitios,
// solo cambia la configuración por variables de entorno.
//
// Publicación por Graph API en un solo paso (más simple que Instagram, que
// necesita contenedor + publish):
//   POST /{PAGE_ID}/feed   { message, link }   -> { id: postId }
//
// Facebook arma su propia tarjeta de previsualización descargando el `link` y
// leyendo sus etiquetas Open Graph (og:title, og:description, og:image) — por
// eso NO se resuelve ni se sube ninguna imagen aquí, a diferencia de Instagram.
// Para que la tarjeta salga bien, la página enlazada tiene que traer esas
// etiquetas (ver sitegen/build.py:shell, parámetros og_title/image/url).
//
// TRAMPA (misma que Instagram, documentada allí): el token va SIEMPRE en la
// cabecera Authorization: Bearer, nunca en el cuerpo JSON.
//
// Sin duplicados: el registro (FB_REGISTRY, array JSON de guids ya
// publicados) se commitea desde el workflow. Sin él se republicaría lo mismo.
// Es un registro APARTE del de Instagram (scripts/instagram-posted.json):
// cada plataforma lleva su propio ritmo de publicación.
//
// -------- Configuración por entorno --------
//   FB_PAGE_ID        (req) ID numérico de la Página de Facebook de ESTE sitio
//   FB_ACCESS_TOKEN   (req) Token de Página (Page Access Token) — lo más
//                      cómodo es un token de Usuario del Sistema de Meta
//                      Business Suite con permiso pages_manage_posts, que no
//                      caduca (mismo Usuario del Sistema que ya usa Instagram,
//                      solo hace falta añadirle este permiso sobre la Página).
//   FEED_URL          (req) URL del RSS del sitio (p. ej. https://elterracampino.es/feed.xml)
//   FB_CTA            (opc) llamada a la acción añadida al final del mensaje
//   FB_REGISTRY       (opc) ruta del registro (por defecto scripts/facebook-posted.json)
//
// Uso:
//   node scripts/publish-facebook.mjs            # publica 1 (el más reciente pendiente)
//   node scripts/publish-facebook.mjs --dry-run  # enseña qué publicaría, sin publicar

import { readFile, writeFile, appendFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const DRY_RUN = process.argv.includes("--dry-run");
const GRAPH = "v21.0";
const API = `https://graph.facebook.com/${GRAPH}`;
const TIMEOUT_MS = 60_000;
const UA = "facebook-rss-bot/1.0";

class PublicarError extends Error {}

function env(nombre, req = false, def = "") {
  const v = (process.env[nombre] ?? "").trim();
  if (!v && req) throw new PublicarError(`Falta la variable de entorno ${nombre}`);
  return v || def;
}

const CFG = {
  pageId: env("FB_PAGE_ID", true),
  token: env("FB_ACCESS_TOKEN", true),
  feedUrl: env("FEED_URL", true),
  cta: env("FB_CTA"),
  registry: resolve(process.cwd(), env("FB_REGISTRY", false, "scripts/facebook-posted.json")),
};

async function conTimeout(fn) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    return await fn(ctrl.signal);
  } finally {
    clearTimeout(t);
  }
}

// --------- Parseo de RSS (sin dependencias, igual que publish-instagram.mjs) ---------

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

function parsearFeed(xml) {
  const texto = xml.replace(/\r\n/g, "\n"); // por si el feed viene de Windows
  const items = [...texto.matchAll(/<item\b[\s\S]*?<\/item>/gi)].map((m) => m[0]);
  return items.map((b) => {
    const link = tag(b, "link");
    return {
      title: tag(b, "title"),
      link,
      guid: tag(b, "guid") || link,
      description: tag(b, "description"),
      pubDate: tag(b, "pubDate"),
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

async function existeUrl(url) {
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

// --------- Mensaje ---------
// A propósito NO se repite la URL dentro del texto: el parámetro `link` ya
// hace que Facebook pinte la tarjeta clicable con el enlace, y meterlo también
// como texto suele duplicar el enlace visible en el post.

function mensaje(item) {
  const partes = [item.title, item.description].filter(Boolean);
  if (CFG.cta) partes.push(CFG.cta);
  return partes.join("\n\n");
}

// --------- Publicación ---------

async function publicar(item) {
  const r = await conTimeout((signal) =>
    fetch(`${API}/${CFG.pageId}/feed`, {
      method: "POST",
      headers: { Authorization: `Bearer ${CFG.token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ message: mensaje(item), link: item.link }),
      signal,
    }).then(async (resp) => ({ ok: resp.ok, status: resp.status, text: await resp.text() }))
  );
  let postId;
  try {
    postId = JSON.parse(r.text).id;
  } catch {
    /* noop */
  }
  if (!r.ok || !postId) {
    throw new PublicarError(`publicando: HTTP ${r.status} ${r.text.slice(0, 400)}`);
  }
  return postId;
}

// --------- Main ---------

async function main() {
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

  // El más reciente, no publicado y con el enlace vivo.
  let elegido = null;
  for (const item of items) {
    if (publicados.has(item.guid)) continue;
    if (await existeUrl(item.link)) {
      elegido = item;
      break;
    }
  }

  if (!elegido) {
    console.log("Nada nuevo que publicar.");
    return 0;
  }

  if (DRY_RUN) {
    console.log(`PUBLICARÍA: ${elegido.guid}`);
    console.log(`link: ${elegido.link}`);
    console.log("---");
    console.log(mensaje(elegido));
    console.log("---");
    return 0;
  }

  const postId = await publicar(elegido);

  const nuevos = [...publicados, elegido.guid];
  await guardarRegistro(nuevos);
  if (process.env.GITHUB_OUTPUT) {
    await appendFile(process.env.GITHUB_OUTPUT, `guid=${elegido.guid}\n`);
    await appendFile(process.env.GITHUB_OUTPUT, `post_id=${postId}\n`);
  }

  console.log(`Publicado en Facebook: ${elegido.guid} (post ${postId})`);
  return 0;
}

main()
  .then((code) => process.exit(code ?? 0))
  .catch((err) => {
    const msg = err instanceof PublicarError ? err.message : err?.stack || String(err);
    console.error(`ERROR: ${msg}`);
    process.exit(1);
  });
