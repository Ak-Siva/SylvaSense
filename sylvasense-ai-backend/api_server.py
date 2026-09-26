# ============================================================
# SYLVASENSE AI BACKEND
#
# Handles:
#   - DeepForest tree detection
#   - Crown metrics
#   - Crown segmentation
#   - Per-tree biomass
#   - Image analysis
#
# Earth Engine remains on the Render backend.
# ============================================================

import os

# ============================================================
# LOW CPU / THREAD USAGE
# MUST BE SET BEFORE NUMPY / TORCH IMPORTS
# ============================================================

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")


# ============================================================
# IMPORTS
# ============================================================

from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
)

from fastapi.middleware.cors import CORSMiddleware

import tempfile
import traceback
import uuid
import threading

import numpy as np
import pandas as pd


# ============================================================
# LOCAL MODULES
#
# tree_detection itself uses lazy imports for DeepForest,
# PyTorch Lightning and matplotlib.
# ============================================================

from tree_detection import (
    load_model,
    detect_trees,
    compute_crown_metrics,
)

from crown_segmentation import (
    segment_tree_crowns,
)

from biomass import (
    per_tree_biomass_pipeline,
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="SYLVASENSE AI Backend",
    version="1.2.0",
    description=(
        "SYLVASENSE AI service for DeepForest tree "
        "detection, crown metrics, crown segmentation "
        "and per-tree aboveground biomass estimation."
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
#
# Do NOT use functools.lru_cache here.
#
# A normal singleton protected by a lock makes model
# initialization explicit and prevents duplicate initialization
# if two requests arrive close together.
# ============================================================

_deepforest_model = None
_model_lock = threading.Lock()


def get_deepforest_model():
    """
    Return the single shared DeepForest model.

    The model is loaded only once per backend process.
    """

    global _deepforest_model

    # --------------------------------------------------------
    # Fast path:
    # Model has already been loaded.
    # --------------------------------------------------------

    if _deepforest_model is not None:

        print(
            "DeepForest model already loaded. "
            "Using existing model."
        )

        return _deepforest_model

    # --------------------------------------------------------
    # Slow path:
    # Only one thread is allowed to initialize the model.
    # --------------------------------------------------------

    with _model_lock:

        # ----------------------------------------------------
        # Double-check after acquiring the lock.
        # Another thread may have initialized the model while
        # this thread was waiting.
        # ----------------------------------------------------

        if _deepforest_model is not None:

            print(
                "DeepForest model initialized by another "
                "thread. Using existing model."
            )

            return _deepforest_model

        print("=" * 60)
        print("DEEPFOREST MODEL INITIALIZATION")
        print("=" * 60)

        try:

            print(
                "Calling tree_detection.load_model()..."
            )

            model = load_model()

            if model is None:

                raise RuntimeError(
                    "tree_detection.load_model() "
                    "returned None."
                )

            _deepforest_model = model

            print(
                "DeepForest model loaded successfully."
            )

            print(
                "DeepForest model is now cached "
                "for this process."
            )

            print("=" * 60)

            return _deepforest_model

        except Exception as exc:

            print("=" * 60)
            print(
                "DEEPFOREST MODEL INITIALIZATION FAILED"
            )
            print(
                f"Error type: {type(exc).__name__}"
            )
            print(
                f"Error: {exc}"
            )
            print("=" * 60)

            traceback.print_exc()

            # Do not leave a partially initialized model.
            _deepforest_model = None

            raise


# ============================================================
# IMAGE JOB STORAGE
# ============================================================

_image_jobs = {}

_image_jobs_lock = threading.Lock()


def create_image_job():

    job_id = str(
        uuid.uuid4()
    )

    with _image_jobs_lock:

        _image_jobs[job_id] = {

            "job_id":
                job_id,

            "status":
                "queued",

            "progress":
                0,

            "stage":
                "Queued",

            "message":
                "Image analysis queued.",

            "result":
                None,

            "error":
                None,
        }

    return job_id


def update_image_job(
    job_id,
    progress=None,
    stage=None,
    message=None,
    status=None,
):

    with _image_jobs_lock:

        job = _image_jobs.get(
            job_id
        )

        if job is None:
            return

        if progress is not None:

            job["progress"] = int(
                max(
                    0,
                    min(
                        100,
                        progress,
                    ),
                )
            )

        if stage is not None:
            job["stage"] = stage

        if message is not None:
            job["message"] = message

        if status is not None:
            job["status"] = status


def complete_image_job(
    job_id,
    result,
):

    with _image_jobs_lock:

        job = _image_jobs.get(
            job_id
        )

        if job is None:
            return

        job["status"] = "completed"

        job["progress"] = 100

        job["stage"] = "Completed"

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

        job = _image_jobs.get(
            job_id
        )

        if job is None:
            return

        job["status"] = "failed"

        job["stage"] = "Failed"

        job["message"] = (
            "Image analysis failed."
        )

        job["error"] = str(
            error
        )


# ============================================================
# JSON SERIALIZATION
# ============================================================

def make_json_safe(obj):

    if isinstance(
        obj,
        dict,
    ):

        return {
            str(key): make_json_safe(value)
            for key, value in obj.items()
        }

    if isinstance(
        obj,
        list,
    ):

        return [
            make_json_safe(value)
            for value in obj
        ]

    if isinstance(
        obj,
        tuple,
    ):

        return [
            make_json_safe(value)
            for value in obj
        ]

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
        np.ndarray,
    ):

        return make_json_safe(
            obj.tolist()
        )

    if isinstance(
        obj,
        np.integer,
    ):

        return int(obj)

    if isinstance(
        obj,
        np.floating,
    ):

        value = float(obj)

        if not np.isfinite(value):
            return None

        return value

    if isinstance(
        obj,
        np.bool_,
    ):

        return bool(obj)

    if isinstance(
        obj,
        float,
    ):

        if not np.isfinite(obj):
            return None

        return obj

    if obj is None:
        return None

    if isinstance(
        obj,
        (
            str,
            int,
            bool,
        ),
    ):

        return obj

    if isinstance(
        obj,
        Path,
    ):

        return str(obj)

    try:

        missing = pd.isna(
            obj
        )

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

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def validate_image(filename):

    if not filename:

        raise HTTPException(
            status_code=400,
            detail=(
                "No image filename provided."
            ),
        )

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if extension not in ALLOWED_IMAGE_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Supported formats: "
                "JPG, JPEG, PNG, TIFF, TIF, WEBP."
            ),
        )


