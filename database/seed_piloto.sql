-- El Terracampino — seed de FUENTES de los municipios piloto + fuentes globales.
-- Ejecutar DESPUÉS de schema.sql Y de seed_comarca.sql (que carga los municipios).
-- Orden completo:  schema.sql  →  seed_comarca.sql  →  seed_piloto.sql
--
-- Los municipios (los 191, con los 12 pilotos enriquecidos) los inserta seed_comarca.sql.
-- Aquí solo se insertan las fuentes (sources), referenciando cada municipio por slug.
--
-- Nota de normalización (decisión 2026-07-05):
-- source_method solo admite ('api','rss','html','pdf','csv','manual') y
-- reliability_level solo ('high','medium','low'), pero los YAML de origen usan valores
-- compuestos ('api_csv_web','html_pdf','html_dynamic','medium_high'). Se normaliza al
-- valor de enum más cercano y se guarda el original en sources.config->>'method_detail'.
--
-- Nota de verificación (estudio 2026-07-11): la sede electrónica y los plenos/actas no
-- se verificaron para ningún piloto. Los 6 primeros conservan las rutas del pack original;
-- los 6 añadidos (Carrión, Paredes de Nava, Villalpando, Becerril, Fuentes de Nava,
-- Villarramiel) solo llevan la web municipal verificada. Su sede/plenos quedan en cola de
-- verificación manual (verify_pending en config/municipios_piloto.yml); no se inventan URLs.

-- 1. Fuentes municipales de los 6 pilotos originales (web + plenos + sede)

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
  ((select id from municipalities where slug = 'valderas'), 'Valderas - Sede electrónica', 'valderas-sede', 'electronic_office', 'html', 'https://aytovalderas.sedelectronica.es/', 'daily', 'high', true, true, null),

-- 2. Fuentes de los 6 pilotos añadidos (2026-07-11): solo web municipal verificada.
--    Sede y plenos pendientes de verificación manual (no se insertan URLs inventadas).

  ((select id from municipalities where slug = 'carrion-de-los-condes'), 'Carrión de los Condes - Web municipal', 'carrion-de-los-condes-web', 'municipal_news', 'html', 'https://carriondeloscondes.org/', 'daily', 'high', true, true, 'Sede y plenos pendientes de verificación manual'),
  ((select id from municipalities where slug = 'paredes-de-nava'), 'Paredes de Nava - Web municipal', 'paredes-de-nava-web', 'municipal_news', 'html', 'https://paredesdenava.es/', 'daily', 'high', true, true, 'Sede y plenos pendientes de verificación manual'),
  ((select id from municipalities where slug = 'villalpando'), 'Villalpando - Web municipal', 'villalpando-web', 'municipal_news', 'html', 'https://villalpando.es/', 'daily', 'high', true, true, 'Sede y plenos pendientes de verificación manual'),
  ((select id from municipalities where slug = 'becerril-de-campos'), 'Becerril de Campos - Web municipal', 'becerril-de-campos-web', 'municipal_news', 'html', 'https://becerrildecampos.es/', 'daily', 'high', true, true, 'Sede y plenos pendientes de verificación manual'),
  ((select id from municipalities where slug = 'fuentes-de-nava'), 'Fuentes de Nava - Web municipal', 'fuentes-de-nava-web', 'municipal_news', 'html', 'https://fuentesdenava.es/', 'daily', 'high', true, true, 'Sede y plenos pendientes de verificación manual'),
  ((select id from municipalities where slug = 'villarramiel'), 'Villarramiel - Web municipal', 'villarramiel-web', 'municipal_news', 'html', 'https://villarramiel.es/', 'daily', 'high', true, true, 'Sede y plenos pendientes de verificación manual')
on conflict (slug) do nothing;

-- 3. Fuentes globales (no ligadas a un municipio concreto)

insert into sources (municipality_id, name, slug, type, method, url, frequency, reliability, requires_review_default, active, config) values
  (null, 'AEMET OpenData', 'aemet-opendata', 'weather', 'api', 'https://opendata.aemet.es/dist/index.html', 'twice_daily', 'high', false, true, '{}'::jsonb),
  (null, 'AEMET predicción municipios', 'aemet-prediccion-municipios', 'weather', 'api', 'https://opendata.aemet.es/centrodedescargas/productosAEMET', 'twice_daily', 'high', false, true, '{}'::jsonb),
  (null, 'InfoRiego', 'inforiego', 'agriculture', 'api', 'https://www.inforiego.org/opencms/opencms/info_meteo/index.html', 'daily', 'high', false, true, '{"method_detail": "api_csv_web"}'::jsonb),
  (null, 'BOCYL Datos Abiertos', 'bocyl-datos-abiertos', 'bocyl', 'api', 'https://analisis.datosabiertos.jcyl.es/explore/dataset/bocyl/api/', 'daily', 'high', true, true, '{}'::jsonb),
  -- Ojo: el BOP de Valladolid NO tiene RSS operativo. La página /rss-bop es ayuda, y el
  -- feed que ella misma documenta (/rss/) devuelve 404 (verificado 2026-07-10). Se scrapea
  -- el sumario HTML de /ultimobop, permitido por robots.txt.
  (null, 'BOP Valladolid — Último BOP', 'bop-valladolid', 'bop', 'html', 'https://bop.sede.diputaciondevalladolid.es/ultimobop', 'daily', 'high', true, true, '{"rss_descartado": "https://bop.sede.diputaciondevalladolid.es/rss/ devuelve 404 (verificado 2026-07-10)"}'::jsonb),
  (null, 'BOP Palencia', 'bop-palencia', 'bop', 'pdf', 'https://www.diputaciondepalencia.es/servicios/boletin-oficial-provincia', 'daily', 'high', true, true, '{"method_detail": "html_pdf"}'::jsonb),
  (null, 'BOP León', 'bop-leon', 'bop', 'pdf', 'https://bop.dipuleon.es/publica/buscador-anuncios/', 'daily', 'medium', true, true, '{"method_detail": "html_pdf", "reliability_detail": "medium_high"}'::jsonb),
  (null, 'BOP Zamora', 'bop-zamora', 'bop', 'pdf', 'https://www.diputaciondezamora.es/opencms/servicios/BOP/busqueda-en-el-bop/', 'daily', 'high', true, true, '{"method_detail": "html_pdf"}'::jsonb),
  (null, 'RFCYLF resultados', 'rfcylf-resultados', 'sports', 'html', 'https://www.rfcylf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120', 'weekend_monday', 'medium', false, true, '{"method_detail": "html_dynamic", "reliability_detail": "medium_high"}'::jsonb),
  (null, 'FBCYL competiciones', 'fbcyl-competiciones', 'sports', 'html', 'https://www.fbcyl.es/buscar_competicion', 'weekly', 'medium', false, true, '{}'::jsonb)
on conflict (slug) do nothing;
