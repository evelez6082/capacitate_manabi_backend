# API de Capacítate Manabí

API FastAPI para autenticación, inscripción, seguimiento académico, aprobaciones y diplomas.

## Requisitos

- Python 3.13.5 (registrado en `.python-version`).
- PostgreSQL 16 con `schema_final.sql` aplicado.
- El repositorio `capacitate_manabi_fullbd` para crear o actualizar la base.

## Desarrollo local

En PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.lock.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

En macOS o Linux:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Edita `.env` antes de iniciar. `DATABASE_URL` debe apuntar a la instancia preparada y
`AUTH_SECRET_KEY` debe ser una cadena aleatoria; nunca reutilices el valor de ejemplo en
un despliegue real.

Los archivos `requirements*.txt` declaran dependencias directas; los archivos
`requirements*.lock.txt` fijan también las transitivas y son los usados para instalar.

Servicios locales:

- API: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs>
- Salud: <http://localhost:8000/health>

## Variables de entorno

`.env.example` contiene todas las opciones admitidas. Las principales son:

| Variable | Propósito |
|---|---|
| `DATABASE_URL` | Conexión PostgreSQL de la API. |
| `AUTH_SECRET_KEY` | Firma de tokens y desafíos; debe ser secreta y única por entorno. |
| `CORS_ORIGINS` | Lista JSON de orígenes permitidos. |
| `CLIENT_IP_HEADER` | Encabezado de IP, solo detrás de un proxy confiable que lo reemplace. |
| `SMTP_*` | Envío opcional de confirmaciones. |
| `RATE_LIMIT_*` | Límites de inscripción por IP, identidad y correo. |

Si SMTP está deshabilitado o falla, la inscripción se conserva y la respuesta indica
`correo_enviado: false`.

## Seguridad de rutas

Las únicas rutas anónimas son `GET /health`, `POST /api/auth/login` y `/api/public/*`.
Las demás exigen `Authorization: Bearer <token>` y validan roles. La inscripción pública
solo crea identidades nuevas: una cédula existente produce `409 Conflict` y no modifica
datos personales.

El formulario público requiere desafío firmado de un solo uso, tiempo mínimo, campo
señuelo y límites persistentes. Las tablas necesarias forman parte de `schema_final.sql`.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

La suite usa el cliente HTTP de FastAPI y una base determinista simulada; no accede a
datos reales.

## Primer usuario administrativo

Con la base inicializada, crea el primer usuario sin exponer la contraseña en el historial
del terminal:

```bash
python scripts/create_admin_user.py --email admin@example.org --name "Administrador" --role admin
```

El comando solicita la contraseña sin mostrarla. También admite la variable temporal
`CAPACITATE_ADMIN_PASSWORD` para automatización desde un gestor de secretos.

## Imagen de despliegue

```bash
docker build -t capacitate-manabi-api .
docker run --rm -p 8000:8000 --env-file .env capacitate-manabi-api
```

La imagen ejecuta la aplicación como usuario sin privilegios. Para levantar el sistema
completo en desarrollo, usa `compose.yaml` del repositorio `capacitate_manabi_fullbd`.

En producción, usa un gestor de secretos, termina TLS en un proxy confiable, restringe
la red de PostgreSQL y ejecuta las migraciones antes de cambiar el tráfico a la nueva
versión.