# ============================================================
# NORMALIZE DEEPFOREST DETECTION OUTPUT
# ============================================================

def normalize_detection_result(
    detections,
):

    if detections is None:

        return pd.DataFrame()

    if isinstance(
        detections,
        pd.DataFrame,
    ):

        return detections.copy()

    if isinstance(
        detections,
        (
            list,
            tuple,
        ),
    ):

        try:

            return pd.DataFrame(
                detections
            )

        except Exception as exc:

            raise RuntimeError(
                "Unable to convert DeepForest "
                "detection list to DataFrame: "
                f"{type(exc).__name__}: {exc}"
            )

    if isinstance(
        detections,
        np.ndarray,
    ):

        try:

            return pd.DataFrame(
                detections
            )

        except Exception as exc:

            raise RuntimeError(
                "Unable to convert DeepForest "
                "NumPy output to DataFrame: "
                f"{type(exc).__name__}: {exc}"
            )

    try:

        normalized = pd.DataFrame(
            detections
        )

        return normalized

    except Exception as exc:

        raise RuntimeError(
            "DeepForest returned an unsupported "
            "detection result. "
            f"Type: {type(detections).__name__}. "
            f"Error: {exc}"
        )


# ============================================================
# VALIDATE DETECTION COLUMNS
# ============================================================

