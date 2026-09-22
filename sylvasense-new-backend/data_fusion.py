"""
SYLVASENSE - Real SAR + Optical Data Fusion
==============================================
Directly answers the ORION-PS-03 requirement: "Multi-Spectral Optical +
Synthetic Aperture Radar (SAR) Data Fusion".

METHOD: Band stacking (early fusion) - a real, published, widely-used
data fusion technique in remote sensing.
"""

import ee
import numpy as np


def fetch_fused_composite(region, start_date, end_date, max_cloud_pct=15):
    s2_collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
    )
    s2_count = s2_collection.size().getInfo()
    if s2_count == 0:
        raise ValueError("No cloud-free Sentinel-2 scenes found for this region/date range.")

    optical = s2_collection.median().clip(region)
    optical_bands = optical.select(["B2", "B3", "B4", "B8"])
    ndvi = optical.normalizedDifference(["B8", "B4"]).rename("NDVI")

    s1_collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )
    s1_count = s1_collection.size().getInfo()
    if s1_count == 0:
        raise ValueError("No Sentinel-1 SAR scenes found for this region/date range.")

    sar = s1_collection.median().clip(region)
    sar_bands = sar.select(["VV", "VH"])

    fused = optical_bands.addBands(sar_bands).addBands(ndvi)

    return {
        "fused_image": fused,
        "band_names": fused.bandNames().getInfo(),
        "s2_scene_count": s2_count,
        "s1_scene_count": s1_count,
    }


def compute_fusion_statistics(fused_image, region, scale=10):
    stats = fused_image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=scale,
        maxPixels=1e9,
    )
    return stats.getInfo()


def classify_forest_biome(mean_ndvi, mean_vv_db, mean_vh_db):
    """
    Simple, honest, rule-based biome/forest-density classification.
    NOT a trained deep classifier - state this plainly in your PPT.
    """
    if mean_ndvi > 0.6 and mean_vh_db > -15:
        return "Dense closed-canopy forest"
    elif mean_ndvi > 0.4 and mean_vh_db > -18:
        return "Moderate/open forest or woodland"
    elif mean_ndvi > 0.2:
        return "Sparse vegetation / shrubland"
    else:
        return "Non-forest (bare soil, water, or built-up area)"


def fuse_and_classify(region, start_date, end_date):
    fusion_result = fetch_fused_composite(region, start_date, end_date)
    stats = compute_fusion_statistics(fusion_result["fused_image"], region)

    mean_ndvi = stats.get("NDVI")
    mean_vv = stats.get("VV")
    mean_vh = stats.get("VH")

    biome = classify_forest_biome(mean_ndvi, mean_vv, mean_vh)

    return {
        "band_names": fusion_result["band_names"],
        "s2_scene_count": fusion_result["s2_scene_count"],
        "s1_scene_count": fusion_result["s1_scene_count"],
        "mean_ndvi": mean_ndvi,
        "mean_vv_db": mean_vv,
        "mean_vh_db": mean_vh,
        "biome_classification": biome,
    }


if __name__ == "__main__":
    ee.Initialize(project="syylvasense")

    point = ee.Geometry.Point([77.05, 10.1])
    region = point.buffer(2000).bounds()

    result = fuse_and_classify(region, "2025-06-01", "2026-02-28")
    for k, v in result.items():
        print(f"{k}: {v}")
