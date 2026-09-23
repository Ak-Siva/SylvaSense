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

function findCanopyCoverage(data) {
  if (data === null || data === undefined) {
    return null;
  }

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
   SAFE VALUE
========================================================= */

function displayValue(value, digits = 2) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return fmt(Number(value), digits);
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
     TREE DETECTION
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
     CO2e
  ======================================================= */

  const co2e =
    biomass?.total_co2e_tonnes ??
    result?.total_co2e_tonnes ??
    result?.co2e ??
    result?.co2eValue ??
    null;

  /* =======================================================
     CANOPY
  ======================================================= */

  const canopyCoverage =
    findCanopyCoverage(
      crownSegmentation
    );

  const canopyDisplay =
    canopyCoverage !== null &&
    canopyCoverage !== undefined &&
    !Number.isNaN(canopyCoverage)
      ? `${displayValue(
          canopyCoverage,
          2
        )}%`
      : "—";

  /* =======================================================
     ANALYSIS STATUS
  ======================================================= */

  const hasAnalysis =
    result !== null &&
    result !== undefined;

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
        description="Central overview of SylvaSense forest analysis, Earth observation and biomass intelligence."
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
            FastAPI backend and connected forest
            intelligence services.
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

        <MetricCard
          icon={Trees}
          title="Trees Detected"
          value={fmt(treeCount, 0)}
          accent="metric-green"
        />

        <MetricCard
          icon={TreePine}
          title="Tree Crowns"
          value={fmt(crownCount, 0)}
          accent="metric-green"
        />

        <MetricCard
          icon={BarChart3}
          title="Aboveground Biomass"
          value={displayValue(agb)}
          unit="t"
          accent="metric-blue"
        />

        <MetricCard
          icon={Leaf}
          title="Carbon"
          value={displayValue(carbon)}
          unit="t C"
          accent="metric-green"
        />

        <MetricCard
          icon={Activity}
          title="Canopy Coverage"
          value={canopyDisplay}
          accent="metric-purple"
        />

      </div>

      {/* ===================================================
          MAIN TWO COLUMN AREA
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
                Summary of the most recent forest
                image processed by SylvaSense.
              </p>
            </div>

            {hasAnalysis && (
              <span className="badge success">
                ANALYZED
              </span>
            )}

          </div>

          {!hasAnalysis ? (

            <div className="empty-panel">

              <ScanSearch size={32} />

              <strong>
                No analysis available
              </strong>

              <span>
                Upload a forest image to generate
                tree, crown and biomass intelligence.
              </span>

              <button
                className="secondary-btn"
                onClick={() =>
                  setPage("image")
                }
              >
                <ScanSearch size={17} />

                Start Image Analysis
              </button>

            </div>

          ) : (

            <div className="analysis-summary">

              <div className="summary-row">
                <span>
                  Trees detected
                </span>

                <strong>
                  {fmt(treeCount, 0)}
                </strong>
              </div>

              <div className="summary-row">
                <span>
                  Tree crowns
                </span>

                <strong>
                  {fmt(crownCount, 0)}
                </strong>
              </div>

              <div className="summary-row">
                <span>
                  Aboveground biomass
                </span>

                <strong>
                  {displayValue(agb)} t
                </strong>
              </div>

              <div className="summary-row">
                <span>
                  Carbon stored
                </span>

                <strong>
                  {displayValue(carbon)} t C
                </strong>
              </div>

              <div className="summary-row">
                <span>
                  CO₂ equivalent
                </span>

                <strong>
                  {displayValue(co2e)} t
                </strong>
              </div>

              <div className="summary-row">
                <span>
                  Canopy coverage
                </span>

                <strong>
                  {canopyDisplay}
                </strong>
              </div>

              <button
                className="secondary-btn full"
                onClick={() =>
                  setPage("image")
                }
              >
                <ScanSearch size={17} />

                View Full Image Analysis
              </button>

            </div>

          )}

        </div>

        {/* =================================================
            EARTH OBSERVATION
        ================================================= */}

        <div className="panel">

          <div className="panel-head">

            <div>
              <h3>
                Earth Observation
              </h3>

              <p>
                Explore satellite data and
                forecasting separately.
              </p>
            </div>

          </div>

          <div className="module-list">

            {/* SATELLITE */}

            <button
              className="module-item"
              onClick={() =>
                setPage("satellite")
              }
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
              onClick={() =>
                setPage("change")
              }
            >

              <div className="module-icon">
                <Layers3 />
              </div>

              <div>
                <strong>
                  Change Detection
                </strong>

                <span>
                  Compare forest conditions
                  across observation periods
                </span>
              </div>

              <span className="module-arrow">
                →
              </span>

            </button>

            {/* FORECAST */}

            <button
              className="module-item"
              onClick={() =>
                setPage("forecast")
              }
            >

              <div className="module-icon">
                <BrainCircuit />
              </div>

              <div>
                <strong>
                  AGB Forecast
                </strong>

                <span>
                  Project future aboveground biomass
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
              Current connection state of the
              SylvaSense analysis pipeline.
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
          DATA NOTICE
      =================================================== */}

      <div className="notice">

        <BrainCircuit size={19} />

        <span>
          Dashboard metrics are read from the latest
          backend analysis response. SylvaSense does
          not generate replacement tree, biomass,
          carbon or canopy values on the frontend.
        </span>

      </div>
    </>
  );
}