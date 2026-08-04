// Publica en Instagram (@elterracampino) el artículo del blog más reciente que
// tenga imagen de portada y que aún no se haya publicado.
//
// Estructura real de ESTE proyecto (no es Astro ni markdown con frontmatter):
//   - Los artículos viven en un manifiesto JSON: data/blog/articulos.json
//     Campos por artículo: { slug, titular, entradilla, tema, fecha, tiene_imagen }
//   - No existe un campo específico de "texto para redes": el pie se compone con
//     titular + entradilla (igual que el publicador Python del repo).
//   - La portada es una URL pública que Meta descarga él mismo:
//       https://elterracampino.es/assets/blog/<slug>.jpg
//     Solo se publica si tiene_imagen === true (Instagram no admite solo texto).
//
// Publicación por Graph API en dos pasos encadenados:
//   1) POST /{IG_USER_ID}/media          { image_url, caption } -> { id: creationId }
//   2) POST /{IG_USER_ID}/media_publish  { creation_id }        -> { id: publishedId }
//
// TRAMPA (documentada por el equipo): el token va SIEMPRE en la cabecera
//   Authorization: Bearer <token>
// nunca en el cuerpo JSON. La documentación de Meta induce a error en esto.
//
// Registro de lo ya publicado: scripts/instagram-posted.json (array JSON de slugs).
// Sin ese registro se republicaría lo mismo en cada ejecución.
//
// Uso:
//   node scripts/publish-instagram.mjs             # publica 1 (el más reciente pendiente)
//   node scripts/publish-instagram.mjs --dry-run   # enseña qué publicaría, sin publicar
//
// Variables de entorno (secrets del repo):
//   META_IG_USER_ID       ID numérico de la cuenta de Instagram de este negocio
//   META_IG_ACCESS_TOKEN  token de Usuario del Sistema (no caduca) con instagram_content_publish

import { readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { appendFile } from "node:fs/promises";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

// Fuente de artículos y registro de publicados.
const ARTICULOS = resolve(ROOT, "data/blog/articulos.json");
const REGISTRO = resolve(ROOT, "scripts/instagram-posted.json");

// El sitio es estático y público: Instagram descarga la imagen de esta URL.
const BASE = "https://elterracampino.es";
const imagenDe = (slug) => `${BASE}/assets/blog/${slug}.jpg`;

// Versión de la Graph API. Meta retira cada versión a los ~2 años: si un día
// empieza a fallar con "Unsupported get request", subir este número.
const GRAPH = "v21.0";
const API = `https://graph.facebook.com/${GRAPH}`;

// Instagram no admite enlaces clicables en el pie: se remite a la bio.
const HASHTAGS =
  "#TierraDeCampos #Palencia #Valladolid #León #Zamora #EspañaVaciada #PueblosDeEspaña";

const TIMEOUT_MS = 60_000;
const DRY_RUN = process.argv.includes("--dry-run");

class PublicarError extends Error {}

function credenciales() {
  const uid = (process.env.META_IG_USER_ID || "").trim();
  const token = (process.env.META_IG_ACCESS_TOKEN || "").trim();
  if (!uid || !token) {
    throw new PublicarError(
      "Faltan META_IG_USER_ID o META_IG_ACCESS_TOKEN (secrets del repo / entorno)."
    );
  }
  return { uid, token };
}

async function cargarArticulos() {
  if (!existsSync(ARTICULOS)) {
    throw new PublicarError(`No existe el manifiesto de artículos: ${ARTICULOS}`);
  }
  const texto = await readFile(ARTICULOS, "utf8");
  const datos = JSON.parse(texto);
  if (!Array.isArray(datos)) {
    throw new PublicarError("data/blog/articulos.json no es un array JSON.");
  }
  return datos;
}

async function cargarRegistro() {
  if (!existsSync(REGISTRO)) return [];
  const datos = JSON.parse(await readFile(REGISTRO, "utf8"));
  if (!Array.isArray(datos)) {
    throw new PublicarError(
      "scripts/instagram-posted.json debe ser un array JSON de slugs."
    );
  }
  return datos;
}

async function guardarRegistro(slugs) {
  // Ordenado alfabéticamente para diffs estables y deterministas.
  const ordenado = [...new Set(slugs)].sort((a, b) => a.localeCompare(b));
  await writeFile(REGISTRO, JSON.stringify(ordenado, null, 2) + "\n", "utf8");
}

// Titular + entradilla + remite a la web. No se inventa nada: solo texto ya
// escrito y revisado en el artículo.
function pieDePublicacion(art) {
  return (
    `${art.titular}\n\n` +
    `${art.entradilla}\n\n` +
    "Lo contamos entero en elterracampino.es — enlace en la bio.\n\n" +
    HASHTAGS
  );
}

// El más reciente, con imagen y con texto para redes, que no esté ya publicado.
function elegirPendiente(articulos, publicados) {
  const ya = new Set(publicados);
  return articulos
    .filter(
      (a) =>
        a &&
        a.slug &&
        !ya.has(a.slug) &&
        a.tiene_imagen === true &&
        typeof a.titular === "string" &&
        a.titular.trim() &&
        typeof a.entradilla === "string" &&
        a.entradilla.trim()
    )
    .sort((a, b) => String(b.fecha || "").localeCompare(String(a.fecha || "")))[0];
}

async function fetchJson(url, opciones) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const r = await fetch(url, { ...opciones, signal: ctrl.signal });
    const texto = await r.text();
    let json;
    try {
      json = texto ? JSON.parse(texto) : {};
    } catch {
      json = { raw: texto };
    }
    return { ok: r.ok, status: r.status, json, texto };
  } finally {
    clearTimeout(t);
  }
}

