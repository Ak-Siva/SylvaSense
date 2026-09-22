"""
SYLVASENSE - Enhanced Interactive Spectral + LiDAR Dashboard

Run:
    streamlit run interactive_spectral_lidar_map.py

This is an additive dashboard around the existing GEE fusion pipeline.
"""
import streamlit as st
import folium
import ee
from streamlit_folium import st_folium

from spectral_layers import add_spectral_layers
from lidar_gedi import add_gedi_layer, gedi_statistics

GEE_PROJECT = "syylvasense"

st.set_page_config(page_title="SylvaSense - Spectral + GEDI", layout="wide")
st.title("SylvaSense — Spectral, SAR & GEDI Explorer")
st.caption("Real Sentinel-2 / Sentinel-1 / NASA GEDI layers from Google Earth Engine")


@st.cache_resource(show_spinner=False)
def init_gee():
    ee.Initialize(project=GEE_PROJECT)
    return True


try:
    init_gee()
except Exception as exc:
    st.error("Google Earth Engine initialization failed.")
    st.exception(exc)
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    lat = st.number_input("Latitude", value=10.10, format="%.6f")
with col2:
    lon = st.number_input("Longitude", value=77.05, format="%.6f")
with col3:
    radius = st.number_input("Radius (km)", min_value=0.5, max_value=20.0, value=2.0)

col4, col5 = st.columns(2)
with col4:
    start_date = st.date_input("Sentinel start date", value=None)
with col5:
    end_date = st.date_input("Sentinel end date", value=None)

# Streamlit's date_input cannot use None consistently across versions.
# Use the project's previously demonstrated dates as defaults when blank.
if start_date is None:
    start_date = "2025-06-01"
else:
    start_date = start_date.isoformat()
if end_date is None:
    end_date = "2026-02-28"
else:
    end_date = end_date.isoformat()

point = ee.Geometry.Point([lon, lat])
region = point.buffer(radius * 1000).bounds()

m = folium.Map(location=[lat, lon], zoom_start=12, tiles=None)
folium.TileLayer(
    "OpenStreetMap", name="Street Map", overlay=False, control=True
).add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery",
    name="Satellite (Esri)",
    overlay=False,
    control=True,
).add_to(m)

try:
    spectral_result = add_spectral_layers(
        m, region, start_date, end_date, max_cloud_pct=15
    )
    gedi_result = add_gedi_layer(
        m, region, start_date="2019-03-25", end_date="2024-11-30"
    )
except Exception as exc:
    st.error("Could not create one or more Earth Engine layers.")
    st.exception(exc)
    st.stop()

folium.Marker([lat, lon], tooltip="SYLVASENSE target").add_to(m)
st_folium(m, height=620, use_container_width=True)

st.subheader("Live data summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sentinel-2 scenes", spectral_result["s2_scene_count"])
c2.metric("Sentinel-1 scenes", spectral_result["s1_scene_count"])
c3.metric("GEDI monthly images", gedi_result["image_count"])
c4.metric("GEDI metric", "rh98")

try:
    stats = gedi_statistics(region)
    a, b, c = st.columns(3)
    a.metric("Mean GEDI canopy height", f"{stats['mean_canopy_height_m']:.2f} m" if stats["mean_canopy_height_m"] is not None else "N/A")
    b.metric("Min rh98", f"{stats['min_canopy_height_m']:.2f} m" if stats["min_canopy_height_m"] is not None else "N/A")
    c.metric("Max rh98", f"{stats['max_canopy_height_m']:.2f} m" if stats["max_canopy_height_m"] is not None else "N/A")
except Exception as exc:
    st.warning(f"GEDI statistics unavailable for this ROI: {exc}")

st.info(
    "Spectral toggles are real Earth Engine raster layers. "
    "GEDI is spaceborne LiDAR-derived canopy-height information at approximately "
    "25 m footprint/raster scale; it is not an airborne point cloud."
)
