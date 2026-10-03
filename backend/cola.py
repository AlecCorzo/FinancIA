"""Conexión con RabbitMQ: la API publica solicitudes y el worker las consume."""
import json
import logging
import os
import time

import pika

log = logging.getLogger(__name__)
COLA = "financia.solicitudes"


def conectar(intentos: int = 15, espera: float = 3.0) -> pika.BlockingConnection:
    url = os.getenv("RABBITMQ_URL", "amqp://admin:admin@rabbitmq:5672/%2F")
    for intento in range(1, intentos + 1):
        try:
            return pika.BlockingConnection(pika.URLParameters(url))
        except pika.exceptions.AMQPConnectionError:
            if intento == intentos:
                raise
            log.warning("RabbitMQ no está listo (intento %s/%s), reintentando...", intento, intentos)
            time.sleep(espera)


def publicar(mensaje: dict) -> None:
    conexion = conectar(intentos=3, espera=1)
    try:
        canal = conexion.channel()
        canal.queue_declare(queue=COLA, durable=True)
        canal.basic_publish(
            exchange="",
            routing_key=COLA,
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
    finally:
        conexion.close()
