# FinancIA

Registra tus ingresos y gastos hablando. Dices *"gasté 25 lucas en almuerzo"* y FinancIA lo guarda como un gasto de $25.000 en alimentación.

## Por qué

La mayoría de personas abandona las apps de finanzas personales porque registrar cada gasto a mano es tedioso. FinancIA reduce el registro a una frase, en el español que hablamos en Colombia ("lucas", "barras", "un palo").

## Cómo funciona

```
Navegador ──audio──▶ API (FastAPI) ──▶ RabbitMQ ──▶ Worker ──▶ Gemini
    ▲                    │                            │
    └── consulta estado ─┴──────── PostgreSQL ◀───────┘ (movimiento validado)
```

1. El navegador graba la voz y la envía a `POST /voz` (o el texto a `POST /texto`).
2. La API crea una solicitud, la publica en RabbitMQ y responde de inmediato con estado `pendiente`.
3. El worker convierte el audio a WAV con ffmpeg y se lo envía a Gemini, que devuelve un JSON estructurado: tipo, monto, categoría, descripción y transcripción.
4. Antes de guardar, el código valida la respuesta (`normalizar()` en `interprete.py`): el monto debe ser positivo y estar en rango, el tipo debe ser ingreso o gasto y la categoría debe estar en la lista. Si algo falla, la solicitud queda `rechazada` con un mensaje claro para el usuario.
5. El navegador consulta `GET /solicitudes/{id}` hasta ver el resultado.

### Decisiones de diseño

- **El LLM propone, el código decide.** Gemini nunca escribe directo en la base de datos. Su respuesta se exige en un esquema JSON y luego pasa por validación determinista.
- **Procesamiento asíncrono.** La transcripción y la llamada al modelo tardan unos segundos. La cola evita bloquear la API y permite escalar agregando más workers.
- **Idempotencia.** Si un mensaje llega dos veces a la cola, el movimiento no se registra dos veces.
- **Dinero con `Numeric`, no `Float`.** Así se evitan errores de redondeo binario en los montos.

## Ejecutar

Requisitos: Docker y una clave gratuita de Gemini ([Google AI Studio](https://aistudio.google.com/apikey)).

```bash
cp .env.example .env        # y pon tu GEMINI_API_KEY
docker compose up --build
```

Abre http://localhost (a través de Traefik) o http://localhost:8000. Panel de RabbitMQ: http://localhost:15672.

## Pruebas

Las pruebas simulan a Gemini, así que no necesitan clave ni Docker.

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

## API

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/voz` | Envía un audio (multipart, campo `audio`). Devuelve la solicitud. |
| POST | `/texto` | Envía `{"texto": "..."}`. Devuelve la solicitud. |
| GET | `/solicitudes/{id}` | Estado: pendiente, procesando, completada, rechazada o error. |
| POST | `/movimientos` | Registro manual. |
| GET | `/movimientos` | Últimos movimientos. |
| GET | `/balance` | Ingresos, gastos y balance. |

Documentación interactiva en http://localhost:8000/docs.

## Tecnologías

Python, FastAPI, SQLAlchemy, Pydantic, PostgreSQL, RabbitMQ, Gemini (google-genai), ffmpeg, Docker Compose, Traefik.
