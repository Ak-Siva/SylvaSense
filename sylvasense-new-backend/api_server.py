# ============================================================
# SYLVASENSE BACKEND
# Memory-safe Render + Earth Engine + Supabase version
# ============================================================

# IMPORTANT:
# Set low CPU/thread usage BEFORE importing numpy / torch.
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pathlib import Path
from functools import lru_cache

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
)

from fastapi.responses import FileResponse

from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

import tempfile
import traceback
import uuid
import math
import urllib.request
import threading
import json
import gc
import time
from datetime import datetime, timezone

import numpy as np

import ee


# ============================================================
# CONFIGURATION
# ============================================================

APP_VERSION = "2.0.0"

MAX_IMAGE_UPLOAD_MB = int(
    os.getenv(
        "MAX_IMAGE_UPLOAD_MB",
        "25",
    )
)

MAX_SATELLITE_IMAGE_MB = int(
    os.getenv(
        "MAX_SATELLITE_IMAGE_MB",
        "8",
    )
)

SATELLITE_IMAGE_TTL_SECONDS = int(
    os.getenv(
        "SATELLITE_IMAGE_TTL_SECONDS",
        "21600",
    )
)

ENABLE_DEEPFOREST = (
    os.getenv(
        "ENABLE_DEEPFOREST",
        "true",
    ).lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)


# ============================================================
# MEMORY / CONCURRENCY PROTECTION
# ============================================================

# Only ONE Earth Engine operation at a time.
EE_REQUEST_LOCK = threading.Lock()

# Only ONE DeepForest image analysis at a time.
IMAGE_ANALYSIS_LOCK = threading.Lock()


# ============================================================
# DIRECTORIES
# ============================================================

JOB_STORAGE_DIR = Path(
    os.getenv(
        "SYLVASENSE_JOB_DIR",
        "/tmp/sylvasense_jobs",
    )
)

JOB_STORAGE_FILE = (
    JOB_STORAGE_DIR / "image_jobs.json"
)

SATELLITE_IMAGE_DIR = Path(
    os.getenv(
        "SYLVASENSE_SATELLITE_DIR",
        "/tmp/sylvasense_satellite_images",
    )
)


def ensure_directories():
    JOB_STORAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SATELLITE_IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


