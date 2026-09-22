# SYLVASENSE — Step 1 + Step 2

## What was added

### Step 1: Spectral/SAR layer toggles
The map now exposes separate layers for:

- Blue (B2)
- Green (B3)
- Red (B4)
- NIR (B8)
- Red Edge (B5/B6/B7)
- SWIR 1 (B11)
- SWIR 2 (B12)
- NDVI
- SAR VV
- SAR VH

### Step 2: GEDI LiDAR
The map also adds:

- GEDI RH98 layer
- quality_flag == 1 mask
- degrade_flag == 0 mask
- GEDI project window constrained to March 2019–November 2024
- GEDI latitude coverage check
- RH98 summary statistics

## Run

Install the additional packages:

    pip install -r requirements_additions.txt

Then:

    streamlit run app.py

The app expects Google Earth Engine credentials to already be configured.
The existing project convention uses the GEE project `syylvasense`; you can
override it with the environment variable `GEE_PROJECT`.

## Important scientific note

GEDI RH98 is a spaceborne LiDAR-derived relative-height metric. It should be
used as canopy-height evidence, not as a direct per-tree height measurement.

The current DeepForest workflow still produces bounding boxes. The next
SYLVASENSE gap is true pixel-level crown segmentation.
