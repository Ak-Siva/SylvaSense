"""
SYLVASENSE - Integrated Step 1 + Step 2 prototype
Run:
    streamlit run app.py

Added:
1. Individual Sentinel-2 spectral / Sentinel-1 SAR map toggles.
2. NASA GEDI RH98 LiDAR layer and statistics.

The existing DeepForest + biomass workflow is preserved.
"""

import datetime as dt
import os
import tempfile
import traceback

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from deepforest import get_data
from streamlit_folium import st_folium

from biomass import per_tree_biomass_pipeline, ndvi_to_agb_density
from data_fusion import fetch_fused_composite
from lidar_gedi import (
    GEDI_START,
    add_gedi_layer,
    gedi_statistics,
)
from spectral_layers import add_spectral_layers
from tree_detection import (
    compute_crown_metrics,
    detect_trees,
    visualize_detections,
)

from crown_segmentation import (
    overlay_segmentation,
    save_segmentation_geojson,
    segment_tree_crowns,
)

st.set_page_config(page_title="SylvaSense", layout="wide")

st.title("SylvaSense — Earth Observation & Tree Intelligence")
st.caption(
    "ORION-PS-03 | Sentinel-2 + Sentinel-1 + GEDI + DeepForest + Chave 2014"
)

MAX_UPLOAD_MB = 25
MIN_IMAGE_DIM = 100


@st.cache_resource(show_spinner=False)
def load_real_model():
    from deepforest import main as df_main

    model = df_main.deepforest()
    model.load_model(model_name="weecology/deepforest-tree", revision="main")
    return model


def get_model_or_show_error():
    try:
        with st.spinner("Loading DeepForest model..."):
            return load_real_model()
    except Exception:
        st.error(
            "Could not load the DeepForest model. Check internet access and "
            "the DeepForest installation."
        )
        with st.expander("Technical error"):
            st.code(traceback.format_exc())
        st.stop()


def validate_uploaded_image(uploaded_file):
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        return False, f"File is {size_mb:.1f}MB; maximum is {MAX_UPLOAD_MB}MB."

    try:
        from PIL import Image

        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        width, height = img.size
        uploaded_file.seek(0)

        if width < MIN_IMAGE_DIM or height < MIN_IMAGE_DIM:
            return (
                False,
                f"Image is {width}x{height}px; minimum is {MIN_IMAGE_DIM}px per side.",
            )
        return True, None
    except Exception:
        return False, "Could not read the uploaded image."


def build_region(lat, lon, radius_m):
    import ee

    point = ee.Geometry.Point([lon, lat])
    return point.buffer(radius_m).bounds()