ensure_directories()


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="SYLVASENSE Backend",
    version=APP_VERSION,
    description=(
        "SYLVASENSE Earth Observation platform with "
        "tree detection, crown segmentation, biomass, "
        "AGB analysis, Sentinel-1/Sentinel-2, NDVI, "
        "GEDI and change detection."
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
# JOB STORAGE
# ============================================================

_image_jobs = {}
_image_jobs_lock = threading.Lock()


def load_persisted_jobs():
    ensure_directories()

    if not JOB_STORAGE_FILE.exists():
        return

    try:
        with open(
            JOB_STORAGE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return

        with _image_jobs_lock:
            for job_id, job in data.items():
                if isinstance(job, dict):
                    _image_jobs[job_id] = job

    except Exception as exc:
        print(
            "[JOBS] Could not load persisted jobs:",
            exc,
        )


def save_persisted_jobs():
    ensure_directories()

    try:
        with _image_jobs_lock:
            snapshot = dict(_image_jobs)

        temporary_file = JOB_STORAGE_FILE.with_suffix(
            ".tmp"
        )

        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                snapshot,
                file,
                ensure_ascii=False,
                allow_nan=False,
            )

        os.replace(
            temporary_file,
            JOB_STORAGE_FILE,
        )

    except Exception as exc:
        print(
            "[JOBS] Could not persist jobs:",
            exc,
        )


load_persisted_jobs()


# ============================================================
# MEMORY CLEANUP
# ============================================================

def force_memory_cleanup():
    """
    Run Python garbage collection.

    This does not guarantee that the OS immediately returns
    every allocated page, but it releases unreachable Python
    objects and helps reduce retained memory.
    """
    try:
        gc.collect()
        gc.collect()
    except Exception:
        pass


# ============================================================
# PYTORCH THREAD CONTROL
# ============================================================

def configure_torch_threads():
    try:
        import torch

        try:
            torch.set_num_threads(1)
        except Exception:
            pass

        try:
            torch.set_num_interop_threads(1)
        except Exception:
            pass

    except Exception:
        pass


# ============================================================
# DEEPFOREST MODEL
#
# IMPORTANT:
# No permanent lru_cache is used here.
#
# The model is loaded for one analysis and released after
# analysis so Render does not permanently retain the model.
# ============================================================

def load_deepforest_model():
    if not ENABLE_DEEPFOREST:
        raise RuntimeError(
            "DeepForest image analysis is disabled. "
            "Set ENABLE_DEEPFOREST=true in Render "
            "Environment Variables to enable it."
        )

    configure_torch_threads()

    from tree_detection import load_model

    model = load_model()

    return model


# ============================================================
# IMAGE JOB HELPERS
# ============================================================

def create_image_job(filename):
    job_id = uuid.uuid4().hex

    now = datetime.now(
        timezone.utc
    ).isoformat()

    job = {
        "job_id": job_id,
        "filename": filename,
        "status": "queued",
        "progress": 0,
        "stage": "Queued",
        "message": "Image analysis is queued.",
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    with _image_jobs_lock:
        _image_jobs[job_id] = job

    save_persisted_jobs()

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

        job["updated_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

    save_persisted_jobs()


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
        job["updated_at"] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

    save_persisted_jobs()


def fail_image_job(
    job_id,
    error,
):
    with _image_jobs_lock:
        job = _image_jobs.get(job_id)

        if job is None:
            _image_jobs[job_id] = {
                "job_id": job_id,
                "filename": "unknown",
                "status": "failed",
                "progress": 0,
                "stage": "Failed",
                "message": str(error),
                "result": None,
                "error": str(error),
                "created_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "updated_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }

        else:
            job["status"] = "failed"
            job["stage"] = "Failed"
            job["message"] = str(error)
            job["error"] = str(error)
            job["updated_at"] = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

    save_persisted_jobs()


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

    # Pandas is intentionally imported only when an object
    # actually comes from Pandas.
    obj_module = getattr(
        obj.__class__,
        "__module__",
        "",
    )

    if obj_module.startswith("pandas"):
        try:
            import pandas as pd

            if isinstance(
                obj,
                pd.DataFrame,
            ):
                return make_json_safe(
                    obj.to_dict(
                        orient="records"
                    )
                )

            if isinstance(
                obj,
                pd.Series,
            ):
                return make_json_safe(
                    obj.to_dict()
                )

            if isinstance(
                obj,
                pd.Timestamp,
            ):
                return obj.isoformat()

        except Exception:
            pass

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

    if isinstance(obj, Path):
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

    try:
        missing = obj != obj

        if isinstance(
            missing,
            bool,
        ) and missing:
            return None

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

    return (
        point
        .buffer(radius_m)
        .bounds()
    )


# ============================================================
# EARTH ENGINE INITIALIZATION
# ============================================================

def initialize_earth_engine():

    project = os.getenv(
        "GEE_PROJECT",
        "syylvasense",
    )

    service_account = os.getenv(
        "GEE_SERVICE_ACCOUNT"
    )

    private_key = os.getenv(
        "GEE_PRIVATE_KEY"
    )

    # --------------------------------------------------------
    # RENDER / SERVICE ACCOUNT AUTHENTICATION
    # --------------------------------------------------------

    if service_account and private_key:

        # Render environment variables may contain literal
        # escaped newlines instead of real newlines.
        private_key = (
            private_key
            .replace(
                "\\n",
                "\n",
            )
            .strip()
        )

        credentials = ee.ServiceAccountCredentials(
            service_account,
            key_data=private_key,
        )

        ee.Initialize(
            credentials=credentials,
            project=project,
        )

        return project

    # --------------------------------------------------------
    # LOCAL FALLBACK
    #
    # This allows local development after:
    #
    # earthengine authenticate
    #
    # --------------------------------------------------------

    try:
        ee.Initialize(
            project=project
        )

        return project

    except Exception as exc:

        raise RuntimeError(
            "Google Earth Engine authentication failed. "
            "On Render, configure GEE_PROJECT, "
            "GEE_SERVICE_ACCOUNT and GEE_PRIVATE_KEY. "
            "Locally, run 'earthengine authenticate'. "
            f"Original error: {exc}"
        ) from exc


# ============================================================
# GEE STATUS / DIAGNOSTIC
# ============================================================

@app.get("/api/gee-status")
def gee_status():

    try:

        with EE_REQUEST_LOCK:

            project = (
                initialize_earth_engine()
            )

            test_result = (
                ee.Number(1)
                .add(1)
                .getInfo()
            )

        return {
            "authenticated": True,
            "project": project,
            "test_result": test_result,
            "service_account_configured": bool(
                os.getenv(
                    "GEE_SERVICE_ACCOUNT"
                )
            ),
            "private_key_configured": bool(
                os.getenv(
                    "GEE_PRIVATE_KEY"
                )
            ),
        }

    except Exception as exc:

        traceback.print_exc()

        return {
            "authenticated": False,
            "project": os.getenv(
                "GEE_PROJECT",
                "syylvasense",
            ),
            "service_account_configured": bool(
                os.getenv(
                    "GEE_SERVICE_ACCOUNT"
                )
            ),
            "private_key_configured": bool(
                os.getenv(
                    "GEE_PRIVATE_KEY"
                )
            ),
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }


# ============================================================
# SUPABASE STORAGE
# ============================================================

def get_supabase_client():

    supabase_url = os.getenv(
        "SUPABASE_URL"
    )

    supabase_key = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY"
    )

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL is missing."
        )

    if not supabase_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is missing."
        )


