# SYLVASENSE Backend
FastAPI backend for ORION-PS-03.

## Run
`python -m uvicorn api_server:app --host 0.0.0.0 --port 8001`

Open `/docs` for the interactive API.

## Main endpoint
`POST /api/image-analyze` with multipart field `file`.

The backend wraps the real DeepForest tree detector and the project's crown/biomass modules; it is not a mock API.


Included additional Step 1-5 and gap-closure modules: app.py, spectral_layers.py, lidar_gedi.py, data_fusion.py, tree_detection.py, crown_segmentation.py, biomass.py, agb_forecasting.py, validation_report.py, interactive_spectral_lidar_map.py, and validation templates.
