# SYLVASENSE Step 5 - Formal Validation

1. Copy `validation_report.py` and `patch_step5.py` into the same folder as `app.py`.

2. Run:
   python patch_step5.py

3. Check syntax:
   python -m py_compile app.py

4. Run:
   streamlit run app.py

A fifth tab named `✅ Validation` will appear.

Inputs:
- Tree detection: predicted count, reference count, matched count.
- Crown segmentation: CSV containing IoU values from predicted-vs-reference masks.
- AGB: CSV with `reference_agb_tonnes,predicted_agb_tonnes`.

The module does not invent ground-truth/reference data.