def upload_satellite_image_to_supabase(
    local_path,
    filename,
):

    bucket = os.getenv(
        "SUPABASE_BUCKET",
        "satellite-images",
    )

    client = get_supabase_client()

    storage_path = (
        "sentinel2/"
        + datetime.now(
            timezone.utc
        ).strftime(
            "%Y/%m/%d"
        )
        + "/"
        + uuid.uuid4().hex
        + "_"
        + Path(filename).name
    )

    with open(
        local_path,
        "rb",
    ) as image_file:

        result = (
            client
            .storage
            .from_(bucket)
            .upload(
                storage_path,
                image_file,
                file_options={
                    "content-type":
                        "image/png",
                    "upsert":
                        "true",
                },
            )
        )

    # For a public bucket.
    public_url = (
        client
        .storage
        .from_(bucket)
        .get_public_url(
            storage_path
        )
    )

    return {
        "bucket": bucket,
        "path": storage_path,
        "public_url": public_url,
        "upload_result": str(result),
    }


# ============================================================
# SATELLITE LOCAL IMAGE CLEANUP
# ============================================================

def cleanup_old_satellite_images():

    ensure_directories()

    now = time.time()

    try:

        for path in SATELLITE_IMAGE_DIR.iterdir():

            if not path.is_file():
                continue

            try:
                age = (
                    now
                    - path.stat().st_mtime
                )

                if age > SATELLITE_IMAGE_TTL_SECONDS:
                    path.unlink(
                        missing_ok=True
                    )

            except Exception:
                pass

    except Exception:
        pass


# ============================================================
# SENTINEL-2 CLOUD MASK
# ============================================================

