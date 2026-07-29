from datetime import date, datetime

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


class PublicRegistrationCreate(BaseModel):
    cedula: str = Field(min_length=10, max_length=20)
    fechaNac: date | None = None
    nombres: str = Field(min_length=2, max_length=120)
    apellidos: str = Field(min_length=2, max_length=120)
    correo: str = Field(min_length=5, max_length=180)
    celular: str = Field(min_length=7, max_length=30)
    provincia_id: int | None = None
    provincia: str | None = None
    canton_id: int | None = None
    canton: str | None = None
    parroquia_id: int | None = None
    parroquia: str | None = None
    barrio: str | None = None
    actividad: str | None = None
    institucion: str | None = None
    autoidentificacion: str | None = None
    genero: str | None = None
    orientacion: str | None = None
    nacionalidad: str | None = None
    discapacidad: str | None = None
    tipoDiscapacidad: str | None = None
    educacion: str | None = None
    acepto: bool = False
