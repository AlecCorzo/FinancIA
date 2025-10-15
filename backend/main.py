from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import Movimiento, MovimientoCreate, MovimientoResponse

app = FastAPI(title="FinancIA Backend")

Base.metadata.create_all(bind=engine)

# Dependencia para obtener sesión
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/movimientos", response_model=MovimientoResponse)
def crear_movimiento(movimiento: MovimientoCreate, db: Session = Depends(get_db)):
    nuevo = Movimiento(**movimiento.dict())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@app.get("/balance")
def obtener_balance(db: Session = Depends(get_db)):
    ingresos = db.query(Movimiento).filter(Movimiento.tipo == "ingreso").all()
    gastos = db.query(Movimiento).filter(Movimiento.tipo == "gasto").all()
    total_ingresos = sum(m.monto for m in ingresos)
    total_gastos = sum(m.monto for m in gastos)
    balance = total_ingresos - total_gastos
    return {"balance_actual": balance}
