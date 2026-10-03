import base64

import pytest
from fastapi.testclient import TestClient

import interprete
import worker
from interprete import ExtraccionLLM
from main import app, get_publicador

publicados = []


class InterpreteFalso:
    """Simula a Gemini para probar el flujo completo sin llamar a la API."""

    def __init__(self, respuesta: ExtraccionLLM):
        self.respuesta = respuesta
        self.recibido = None

    def extraer(self, *, texto=None, audio_wav=None):
        self.recibido = texto or audio_wav
        return self.respuesta


@pytest.fixture
def cliente():
    publicados.clear()
    app.dependency_overrides[get_publicador] = lambda: publicados.append
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def gasto(monto=25000):
    return ExtraccionLLM(es_movimiento=True, transcripcion="gasté 25 lucas en almuerzo", tipo="gasto",
                         monto=monto, categoria="alimentacion", descripcion="Almuerzo", motivo="")


def test_texto_se_encola_y_el_worker_lo_registra(cliente):
    r = cliente.post("/texto", json={"texto": "gasté 25 lucas en almuerzo"})
    assert r.status_code == 202
    assert r.json()["estado"] == "pendiente"
    assert len(publicados) == 1

    falso = InterpreteFalso(gasto())
    worker.procesar(publicados[0], falso)
    assert falso.recibido == "gasté 25 lucas en almuerzo"

    s = cliente.get(f"/solicitudes/{r.json()['id']}").json()
    assert s["estado"] == "completada"
    assert s["movimiento"]["monto"] == 25000
    assert s["movimiento"]["origen"] == "texto"
    assert cliente.get("/balance").json() == {"ingresos": 0, "gastos": 25000, "balance": -25000}


def test_mensaje_duplicado_no_registra_dos_veces(cliente):
    r = cliente.post("/texto", json={"texto": "gasté 25 lucas"})
    falso = InterpreteFalso(gasto())
    worker.procesar(publicados[0], falso)
    worker.procesar(publicados[0], falso)
    assert len(cliente.get("/movimientos").json()) == 1
    assert cliente.get(f"/solicitudes/{r.json()['id']}").json()["estado"] == "completada"


def test_mensaje_sin_monto_se_rechaza(cliente):
    r = cliente.post("/texto", json={"texto": "hola, ¿cómo estás?"})
    respuesta = ExtraccionLLM(es_movimiento=False, transcripcion="hola, ¿cómo estás?", tipo="", monto=0,
                              categoria="", descripcion="", motivo="No mencionaste un ingreso o un gasto.")
    worker.procesar(publicados[0], InterpreteFalso(respuesta))
    s = cliente.get(f"/solicitudes/{r.json()['id']}").json()
    assert s["estado"] == "rechazada"
    assert s["mensaje"] == "No mencionaste un ingreso o un gasto."
    assert cliente.get("/movimientos").json() == []


def test_error_del_modelo_queda_registrado(cliente):
    r = cliente.post("/texto", json={"texto": "gasté 10 mil"})

    class Falla:
        def extraer(self, **_):
            raise RuntimeError("Gemini no responde")

    worker.procesar(publicados[0], Falla())
    assert cliente.get(f"/solicitudes/{r.json()['id']}").json()["estado"] == "error"


def test_voz_convierte_el_audio_y_registra(cliente, monkeypatch):
    monkeypatch.setattr(worker, "a_wav", lambda datos: b"WAV:" + datos)
    r = cliente.post("/voz", files={"audio": ("grabacion", b"audio-falso", "audio/webm;codecs=opus")})
    assert r.status_code == 202
    assert base64.b64decode(publicados[0]["audio_b64"]) == b"audio-falso"

    falso = InterpreteFalso(gasto())
    worker.procesar(publicados[0], falso)
    assert falso.recibido == b"WAV:audio-falso"
    s = cliente.get(f"/solicitudes/{r.json()['id']}").json()
    assert s["estado"] == "completada" and s["movimiento"]["origen"] == "voz"


def test_archivo_que_no_es_audio_se_rechaza(cliente):
    r = cliente.post("/voz", files={"audio": ("x.txt", b"hola", "text/plain")})
    assert r.status_code == 415


def test_cola_caida_responde_503(cliente):
    def caida(_):
        raise ConnectionError("RabbitMQ caído")

    app.dependency_overrides[get_publicador] = lambda: caida
    r = cliente.post("/texto", json={"texto": "gasté 10 mil"})
    assert r.status_code == 503


def test_movimiento_manual_y_balance(cliente):
    assert cliente.post("/movimientos", json={"tipo": "ingreso", "monto": 1000000, "categoria": "Salario"}).status_code == 201
    assert cliente.post("/movimientos", json={"tipo": "gasto", "monto": 0}).status_code == 422
    assert cliente.get("/balance").json()["balance"] == 1000000


def test_conversion_real_de_audio_con_ffmpeg():
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg no está instalado")
    webm = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                           "-c:a", "libopus", "-f", "webm", "pipe:1"], capture_output=True).stdout
    wav = interprete.a_wav(webm)
    assert wav[:4] == b"RIFF"