def mask_s2_clouds_satellite(
    image,
):

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

    cleanup_old_satellite_images()

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

    empty_result = {
        "available": False,
        "scene_count": 0,
        "url": None,
        "data_url": None,
        "image_url": None,
        "storage_path": None,
        "date": None,
        "cloud_percentage": None,
        "scene_id": None,
        "center": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "radius_m": radius_m,
    }

    if scene_count == 0:
        return empty_result

    image = ee.Image(
        collection.first()
    )

    image_info = (
        image.getInfo()
        or {}
    )

    properties = (
        image_info.get(
            "properties",
            {},
        )
    )

    scene_id = properties.get(
        "PRODUCT_ID"
    )

    acquisition_millis = (
        properties.get(
            "system:time_start"
        )
    )

    acquisition_date = None

    if acquisition_millis:

        try:

            acquisition_date = (
                datetime.fromtimestamp(
                    acquisition_millis / 1000,
                    tz=timezone.utc,
                ).strftime(
                    "%Y-%m-%d"
                )
            )

        except Exception:
            pass

    cloud_percentage = (
        properties.get(
            "CLOUDY_PIXEL_PERCENTAGE"
        )
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

    local_filename = (
        "satellite_"
        + (
            acquisition_date
            or "image"
        )
        + "_"
        + uuid.uuid4().hex
        + ".png"
    )

    local_path = (
        SATELLITE_IMAGE_DIR
        / local_filename
    )

    image_size_bytes = None
    supabase_info = None

    try:

        request = urllib.request.Request(
            thumbnail_url,
            headers={
                "User-Agent":
                    "SylvaSense/2.0.0"
            },
        )

        max_bytes = (
            MAX_SATELLITE_IMAGE_MB
            * 1024
            * 1024
        )

        downloaded = 0

        with urllib.request.urlopen(
            request,
            timeout=60,
        ) as response:

            with open(
                local_path,
                "wb",
            ) as output:

                while True:

                    chunk = response.read(
                        64 * 1024
                    )

                    if not chunk:
                        break

                    downloaded += len(
                        chunk
                    )

                    if downloaded > max_bytes:

                        raise ValueError(
                            "Satellite thumbnail exceeded "
                            f"{MAX_SATELLITE_IMAGE_MB} MB."
                        )

                    output.write(
                        chunk
                    )

        image_size_bytes = (
            local_path.stat().st_size
        )

        if image_size_bytes <= 0:
            raise ValueError(
                "Earth Engine returned an empty image."
            )

        # ----------------------------------------------------
        # SUPABASE UPLOAD
        # ----------------------------------------------------

        supabase_info = (
            upload_satellite_image_to_supabase(
                local_path=local_path,
                filename=local_filename,
            )
        )

        image_url = (
            supabase_info.get(
                "public_url"
            )
        )

    except Exception as exc:

        print(
            "[SATELLITE] Image storage failed:",
            exc,
        )

        image_url = None

    finally:

        # Local copy is temporary only.
        try:

            if local_path.exists():
                local_path.unlink()

        except Exception:
            pass

    return {
        "available":
            image_url is not None,

        "scene_count":
            scene_count,

        "url":
            thumbnail_url,

        # IMPORTANT:
        # No Base64 data_url anymore.
        "data_url":
            None,

        "image_url":
            image_url,

        "storage":
            "supabase"
            if image_url
            else None,

        "storage_path":
            (
                supabase_info.get(
                    "path"
                )
                if supabase_info
                else None
            ),

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
# ============================================================

def run_image_analysis_job(
    job_id,
    temp_path,
    filename,
):

    model = None
    predictions = None
    segmentation_output = None
    df = None
    biomass_result = None
    response = None

    acquired = False

    try:

        # ----------------------------------------------------
        # SINGLE DEEPFOREST JOB
        # ----------------------------------------------------

        acquired = (
            IMAGE_ANALYSIS_LOCK.acquire(
                timeout=5
            )
        )

        if not acquired:

            fail_image_job(
                job_id,
                (
                    "Another image analysis is currently "
                    "running. Please try again after it finishes."
                ),
            )

            return

        update_image_job(
            job_id,
            1,
            "Starting analysis",
            "Image analysis worker started.",
        )

        print(
            f"[IMAGE ANALYSIS] Starting job: {job_id}"
        )

        # ----------------------------------------------------
        # CHECK DEEPFOREST
        # ----------------------------------------------------

        if not ENABLE_DEEPFOREST:

            raise RuntimeError(
                "DeepForest analysis is disabled. "
                "Set ENABLE_DEEPFOREST=true on Render."
            )

        # ----------------------------------------------------
        # HEAVY MODULES
        # ----------------------------------------------------

        update_image_job(
            job_id,
            3,
            "Loading analysis modules",
            "Loading tree detection and biomass modules...",
        )

        configure_torch_threads()

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

        update_image_job(
            job_id,
            5,
            "Image uploaded",
            "Image uploaded and ready for analysis.",
        )

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        update_image_job(
            job_id,
            10,
            "Loading AI model",
            "Loading the DeepForest tree detection model...",
        )

        print(
            "[IMAGE ANALYSIS] Loading DeepForest..."
        )

        model = load_deepforest_model()

        update_image_job(
            job_id,
            15,
            "AI model ready",
            "DeepForest model loaded successfully.",
        )

        # ----------------------------------------------------
        # TREE DETECTION
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

        tree_count = len(
            predictions
        )

        print(
            f"[IMAGE ANALYSIS] Detected {tree_count} trees."
        )

        # ----------------------------------------------------
        # TREE BOX LOGGING
        # ----------------------------------------------------

        try:

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

        except Exception:
            pass

        update_image_job(
            job_id,
            50,
            "Tree detection complete",
            f"Detected {tree_count} trees.",
        )

        # ----------------------------------------------------
        # CROWN SEGMENTATION
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

        update_image_job(
            job_id,
            70,
            "Crown segmentation complete",
            "Tree crown segmentation completed.",
        )

        # ----------------------------------------------------
        # BIOMASS
        # ----------------------------------------------------

        update_image_job(
            job_id,
            75,
            "Biomass estimation",
            "Calculating aboveground biomass...",
        )

        if predictions.empty:

            biomass_result = {
                "status": "success",
                "tree_count": 0,
                "total_agb_tonnes": 0.0,
                "total_carbon_tonnes": 0.0,
                "total_co2e_tonnes": 0.0,
                "trees": [],
            }

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

        update_image_job(
            job_id,
            90,
            "Biomass estimation complete",
            "Biomass and carbon calculations completed.",
        )

        # ----------------------------------------------------
        # PREPARE RESPONSE
        # ----------------------------------------------------

        update_image_job(
            job_id,
            95,
            "Preparing results",
            "Preparing final analysis results...",
        )

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

        # ----------------------------------------------------
        # RELEASE TEMP FILE
        # ----------------------------------------------------

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            try:
                os.remove(
                    temp_path
                )
            except Exception:
                pass

        # ----------------------------------------------------
        # RELEASE LARGE OBJECTS
        # ----------------------------------------------------

        try:
            del predictions
        except Exception:
            pass

        try:
            del segmentation_output
        except Exception:
            pass

        try:
            del df
        except Exception:
            pass

        try:
            del biomass_result
        except Exception:
            pass

        try:
            del response
        except Exception:
            pass

        # ----------------------------------------------------
        # RELEASE DEEPFOREST MODEL
        # ----------------------------------------------------

        try:
            del model
        except Exception:
            pass

        force_memory_cleanup()

        # ----------------------------------------------------
        # RELEASE SINGLE-JOB LOCK
        # ----------------------------------------------------

        if acquired:

            try:
                IMAGE_ANALYSIS_LOCK.release()
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
            APP_VERSION,
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

        "version":
            APP_VERSION,

        "deepforest_enabled":
            ENABLE_DEEPFOREST,

        "deepforest_model":
            "weecology/deepforest-tree",

        "supabase_storage":
            bool(
                os.getenv(
                    "SUPABASE_URL"
                )
                and os.getenv(
                    "SUPABASE_SERVICE_ROLE_KEY"
                )
            ),

        "earth_engine_service_account":
            bool(
                os.getenv(
                    "GEE_SERVICE_ACCOUNT"
                )
                and os.getenv(
                    "GEE_PRIVATE_KEY"
                )
            ),

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
# ============================================================

@app.post(
    "/api/image-analyze"
)
async def image_analyze(
    file: UploadFile = File(...),
):

    suffix = validate_image(
        file.filename
    )

    # --------------------------------------------------------
    # Prevent multiple analyses from being accepted
    # simultaneously.
    # --------------------------------------------------------

    if IMAGE_ANALYSIS_LOCK.locked():

        raise HTTPException(
            status_code=429,
            detail=(
                "Another image analysis is currently "
                "running. Please wait until it finishes."
            ),
        )

    max_bytes = (
        MAX_IMAGE_UPLOAD_MB
        * 1024
        * 1024
    )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp:

            total = 0

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total += len(
                    chunk
                )

                if total > max_bytes:

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Image file is too large. "
                            f"Maximum size is "
                            f"{MAX_IMAGE_UPLOAD_MB} MB."
                        ),
                    )

                temp.write(
                    chunk
                )

            temp_path = temp.name

        if total <= 0:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        job_id = create_image_job(
            file.filename
        )

        update_image_job(
            job_id,
            1,
            "Starting analysis",
            "Starting image analysis worker...",
        )

        print(
            f"[IMAGE ANALYSIS] Queuing job "
            f"{job_id} for {file.filename}"
        )

        worker = threading.Thread(
            target=run_image_analysis_job,
            args=(
                job_id,
                temp_path,
                file.filename,
            ),
            daemon=True,
            name=(
                f"sylvasense-image-"
                f"{job_id[:8]}"
            ),
        )

        worker.start()

        return {
            "status":
                "accepted",

            "job_id":
                job_id,

            "filename":
                file.filename,

            "progress":
                1,

            "stage":
                "Starting analysis",

            "message":
                "Image analysis worker started.",
        }

    except HTTPException:
        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):
            try:
                os.remove(
                    temp_path
                )
            except Exception:
                pass

        raise

    except Exception as exc:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):
            try:
                os.remove(
                    temp_path
                )
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
                detail=(
                    "Analysis job not found. "
                    "The backend process may have restarted "
                    "while the analysis was running."
                ),
            )

        return make_json_safe(
            {
                "job_id":
                    job.get(
                        "job_id"
                    ),

                "filename":
                    job.get(
                        "filename"
                    ),

                "status":
                    job.get(
                        "status"
                    ),

                "progress":
                    job.get(
                        "progress",
                        0,
                    ),

                "stage":
                    job.get(
                        "stage"
                    ),

                "message":
                    job.get(
                        "message"
                    ),

                "result":
                    job.get(
                        "result"
                    ),

                "error":
                    job.get(
                        "error"
                    ),

                "created_at":
                    job.get(
                        "created_at"
                    ),

                "updated_at":
                    job.get(
                        "updated_at"
                    ),
            }
        )


