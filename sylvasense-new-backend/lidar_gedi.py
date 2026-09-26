import ee
import folium


# ============================================================
# GEDI CONFIGURATION
# ============================================================

GEDI_COLLECTION = "LARSE/GEDI/GEDI02_A_002_MONTHLY"

GEDI_START = "2019-03-25"
GEDI_END_EXCLUSIVE = "2024-12-01"

GEDI_LAT_MIN = -51.6
GEDI_LAT_MAX = 51.6


# ============================================================
# DATE VALIDATION
# ============================================================

def validate_gedi_window(start_date, end_date):
    """
    Validate that the requested GEDI period is inside
    the available GEDI mission/data window.
    """

    start_date = str(start_date)
    end_date = str(end_date)

    if start_date < GEDI_START:
        raise ValueError(
            f"GEDI analysis cannot start before {GEDI_START}."
        )

    if end_date >= GEDI_END_EXCLUSIVE:
        raise ValueError(
            "GEDI analysis end date must be before "
            "2024-12-01 (project window ends in November 2024)."
        )

    if start_date >= end_date:
        raise ValueError(
            "GEDI start date must be earlier than the end date."
        )


# ============================================================
# REGION VALIDATION
# ============================================================

def validate_gedi_region(region):
    """
    Check whether the selected region falls within
    the GEDI latitude coverage.
    """

    coords = (
        region
        .bounds()
        .coordinates()
        .getInfo()[0]
    )

    if not coords:
        raise ValueError(
            "Unable to determine the selected GEDI region."
        )

    lats = [
        point[1]
        for point in coords
    ]

    if (
        max(lats) < GEDI_LAT_MIN
        or min(lats) > GEDI_LAT_MAX
    ):
        raise ValueError(
            "The selected region is outside GEDI coverage."
        )


# ============================================================
# BUILD QUALITY-FILTERED GEDI COLLECTION
# ============================================================

def _get_quality_filtered_collection(
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
):
    """
    Build the quality-filtered GEDI RH98 collection.

    Important:
    filterDate uses the user's actual end date rather than
    always forcing 2024-12-01.
    """

    validate_gedi_window(
        start_date,
        end_date,
    )

    validate_gedi_region(region)

    # Earth Engine filterDate has an exclusive end date.
    # Therefore convert the requested end date to the
    # following day when necessary.
    end_date_exclusive = ee.Date(
        str(end_date)
    ).advance(
        1,
        "day",
    )

    collection = (
        ee.ImageCollection(
            GEDI_COLLECTION
        )
        .filterBounds(region)
        .filterDate(
            str(start_date),
            end_date_exclusive,
        )
        .map(
            lambda image:
                image
                .updateMask(
                    image
                    .select("quality_flag")
                    .eq(1)
                )
                .updateMask(
                    image
                    .select("degrade_flag")
                    .eq(0)
                )
        )
        .select("rh98")
    )

    return collection


# ============================================================
# GET GEDI RH98
# ============================================================

def get_gedi_rh98(
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
):
    """
    Return a quality-filtered median GEDI RH98 image.

    This function checks BOTH:

    1. Whether GEDI images exist.
    2. Whether valid GEDI pixels actually exist inside
       the selected region.

    This prevents a false 'GEDI available' result when all
    pixels are masked by quality/degrade flags.
    """

    collection = _get_quality_filtered_collection(
        region,
        start_date,
        end_date,
    )

    # --------------------------------------------------------
    # Check number of GEDI images
    # --------------------------------------------------------

    image_count = (
        collection
        .size()
        .getInfo()
    )

    if not image_count:
        raise ValueError(
            "No GEDI images were found for this region "
            "and date range."
        )

    # --------------------------------------------------------
    # Create median RH98 image
    # --------------------------------------------------------

    image = (
        collection
        .median()
        .clip(region)
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Check actual valid pixels.
    #
    # collection.size() can be > 0 while the selected
    # location has zero valid GEDI observations.
    # --------------------------------------------------------

    valid_pixel_result = (
        image
        .reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=region,
            scale=25,
            maxPixels=1e9,
            bestEffort=True,
        )
        .getInfo()
    )

    valid_pixel_count = (
        valid_pixel_result.get("rh98", 0)
        if valid_pixel_result
        else 0
    )

    if not valid_pixel_count:
        raise ValueError(
            "GEDI images were found, but there are no valid "
            "quality-filtered GEDI RH98 pixels at the selected "
            "location."
        )

    return image, image_count


# ============================================================
# GEDI STATISTICS
# ============================================================

def gedi_statistics(
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
):
    """
    Calculate GEDI RH98 statistics for the selected region.
    """

    image, image_count = get_gedi_rh98(
        region,
        start_date,
        end_date,
    )

    stats = (
        image
        .reduceRegion(
            reducer=(
                ee.Reducer.mean()
                .combine(
                    ee.Reducer.minMax(),
                    sharedInputs=True,
                )
                .combine(
                    ee.Reducer.count(),
                    sharedInputs=True,
                )
            ),
            geometry=region,
            scale=25,
            maxPixels=1e9,
            bestEffort=True,
        )
        .getInfo()
    )

    if not stats:
        raise ValueError(
            "GEDI statistics could not be calculated "
            "for the selected region."
        )

    valid_pixels = stats.get(
        "rh98_count"
    )

    if not valid_pixels:
        raise ValueError(
            "No valid GEDI RH98 pixels were available "
            "for the selected location."
        )

    return {
        "available": True,
        "collection_images": image_count,
        "rh98_mean_m": stats.get(
            "rh98_mean"
        ),
        "rh98_min_m": stats.get(
            "rh98_min"
        ),
        "rh98_max_m": stats.get(
            "rh98_max"
        ),
        "rh98_valid_pixels": valid_pixels,
    }


# ============================================================
# ADD GEDI MAP LAYER
# ============================================================

def add_gedi_layer(
    map_object,
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
    show=False,
):
    """
    Add GEDI RH98 visualization to a Folium map.
    """

    image, image_count = get_gedi_rh98(
        region,
        start_date,
        end_date,
    )

    map_id = image.getMapId(
        {
            "min": 0,
            "max": 40,
            "palette": [
                "440154",
                "31688e",
                "35b779",
                "fde725",
            ],
        }
    )

    folium.raster_layers.TileLayer(
        tiles=(
            map_id[
                "tile_fetcher"
            ].url_format
        ),
        attr=(
            "NASA GEDI / "
            "Google Earth Engine"
        ),
        name="GEDI RH98 (m)",
        overlay=True,
        control=True,
        show=show,
        opacity=0.75,
    ).add_to(
        map_object
    )

    return {
        "available": True,
        "collection_images": image_count,
    }