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
      type="button"
      className="dashboard-card module-card"
      onClick={onClick}
    >
      <div className="module-card-icon">
        <Icon size={22} />
      </div>

      <div className="module-card-content">
        <div className="module-card-header">
          <h3>{title}</h3>

          <span
            className={`status-badge ${
              status ? "online" : "offline"
            }`}
          >
            <span className="status-badge-dot" />
            {statusText}
          </span>
        </div>

        <p>{description}</p>

        <div className="module-card-action">
          <span>Open module</span>
          <ArrowRight size={16} />
        </div>
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
  completed,
  active,
}) {
  return (
    <div
      className={`pipeline-step ${
        completed ? "completed" : ""
      } ${active ? "active" : ""}`}
    >
      <div className="pipeline-step-number">
        {completed ? (
          <CheckCircle2 size={18} />
        ) : (
          number
        )}
      </div>

      <div className="pipeline-step-icon">
        <Icon size={18} />
      </div>

      <div className="pipeline-step-content">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
    </div>
  );
}

/* =========================================================
   SERVICE STATUS
========================================================= */

function ServiceStatus({
  status,
  title,
  description,
}) {
  return (
    <div className="dashboard-service">
      <StatusDot status={status} />

      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>

      <b>
        {status ? "READY" : "OFFLINE"}
      </b>
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

  const hasTreeDetection =
    result?.modules?.tree_detection ||
    result?.tree_count !== undefined ||
    result?.treeCount !== undefined;

  const hasCrownSegmentation =
    result?.modules?.crown_segmentation ||
    result?.crown_segmentation !== undefined;

  const hasBiomass =
    result?.modules?.biomass ||
    result?.total_agb_tonnes !== undefined ||
    result?.agb !== undefined;

  /* =======================================================
     PIPELINE STATUS
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
    pipelineStage = "Tree detection completed";
  }

  if (
    hasAnalysis &&
    hasCrownSegmentation &&
    !hasBiomass
  ) {
    pipelineStage = "Crown segmentation completed";
  }

  /* =======================================================
     RENDER
  ======================================================= */

  return (
    <div className="dashboard">

      {/* ===================================================
          HEADER
      =================================================== */}

      <PageHeader
        icon={BarChart3}
        title="Forest Intelligence Center"
        description="Monitor your SylvaSense workflow and access forest intelligence modules from one place."
      />

      {/* ===================================================
          SYSTEM OVERVIEW
      =================================================== */}

      <section className="dashboard-card dashboard-overview">

        <div className="dashboard-overview-main">

          <div className="dashboard-overview-icon">
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
                ? "Your latest analysis is ready. Open the appropriate module to explore detailed results."
                : "Start an image or satellite analysis to generate forest intelligence."}
            </p>
          </div>

        </div>

        <div className="dashboard-overview-status">

          <div className="status-row">

            <StatusDot status={backendOnline} />

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

      <section className="dashboard-grid">

        <button
          type="button"
          className="dashboard-card dashboard-action-card"
          onClick={() => setPage("image")}
        >

          <div className="dashboard-action-icon">
            <Upload size={23} />
          </div>

          <div className="dashboard-action-content">

            <h3>
              Image Analysis
            </h3>

            <p>
              Upload forest imagery and run the AI
              tree detection, crown segmentation
              and biomass pipeline.
            </p>

            <span className="dashboard-action-link">
              Start analysis
              <ArrowRight size={17} />
            </span>

          </div>

        </button>

        <button
          type="button"
          className="dashboard-card dashboard-action-card"
          onClick={() => setPage("satellite")}
        >

          <div className="dashboard-action-icon">
            <Satellite size={23} />
          </div>

          <div className="dashboard-action-content">

            <h3>
              Satellite Intelligence
            </h3>

            <p>
              Explore satellite-based forest information
              including Sentinel imagery, spectral data,
              SAR and GEDI observations.
            </p>

            <span className="dashboard-action-link">
              Explore satellite data
              <ArrowRight size={17} />
            </span>

          </div>

        </button>

      </section>

      {/* ===================================================
          INTELLIGENCE MODULES
      =================================================== */}

      <section className="dashboard-section">

        <div className="dashboard-section-heading">

          <div>

            <div className="panel-kicker">
              INTELLIGENCE MODULES
            </div>

            <h2>
              Forest Intelligence
            </h2>

            <p>
              Access each SylvaSense analysis module
              without duplicating its detailed results here.
            </p>

          </div>

        </div>

        <div className="dashboard-grid">

          <ModuleCard
            icon={ScanSearch}
            title="Image Analysis"
            description="Run and inspect tree detection, crown segmentation and biomass analysis."
            status={backendOnline}
            statusText={
              backendOnline
                ? "READY"
                : "OFFLINE"
            }
            onClick={() => setPage("image")}
          />

          <ModuleCard
            icon={Satellite}
            title="Satellite Intelligence"
            description="Explore Sentinel-1, Sentinel-2, NDVI, SAR and GEDI information."
            status={backendOnline}
            statusText={
              backendOnline
                ? "CONNECTED"
                : "OFFLINE"
            }
            onClick={() => setPage("satellite")}
          />

          <ModuleCard
            icon={Layers3}
            title="Change Detection"
            description="Compare forest observations and identify changes in vegetation conditions."
            status={backendOnline}
            statusText={
              backendOnline
                ? "READY"
                : "OFFLINE"
            }
            onClick={() => setPage("change")}
          />

          <ModuleCard
            icon={BrainCircuit}
            title="AGB Forecast"
            description="Explore aboveground biomass forecasting generated by the SylvaSense pipeline."
            status={backendOnline}
            statusText={
              backendOnline
                ? "READY"
                : "OFFLINE"
            }
            onClick={() => setPage("forecast")}
          />

        </div>

      </section>

      {/* ===================================================
          AI PIPELINE
      =================================================== */}

      <section className="dashboard-card dashboard-workflow">

        <div className="panel-head">

          <div>

            <div className="panel-kicker">
              AI ANALYSIS WORKFLOW
            </div>

            <h3>
              Forest Processing Pipeline
            </h3>

            <p>
              High-level view of how SylvaSense
              processes forest imagery.
            </p>

          </div>

          <span
            className={`badge ${
              hasAnalysis ? "success" : ""
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
            description="Forest imagery is provided for analysis."
            completed={hasAnalysis}
            active={!hasAnalysis}
          />

          <PipelineStep
            number="2"
            icon={ScanSearch}
            title="Tree Detection"
            description="AI identifies individual trees."
            completed={hasTreeDetection}
            active={
              hasAnalysis &&
              !hasTreeDetection
            }
          />

          <PipelineStep
            number="3"
            icon={TreePine}
            title="Crown Segmentation"
            description="Tree crown boundaries are extracted."
            completed={hasCrownSegmentation}
            active={
              hasTreeDetection &&
              !hasCrownSegmentation
            }
          />

          <PipelineStep
            number="4"
            icon={BarChart3}
            title="Biomass Estimation"
            description="Aboveground biomass is estimated."
            completed={hasBiomass}
            active={
              hasCrownSegmentation &&
              !hasBiomass
            }
          />

          <PipelineStep
            number="5"
            icon={BrainCircuit}
            title="Forest Intelligence"
            description="Processed information becomes available in the modules."
            completed={
              hasAnalysis &&
              hasBiomass
            }
            active={
              hasBiomass &&
              hasAnalysis
            }
          />

        </div>

      </section>

      {/* ===================================================
          CURRENT STATE
      =================================================== */}

      <section className="dashboard-grid">

        <div className="dashboard-card dashboard-status-card">

          <div className="dashboard-status-icon">
            <Activity size={22} />
          </div>

          <div className="dashboard-status-content">

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
                ? "Detailed analysis results are available inside the Image Analysis module."
                : "Run an image analysis to generate forest intelligence."}
            </p>

            <button
              type="button"
              className="text-action"
              onClick={() => setPage("image")}
            >
              {hasAnalysis
                ? "View analysis"
                : "Start analysis"}

              <ArrowRight size={16} />
            </button>

          </div>

        </div>

        <div className="dashboard-card dashboard-status-card">

          <div className="dashboard-status-icon">
            <Map size={22} />
          </div>

          <div className="dashboard-status-content">

            <div className="panel-kicker">
              EARTH OBSERVATION
            </div>

            <h3>
              Satellite services
            </h3>

            <p>
              Open Satellite Intelligence for
              location-based Earth observation data.
            </p>

            <button
              type="button"
              className="text-action"
              onClick={() => setPage("satellite")}
            >
              Explore
              <ArrowRight size={16} />
            </button>

          </div>

        </div>

      </section>

      {/* ===================================================
          PLATFORM STATUS
      =================================================== */}

      <section className="dashboard-card dashboard-services">

        <div className="panel-head">

          <div>

            <div className="panel-kicker">
              PLATFORM STATUS
            </div>

            <h3>
              Service Availability
            </h3>

            <p>
              Current status of the services connected
              to SylvaSense.
            </p>

          </div>

        </div>

        <div className="dashboard-grid service-grid">

          <ServiceStatus
            status={backendOnline}
            title="FastAPI"
            description="Core backend"
          />

          <ServiceStatus
            status={backendOnline}
            title="AI Analysis"
            description="Tree and biomass pipeline"
          />

          <ServiceStatus
            status={backendOnline}
            title="Earth Engine"
            description="Satellite processing"
          />

          <ServiceStatus
            status={backendOnline}
            title="Remote Sensing"
            description="Sentinel and GEDI services"
          />

        </div>

      </section>

      {/* ===================================================
          NOTICE
      =================================================== */}

      <div className="notice">

        <Clock3 size={18} />

        <span>
          The Dashboard provides a high-level overview
          and navigation center. Detailed analysis,
          satellite information, change detection and
          forecasting results remain inside their
          respective modules.
        </span>

      </div>

    </div>
  );
}