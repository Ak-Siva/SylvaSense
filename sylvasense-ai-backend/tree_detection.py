"""
SYLVASENSE - Real Tree Crown Detection
======================================

Uses DeepForest for real individual tree crown detection.

This version also exposes REAL DeepForest prediction progress.

IMPORTANT MEMORY OPTIMIZATION
-----------------------------
Heavy dependencies such as:

    DeepForest
    PyTorch Lightning
    Matplotlib

are imported lazily.

This allows the FastAPI service to start with much lower memory
usage on memory-limited hosting such as Render.

The actual DeepForest model is still loaded only when required.
"""

import pandas as pd
import numpy as np

from PIL import Image


# ============================================================
# LAZY DEEPFOREST IMPORT
# ============================================================

def get_deepforest_main():
    """
    Import DeepForest only when the model is actually needed.
    """

    from deepforest import main

    return main


def get_deepforest_data():
    """
    Import DeepForest sample-data helper only when needed.
    """

    from deepforest import get_data

    return get_data


# ============================================================
# LAZY MATPLOTLIB IMPORT
# ============================================================

def get_matplotlib():
    """
    Import Matplotlib only when visualization is requested.

    Matplotlib is intentionally NOT imported during API startup.
    """

    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    return plt, patches


# ============================================================
# MODEL LOADING
# ============================================================

def load_model():
    """
    Load the real pretrained DeepForest tree-crown model.
    """

    print(
        "Loading DeepForest model..."
    )

    main = get_deepforest_main()

    model = main.deepforest()

    model.load_model(
        model_name="weecology/deepforest-tree",
        revision="main",
    )

    print(
        "Loaded real pretrained tree-crown "
        "detection model (DeepForest)"
    )

    return model


# ============================================================
# DEEPFOREST REAL PROGRESS CALLBACK
# ============================================================

def DeepForestProgressCallback(
    total_batches,
    progress_callback=None,
):
    """
    Create the real DeepForest prediction callback.

    PyTorch Lightning is imported ONLY when this function is
    called during an actual prediction.

    This preserves the existing API:

        DeepForestProgressCallback(
            total_batches=130,
            progress_callback=callback,
        )

    Returns
    -------
    pytorch_lightning.Callback
        A real Lightning callback instance.
    """

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT import PyTorch Lightning at module startup.
    # --------------------------------------------------------

    import pytorch_lightning as pl

    # --------------------------------------------------------
    # Real Lightning callback class
    # --------------------------------------------------------

    class _DeepForestProgressCallback(
        pl.Callback
    ):
        """
        Tracks actual DeepForest prediction batches.

        Lightning calls:

            on_predict_start()
            on_predict_batch_end()
            on_predict_end()

        during DeepForest prediction.
        """

        def __init__(
            self,
            total_batches,
            progress_callback=None,
        ):
            super().__init__()

            self.total_batches = max(
                int(total_batches),
                1,
            )

            self.progress_callback = (
                progress_callback
            )

            self.completed_batches = 0

        def on_predict_start(
            self,
            trainer,
            pl_module,
        ):
            """
            Called when DeepForest prediction starts.
            """

            self.completed_batches = 0

            print(
                "DeepForest prediction started: "
                f"0/{self.total_batches}"
            )

            if self.progress_callback:

                self.progress_callback(
                    0,
                    self.total_batches,
                )

        def on_predict_batch_end(
            self,
            trainer,
            pl_module,
            outputs,
            batch,
            batch_idx,
            dataloader_idx=0,
        ):
            """
            Called after every completed DeepForest
            prediction batch.
            """

            self.completed_batches += 1

            current = min(
                self.completed_batches,
                self.total_batches,
            )

            percentage = (
                current
                / self.total_batches
                * 100.0
            )

            percentage = min(
                max(
                    percentage,
                    0.0,
                ),
                100.0,
            )

            print(
                "DeepForest: Predicting "
                f"{current}/"
                f"{self.total_batches} "
                f"({percentage:.1f}%)"
            )

            if self.progress_callback:

                self.progress_callback(
                    current,
                    self.total_batches,
                )

        def on_predict_end(
            self,
            trainer,
            pl_module,
        ):
            """
            Ensure the final state reaches total / total.
            """

            if self.progress_callback:

                self.progress_callback(
                    self.total_batches,
                    self.total_batches,
                )

            print(
                "DeepForest prediction completed: "
                f"{self.total_batches}/"
                f"{self.total_batches} "
                "(100.0%)"
            )

    # --------------------------------------------------------
    # Return actual Lightning callback instance
    # --------------------------------------------------------

    return _DeepForestProgressCallback(
        total_batches=total_batches,
        progress_callback=progress_callback,
    )


# ============================================================
# CREATE SAME DATASET USED BY DEEPFOREST
# ============================================================

