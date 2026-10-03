"""Convierte lo que dice el usuario (voz o texto) en un movimiento validado.

Flujo: audio -> ffmpeg (WAV) -> Gemini (JSON estructurado) -> normalizar() -> MovimientoCreate
El LLM solo propone; normalizar() decide qué se guarda.
"""
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

from categorias import CATEGORIAS_GASTO, CATEGORIAS_INGRESO, normalizar_categoria
from schemas import MovimientoCreate

log = logging.getLogger(__name__)

PROMPT_SISTEMA = f"""Eres el asistente de registro de FinancIA, una app de finanzas personales en Colombia.
El usuario te dice, por voz o por escrito, un ingreso o un gasto. Extrae UN solo movimiento.

Reglas:
- Los montos están en pesos colombianos (COP). Devuelve el monto como número, sin puntos, comas ni símbolos.
- Expresiones colombianas: "mil", "lucas" y "barras" equivalen a 1.000 (25 lucas = 25000).
  "palo" o "millón" equivale a 1.000.000 (medio palo = 500000). "luca y media" = 1500.
- tipo es "gasto" si pagó, compró, gastó o le cobraron; "ingreso" si recibió, le pagaron, vendió o ganó.
- categoria para gastos: {", ".join(sorted(CATEGORIAS_GASTO))}.
  categoria para ingresos: {", ".join(sorted(CATEGORIAS_INGRESO))}.
- descripcion: frase corta de máximo 8 palabras, en español.
- transcripcion: lo que dijo el usuario, palabra por palabra.
- Si el mensaje no describe un ingreso o gasto, o no tiene un monto claro, responde es_movimiento=false
  y explica en motivo qué faltó, en una frase dirigida al usuario. En ese caso usa tipo="", monto=0,
  categoria="" y descripcion="".
- Si es un movimiento válido, usa motivo="".
"""


class ExtraccionLLM(BaseModel):
    """Esquema que se le exige a Gemini (sin valores por defecto: la API no los admite)."""

    es_movimiento: bool
    transcripcion: str
    tipo: str
    monto: float
    categoria: str
    descripcion: str
    motivo: str


@dataclass
class Resultado:
    transcripcion: str
    movimiento: MovimientoCreate | None
    motivo: str = ""


class Interprete(Protocol):
    def extraer(self, *, texto: str | None = None, audio_wav: bytes | None = None) -> ExtraccionLLM: ...


def normalizar(ext: ExtraccionLLM) -> Resultado:
    """Red de seguridad determinista sobre la respuesta del LLM."""
    transcripcion = ext.transcripcion.strip()

    def rechazo(motivo: str) -> Resultado:
        return Resultado(transcripcion=transcripcion, movimiento=None, motivo=motivo)

    if not ext.es_movimiento:
        return rechazo(ext.motivo.strip() or "No identifiqué un ingreso o un gasto con un monto.")

    tipo = ext.tipo.strip().lower()
    if tipo not in ("ingreso", "gasto"):
        return rechazo("No pude saber si es un ingreso o un gasto. Intenta decirlo de nuevo.")

    monto = round(ext.monto, 2)
    if monto <= 0:
        return rechazo("No identifiqué un monto válido. Di la cantidad, por ejemplo: 25 mil pesos.")

    try:
        movimiento = MovimientoCreate(
            tipo=tipo,
            monto=monto,
            categoria=normalizar_categoria(ext.categoria, tipo),
            descripcion=ext.descripcion.strip()[:200] or None,
        )
    except ValidationError:
        return rechazo("El monto está fuera del rango permitido.")

    return Resultado(transcripcion=transcripcion, movimiento=movimiento)


def a_wav(datos: bytes) -> bytes:
    """Convierte el audio del navegador (webm/ogg/mp4) a WAV mono de 16 kHz."""
    proceso = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
         "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
        input=datos, capture_output=True, timeout=60,
    )
    if proceso.returncode != 0 or not proceso.stdout:
        raise ValueError("No se pudo convertir el audio: " + proceso.stderr.decode(errors="ignore")[:200])
    return proceso.stdout


class GeminiInterprete:
    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        from google import genai

        clave = api_key or os.getenv("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")
        self.client = genai.Client(api_key=clave)
        self.modelo = modelo or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    def extraer(self, *, texto: str | None = None, audio_wav: bytes | None = None) -> ExtraccionLLM:
        from google.genai import types

        if audio_wav:
            contenido = [
                types.Part.from_bytes(data=audio_wav, mime_type="audio/wav"),
                "Este audio es el mensaje del usuario.",
            ]
        elif texto:
            contenido = [f"Mensaje del usuario: {texto}"]
        else:
            raise ValueError("Se necesita texto o audio.")

        respuesta = self.client.models.generate_content(
            model=self.modelo,
            contents=contenido,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT_SISTEMA,
                response_mime_type="application/json",
                response_schema=ExtraccionLLM,
                temperature=0,
            ),
        )
        return ExtraccionLLM.model_validate_json(respuesta.text)
