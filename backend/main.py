import base64
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import cola
from database import Base, SessionLocal, engine
from models import Movimiento, Solicitud
from schemas import Balance, MovimientoCreate, MovimientoResponse, SolicitudResponse, TextoEntrada

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # 5 MB, unos 30 segundos de voz sobran
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="FinancIA", lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_publicador():
    return cola.publicar


def a_respuesta(solicitud: Solicitud, db: Session) -> SolicitudResponse:
    movimiento = db.get(Movimiento, solicitud.movimiento_id) if solicitud.movimiento_id else None
    return SolicitudResponse(
        id=solicitud.id,
        estado=solicitud.estado,
        origen=solicitud.origen,
        transcripcion=solicitud.transcripcion,
        mensaje=solicitud.mensaje,
        movimiento=MovimientoResponse.model_validate(movimiento) if movimiento else None,
    )


def encolar(db: Session, publicar, origen: str, datos: dict) -> SolicitudResponse:
    solicitud = Solicitud(id=str(uuid.uuid4()), estado="pendiente", origen=origen)
    db.add(solicitud)
    db.commit()
    try:
        publicar({"solicitud_id": solicitud.id, **datos})
    except Exception:
        solicitud.estado = "error"
        solicitud.mensaje = "El servicio de procesamiento no está disponible."
        db.commit()
        raise HTTPException(503, "El servicio de procesamiento no está disponible. Intenta en unos segundos.")
    return a_respuesta(solicitud, db)


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(STATIC / "index.html")


@app.post("/movimientos", response_model=MovimientoResponse, status_code=201)
def crear_movimiento(movimiento: MovimientoCreate, db: Session = Depends(get_db)):
    nuevo = Movimiento(**movimiento.model_dump(), origen="manual")
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/movimientos", response_model=list[MovimientoResponse])
def listar_movimientos(limite: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return db.query(Movimiento).order_by(Movimiento.fecha.desc(), Movimiento.id.desc()).limit(limite).all()


@app.get("/balance", response_model=Balance)
def obtener_balance(db: Session = Depends(get_db)):
    # La suma se hace en la base de datos, no trayendo todos los registros a Python.
    ingresos, gastos = db.query(
        func.coalesce(func.sum(case((Movimiento.tipo == "ingreso", Movimiento.monto), else_=0)), 0),
        func.coalesce(func.sum(case((Movimiento.tipo == "gasto", Movimiento.monto), else_=0)), 0),
    ).one()
    return Balance(ingresos=float(ingresos), gastos=float(gastos), balance=float(ingresos) - float(gastos))


@app.post("/voz", response_model=SolicitudResponse, status_code=202)
async def registrar_por_voz(
    audio: UploadFile = File(...), db: Session = Depends(get_db), publicar=Depends(get_publicador)
):
    tipo = (audio.content_type or "").split(";")[0]
    if not (tipo.startswith("audio/") or tipo == "video/webm"):
        raise HTTPException(415, "El archivo debe ser de audio.")
    datos = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(datos) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "El audio es demasiado largo. Graba menos de 30 segundos.")
    if not datos:
        raise HTTPException(400, "El audio está vacío.")
    return encolar(db, publicar, "voz", {"audio_b64": base64.b64encode(datos).decode()})


@app.post("/texto", response_model=SolicitudResponse, status_code=202)
def registrar_por_texto(entrada: TextoEntrada, db: Session = Depends(get_db), publicar=Depends(get_publicador)):
    return encolar(db, publicar, "texto", {"texto": entrada.texto.strip()})


@app.get("/solicitudes/{solicitud_id}", response_model=SolicitudResponse)
def consultar_solicitud(solicitud_id: str, db: Session = Depends(get_db)):
    solicitud = db.get(Solicitud, solicitud_id)
    if solicitud is None:
        raise HTTPException(404, "Solicitud no encontrada.")
    return a_respuesta(solicitud, db)
