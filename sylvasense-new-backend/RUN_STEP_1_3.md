# SYLVASENSE — Step 1 + 2 + 3

Run from this folder:

```powershell
pip install -r requirements_additions.txt
streamlit run app.py
```

## Step 3: Pixel-level crown segmentation

The Tree Detection tab now runs:

DeepForest detection box -> Excess Green vegetation mask -> morphology -> distance transform -> watershed -> individual crown pixel mask.

The app displays:
- pixel-level crown instance overlay
- segmented crown area (m²)
- equivalent segmented crown diameter
- mask coverage
- CSV results
- pixel-coordinate GeoJSON crown polygons

### Important methodology note

This is classical computer-vision instance segmentation. It is a genuine pixel mask refinement, but it is not a trained neural instance-segmentation network such as Mask R-CNN or Mask2Former.

The segmented equivalent crown diameter is used for the biomass allometry when a valid mask is available; otherwise the original detection-box diameter is retained as a fallback.

The GeoJSON export is explicitly in image pixel coordinates. It is not longitude/latitude unless a raster geotransform is added.
