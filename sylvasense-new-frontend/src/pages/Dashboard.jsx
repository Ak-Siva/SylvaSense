import React from "react";

import {
  Activity,
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Layers3,
  Map,
  ScanSearch,
  Satellite,
  TreePine,
  Upload,
} from "lucide-react";

import PageHeader from "../components/PageHeader";
import StatusDot from "../components/StatusDot";

import { getApiBase } from "../services/api";

/* =========================================================
   MODULE CARD
========================================================= */

function ModuleCard({
  icon: Icon,
  title,
  description,
  status,
  statusText,
  onClick,
}) {
  return (
    <button
      className="dashboard-module-card"
      onClick={onClick}
    >
      <div className="dashboard-module-top">

        <div className="dashboard-module-icon">
          <Icon size={23} />
        </div>

        <span
          className={`dashboard-module-status ${
            status ? "online" : "offline"
          }`}
        >
          <span className="dashboard-status-dot" />

          {statusText}
        </span>

      </div>

      <div className="dashboard-module-content">

        <h3>
          {title}
        </h3>

        <p>
          {description}
        </p>

      </div>

      <div className="dashboard-module-footer">

        <span>
          Open module
        </span>

        <ArrowRight size={17} />

      </div>
    </button>
  );
}

/* =========================================================
   PIPELINE STEP
========================================================= */

function PipelineStep({
  number,
  icon: Icon,
  title,
  description,
  active,
  completed,
}) {
  return (
    <div
      className={`pipeline-step ${
        active ? "active" : ""
      } ${completed ? "completed" : ""}`}
    >
      <div className="pipeline-step-number">

        {completed ? (
          <CheckCircle2 size={19} />
        ) : (
          number
        )}

      </div>

      <div className="pipeline-step-icon">
        <Icon size={19} />
      </div>

      <div className="pipeline-step-content">

        <strong>
          {title}
        </strong>

        <span>
          {description}
        </span>

      </div>
    </div>
  );
}

/* =========================================================
   DASHBOARD
========================================================= */

