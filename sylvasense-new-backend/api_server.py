from pathlib import Path
from functools import lru_cache

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
)

from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

import tempfile
import os
import traceback
import uuid
import math
import base64
import urllib.request
import threading

import numpy as np
import pandas as pd

import ee


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="SYLVASENSE Backend",
    version="1.5.0",
    description=(
        "SYLVASENSE Earth Observation platform with "
        "tree detection, crown segmentation, biomass, "
        "AGB analysis, Sentinel-1/Sentinel-2, "
        "NDVI, GEDI and change detection."
    ),
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DEEPFOREST MODEL
#
# IMPORTANT:
# tree_detection is imported only when the model is actually
# requested. This keeps Render startup memory much lower.
# ============================================================

@lru_cache(maxsize=1)
def get_deepforest_model():
    from tree_detection import load_model

    return load_model()


# ============================================================
# IMAGE ANALYSIS JOB STORAGE
#
# Each uploaded image receives a job_id.
#
# The frontend polls:
#
# GET /api/image-analysis-progress/{job_id}
#
# ============================================================

_image_jobs = {}

_image_jobs_lock = threading.Lock()


def create_image_job(filename):
    job_id = uuid.uuid4().hex

    with _image_jobs_lock:
        _image_jobs[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "status": "queued",
            "progress": 0,
            "stage": "Queued",
            "message": "Image analysis is queued.",
            "result": None,
            "error": None,
        }

    return job_id


def update_image_job(
    job_id,
    progress,
    stage,
    message,
):
    with _image_jobs_lock:

        job = _image_jobs.get(job_id)

        if job is None:
            return

        progress = int(
            max(
                0,
                min(
                    100,
                    progress,
                ),
            )
        )

        job["progress"] = progress
        job["stage"] = stage
        job["message"] = message

        if progress >= 100:
            job["status"] = "completed"

        elif progress > 0:
            job["status"] = "running"


def complete_image_job(
    job_id,
    result,
):
    with _image_jobs_lock:

        job = _image_jobs.get(job_id)

        if job is None:
            return

        job["progress"] = 100
        job["status"] = "completed"
        job["stage"] = "Complete"
        job["message"] = (
            "Image analysis completed successfully."
        )
        job["result"] = result
        job["error"] = None


def fail_image_job(
    job_id,
    error,
):
    with _image_jobs_lock:

        job = _image_jobs.get(job_id)

        if job is None:
            return

        job["status"] = "failed"
        job["stage"] = "Failed"
        job["message"] = str(error)
        job["error"] = str(error)


# ============================================================
# JSON SERIALIZATION
# ============================================================

def make_json_safe(obj):

    if isinstance(obj, dict):

        return {
            str(key): make_json_safe(value)
            for key, value in obj.items()
        }

    if isinstance(obj, list):

        return [
            make_json_safe(value)
            for value in obj
        ]

    if isinstance(obj, tuple):

        return [
            make_json_safe(value)
            for value in obj
        ]

    if isinstance(obj, pd.DataFrame):

        return make_json_safe(
            obj.to_dict(
                orient="records"
            )
        )

    if isinstance(obj, pd.Series):

        return make_json_safe(
            obj.to_dict()
        )

    if isinstance(obj, np.ndarray):

        return make_json_safe(
            obj.tolist()
        )

    if isinstance(obj, np.integer):

        return int(obj)

    if isinstance(obj, np.floating):

        value = float(obj)

        if (
            math.isnan(value)
            or math.isinf(value)
        ):
            return None

        return value

    if isinstance(obj, np.bool_):

        return bool(obj)

    if isinstance(obj, float):

        if (
            math.isnan(obj)
            or math.isinf(obj)
        ):
            return None

        return obj

    if obj is None or isinstance(
        obj,
        (str, int, bool),
    ):

        return obj

    try:

        missing = pd.isna(obj)

        if (
            isinstance(
                missing,
                bool,
            )
            and missing
        ):
            return None

    except Exception:
        pass

    if isinstance(
        obj,
        pd.Timestamp,
    ):

        return obj.isoformat()

    if isinstance(
        obj,
        Path,
    ):

        return str(obj)

    if hasattr(
        obj,
        "__geo_interface__",
    ):

        try:

            return make_json_safe(
                obj.__geo_interface__
            )

        except Exception:
            pass

    if hasattr(
        obj,
        "to_dict",
    ):

        try:

            return make_json_safe(
                obj.to_dict()
            )

        except Exception:
            pass

    return str(obj)


# ============================================================
# IMAGE VALIDATION
# ============================================================

def validate_image(filename):

    suffix = Path(
        filename or ""
    ).suffix.lower()

    allowed = {
        ".jpg",
        ".jpeg",
        ".png",
        ".tif",
        ".tiff",
    }

    if suffix not in allowed:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Use JPG, JPEG, PNG, TIF or TIFF."
            ),
        )

    return suffix


# ============================================================
# EARTH ENGINE REGION
# ============================================================

def build_satellite_region(
    latitude,
    longitude,
    radius_m,
):

    point = ee.Geometry.Point(
        [
            longitude,
            latitude,
        ]
    )

    region = (
        point
        .buffer(radius_m)
        .bounds()
    )

    return region


# ============================================================
# EARTH ENGINE INITIALIZATION
# ============================================================

def initialize_earth_engine():

    project = os.getenv(
        "GEE_PROJECT",
        "syylvasense",
    )

    ee.Initialize(
        project=project
    )

    return project


# ============================================================
# SENTINEL-2 CLOUD MASK
# ============================================================

def mask_s2_clouds_satellite(image):

    qa = image.select(
        "QA60"
    )

    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11

    mask = (
        qa.bitwiseAnd(
            cloud_bit_mask
        )
        .eq(0)
        .And(
            qa.bitwiseAnd(
                cirrus_bit_mask
            )
            .eq(0)
        )
    )

    return (
        image
        .updateMask(mask)
        .divide(10000)
    )


# ============================================================
# GET ACTUAL SENTINEL-2 RGB IMAGE
# ============================================================

