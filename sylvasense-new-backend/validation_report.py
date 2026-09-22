"""
SYLVASENSE - Validation Metrics

Provides reproducible metrics for a validation table. It does not create
ground truth; the reference values must come from independently measured
or manually verified observations.
"""
import numpy as np
import pandas as pd


def regression_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) != len(y_pred) or len(y_true) == 0:
        raise ValueError("Reference and prediction arrays must have equal non-zero length.")

    error = y_pred - y_true
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error ** 2)))
    ss_res = float(np.sum(error ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = None if ss_tot == 0 else float(1 - ss_res / ss_tot)

    return {"MAE": mae, "RMSE": rmse, "R2": r2}


def detection_metrics(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "TP": int(tp),
        "FP": int(fp),
        "FN": int(fn),
        "precision": precision,
        "recall": recall,
        "F1": f1,
    }


def iou(mask_a, mask_b):
    a = np.asarray(mask_a, dtype=bool)
    b = np.asarray(mask_b, dtype=bool)
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def build_validation_report(
    detection=None,
    segmentation_ious=None,
    agb_true=None,
    agb_pred=None,
):
    report = {
        "validation_standard": (
            "Reference values must be independently measured, manually annotated, "
            "or otherwise external to the prediction pipeline."
        )
    }

    if detection:
        report["tree_detection"] = detection_metrics(
            detection["TP"], detection["FP"], detection["FN"]
        )

    if segmentation_ious is not None and len(segmentation_ious):
        report["segmentation"] = {
            "mean_IoU": float(np.mean(segmentation_ious)),
            "median_IoU": float(np.median(segmentation_ious)),
            "n_reference_masks": len(segmentation_ious),
        }

    if agb_true is not None and agb_pred is not None:
        report["AGB"] = regression_metrics(agb_true, agb_pred)

    return report


def save_report(report, path="sylvasense_validation_report.json"):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return path


if __name__ == "__main__":
    demo = build_validation_report(
        detection={"TP": 50, "FP": 5, "FN": 8},
        segmentation_ious=[0.71, 0.76, 0.68],
        agb_true=[100, 120, 140],
        agb_pred=[105, 118, 136],
    )
    print(json.dumps(demo, indent=2))
