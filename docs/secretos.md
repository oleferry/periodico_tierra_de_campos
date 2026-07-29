# Mapa de secretos y configuración

**Este documento NO contiene ningún valor.** Es solo el mapa: qué credencial
existe, para qué sirve y **dónde está configurada**. Los **valores** (tokens,
claves, contraseñas) van en tu **gestor de contraseñas** (Bitwarden, KeePassXC…),
nunca aquí ni en ningún fichero del repo.

Regla: cuando generes o rotes un token, apúntalo en el gestor **y** actualízalo
en todos los sitios de la columna "Dónde se configura".

## Tokens y claves (secretos — guardar en el gestor)

| Nombre | Para qué | Dónde se configura |
|---|---|---|
| `ANTHROPIC_API_KEY` | Redacción con IA (Claude) | GitHub Actions · `.env` local |
| `OPENAI_API_KEY` | Generación de imágenes (portadas, banners) | `.env` local |
| `SUPABASE_SERVICE_ROLE_KEY` | Almacén de fotos, esquelas, archivo, comentarios | Vercel · GitHub Actions · Railway · `.env` |
| `SUPABASE_ANON_KEY` | Acceso de cliente a Supabase | `.env` local |
| `DATABASE_URL` | Cadena de conexión a la base de datos (lleva credenciales) | `.env` local |
| `AEMET_API_KEY` | Datos de AEMET | `.env` local |
| `TELEGRAM_BOT_TOKEN` | Bot de Telegram (fotos, esquelas, chivatazos) | Railway · `.env` |
| `MAILERLITE_API_KEY` | Alta en la newsletter | Vercel · `.env` — **anota de qué cuenta de MailerLite es** |

## Configuración (no secreto, pero necesario)

| Nombre | Para qué | Dónde se configura |
|---|---|---|
| `SUPABASE_URL` | URL del proyecto Supabase | Vercel · GitHub Actions · Railway · `.env` |
| `MAILERLITE_GROUP_ID` | Grupo donde entran los suscriptores (dispara la bienvenida) | Vercel |
| `TELEGRAM_CHANNEL_ID` | Canal donde publica el bot | Railway · `.env` |
| `ADMIN_TELEGRAM_ID` | Tu id de Telegram; habilita el bloc de notas privado del bot | Railway · `.env` |
| `LLM_PROVIDER` / `LLM_MODEL` | Qué modelo de IA usar | GitHub Actions · `.env` |
| `APP_TIMEZONE` · `SCRAPER_USER_AGENT` · `REVIEW_REQUIRED_BY_DEFAULT` | Ajustes del sitio | `.env` |

## Accesos (usuario/contraseña — guardar en el gestor)

Plataformas: **Vercel**, **Railway**, **Supabase**, **GitHub**, **MailerLite**,
**Dondominio** (DNS), **OpenAI**, **Anthropic**.
Redes: **Facebook**, **Instagram**, **WhatsApp**, **Telegram** (vía @BotFather).

> Para cada una, guarda en el gestor: usuario/email, contraseña, y si tiene 2FA,
> los códigos de recuperación. Anota **con qué cuenta/email** entras a cada
> plataforma — evita el lío de "esta clave era de otra cuenta".

## Dónde se gestiona cada entorno (para actualizarlos)

- **Vercel** → proyecto `periodico-tierra-de-campos` → Settings → Environment
  Variables. (Cifradas; no se vuelven a mostrar. Tras cambiar una, **redeploy**.)
- **GitHub Actions** → repositorio → Settings → Secrets and variables → Actions.
- **Railway** → servicio del bot → Variables.
- **`.env` local** → en la raíz del proyecto. Está en `.gitignore` (verificado):
  **nunca** se sube a git. Es tu copia de trabajo, no una bóveda ni un backup.