export default function Dashboard({
  result,
  backendOnline,
  setPage,
}) {
  const hasAnalysis =
    result !== null &&
    result !== undefined;

  /*
   * These values are used ONLY to determine whether
   * the pipeline has produced an analysis.
   *
   * They are not displayed as duplicate metrics.
   */

  const hasTreeDetection =
    result?.modules?.tree_detection ||
    result?.tree_count !== undefined ||
    result?.treeCount !== undefined;

  const hasCrownSegmentation =
    result?.modules?.crown_segmentation;

  const hasBiomass =
    result?.modules?.biomass ||
    result?.total_agb_tonnes !== undefined ||
    result?.agb !== undefined;

  /* =======================================================
     CURRENT PIPELINE STATE
  ======================================================= */

  let pipelineStage = "Ready for analysis";

  if (hasAnalysis) {
    pipelineStage = "Analysis completed";
  }

  if (
    hasAnalysis &&
    hasTreeDetection &&
    !hasCrownSegmentation
  ) {
    pipelineStage =
      "Tree detection completed";
  }

  if (
    hasAnalysis &&
    hasCrownSegmentation &&
    !hasBiomass
  ) {
    pipelineStage =
      "Crown segmentation completed";
  }

  /* =======================================================
     RENDER
  ======================================================= */

  return (
    <>
      {/* ===================================================
          HEADER
      =================================================== */}

      <PageHeader
        icon={GaugeIcon}
        title="Forest Intelligence Center"
        description="Monitor your SylvaSense analysis workflow and access every forest intelligence module from one place."
      />

      {/* ===================================================
          SYSTEM OVERVIEW
      =================================================== */}

      <section className="dashboard-hero panel">

        <div className="dashboard-hero-main">

          <div className="dashboard-hero-icon">
            <TreePine size={30} />
          </div>

          <div>

            <div className="panel-kicker">
              SYLVASENSE FOREST INTELLIGENCE
            </div>

            <h2>
              {hasAnalysis
                ? "Forest analysis is available"
                : "Ready for forest analysis"}
            </h2>

            <p>
              {hasAnalysis
                ? "Your latest AI processing is complete. Use the modules below to explore the detailed results."
                : "Upload forest imagery or select a satellite location to begin extracting forest intelligence."}
            </p>

          </div>

        </div>

        <div className="dashboard-hero-status">

          <div className="dashboard-online-row">

            <StatusDot
              status={backendOnline}
            />

            <strong>
              {backendOnline
                ? "System Online"
                : "Backend Offline"}
            </strong>

          </div>

          <code>
            {getApiBase()}
          </code>

        </div>

      </section>

      {/* ===================================================
          PRIMARY ACTIONS
      =================================================== */}

      <section className="dashboard-actions">

        <button
          className="dashboard-primary-action"
          onClick={() => setPage("image")}
        >

          <div className="action-icon">
            <Upload size={23} />
          </div>

          <div>
            <strong>
              Image Analysis
            </strong>

            <span>
              Upload forest imagery and run AI tree,
              crown and biomass analysis.
            </span>
          </div>

          <ArrowRight size={20} />

        </button>

        <button
          className="dashboard-secondary-action"
          onClick={() => setPage("satellite")}
        >

          <div className="action-icon">
            <Satellite size={23} />
          </div>

          <div>
            <strong>
              Explore Satellite Data
            </strong>

            <span>
              Analyze Sentinel and GEDI
              Earth observation data.
            </span>
          </div>

          <ArrowRight size={20} />

        </button>

      </section>

      {/* ===================================================
          INTELLIGENCE MODULES
      =================================================== */}

      <section>

        <div className="dashboard-section-heading">

          <div>

            <div className="panel-kicker">
              INTELLIGENCE MODULES
            </div>

            <h2>
              Explore Forest Intelligence
            </h2>

            <p>
              Each module provides a different view of
              your forest data.
            </p>

          </div>

        </div>

        <div className="dashboard-module-grid">

          <ModuleCard
            icon={ScanSearch}
            title="Image Analysis"
            description="Detect trees, segment crowns and estimate biomass from uploaded forest imagery."
            status={backendOnline}
            statusText={
              backendOnline
                ? "READY"
                : "OFFLINE"
            }
            onClick={() =>
              setPage("image")
            }
          />

          <ModuleCard
            icon={Satellite}
            title="Satellite Intelligence"
            description="Explore Sentinel-1, Sentinel-2, NDVI, SAR and GEDI information for a selected location."
            status={backendOnline}
            statusText={
              backendOnline
                ? "CONNECTED"
                : "OFFLINE"
            }
            onClick={() =>
              setPage("satellite")
            }
          />

          <ModuleCard
            icon={Layers3}
            title="Change Detection"
            description="Compare forest conditions between observation periods and identify vegetation changes."
            status={backendOnline}
            statusText={
              backendOnline
                ? "READY"
                : "OFFLINE"
            }
            onClick={() =>
              setPage("change")
            }
          />

          <ModuleCard
            icon={BrainCircuit}
            title="AGB Forecast"
            description="Explore aboveground biomass projections generated from the forecasting pipeline."
            status={backendOnline}
            statusText={
              backendOnline
                ? "READY"
                : "OFFLINE"
            }
            onClick={() =>
              setPage("forecast")
            }
          />

        </div>

      </section>

      {/* ===================================================
          ANALYSIS WORKFLOW
      =================================================== */}

      <section className="panel dashboard-workflow">

        <div className="panel-head">

          <div>

            <div className="panel-kicker">
              AI ANALYSIS WORKFLOW
            </div>

            <h3>
              Forest Processing Pipeline
            </h3>

            <p>
              The workflow used by SylvaSense to turn
              forest imagery into measurable intelligence.
            </p>

          </div>

          <span
            className={`badge ${
              hasAnalysis
                ? "success"
                : ""
            }`}
          >
            {pipelineStage}
          </span>

        </div>

        <div className="pipeline">

          <PipelineStep
            number="1"
            icon={Upload}
            title="Input Imagery"
            description="Forest image uploaded for analysis"
            completed={hasAnalysis}
            active={!hasAnalysis}
          />

          <PipelineStep
            number="2"
            icon={ScanSearch}
            title="Tree Detection"
            description="AI identifies individual trees"
            completed={
              hasTreeDetection
            }
            active={
              hasAnalysis &&
              !hasTreeDetection
            }
          />

          <PipelineStep
            number="3"
            icon={TreePine}
            title="Crown Segmentation"
            description="Tree crown boundaries are extracted"
            completed={
              !!hasCrownSegmentation
            }
            active={
              hasTreeDetection &&
              !hasCrownSegmentation
            }
          />

          <PipelineStep
            number="4"
            icon={BarChart3}
            title="Biomass Estimation"
            description="Aboveground biomass and carbon are calculated"
            completed={
              !!hasBiomass
            }
            active={
              hasCrownSegmentation &&
              !hasBiomass
            }
          />

          <PipelineStep
            number="5"
            icon={BrainCircuit}
            title="Forest Intelligence"
            description="Results become available across the dashboard"
            completed={
              hasAnalysis &&
              !!hasBiomass
            }
            active={
              hasBiomass &&
              hasAnalysis
            }
          />

        </div>

      </section>

      {/* ===================================================
          ANALYSIS STATE
      =================================================== */}

      <section className="dashboard-status-grid">

        <div className="panel dashboard-status-card">

          <div className="status-card-icon">
            <Activity size={23} />
          </div>

          <div>

            <div className="panel-kicker">
              LATEST ACTIVITY
            </div>

            <h3>
              {hasAnalysis
                ? "Analysis available"
                : "No analysis yet"}
            </h3>

            <p>
              {hasAnalysis
                ? "Your latest forest analysis can be opened from the Image Analysis module."
                : "Run an image analysis to populate your forest intelligence results."}
            </p>

          </div>

          {hasAnalysis && (
            <button
              className="text-action"
              onClick={() =>
                setPage("image")
              }
            >
              View
              <ArrowRight size={16} />
            </button>
          )}

        </div>

        <div className="panel dashboard-status-card">

          <div className="status-card-icon">
            <Map size={23} />
          </div>

          <div>

            <div className="panel-kicker">
              EARTH OBSERVATION
            </div>

            <h3>
              Satellite services
            </h3>

            <p>
              Access Sentinel imagery, spectral
              layers, SAR information and GEDI
              observations.
            </p>

          </div>

          <button
            className="text-action"
            onClick={() =>
              setPage("satellite")
            }
          >
            Explore
            <ArrowRight size={16} />
          </button>

        </div>

      </section>

      {/* ===================================================
          SERVICE STATUS
      =================================================== */}

      <section className="panel dashboard-services">

        <div className="panel-head">

          <div>

            <div className="panel-kicker">
              PLATFORM STATUS
            </div>

            <h3>
              Service Availability
            </h3>

            <p>
              Current state of the connected
              SylvaSense services.
            </p>

          </div>

        </div>

        <div className="dashboard-service-grid">

          <div className="dashboard-service">

            <StatusDot
              status={backendOnline}
            />

            <div>
              <strong>
                FastAPI
              </strong>

              <span>
                Core backend
              </span>
            </div>

            <b>
              {backendOnline
                ? "READY"
                : "OFFLINE"}
            </b>

          </div>

          <div className="dashboard-service">

            <StatusDot
              status={backendOnline}
            />

            <div>
              <strong>
                AI Analysis
              </strong>

              <span>
                Tree and biomass pipeline
              </span>
            </div>

            <b>
              {backendOnline
                ? "READY"
                : "OFFLINE"}
            </b>

          </div>

          <div className="dashboard-service">

            <StatusDot
              status={backendOnline}
            />

            <div>
              <strong>
                Earth Engine
              </strong>

              <span>
                Satellite processing
              </span>
            </div>

            <b>
              {backendOnline
                ? "READY"
                : "OFFLINE"}
            </b>

          </div>

          <div className="dashboard-service">

            <StatusDot
              status={backendOnline}
            />

            <div>
              <strong>
                Remote Sensing
              </strong>

              <span>
                Sentinel and GEDI services
              </span>
            </div>

            <b>
              {backendOnline
                ? "READY"
                : "OFFLINE"}
            </b>

          </div>

        </div>

      </section>

      {/* ===================================================
          FOOTER NOTICE
      =================================================== */}

      <div className="notice">

        <Clock3 size={18} />

        <span>
          The Dashboard is an overview and navigation
          center. Detailed tree detection, crown
          segmentation, biomass, satellite imagery,
          change detection and forecasting results are
          available inside their respective modules.
        </span>

      </div>
    </>
  );
}

/* =========================================================
   HEADER ICON
========================================================= */

function GaugeIcon(props) {
  return <BarChart3 {...props} />;
}