from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from pydantic import BaseModel

Base = declarative_base()

class Movimiento(Base):
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)      # ingreso o gasto
    monto = Column(Float, nullable=False)
    categoria = Column(String, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

# --- Modelos Pydantic ---
class MovimientoCreate(BaseModel):
    tipo: str
    monto: float
    categoria: str | None = None

class MovimientoResponse(MovimientoCreate):
    id: int
    fecha: datetime

    class Config:
        from_attributes = True

