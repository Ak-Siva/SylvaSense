from pathlib import Path

APP = Path("app.py")

if not APP.exists():
    raise SystemExit("Run this script from the folder containing app.py.")

original = APP.read_text(encoding="utf-8")
backup = APP.with_name("app_backup_before_step5.py")
backup.write_text(original, encoding="utf-8")

text = original

# Add validation imports.
if "from validation_report import (" not in text:
    marker = "from tree_detection import ("
    pos = text.find(marker)
    if pos == -1:
        raise SystemExit("Could not find tree_detection import block.")
    imports = (
        "from validation_report import (\n"
        "    agb_metrics,\n"
        "    detection_metrics,\n"
        "    mean_iou,\n"
        "    save_validation_report,\n"
        ")\n\n"
    )
    text = text[:pos] + imports + text[pos:]

# Add validation dashboard before the main tabs.
if "def validation_dashboard():" not in text:
    marker = "\n# ============================================================\n# MAIN APPLICATION TABS\n# ============================================================\n"
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("Could not find main application tabs section.")

    function = r