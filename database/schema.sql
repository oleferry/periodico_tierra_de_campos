-- Tierra de Campos al Día — esquema MVP PostgreSQL/Supabase
-- Ejecutar en Supabase SQL editor o PostgreSQL compatible.

create extension if not exists "uuid-ossp";

create type source_type as enum (
  'municipal_plenary',
  'municipal_news',
  'electronic_office',
  'bop',
  'bocyl',
  'weather',
  'agriculture',
  'sports',
  'agenda',
  'employment',
  'commerce',
  'other'
);

create type source_method as enum ('api', 'rss', 'html', 'pdf', 'csv', 'manual');
create type reliability_level as enum ('high', 'medium', 'low');
create type document_status as enum ('new', 'processed', 'error', 'discarded');
create type piece_status as enum ('draft', 'needs_review', 'approved', 'published', 'rejected', 'error');
create type risk_level as enum ('low', 'medium', 'high');
create type match_status as enum ('scheduled', 'played', 'postponed', 'cancelled', 'unknown');

create table municipalities (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  slug text not null unique,
  province text not null,
  comarca text default 'Tierra de Campos',
  population integer,
  lat numeric(9,6),
  lon numeric(9,6),
  priority integer default 3,
  active boolean default true,
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table sources (
  id uuid primary key default uuid_generate_v4(),
  municipality_id uuid references municipalities(id) on delete set null,
  name text not null,
  slug text not null unique,
  type source_type not null,
  method source_method not null,
  url text not null,
  frequency text not null default 'daily',
  reliability reliability_level default 'medium',
  requires_review_default boolean default true,
  active boolean default true,
  robots_checked boolean default false,
  legal_notes text,
  parser_name text,
  config jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table scrape_runs (
  id uuid primary key default uuid_generate_v4(),
  source_id uuid references sources(id) on delete cascade,
  started_at timestamptz default now(),
  finished_at timestamptz,
  status text not null default 'running',
  documents_found integer default 0,
  documents_new integer default 0,
  error_type text,
  error_message text,
  logs jsonb default '[]'::jsonb
);

create table documents (
  id uuid primary key default uuid_generate_v4(),
  source_id uuid references sources(id) on delete set null,
  municipality_id uuid references municipalities(id) on delete set null,
  title text,
  source_type source_type,
  url_original text not null,
  file_url text,
  published_at date,
  detected_at timestamptz default now(),
  hash text not null,
  raw_text text,
  clean_text text,
  extraction_method text,
  confidence reliability_level default 'medium',
  status document_status default 'new',
  requires_review boolean default true,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  unique(source_id, hash)
);

create table pieces (
  id uuid primary key default uuid_generate_v4(),
  document_id uuid references documents(id) on delete set null,
  municipality_id uuid references municipalities(id) on delete set null,
  vertical text not null,
  title text not null,
  lead text,
  body text not null,
  short_summary text,
  telegram_text text,
  newsletter_text text,
  factual_json jsonb,
  risk risk_level default 'medium',
  status piece_status default 'draft',
  source_url text,
  source_date date,
  generated_by text,
  prompt_version text,
  published_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table editorial_reviews (
  id uuid primary key default uuid_generate_v4(),
  piece_id uuid references pieces(id) on delete cascade,
  reviewer text,
  decision text not null,
  notes text,
  reviewed_at timestamptz default now()
);

create table teams (
  id uuid primary key default uuid_generate_v4(),
  municipality_id uuid references municipalities(id) on delete set null,
  name text not null,
  sport text not null,
  category text,
  competition text,
  federation_url text,
  active boolean default true,
  notes text,
  created_at timestamptz default now()
);

create table matches (
  id uuid primary key default uuid_generate_v4(),
  team_id uuid references teams(id) on delete set null,
  home_team text not null,
  away_team text not null,
  competition text,
  match_at timestamptz,
  home_score integer,
  away_score integer,
  status match_status default 'unknown',
  venue text,
  source_url text,
  hash text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table alerts (
  id uuid primary key default uuid_generate_v4(),
  municipality_id uuid references municipalities(id) on delete set null,
  type text not null,
  title text not null,
  body text not null,
  severity risk_level default 'low',
  starts_at timestamptz,
  ends_at timestamptz,
  source_url text,
  published boolean default false,
  created_at timestamptz default now()
);

create table subscribers (
  id uuid primary key default uuid_generate_v4(),
  email text,
  telegram_user_id text,
  municipality_id uuid references municipalities(id) on delete set null,
  interests text[] default '{}',
  active boolean default true,
  created_at timestamptz default now()
);

create index idx_sources_type on sources(type);
create index idx_documents_detected_at on documents(detected_at desc);
create index idx_documents_municipality on documents(municipality_id);
create index idx_pieces_status on pieces(status);
create index idx_pieces_vertical on pieces(vertical);
create index idx_matches_match_at on matches(match_at desc);
create index idx_alerts_type on alerts(type);
