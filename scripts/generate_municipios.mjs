// Genera la base maestra de municipios de Tierra de Campos (191, delimitación Wikipedia).
// Salidas:
//   - data/municipios_tierra_de_campos.csv   (lista completa + enriquecimiento de los 12 pilotos)
//   - database/seed_comarca.sql              (INSERT de los 191 en la tabla municipalities)
//
// Fuente de la lista: https://es.wikipedia.org/wiki/Tierra_de_Campos (2026-07-11).
// Enriquecimiento (población 2025, coordenadas) de los 12 pilotos:
//   docs/estudio-fuentes-y-viabilidad.md.
// Los municipios no piloto quedan con población/coordenadas vacías a propósito
// (principio del proyecto: si no está verificado, "no disponible", no se inventa).
//
// Regenerar con:  node scripts/generate_municipios.mjs

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const byProvince = {
  Palencia: [
    'Abarca de Campos', 'Abia de las Torres', 'Amayuelas de Arriba', 'Ampudia', 'Amusco',
    'Arconada', 'Autilla del Pino', 'Autillo de Campos', 'Baquerín de Campos', 'Becerril de Campos',
    'Belmonte de Campos', 'Boada de Campos', 'Boadilla de Rioseco', 'Boadilla del Camino', 'Bárcena de Campos',
    'Calzada de los Molinos', 'Capillas', 'Cardeñosa de Volpejera', 'Carrión de los Condes', 'Castil de Vela',
    'Castrillo de Villavega', 'Castromocho', 'Cervatos de la Cueza', 'Cisneros', 'Frechilla',
    'Frómista', 'Fuentes de Nava', 'Fuentes de Valdepero', 'Grijota', 'Guaza de Campos',
    'Husillos', 'Itero de la Vega', 'Lantadilla', 'Lomas de Campos', 'Manquillos',
    'Marcilla de Campos', 'Mazariegos', 'Mazuecos de Valdeginate', 'Meneses de Campos', 'Monzón de Campos',
    'Moratinos', 'Nogal de las Huertas', 'Osornillo', 'Osorno', 'Palencia',
    'Paredes de Nava', 'Pedraza de Campos', 'Perales', 'Piña de Campos', 'Población de Arroyo',
    'Población de Campos', 'Pozo de Urama', 'Requena de Campos', 'Revenga de Campos', 'Ribas de Campos',
    'Riberos de la Cueza', 'San Cebrián de Campos', 'San Mamés de Campos', 'San Román de la Cuba', 'Santa Cecilia del Alcor',
    'Santoyo', 'Torremormojón', 'Támara de Campos', 'Valde-Ucieza', 'Valle del Retortillo',
    'Villacidaler', 'Villada', 'Villaherreros', 'Villalcázar de Sirga', 'Villalcón',
    'Villalobón', 'Villamartín de Campos', 'Villamoronta', 'Villamuera de la Cueza', 'Villanueva del Rebollar',
    'Villarmentero de Campos', 'Villarramiel', 'Villasarracino', 'Villaturde', 'Villaumbrales',
    'Villerías de Campos', 'Villoldo', 'Villovieco',
  ],
  Valladolid: [
    'Aguilar de Campos', 'Barcial de la Loma', 'Becilla de Valderaduey', 'Berrueces', 'Bolaños de Campos',
    'Bustillo de Chaves', 'Cabezón de Valderaduey', 'Cabreros del Monte', 'Castrobol', 'Castroponce de Valderaduey',
    'Ceinos de Campos', 'Cuenca de Campos', 'Fontihoyuelo', 'Gatón de Campos', 'Gordaliza de la Loma',
    'Herrín de Campos', 'La Unión de Campos', 'Mayorga', 'Medina de Rioseco', 'Melgar de Abajo',
    'Melgar de Arriba', 'Monasterio de Vega', 'Montealegre de Campos', 'Moral de la Reina', 'Morales de Campos',
    'Palazuelo de Vedija', 'Pozuelo de la Orden', 'Quintanilla del Molar', 'Roales de Campos', 'Saelices de Mayorga',
    'San Pedro de Latarce', 'Santa Eufemia del Arroyo', 'Santervás de Campos', 'Tamariz de Campos', 'Tordehumos',
    'Urones de Castroponce', 'Valdunquillo', 'Valverde de Campos', 'Vega de Ruiponce', 'Villabaruz de Campos',
    'Villabrágima', 'Villacarralón', 'Villacid de Campos', 'Villafrades de Campos', 'Villafrechós',
    'Villagarcía de Campos', 'Villagómez la Nueva', 'Villalán de Campos', 'Villalba de la Loma', 'Villalón de Campos',
    'Villamuriel de Campos', 'Villanueva de la Condesa', 'Villanueva de los Caballeros', 'Villanueva de San Mancio', 'Villardefrades',
    'Villavicencio de los Caballeros',
  ],
  Zamora: [
    'Belver de los Montes', 'Castronuevo de los Arcos', 'Castroverde de Campos', 'Cañizo de Campos', 'Cerecinos de Campos',
    'Cotanes del Monte', 'Granja de Moreruela', 'Prado', 'Quintanilla del Monte', 'Quintanilla del Olmo',
    'Revellinos', 'San Agustín del Pozo', 'San Esteban del Molar', 'San Martín de Valderaduey', 'San Miguel del Valle',
    'Tapioles', 'Valdescorriel', 'Vega de Villalobos', 'Vidayanes', 'Villafáfila',
    'Villalba de la Lampreana', 'Villalobos', 'Villalpando', 'Villamayor de Campos', 'Villanueva del Campo',
    'Villar de Fallaves', 'Villárdiga', 'Villarrín de Campos',
  ],
  León: [
    'Almanza', 'Bercianos del Real Camino', 'El Burgo Ranero', 'Calzada del Coto', 'Campazas',
    'Castilfalé', 'Castrotierra de Valmadrigal', 'Cea', 'Escobar de Campos', 'Fuentes de Carbajal',
    'Gordaliza del Pino', 'Gordoncillo', 'Grajal de Campos', 'Izagre', 'Joarilla de las Matas',
    'Matanza de los Oteros', 'Sahagún', 'Valderas', 'Valdemora', 'Vallecillo',
    'Valverde-Enrique', 'Villabraz', 'Villamol', 'Villazanzo de Valderaduey',
  ],
};