def validate_detection_columns(
    detections_df,
):

    if detections_df.empty:
        return

    expected_columns = [
        "xmin",
        "ymin",
        "xmax",
        "ymax",
    ]

    missing_columns = [
        column
        for column in expected_columns
        if column not in detections_df.columns
    ]

    if missing_columns:

        raise RuntimeError(
            "DeepForest detection output is missing "
            "required bounding-box columns: "
            + ", ".join(
                missing_columns
            )
            + ". Returned columns: "
            + ", ".join(
                map(
                    str,
                    detections_df.columns,
                )
            )
        )


# ============================================================
# IMAGE ANALYSIS BACKGROUND JOB
# ============================================================

def run_image_analysis_job(
    job_id,
    image_path,
    original_filename,
):

    try:

        # ====================================================
        # 5%
        # PREPARING
        # ====================================================

        update_image_job(
            job_id,
            progress=5,
            stage="Preparing",
            message=(
                "Preparing image for AI analysis."
            ),
            status="running",
        )

        if not os.path.exists(
            image_path
        ):

            raise FileNotFoundError(
                f"Image file not found: "
                f"{image_path}"
            )

        # ====================================================
        # 10%
        # MODEL
        # ====================================================

        update_image_job(
            job_id,
            progress=10,
            stage="Loading model",
            message=(
                "Loading DeepForest tree detection model."
            ),
        )

        print("=" * 60)
        print(
            "IMAGE ANALYSIS: MODEL STAGE"
        )
        print(
            f"Job ID: {job_id}"
        )
        print(
            f"File: {original_filename}"
        )
        print("=" * 60)

        model = get_deepforest_model()

        print(
            "IMAGE ANALYSIS: MODEL READY"
        )

        # ====================================================
        # 20%
        # TREE DETECTION
        # ====================================================

        update_image_job(
            job_id,
            progress=20,
            stage="Tree detection",
            message=(
                "Detecting individual trees."
            ),
        )

        print("=" * 60)

        print(
            "Starting DeepForest tree detection..."
        )

        print(
            f"Image: {original_filename}"
        )

        print("=" * 60)

        raw_detections = detect_trees(
            model,
            image_path,
            patch_size=400,
            patch_overlap=0.25,
            iou_threshold=0.15,
        )

        # ----------------------------------------------------
        # Keep AI processing in DataFrame format.
        # ----------------------------------------------------

        detections_df = (
            normalize_detection_result(
                raw_detections
            )
        )

        validate_detection_columns(
            detections_df
        )

        print(
            "DeepForest raw result type:",
            type(
                raw_detections
            ).__name__,
        )

        print(
            "Normalized detection type:",
            type(
                detections_df
            ).__name__,
        )

        print(
            "Detection columns:",
            list(
                detections_df.columns
            ),
        )

        tree_count = len(
            detections_df
        )

        print(
            f"Tree detection complete: "
            f"{tree_count} trees"
        )

        # ====================================================
        # 40%
        # PREPARE CROWN METRICS
        # ====================================================

        update_image_job(
            job_id,
            progress=40,
            stage="Preparing crown metrics",
            message=(
                f"Preparing crown metrics for "
                f"{tree_count} detected trees."
            ),
        )

        # ====================================================
        # 50%
        # CROWN METRICS
        # ====================================================

        update_image_job(
            job_id,
            progress=50,
            stage="Crown metrics",
            message=(
                "Calculating tree crown metrics."
            ),
        )

        crown_metrics_result = (
            compute_crown_metrics(
                detections_df,
                pixel_size_m=0.1,
            )
        )

        # ----------------------------------------------------
        # Support either:
        #
        # 1. DataFrame output
        # 2. Dictionary output
        #
        # from tree_detection.py
        # ----------------------------------------------------

        if crown_metrics_result is None:

            crown_metrics_df = (
                pd.DataFrame()
            )

        elif isinstance(
            crown_metrics_result,
            pd.DataFrame,
        ):

            crown_metrics_df = (
                crown_metrics_result
            )

        elif isinstance(
            crown_metrics_result,
            dict,
        ):

            crown_metrics_df = pd.DataFrame(
                [
                    crown_metrics_result
                ]
            )

        else:

            try:

                crown_metrics_df = pd.DataFrame(
                    crown_metrics_result
                )

            except Exception as exc:

                raise RuntimeError(
                    "compute_crown_metrics() returned "
                    f"{type(crown_metrics_result).__name__}. "
                    f"Could not normalize: {exc}"
                )

        print(
            "Crown metrics complete."
        )

        print(
            "Crown metrics type:",
            type(
                crown_metrics_result
            ).__name__,
        )

        # ====================================================
        # 55%
        # CROWN SEGMENTATION
        # ====================================================

        update_image_job(
            job_id,
            progress=55,
            stage="Crown segmentation",
            message=(
                "Segmenting individual tree crowns."
            ),
        )

        segmentation_output = (
            segment_tree_crowns(
                image_path,
                crown_metrics_df,
                pixel_size_m=0.1,
            )
        )

        # ----------------------------------------------------
        # Expected:
        #
        # (segmentation_dataframe, crown_masks)
        # ----------------------------------------------------

        if not isinstance(
            segmentation_output,
            (
                tuple,
                list,
            ),
        ):

            raise RuntimeError(
                "segment_tree_crowns() must return "
                "(DataFrame, masks). "
                f"Received: "
                f"{type(segmentation_output).__name__}"
            )

        if len(
            segmentation_output
        ) != 2:

            raise RuntimeError(
                "segment_tree_crowns() must return "
                "exactly two values: "
                "segmentation DataFrame and masks."
            )

        segmentation_df = (
            segmentation_output[0]
        )

        crown_masks = (
            segmentation_output[1]
        )

        if segmentation_df is None:

            segmentation_df = (
                pd.DataFrame()
            )

        if not isinstance(
            segmentation_df,
            pd.DataFrame,
        ):

            try:

                segmentation_df = pd.DataFrame(
                    segmentation_df
                )

            except Exception as exc:

                raise RuntimeError(
                    "Crown segmentation result could "
                    "not be converted to DataFrame: "
                    f"{exc}"
                )

        if crown_masks is None:

            crown_masks = []

        elif not isinstance(
            crown_masks,
            list,
        ):

            try:

                crown_masks = list(
                    crown_masks
                )

            except Exception as exc:

                raise RuntimeError(
                    "Crown segmentation masks could "
                    "not be converted to list: "
                    f"{exc}"
                )

        print(
            "Crown segmentation complete."
        )

        print(
            f"Segmentation rows: "
            f"{len(segmentation_df)}"
        )

        print(
            f"Crown masks: "
            f"{len(crown_masks)}"
        )

        # ====================================================
        # CANOPY METRICS
        # ====================================================

        canopy_coverage_percent = 0.0

        total_crown_area_m2 = 0.0

        canopy_pixels = 0

        total_image_pixels = 0

        # ----------------------------------------------------
        # Read segmentation-derived values when available.
        # ----------------------------------------------------

        if not segmentation_df.empty:

            if (
                "canopy_coverage_percent"
                in segmentation_df.columns
            ):

                value = (
                    segmentation_df[
                        "canopy_coverage_percent"
                    ].iloc[0]
                )

                if pd.notna(value):

                    canopy_coverage_percent = float(
                        value
                    )

            if (
                "total_crown_area_m2"
                in segmentation_df.columns
            ):

                value = (
                    segmentation_df[
                        "total_crown_area_m2"
                    ].iloc[0]
                )

                if pd.notna(value):

                    total_crown_area_m2 = float(
                        value
                    )

            if (
                "canopy_pixels"
                in segmentation_df.columns
            ):

                value = (
                    segmentation_df[
                        "canopy_pixels"
                    ].iloc[0]
                )

                if pd.notna(value):

                    canopy_pixels = int(
                        value
                    )

            if (
                "total_image_pixels"
                in segmentation_df.columns
            ):

                value = (
                    segmentation_df[
                        "total_image_pixels"
                    ].iloc[0]
                )

                if pd.notna(value):

                    total_image_pixels = int(
                        value
                    )

        # ----------------------------------------------------
        # Fallback to crown_metrics_result dictionary.
        #
        # This is useful with the current tree_detection.py.
        # ----------------------------------------------------

        if (
            isinstance(
                crown_metrics_result,
                dict,
            )
        ):

            if total_crown_area_m2 <= 0:

                total_crown_area_m2 = float(
                    crown_metrics_result.get(
                        "total_crown_area_m2",
                        0.0,
                    )
                    or 0.0
                )

        # ====================================================
        # 70%
        # BIOMASS
        # ====================================================

        update_image_job(
            job_id,
            progress=70,
            stage="Biomass estimation",
            message=(
                "Estimating per-tree aboveground biomass."
            ),
        )

        biomass_input_df = (
            segmentation_df.copy()
        )

        # ----------------------------------------------------
        # Ensure crown diameter exists.
        # ----------------------------------------------------

        if (
            "segmentation_crown_diameter_m"
            in biomass_input_df.columns
        ):

            biomass_input_df[
                "biomass_crown_diameter_m"
            ] = pd.to_numeric(
                biomass_input_df[
                    "segmentation_crown_diameter_m"
                ],
                errors="coerce",
            )

        elif (
            "crown_diameter_m"
            in biomass_input_df.columns
        ):

            biomass_input_df[
                "biomass_crown_diameter_m"
            ] = pd.to_numeric(
                biomass_input_df[
                    "crown_diameter_m"
                ],
                errors="coerce",
            )

        else:

            if not biomass_input_df.empty:

                raise RuntimeError(
                    "No crown diameter column was "
                    "available for biomass estimation."
                )

            biomass_input_df[
                "biomass_crown_diameter_m"
            ] = pd.Series(
                dtype=float
            )

        # ----------------------------------------------------
        # Convert invalid values to NaN.
        # ----------------------------------------------------

        biomass_input_df[
            "biomass_crown_diameter_m"
        ] = pd.to_numeric(
            biomass_input_df[
                "biomass_crown_diameter_m"
            ],
            errors="coerce",
        )

        # ----------------------------------------------------
        # Fallback to standard crown diameter.
        # ----------------------------------------------------

        invalid_biomass_diameter = (
            biomass_input_df[
                "biomass_crown_diameter_m"
            ].isna()
            |
            (
                biomass_input_df[
                    "biomass_crown_diameter_m"
                ]
                <= 0
            )
        )

        if (
            "crown_diameter_m"
            in biomass_input_df.columns
        ):

            fallback_diameter = pd.to_numeric(
                biomass_input_df[
                    "crown_diameter_m"
                ],
                errors="coerce",
            )

            biomass_input_df.loc[
                invalid_biomass_diameter,
                "biomass_crown_diameter_m",
            ] = fallback_diameter[
                invalid_biomass_diameter
            ]

        # ----------------------------------------------------
        # Final validation.
        # ----------------------------------------------------

        if not biomass_input_df.empty:

            remaining_invalid = (
                biomass_input_df[
                    "biomass_crown_diameter_m"
                ].isna()
                |
                (
                    biomass_input_df[
                        "biomass_crown_diameter_m"
                    ]
                    <= 0
                )
            )

            invalid_count = int(
                remaining_invalid.sum()
            )

            if invalid_count > 0:

                print(
                    f"Warning: {invalid_count} trees "
                    "have invalid crown diameter."
                )

        # ====================================================
        # BIOMASS PIPELINE
        # ====================================================

        biomass_result_df = (
            per_tree_biomass_pipeline(
                biomass_input_df,
                wood_density_g_cm3=0.6,
                crown_diameter_column=(
                    "biomass_crown_diameter_m"
                ),
            )
        )

        if biomass_result_df is None:

            biomass_result_df = (
                pd.DataFrame()
            )

        if not isinstance(
            biomass_result_df,
            pd.DataFrame,
        ):

            try:

                biomass_result_df = pd.DataFrame(
                    biomass_result_df
                )

            except Exception as exc:

                raise RuntimeError(
                    "Biomass pipeline result could "
                    "not be converted to DataFrame: "
                    f"{exc}"
                )

        print(
            "Biomass estimation complete."
        )

        # ====================================================
        # BIOMASS SUMMARY
        # ====================================================

        total_agb_kg = 0.0

        total_agb_tonnes = 0.0

        total_carbon_tonnes = 0.0

        total_co2e_tonnes = 0.0

        if not biomass_result_df.empty:

            if (
                "agb_kg"
                in biomass_result_df.columns
            ):

                total_agb_kg = float(
                    pd.to_numeric(
                        biomass_result_df[
                            "agb_kg"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )

            if (
                "agb_tonnes"
                in biomass_result_df.columns
            ):

                total_agb_tonnes = float(
                    pd.to_numeric(
                        biomass_result_df[
                            "agb_tonnes"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )

            if (
                "carbon_tonnes"
                in biomass_result_df.columns
            ):

                total_carbon_tonnes = float(
                    pd.to_numeric(
                        biomass_result_df[
                            "carbon_tonnes"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )

            if (
                "co2e_tonnes"
                in biomass_result_df.columns
            ):

                total_co2e_tonnes = float(
                    pd.to_numeric(
                        biomass_result_df[
                            "co2e_tonnes"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )

        # ====================================================
        # 90%
        # GENERATING RESULTS
        # ====================================================

        update_image_job(
            job_id,
            progress=90,
            stage="Generating results",
            message=(
                "Combining tree detection, crown "
                "segmentation and biomass results."
            ),
        )

        # ====================================================
        # SEGMENTATION SUMMARY
        # ====================================================

        valid_segmentations = 0

        if (
            not segmentation_df.empty
            and
            "segmentation_valid"
            in segmentation_df.columns
        ):

            valid_segmentations = int(
                pd.to_numeric(
                    segmentation_df[
                        "segmentation_valid"
                    ],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        result = {

            "status":
                "success",

            "filename":
                original_filename,

            "tree_count":
                int(tree_count),

            "detections":
                detections_df,

            "crown_metrics":
                crown_metrics_df,

            "crown_segmentation":
                segmentation_df,

            "biomass":
                biomass_result_df,

            "canopy_metrics": {

                "canopy_coverage_percent":
                    canopy_coverage_percent,

                "total_crown_area_m2":
                    total_crown_area_m2,

                "canopy_pixels":
                    canopy_pixels,

                "total_image_pixels":
                    total_image_pixels,
            },

            "biomass_summary": {

                "total_agb_kg":
                    total_agb_kg,

                "total_agb_tonnes":
                    total_agb_tonnes,

                "total_carbon_tonnes":
                    total_carbon_tonnes,

                "total_co2e_tonnes":
                    total_co2e_tonnes,
            },

            "segmentation_summary": {

                "tree_masks":
                    len(crown_masks),

                "valid_segmentations":
                    valid_segmentations,
            },

            "model":
                "weecology/deepforest-tree",

            "parameters": {

                "patch_size":
                    400,

                "patch_overlap":
                    0.25,

                "iou_threshold":
                    0.15,

                "pixel_size_m":
                    0.1,

                "wood_density_g_cm3":
                    0.6,

                "biomass_method":
                    "Chave et al. 2014",

                "dbh_method":
                    "Jucker et al. 2017",

                "height_method":
                    "Feldpausch et al. 2012",
            },
        }

        # ====================================================
        # 95%
        # FINALIZING
        # ====================================================

        update_image_job(
            job_id,
            progress=95,
            stage="Finalizing",
            message=(
                "Finalizing AI analysis."
            ),
        )

        # ====================================================
        # 100%
        # COMPLETE
        # ====================================================

        complete_image_job(
            job_id,
            make_json_safe(
                result
            ),
        )

        print("=" * 60)

        print(
            "IMAGE ANALYSIS COMPLETED"
        )

        print(
            f"Trees: {tree_count}"
        )

        print(
            f"Canopy coverage: "
            f"{canopy_coverage_percent:.2f}%"
        )

        print(
            f"AGB: "
            f"{total_agb_tonnes:.4f} tonnes"
        )

        print("=" * 60)

    except Exception as exc:

        traceback.print_exc()

        print("=" * 60)

        print(
            "IMAGE ANALYSIS FAILED"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 60)

        fail_image_job(
            job_id,
            (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    finally:

        # ----------------------------------------------------
        # Always remove temporary upload.
        # ----------------------------------------------------

        try:

            if os.path.exists(
                image_path
            ):

                os.remove(
                    image_path
                )

        except Exception as cleanup_error:

            print(
                "Temporary image cleanup failed:"
            )

            print(
                cleanup_error
            )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "service":
            "SYLVASENSE AI backend",

        "status":
            "online",

        "docs":
            "/docs",

        "version":
            "1.2.0",
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
            "SYLVASENSE AI backend",

        "modules": [

            "deepforest",

            "tree_detection",

            "crown_segmentation",

            "per_tree_biomass",

            "image_analysis_progress",

        ],

        "earth_engine":
            "handled_by_render_backend",
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):

    validate_image(
        file.filename
    )

    original_filename = (
        file.filename
        or "uploaded_image"
    )

    extension = (
        Path(original_filename)
        .suffix
        .lower()
    )

    if not extension:

        extension = ".png"

    job_id = create_image_job()

    temp_path = None

    try:

        contents = await file.read()

        if not contents:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Uploaded image is empty."
                ),
            )

        # ----------------------------------------------------
        # 50 MB maximum
        # ----------------------------------------------------

        max_size = (
            50
            * 1024
            * 1024
        )

        if len(contents) > max_size:

            raise HTTPException(
                status_code=413,
                detail=(
                    "Image is too large. "
                    "Maximum supported size is 50 MB."
                ),
            )

        # ----------------------------------------------------
        # Temporary file
        # ----------------------------------------------------

        temp_file = (
            tempfile.NamedTemporaryFile(
                delete=False,
                suffix=extension,
            )
        )

        temp_path = (
            temp_file.name
        )

        temp_file.write(
            contents
        )

        temp_file.close()

        # ----------------------------------------------------
        # Queue job
        # ----------------------------------------------------

        update_image_job(
            job_id,
            progress=2,
            stage="Uploaded",
            message=(
                "Image uploaded successfully."
            ),
            status="queued",
        )

        background_tasks.add_task(
            run_image_analysis_job,
            job_id,
            temp_path,
            original_filename,
        )

        return {

            "status":
                "queued",

            "job_id":
                job_id,

            "filename":
                original_filename,

            "message":
                (
                    "Image uploaded successfully. "
                    "AI analysis has started."
                ),

            "progress_url":
                (
                    "/api/image-analysis-progress/"
                    + job_id
                ),
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

        fail_image_job(
            job_id,
            exc,
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Image upload failed: "
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
                    f"Image analysis job "
                    f"{job_id} was not found."
                ),
            )

        return make_json_safe(
            job
        )


# ============================================================
# TREE DETECTION ALIAS
# ============================================================

@app.post(
    "/api/tree-detection"
)
async def tree_detection_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):

    return await image_analyze(
        background_tasks,
        file,
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event(
    "startup"
)
async def startup_event():

    print("=" * 60)

    print(
        "SYLVASENSE AI BACKEND STARTING"
    )

    print(
        "Earth Engine: Render backend"
    )

    print(
        "DeepForest: AI backend"
    )

    print(
        "Crown segmentation: AI backend"
    )

    print(
        "Per-tree biomass: AI backend"
    )

    print(
        "DeepForest model: lazy-loaded"
    )

    print(
        "Model initialization: thread-safe"
    )

    print("=" * 60)


# ============================================================
# END
# ============================================================