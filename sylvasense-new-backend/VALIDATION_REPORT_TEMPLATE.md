# SYLVASENSE — Validation Report Template

## 1. Scope
This report evaluates tree detection, watershed crown delineation, AGB estimation,
and temporal forecasting against independently prepared reference data.

## 2. Reference data
Do not enter model-generated values as ground truth. Use:
- manually reviewed tree locations/bounding boxes,
- manually digitized crown masks,
- field plot DBH/height/biomass measurements, or
- an independent published/reference dataset.

Record source, date, coordinate system, sample size, and measurement method.

## 3. Tree detection
Report TP, FP, FN, precision, recall, and F1.

## 4. Crown segmentation
For each reference crown, report IoU and optionally Dice.
State that SYLVASENSE uses watershed-based classical CV constrained by DeepForest detections.

## 5. AGB
Report MAE, RMSE and R² between independently measured/reference AGB and predicted AGB.

## 6. Forecasting
Report historical dates and AGB values used to fit the trend.
Report forecast horizon and the linear-trend assumption.
Do not call the result a validated forecast until it has been tested against a held-out
future observation.

## 7. Limitations
- GEDI is spaceborne LiDAR-derived data and has approximately 25 m footprints.
- GEDI observations are limited to the mission's acquisition period and latitude coverage.
- Watershed segmentation is a classical CV method, not a learned instance-segmentation model.
- The AGB forecast is a trend projection, not a physical ecosystem model.
- Biomass accuracy depends on allometric assumptions and independent calibration.