// 12 municipios piloto: población 2025 y coordenadas verificadas (estudio de fuentes).
const pilots = {
  'Medina de Rioseco': { priority: 1, population: 4617, lat: 41.883056, lon: -5.042778 },
  'Sahagún': { priority: 1, population: 2380, lat: 42.371111, lon: -5.033056 },
  'Carrión de los Condes': { priority: 1, population: 1997, lat: 42.338889, lon: -4.601944 },
  'Paredes de Nava': { priority: 1, population: 1927, lat: 42.152778, lon: -4.694444 },
  'Valderas': { priority: 1, population: 1479, lat: 42.077500, lon: -5.442500 },
  'Villalón de Campos': { priority: 1, population: 1473, lat: 42.098449, lon: -5.034713 },
  'Villalpando': { priority: 1, population: 1433, lat: 41.864722, lon: -5.413056 },
  'Mayorga': { priority: 1, population: 1354, lat: 42.166630, lon: -5.262700 },
  'Villada': { priority: 1, population: 863, lat: 42.250560, lon: -4.966940 },
  'Villarramiel': { priority: 1, population: 782, lat: 42.042500, lon: -4.913056 },
  'Becerril de Campos': { priority: 1, population: 737, lat: 42.108333, lon: -4.641667 },
  'Fuentes de Nava': { priority: 1, population: 581, lat: 42.083056, lon: -4.783056 },
};

const slugify = (name) =>
  name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

const sqlStr = (v) => (v === null || v === undefined ? 'null' : `'${String(v).replace(/'/g, "''")}'`);
const sqlNum = (v) => (v === null || v === undefined ? 'null' : String(v));

const rows = [];
for (const [province, names] of Object.entries(byProvince)) {
  for (const name of names) {
    const p = pilots[name];
    rows.push({
      name,
      slug: slugify(name),
      province,
      comarca: 'Tierra de Campos',
      priority: p ? p.priority : 3,
      status: p ? 'piloto' : 'comarca',
      population: p ? p.population : null,
      lat: p ? p.lat : null,
      lon: p ? p.lon : null,
    });
  }
}

// Chequeo de slugs duplicados (nunique en la BD).
const seen = new Map();
for (const r of rows) {
  if (seen.has(r.slug)) throw new Error(`Slug duplicado: ${r.slug} (${r.name} y ${seen.get(r.slug)})`);
  seen.set(r.slug, r.name);
}

// --- CSV ---
const csvHeader = 'name,slug,province,comarca,priority,status,population,lat,lon';
const csvBody = rows
  .map((r) => {
    const cell = (v) => {
      if (v === null || v === undefined) return '';
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return [r.name, r.slug, r.province, r.comarca, r.priority, r.status, r.population, r.lat, r.lon]
      .map(cell)
      .join(',');
  })
  .join('\n');
mkdirSync(resolve(root, 'data'), { recursive: true });
writeFileSync(resolve(root, 'data/municipios_tierra_de_campos.csv'), `${csvHeader}\n${csvBody}\n`, 'utf8');

// --- SQL seed comarca ---
const header = `-- El Terracampino — seed de la comarca completa (191 municipios, delimitación Wikipedia)
-- GENERADO por scripts/generate_municipios.mjs — no editar a mano.
-- Ejecutar DESPUÉS de schema.sql. Es seguro ejecutarlo después de seed_piloto.sql:
-- el "on conflict (slug) do nothing" respeta las filas piloto ya cargadas (con su
-- prioridad 1, población y coordenadas), y solo añade el resto de la comarca.
-- Fuente de la lista: https://es.wikipedia.org/wiki/Tierra_de_Campos

insert into municipalities (name, slug, province, comarca, priority, population, lat, lon, active, notes) values`;

const values = rows
  .map((r) => {
    const notes = r.status === 'piloto' ? 'Municipio piloto' : 'Comarca (base geográfica Wikipedia)';
    return `  (${sqlStr(r.name)}, ${sqlStr(r.slug)}, ${sqlStr(r.province)}, ${sqlStr(r.comarca)}, ${r.priority}, ${sqlNum(r.population)}, ${sqlNum(r.lat)}, ${sqlNum(r.lon)}, true, ${sqlStr(notes)})`;
  })
  .join(',\n');

writeFileSync(
  resolve(root, 'database/seed_comarca.sql'),
  `${header}\n${values}\non conflict (slug) do nothing;\n`,
  'utf8',
);

console.log(`OK: ${rows.length} municipios (${Object.values(byProvince).map((a) => a.length).join('+')})`);
console.log(`Pilotos: ${rows.filter((r) => r.status === 'piloto').length}`);