def get_sentinel2_rgb_image(
    region,
    latitude,
    longitude,
    radius_m,
    start_date,
    end_date,
    max_cloud_pct,
):

    selected_point = ee.Geometry.Point(
        [
            longitude,
            latitude,
        ]
    )

    collection = (
        ee.ImageCollection(
            "COPERNICUS/S2_SR_HARMONIZED"
        )
        .filterBounds(region)
        .filterDate(
            start_date,
            end_date,
        )
        .filter(
            ee.Filter.lte(
                "CLOUDY_PIXEL_PERCENTAGE",
                max_cloud_pct,
            )
        )
        .sort(
            "CLOUDY_PIXEL_PERCENTAGE"
        )
    )

    scene_count = int(
        collection
        .size()
        .getInfo()
        or 0
    )

    if scene_count == 0:

        return {
            "available": False,
            "scene_count": 0,
            "url": None,
            "data_url": None,
            "date": None,
            "cloud_percentage": None,
            "scene_id": None,
            "center": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "radius_m": radius_m,
        }

    image = ee.Image(
        collection.first()
    )

    intersection_collection = (
        ee.ImageCollection(
            "COPERNICUS/S2_SR_HARMONIZED"
        )
        .filterBounds(selected_point)
        .filterDate(
            start_date,
            end_date,
        )
        .filter(
            ee.Filter.lte(
                "CLOUDY_PIXEL_PERCENTAGE",
                max_cloud_pct,
            )
        )
    )

    intersection_count = int(
        intersection_collection
        .size()
        .getInfo()
        or 0
    )

    if intersection_count == 0:

        return {
            "available": False,
            "scene_count": 0,
            "url": None,
            "data_url": None,
            "date": None,
            "cloud_percentage": None,
            "scene_id": None,
            "center": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "radius_m": radius_m,
        }

    image_info = image.getInfo() or {}

    properties = image_info.get(
        "properties",
        {}
    )

    scene_id = properties.get(
        "PRODUCT_ID"
    )

    acquisition_millis = properties.get(
        "system:time_start"
    )

    acquisition_date = None

    if acquisition_millis:

        try:

            from datetime import datetime, timezone

            acquisition_date = (
                datetime.fromtimestamp(
                    acquisition_millis / 1000,
                    tz=timezone.utc,
                )
                .strftime("%Y-%m-%d")
            )

        except Exception:

            acquisition_date = None

    cloud_percentage = properties.get(
        "CLOUDY_PIXEL_PERCENTAGE"
    )

    masked_image = (
        mask_s2_clouds_satellite(
            image
        )
    )

    clipped_image = (
        masked_image
        .clip(region)
    )

    visualization = {
        "bands": [
            "B4",
            "B3",
            "B2",
        ],
        "min": 0.0,
        "max": 0.3,
    }

    region_info = region.getInfo()

    thumbnail_params = {
        "region": region,
        "dimensions": 1024,
        "format": "png",
        "crs": "EPSG:4326",
        **visualization,
    }

    thumbnail_url = (
        clipped_image
        .getThumbURL(
            thumbnail_params
        )
    )

    data_url = None
    image_size_bytes = None

    try:

        request = urllib.request.Request(
            thumbnail_url,
            headers={
                "User-Agent":
                    "SylvaSense/1.5.0"
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:

            image_bytes = response.read()

        image_size_bytes = len(
            image_bytes
        )

        if not image_bytes:

            raise ValueError(
                "Earth Engine returned an empty image."
            )

        encoded = (
            base64.b64encode(
                image_bytes
            )
            .decode("utf-8")
        )

        data_url = (
            "data:image/png;base64,"
            + encoded
        )

    except Exception as download_error:

        print(
            "Satellite thumbnail download failed:"
        )

        print(download_error)

        data_url = None

    return {

        "available":
            data_url is not None,

        "scene_count":
            scene_count,

        "url":
            thumbnail_url,

        "data_url":
            data_url,

        "type":
            "Sentinel-2 RGB",

        "source":
            "COPERNICUS/S2_SR_HARMONIZED",

        "bands": [
            "B4",
            "B3",
            "B2",
        ],

        "date":
            acquisition_date,

        "cloud_percentage":
            cloud_percentage,

        "scene_id":
            scene_id,

        "dimensions":
            1024,

        "scale_m":
            10,

        "radius_m":
            radius_m,

        "center": {
            "latitude":
                latitude,
            "longitude":
                longitude,
        },

        "selected_location": {
            "latitude":
                latitude,
            "longitude":
                longitude,
        },

        "region":
            region_info,

        "image_size_bytes":
            image_size_bytes,

        "visualization":
            visualization,

        "description":
            (
                "Real Sentinel-2 RGB imagery generated "
                "from the user-selected latitude and "
                "longitude and clipped to the selected "
                "analysis region. The RGB source bands "
                "have 10 metre native spatial resolution."
            ),
    }


# ============================================================
# IMAGE ANALYSIS BACKGROUND JOB
#
# Heavy modules are imported INSIDE this function.
# ============================================================

def run_image_analysis_job(
    job_id,
    temp_path,
    filename,
):

    try:

        # ----------------------------------------------------
        # LAZY IMPORTS
        # ----------------------------------------------------

        from tree_detection import (
            detect_trees,
            compute_crown_metrics,
        )

        from crown_segmentation import (
            segment_tree_crowns,
        )

        from biomass import (
            per_tree_biomass_pipeline,
        )

        # ----------------------------------------------------
        # 5% - FILE READY
        # ----------------------------------------------------

        update_image_job(
            job_id,
            5,
            "Image uploaded",
            "Image uploaded and ready for analysis.",
        )

        # ----------------------------------------------------
        # 10% - LOADING MODEL
        # ----------------------------------------------------

        update_image_job(
            job_id,
            10,
            "Loading AI model",
            "Loading the DeepForest tree detection model...",
        )

        model = get_deepforest_model()

        # ----------------------------------------------------
        # 15% - MODEL READY
        # ----------------------------------------------------

        update_image_job(
            job_id,
            15,
            "AI model ready",
            "DeepForest model loaded successfully.",
        )

        # ----------------------------------------------------
        # 20% - TREE DETECTION START
        # ----------------------------------------------------

        update_image_job(
            job_id,
            20,
            "Tree detection",
            "Detecting individual trees with DeepForest...",
        )

        predictions = detect_trees(
            model,
            temp_path,
            patch_size=400,
            patch_overlap=0.25,
            iou_threshold=0.15,
        )

        predictions = compute_crown_metrics(
            predictions,
            pixel_size_m=0.1,
        )

        tree_count = len(predictions)

        # ----------------------------------------------------
        # LOG DETECTED BOXES
        # ----------------------------------------------------

        print(
            "\n========== DETECTED TREE BOXES =========="
        )

        box_columns = [
            column
            for column in [
                "xmin",
                "ymin",
                "xmax",
                "ymax",
                "score",
                "label",
            ]
            if column in predictions.columns
        ]

        if box_columns:

            print(
                predictions[
                    box_columns
                ].to_string(
                    index=False
                )
            )

        else:

            print(
                "Bounding-box columns were not found. "
                f"Available columns: "
                f"{list(predictions.columns)}"
            )

        print(
            "=========================================\n"
        )

        # ----------------------------------------------------
        # 50% - TREE DETECTION COMPLETE
        # ----------------------------------------------------

        update_image_job(
            job_id,
            50,
            "Tree detection complete",
            f"Detected {tree_count} trees.",
        )

        # ----------------------------------------------------
        # 55% - CROWN SEGMENTATION START
        # ----------------------------------------------------

        update_image_job(
            job_id,
            55,
            "Crown segmentation",
            "Segmenting individual tree crowns...",
        )

        segmentation_output = (
            segment_tree_crowns(
                temp_path,
                predictions,
            )
        )

        # ----------------------------------------------------
        # 70% - CROWN SEGMENTATION COMPLETE
        # ----------------------------------------------------

        update_image_job(
            job_id,
            70,
            "Crown segmentation complete",
            "Tree crown segmentation completed.",
        )

        # ----------------------------------------------------
        # 75% - BIOMASS START
        # ----------------------------------------------------

        update_image_job(
            job_id,
            75,
            "Biomass estimation",
            "Calculating aboveground biomass...",
        )

        # ----------------------------------------------------
        # EMPTY TREE RESULT
        # ----------------------------------------------------

        if predictions.empty:

            biomass_result = {
                "status": "success",
                "tree_count": 0,
                "total_agb_tonnes": 0.0,
                "total_carbon_tonnes": 0.0,
                "total_co2e_tonnes": 0.0,
                "trees": [],
            }

        # ----------------------------------------------------
        # BIOMASS CALCULATION
        # ----------------------------------------------------

        else:

            df = per_tree_biomass_pipeline(
                predictions,
                wood_density_g_cm3=0.6,
                crown_diameter_column=(
                    "crown_diameter_m"
                ),
            )

            trees = []

            for i, row in df.iterrows():

                trees.append(
                    make_json_safe(
                        {
                            "tree_id":
                                int(i) + 1,

                            "crown_diameter_m":
                                row.get(
                                    "biomass_crown_diameter_m"
                                ),

                            "dbh_cm":
                                row.get(
                                    "dbh_cm"
                                ),

                            "height_m":
                                row.get(
                                    "height_m"
                                ),

                            "agb_kg":
                                row.get(
                                    "agb_kg"
                                ),

                            "agb_tonnes":
                                row.get(
                                    "agb_tonnes"
                                ),

                            "carbon_tonnes":
                                row.get(
                                    "carbon_tonnes"
                                ),

                            "co2e_tonnes":
                                row.get(
                                    "co2e_tonnes"
                                ),
                        }
                    )
                )

            biomass_result = {

                "status":
                    "success",

                "tree_count":
                    len(df),

                "method":
                    (
                        "Jucker crown-to-DBH + "
                        "Feldpausch height + "
                        "Chave 2014 AGB"
                    ),

                "wood_density_g_cm3":
                    0.6,

                "total_agb_tonnes":
                    float(
                        df[
                            "agb_tonnes"
                        ].sum()
                    ),

                "total_carbon_tonnes":
                    float(
                        df[
                            "carbon_tonnes"
                        ].sum()
                    ),

                "total_co2e_tonnes":
                    float(
                        df[
                            "co2e_tonnes"
                        ].sum()
                    ),

                "trees":
                    trees,
            }

        # ----------------------------------------------------
        # 90% - BIOMASS COMPLETE
        # ----------------------------------------------------

        update_image_job(
            job_id,
            90,
            "Biomass estimation complete",
            "Biomass and carbon calculations completed.",
        )

        # ----------------------------------------------------
        # 95% - PREPARING RESPONSE
        # ----------------------------------------------------

        update_image_job(
            job_id,
            95,
            "Preparing results",
            "Preparing final analysis results...",
        )

        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        response = {

            "status":
                "success",

            "analysis_id":
                uuid.uuid4().hex,

            "filename":
                filename,

            "tree_count":
                tree_count,

            "modules": {

                "tree_detection": {

                    "status":
                        "success",

                    "model":
                        "weecology/deepforest-tree",

                    "tree_count":
                        tree_count,

                    "trees":
                        predictions.to_dict(
                            orient="records"
                        ),
                },

                "crown_segmentation":
                    segmentation_output,

                "biomass":
                    biomass_result,
            },
        }

        response = make_json_safe(
            response
        )

        # ----------------------------------------------------
        # 100% - COMPLETE
        # ----------------------------------------------------

        complete_image_job(
            job_id,
            response,
        )

    except Exception as exc:

        traceback.print_exc()

        fail_image_job(
            job_id,
            (
                f"Image analysis failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

    finally:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            try:
                os.remove(temp_path)

            except Exception:
                pass


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "service":
            "SYLVASENSE backend",

        "status":
            "online",

        "docs":
            "/docs",

        "version":
            "1.5.0",
    }


# ============================================================
# STATUS
# ============================================================

@app.get("/api/status")
def status():

    return {

        "status":
            "healthy",

        "service":
            "SYLVASENSE backend",

        "deepforest_model":
            "weecology/deepforest-tree",

        "modules": [

            "tree_detection",

            "crown_segmentation",

            "biomass",

            "sentinel_1",

            "sentinel_2",

            "ndvi",

            "gedi_lidar",

            "agb_forecasting",

            "change_detection",

            "satellite_agb",

            "satellite_rgb_acquisition",

            "image_analysis_progress",
        ],
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status":
            "ok"
    }


# ============================================================
# IMAGE ANALYSIS
#
# START JOB
# ============================================================

@app.post(
    "/api/image-analyze"
)
async def image_analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):

    suffix = validate_image(
        file.filename
    )

    data = await file.read()

    if not data:

        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    if len(data) > 25 * 1024 * 1024:

        raise HTTPException(
            status_code=413,
            detail=(
                "Image file is too large. "
                "Maximum size is 25 MB."
            ),
        )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp:

            temp.write(data)
            temp_path = temp.name

        job_id = create_image_job(
            file.filename
        )

        background_tasks.add_task(
            run_image_analysis_job,
            job_id,
            temp_path,
            file.filename,
        )

        return {

            "status":
                "accepted",

            "job_id":
                job_id,

            "filename":
                file.filename,

            "progress":
                0,

            "stage":
                "Queued",

            "message":
                "Image analysis started.",
        }

    except Exception as exc:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            try:
                os.remove(temp_path)

            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to start image analysis: "
                f"{type(exc).__name__}: {exc}"
            ),
        )


