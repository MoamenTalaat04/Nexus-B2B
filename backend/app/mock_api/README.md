# NEXUS B2B — Mock API Mode

Isolated, deterministic in-memory Mock API layer under `/api/v1`, controlled by `USE_MOCK_API=true`.

## Activation

Set in `.env` (never enable in production):

```env
USE_MOCK_API=true
```

Start the backend:

```bash
cd backend
uv run poe api
```

## Browser & Swagger Testing

- **Base URL:** `http://localhost:8000/api/v1`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
- **Health Check:** `http://localhost:8000/health` and `http://localhost:8000/api/v1/health`

## Demo Credentials

- **Tenant 1 (Little Stars Kids Wear):** `demo@littlestars.eg` / `DemoPass123!`
- **Tenant 2 (Cairo MedTech Supplies, isolated):** `medtech@example.com` / `MedTech123!`

In Swagger UI, call `POST /api/v1/auth/login` first. It sets the `access_token` httpOnly cookie automatically for same-origin requests and also returns `access_token` in the JSON body.

## Reset Mock Data

```bash
curl -X POST http://localhost:8000/api/v1/mock/reset
```

