"""
SYLVASENSE - Pixel-level Tree Crown Instance Segmentation
============================================================

This module refines DeepForest bounding-box detections into individual
pixel masks using a classical computer-vision pipeline.

Important memory optimization:
- Each tree keeps only its LOCAL crop mask.
- We do NOT allocate a full-image boolean mask for every tree.
- A single combined full-image canopy mask is maintained internally.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import filters, measure, morphology, segmentation


@dataclass
class CrownMask:
    """
    Memory-efficient representation of one tree crown.

    Instead of storing a full-image mask, we store only the local
    mask and its position in the original image.
    """

    mask: np.ndarray
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def shape(self):
        return self.mask.shape

    def __bool__(self):
        return bool(np.any(self.mask))


def _load_rgb(image_path: str) -> np.ndarray:
    """Load any PIL-readable image as RGB uint8."""
    return np.asarray(
        Image.open(image_path).convert("RGB"),
        dtype=np.uint8,
    )


def _vegetation_mask(rgb: np.ndarray) -> np.ndarray:
    """Create a vegetation mask from Excess Green and Otsu thresholding."""

    arr = rgb.astype(np.float32) / 255.0

    r = arr[..., 0]
    g = arr[..., 1]
    b = arr[..., 2]

    # Excess Green index.
    exg = 2.0 * g - r - b

    try:
        threshold = filters.threshold_otsu(exg)
    except ValueError:
        threshold = float(np.mean(exg))

    mask = exg > threshold

    # Green-dominance fallback.
    green_dominant = (
        (g > r * 0.92)
        & (g > b * 0.92)
        & (g > 0.12)
    )

    mask = mask | green_dominant

    # ---------------------------------------------------------
    # scikit-image >= 0.26 compatible morphology API
    # ---------------------------------------------------------

    min_size = max(
        8,
        int(rgb.shape[0] * rgb.shape[1] * 0.002),
    )

    # max_size is the replacement for deprecated min_size.
    # To preserve the previous behavior as closely as possible,
    # use min_size - 1 because max_size removes objects
    # <= max_size.
    object_threshold = max(1, min_size - 1)

    mask = morphology.remove_small_objects(
        mask,
        max_size=object_threshold,
    )

    hole_threshold = max(
        16,
        min_size * 2,
    )

    # max_size replaces deprecated area_threshold.
    # Old area_threshold removed holes strictly smaller than
    # the threshold. New max_size removes <= max_size.
    hole_threshold = max(1, hole_threshold - 1)

    mask = morphology.remove_small_holes(
        mask,
        max_size=hole_threshold,
    )

    # New names replacing binary_closing/binary_opening.
    mask = morphology.closing(
        mask,
        morphology.disk(2),
    )

    mask = morphology.opening(
        mask,
        morphology.disk(1),
    )

    return mask.astype(bool, copy=False)


def _split_with_watershed(
    mask: np.ndarray,
) -> np.ndarray:
    """Label separated vegetation objects using watershed."""

    if not np.any(mask):
        return np.zeros(
            mask.shape,
            dtype=np.int32,
        )

    distance = ndi.distance_transform_edt(mask)

    try:
        # Local maxima act as seeds.
        peaks = morphology.local_maxima(
            distance
        )

        if np.any(mask):
            percentile_value = np.percentile(
                distance[mask],
                60,
            )

            peaks &= (
                distance
                >= max(
                    1.0,
                    float(percentile_value),
                )
            )

        markers, _ = ndi.label(peaks)

    except Exception:
        markers, _ = ndi.label(
            distance == distance.max()
        )

    if markers.max() == 0:
        markers, _ = ndi.label(mask)

    labels = segmentation.watershed(
        -distance,
        markers,
        mask=mask,
        compactness=0.001,
    )

    return labels.astype(
        np.int32,
        copy=False,
    )


def _select_tree_instance(
    labels: np.ndarray,
    center_y: float,
    center_x: float,
) -> np.ndarray:
    """Select the watershed instance containing the detection center."""

    if (
        labels.size == 0
        or labels.max() == 0
    ):
        return np.zeros(
            labels.shape,
            dtype=bool,
        )

    cy = int(
        np.clip(
            round(center_y),
            0,
            labels.shape[0] - 1,
        )
    )

    cx = int(
        np.clip(
            round(center_x),
            0,
            labels.shape[1] - 1,
        )
    )

    label_id = int(
        labels[cy, cx]
    )

    # ---------------------------------------------------------
    # If center is background, search nearby.
    # ---------------------------------------------------------

    if label_id == 0:

        radius = max(
            2,
            min(labels.shape) // 10,
        )

        y0 = max(
            0,
            cy - radius,
        )

        y1 = min(
            labels.shape[0],
            cy + radius + 1,
        )

        x0 = max(
            0,
            cx - radius,
        )

        x1 = min(
            labels.shape[1],
            cx + radius + 1,
        )

        nearby = labels[
            y0:y1,
            x0:x1
        ]

        ids, counts = np.unique(
            nearby[nearby > 0],
            return_counts=True,
        )

        if len(ids):
            label_id = int(
                ids[np.argmax(counts)]
            )

    # ---------------------------------------------------------
    # Last fallback: largest segment.
    # ---------------------------------------------------------

    if label_id == 0:

        ids, counts = np.unique(
            labels[labels > 0],
            return_counts=True,
        )

        if not len(ids):
            return np.zeros(
                labels.shape,
                dtype=bool,
            )

        label_id = int(
            ids[np.argmax(counts)]
        )

    return labels == label_id


def _mask_polygon(
    mask: np.ndarray,
) -> List[List[float]]:
    """Return the largest exterior contour in local pixel coordinates."""

    contours = measure.find_contours(
        mask.astype(np.uint8),
        0.5,
    )

    if not contours:
        return []

    contour = max(
        contours,
        key=len,
    )

    # find_contours returns row=y, col=x.
    coords = [
        [float(x), float(y)]
        for y, x in contour
    ]

    if (
        coords
        and coords[0] != coords[-1]
    ):
        coords.append(
            coords[0]
        )

    return coords


def _full_mask_from_crown(
    crown: CrownMask,
    image_shape: Tuple[int, int],
) -> np.ndarray:
    """
    Materialize ONE full-image mask when explicitly required.

    This is intentionally NOT used during normal segmentation.
    """

    image_h, image_w = image_shape

    full_mask = np.zeros(
        (image_h, image_w),
        dtype=bool,
    )

    full_mask[
        crown.y0:crown.y1,
        crown.x0:crown.x1
    ] = crown.mask

    return full_mask


def segment_tree_crowns(
    image_path: str,
    predictions: pd.DataFrame,
    pixel_size_m: float = 0.1,
) -> Tuple[
    pd.DataFrame,
    List[CrownMask],
]:
    """
    Segment each DeepForest detection.

    MEMORY OPTIMIZATION:
    Each returned crown contains only its local crop mask.

    Returns:
        results:
            Predictions with segmentation metrics.

        masks:
            List of CrownMask objects containing local masks
            and their original image coordinates.
    """

    if pixel_size_m <= 0:
        raise ValueError(
            "pixel_size_m must be greater than zero."
        )

    rgb = _load_rgb(
        image_path
    )

    image_h, image_w = rgb.shape[:2]

    results = (
        predictions
        .copy()
        .reset_index(drop=True)
    )

    masks: List[CrownMask] = []

    # ---------------------------------------------------------
    # ONE combined canopy mask.
    #
    # Only ONE full-image mask exists, instead of 869
    # full-image masks.
    # ---------------------------------------------------------

    combined_canopy_mask = np.zeros(
        (image_h, image_w),
        dtype=bool,
    )

    areas = []
    diameters = []
    fractions = []
    valid_flags = []

    for _, row in results.iterrows():

        x0 = int(
            np.clip(
                np.floor(row["xmin"]),
                0,
                image_w - 1,
            )
        )

        y0 = int(
            np.clip(
                np.floor(row["ymin"]),
                0,
                image_h - 1,
            )
        )

        x1 = int(
            np.clip(
                np.ceil(row["xmax"]),
                x0 + 1,
                image_w,
            )
        )

        y1 = int(
            np.clip(
                np.ceil(row["ymax"]),
                y0 + 1,
                image_h,
            )
        )

        crop = rgb[
            y0:y1,
            x0:x1
        ]

        # Vegetation segmentation happens only
        # inside this tree's bounding-box crop.
        veg = _vegetation_mask(
            crop
        )

        labels = _split_with_watershed(
            veg
        )

        center_x = (
            float(row["xmax"])
            - float(row["xmin"])
        ) / 2.0

        center_y = (
            float(row["ymax"])
            - float(row["ymin"])
        ) / 2.0

        local_mask = _select_tree_instance(
            labels,
            center_y,
            center_x,
        )

        local_mask = local_mask.astype(
            bool,
            copy=False,
        )

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # DO NOT create:
        #
        # np.zeros((image_h, image_w))
        #
        # for every tree.
        # -----------------------------------------------------

        crown = CrownMask(
            mask=local_mask,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
        )

        masks.append(
            crown
        )

        # Add this tree to the ONE combined canopy mask.
        if np.any(local_mask):

            combined_canopy_mask[
                y0:y1,
                x0:x1
            ] |= local_mask

        area_px = int(
            np.count_nonzero(
                local_mask
            )
        )

        area_m2 = (
            area_px
            * (pixel_size_m ** 2)
        )

        equivalent_diameter_m = (
            2.0
            * np.sqrt(
                area_m2 / np.pi
            )
            if area_m2 > 0
            else 0.0
        )

        box_area = max(
            1.0,
            float(
                (x1 - x0)
                * (y1 - y0)
            ),
        )

        fraction = (
            area_px
            / box_area
        )

        areas.append(
            area_m2
        )

        diameters.append(
            equivalent_diameter_m
        )

        fractions.append(
            fraction
        )

        valid_flags.append(
            bool(area_px > 0)
        )

    results[
        "segmentation_area_m2"
    ] = areas

    results[
        "segmentation_crown_diameter_m"
    ] = diameters

    results[
        "segmentation_mask_fraction"
    ] = fractions

    results[
        "segmentation_valid"
    ] = valid_flags

    # ---------------------------------------------------------
    # Store canopy information on the dataframe.
    #
    # api_server.py can use these values directly.
    # ---------------------------------------------------------

    canopy_pixels = int(
        np.count_nonzero(
            combined_canopy_mask
        )
    )

    total_image_pixels = int(
        image_h * image_w
    )

    canopy_coverage_percent = (
        (
            canopy_pixels
            / total_image_pixels
        )
        * 100.0
        if total_image_pixels > 0
        else 0.0
    )

    total_crown_area_m2 = (
        canopy_pixels
        * (pixel_size_m ** 2)
    )

    results[
        "canopy_coverage_percent"
    ] = canopy_coverage_percent

    results[
        "total_crown_area_m2"
    ] = total_crown_area_m2

    results[
        "canopy_pixels"
    ] = canopy_pixels

    results[
        "total_image_pixels"
    ] = total_image_pixels

    return results, masks


def overlay_segmentation(
    image_path: str,
    predictions: pd.DataFrame,
    masks: List[CrownMask],
    save_path: str = "sylvasense_crown_segmentation.png",
) -> str:
    """Draw crown masks and boundaries on the RGB image."""

    base = Image.open(
        image_path
    ).convert("RGBA")

    overlay = Image.new(
        "RGBA",
        base.size,
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(
        overlay
    )

    for idx, crown in enumerate(
        masks
    ):

        mask = crown.mask

        if not np.any(mask):
            continue

        # Unique deterministic visual color.
        r = int(
            (37 * idx + 80) % 200 + 30
        )

        g = int(
            (97 * idx + 60) % 200 + 30
        )

        b = int(
            (157 * idx + 40) % 200 + 30
        )

        # -----------------------------------------------------
        # IMPORTANT:
        # Create RGBA only for the LOCAL crop.
        # -----------------------------------------------------

        rgba = np.zeros(
            (
                mask.shape[0],
                mask.shape[1],
                4,
            ),
            dtype=np.uint8,
        )

        rgba[mask] = [
            r,
            g,
            b,
            75,
        ]

        layer = Image.fromarray(
            rgba,
            mode="RGBA",
        )

        # Put local overlay at original position.
        overlay.alpha_composite(
            layer,
            dest=(
                crown.x0,
                crown.y0,
            ),
        )

        polygon = _mask_polygon(
            mask
        )

        if len(polygon) >= 3:

            global_polygon = [
                (
                    float(x) + crown.x0,
                    float(y) + crown.y0,
                )
                for x, y in polygon
            ]

            draw.line(
                global_polygon,
                fill=(
                    r,
                    g,
                    b,
                    255,
                ),
                width=2,
                joint="curve",
            )

        draw.text(
            (
                crown.x0,
                crown.y0,
            ),
            str(idx + 1),
            fill=(
                255,
                255,
                255,
                255,
            ),
        )

    result = Image.alpha_composite(
        base,
        overlay,
    ).convert("RGB")

    result.save(
        save_path,
        quality=95,
    )

    return save_path


def segmentation_to_geojson(
    predictions: pd.DataFrame,
    masks: List[CrownMask],
) -> Dict:
    """
    Create pixel-coordinate GeoJSON FeatureCollection.

    Coordinates are image pixels, NOT longitude/latitude.
    """

    features = []

    for idx, (
        crown,
        (_, row),
    ) in enumerate(
        zip(
            masks,
            predictions.iterrows(),
        )
    ):

        polygon = _mask_polygon(
            crown.mask
        )

        if len(polygon) < 4:
            continue

        # Convert local crop coordinates
        # back to full-image coordinates.
        global_polygon = [
            [
                float(x) + crown.x0,
                float(y) + crown.y0,
            ]
            for x, y in polygon
        ]

        properties = {
            "tree_id": int(
                idx + 1
            ),
            "detection_score": float(
                row.get(
                    "score",
                    0.0,
                )
            ),
            "crown_area_m2": float(
                row.get(
                    "segmentation_area_m2",
                    0.0,
                )
            ),
            "crown_diameter_m": float(
                row.get(
                    "segmentation_crown_diameter_m",
                    0.0,
                )
            ),
        }

        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        global_polygon
                    ],
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "name": (
            "sylvasense_tree_"
            "crown_masks_pixel_coordinates"
        ),
        "features": features,
    }


def save_segmentation_geojson(
    predictions: pd.DataFrame,
    masks: List[CrownMask],
    save_path: str = (
        "sylvasense_crown_masks.geojson"
    ),
) -> str:
    """Save pixel-coordinate crown polygons as GeoJSON."""

    data = segmentation_to_geojson(
        predictions,
        masks,
    )

    with open(
        save_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
        )

    return save_path