# ============================================================
# IMAGE ANALYSIS PROGRESS
# ============================================================

@app.get(
    "/api/image-analysis-progress/{job_id}"
)
def image_analysis_progress(
    job_id: str,
):

    with _image_jobs_lock:

        job = _image_jobs.get(
            job_id
        )

        if job is None:

            raise HTTPException(
                status_code=404,
                detail="Analysis job not found.",
            )

        return {

            "job_id":
                job["job_id"],

            "filename":
                job["filename"],

            "status":
                job["status"],

            "progress":
                job["progress"],

            "stage":
                job["stage"],

            "message":
                job["message"],

            "result":
                job["result"],

            "error":
                job["error"],
        }


# ============================================================
# TREE DETECTION
#
# Kept as an alias for compatibility.
# ============================================================

@app.post(
    "/api/tree-detection"
)
async def tree_detection(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):

    return await image_analyze(
        background_tasks,
        file,
    )


# ============================================================
# FORECAST REQUEST
# ============================================================

class ForecastRequest(BaseModel):

    historical_years: list[float] = Field(
        ...,
        min_length=2,
    )

    historical_agb: list[float] = Field(
        ...,
        min_length=2,
    )

    forecast_years: list[float] = Field(
        ...,
        min_length=1,
    )


# ============================================================
# OLD AGB FORECAST ENDPOINT
# ============================================================

@app.post(
    "/api/forecast"
)
def forecast(
    req: ForecastRequest,
):

    if (
        len(req.historical_years)
        != len(req.historical_agb)
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "historical_years and "
                "historical_agb must have equal length."
            ),
        )

    try:

        # Lazy import
        from agb_forecasting import (
            forecast_agb,
            calculate_forecast_summary,
        )

        result = forecast_agb(
            req.historical_years,
            req.historical_agb,
            req.forecast_years,
        )

        summary = calculate_forecast_summary(
            result
        )

        return make_json_safe(
            {
                "status":
                    "success",

                "forecast":
                    result,

                "summary":
                    summary,
            }
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Forecast failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )


