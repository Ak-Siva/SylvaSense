"""
SYLVASENSE - Interactive Sentinel-2 / Sentinel-1 spectral layers.

Adds individual Earth Engine layers to a Folium map so the user can
turn Blue, Green, Red, NIR, Red Edge, SWIR, NDVI, VV and VH on/off.
"""

import ee
import folium


S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S1_COLLECTION = "COPERNICUS/S1_GRD"


SPECTRAL_VIS = {
    "Blue (B2)": {"bands": ["B2"], "min": 0.0, "max": 0.30},
    "Green (B3)": {"bands": ["B3"], "min": 0.0, "max": 0.30},
    "Red (B4)": {"bands": ["B4"], "min": 0.0, "max": 0.30},
    "NIR (B8)": {"bands": ["B8"], "min": 0.0, "max": 0.50},
    "Red Edge (B5/B6/B7)": {
        "bands": ["B5", "B6", "B7"],
        "min": 0.0,
        "max": 0.40,
    },
    "SWIR 1 (B11)": {"bands": ["B11"], "min": 0.0, "max": 0.40},
    "SWIR 2 (B12)": {"bands": ["B12"], "min": 0.0, "max": 0.40},
    "NDVI": {
        "bands": ["NDVI"],
        "min": -0.2,
        "max": 0.9,
        "palette": ["8c510a", "f6e8c3", "c7eae5", "01665e"],
    },
    "SAR VV": {"bands": ["VV"], "min": -25, "max": 5},
    "SAR VH": {"bands": ["VH"], "min": -30, "max": 0},
}


def get_layer_images(region, start_date, end_date, max_cloud_pct=15):
    """Return real Sentinel-2 and Sentinel-1 composites and scene counts."""
    s2 = (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
    )

    s2_count = s2.size().getInfo()
    if s2_count == 0:
        raise ValueError("No Sentinel-2 scenes found for this region/date range.")

    optical = s2.median().clip(region)
    ndvi = optical.normalizedDifference(["B8", "B4"]).rename("NDVI")

    s1 = (
        ee.ImageCollection(S1_COLLECTION)
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(
            ee.Filter.listContains(
                "transmitterReceiverPolarisation", "VV"
            )
        )
        .filter(
            ee.Filter.listContains(
                "transmitterReceiverPolarisation", "VH"
            )
        )
    )

    s1_count = s1.size().getInfo()
    if s1_count == 0:
        raise ValueError("No Sentinel-1 VV/VH scenes found for this region/date range.")

    sar = s1.median().clip(region)

    return {
        "optical": optical,
        "ndvi": ndvi,
        "sar": sar,
        "s2_count": s2_count,
        "s1_count": s1_count,
    }


def add_ee_image_layer(map_object, image, name, vis_params, show=False, opacity=0.85):
    """Add an Earth Engine image as a Folium toggleable tile layer."""
    map_id = image.getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
        show=show,
        opacity=opacity,
    ).add_to(map_object)


def add_spectral_layers(
    map_object,
    region,
    start_date,
    end_date,
    max_cloud_pct=15,
    include_sar=True,
):
    """Add individual spectral/SAR layers and return scene counts."""
    data = get_layer_images(
        region, start_date, end_date, max_cloud_pct=max_cloud_pct
    )

    optical = data["optical"]
    for name, params in SPECTRAL_VIS.items():
        if name == "NDVI":
            image = data["ndvi"]
        elif name.startswith("SAR"):
            if not include_sar:
                continue
            image = data["sar"]
        else:
            image = optical

        add_ee_image_layer(
            map_object,
            image,
            name,
            params,
            show=(name in {"NIR (B8)", "NDVI"}),
        )

    return {
        "s2_count": data["s2_count"],
        "s1_count": data["s1_count"],
    }
