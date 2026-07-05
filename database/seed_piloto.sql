-- Tierra de Campos al Día — seed de municipios piloto y fuentes
-- Ejecutar DESPUÉS de schema.sql en el mismo proyecto Supabase/Postgres.
-- Generado a partir de config/municipios_piloto.yml y config/fuentes_globales.yml.
--
-- Nota de normalización (decisión 2026-07-05):
-- El enum source_method solo admite ('api','rss','html','pdf','csv','manual') y
-- reliability_level solo admite ('high','medium','low'), pero los YAML de origen
-- usan valores compuestos ('api_csv_web', 'html_pdf', 'html_dynamic', 'medium_high').
-- Se normalizan al valor más cercano del enum y se conserva el valor original del
-- YAML en sources.config->>'method_detail' para no perder el matiz.

-- 1. Municipios piloto (prioridad 1)

insert into municipalities (name, slug, province, comarca, priority, active, notes) values
  ('Mayorga', 'mayorga', 'Valladolid', 'Tierra de Campos', 1, true, 'Municipio piloto'),
  ('Villalón de Campos', 'villalon-de-campos', 'Valladolid', 'Tierra de Campos', 1, true, 'Municipio piloto'),
  ('Villada', 'villada', 'Palencia', 'Tierra de Campos', 1, true, 'Municipio piloto'),
  ('Medina de Rioseco', 'medina-de-rioseco', 'Valladolid', 'Tierra de Campos', 1, true, 'Municipio piloto'),
  ('Sahagún', 'sahagun', 'León', 'Tierra de Campos', 1, true, 'Municipio piloto'),
  ('Valderas', 'valderas', 'León', 'Tierra de Campos', 1, true, 'Municipio piloto')
on conflict (slug) do nothing;

-- 2. Fuentes municipales (web, sede electrónica, plenos) por municipio piloto