# ============================================================
# SATELLITE ANALYSIS REQUEST
# ============================================================

class SatelliteAnalysisRequest(BaseModel):

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
    )

    radius_m: float = Field(
        2000,
        ge=100,
        le=10000,
    )

    start_date: str = "2025-06-01"

    end_date: str = "2026-02-28"

    max_cloud_pct: float = Field(
        15,
        ge=0,
        le=100,
    )

    gedi_start_date: str = "2019-03-25"

    gedi_end_date: str = "2024-11-30"

    include_sar: bool = True


# ============================================================
# SATELLITE ANALYSIS
# ============================================================

@app.post(
    "/api/satellite-analysis"
)
def satellite_analysis(
    req: SatelliteAnalysisRequest,
):

    if req.start_date >= req.end_date:

        raise HTTPException(
            status_code=400,
            detail=(
                "start_date must be before end_date."
            ),
        )

    if (
        req.gedi_start_date
        >= req.gedi_end_date
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "gedi_start_date must be before "
                "gedi_end_date."
            ),
        )

    try:

        # ----------------------------------------------------
        # LAZY IMPORTS
        # ----------------------------------------------------

        from spectral_layers import (
            get_layer_images,
            SPECTRAL_VIS,
        )

        from lidar_gedi import (
            get_gedi_rh98,
            gedi_statistics,
        )

        # ----------------------------------------------------
        # EARTH ENGINE
        # ----------------------------------------------------

        gee_project = (
            initialize_earth_engine()
        )

        region = build_satellite_region(
            latitude=req.latitude,
            longitude=req.longitude,
            radius_m=req.radius_m,
        )

        satellite_image = (
            get_sentinel2_rgb_image(
                region=region,
                latitude=req.latitude,
                longitude=req.longitude,
                radius_m=req.radius_m,
                start_date=req.start_date,
                end_date=req.end_date,
                max_cloud_pct=req.max_cloud_pct,
            )
        )

        satellite_data = get_layer_images(
            region=region,
            start_date=req.start_date,
            end_date=req.end_date,
            max_cloud_pct=req.max_cloud_pct,
        )

        optical = satellite_data[
            "optical"
        ]

        ndvi = satellite_data[
            "ndvi"
        ]

        sar = satellite_data[
            "sar"
        ]

        layers = []

        for name, params in SPECTRAL_VIS.items():

            if (
                name.startswith("SAR")
                and not req.include_sar
            ):
                continue

            if name == "NDVI":

                image = ndvi

            elif name.startswith("SAR"):

                image = sar

            else:

                image = optical

            map_id = image.getMapId(
                params
            )

            tile_url = (
                map_id[
                    "tile_fetcher"
                ].url_format
            )

            layer = {

                "id":
                    (
                        name
                        .lower()
                        .replace(
                            " ",
                            "_",
                        )
                        .replace(
                            "(",
                            "",
                        )
                        .replace(
                            ")",
                            "",
                        )
                        .replace(
                            "/",
                            "_",
                        )
                    ),

                "name":
                    name,

                "type":
                    (
                        "sar"
                        if name.startswith("SAR")
                        else (
                            "index"
                            if name == "NDVI"
                            else "spectral"
                        )
                    ),

                "tile_url":
                    tile_url,

                "bands":
                    params.get(
                        "bands",
                        [],
                    ),

                "min":
                    params.get(
                        "min"
                    ),

                "max":
                    params.get(
                        "max"
                    ),

                "palette":
                    params.get(
                        "palette"
                    ),

                "default_visible":
                    name in {
                        "NIR (B8)",
                        "NDVI",
                    },
            }

            layers.append(layer)

        # ----------------------------------------------------
        # GEDI RH98
        # ----------------------------------------------------

        gedi_image, gedi_count = (
            get_gedi_rh98(
                region=region,
                start_date=req.gedi_start_date,
                end_date=req.gedi_end_date,
            )
        )

        gedi_stats = gedi_statistics(
            region=region,
            start_date=req.gedi_start_date,
            end_date=req.gedi_end_date,
        )

        gedi_vis = {

            "min":
                0,

            "max":
                40,

            "palette": [
                "440154",
                "31688e",
                "35b779",
                "fde725",
            ],
        }

        gedi_map_id = (
            gedi_image.getMapId(
                gedi_vis
            )
        )

        gedi_tile_url = (
            gedi_map_id[
                "tile_fetcher"
            ].url_format
        )

        layers.append(
            {

                "id":
                    "gedi_rh98",

                "name":
                    "GEDI RH98 (m)",

                "type":
                    "gedi",

                "tile_url":
                    gedi_tile_url,

                "bands":
                    ["rh98"],

                "min":
                    0,

                "max":
                    40,

                "palette":
                    gedi_vis[
                        "palette"
                    ],

                "default_visible":
                    False,
            }
        )

        region_info = (
            region.getInfo()
        )

        response = {

            "status":
                "success",

            "gee_project":
                gee_project,

            "location": {

                "latitude":
                    req.latitude,

                "longitude":
                    req.longitude,

                "radius_m":
                    req.radius_m,

                "region":
                    region_info,
            },

            "satellite_image":
                satellite_image,

            "sentinel": {

                "sentinel_2": {

                    "collection":
                        "COPERNICUS/S2_SR_HARMONIZED",

                    "scene_count":
                        satellite_data[
                            "s2_count"
                        ],

                    "selected_scene":
                        satellite_image.get(
                            "scene_id"
                        ),

                    "selected_date":
                        satellite_image.get(
                            "date"
                        ),

                    "selected_cloud_percentage":
                        satellite_image.get(
                            "cloud_percentage"
                        ),

                    "selected_location":
                        satellite_image.get(
                            "selected_location"
                        ),

                    "start_date":
                        req.start_date,

                    "end_date":
                        req.end_date,

                    "max_cloud_pct":
                        req.max_cloud_pct,

                    "rgb_bands": [
                        "B4",
                        "B3",
                        "B2",
                    ],

                    "spatial_resolution_m":
                        10,
                },

                "sentinel_1": {

                    "collection":
                        "COPERNICUS/S1_GRD",

                    "scene_count":
                        satellite_data[
                            "s1_count"
                        ],
                },
            },

            "gedi": {

                "collection":
                    "LARSE/GEDI/"
                    "GEDI02_A_002_MONTHLY",

                "scene_count":
                    gedi_count,

                "start_date":
                    req.gedi_start_date,

                "end_date":
                    req.gedi_end_date,

                "statistics":
                    gedi_stats,
            },

            "layers":
                layers,

            "image_analysis_handoff": {

                "available":
                    satellite_image.get(
                        "data_url"
                    ) is not None,

                "filename":
                    (
                        "satellite_"
                        + (
                            satellite_image.get(
                                "date"
                            )
                            or "image"
                        )
                        + ".png"
                    ),

                "format":
                    "PNG",

                "source":
                    "Sentinel-2",

                "center_latitude":
                    req.latitude,

                "center_longitude":
                    req.longitude,

                "radius_m":
                    req.radius_m,

                "selected_scene":
                    satellite_image.get(
                        "scene_id"
                    ),

                "selected_date":
                    satellite_image.get(
                        "date"
                    ),

                "cloud_percentage":
                    satellite_image.get(
                        "cloud_percentage"
                    ),

                "description":
                    (
                        "True-color Sentinel-2 image "
                        "generated from the exact "
                        "user-selected map location "
                        "and selected analysis region."
                    ),

                "ready_for_image_analysis":
                    satellite_image.get(
                        "data_url"
                    ) is not None,
            },
        }

        return make_json_safe(
            response
        )

    except HTTPException:
        raise

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Satellite analysis failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )


