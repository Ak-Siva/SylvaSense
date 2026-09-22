import ee
import folium


GEDI_COLLECTION = (
    "LARSE/GEDI/GEDI02_A_002_MONTHLY"
)

GEDI_START = "2019-03-25"

GEDI_END_EXCLUSIVE = (
    "2024-12-01"
)

GEDI_LAT_MIN = -51.6
GEDI_LAT_MAX = 51.6


def validate_gedi_window(
    start_date,
    end_date,
):

    if str(start_date) < GEDI_START:

        raise ValueError(
            f"GEDI analysis cannot start "
            f"before {GEDI_START}."
        )

    if (
        str(end_date)
        >= GEDI_END_EXCLUSIVE
    ):

        raise ValueError(
            "GEDI analysis end date must "
            "be before 2024-12-01 "
            "(project window ends in "
            "November 2024)."
        )


def validate_gedi_region(
    region
):

    coords = (
        region
        .bounds()
        .coordinates()
        .getInfo()[0]
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
            "The selected region is "
            "outside GEDI coverage."
        )


def get_gedi_rh98(
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
):

    validate_gedi_window(
        start_date,
        end_date,
    )

    validate_gedi_region(
        region
    )

    collection = (
        ee.ImageCollection(
            GEDI_COLLECTION
        )
        .filterBounds(region)
        .filterDate(
            start_date,
            "2024-12-01",
        )
        .map(
            lambda image:
                image
                .updateMask(
                    image
                    .select(
                        "quality_flag"
                    )
                    .eq(1)
                )
                .updateMask(
                    image
                    .select(
                        "degrade_flag"
                    )
                    .eq(0)
                )
        )
        .select("rh98")
    )

    count = (
        collection
        .size()
        .getInfo()
    )

    if count == 0:

        raise ValueError(
            "No quality-filtered GEDI "
            "RH98 observations were "
            "found for this region."
        )

    image = (
        collection
        .median()
        .clip(region)
    )

    return image, count


def gedi_statistics(
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
):

    image, count = (
        get_gedi_rh98(
            region,
            start_date,
            end_date,
        )
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
        )
        .getInfo()
    )

    return {
        "collection_images": count,
        "rh98_mean_m": stats.get(
            "rh98_mean"
        ),
        "rh98_min_m": stats.get(
            "rh98_min"
        ),
        "rh98_max_m": stats.get(
            "rh98_max"
        ),
        "rh98_valid_pixels": stats.get(
            "rh98_count"
        ),
    }


def add_gedi_layer(
    map_object,
    region,
    start_date=GEDI_START,
    end_date="2024-11-30",
    show=False,
):

    image, count = (
        get_gedi_rh98(
            region,
            start_date,
            end_date,
        )
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
        "collection_images": count
    }