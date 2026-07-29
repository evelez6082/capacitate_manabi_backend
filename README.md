# Backend FastAPI

Backend inicial para la super BD de inscripciones, Moodle, seguimiento, aprobaciones y diplomas.

## Requisitos

- PostgreSQL corriendo.
- La BD migrada con `outputs/super_bd/migrar_datos.py`.
- Python 3.11+.

## Instalacion

```bash
cd /Users/elize/Documents/Codex/2026-07-28/que/outputs/backend_fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` y coloca la clave real de PostgreSQL.

## Correo de confirmacion

El backend puede enviar un correo automatico cuando una persona completa la preinscripcion publica.

En `.env`, configura SMTP:

```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=tu_correo@gmail.com
SMTP_PASSWORD=tu_app_password
SMTP_FROM_EMAIL=tu_correo@gmail.com
SMTP_FROM_NAME=Capacitate Manabi
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Para Gmail se recomienda usar una clave de aplicacion. Si `SMTP_ENABLED=false` o el servidor SMTP falla, la preinscripcion se guarda igual y la respuesta retorna `correo_enviado: false`.

Si tu proveedor usa SSL directo, normalmente la configuracion cambia a:

```bash
SMTP_PORT=465
SMTP_USE_TLS=false
SMTP_USE_SSL=true
```

## Ejecutar

```bash
uvicorn app.main:app --reload --port 8000
```

Abre:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Endpoints iniciales

- `GET /health`
- `GET /api/resumen`
- `GET /api/personas?q=texto`
- `GET /api/personas/{cedula}`
- `GET /api/personas/{cedula}/trazabilidad`
- `GET /api/personas/{cedula}/estado`
- `GET /api/diplomas?q=texto`
- `GET /api/reportes/aprobados-sin-diploma`
- `GET /api/reportes/aprobados-sin-solicitud-diploma`
- `GET /api/reportes/aprobados-solicitados-sin-diploma`
- `GET /api/reportes/inscritos-sin-aprobar`
- `GET /api/reportes/estudiantes-para-seguimiento`
- `GET /api/reportes/personas-multiples-versiones`
- `GET /api/catalogos/provincias`
- `GET /api/catalogos/cantones?provincia_id=1`
- `GET /api/catalogos/parroquias?canton_id=1`
- `GET /api/catalogos/nacionalidades`
- `GET /api/campanas-inscripcion`
- `POST /api/campanas-inscripcion`
- `GET /api/campanas-inscripcion/{campana_id}/inscripciones`
- `GET /api/usuarios/roles`
- `GET /api/usuarios`
- `GET /api/public/campanas/{slug_publico}`
- `POST /api/public/campanas/{slug_publico}/inscripciones`

## Ejemplo de campana

```bash
curl -X POST http://localhost:8000/api/campanas-inscripcion \
  -H "Content-Type: application/json" \
  -d '{
    "codigo": "liderazgo-espam-001-2026",
    "nombre": "Curso de Liderazgo ESPAM 001-2026",
    "organizacion_origen": "ESPAM"
  }'
```

La respuesta incluye `slug_publico` y `token_publico`, que luego serviran para construir el link publico de inscripcion.

## Integracion con frontend React

El formulario publico debe enviar los datos a:

```text
POST /api/public/campanas/{slug_publico}/inscripciones
```

Ejemplo local:

```bash
curl -X POST http://localhost:8000/api/public/campanas/liderazgo-espam-001-2026/inscripciones \
  -H "Content-Type: application/json" \
  -d '{
    "cedula": "1234567890",
    "fechaNac": "1990-01-01",
    "nombres": "Ana",
    "apellidos": "Alcivar",
    "correo": "ana@example.com",
    "celular": "0999999999",
    "provincia": "Manabi",
    "canton": "Portoviejo",
    "parroquia": "Parroquia urbana",
    "barrio": "Centro",
    "actividad": "Estudio",
    "institucion": "ESPAM",
    "autoidentificacion": "Mestizo/a",
    "genero": "Mujer",
    "nacionalidad": "Ecuatoriana",
    "discapacidad": "No",
    "educacion": "Tercer nivel",
    "acepto": true
  }'
```
