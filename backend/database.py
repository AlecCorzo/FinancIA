import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# En Docker se usa PostgreSQL (DATABASE_URL viene del docker-compose).
# Sin la variable, se usa SQLite local para desarrollo y pruebas.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./financia.db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
