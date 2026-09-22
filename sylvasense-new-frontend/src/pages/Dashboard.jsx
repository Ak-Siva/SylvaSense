import React from "react";

import {
  Activity,
  BarChart3,
  BrainCircuit,
  Gauge,
  Layers3,
  Leaf,
  ScanSearch,
  Satellite,
  TreePine,
  Trees,
} from "lucide-react";

import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";
import StatusDot from "../components/StatusDot";

import { fmt } from "../utils/normalize";
import { getApiBase } from "../services/api";

/* =========================================================
   AVAILABILITY
========================================================= */

function Availability({ status, label }) {
  return (
    <div className="availability">
      <StatusDot status={status} />

      <span>{label}</span>

      <strong>
        {status ? "READY" : "UNAVAILABLE"}
      </strong>
    </div>
  );
}

/* =========================================================
   FIND CANOPY COVERAGE
========================================================= */

/*
  The backend may return canopy_coverage_percent
  directly, inside an array, or nested inside another object.

  This function searches the complete crown segmentation
  response until it finds the first valid value.
*/

function findCanopyCoverage(data) {
  if (data === null || data === undefined) {
    return null;
  }

  /* Direct canopy value */

  if (
    typeof data === "object" &&
    !Array.isArray(data) &&
    data.canopy_coverage_percent !== null &&
    data.canopy_coverage_percent !== undefined
  ) {
    const value = Number(
      data.canopy_coverage_percent
    );

    if (!Number.isNaN(value)) {
      return value;
    }
  }

  /* Array */

  if (Array.isArray(data)) {
    for (const item of data) {
      const value = findCanopyCoverage(item);

      if (
        value !== null &&
        value !== undefined &&
        !Number.isNaN(value)
      ) {
        return value;
      }
    }

    return null;
  }

  /* Nested object */

  if (typeof data === "object") {
    for (const [key, value] of Object.entries(data)) {
      if (
        key === "canopy_coverage_percent" &&
        value !== null &&
        value !== undefined
      ) {
        const numberValue = Number(value);

        if (!Number.isNaN(numberValue)) {
          return numberValue;
        }
      }

      if (
        value !== null &&
        typeof value === "object"
      ) {
        const found = findCanopyCoverage(value);

        if (
          found !== null &&
          found !== undefined &&
          !Number.isNaN(found)
        ) {
          return found;
        }
      }
    }
  }

  return null;
}

/* =========================================================
   DASHBOARD
========================================================= */

