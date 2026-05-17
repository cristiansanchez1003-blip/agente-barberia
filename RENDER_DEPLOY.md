# Deploy en Render

## Configuracion del servicio

Render detecta `render.yaml` y crea un Web Service Python.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
- Health check: `/healthz`

## Variables de entorno obligatorias

Configuralas en Render Dashboard > Environment:

```env
DATABASE_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
GEMINI_API_KEY=<google_gemini_api_key>
VOICE_API_URL=<vapi_or_retell_outbound_call_url>
VOICE_API_KEY=<voice_provider_api_key>
VOICE_ASSISTANT_ID=<robotia_outbound_assistant_id>
```

## Endpoints publicos despues del deploy

- `GET /healthz`
- `GET /`
- `POST /api/chat`
- `POST /api/citas`
- `POST /api/citas/cambiar_estado`
- `POST /api/voice/tools`
- `GET /api/tasks/trigger-outbound-confirmations`
- `POST /api/voice/outbound-callback`

## Cron externo

Configura el Cron Job externo para llamar cada 30 minutos:

```text
GET https://<tu-servicio>.onrender.com/api/tasks/trigger-outbound-confirmations
```

## Callback de la plataforma de voz

Configura el webhook de retorno en Vapi/Retell:

```text
POST https://<tu-servicio>.onrender.com/api/voice/outbound-callback
```
