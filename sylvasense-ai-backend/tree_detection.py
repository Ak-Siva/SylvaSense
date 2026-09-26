# ============================================================
# SYLVASENSE AI - TREE DETECTION
# Memory-conscious DeepForest tree detection backend
# ============================================================

import os

# ------------------------------------------------------------
# CPU / THREAD LIMITS
# Must be configured before heavy ML libraries are imported.
# ------------------------------------------------------------

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# Keep PyTorch CPU usage conservative.
os.environ.setdefault("TORCH_NUM_THREADS", "1")


# ------------------------------------------------------------
# Standard imports
# ------------------------------------------------------------

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from PIL import Image


# ------------------------------------------------------------
# Lazy imports
# ------------------------------------------------------------

def get_deepforest_main():
    """
    Import DeepForest only when the model is actually required.
    This keeps FastAPI startup memory usage low.
    """
    from deepforest import main
    return main


def get_deepforest_data():
    """
    Import DeepForest sample-data utilities only when required.
    """
    from deepforest import get_data
    return get_data


def get_matplotlib():
    """
    Import matplotlib only when visualization is requested.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    return plt, patches


def configure_torch_for_cpu():
    """
    Configure PyTorch for low-memory CPU inference.
    """
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

        return torch

    except Exception as exc:
        print(f"PyTorch CPU configuration warning: {exc}")
        return None


# ------------------------------------------------------------
# MODEL LOADING
# ------------------------------------------------------------

def load_model():
    """
    Load the pretrained DeepForest tree-crown detection model.

    The model is loaded lazily so importing this module does not
    immediately consume the memory required by DeepForest.
    """

    print("=" * 60)
    print("Loading DeepForest model...")
    print("=" * 60)

    # Configure CPU before loading the model.
    torch = configure_torch_for_cpu()

    # Import DeepForest only now.
    main = get_deepforest_main()

    print("Creating DeepForest model object...")

    model = main.deepforest()

    print("Downloading/loading pretrained DeepForest model...")

    model.load_model(
        model_name="weecology/deepforest-tree",
        revision="main",
    )

    # --------------------------------------------------------
    # Force CPU where supported.
    # --------------------------------------------------------

    if torch is not None:
        try:
            model.model.cpu()
            print("DeepForest neural network moved to CPU.")
        except Exception as exc:
            print(f"CPU model move warning: {exc}")

    # --------------------------------------------------------
    # Put neural network into evaluation mode.
    # --------------------------------------------------------

    try:
        if hasattr(model, "model") and hasattr(model.model, "eval"):
            model.model.eval()
    except Exception as exc:
        print(f"Evaluation-mode warning: {exc}")

    # --------------------------------------------------------
    # Configure Lightning/PyTorch settings when available.
    # These are best-effort settings because DeepForest versions
    # can expose configuration differently.
    # --------------------------------------------------------

    try:
        config = getattr(model, "config", None)

        if isinstance(config, dict):

            # Dataset / prediction workers
            try:
                if "workers" in config:
                    config["workers"] = 0
            except Exception:
                pass

            # Batch size
            try:
                if "batch_size" in config:
                    config["batch_size"] = 1
            except Exception:
                pass

            # Device
            try:
                if "devices" in config:
                    config["devices"] = 1
            except Exception:
                pass

            # Accelerator
            try:
                if "accelerator" in config:
                    config["accelerator"] = "cpu"
            except Exception:
                pass

    except Exception as exc:
        print(f"DeepForest configuration warning: {exc}")

    print("Loaded real pretrained tree-crown detection model (DeepForest)")
    print("=" * 60)

    return model


# ------------------------------------------------------------
# PROGRESS CALLBACK
# ------------------------------------------------------------

def DeepForestProgressCallback(progress_callback=None):
    """
    Creates a DeepForest/PyTorch-Lightning callback lazily.

    This avoids importing pytorch_lightning during API startup.
    """

    try:
        import pytorch_lightning as pl
    except Exception as exc:
        print(f"PyTorch Lightning unavailable: {exc}")
        return None

    class _DeepForestProgressCallback(pl.Callback):

        def __init__(self):
            super().__init__()
            self.progress_callback = progress_callback

        def _update(self, value, message=None):
            if self.progress_callback is None:
                return

            try:
                self.progress_callback(
                    value,
                    message,
                )
            except TypeError:
                try:
                    self.progress_callback(value)
                except Exception:
                    pass
            except Exception:
                pass

        def on_predict_start(self, trainer, pl_module):
            self._update(
                0,
                "DeepForest prediction started."
            )

        def on_predict_batch_start(
            self,
            trainer,
            pl_module,
            batch,
            batch_idx,
            dataloader_idx=0,
        ):
            try:
                total = trainer.num_predict_batches

                if total and total > 0:
                    progress = int(
                        min(
                            100,
                            ((batch_idx + 1) / total) * 100,
                        )
                    )
                    self._update(
                        progress,
                        f"Processing prediction tile {batch_idx + 1}/{total}",
                    )
            except Exception:
                pass

        def on_predict_end(self, trainer, pl_module):
            self._update(
                100,
                "DeepForest prediction completed.",
            )

    return _DeepForestProgressCallback()


# ------------------------------------------------------------
# INPUT / DATASET HELPERS
# ------------------------------------------------------------

def _create_prediction_dataset(
    image_path: str,
    patch_size: int = 400,
    patch_overlap: float = 0.25,
):
    """
    Create a prediction dataset using DeepForest's tile utilities.

    This function is intentionally isolated because DeepForest
    versions can differ in how prediction datasets are exposed.
    """

    main = get_deepforest_main()

    # --------------------------------------------------------
    # Preferred DeepForest API
    # --------------------------------------------------------

    try:
        from deepforest import preprocess

        if hasattr(preprocess, "split_raster"):
            return preprocess.split_raster(
                image_path,
                patch_size=patch_size,
                patch_overlap=patch_overlap,
            )

    except Exception as exc:
        print(f"DeepForest split_raster unavailable: {exc}")

    # --------------------------------------------------------
    # Return None when the installed DeepForest version handles
    # tiling internally.
    # --------------------------------------------------------

    return None


def _get_prediction_batch_count(dataset) -> Optional[int]:
    """
    Best-effort extraction of prediction batch count.
    """

    if dataset is None:
        return None

    try:
        return len(dataset)
    except Exception:
        return None


# ------------------------------------------------------------
# TREE DETECTION
# ------------------------------------------------------------

def detect_trees(
    model,
    image_path: str,
    patch_size: int = 400,
    patch_overlap: float = 0.25,
    iou_threshold: float = 0.15,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Detect individual tree crowns using DeepForest.

    Parameters
    ----------
    model:
        Loaded DeepForest model.

    image_path:
        Input raster/image path.

    patch_size:
        Tile size used by DeepForest.

    patch_overlap:
        Fractional overlap between adjacent tiles.

    iou_threshold:
        IoU threshold used for duplicate prediction filtering.

    progress_callback:
        Optional callback receiving progress and message.

    Returns
    -------
    pandas.DataFrame
        DeepForest detection dataframe.
    """

    if model is None:
        raise ValueError("DeepForest model is not loaded.")

    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    print("=" * 60)
    print("Starting DeepForest tree detection")
    print(f"Image: {image_path}")
    print(f"Patch size: {patch_size}")
    print(f"Patch overlap: {patch_overlap}")
    print(f"IoU threshold: {iou_threshold}")
    print("=" * 60)

    if progress_callback:
        try:
            progress_callback(
                0,
                "Starting DeepForest tree detection.",
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # Configure PyTorch for CPU inference.
    # --------------------------------------------------------

    torch = configure_torch_for_cpu()

    # --------------------------------------------------------
    # Run DeepForest prediction.
    # --------------------------------------------------------

    predictions = None

    try:
        if torch is not None:

            with torch.inference_mode():

                predictions = model.predict_tile(
                    path=image_path,
                    patch_size=patch_size,
                    patch_overlap=patch_overlap,
                    iou_threshold=iou_threshold,
                )

        else:

            predictions = model.predict_tile(
                path=image_path,
                patch_size=patch_size,
                patch_overlap=patch_overlap,
                iou_threshold=iou_threshold,
            )

    except TypeError as exc:

        # Some DeepForest versions may use slightly different
        # argument names/signatures.
        print(
            "Primary DeepForest prediction call failed "
            f"with TypeError: {exc}"
        )

        if progress_callback:
            try:
                progress_callback(
                    0,
                    "Retrying DeepForest prediction with compatibility mode.",
                )
            except Exception:
                pass

        try:

            if torch is not None:

                with torch.inference_mode():

                    predictions = model.predict_tile(
                        path=image_path,
                        patch_size=patch_size,
                        patch_overlap=patch_overlap,
                    )

            else:

                predictions = model.predict_tile(
                    path=image_path,
                    patch_size=patch_size,
                    patch_overlap=patch_overlap,
                )

        except Exception as retry_exc:
            raise RuntimeError(
                "DeepForest prediction failed: "
                f"{retry_exc}"
            ) from retry_exc

    except Exception as exc:

        raise RuntimeError(
            "DeepForest prediction failed: "
            f"{exc}"
        ) from exc

    # --------------------------------------------------------
    # Convert result into DataFrame.
    # --------------------------------------------------------

    if predictions is None:
        print("DeepForest returned no predictions.")
        return pd.DataFrame(
            columns=[
                "xmin",
                "ymin",
                "xmax",
                "ymax",
                "score",
                "label",
            ]
        )

    if isinstance(predictions, pd.DataFrame):
        detections = predictions.copy()

    elif isinstance(predictions, list):
        detections = pd.DataFrame(predictions)

    elif isinstance(predictions, dict):
        detections = pd.DataFrame(predictions)

    else:
        try:
            detections = pd.DataFrame(predictions)
        except Exception as exc:
            raise RuntimeError(
                "Unable to convert DeepForest predictions "
                f"to DataFrame: {exc}"
            ) from exc

    # --------------------------------------------------------
    # Normalize column names.
    # --------------------------------------------------------

    detections.columns = [
        str(column).strip().lower()
        for column in detections.columns
    ]

    # DeepForest normally returns:
    # xmin, ymin, xmax, ymax, label, score

    required_columns = [
        "xmin",
        "ymin",
        "xmax",
        "ymax",
    ]

    for column in required_columns:

        if column not in detections.columns:
            detections[column] = 0.0

    if "score" not in detections.columns:
        detections["score"] = 0.0

    if "label" not in detections.columns:
        detections["label"] = "Tree"

    # --------------------------------------------------------
    # Convert numeric fields.
    # --------------------------------------------------------

    for column in [
        "xmin",
        "ymin",
        "xmax",
        "ymax",
        "score",
    ]:

        detections[column] = pd.to_numeric(
            detections[column],
            errors="coerce",
        )

    detections = detections.dropna(
        subset=[
            "xmin",
            "ymin",
            "xmax",
            "ymax",
        ]
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # Calculate width/height.
    # --------------------------------------------------------

    detections["width"] = (
        detections["xmax"] -
        detections["xmin"]
    )

    detections["height"] = (
        detections["ymax"] -
        detections["ymin"]
    )

    detections["bbox_area_pixels"] = (
        detections["width"].clip(lower=0) *
        detections["height"].clip(lower=0)
    )

    # --------------------------------------------------------
    # Remove obviously invalid bounding boxes.
    # --------------------------------------------------------

    detections = detections[
        (detections["width"] > 0) &
        (detections["height"] > 0)
    ].reset_index(drop=True)

    # --------------------------------------------------------
    # Tree ID.
    # --------------------------------------------------------

    detections["tree_id"] = np.arange(
        1,
        len(detections) + 1,
    )

    if progress_callback:
        try:
            progress_callback(
                100,
                f"Detected {len(detections)} trees.",
            )
        except Exception:
            pass

    print("=" * 60)
    print(
        f"DeepForest detection completed: "
        f"{len(detections)} trees"
    )
    print("=" * 60)

    return detections


# ------------------------------------------------------------
# CROWN METRICS
# ------------------------------------------------------------

def compute_crown_metrics(
    detections: pd.DataFrame,
    pixel_size_m: float = 0.1,
) -> Dict[str, Any]:
    """
    Calculate crown dimensions and area from detected bounding boxes.

    pixel_size_m:
        Ground sampling distance represented by one pixel.

    Returns:
        Dictionary containing crown statistics.
    """

    if detections is None or detections.empty:

        return {
            "tree_count": 0,
            "total_crown_area_m2": 0.0,
            "mean_crown_area_m2": 0.0,
            "median_crown_area_m2": 0.0,
            "min_crown_area_m2": 0.0,
            "max_crown_area_m2": 0.0,
            "mean_crown_diameter_m": 0.0,
            "median_crown_diameter_m": 0.0,
        }

    data = detections.copy()

    # --------------------------------------------------------
    # Width / height in pixels.
    # --------------------------------------------------------

    if "width" not in data.columns:
        data["width"] = (
            data["xmax"] -
            data["xmin"]
        )

    if "height" not in data.columns:
        data["height"] = (
            data["ymax"] -
            data["ymin"]
        )

    # --------------------------------------------------------
    # Bounding-box area in pixels.
    # --------------------------------------------------------

    data["crown_area_pixels"] = (
        data["width"].clip(lower=0) *
        data["height"].clip(lower=0)
    )

    # --------------------------------------------------------
    # Convert pixels to square metres.
    # --------------------------------------------------------

    data["crown_area_m2"] = (
        data["crown_area_pixels"] *
        float(pixel_size_m) *
        float(pixel_size_m)
    )

    # --------------------------------------------------------
    # Equivalent circular diameter.
    #
    # A = pi * (D/2)^2
    # D = 2 * sqrt(A/pi)
    # --------------------------------------------------------

    data["crown_diameter_m"] = (
        2.0 *
        np.sqrt(
            data["crown_area_m2"] /
            np.pi
        )
    )

    # --------------------------------------------------------
    # Statistics.
    # --------------------------------------------------------

    areas = data["crown_area_m2"].to_numpy(
        dtype=float
    )

    diameters = data["crown_diameter_m"].to_numpy(
        dtype=float
    )

    metrics = {
        "tree_count": int(len(data)),

        "total_crown_area_m2": float(
            np.sum(areas)
        ),

        "mean_crown_area_m2": float(
            np.mean(areas)
        ),

        "median_crown_area_m2": float(
            np.median(areas)
        ),

        "min_crown_area_m2": float(
            np.min(areas)
        ),

        "max_crown_area_m2": float(
            np.max(areas)
        ),

        "mean_crown_diameter_m": float(
            np.mean(diameters)
        ),

        "median_crown_diameter_m": float(
            np.median(diameters)
        ),
    }

    return metrics


# ------------------------------------------------------------
# CANOPY COVERAGE
# ------------------------------------------------------------

def calculate_canopy_coverage(
    detections: pd.DataFrame,
    image_width: int,
    image_height: int,
    pixel_size_m: float = 0.1,
) -> Dict[str, Any]:
    """
    Estimate canopy coverage using detected crown bounding boxes.

    The union of bounding boxes is approximated using a raster mask.
    """

    if image_width <= 0 or image_height <= 0:

        return {
            "canopy_coverage_percent": 0.0,
            "canopy_pixels": 0,
            "total_image_pixels": 0,
            "canopy_area_m2": 0.0,
        }

    total_pixels = int(
        image_width * image_height
    )

    if detections is None or detections.empty:

        return {
            "canopy_coverage_percent": 0.0,
            "canopy_pixels": 0,
            "total_image_pixels": total_pixels,
            "canopy_area_m2": 0.0,
        }

    # --------------------------------------------------------
    # Allocate boolean mask.
    # --------------------------------------------------------

    mask = np.zeros(
        (image_height, image_width),
        dtype=bool,
    )

    # --------------------------------------------------------
    # Paint every detection bounding box.
    # --------------------------------------------------------

    for _, row in detections.iterrows():

        try:

            xmin = max(
                0,
                int(np.floor(row["xmin"]))
            )

            ymin = max(
                0,
                int(np.floor(row["ymin"]))
            )

            xmax = min(
                image_width,
                int(np.ceil(row["xmax"]))
            )

            ymax = min(
                image_height,
                int(np.ceil(row["ymax"]))
            )

            if xmax <= xmin or ymax <= ymin:
                continue

            mask[
                ymin:ymax,
                xmin:xmax
            ] = True

        except Exception:
            continue

    canopy_pixels = int(
        np.count_nonzero(mask)
    )

    coverage_percent = (
        canopy_pixels /
        total_pixels *
        100.0
        if total_pixels > 0
        else 0.0
    )

    canopy_area_m2 = (
        canopy_pixels *
        float(pixel_size_m) *
        float(pixel_size_m)
    )

    return {
        "canopy_coverage_percent": float(
            coverage_percent
        ),
        "canopy_pixels": canopy_pixels,
        "total_image_pixels": total_pixels,
        "canopy_area_m2": float(
            canopy_area_m2
        ),
    }


# ------------------------------------------------------------
# IMAGE INFORMATION
# ------------------------------------------------------------

def get_image_dimensions(
    image_path: str,
):
    """
    Read image dimensions without loading unnecessary
    ML components.
    """

    try:

        with Image.open(image_path) as image:

            width, height = image.size

            return int(width), int(height)

    except Exception as exc:

        raise RuntimeError(
            f"Unable to read image dimensions: {exc}"
        ) from exc


# ------------------------------------------------------------
# VISUALIZATION
# ------------------------------------------------------------

def visualize_detections(
    image_path: str,
    detections: pd.DataFrame,
    output_path: Optional[str] = None,
):
    """
    Create a visualization of detected tree bounding boxes.

    Matplotlib is imported only when this function is called.
    """

    plt, patches = get_matplotlib()

    image = Image.open(image_path)

    fig, ax = plt.subplots(
        figsize=(12, 10)
    )

    ax.imshow(image)

    if detections is not None and not detections.empty:

        for _, row in detections.iterrows():

            xmin = float(row["xmin"])
            ymin = float(row["ymin"])
            xmax = float(row["xmax"])
            ymax = float(row["ymax"])

            width = xmax - xmin
            height = ymax - ymin

            rectangle = patches.Rectangle(
                (xmin, ymin),
                width,
                height,
                fill=False,
                linewidth=1.5,
            )

            ax.add_patch(rectangle)

            tree_id = row.get(
                "tree_id",
                "",
            )

            ax.text(
                xmin,
                max(0, ymin - 3),
                str(tree_id),
                fontsize=7,
            )

    ax.set_title(
        f"SylvaSense Tree Detection "
        f"({len(detections) if detections is not None else 0} trees)"
    )

    ax.axis("off")

    plt.tight_layout()

    if output_path:

        fig.savefig(
            output_path,
            dpi=150,
            bbox_inches="tight",
        )

        plt.close(fig)

        return output_path

    return fig


# ------------------------------------------------------------
# SERIALIZATION HELPER
# ------------------------------------------------------------

def detections_to_records(
    detections: pd.DataFrame,
):
    """
    Convert detection DataFrame into JSON-friendly records.
    """

    if detections is None or detections.empty:
        return []

    records = []

    for _, row in detections.iterrows():

        record = {}

        for column in detections.columns:

            value = row[column]

            if isinstance(
                value,
                (
                    np.integer,
                    np.int64,
                    np.int32,
                ),
            ):

                value = int(value)

            elif isinstance(
                value,
                (
                    np.floating,
                    np.float64,
                    np.float32,
                ),
            ):

                value = float(value)

            elif pd.isna(value):

                value = None

            record[str(column)] = value

        records.append(record)

    return records


# ------------------------------------------------------------
# STANDALONE TEST
# ------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("SYLVASENSE TREE DETECTION TEST")
    print("=" * 60)

    try:

        get_data = get_deepforest_data()

        sample_image = get_data(
            "OSBS_029.tif"
        )

        print(
            f"Sample image: {sample_image}"
        )

        model = load_model()

        detections = detect_trees(
            model=model,
            image_path=sample_image,
            patch_size=400,
            patch_overlap=0.25,
            iou_threshold=0.15,
        )

        print()
        print(
            f"Trees detected: {len(detections)}"
        )

        metrics = compute_crown_metrics(
            detections,
            pixel_size_m=0.1,
        )

        print()
        print("CROWN METRICS")
        print("-" * 60)

        for key, value in metrics.items():
            print(f"{key}: {value}")

        width, height = get_image_dimensions(
            sample_image
        )

        canopy = calculate_canopy_coverage(
            detections,
            image_width=width,
            image_height=height,
            pixel_size_m=0.1,
        )

        print()
        print("CANOPY METRICS")
        print("-" * 60)

        for key, value in canopy.items():
            print(f"{key}: {value}")

        print()
        print("=" * 60)
        print("TREE DETECTION TEST COMPLETED")
        print("=" * 60)

    except Exception as exc:

        print()
        print("=" * 60)
        print("TREE DETECTION TEST FAILED")
        print("=" * 60)
        print(f"Error: {exc}")
        print("=" * 60)

        raise