export default function Dashboard({
  result,
  backendOnline,
  setPage,
}) {
  /* =======================================================
     TREE COUNT
  ======================================================= */

  const treeCount =
    result?.tree_count ??
    result?.treeCount ??
    result?.modules?.tree_detection?.tree_count ??
    0;

  /* =======================================================
     CROWN SEGMENTATION
  ======================================================= */

  const crownSegmentation =
    result?.modules?.crown_segmentation;

  /* =======================================================
     CROWN COUNT
  ======================================================= */

  const crownCount =
    result?.crown_count ??
    result?.crownCount ??
    result?.modules?.crown_segmentation?.tree_count ??
    result?.modules?.crown_segmentation?.crown_count ??
    (Array.isArray(crownSegmentation)
      ? crownSegmentation.length
      : 0);

  /* =======================================================
     BIOMASS
  ======================================================= */

  const biomass =
    result?.modules?.biomass ?? {};

  const agb =
    biomass?.total_agb_tonnes ??
    result?.total_agb_tonnes ??
    result?.agb ??
    null;

  /* =======================================================
     CARBON
  ======================================================= */

  const carbon =
    biomass?.total_carbon_tonnes ??
    result?.total_carbon_tonnes ??
    result?.carbon ??
    result?.carbon_tonnes ??
    result?.carbonValue ??
    null;

  /* =======================================================
     CO2 EQUIVALENT
  ======================================================= */

  const co2e =
    biomass?.total_co2e_tonnes ??
    result?.total_co2e_tonnes ??
    result?.co2e ??
    result?.co2eValue ??
    null;

  /* =======================================================
     CANOPY COVERAGE
  ======================================================= */

  const canopyCoverage =
    findCanopyCoverage(crownSegmentation);

  const canopyDisplay =
    canopyCoverage !== null &&
    canopyCoverage !== undefined &&
    !Number.isNaN(canopyCoverage)
      ? `${fmt(canopyCoverage)}%`
      : "—";

  /* =======================================================
     RENDER
  ======================================================= */

  return (
    <>
      {/* ===================================================
          HEADER
      =================================================== */}

      <PageHeader
        icon={Gauge}
        title="Forest Intelligence Dashboard"
        description="A unified view of forest imagery analysis, Earth observation and biomass intelligence."
      />

      {/* ===================================================
          SYSTEM STATUS
      =================================================== */}

      <div className="dashboard-status panel">

        <div>
          <div className="panel-kicker">
            SYSTEM STATUS
          </div>

          <h3>
            SylvaSense AI Pipeline
          </h3>

          <p className="muted">
            FastAPI backend connection and analysis services.
          </p>
        </div>

        <div className="dashboard-status-right">

          <StatusDot
            status={backendOnline}
          />

          <span>
            {backendOnline
              ? "Backend online"
              : "Backend offline"}
          </span>

          <code>
            {getApiBase()}
          </code>

        </div>

      </div>

      {/* ===================================================
          MAIN METRICS
      =================================================== */}

      <div className="metrics-grid">

        {/* TREES DETECTED */}

        <MetricCard
          icon={Trees}
          title="Trees Detected"
          value={fmt(treeCount, 0)}
          accent="metric-green"
        />

        {/* TREE CROWNS */}

        <MetricCard
          icon={TreePine}
          title="Tree Crowns"
          value={fmt(crownCount, 0)}
          accent="metric-green"
        />

        {/* ABOVEGROUND BIOMASS */}

        <MetricCard
          icon={BarChart3}
          title="Aboveground Biomass"
          value={fmt(agb)}
          unit="t"
          accent="metric-blue"
        />

        {/* CARBON */}

        <MetricCard
          icon={Leaf}
          title="Carbon"
          value={fmt(carbon)}
          unit="t C"
          accent="metric-green"
        />

        {/* CANOPY COVERAGE */}

        <MetricCard
          icon={Activity}
          title="Canopy Coverage"
          value={canopyDisplay}
          accent="metric-purple"
        />

      </div>

      {/* ===================================================
          TWO COLUMN SECTION
      =================================================== */}

      <div className="two-column">

        {/* =================================================
            LATEST ANALYSIS
        ================================================= */}

        <div className="panel">

          <div className="panel-head">

            <div>

              <h3>
                Latest Analysis
              </h3>

              <p>
                Most recent forest image processed by the AI
                pipeline.
              </p>

            </div>

            {result && (
              <span className="badge success">
                LIVE
              </span>
            )}

          </div>

          {!result ? (

            /* ===============================================
               NO ANALYSIS
            =============================================== */

            <div className="empty-panel">

              <ScanSearch size={30} />

              <strong>
                No analysis available
              </strong>

              <span>
                Upload a forest image to begin analysis.
              </span>

              <button
                className="secondary-btn"
                onClick={() => setPage("image")}
              >
                <ScanSearch size={17} />

                Open Image Analysis
              </button>

            </div>

          ) : (

            /* ===============================================
               ANALYSIS SUMMARY
            =============================================== */

            <div className="analysis-summary">

              {/* TREES */}

              <div className="summary-row">

                <span>
                  Trees detected
                </span>

                <strong>
                  {fmt(treeCount, 0)}
                </strong>

              </div>

              {/* CROWNS */}

              <div className="summary-row">

                <span>
                  Crown segmentation
                </span>

                <strong>
                  {fmt(crownCount, 0)}
                </strong>

              </div>

              {/* AGB */}

              <div className="summary-row">

                <span>
                  Aboveground biomass
                </span>

                <strong>
                  {fmt(agb)} t
                </strong>

              </div>

              {/* CARBON */}

              <div className="summary-row">

                <span>
                  Carbon
                </span>

                <strong>
                  {fmt(carbon)} t C
                </strong>

              </div>

              {/* CO2 */}

              <div className="summary-row">

                <span>
                  CO₂e
                </span>

                <strong>
                  {fmt(co2e)} t
                </strong>

              </div>

              {/* CANOPY */}

              <div className="summary-row">

                <span>
                  Canopy coverage
                </span>

                <strong>
                  {canopyDisplay}
                </strong>

              </div>

              {/* FULL ANALYSIS */}

              <button
                className="secondary-btn full"
                onClick={() => setPage("image")}
              >
                <ScanSearch size={17} />

                View Full Analysis
              </button>

            </div>

          )}

        </div>

        {/* =================================================
            EARTH OBSERVATION MODULES
        ================================================= */}

        <div className="panel">

          <div className="panel-head">

            <div>

              <h3>
                Earth Observation Modules
              </h3>

              <p>
                Remote sensing services connected to FastAPI.
              </p>

            </div>

          </div>

          <div className="module-list">

            {/* SATELLITE */}

            <button
              className="module-item"
              onClick={() => setPage("satellite")}
            >

              <div className="module-icon">
                <Satellite />
              </div>

              <div>

                <strong>
                  Satellite Intelligence
                </strong>

                <span>
                  Sentinel-1, Sentinel-2 and GEDI
                </span>

              </div>

              <span className="module-arrow">
                →
              </span>

            </button>

            {/* CHANGE DETECTION */}

            <button
              className="module-item"
              onClick={() => setPage("change")}
            >

              <div className="module-icon">
                <Layers3 />
              </div>

              <div>

                <strong>
                  Change Detection
                </strong>

                <span>
                  Compare Earth observation periods
                </span>

              </div>

              <span className="module-arrow">
                →
              </span>

            </button>

            {/* AGB FORECAST */}

            <button
              className="module-item"
              onClick={() => setPage("forecast")}
            >

              <div className="module-icon">
                <BrainCircuit />
              </div>

              <div>

                <strong>
                  AGB Forecast
                </strong>

                <span>
                  Biomass projection from backend
                </span>

              </div>

              <span className="module-arrow">
                →
              </span>

            </button>

          </div>

        </div>

      </div>

      {/* ===================================================
          SERVICE AVAILABILITY
      =================================================== */}

      <div className="panel">

        <div className="panel-head">

          <div>

            <h3>
              Service Availability
            </h3>

            <p>
              Current connection state of the SylvaSense
              backend.
            </p>

          </div>

        </div>

        <div className="availability-grid">

          <Availability
            status={backendOnline}
            label="FastAPI"
          />

          <Availability
            status={backendOnline}
            label="Image Analysis"
          />

          <Availability
            status={backendOnline}
            label="Satellite Analysis"
          />

          <Availability
            status={backendOnline}
            label="Earth Engine"
          />

        </div>

      </div>

      {/* ===================================================
          NOTICE
      =================================================== */}

      <div className="notice">

        <BrainCircuit size={19} />

        <span>
          Dashboard values are populated from the latest
          backend analysis response. No frontend-generated
          tree, biomass or carbon values are substituted.
        </span>

      </div>
    </>
  );
}