# ============================================================
# CHANGE DETECTION REQUEST
# ============================================================

class ChangeDetectionRequest(BaseModel):

    before_date: str = "2025-06-01"

    after_date: str = "2026-02-28"

    latitude: float = Field(
        10.1,
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        77.05,
        ge=-180,
        le=180,
    )

    radius_m: float = Field(
        2000,
        ge=100,
        le=10000,
    )

    window_days: int = Field(
        30,
        ge=1,
        le=180,
    )

    max_cloud_pct: float = Field(
        20,
        ge=0,
        le=100,
    )


# ============================================================
# CHANGE DETECTION
# ============================================================

@app.post(
    "/api/change-detection"
)
def change_detection(
    req: ChangeDetectionRequest,
):

    if req.before_date >= req.after_date:

        raise HTTPException(
            status_code=400,
            detail=(
                "before_date must be earlier "
                "than after_date."
            ),
        )

    try:

        gee_project = (
            initialize_earth_engine()
        )

        region = build_satellite_region(
            latitude=req.latitude,
            longitude=req.longitude,
            radius_m=req.radius_m,
        )

        collection = (
            ee.ImageCollection(
                "COPERNICUS/S2_SR_HARMONIZED"
            )
            .filterBounds(region)
            .filter(
                ee.Filter.lte(
                    "CLOUDY_PIXEL_PERCENTAGE",
                    req.max_cloud_pct,
                )
            )
        )

        before_center = ee.Date(
            req.before_date
        )

        before_start = (
            before_center.advance(
                -req.window_days,
                "day",
            )
        )

        before_end = (
            before_center.advance(
                req.window_days,
                "day",
            )
        )

        after_center = ee.Date(
            req.after_date
        )

        after_start = (
            after_center.advance(
                -req.window_days,
                "day",
            )
        )

        after_end = (
            after_center.advance(
                req.window_days,
                "day",
            )
        )

        before_collection = (
            collection
            .filterDate(
                before_start,
                before_end,
            )
        )

        after_collection = (
            collection
            .filterDate(
                after_start,
                after_end,
            )
        )

        before_count = int(
            before_collection
            .size()
            .getInfo()
        )

        after_count = int(
            after_collection
            .size()
            .getInfo()
        )

        if before_count == 0:

            raise HTTPException(
                status_code=404,
                detail=(
                    "No Sentinel-2 scenes found "
                    "for the before period. "
                    f"Date: {req.before_date}. "
                    "Try increasing window_days "
                    "or changing the date."
                ),
            )

        if after_count == 0:

            raise HTTPException(
                status_code=404,
                detail=(
                    "No Sentinel-2 scenes found "
                    "for the after period. "
                    f"Date: {req.after_date}. "
                    "Try increasing window_days "
                    "or changing the date."
                ),
            )

        def add_ndvi(image):

            ndvi = (
                image
                .normalizedDifference(
                    [
                        "B8",
                        "B4",
                    ]
                )
                .rename(
                    "NDVI"
                )
            )

            return image.addBands(
                ndvi
            )

        before_ndvi = (
            before_collection
            .map(add_ndvi)
            .select("NDVI")
            .median()
            .clip(region)
        )

        after_ndvi = (
            after_collection
            .map(add_ndvi)
            .select("NDVI")
            .median()
            .clip(region)
        )

        ndvi_change = (
            after_ndvi
            .subtract(
                before_ndvi
            )
            .rename(
                "NDVI_CHANGE"
            )
            .clip(region)
        )

        decrease_threshold = -0.15
        increase_threshold = 0.15

        statistics = (
            ndvi_change
            .reduceRegion(
                reducer=(
                    ee.Reducer.mean()
                    .combine(
                        reducer2=ee.Reducer.minMax(),
                        sharedInputs=True,
                    )
                ),
                geometry=region,
                scale=10,
                maxPixels=1_000_000,
                bestEffort=True,
            )
        )

        statistics_info = (
            statistics.getInfo()
        )

        mean_change = (
            statistics_info.get(
                "NDVI_CHANGE_mean"
            )
        )

        min_change = (
            statistics_info.get(
                "NDVI_CHANGE_min"
            )
        )

        max_change = (
            statistics_info.get(
                "NDVI_CHANGE_max"
            )
        )

        decrease_mask = (
            ndvi_change
            .lt(
                decrease_threshold
            )
            .selfMask()
        )

        increase_mask = (
            ndvi_change
            .gt(
                increase_threshold
            )
            .selfMask()
        )

        decrease_result = (
            decrease_mask
            .reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=region,
                scale=10,
                maxPixels=1_000_000,
                bestEffort=True,
            )
        )

        decrease_pixels = (
            decrease_result
            .get(
                "NDVI_CHANGE"
            )
            .getInfo()
        )

        if decrease_pixels is None:
            decrease_pixels = 0

        increase_result = (
            increase_mask
            .reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=region,
                scale=10,
                maxPixels=1_000_000,
                bestEffort=True,
            )
        )

        increase_pixels = (
            increase_result
            .get(
                "NDVI_CHANGE"
            )
            .getInfo()
        )

        if increase_pixels is None:
            increase_pixels = 0

        ndvi_vis = {

            "min":
                -0.2,

            "max":
                0.9,

            "palette": [
                "8c510a",
                "d8b365",
                "f6e8c3",
                "c7eae5",
                "5ab4ac",
                "01665e",
            ],
        }

        change_vis = {

            "min":
                -0.5,

            "max":
                0.5,

            "palette": [
                "8B0000",
                "FF0000",
                "FF4500",
                "FFA500",
                "FFFF00",
                "FFFFFF",
                "ADFF2F",
                "32CD32",
                "008000",
                "006400",
                "004D00",
            ],
        }

        before_map_id = (
            before_ndvi
            .getMapId(
                ndvi_vis
            )
        )

        before_tile_url = (
            before_map_id[
                "tile_fetcher"
            ].url_format
        )

        after_map_id = (
            after_ndvi
            .getMapId(
                ndvi_vis
            )
        )

        after_tile_url = (
            after_map_id[
                "tile_fetcher"
            ].url_format
        )

        change_map_id = (
            ndvi_change
            .getMapId(
                change_vis
            )
        )

        change_tile_url = (
            change_map_id[
                "tile_fetcher"
            ].url_format
        )

        response = {

            "status":
                "success",

            "analysis":
                "Sentinel-2 NDVI change",

            "gee_project":
                gee_project,

            "location": {

                "latitude":
                    req.latitude,

                "longitude":
                    req.longitude,

                "radius_m":
                    req.radius_m,
            },

            "before": {

                "date":
                    req.before_date,

                "window_days":
                    req.window_days,

                "scene_count":
                    before_count,

                "tile_url":
                    before_tile_url,
            },

            "after": {

                "date":
                    req.after_date,

                "window_days":
                    req.window_days,

                "scene_count":
                    after_count,

                "tile_url":
                    after_tile_url,
            },

            "change": {

                "method":
                    (
                        "After median NDVI "
                        "minus Before median NDVI"
                    ),

                "mean_ndvi_change":
                    mean_change,

                "minimum_ndvi_change":
                    min_change,

                "maximum_ndvi_change":
                    max_change,

                "decrease_threshold":
                    decrease_threshold,

                "increase_threshold":
                    increase_threshold,

                "decrease_pixel_count":
                    decrease_pixels,

                "increase_pixel_count":
                    increase_pixels,

                "tile_url":
                    change_tile_url,

                "visualization": {

                    "min":
                        -0.5,

                    "max":
                        0.5,

                    "palette":
                        change_vis[
                            "palette"
                        ],
                },
            },

            "layers": [

                {

                    "id":
                        "before_ndvi",

                    "name":
                        "Before NDVI",

                    "type":
                        "ndvi",

                    "tile_url":
                        before_tile_url,

                    "min":
                        -0.2,

                    "max":
                        0.9,

                    "default_visible":
                        False,
                },

                {

                    "id":
                        "after_ndvi",

                    "name":
                        "After NDVI",

                    "type":
                        "ndvi",

                    "tile_url":
                        after_tile_url,

                    "min":
                        -0.2,

                    "max":
                        0.9,

                    "default_visible":
                        False,
                },

                {

                    "id":
                        "ndvi_change",

                    "name":
                        "NDVI Change",

                    "type":
                        "change",

                    "tile_url":
                        change_tile_url,

                    "min":
                        -0.5,

                    "max":
                        0.5,

                    "default_visible":
                        True,

                    "palette":
                        change_vis[
                            "palette"
                        ],
                },
            ],

            "interpretation": {

                "note":
                    (
                        "NDVI change represents the "
                        "difference between the after "
                        "and before vegetation index. "
                        "Red areas indicate vegetation "
                        "decrease, white/yellow areas "
                        "indicate relatively small "
                        "changes, and green areas indicate "
                        "vegetation increase. NDVI change "
                        "alone should not be interpreted "
                        "as proof of deforestation or a "
                        "specific land-use change."
                    ),

                "legend": {

                    "decrease":
                        "NDVI change < -0.15",

                    "little_change":
                        (
                            "-0.15 <= NDVI change <= 0.15"
                        ),

                    "increase":
                        "NDVI change > 0.15",
                },
            },
        }

        return make_json_safe(
            response
        )

    except HTTPException:
        raise

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Change detection failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )


