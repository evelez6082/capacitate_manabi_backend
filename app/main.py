from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import campanas, catalogos, diplomas, health, personas, reportes, resumen, usuarios


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend FastAPI para inscripciones, seguimiento, aprobaciones y diplomas.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(resumen.router)
    app.include_router(personas.router)
    app.include_router(diplomas.router)
    app.include_router(reportes.router)
    app.include_router(catalogos.router)
    app.include_router(campanas.router)
    app.include_router(usuarios.router)
    return app


app = create_app()
