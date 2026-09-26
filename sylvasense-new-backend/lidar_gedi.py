# ============================================================
# SYLVASENSE - GEDI L4A ABOVEGROUND BIOMASS DENSITY
# ============================================================

import ee


# ============================================================
# CONFIGURATION
# ============================================================

GEDI_COLLECTION = (
    "LARSE/GEDI/GEDI04_A_002_MONTHLY"
)

GEDI_START = "2019-03-25"

# Current Earth Engine catalog availability extends into 2025.
GEDI_END_EXCLUSIVE = "2025-08-01"

GEDI_LAT_MIN = -51.6
GEDI_LAT_MAX = 51.6


# ============================================================
# VALIDATION
# ============================================================

def validate_gedi_window(
    start_date,
    end_date,
):
    start_date = str(start_date)
    end_date = str(end_date)

    if start_date < GEDI_START:
        raise ValueError(
            f"GEDI analysis cannot start before "
            f"{GEDI_START}."
        )

    if start_date >= end_date:
        raise ValueError(
            "GEDI start date must be before "
            "GEDI end date."
        )


def validate_gedi_region(
    region,
):
    coordinates = (
        region
        .bounds()
        .coordinates()
        .getInfo()
    )

    if not coordinates:
        raise ValueError(
            "Unable to determine GEDI analysis region."
        )

    outer_ring = coordinates[0]

    if not outer_ring:
        raise ValueError(
            "GEDI analysis region is empty."
        )

    latitudes = [
        point[1]
        for point in outer_ring
    ]

    if not latitudes:
        raise ValueError(
            "GEDI region contains no latitude coordinates."
        )

    if (
        max(latitudes) < GEDI_LAT_MIN
        or min(latitudes) > GEDI_LAT_MAX
    ):
        raise ValueError(
            "The selected region is outside "
            "GEDI coverage."
        )


# ============================================================
# DATE HELPER
# ============================================================

def make_exclusive_end_date(
    end_date,
):
    """
    Convert an inclusive-looking YYYY-MM-DD date into
    an exclusive Earth Engine end date.

    Example:
        2024-11-30
        ->
        2024-12-01
    """

    return (
        ee.Date(
            str(end_date)
        )
        .advance(
            1,
            "day",
        )
    )


# ============================================================
# QUALITY FILTER
# ============================================================

def apply_gedi_quality_mask(
    image,
):
    """
    Official GEDI L4A quality filtering:

        l4_quality_flag == 1
        degrade_flag == 0

    The Earth Engine catalog identifies:
      agbd -> aboveground biomass density
      l4_quality_flag -> useful biomass predictions
      degrade_flag -> degraded positioning/pointing flag
    """

    quality = (
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
            quality
        )
        .updateMask(
            not_degraded
        )
    )


# ============================================================
# GET GEDI L4A COLLECTION
# ============================================================

def get_gedi_collection(
    region,
    start_date=GEDI_START,
    end_date="2025-07-31",
):
    validate_gedi_window(
        start_date,
        end_date,
    )

    validate_gedi_region(
        region
    )

    exclusive_end = (
        make_exclusive_end_date(
            end_date
        )
    )

    collection = (
        ee.ImageCollection(
            GEDI_COLLECTION
        )
        .filterBounds(
            region
        )
        .filterDate(
            str(start_date),
            exclusive_end,
        )
        .map(
            apply_gedi_quality_mask
        )
        .select(
            "agbd"
        )
    )

    return collection


# ============================================================
# GEDI AGBD STATISTICS
# ============================================================