# ============================================================
# SATELLITE AGB REQUEST
# ============================================================

class SatelliteAGBRequest(BaseModel):

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
    )

    radius_m: float = Field(
        1000,
        ge=100,
        le=5000,
    )

    year: int = Field(
        ...,
        ge=2019,
        le=2025,
    )

    max_cloud_pct: float = Field(
        20,
        ge=0,
        le=100,
    )


# ============================================================
# SENTINEL-2 CLOUD MASK FOR AGB
# ============================================================

def mask_s2_clouds_agb(image):

    qa = image.select(
        "QA60"
    )

    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11

    mask = (
        qa.bitwiseAnd(
            cloud_bit_mask
        )
        .eq(0)
        .And(
            qa.bitwiseAnd(
                cirrus_bit_mask
            )
            .eq(0)
        )
    )

    return (
        image
        .updateMask(mask)
        .divide(10000)
    )


# ============================================================
# GEDI YEARLY AGBD
# ============================================================

def get_yearly_gedi_agbd(
    region,
    year,
):

    start_date = ee.Date.fromYMD(
        year,
        1,
        1,
    )

    end_date = ee.Date.fromYMD(
        year + 1,
        1,
        1,
    )

    collection = (
        ee.ImageCollection(
            "LARSE/GEDI/GEDI04_A_002_MONTHLY"
        )
        .filterDate(
            start_date,
            end_date,
        )
        .filterBounds(
            region
        )
    )

    raw_image_count = int(
        collection
        .size()
        .getInfo()
        or 0
    )

    if raw_image_count == 0:

        return {

            "year":
                year,

            "agbd_mg_ha":
                None,

            "agbd_median_mg_ha":
                None,

            "agbd_min_mg_ha":
                None,

            "agbd_max_mg_ha":
                None,

            "image_count":
                0,

            "valid_pixel_count":
                0,

            "available":
                False,

            "reason":
                (
                    "No GEDI L4A monthly scenes "
                    "intersected the requested region "
                    "and year."
                ),
        }

    def quality_mask(image):

        l4_quality = (
            image
            .select(
                "l4_quality_flag"
            )
            .eq(1)
        )

        not_degraded = (
            image
            .select(
                "degrade_flag"
            )
            .eq(0)
        )

        return (
            image
            .updateMask(
                l4_quality
            )
            .updateMask(
                not_degraded
            )
        )

    quality_collection = (
        collection
        .map(
            quality_mask
        )
        .select(
            "agbd"
        )
    )

    try:

        first_image = (
            quality_collection
            .first()
        )

        projection = (
            first_image
            .select("agbd")
            .projection()
        )

        yearly_agbd = (
            quality_collection
            .mosaic()
            .setDefaultProjection(
                projection
            )
            .clip(
                region
            )
        )

    except Exception as mosaic_error:

        print(
            "GEDI mosaic creation failed:"
        )

        print(
            mosaic_error
        )

        return {

            "year":
                year,

            "agbd_mg_ha":
                None,

            "agbd_median_mg_ha":
                None,

            "agbd_min_mg_ha":
                None,

            "agbd_max_mg_ha":
                None,

            "image_count":
                raw_image_count,

            "valid_pixel_count":
                0,

            "available":
                False,

            "reason":
                (
                    "GEDI scenes were found, "
                    "but a valid AGBD mosaic "
                    "could not be created."
                ),
        }

    valid_count_result = (
        yearly_agbd
        .reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=region,
            scale=25,
            bestEffort=True,
            maxPixels=1_000_000_000,
        )
    )

    valid_count_info = (
        valid_count_result
        .getInfo()
        or {}
    )

    valid_pixel_count = (
        valid_count_info.get(
            "agbd"
        )
    )

    if valid_pixel_count is None:
        valid_pixel_count = 0

    try:

        valid_pixel_count = int(
            valid_pixel_count
        )

    except (
        TypeError,
        ValueError,
    ):

        valid_pixel_count = 0

    if valid_pixel_count <= 0:

        return {

            "year":
                year,

            "agbd_mg_ha":
                None,

            "agbd_median_mg_ha":
                None,

            "agbd_min_mg_ha":
                None,

            "agbd_max_mg_ha":
                None,

            "image_count":
                raw_image_count,

            "valid_pixel_count":
                0,

            "available":
                False,

            "reason":
                (
                    "GEDI scenes intersected the region, "
                    "but no valid quality-filtered AGBD "
                    "pixels were available."
                ),
        }

    stats = (
        yearly_agbd
        .reduceRegion(
            reducer=(
                ee.Reducer.mean()
                .combine(
                    reducer2=ee.Reducer.median(),
                    sharedInputs=True,
                )
                .combine(
                    reducer2=ee.Reducer.minMax(),
                    sharedInputs=True,
                )
            ),
            geometry=region,
            scale=25,
            bestEffort=True,
            maxPixels=1_000_000_000,
        )
        .getInfo()
        or {}
    )

    agbd_mean = stats.get(
        "agbd_mean"
    )

    agbd_median = stats.get(
        "agbd_median"
    )

    agbd_min = stats.get(
        "agbd_min"
    )

    agbd_max = stats.get(
        "agbd_max"
    )

    try:

        agbd_mean = (
            float(agbd_mean)
            if agbd_mean is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):

        agbd_mean = None

    try:

        agbd_median = (
            float(agbd_median)
            if agbd_median is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):

        agbd_median = None

    try:

        agbd_min = (
            float(agbd_min)
            if agbd_min is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):

        agbd_min = None

    try:

        agbd_max = (
            float(agbd_max)
            if agbd_max is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):

        agbd_max = None

    if agbd_mean is None:

        return {

            "year":
                year,

            "agbd_mg_ha":
                None,

            "agbd_median_mg_ha":
                agbd_median,

            "agbd_min_mg_ha":
                agbd_min,

            "agbd_max_mg_ha":
                agbd_max,

            "image_count":
                raw_image_count,

            "valid_pixel_count":
                valid_pixel_count,

            "available":
                False,

            "reason":
                "No numeric AGBD mean was returned by Earth Engine.",
        }

    return {

        "year":
            year,

        "agbd_mg_ha":
            agbd_mean,

        "agbd_median_mg_ha":
            agbd_median,

        "agbd_min_mg_ha":
            agbd_min,

        "agbd_max_mg_ha":
            agbd_max,

        "image_count":
            raw_image_count,

        "valid_pixel_count":
            valid_pixel_count,

        "available":
            True,

        "reason":
            (
                "Valid quality-filtered GEDI L4A "
                "AGBD observations were found."
            ),
    }