# ============================================================
# TREE DETECTION
# ============================================================

@app.post(
    "/api/tree-detection"
)
async def tree_detection(
    file: UploadFile = File(...),
):

    return await image_analyze(
        file
    )


# ============================================================
# FORECAST REQUEST
# ============================================================

class ForecastRequest(
    BaseModel
):

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
# FORECAST
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

        from agb_forecasting import (
            forecast_agb,
            calculate_forecast_summary,
        )

        result = forecast_agb(
            req.historical_years,
            req.historical_agb,
            req.forecast_years,
        )

        summary = (
            calculate_forecast_summary(
                result
            )
        )

        response = make_json_safe(
            {
                "status":
                    "success",

                "forecast":
                    result,

                "summary":
                    summary,
            }
        )

        force_memory_cleanup()

        return response

    except Exception as exc:

        traceback.print_exc()

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

class SatelliteAnalysisRequest(
    BaseModel
):

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

    gedi_start_date: str = (
        "2019-03-25"
    )

    gedi_end_date: str = (
        "2024-11-30"
    )

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

    # --------------------------------------------------------
    # ONLY ONE EARTH ENGINE REQUEST PIPELINE AT A TIME
    # --------------------------------------------------------

    acquired = EE_REQUEST_LOCK.acquire(
        timeout=120
    )

    if not acquired:

        raise HTTPException(
            status_code=503,
            detail=(
                "Earth Engine is busy processing "
                "another request. Please try again."
            ),
        )

    try:

        from spectral_layers import (
            get_layer_images,
            SPECTRAL_VIS,
        )

        from lidar_gedi import (
            get_gedi_rh98,
            gedi_statistics,
        )

        gee_project = (
            initialize_earth_engine()
        )

        region = (
            build_satellite_region(
                latitude=req.latitude,
                longitude=req.longitude,
                radius_m=req.radius_m,
            )
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

        satellite_data = (
            get_layer_images(
                region=region,
                start_date=req.start_date,
                end_date=req.end_date,
                max_cloud_pct=req.max_cloud_pct,
            )
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

        for name, params in (
            SPECTRAL_VIS.items()
        ):

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

            layers.append(
                layer
            )

        gedi_image, gedi_count = (
            get_gedi_rh98(
                region=region,
                start_date=req.gedi_start_date,
                end_date=req.gedi_end_date,
            )
        )

        gedi_stats = (
            gedi_statistics(
                region=region,
                start_date=req.gedi_start_date,
                end_date=req.gedi_end_date,
            )
        )

        gedi_vis = {
            "min": 0,
            "max": 40,
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
                        "image_url"
                    ) is not None,

                "image_url":
                    satellite_image.get(
                        "image_url"
                    ),

                "storage":
                    satellite_image.get(
                        "storage"
                    ),

                "storage_path":
                    satellite_image.get(
                        "storage_path"
                    ),

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
                        "image_url"
                    ) is not None,
            },
        }

        result = make_json_safe(
            response
        )

        force_memory_cleanup()

        return result

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

    finally:

        try:
            EE_REQUEST_LOCK.release()
        except Exception:
            pass

        force_memory_cleanup()