insert into sources (municipality_id, name, slug, type, method, url, frequency, reliability, requires_review_default, active, legal_notes) values
  ((select id from municipalities where slug = 'mayorga'), 'Mayorga - Web municipal', 'mayorga-web', 'municipal_news', 'html', 'https://mayorga.ayuntamientosdevalladolid.es/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'mayorga'), 'Mayorga - Plenos', 'mayorga-plenos', 'municipal_plenary', 'html', 'https://mayorga.ayuntamientosdevalladolid.es/el-ayuntamiento/organizacion-municipal/plenos-municipales', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'mayorga'), 'Mayorga - Sede electrónica', 'mayorga-sede', 'electronic_office', 'html', 'https://mayorga.sedelectronica.es/', 'daily', 'high', true, true, null),

  ((select id from municipalities where slug = 'villalon-de-campos'), 'Villalón de Campos - Web municipal', 'villalon-de-campos-web', 'municipal_news', 'html', 'https://villalondecampos.ayuntamientosdevalladolid.es/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'villalon-de-campos'), 'Villalón de Campos - Plenos', 'villalon-de-campos-plenos', 'municipal_plenary', 'html', 'https://villalondecampos.ayuntamientosdevalladolid.es/el-ayuntamiento/organizacion-municipal/plenos-municipales', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'villalon-de-campos'), 'Villalón de Campos - Sede electrónica', 'villalon-de-campos-sede', 'electronic_office', 'html', 'https://villalondecampos.sedelectronica.es/', 'daily', 'high', true, true, null),

  ((select id from municipalities where slug = 'villada'), 'Villada - Web municipal', 'villada-web', 'municipal_news', 'html', 'https://villada.es/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'villada'), 'Villada - Actas de pleno', 'villada-plenos', 'municipal_plenary', 'html', 'https://villada.es/categoria/ayuntamiento/actas-de-pleno/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'villada'), 'Villada - Sede electrónica', 'villada-sede', 'electronic_office', 'html', 'https://villada.sedelectronica.es/', 'daily', 'high', true, true, null),

  ((select id from municipalities where slug = 'medina-de-rioseco'), 'Medina de Rioseco - Web municipal', 'medina-de-rioseco-web', 'municipal_news', 'html', 'https://medinaderioseco.org/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'medina-de-rioseco'), 'Medina de Rioseco - Plenos', 'medina-de-rioseco-plenos', 'municipal_plenary', 'html', 'https://medinaderioseco.org/organizacion-municipal/plenos-municipales/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'medina-de-rioseco'), 'Medina de Rioseco - Sede electrónica', 'medina-de-rioseco-sede', 'electronic_office', 'html', 'https://medinaderioseco.sedelectronica.es/', 'daily', 'high', true, true, null),

  ((select id from municipalities where slug = 'sahagun'), 'Sahagún - Web municipal', 'sahagun-web', 'municipal_news', 'html', 'https://www.aytosahagun.es/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'sahagun'), 'Sahagún - Normativa municipal', 'sahagun-normativa', 'municipal_plenary', 'html', 'https://www.aytosahagun.es/ayuntamiento/normativa-municipal/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'sahagun'), 'Sahagún - Sede electrónica', 'sahagun-sede', 'electronic_office', 'html', 'https://sahagun.sedelectronica.es/', 'daily', 'high', true, true, null),

  ((select id from municipalities where slug = 'valderas'), 'Valderas - Web municipal', 'valderas-web', 'municipal_news', 'html', 'https://www.aytovalderas.es/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'valderas'), 'Valderas - Normativa municipal', 'valderas-normativa', 'municipal_plenary', 'html', 'https://www.aytovalderas.es/ayuntamiento/normativa-municipal/', 'daily', 'high', true, true, null),
  ((select id from municipalities where slug = 'valderas'), 'Valderas - Sede electrónica', 'valderas-sede', 'electronic_office', 'html', 'https://aytovalderas.sedelectronica.es/', 'daily', 'high', true, true, null)
on conflict (slug) do nothing;

-- 3. Fuentes globales (no ligadas a un municipio concreto)

insert into sources (municipality_id, name, slug, type, method, url, frequency, reliability, requires_review_default, active, config) values
  (null, 'AEMET OpenData', 'aemet-opendata', 'weather', 'api', 'https://opendata.aemet.es/dist/index.html', 'twice_daily', 'high', false, true, '{}'::jsonb),
  (null, 'AEMET predicción municipios', 'aemet-prediccion-municipios', 'weather', 'api', 'https://opendata.aemet.es/centrodedescargas/productosAEMET', 'twice_daily', 'high', false, true, '{}'::jsonb),
  (null, 'InfoRiego', 'inforiego', 'agriculture', 'api', 'https://www.inforiego.org/opencms/opencms/info_meteo/index.html', 'daily', 'high', false, true, '{"method_detail": "api_csv_web"}'::jsonb),
  (null, 'BOCYL Datos Abiertos', 'bocyl-datos-abiertos', 'bocyl', 'api', 'https://analisis.datosabiertos.jcyl.es/explore/dataset/bocyl/api/', 'daily', 'high', true, true, '{}'::jsonb),
  (null, 'BOP Valladolid RSS', 'bop-valladolid-rss', 'bop', 'rss', 'https://bop.sede.diputaciondevalladolid.es/rss-bop', 'daily', 'high', true, true, '{}'::jsonb),
  (null, 'BOP Palencia', 'bop-palencia', 'bop', 'pdf', 'https://www.diputaciondepalencia.es/servicios/boletin-oficial-provincia', 'daily', 'high', true, true, '{"method_detail": "html_pdf"}'::jsonb),
  (null, 'BOP León', 'bop-leon', 'bop', 'pdf', 'https://bop.dipuleon.es/publica/buscador-anuncios/', 'daily', 'medium', true, true, '{"method_detail": "html_pdf", "reliability_detail": "medium_high"}'::jsonb),
  (null, 'BOP Zamora', 'bop-zamora', 'bop', 'pdf', 'https://www.diputaciondezamora.es/opencms/servicios/BOP/busqueda-en-el-bop/', 'daily', 'high', true, true, '{"method_detail": "html_pdf"}'::jsonb),
  (null, 'RFCYLF resultados', 'rfcylf-resultados', 'sports', 'html', 'https://www.rfcylf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120', 'weekend_monday', 'medium', false, true, '{"method_detail": "html_dynamic", "reliability_detail": "medium_high"}'::jsonb),
  (null, 'FBCYL competiciones', 'fbcyl-competiciones', 'sports', 'html', 'https://www.fbcyl.es/buscar_competicion', 'weekly', 'medium', false, true, '{}'::jsonb)
on conflict (slug) do nothing;