# ============================================================
# SEARCH GEDI WITH MULTIPLE RADII
# ============================================================

def find_gedi_year_result(
    latitude,
    longitude,
    requested_radius_m,
    year,
):

    search_radii = []

    candidates = [
        requested_radius_m,
        requested_radius_m * 2,
        5000,
    ]

    for radius in candidates:

        radius = min(
            float(radius),
            5000.0,
        )

        if radius < 100:
            radius = 100.0

        duplicate = any(
            abs(
                existing - radius
            ) < 1
            for existing in search_radii
        )

        if not duplicate:

            search_radii.append(
                radius
            )

    for radius in search_radii:

        region = build_satellite_region(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius,
        )

        result = get_yearly_gedi_agbd(
            region=region,
            year=year,
        )

        if result.get("available"):

            result[
                "search_radius_m"
            ] = radius

            return (
                result,
                region,
                radius,
            )

    return (
        None,
        None,
        None,
    )


# ============================================================
# SENTINEL-2 RGB COMPOSITE
# ============================================================

def get_yearly_sentinel_rgb(
    region,
    year,
    max_cloud_pct,
):

    start_date = ee.Date.fromYMD(
        year,
        1,
        1,
    )

    end_date = ee.Date.fromYMD(
        year + 1,
        1,
        1,
    )

    collection = (
        ee.ImageCollection(
            "COPERNICUS/S2_SR_HARMONIZED"
        )
        .filterDate(
            start_date,
            end_date,
        )
        .filterBounds(
            region
        )
        .filter(
            ee.Filter.lte(
                "CLOUDY_PIXEL_PERCENTAGE",
                max_cloud_pct,
            )
        )
        .map(
            mask_s2_clouds_agb
        )
    )

    scene_count = int(
        collection
        .size()
        .getInfo()
        or 0
    )

    if scene_count == 0:

        return {

            "tile_url":
                None,

            "scene_count":
                0,
        }

    composite = (
        collection
        .median()
        .clip(region)
    )

    visualization = {

        "bands": [
            "B4",
            "B3",
            "B2",
        ],

        "min":
            0.0,

        "max":
            0.3,
    }

    map_id = (
        composite
        .getMapId(
            visualization
        )
    )

    tile_url = (
        map_id[
            "tile_fetcher"
        ].url_format
    )

    return {

        "tile_url":
            tile_url,

        "scene_count":
            scene_count,
    }


# ============================================================
# SATELLITE AGB ANALYSIS
# ============================================================

