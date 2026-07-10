-- Corrección: el BOP de Valladolid no tiene RSS operativo.
--
-- El seed original registraba la fuente como method='rss' apuntando a
-- https://bop.sede.diputaciondevalladolid.es/rss-bop . Verificado el 2026-07-10:
--   · /rss-bop  → HTTP 200 pero es text/html (página de ayuda "Acceda al BOP desde
--                 su lector de noticias"), no un feed.
--   · /rss/     → HTTP 404 (es el feed que la propia página de ayuda documenta).
-- La vía real es el sumario HTML de /ultimobop, que lista cada anuncio como
-- <li class="un_anuncio"> con emisor, título, PDF y CVE. robots.txt lo permite.
--
-- Ejecutar una vez en el SQL Editor. Idempotente.

update sources
set
  name   = 'BOP Valladolid — Último BOP',
  slug   = 'bop-valladolid',
  method = 'html',
  url    = 'https://bop.sede.diputaciondevalladolid.es/ultimobop',
  config = coalesce(config, '{}'::jsonb)
           || '{"rss_descartado": "https://bop.sede.diputaciondevalladolid.es/rss/ devuelve 404 (verificado 2026-07-10)"}'::jsonb,
  updated_at = now()
where slug = 'bop-valladolid-rss';
