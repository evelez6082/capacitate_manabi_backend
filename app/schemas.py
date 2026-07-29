from datetime import datetime

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    curso_id: int = Field(default=1)
    curso_version_id: int | None = None
    codigo: str = Field(min_length=3, max_length=120)
    nombre: str = Field(min_length=3, max_length=240)
    organizacion_origen: str | None = None
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None


class CampaignOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    organizacion_origen: str | None = None
    slug_publico: str
    token_publico: str
    estado: str
    created_at: datetime | None = None


class Pagination(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
