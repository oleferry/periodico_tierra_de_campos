# Publicación automática en Instagram

Cada investigación nueva del blog se publica sola en **@elterracampino**, con su
imagen y su titular. Lo hace un GitHub Action, igual que el build diario: no
depende de que haya ningún ordenador encendido.

## Cómo funciona

```
build diario (06:10 UTC) → la web publica el artículo y su imagen
        ↓
Action "Instagram" (07:45 UTC) → coge la más reciente sin publicar
        ↓
Graph API: 1) crear contenedor con image_url  2) media_publish
        ↓
data/instagram_publicados.json ← se commitea para no repetir
```

- **Una publicación por vuelta**, la más reciente pendiente. Si hay varias en
  cola, van saliendo un día tras otro (ni spam ni roza los límites de Instagram,
  que son del orden de 25 al día por cuenta).
- **Instagram descarga la imagen de una URL pública** (no se sube el fichero).
  Por eso se usa la del propio artículo, `…/assets/blog/<slug>.jpg`, que ya está
  publicada en la web.
- **Los artículos sin imagen se saltan**: Instagram no admite solo texto. Es el
  caso del homenaje a Mariano Haro, publicado sin foto a propósito (no se
  generan retratos de IA de personas reales). Si se quiere en Instagram, hay que
  ponerle una imagen real primero.
- El pie usa el **titular y la entradilla ya escritos y revisados** — no se
  redacta nada nuevo ni se inventa. Como Instagram no admite enlaces clicables
  en el pie, remite a "enlace en la bio": la bio debe apuntar a elterracampino.es.

## Credenciales (secrets del repo)

| Secret | Qué es |
|---|---|
| `IG_USER_ID` | Id de la cuenta de Instagram (se saca con `GET /{PAGE_ID}?fields=instagram_business_account`) |
| `IG_ACCESS_TOKEN` | Token con permiso `instagram_content_publish` |

Requisitos de la cuenta: **Profesional** (Empresa o Creador) y **vinculada a la
Página de Facebook**. Con la app de Meta en modo desarrollo basta, siempre que
seas administrador de ambas — no hace falta revisión de Meta para publicar en
cuentas propias.

**Sobre la caducidad del token** (el fallo más típico de estas automatizaciones):
un token de Página de larga duración caduca a los ~60 días y entonces el Action
empieza a fallar en silencio salvo por la ejecución en rojo. Lo recomendable es
un **token de Usuario del Sistema** (Meta Business Suite → Configuración →
Usuarios del sistema), que no caduca.

## Operar

```
python -m scripts.publicar_instagram --dry-run           # qué publicaría
python -m scripts.publicar_instagram                     # publica una
python -m scripts.publicar_instagram --marcar-existentes # marca el atrasado
                                                         # como ya publicado
```

- **Lanzarlo a mano**: pestaña Actions → "Instagram" → *Run workflow* (tiene una
  casilla `dry_run` para probar sin publicar).
- **Si no quieres que salgan los reportajes antiguos** uno por día al activarlo,
  ejecuta antes `--marcar-existentes` y commitea el registro: a partir de ahí
  solo saldrán los nuevos.

## Qué NO hace

- No publica las noticias del día a día ni los plenos, solo las
  investigaciones/reportajes del blog (igual que el feed RSS).
- No publica stories ni carruseles, solo una imagen.
- No responde comentarios ni mensajes.
