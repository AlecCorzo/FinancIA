from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from database import Base  # Un solo Base para que create_all cree todas las tablas


def ahora():
    return datetime.now(timezone.utc)


class Movimiento(Base):
    __tablename__ = "movimientos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(10), nullable=False)  # "ingreso" o "gasto"
    # Numeric y no Float: el dinero no debe tener errores de redondeo binario.
    monto = Column(Numeric(14, 2), nullable=False)
    categoria = Column(String(30), nullable=False, default="otros")
    descripcion = Column(String(200), nullable=True)
    origen = Column(String(10), nullable=False, default="manual")  # manual, voz o texto
    fecha = Column(DateTime(timezone=True), default=ahora, index=True)


class Solicitud(Base):
    """Una petición de registro por voz o texto que procesa el worker de forma asíncrona."""

    __tablename__ = "solicitudes"

    id = Column(String(36), primary_key=True)  # UUID
    # pendiente -> procesando -> completada | rechazada | error
    estado = Column(String(15), nullable=False, default="pendiente")
    origen = Column(String(10), nullable=False)  # voz o texto
    transcripcion = Column(Text, nullable=True)
    mensaje = Column(Text, nullable=True)  # Motivo del rechazo o del error
    movimiento_id = Column(Integer, ForeignKey("movimientos.id"), nullable=True)
    creada = Column(DateTime(timezone=True), default=ahora)
    actualizada = Column(DateTime(timezone=True), default=ahora, onupdate=ahora)
