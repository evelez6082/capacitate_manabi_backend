from datetime import date, datetime
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.validation import is_valid_ecuadorian_id


class CampaignCreate(BaseModel):
    curso_id: int = Field(default=1)
    curso_version_id: int | None = None
    codigo: str = Field(min_length=3, max_length=120)
    nombre: str = Field(min_length=3, max_length=240)
    organizacion_origen: str | None = None
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CampaignCreate":
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin <= self.fecha_inicio:
            raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio")
        return self


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
    form_token: str = Field(min_length=40, max_length=512)
    website: str | None = Field(default=None, max_length=200)
    cedula: str = Field(min_length=10, max_length=10)
    fechaNac: date
    nombres: str = Field(min_length=2, max_length=120)
    apellidos: str = Field(min_length=2, max_length=120)
    correo: str = Field(min_length=5, max_length=180)
    celular: str = Field(min_length=9, max_length=16)
    provincia_id: int = Field(gt=0)
    provincia: str | None = Field(default=None, max_length=120)
    canton_id: int = Field(gt=0)
    canton: str | None = Field(default=None, max_length=120)
    parroquia_id: int = Field(gt=0)
    parroquia: str | None = Field(default=None, max_length=120)
    barrio: str = Field(min_length=2, max_length=180)
    actividad: Literal["Trabajo", "Estudio", "Trabajo y estudio", "Ninguno"]
    institucion: str | None = Field(default=None, min_length=2, max_length=180)
    autoidentificacion: Literal["Mestizo/a", "Indígena", "Cholo/a", "Montuvio/a", "Afrodescendiente", "Blanco/a"]
    genero: Literal["Mujer", "Hombre", "No binario", "Prefiero no decirlo", "Otros"]
    orientacion: Literal["Heterosexual", "Homosexual", "Bisexual", "Pansexual", "Asexual", "Prefiero no decirlo"]
    nacionalidad_id: int = Field(gt=0)
    nacionalidad: str | None = Field(default=None, max_length=120)
    discapacidad: Literal["Sí", "No"]
    tipoDiscapacidad: str | None = Field(default=None, min_length=2, max_length=180)
    educacion: Literal["Básica", "Bachillerato", "Tercer nivel", "Cuarto nivel", "Sin estudios"]
    acepto: bool = False

    @field_validator("cedula", mode="before")
    @classmethod
    def validate_cedula(cls, value: object) -> str:
        normalized = str(value or "").strip()
        if not is_valid_ecuadorian_id(normalized):
            raise ValueError("La cédula ecuatoriana no es válida")
        return normalized

    @field_validator("nombres", "apellidos", "barrio", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        return " ".join(str(value or "").split())

    @field_validator("nombres", "apellidos")
    @classmethod
    def validate_person_name(cls, value: str) -> str:
        if not all(character.isalpha() or character in " '-" for character in value):
            raise ValueError("Los nombres y apellidos solo pueden contener letras, espacios, apóstrofes y guiones")
        return value

    @field_validator("correo", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        normalized = str(value or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("El correo electrónico no es válido")
        return normalized

    @field_validator("celular", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str:
        normalized = re.sub(r"[\s()-]", "", str(value or ""))
        if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
            raise ValueError("El celular debe incluir código de país y entre 8 y 15 dígitos")
        return normalized

    @field_validator("fechaNac")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if value > today or value < date(1900, 1, 1) or age < 12:
            raise ValueError("La fecha de nacimiento debe corresponder a una persona de al menos 12 años")
        return value

    @field_validator(
        "institucion",
        "tipoDiscapacidad",
        "provincia",
        "canton",
        "parroquia",
        "nacionalidad",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        normalized = " ".join(str(value or "").split())
        return normalized or None

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> "PublicRegistrationCreate":
        if self.actividad != "Ninguno" and (not self.institucion or len(self.institucion) < 2):
            raise ValueError("La institución es obligatoria cuando trabajas o estudias")
        if self.actividad == "Ninguno":
            self.institucion = None
        if self.discapacidad == "Sí" and (not self.tipoDiscapacidad or len(self.tipoDiscapacidad) < 2):
            raise ValueError("Debes indicar el tipo de discapacidad")
        if self.discapacidad == "No":
            self.tipoDiscapacidad = None
        if not self.acepto:
            raise ValueError("Debes aceptar los términos para inscribirte")
        return self
