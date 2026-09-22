# SylvaSense Frontend

React/Vite frontend for the SylvaSense FastAPI backend.

## Run

```powershell
npm install
npm run dev
```

Default frontend:
`http://localhost:5173`

Default backend:
`http://localhost:8001`

Optional backend URL:

```text
VITE_API_BASE_URL=http://localhost:8001
```

## Current backend endpoints used

- `GET /api/status`
- `GET /health`
- `POST /api/image-analyze`
- `POST /api/tree-detection`
- `POST /api/forecast`

## Expanded endpoint hooks already prepared

The frontend API service also has methods for:

- `/api/crown-segmentation`
- `/api/biomass`
- `/api/carbon`
- `/api/satellite-analysis`
- `/api/change-detection`
- `/api/validate`
- `/api/analyze`

These are not mocked. If the FastAPI backend does not expose them yet, the UI reports that the endpoint is unavailable.

## Design principle

The frontend never runs DeepForest, Earth Engine, GEDI, raster processing, biomass calculations, or forecasting locally. It sends requests to FastAPI and visualizes the returned JSON.