# ============================================================
# CHANGE DETECTION REQUEST
# ============================================================

class ChangeDetectionRequest(
    BaseModel
):

    before_date: str = (
        "2025-06-01"
    )

    after_date: str = (
        "2026-02-28"
    )

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

    if (
        req.before_date
        >= req.after_date
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "before_date must be earlier "
                "than after_date."
            ),
        )

    acquired = EE_REQUEST_LOCK.acquire(
        timeout=120
    )

    if not acquired:

        raise HTTPException(
            status_code=503,
            detail=(
                "Earth Engine is busy processing "
                "another request."
            ),
        )

    try:

        gee_project = (
            initialize_earth_engine()
        )

        region = (
            build_satellite_region(
                latitude=req.latitude,
                longitude=req.longitude,
                radius_m=req.radius_m,
            )
        )

        collection = (
            ee.ImageCollection(
                "COPERNICUS/S2_SR_HARMONIZED"
            )
            .filterBounds(
                region
            )
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
                    "for the before period."
                ),
            )

        if after_count == 0:

            raise HTTPException(
                status_code=404,
                detail=(
                    "No Sentinel-2 scenes found "
                    "for the after period."
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
            .getInfo()
        )

        statistics = (
            statistics
            or {}
        )

        mean_change = statistics.get(
            "NDVI_CHANGE_mean"
        )

        min_change = statistics.get(
            "NDVI_CHANGE_min"
        )

        max_change = statistics.get(
            "NDVI_CHANGE_max"
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

        decrease_pixels = (
            decrease_mask
            .reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=region,
                scale=10,
                maxPixels=1_000_000,
                bestEffort=True,
            )
            .get(
                "NDVI_CHANGE"
            )
            .getInfo()
        )

        increase_pixels = (
            increase_mask
            .reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=region,
                scale=10,
                maxPixels=1_000_000,
                bestEffort=True,
            )
            .get(
                "NDVI_CHANGE"
            )
            .getInfo()
        )

        if decrease_pixels is None:
            decrease_pixels = 0

        if increase_pixels is None:
            increase_pixels = 0

        ndvi_vis = {
            "min": -0.2,
            "max": 0.9,
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
            "min": -0.5,
            "max": 0.5,
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

        before_tile_url = (
            before_ndvi
            .getMapId(
                ndvi_vis
            )[
                "tile_fetcher"
            ].url_format
        )

        after_tile_url = (
            after_ndvi
            .getMapId(
                ndvi_vis
            )[
                "tile_fetcher"
            ].url_format
        )

        change_tile_url = (
            ndvi_change
            .getMapId(
                change_vis
            )[
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

                "visualization":
                    change_vis,
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
                        "and before vegetation index."
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

    finally:

        try:
            EE_REQUEST_LOCK.release()
        except Exception:
            pass

        force_memory_cleanup()


# ============================================================
# SATELLITE AGB REQUEST
# ============================================================

class SatelliteAGBRequest(
    BaseModel
):

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

def mask_s2_clouds_agb(
    image,
):

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

    empty = {
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
    }

    if raw_image_count == 0:

        empty["reason"] = (
            "No GEDI L4A monthly scenes "
            "intersected the requested region "
            "and year."
        )

        return empty

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
            .select(
                "agbd"
            )
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

    except Exception as exc:

        print(
            "[GEDI] Mosaic creation failed:",
            exc,
        )

        empty["reason"] = (
            "GEDI scenes were found, "
            "but a valid AGBD mosaic "
            "could not be created."
        )

        return empty

    valid_count_info = (
        yearly_agbd
        .reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=region,
            scale=25,
            bestEffort=True,
            maxPixels=1_000_000_000,
        )
        .getInfo()
        or {}
    )

    valid_pixel_count = (
        valid_count_info.get(
            "agbd"
        )
        or 0
    )

    try:
        valid_pixel_count = int(
            valid_pixel_count
        )
    except Exception:
        valid_pixel_count = 0

    if valid_pixel_count <= 0:

        empty["reason"] = (
            "GEDI scenes intersected the region, "
            "but no valid quality-filtered AGBD "
            "pixels were available."
        )

        return empty

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

    def as_float(value):

        try:
            return (
                float(value)
                if value is not None
                else None
            )
        except Exception:
            return None

    agbd_mean = as_float(
        stats.get(
            "agbd_mean"
        )
    )

    agbd_median = as_float(
        stats.get(
            "agbd_median"
        )
    )

    agbd_min = as_float(
        stats.get(
            "agbd_min"
        )
    )

    agbd_max = as_float(
        stats.get(
            "agbd_max"
        )
    )

    if agbd_mean is None:

        empty.update(
            {
                "agbd_median_mg_ha":
                    agbd_median,

                "agbd_min_mg_ha":
                    agbd_min,

                "agbd_max_mg_ha":
                    agbd_max,

                "valid_pixel_count":
                    valid_pixel_count,

                "reason":
                    (
                        "No numeric AGBD mean "
                        "was returned by Earth Engine."
                    ),
            }
        )

        return empty

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

        if not any(
            abs(
                existing - radius
            ) < 1
            for existing in search_radii
        ):
            search_radii.append(
                radius
            )

    for radius in search_radii:

        region = (
            build_satellite_region(
                latitude=latitude,
                longitude=longitude,
                radius_m=radius,
            )
        )

        result = (
            get_yearly_gedi_agbd(
                region=region,
                year=year,
            )
        )

        if result.get(
            "available"
        ):

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
# SENTINEL-2 YEARLY RGB
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
        .clip(
            region
        )
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

    map_id = (
        composite
        .getMapId(
            visualization
        )
    )

    return {
        "tile_url":
            map_id[
                "tile_fetcher"
            ].url_format,

        "scene_count":
            scene_count,
    }


# ============================================================
# SATELLITE AGB
# ============================================================

@app.post(
    "/api/satellite-agb"
)
def satellite_agb_analysis(
    req: SatelliteAGBRequest,
):

    acquired = EE_REQUEST_LOCK.acquire(
        timeout=120
    )

    if not acquired:

        raise HTTPException(
            status_code=503,
            detail=(
                "Earth Engine is busy processing "
                "another request."
            ),
        )

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
                            "No valid GEDI L4A "
                            "AGBD observation was found."
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
                item.get(
                    "available"
                )
                and item.get(
                    "agbd_mg_ha"
                )
                is not None
            )
        ]

        requested_year_result = next(
            (
                item
                for item in historical
                if item.get(
                    "year"
                ) == req.year
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
                        "No valid GEDI L4A "
                        "AGBD observations were found."
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
                key=lambda item:
                    item["year"],
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
                    key=lambda item:
                        item["year"],
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
                    change_absolute
                    / previous_value
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
            ) == 0
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
                        latest_available[
                            "year"
                        ]
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
                        "from actual valid GEDI observations."
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

                "data_policy":
                    (
                        "Only actual GEDI observations "
                        "are returned."
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

    finally:

        try:
            EE_REQUEST_LOCK.release()
        except Exception:
            pass

        force_memory_cleanup()


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():

    ensure_directories()

    print(
        "============================================"
    )

    print(
        "SYLVASENSE BACKEND STARTED"
    )

    print(
        f"Version: {APP_VERSION}"
    )

    print(
        f"DeepForest enabled: {ENABLE_DEEPFOREST}"
    )

    print(
        "Earth Engine service-account configured:",
        bool(
            os.getenv(
                "GEE_SERVICE_ACCOUNT"
            )
            and os.getenv(
                "GEE_PRIVATE_KEY"
            )
        ),
    )

    print(
        "Supabase configured:",
        bool(
            os.getenv(
                "SUPABASE_URL"
            )
            and os.getenv(
                "SUPABASE_SERVICE_ROLE_KEY"
            )
        ),
    )

    print(
        "============================================"
    )