def spectral_lidar_dashboard():
    st.header("🛰️ Spectral Bands + GEDI LiDAR Map")
    st.write(
        "Explore real Earth Engine layers individually. Use the map controls "
        "to switch Sentinel-2/Sentinel-1 layers on or off."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        lat = st.number_input(
            "Latitude",
            value=10.10,
            min_value=-90.0,
            max_value=90.0,
            format="%.6f",
        )
    with col2:
        lon = st.number_input(
            "Longitude",
            value=77.05,
            min_value=-180.0,
            max_value=180.0,
            format="%.6f",
        )
    with col3:
        radius = st.number_input(
            "Radius (metres)",
            min_value=100,
            max_value=10000,
            value=2000,
            step=100,
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        start = st.date_input(
            "Sentinel start date",
            value=dt.date(2025, 6, 1),
        )
    with c2:
        end = st.date_input(
            "Sentinel end date",
            value=dt.date(2026, 2, 28),
        )
    with c3:
        cloud = st.slider(
            "Maximum Sentinel-2 cloud %",
            0,
            100,
            15,
        )

    g1, g2 = st.columns(2)
    with g1:
        gedi_start = st.date_input(
            "GEDI start date",
            value=dt.date(2019, 3, 25),
            min_value=dt.date(2019, 3, 25),
            max_value=dt.date(2024, 11, 29),
        )
    with g2:
        gedi_end = st.date_input(
            "GEDI end date",
            value=dt.date(2024, 11, 29),
            min_value=dt.date(2019, 3, 25),
            max_value=dt.date(2024, 11, 29),
        )

    if start >= end:
        st.error("Sentinel start date must be before the end date.")
        return
    if gedi_start > gedi_end:
        st.error("GEDI start date must be on or before the end date.")
        return

    if st.button("Build Earth Observation Map", type="primary"):
        try:
            import ee

            # Use the same GEE project convention already used by the project.
            ee.Initialize(project=os.getenv("GEE_PROJECT", "syylvasense"))

            region = build_region(lat, lon, radius)
            m = folium.Map(
                location=[lat, lon],
                zoom_start=13,
                control_scale=True,
            )

            folium.TileLayer(
                "OpenStreetMap",
                name="Street",
                control=True,
                show=True,
            ).add_to(m)

            # Satellite base layer.
            folium.TileLayer(
                tiles=(
                    "https://server.arcgisonline.com/ArcGIS/rest/services/"
                    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                ),
                attr="Esri World Imagery",
                name="Satellite",
                overlay=False,
                control=True,
                show=False,
            ).add_to(m)

            scene_info = add_spectral_layers(
                m,
                region,
                str(start),
                str(end),
                max_cloud_pct=cloud,
                include_sar=True,
            )

            gedi_info = add_gedi_layer(
                m,
                region,
                str(gedi_start),
                str(gedi_end),
                show=False,
            )

            folium.LayerControl(collapsed=False).add_to(m)

            st_folium(
                m,
                use_container_width=True,
                height=650,
                returned_objects=[],
            )

            st.success("Map built successfully.")

            a, b, c = st.columns(3)
            a.metric("Sentinel-2 scenes", scene_info["s2_count"])
            b.metric("Sentinel-1 scenes", scene_info["s1_count"])
            c.metric("GEDI collection images", gedi_info["collection_images"])

            with st.expander("GEDI RH98 statistics"):
                stats = gedi_statistics(
                    region,
                    str(gedi_start),
                    str(gedi_end),
                )
                st.json(stats)

            st.info(
                "GEDI RH98 represents the 98th-percentile relative height "
                "metric from quality-filtered GEDI observations. It is a "
                "LiDAR-derived canopy-height indicator, not a direct per-tree "
                "measurement."
            )

        except Exception as exc:
            st.error("Could not build the Earth Observation map.")
            st.write(str(exc))
            with st.expander("Technical error"):
                st.code(traceback.format_exc())


def tree_detection_dashboard():
    st.header("🌳 Per-tree Detection & Biomass")

    source = st.radio(
        "Image source:",
        [
            "Use DeepForest's real NEON sample plot",
            "Upload your own aerial/drone image",
        ],
    )

    image_path = None

    if source.startswith("Use DeepForest"):
        image_path = get_data("OSBS_029.tif")
        st.info("Using DeepForest's real NEON sample image.")
    else:
        uploaded = st.file_uploader(
            "Upload image (TIF/JPG/PNG)",
            type=["tif", "tiff", "jpg", "jpeg", "png"],
        )
        if uploaded:
            valid, error = validate_uploaded_image(uploaded)
            if not valid:
                st.error(error)
            else:
                suffix = os.path.splitext(uploaded.name)[1]
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix
                ) as tmp:
                    uploaded.seek(0)
                    tmp.write(uploaded.read())
                    image_path = tmp.name

    pixel_size = st.number_input(
        "Ground sample distance (metres/pixel)",
        min_value=0.01,
        max_value=10.0,
        value=0.1,
        step=0.01,
    )
    wood_density = st.slider(
        "Wood density (g/cm³)",
        0.3,
        0.9,
        0.6,
        0.05,
    )

    run_segmentation = st.checkbox(
        "Run pixel-level crown segmentation after detection",
        value=True,
        help=(
            "Refines each DeepForest detection box into a pixel mask using "
            "Excess Green + morphology + watershed. This is classical "
            "computer-vision instance segmentation, not a trained "
            "Mask R-CNN/Mask2Former model."
        ),
    )

    if st.button(
        "Run detection + crown segmentation",
        type="primary",
        disabled=image_path is None,
    ):
        model = get_model_or_show_error()

        try:
            with st.spinner("Running DeepForest inference..."):
                predictions = detect_trees(model, image_path)

            if predictions is None or len(predictions) == 0:
                st.warning("No tree crowns were detected.")
                return

            predictions = compute_crown_metrics(
                predictions,
                pixel_size_m=pixel_size,
            )

            segmentation_masks = None
            if run_segmentation:
                with st.spinner(
                    "Refining detections into pixel-level crown masks..."
                ):
                    predictions, segmentation_masks = segment_tree_crowns(
                        image_path,
                        predictions,
                        pixel_size_m=pixel_size,
                    )

                valid_count = int(
                    predictions["segmentation_valid"].sum()
                )
                st.success(
                    f"Crown segmentation completed: {valid_count}/"
                    f"{len(predictions)} detections received valid masks."
                )

            if run_segmentation and segmentation_masks is not None:
                predictions["biomass_crown_diameter_m"] = predictions[
                    "crown_diameter_m"
                ]
                valid = (
                    predictions["segmentation_valid"]
                    & (predictions["segmentation_crown_diameter_m"] > 0)
                )
                predictions.loc[valid, "biomass_crown_diameter_m"] = predictions.loc[
                    valid, "segmentation_crown_diameter_m"
                ]
                biomass_diameter_column = "biomass_crown_diameter_m"
            else:
                biomass_diameter_column = "crown_diameter_m"

            results = per_tree_biomass_pipeline(
                predictions,
                wood_density_g_cm3=wood_density,
                crown_diameter_column=biomass_diameter_column,
            )

            col1, col2 = st.columns([2, 1])
            with col1:
                if run_segmentation and segmentation_masks is not None:
                    seg_path = overlay_segmentation(
                        image_path,
                        predictions,
                        segmentation_masks,
                        "sylvasense_crown_segmentation.png",
                    )
                    st.image(
                        seg_path,
                        caption=(
                            f"Pixel-level crown instances — "
                            f"{len(predictions)} detected trees"
                        ),
                        use_container_width=True,
                    )
                else:
                    viz_path = visualize_detections(
                        image_path,
                        predictions,
                        "streamlit_detection.png",
                    )
                    st.image(
                        viz_path,
                        caption=f"{len(predictions)} detected tree crowns",
                        use_container_width=True,
                    )

            with col2:
                st.metric("Trees detected", len(predictions))
                st.metric(
                    "Total AGB",
                    f"{results['agb_tonnes'].sum():.2f} tonnes",
                )
                st.metric(
                    "Total Carbon",
                    f"{results['carbon_tonnes'].sum():.2f} tonnes C",
                )
                st.metric(
                    "CO₂ equivalent",
                    f"{results['co2e_tonnes'].sum():.2f} tonnes CO₂e",
                )

            st.subheader("Per-tree results")
            st.dataframe(
                results[
                    [
                        "xmin", "ymin", "xmax", "ymax", "score",
                        "crown_diameter_m",
                        "biomass_crown_diameter_m",
                        "dbh_cm", "height_m",
                        "agb_tonnes", "co2e_tonnes",
                    ]
                    + (
                        [
                            "segmentation_area_m2",
                            "segmentation_crown_diameter_m",
                            "segmentation_mask_fraction",
                            "segmentation_valid",
                        ]
                        if run_segmentation
                        else []
                    )
                ].round(3),
                use_container_width=True,
            )

            if run_segmentation and segmentation_masks is not None:
                st.subheader("Crown segmentation outputs")
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric(
                    "Valid crown masks",
                    int(predictions["segmentation_valid"].sum()),
                )
                sc2.metric(
                    "Mean segmented crown area",
                    f"{predictions['segmentation_area_m2'].mean():.2f} m²",
                )
                sc3.metric(
                    "Mean mask coverage",
                    f"{predictions['segmentation_mask_fraction'].mean() * 100:.1f}%",
                )

                geojson_path = save_segmentation_geojson(
                    predictions,
                    segmentation_masks,
                    "sylvasense_crown_masks.geojson",
                )
                with open(geojson_path, "rb") as f:
                    st.download_button(
                        "Download crown mask GeoJSON (pixel coordinates)",
                        f.read(),
                        "sylvasense_crown_masks.geojson",
                        "application/geo+json",
                    )
                st.caption(
                    "The exported polygons are in image pixel coordinates, "
                    "not longitude/latitude. A raster geotransform is required "
                    "to convert them to geographic coordinates."
                )

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.hist(
                results["dbh_cm"],
                bins=min(15, max(1, len(results))),
                edgecolor="black",
                alpha=0.8,
            )
            ax.set_xlabel("Estimated DBH (cm)")
            ax.set_ylabel("Number of trees")
            ax.set_title("Tree size distribution")
            st.pyplot(fig)

            st.download_button(
                "Download full results (CSV)",
                results.to_csv(index=False),
                "sylvasense_results.csv",
                "text/csv",
            )

            if run_segmentation:
                st.caption(
                    "Crown area is now measured from the segmented pixel mask. "
                    "Segmentation uses classical watershed CV within each "
                    "DeepForest detection box; production-grade learned "
                    "instance segmentation can be added later."
                )
            else:
                st.caption(
                    "Crown metric is derived from DeepForest detection boxes "
                    "because segmentation was disabled."
                )

        except Exception:
            st.error("Detection or biomass calculation failed.")
            with st.expander("Technical error"):
                st.code(traceback.format_exc())


def area_biomass_dashboard():
    st.header("🌱 Area-based Biomass Proxy")
    st.warning(
        "Sentinel-2 pixels are 10 m across, so individual trees cannot be "
        "reliably counted from Sentinel-2 alone."
    )

    mean_ndvi = st.slider("Mean NDVI", 0.0, 1.0, 0.65, 0.01)
    area_ha = st.number_input(
        "Region area (hectares)",
        min_value=0.1,
        value=400.0,
        step=10.0,
    )

    if st.button("Estimate area-based biomass"):
        agb_per_ha = ndvi_to_agb_density(np.array([mean_ndvi]))[0]
        total_agb = agb_per_ha * area_ha

        c1, c2, c3 = st.columns(3)
        c1.metric("AGB density", f"{agb_per_ha:.1f} t/ha")
        c2.metric("Total AGB", f"{total_agb:.0f} tonnes")
        c3.metric(
            "CO₂e",
            f"{total_agb * 0.47 * 3.6663:.0f} tonnes",
        )

        st.caption(
            "Methodology: illustrative NDVI-biomass regression. "
            "Field calibration is required for production use."
        )


tabs = st.tabs(
    [
        "🛰️ Spectral + GEDI Map",
        "🌳 Tree Detection",
        "🌱 Area Biomass",
    ]
)

with tabs[0]:
    spectral_lidar_dashboard()

with tabs[1]:
    tree_detection_dashboard()

with tabs[2]:
    area_biomass_dashboard()

st.divider()
st.caption(
    "SYLVASENSE | ORION-PS-03 | Step 1 + Step 2 integrated prototype"
)