def gedi_agbd_statistics(
    region,
    start_date=GEDI_START,
    end_date="2025-07-31",
):
    """
    Return GEDI L4A AGBD statistics for a region.

    Units:
        Mg/ha

    Returns an unavailable result rather than raising when
    there are no valid GEDI pixels.
    """

    try:

        collection = get_gedi_collection(
            region=region,
            start_date=start_date,
            end_date=end_date,
        )

        image_count = int(
            collection
            .size()
            .getInfo()
            or 0
        )

        if image_count == 0:

            return {
                "available": False,
                "collection_images": 0,
                "valid_pixels": 0,
                "agbd_mean_mg_ha": None,
                "agbd_median_mg_ha": None,
                "agbd_min_mg_ha": None,
                "agbd_max_mg_ha": None,
                "reason": (
                    "No GEDI L4A monthly scenes "
                    "intersected the requested region "
                    "during this period."
                ),
            }

        # Median is preferable here to avoid one monthly
        # observation dominating the regional result.
        image = (
            collection
            .median()
            .clip(
                region
            )
        )

        count_result = (
            image
            .reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=region,
                scale=25,
                maxPixels=1_000_000_000,
                bestEffort=True,
            )
            .getInfo()
            or {}
        )

        valid_pixels = (
            count_result.get(
                "agbd"
            )
            or 0
        )

        try:
            valid_pixels = int(
                valid_pixels
            )
        except Exception:
            valid_pixels = 0

        if valid_pixels <= 0:

            return {
                "available": False,
                "collection_images": image_count,
                "valid_pixels": 0,
                "agbd_mean_mg_ha": None,
                "agbd_median_mg_ha": None,
                "agbd_min_mg_ha": None,
                "agbd_max_mg_ha": None,
                "reason": (
                    "GEDI scenes exist, but there are "
                    "no valid quality-filtered GEDI "
                    "AGBD pixels in this region."
                ),
            }

        stats = (
            image
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
                maxPixels=1_000_000_000,
                bestEffort=True,
            )
            .getInfo()
            or {}
        )

        def to_float(
            value,
        ):
            try:
                if value is None:
                    return None

                return float(
                    value
                )

            except Exception:
                return None

        mean_value = to_float(
            stats.get(
                "agbd_mean"
            )
        )

        median_value = to_float(
            stats.get(
                "agbd_median"
            )
        )

        min_value = to_float(
            stats.get(
                "agbd_min"
            )
        )

        max_value = to_float(
            stats.get(
                "agbd_max"
            )
        )

        if mean_value is None:

            return {
                "available": False,
                "collection_images": image_count,
                "valid_pixels": valid_pixels,
                "agbd_mean_mg_ha": None,
                "agbd_median_mg_ha": median_value,
                "agbd_min_mg_ha": min_value,
                "agbd_max_mg_ha": max_value,
                "reason": (
                    "Earth Engine returned valid GEDI "
                    "pixels but no numeric AGBD mean."
                ),
            }

        return {
            "available": True,

            "collection_images":
                image_count,

            "valid_pixels":
                valid_pixels,

            "agbd_mean_mg_ha":
                mean_value,

            "agbd_median_mg_ha":
                median_value,

            "agbd_min_mg_ha":
                min_value,

            "agbd_max_mg_ha":
                max_value,

            "reason":
                (
                    "Valid GEDI L4A AGBD observations "
                    "were found."
                ),
        }

    except Exception as exc:

        return {
            "available": False,
            "collection_images": 0,
            "valid_pixels": 0,
            "agbd_mean_mg_ha": None,
            "agbd_median_mg_ha": None,
            "agbd_min_mg_ha": None,
            "agbd_max_mg_ha": None,
            "reason": (
                f"GEDI query failed: "
                f"{type(exc).__name__}: {exc}"
            ),
        }


# ============================================================
# GET GEDI AGBD IMAGE
# ============================================================

def get_gedi_agbd_image(
    region,
    start_date=GEDI_START,
    end_date="2025-07-31",
):
    """
    Return:
        image
        statistics
    """

    statistics = (
        gedi_agbd_statistics(
            region=region,
            start_date=start_date,
            end_date=end_date,
        )
    )

    if not statistics.get(
        "available"
    ):
        return (
            None,
            statistics,
        )

    collection = get_gedi_collection(
        region=region,
        start_date=start_date,
        end_date=end_date,
    )

    image = (
        collection
        .median()
        .clip(
            region
        )
    )

    return (
        image,
        statistics,
    )


# ============================================================
# GEDI MAP LAYER
# ============================================================

def get_gedi_agbd_tile(
    region,
    start_date=GEDI_START,
    end_date="2025-07-31",
):
    """
    Return a tile URL when GEDI is available.

    Otherwise return tile_url=None.
    """

    image, statistics = (
        get_gedi_agbd_image(
            region=region,
            start_date=start_date,
            end_date=end_date,
        )
    )

    if image is None:

        return {
            "available": False,
            "tile_url": None,
            "statistics": statistics,
        }

    visualization = {
        "min": 0,
        "max": 400,
        "palette": [
            "440154",
            "31688e",
            "35b779",
            "fde725",
        ],
    }

    map_id = image.getMapId(
        visualization
    )

    tile_url = (
        map_id[
            "tile_fetcher"
        ].url_format
    )

    return {
        "available": True,
        "tile_url": tile_url,
        "statistics": statistics,
        "visualization": visualization,
    }


# ============================================================
# BACKWARD-COMPATIBILITY ALIAS
# ============================================================

def get_gedi_rh98(
    region,
    start_date=GEDI_START,
    end_date="2025-07-31",
):
    """
    Kept only so old imports do not immediately crash.

    IMPORTANT:
    This now returns GEDI L4A AGBD, not RH98.
    """

    image, statistics = (
        get_gedi_agbd_image(
            region=region,
            start_date=start_date,
            end_date=end_date,
        )
    )

    if image is None:

        raise ValueError(
            statistics.get(
                "reason",
                "No valid GEDI AGBD data found.",
            )
        )

    return (
        image,
        statistics.get(
            "collection_images",
            0,
        ),
    )


def gedi_statistics(
    region,
    start_date=GEDI_START,
    end_date="2025-07-31",
):
    """
    Backward-compatible function.
    """

    return gedi_agbd_statistics(
        region=region,
        start_date=start_date,
        end_date=end_date,
    )