@app.post(
    "/api/satellite-agb"
)
def satellite_agb_analysis(
    req: SatelliteAGBRequest,
):

    try:

        gee_project = (
            initialize_earth_engine()
        )

        requested_region = (
            build_satellite_region(
                latitude=req.latitude,
                longitude=req.longitude,
                radius_m=req.radius_m,
            )
        )

        historical = []

        search_radius_by_year = {}
        search_region_by_year = {}

        for current_year in range(
            2019,
            req.year + 1,
        ):

            (
                year_result,
                year_region,
                used_radius,
            ) = find_gedi_year_result(
                latitude=req.latitude,
                longitude=req.longitude,
                requested_radius_m=req.radius_m,
                year=current_year,
            )

            if year_result is None:

                year_result = {

                    "year":
                        current_year,

                    "agbd_mg_ha":
                        None,

                    "agbd_median_mg_ha":
                        None,

                    "agbd_min_mg_ha":
                        None,

                    "agbd_max_mg_ha":
                        None,

                    "image_count":
                        0,

                    "valid_pixel_count":
                        0,

                    "available":
                        False,

                    "search_radius_m":
                        None,

                    "reason":
                        (
                            "No valid GEDI L4A AGBD "
                            "observation was found within "
                            "the available search radii."
                        ),
                }

            else:

                search_radius_by_year[
                    current_year
                ] = used_radius

                search_region_by_year[
                    current_year
                ] = year_region

            historical.append(
                year_result
            )

        available_observations = [
            item
            for item in historical
            if (
                item.get("available")
                and item.get("agbd_mg_ha") is not None
            )
        ]

        requested_year_result = next(
            (
                item
                for item in historical
                if item.get("year") == req.year
            ),
            None,
        )

        requested_year_available = bool(
            requested_year_result
            and requested_year_result.get(
                "available"
            )
        )

        fallback_observation = None

        if available_observations:

            fallback_observation = min(
                available_observations,
                key=lambda item: (
                    abs(
                        item["year"]
                        - req.year
                    ),
                    -item["year"],
                ),
            )

        if requested_year_available:

            selected_year_result = (
                requested_year_result
            )

            effective_year = req.year

            effective_region = (
                search_region_by_year.get(
                    req.year,
                    requested_region,
                )
            )

            effective_radius = (
                search_radius_by_year.get(
                    req.year,
                    req.radius_m,
                )
            )

        elif fallback_observation:

            selected_year_result = (
                fallback_observation
            )

            effective_year = (
                fallback_observation[
                    "year"
                ]
            )

            effective_region = (
                search_region_by_year.get(
                    effective_year,
                    requested_region,
                )
            )

            effective_radius = (
                search_radius_by_year.get(
                    effective_year,
                    req.radius_m,
                )
            )

        else:

            selected_year_result = {

                "year":
                    req.year,

                "agbd_mg_ha":
                    None,

                "agbd_median_mg_ha":
                    None,

                "agbd_min_mg_ha":
                    None,

                "agbd_max_mg_ha":
                    None,

                "image_count":
                    0,

                "valid_pixel_count":
                    0,

                "available":
                    False,

                "reason":
                    (
                        "No valid GEDI L4A AGBD "
                        "observations were found from "
                        "2019 through the requested year."
                    ),
            }

            effective_year = None

            effective_region = requested_region
            effective_radius = req.radius_m

        selected_agb = (
            selected_year_result.get(
                "agbd_mg_ha"
            )
        )

        selected_year_available = (
            selected_agb is not None
        )

        latest_available = (
            max(
                available_observations,
                key=lambda item: item["year"],
            )
            if available_observations
            else None
        )

        previous_available = None

        if latest_available:

            earlier_observations = [
                item
                for item in available_observations
                if item["year"]
                < latest_available["year"]
            ]

            if earlier_observations:

                previous_available = max(
                    earlier_observations,
                    key=lambda item: item["year"],
                )

        change_absolute = None
        change_percent = None

        if (
            latest_available
            and previous_available
        ):

            latest_value = (
                latest_available.get(
                    "agbd_mg_ha"
                )
            )

            previous_value = (
                previous_available.get(
                    "agbd_mg_ha"
                )
            )

            if (
                latest_value is not None
                and previous_value is not None
                and previous_value != 0
            ):

                change_absolute = (
                    latest_value
                    - previous_value
                )

                change_percent = (
                    (
                        change_absolute
                        / previous_value
                    )
                    * 100
                )

        available_years = [
            item["year"]
            for item in available_observations
        ]

        sentinel_year = req.year

        sentinel = (
            get_yearly_sentinel_rgb(
                effective_region,
                sentinel_year,
                req.max_cloud_pct,
            )
        )

        if (
            sentinel.get(
                "scene_count",
                0,
            )
            == 0
            and effective_year is not None
            and effective_year != req.year
        ):

            sentinel_year = effective_year

            sentinel = (
                get_yearly_sentinel_rgb(
                    effective_region,
                    sentinel_year,
                    req.max_cloud_pct,
                )
            )

        response = {

            "status":
                "success",

            "gee_project":
                gee_project,

            "location": {

                "latitude":
                    req.latitude,

                "longitude":
                    req.longitude,

                "requested_radius_m":
                    req.radius_m,

                "effective_radius_m":
                    effective_radius,
            },

            "requested_year":
                req.year,

            "requested_year_available":
                requested_year_available,

            "effective_year":
                effective_year,

            "selected_year": {

                "year":
                    selected_year_result.get(
                        "year"
                    ),

                "requested_year":
                    req.year,

                "agbd_mg_ha":
                    selected_agb,

                "available":
                    selected_year_available,

                "is_fallback":
                    (
                        effective_year is not None
                        and effective_year != req.year
                    ),

                "image_count":
                    selected_year_result.get(
                        "image_count",
                        0,
                    ),

                "valid_pixel_count":
                    selected_year_result.get(
                        "valid_pixel_count",
                        0,
                    ),

                "search_radius_m":
                    selected_year_result.get(
                        "search_radius_m",
                        effective_radius,
                    ),

                "agbd_median_mg_ha":
                    selected_year_result.get(
                        "agbd_median_mg_ha"
                    ),

                "agbd_min_mg_ha":
                    selected_year_result.get(
                        "agbd_min_mg_ha"
                    ),

                "agbd_max_mg_ha":
                    selected_year_result.get(
                        "agbd_max_mg_ha"
                    ),

                "reason":
                    selected_year_result.get(
                        "reason"
                    ),
            },

            "latest_available": {

                "year":
                    (
                        latest_available["year"]
                        if latest_available
                        else None
                    ),

                "agbd_mg_ha":
                    (
                        latest_available[
                            "agbd_mg_ha"
                        ]
                        if latest_available
                        else None
                    ),

                "image_count":
                    (
                        latest_available.get(
                            "image_count",
                            0,
                        )
                        if latest_available
                        else 0
                    ),

                "valid_pixel_count":
                    (
                        latest_available.get(
                            "valid_pixel_count",
                            0,
                        )
                        if latest_available
                        else 0
                    ),

                "search_radius_m":
                    (
                        latest_available.get(
                            "search_radius_m"
                        )
                        if latest_available
                        else None
                    ),

                "agbd_median_mg_ha":
                    (
                        latest_available.get(
                            "agbd_median_mg_ha"
                        )
                        if latest_available
                        else None
                    ),
            },

            "previous_available": {

                "year":
                    (
                        previous_available[
                            "year"
                        ]
                        if previous_available
                        else None
                    ),

                "agbd_mg_ha":
                    (
                        previous_available[
                            "agbd_mg_ha"
                        ]
                        if previous_available
                        else None
                    ),

                "image_count":
                    (
                        previous_available.get(
                            "image_count",
                            0,
                        )
                        if previous_available
                        else 0
                    ),

                "valid_pixel_count":
                    (
                        previous_available.get(
                            "valid_pixel_count",
                            0,
                        )
                        if previous_available
                        else 0
                    ),

                "search_radius_m":
                    (
                        previous_available.get(
                            "search_radius_m"
                        )
                        if previous_available
                        else None
                    ),
            },

            "change": {

                "from_year":
                    (
                        previous_available[
                            "year"
                        ]
                        if previous_available
                        else None
                    ),

                "to_year":
                    (
                        latest_available[
                            "year"
                        ]
                        if latest_available
                        else None
                    ),

                "absolute_mg_ha":
                    change_absolute,

                "percent":
                    change_percent,
            },

            "historical":
                historical,

            "available_years":
                available_years,

            "satellite": {

                "collection":
                    "COPERNICUS/S2_SR_HARMONIZED",

                "scene_count":
                    sentinel.get(
                        "scene_count",
                        0,
                    ),

                "tile_url":
                    sentinel.get(
                        "tile_url"
                    ),

                "year":
                    sentinel_year,
            },

            "analysis": {

                "method":
                    (
                        "Quality-filtered GEDI L4A "
                        "aboveground biomass density "
                        "from actual valid GEDI observations "
                        "inside an automatically expanded "
                        "search region."
                    ),

                "agb_unit":
                    "Mg/ha",

                "requested_radius_m":
                    req.radius_m,

                "effective_radius_m":
                    effective_radius,

                "gedi_collection":
                    "LARSE/GEDI/GEDI04_A_002_MONTHLY",

                "quality_filters": [
                    "l4_quality_flag == 1",
                    "degrade_flag == 0",
                ],

                "fallback_enabled":
                    True,

                "fallback_description":
                    (
                        "When the requested year has no "
                        "valid GEDI observation, the nearest "
                        "available GEDI observation year "
                        "between 2019 and the requested year "
                        "is returned and explicitly marked "
                        "as a fallback."
                    ),

                "data_policy":
                    (
                        "Only actual GEDI observations "
                        "are returned. Missing values are "
                        "not fabricated or interpolated."
                    ),
            },
        }

        return make_json_safe(
            response
        )

    except HTTPException:
        raise

    except Exception as exc:

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Satellite AGB analysis failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        )