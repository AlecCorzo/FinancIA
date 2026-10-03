from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from categorias import normalizar_categoria


class MovimientoCreate(BaseModel):
    tipo: Literal["ingreso", "gasto"]
    monto: float = Field(gt=0, le=10_000_000_000)
    categoria: str = "otros"
    descripcion: str | None = Field(default=None, max_length=200)

    @field_validator("categoria")
    @classmethod
    def validar_categoria(cls, valor: str) -> str:
        return normalizar_categoria(valor)


class MovimientoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    monto: float
    categoria: str
    descripcion: str | None
    origen: str
    fecha: datetime


class TextoEntrada(BaseModel):
    texto: str = Field(min_length=2, max_length=300)


class SolicitudResponse(BaseModel):
    id: str
    estado: str
    origen: str
    transcripcion: str | None = None
    mensaje: str | None = None
    movimiento: MovimientoResponse | None = None


class Balance(BaseModel):
    ingresos: float
    gastos: float
    balance: float