async function comprobarImagen(url, token) {
  // Comprobar que la imagen existe ANTES de llamar a Meta: si no, la API
  // devuelve un error genérico difícil de interpretar en los logs del Action.
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const r = await fetch(url, { method: "HEAD", redirect: "follow", signal: ctrl.signal });
    if (!r.ok) {
      throw new PublicarError(
        `la imagen no está publicada todavía (${url} → HTTP ${r.status})`
      );
    }
  } finally {
    clearTimeout(t);
  }
}

async function publicar(art, { uid, token }) {
  const image_url = imagenDe(art.slug);
  await comprobarImagen(image_url, token);

  // El token SIEMPRE en la cabecera, nunca en el cuerpo.
  const cabeceras = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  // Paso 1: crear el contenedor de media.
  const crear = await fetchJson(`${API}/${uid}/media`, {
    method: "POST",
    headers: cabeceras,
    body: JSON.stringify({ image_url, caption: pieDePublicacion(art) }),
  });
  if (!crear.ok || !crear.json.id) {
    throw new PublicarError(
      `creando el contenedor: HTTP ${crear.status} ${crear.texto.slice(0, 400)}`
    );
  }
  const creationId = crear.json.id;

  // Paso 2: publicar el contenedor.
  const pub = await fetchJson(`${API}/${uid}/media_publish`, {
    method: "POST",
    headers: cabeceras,
    body: JSON.stringify({ creation_id: creationId }),
  });
  if (!pub.ok || !pub.json.id) {
    throw new PublicarError(
      `publicando: HTTP ${pub.status} ${pub.texto.slice(0, 400)}`
    );
  }
  return pub.json.id;
}

async function escribirOutput(slug) {
  // Para que el workflow sepa que hubo publicación y commitee el registro.
  if (process.env.GITHUB_OUTPUT) {
    await appendFile(process.env.GITHUB_OUTPUT, `slug=${slug}\n`);
  }
}

async function main() {
  const articulos = await cargarArticulos();
  const publicados = await cargarRegistro();

  const art = elegirPendiente(articulos, publicados);
  if (!art) {
    console.log("Nada nuevo que publicar en Instagram.");
    return 0;
  }

  if (DRY_RUN) {
    console.log(`PUBLICARÍA: ${art.slug}`);
    console.log(`imagen: ${imagenDe(art.slug)}`);
    console.log("---");
    console.log(pieDePublicacion(art));
    console.log("---");
    return 0;
  }

  const { uid, token } = credenciales();
  const publishedId = await publicar(art, { uid, token });

  publicados.push(art.slug);
  await guardarRegistro(publicados);
  await escribirOutput(art.slug);

  console.log(`Publicado en Instagram: ${art.slug} (media ${publishedId})`);
  return 0;
}

main()
  .then((code) => process.exit(code ?? 0))
  .catch((err) => {
    const msg = err instanceof PublicarError ? err.message : (err?.stack || String(err));
    console.error(`ERROR: ${msg}`);
    process.exit(1);
  });