def _create_prediction_dataset(
    model,
    image_path,
    patch_size,
    patch_overlap,
):
    """
    Create the same SingleImage dataset used internally
    by DeepForest.predict_tile().

    This lets us determine the actual number of prediction
    batches before prediction starts.
    """

    from deepforest.datasets import prediction

    ds = prediction.SingleImage(
        path=image_path,
        image=None,
        patch_overlap=patch_overlap,
        patch_size=patch_size,
    )

    return ds


# ============================================================
# GET TOTAL NUMBER OF PREDICTION BATCHES
# ============================================================

def _get_prediction_batch_count(
    model,
    image_path,
    patch_size,
    patch_overlap,
):
    """
    Determine the number of prediction batches.

    For example:

        130

    means DeepForest will process:

        1/130
        2/130
        ...
        130/130
    """

    try:

        dataset = _create_prediction_dataset(
            model=model,
            image_path=image_path,
            patch_size=patch_size,
            patch_overlap=patch_overlap,
        )

        dataloader = model.predict_dataloader(
            dataset
        )

        total_batches = len(
            dataloader
        )

        return int(
            total_batches
        )

    except Exception as exc:

        print(
            "WARNING: Could not determine "
            "DeepForest prediction batch count:"
        )

        print(exc)

        return 0


# ============================================================
# TREE DETECTION
# ============================================================

def detect_trees(
    model,
    image_path,
    patch_size=400,
    patch_overlap=0.25,
    iou_threshold=0.15,
    progress_callback=None,
):
    """
    Detect individual tree crowns using DeepForest.

    Parameters
    ----------
    model:
        Loaded DeepForest model.

    image_path:
        Input image path.

    patch_size:
        Size of each DeepForest prediction tile.

    patch_overlap:
        Overlap between prediction tiles.

    iou_threshold:
        IoU threshold for removing duplicate detections
        between overlapping tiles.

    progress_callback:
        Optional function:

            progress_callback(current, total)

        Example:

            progress_callback(68, 130)

    Returns
    -------
    pandas.DataFrame
        DeepForest tree predictions.
    """

    if model is None:

        raise ValueError(
            "DeepForest model is not loaded."
        )

    # ========================================================
    # NORMAL MODE
    # ========================================================

    if progress_callback is None:

        predictions = model.predict_tile(
            path=image_path,
            patch_size=patch_size,
            patch_overlap=patch_overlap,
            iou_threshold=iou_threshold,
        )

        if predictions is None:

            predictions = pd.DataFrame()

        print(
            f"Detected {len(predictions)} "
            f"real tree crowns in {image_path}"
        )

        return predictions

    # ========================================================
    # PROGRESS MODE
    # ========================================================

    print(
        "\nStarting DeepForest prediction "
        "with real progress tracking..."
    )

    # --------------------------------------------------------
    # Determine actual number of prediction batches.
    # --------------------------------------------------------

    total_batches = (
        _get_prediction_batch_count(
            model=model,
            image_path=image_path,
            patch_size=patch_size,
            patch_overlap=patch_overlap,
        )
    )

    if total_batches <= 0:

        print(
            "WARNING: Could not determine "
            "DeepForest batch count."
        )

        print(
            "Falling back to normal DeepForest "
            "prediction."
        )

        predictions = model.predict_tile(
            path=image_path,
            patch_size=patch_size,
            patch_overlap=patch_overlap,
            iou_threshold=iou_threshold,
        )

        if predictions is None:

            predictions = pd.DataFrame()

        return predictions

    print(
        f"DeepForest prediction batches: "
        f"{total_batches}"
    )

    # ========================================================
    # CREATE REAL LIGHTNING CALLBACK
    # ========================================================

    progress_callback_object = (
        DeepForestProgressCallback(
            total_batches=total_batches,
            progress_callback=progress_callback,
        )
    )

    # ========================================================
    # SAVE EXISTING CALLBACKS
    # ========================================================

    trainer = model.trainer

    original_callbacks = list(
        trainer.callbacks
    )

    # ========================================================
    # ADD OUR CALLBACK
    # ========================================================

    trainer.callbacks.append(
        progress_callback_object
    )

    try:

        # ====================================================
        # IMPORTANT:
        #
        # We still use DeepForest's own predict_tile().
        #
        # The callback receives the REAL prediction batch
        # completion events from trainer.predict().
        # ====================================================

        predictions = model.predict_tile(
            path=image_path,
            patch_size=patch_size,
            patch_overlap=patch_overlap,
            iou_threshold=iou_threshold,
        )

    finally:

        # ====================================================
        # RESTORE ORIGINAL CALLBACKS
        # ====================================================

        trainer.callbacks.clear()

        trainer.callbacks.extend(
            original_callbacks
        )

    # ========================================================
    # EMPTY RESULT SAFETY
    # ========================================================

    if predictions is None:

        predictions = pd.DataFrame()

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print(
        f"Detected {len(predictions)} "
        f"real tree crowns in {image_path}"
    )

    return predictions


