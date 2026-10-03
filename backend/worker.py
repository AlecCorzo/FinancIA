"""Worker: consume solicitudes de RabbitMQ, las interpreta con Gemini y guarda el movimiento."""
import base64
import json
import logging

from database import Base, SessionLocal, engine
from interprete import Interprete, a_wav, normalizar
from models import Movimiento, Solicitud

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


def procesar(mensaje: dict, interprete: Interprete, crear_sesion=SessionLocal) -> None:
    db = crear_sesion()
    try:
        solicitud = db.get(Solicitud, mensaje["solicitud_id"])
        # Idempotencia: si el mensaje llega dos veces, no se registra dos veces.
        if solicitud is None or solicitud.estado != "pendiente":
            return
        solicitud.estado = "procesando"
        db.commit()

        try:
            if mensaje.get("audio_b64"):
                wav = a_wav(base64.b64decode(mensaje["audio_b64"]))
                extraccion = interprete.extraer(audio_wav=wav)
            else:
                extraccion = interprete.extraer(texto=mensaje["texto"])
            resultado = normalizar(extraccion)
        except Exception as e:
            log.exception("Error procesando la solicitud %s", solicitud.id)
            solicitud.estado = "error"
            if "503" in str(e) or "UNAVAILABLE" in str(e) or "high demand" in str(e):
                solicitud.mensaje = "Los servidores de Gemini están temporalmente saturados. Intenta de nuevo en unos segundos."
            else:
                solicitud.mensaje = "No se pudo procesar la solicitud. Intenta de nuevo."
            db.commit()
            return

        solicitud.transcripcion = resultado.transcripcion or mensaje.get("texto")
        if resultado.movimiento is None:
            solicitud.estado = "rechazada"
            solicitud.mensaje = resultado.motivo
        else:
            movimiento = Movimiento(**resultado.movimiento.model_dump(), origen=solicitud.origen)
            db.add(movimiento)
            db.flush()
            solicitud.movimiento_id = movimiento.id
            solicitud.estado = "completada"
        db.commit()
        log.info("Solicitud %s -> %s", solicitud.id, solicitud.estado)
    finally:
        db.close()


def main() -> None:
    from cola import COLA, conectar
    from interprete import GeminiInterprete

    Base.metadata.create_all(bind=engine)
    interprete = GeminiInterprete()
    conexion = conectar()
    canal = conexion.channel()
    canal.queue_declare(queue=COLA, durable=True)
    canal.basic_qos(prefetch_count=1)  # Una solicitud a la vez por worker

    def al_recibir(canal, metodo, propiedades, cuerpo):
        try:
            procesar(json.loads(cuerpo), interprete)
        except Exception:
            log.exception("Mensaje inválido")
        finally:
            canal.basic_ack(delivery_tag=metodo.delivery_tag)

    canal.basic_consume(queue=COLA, on_message_callback=al_recibir)
    log.info("Worker escuchando la cola %s", COLA)
    canal.start_consuming()


if __name__ == "__main__":
    main()
