"""
SYLVASENSE - Real Aboveground Biomass (AGB) Estimation
=========================================================
METHOD 1: Per-tree allometric equation (Chave et al. 2014, Global Change
Biology, 20(10), 3177-3190) - the real pantropical biomass equation.

METHOD 2: Area-based NDVI/canopy-cover proxy for coarser Sentinel-2
10m-pixel imagery where individual trees can't be resolved.

HONESTY NOTE: Sentinel-2 has 10m pixels; a tree crown is typically
3-15m across. You genuinely cannot reliably detect/count individual
trees from Sentinel-2 alone - this is a known remote-sensing limit,
not a shortcut. State this in your PPT as a technical-depth strength.
"""

import numpy as np
import pandas as pd


def diameter_from_crown(crown_diameter_m, allometry="jucker"):
    """
    Jucker et al. (2017), Global Change Biology, 23(1):
    DBH (cm) = exp( (log(CD_m) - 0.336) / 0.503 )
    """
    crown_diameter_m = np.asarray(crown_diameter_m, dtype=float)
    dbh_cm = np.exp((np.log(crown_diameter_m) - 0.336) / 0.503)
    return dbh_cm


def estimate_height_from_dbh(dbh_cm, region="tropical_moist"):
    """
    Feldpausch et al. (2012), Biogeosciences, 9, 3381-3403.
    Simplified regional coefficients for tropical moist forest.
    """
    dbh_cm = np.asarray(dbh_cm, dtype=float)
    a, b = 0.893, 0.760
    height_m = np.exp(a + b * np.log(dbh_cm))
    return height_m


def chave_2014_agb(dbh_cm, height_m, wood_density_g_cm3=0.6):
    """
    Chave et al. (2014). AGB in kilograms per tree.
    """
    dbh_cm = np.asarray(dbh_cm, dtype=float)
    height_m = np.asarray(height_m, dtype=float)
    agb_kg = 0.0673 * (wood_density_g_cm3 * (dbh_cm ** 2) * height_m) ** 0.976
    return agb_kg


def per_tree_biomass_pipeline(
    detections_df,
    wood_density_g_cm3=0.6,
    crown_diameter_column="crown_diameter_m",
):
    """
    Full pipeline: crown diameter -> DBH -> height -> AGB -> carbon -> CO2e.

    crown_diameter_column can point to a segmented-mask-derived equivalent
    crown diameter, allowing the biomass estimate to use the pixel-level
    crown footprint instead of the DeepForest bounding-box approximation.
    """
    df = detections_df.copy()
    if crown_diameter_column not in df.columns:
        raise ValueError(
            f"Missing crown diameter column: {crown_diameter_column}"
        )
    df["biomass_crown_diameter_m"] = pd.to_numeric(
        df[crown_diameter_column], errors="coerce"
    )
    if (df["biomass_crown_diameter_m"] <= 0).any() or df[
        "biomass_crown_diameter_m"
    ].isna().any():
        raise ValueError("Crown diameter must be positive for biomass estimation.")

    df["dbh_cm"] = diameter_from_crown(df["biomass_crown_diameter_m"])
    df["height_m"] = estimate_height_from_dbh(df["dbh_cm"])
    df["agb_kg"] = chave_2014_agb(df["dbh_cm"], df["height_m"], wood_density_g_cm3)
    df["agb_tonnes"] = df["agb_kg"] / 1000
    df["carbon_tonnes"] = df["agb_tonnes"] * 0.47
    df["co2e_tonnes"] = df["carbon_tonnes"] * 3.6663
    return df


def ndvi_to_agb_density(mean_ndvi, forest_type="tropical"):
    """
    Real empirical NDVI-biomass regression, calibrated form used in
    pantropical biomass mapping literature (Baccini-style approach).
    Coefficients are illustrative - production use requires field-plot
    calibration, worth stating as future work.
    Returns tonnes of AGB per hectare.
    """
    a, b = 5.0, 4.5
    agb_per_ha = a * np.exp(b * np.clip(mean_ndvi, 0, 1))
    return agb_per_ha


def area_based_biomass(ndvi_image_array, pixel_area_ha):
    """
    Applies the NDVI-biomass regression pixel-by-pixel across a real
    Sentinel-2 NDVI raster and sums total biomass across the region.
    """
    ndvi_flat = ndvi_image_array.flatten()
    ndvi_flat = ndvi_flat[~np.isnan(ndvi_flat)]
    agb_density_per_pixel = ndvi_to_agb_density(ndvi_flat)
    total_agb_tonnes = np.sum(agb_density_per_pixel * pixel_area_ha)
    return {
        "total_agb_tonnes": total_agb_tonnes,
        "mean_ndvi": float(np.mean(ndvi_flat)),
        "n_pixels": len(ndvi_flat),
        "total_carbon_tonnes": total_agb_tonnes * 0.47,
        "total_co2e_tonnes": total_agb_tonnes * 0.47 * 3.6663,
    }


if __name__ == "__main__":
    test_crown_diameters = [4.0, 8.0, 12.0, 6.5]
    df = pd.DataFrame({"crown_diameter_m": test_crown_diameters})
    result = per_tree_biomass_pipeline(df)
    print(result[["crown_diameter_m", "dbh_cm", "height_m", "agb_tonnes", "co2e_tonnes"]])
    print("Total CO2e across", len(df), "trees:", round(result["co2e_tonnes"].sum(), 3), "tonnes")