# ============================================================
# CROWN METRICS
# ============================================================

def compute_crown_metrics(
    predictions,
    pixel_size_m=0.1,
):
    """
    Calculate:

    - crown width
    - crown height
    - crown diameter
    - crown area
    """

    if predictions is None:

        return pd.DataFrame()

    predictions = predictions.copy()

    # --------------------------------------------------------
    # Empty predictions
    # --------------------------------------------------------

    if predictions.empty:

        predictions["width_px"] = pd.Series(
            dtype=float
        )

        predictions["height_px"] = pd.Series(
            dtype=float
        )

        predictions["crown_diameter_m"] = pd.Series(
            dtype=float
        )

        predictions["crown_area_m2"] = pd.Series(
            dtype=float
        )

        return predictions

    # --------------------------------------------------------
    # Pixel dimensions
    # --------------------------------------------------------

    predictions["width_px"] = (
        predictions["xmax"]
        - predictions["xmin"]
    )

    predictions["height_px"] = (
        predictions["ymax"]
        - predictions["ymin"]
    )

    # --------------------------------------------------------
    # Crown diameter
    # --------------------------------------------------------

    predictions["crown_diameter_m"] = (
        (
            predictions["width_px"]
            + predictions["height_px"]
        )
        / 2
    ) * pixel_size_m

    # --------------------------------------------------------
    # Crown area
    # --------------------------------------------------------

    predictions["crown_area_m2"] = (
        np.pi
        * (
            predictions["crown_diameter_m"]
            / 2
        )
        ** 2
    )

    return predictions


# ============================================================
# VISUALIZE DETECTIONS
# ============================================================

def visualize_detections(
    image_path,
    predictions,
    save_path="detection_result.png",
):
    """
    Draw DeepForest bounding boxes over the input image.

    Matplotlib is imported ONLY when this visualization
    function is actually called.
    """

    # --------------------------------------------------------
    # Lazy Matplotlib import
    # --------------------------------------------------------

    plt, patches = get_matplotlib()

    img = Image.open(
        image_path
    )

    fig, ax = plt.subplots(
        1,
        figsize=(10, 10),
    )

    ax.imshow(img)

    if predictions is not None:

        for _, row in predictions.iterrows():

            rect = patches.Rectangle(
                (
                    row["xmin"],
                    row["ymin"],
                ),
                row["xmax"]
                - row["xmin"],
                row["ymax"]
                - row["ymin"],
                linewidth=1.5,
                edgecolor="lime",
                facecolor="none",
            )

            ax.add_patch(rect)

    tree_count = (
        0
        if predictions is None
        else len(predictions)
    )

    ax.set_title(
        "DeepForest: "
        f"{tree_count} tree crowns detected"
    )

    ax.axis("off")

    plt.savefig(
        save_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)

    print(
        f"Saved visualization to {save_path}"
    )

    return save_path


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # DeepForest sample data is also lazy-loaded.
    # --------------------------------------------------------

    get_data = get_deepforest_data()

    sample_image = get_data(
        "OSBS_029.tif"
    )

    model = load_model()

    # --------------------------------------------------------
    # Test progress callback
    # --------------------------------------------------------

    def test_progress(
        current,
        total,
    ):

        if total <= 0:

            return

        percentage = (
            current
            / total
        ) * 100

        print(
            "SYLVASENSE PROGRESS: "
            f"{current}/{total} "
            f"({percentage:.1f}%)"
        )

    # --------------------------------------------------------
    # Run detection
    # --------------------------------------------------------

    predictions = detect_trees(
        model,
        sample_image,
        patch_size=400,
        patch_overlap=0.25,
        iou_threshold=0.15,
        progress_callback=test_progress,
    )

    # --------------------------------------------------------
    # Crown metrics
    # --------------------------------------------------------

    predictions = compute_crown_metrics(
        predictions,
        pixel_size_m=0.1,
    )

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    if not predictions.empty:

        print(
            predictions[
                [
                    "xmin",
                    "ymin",
                    "xmax",
                    "ymax",
                    "score",
                    "crown_diameter_m",
                ]
            ].head(10)
        )

        print(
            f"\nTotal trees detected: "
            f"{len(predictions)}"
        )

        print(
            "Mean crown diameter: "
            f"{predictions['crown_diameter_m'].mean():.2f} m"
        )

    else:

        print(
            "\nNo trees detected."
        )

    # --------------------------------------------------------
    # Visualization
    # --------------------------------------------------------

    visualize_detections(
        sample_image,
        predictions,
        "osbs_detection_result.png",
    )