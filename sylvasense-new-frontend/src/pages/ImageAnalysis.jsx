// src/pages/ImageAnalysis.jsx

import React, { useState } from "react";

import {
  BrainCircuit,
  ChevronRight,
  FileImage,
  RefreshCw,
  ScanSearch,
  Upload,
  X,
  TreePine,
  Leaf,
  Database,
} from "lucide-react";

import { fmt, normalizeAnalysis } from "../utils/normalize";
import { api } from "../services/api";
import * as UTIF from "utif";

/* =========================================================
   FIND NUMERIC VALUE DEEPLY
   ========================================================= */

function findNumericValueDeep(data, keys) {
  if (data === null || data === undefined) {
    return null;
  }

  if (Array.isArray(data)) {
    for (const item of data) {
      const found = findNumericValueDeep(item, keys);

      if (
        found !== null &&
        found !== undefined &&
        !Number.isNaN(found)
      ) {
        return found;
      }
    }

    return null;
  }

  if (typeof data !== "object") {
    return null;
  }

  for (const key of keys) {
    if (
      Object.prototype.hasOwnProperty.call(data, key) &&
      data[key] !== null &&
      data[key] !== undefined
    ) {
      const value = Number(data[key]);

      if (!Number.isNaN(value)) {
        return value;
      }
    }
  }

  for (const value of Object.values(data)) {
    if (value !== null && typeof value === "object") {
      const found = findNumericValueDeep(value, keys);

      if (
        found !== null &&
        found !== undefined &&
        !Number.isNaN(found)
      ) {
        return found;
      }
    }
  }

  return null;
}

/* =========================================================
   FIND CANOPY COVERAGE
   ========================================================= */

function findCanopyCoverage(data) {
  return findNumericValueDeep(data, [
    "canopy_coverage_percent",
    "canopyCoveragePercent",
    "canopy_coverage_percentage",
    "canopyCoveragePercentage",
    "canopy_percent",
    "canopyPercent",
    "coverage_percent",
    "coveragePercent",
    "coverage_percentage",
    "coveragePercentage",
    "canopy_coverage",
    "canopyCoverage",
  ]);
}

/* =========================================================
   FIND AGB
   ========================================================= */

function findAGB(data) {
  return findNumericValueDeep(data, [
    "total_agb_tonnes",
    "total_agb_tons",
    "total_agb_t",
    "totalAgbTonnes",
    "totalAgbTons",
    "totalAgbT",
    "total_agb",
    "totalAgb",
    "agb_tonnes",
    "agb_tons",
    "agb_t",
    "agb",
    "AGB",
    "aboveground_biomass_tonnes",
    "aboveground_biomass_tons",
    "aboveground_biomass_t",
    "abovegroundBiomassTonnes",
    "abovegroundBiomassTons",
    "abovegroundBiomassT",
    "aboveground_biomass",
    "abovegroundBiomass",
    "biomass_tonnes",
    "biomass_tons",
    "biomass_t",
    "biomass",
  ]);
}

/* =========================================================
   FIND CARBON
   ========================================================= */

function findCarbon(data) {
  return findNumericValueDeep(data, [
    "total_carbon_tonnes",
    "total_carbon_tons",
    "total_carbon_t",
    "totalCarbonTonnes",
    "totalCarbonTons",
    "totalCarbonT",
    "total_carbon",
    "totalCarbon",
    "carbon_tonnes",
    "carbon_tons",
    "carbon_t",
    "carbon",
  ]);
}

/* =========================================================
   FIND CO2E
   ========================================================= */

function findCO2e(data) {
  return findNumericValueDeep(data, [
    "total_co2e_tonnes",
    "total_co2e_tons",
    "total_co2e_t",
    "totalCO2eTonnes",
    "totalCO2eTons",
    "totalCO2eT",
    "total_co2e",
    "totalCO2e",
    "co2e_tonnes",
    "co2e_tons",
    "co2e_t",
    "co2e",
    "CO2e",
  ]);
}

/* =========================================================
   FIND TREE COUNT
   ========================================================= */

function findTreeCount(data) {
  return findNumericValueDeep(data, [
    "tree_count",
    "treeCount",
    "trees_detected",
    "treesDetected",
    "detected_trees",
    "detectedTrees",
    "number_of_trees",
    "numberOfTrees",
  ]);
}

/* =========================================================
   FIND CROWN COUNT
   ========================================================= */

function findCrownCount(data) {
  const direct = findNumericValueDeep(data, [
    "crown_count",
    "crownCount",
    "crowns_detected",
    "crownsDetected",
    "segmentation_count",
    "segmentationCount",
  ]);

  if (direct !== null) {
    return direct;
  }

  return null;
}

/* =========================================================
   TIFF TO DATA URL
   ========================================================= */

async function convertTiffToDataUrl(file) {
  const buffer = await file.arrayBuffer();

  const ifds = UTIF.decode(buffer);

  if (!ifds || ifds.length === 0) {
    throw new Error("Unable to read TIFF image.");
  }

  UTIF.decodeImage(buffer, ifds[0]);

  const rgba = UTIF.toRGBA8(ifds[0]);

  const width = ifds[0].width;
  const height = ifds[0].height;

  const canvas = document.createElement("canvas");

  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("Unable to create image preview.");
  }

  const imageData = new ImageData(
    new Uint8ClampedArray(rgba),
    width,
    height
  );

  context.putImageData(imageData, 0, 0);

  return canvas.toDataURL("image/png");
}

/* =========================================================
   IMAGE ANALYSIS
   ========================================================= */

export default function ImageAnalysis({
  result,
  setResult,
  setPage,
  file,
  setFile,
  fileUrl,
  setFileUrl,
  analysisRunning = false,
  analysisType = "",
  analysisStatus = "",
  analysisError = "",
  startAnalysis,
  updateAnalysis,
  finishAnalysis,
  failAnalysis,
}) {
  /* =======================================================
     LOCAL ERROR
  ======================================================= */

  const [localError, setLocalError] = useState("");

  /* =======================================================
     SELECT IMAGE
  ======================================================= */

  async function chooseFile(nextFile) {
    if (!nextFile) {
      return;
    }

    const isImage =
      nextFile.type.startsWith("image/");

    const isSupportedExtension =
      /\.(jpg|jpeg|png|tif|tiff)$/i.test(
        nextFile.name
      );

    if (!isImage && !isSupportedExtension) {
      setLocalError(
        "Please select a JPG, PNG or TIFF image."
      );
      return;
    }

    setLocalError("");

    if (
      fileUrl &&
      fileUrl.startsWith("blob:")
    ) {
      URL.revokeObjectURL(fileUrl);
    }

    try {
      let nextUrl = "";

      const isTiff =
        /\.(tif|tiff)$/i.test(nextFile.name);

      if (isTiff) {
        nextUrl =
          await convertTiffToDataUrl(nextFile);
      } else {
        nextUrl =
          URL.createObjectURL(nextFile);
      }

      setResult(null);
      setFile(nextFile);
      setFileUrl(nextUrl);
    } catch (err) {
      console.error(
        "Image preview error:",
        err
      );

      setResult(null);
      setFile(nextFile);
      setFileUrl("");

      setLocalError(
        "The image was selected, but its preview could not be generated. You can still try the analysis."
      );
    }
  }

  /* =======================================================
     ANALYZE IMAGE
  ======================================================= */

  async function analyze() {
    if (!file) {
      setLocalError(
        "Please select an image first."
      );
      return;
    }

    if (analysisRunning) {
      return;
    }

    setLocalError("");

    startAnalysis(
      "Image Analysis",
      "Uploading image and running AI analysis..."
    );

    try {
      updateAnalysis(
        "Sending image to FastAPI..."
      );

      const raw =
        await api.imageAnalyze(file);

      console.log(
        "SYLVASENSE RAW IMAGE ANALYSIS:",
        raw
      );

      updateAnalysis(
        "Processing tree, crown and biomass results..."
      );

      const normalized =
        normalizeAnalysis(raw);

      console.log(
        "SYLVASENSE NORMALIZED IMAGE ANALYSIS:",
        normalized
      );

      const finalResult = {
        ...normalized,
        raw,
      };

      finishAnalysis(finalResult);
    } catch (err) {
      console.error(
        "Image analysis error:",
        err
      );

      failAnalysis(err);
    }
  }

  /* =======================================================
     RESULT SOURCE
  ======================================================= */

  const rawSource =
    result?.raw ||
    result ||
    null;

  /* =======================================================
     TREE COUNT
  ======================================================= */

  const treeCount =
    findTreeCount(result) ??
    findTreeCount(rawSource) ??
    0;

  /* =======================================================
     CROWN SEGMENTATION
  ======================================================= */

  const crownSegmentation =
    rawSource?.modules?.crown_segmentation ??
    result?.modules?.crown_segmentation ??
    null;

  /* =======================================================
     CROWN COUNT
  ======================================================= */

  const crownCount =
    findCrownCount(result) ??
    findCrownCount(rawSource) ??
    (
      Array.isArray(crownSegmentation)
        ? crownSegmentation.length
        : 0
    );

  /* =======================================================
     AGB
  ======================================================= */

  const agb =
    findAGB(result) ??
    findAGB(rawSource);

  /* =======================================================
     CARBON
  ======================================================= */

  const carbon =
    findCarbon(result) ??
    findCarbon(rawSource);

  /* =======================================================
     CO2 EQUIVALENT
  ======================================================= */

  const co2e =
    findCO2e(result) ??
    findCO2e(rawSource);

  /* =======================================================
     CANOPY COVERAGE

     Backend confirmed value:
     canopy_coverage_percent = 38.364375
  ======================================================= */

  const canopyCoverage =
    findCanopyCoverage(result) ??
    findCanopyCoverage(rawSource);

  const canopyDisplay =
    canopyCoverage !== null &&
    canopyCoverage !== undefined &&
    !Number.isNaN(Number(canopyCoverage))
      ? `${fmt(Number(canopyCoverage), 2)}%`
      : "—";

  /* =======================================================
     DEBUG

     This makes it very easy to verify exactly what the
     frontend is receiving.
  ======================================================= */

  if (result) {
    console.log(
      "SYLVASENSE FINAL DISPLAY VALUES:",
      {
        treeCount,
        crownCount,
        agb,
        carbon,
        co2e,
        canopyCoverage,
      }
    );
  }

  /* =======================================================
     RESULT STATE
  ======================================================= */

  const hasResult =
    Boolean(result);

  /* =======================================================
     RENDER
  ======================================================= */

  return (
    <main className="dashboard">

      {/* =================================================
          HEADER
      ================================================= */}

      <div className="dashboard-header">

        <div>

          <div className="dashboard-title">

            <ScanSearch size={30} />

            <h1>
              Image Analysis
            </h1>

          </div>

          <p>
            Upload forest imagery and run the
            SYLVASENSE AI analysis pipeline.
          </p>

        </div>

        {analysisRunning &&
          analysisType === "Image Analysis" && (

            <div
              className="badge"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "7px",
                padding: "9px 13px",
              }}
            >

              <RefreshCw
                size={16}
                className="spin"
              />

              Analyzing...

            </div>

        )}

      </div>

      {/* =================================================
          ERROR
      ================================================= */}

      {(localError || analysisError) && (

        <div
          className="error-box"
          style={{
            marginBottom: "18px",
          }}
        >

          <X size={18} />

          <span>
            {localError || analysisError}
          </span>

        </div>

      )}

      {/* =================================================
          UPLOAD + IMAGE PREVIEW
      ================================================= */}

      <div
        className="dashboard-grid"
        style={{
          gridTemplateColumns:
            "320px minmax(0, 1fr)",
          gap: "18px",
          alignItems: "start",
        }}
      >

        {/* =================================================
            LEFT — UPLOAD
        ================================================= */}

        <div
          className="panel"
          style={{
            padding: "18px",
          }}
        >

          <div className="panel-head">

            <div>

              <h3>
                Forest Imagery
              </h3>

              <p>
                Upload an image for AI analysis.
              </p>

            </div>

            <Upload size={21} />

          </div>

          {/* UPLOAD AREA */}

          <div
            className="drop-zone"
            style={{
              padding: "28px 16px",
              minHeight: "220px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              textAlign: "center",
              borderRadius: "12px",
            }}
            onDragOver={(event) =>
              event.preventDefault()
            }
            onDrop={(event) => {
              event.preventDefault();

              chooseFile(
                event.dataTransfer.files?.[0]
              );
            }}
          >

            <div
              style={{
                width: "52px",
                height: "52px",
                borderRadius: "12px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background:
                  "rgba(74,211,132,0.10)",
                border:
                  "1px solid rgba(74,211,132,0.20)",
                marginBottom: "12px",
              }}
            >

              <Upload size={25} />

            </div>

            <h3
              style={{
                margin: 0,
              }}
            >
              Upload forest imagery
            </h3>

            <p
              style={{
                margin: "6px 0 14px",
                fontSize: "13px",
                opacity: 0.7,
              }}
            >
              JPG, PNG or TIFF
            </p>

            <label
              className="secondary-btn file-btn"
              style={{
                justifyContent: "center",
                cursor:
                  analysisRunning
                    ? "not-allowed"
                    : "pointer",
              }}
            >

              Select Image

              <input
                type="file"
                accept=".jpg,.jpeg,.png,.tif,.tiff,image/jpeg,image/png,image/tiff"
                disabled={analysisRunning}
                onChange={(event) =>
                  chooseFile(
                    event.target.files?.[0]
                  )
                }
                style={{
                  display: "none",
                }}
              />

            </label>

            {file && (

              <div
                style={{
                  marginTop: "13px",
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: "8px",
                  background:
                    "rgba(31,126,76,0.08)",
                  border:
                    "1px solid rgba(74,211,132,0.15)",
                  fontSize: "12px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >

                <FileImage
                  size={14}
                  style={{
                    verticalAlign: "middle",
                    marginRight: "6px",
                  }}
                />

                {file.name}

              </div>

            )}

          </div>

          {/* ANALYZE BUTTON */}

          <button
            className="primary-btn"
            style={{
              width: "100%",
              marginTop: "14px",
              justifyContent: "center",
            }}
            disabled={
              !file ||
              analysisRunning
            }
            onClick={analyze}
          >

            {analysisRunning ? (

              <>
                <RefreshCw
                  size={18}
                  className="spin"
                />

                Analyzing...
              </>

            ) : (

              <>
                <BrainCircuit size={18} />

                Run Complete Analysis
              </>

            )}

          </button>

        </div>

        {/* =================================================
            RIGHT — IMAGE PREVIEW
        ================================================= */}

        <div
          className="panel"
          style={{
            padding: "12px",
          }}
        >

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "4px 6px 10px",
            }}
          >

            <div>

              <h3
                style={{
                  margin: 0,
                }}
              >
                Image Preview
              </h3>

              <p
                style={{
                  margin: "4px 0 0",
                  fontSize: "13px",
                  opacity: 0.7,
                }}
              >
                {file
                  ? file.name
                  : "Selected forest imagery appears here."}
              </p>

            </div>

            <FileImage size={21} />

          </div>

          {/* IMAGE CONTAINER */}

          <div
            style={{
              width: "100%",
              minHeight: "360px",
              maxHeight: "520px",
              borderRadius: "12px",
              overflow: "hidden",
              background: "#07110b",
              border:
                "1px solid rgba(255,255,255,0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxSizing: "border-box",
              padding: "12px",
            }}
          >

            {fileUrl ? (

              <img
                src={fileUrl}
                alt={
                  file?.name ||
                  "Uploaded forest image"
                }
                title={
                  file?.name ||
                  "Forest image"
                }
                style={{
                  display: "block",
                  maxWidth: "100%",
                  maxHeight: "490px",
                  width: "auto",
                  height: "auto",
                  objectFit: "contain",
                  objectPosition: "center",
                  margin: "0 auto",
                  borderRadius: "8px",
                }}
              />

            ) : (

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "10px",
                  opacity: 0.55,
                  textAlign: "center",
                  padding: "30px",
                }}
              >

                <FileImage size={42} />

                <span>
                  Select a forest image
                  to preview it here.
                </span>

              </div>

            )}

          </div>

        </div>

      </div>

      {/* =================================================
          ANALYSIS STATUS
      ================================================= */}

      {analysisRunning &&
        analysisType === "Image Analysis" && (

          <div
            className="panel"
            style={{
              marginTop: "18px",
              border:
                "1px solid rgba(74,211,132,0.25)",
              background:
                "rgba(31,126,76,0.08)",
            }}
          >

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
              }}
            >

              <RefreshCw
                size={25}
                className="spin"
              />

              <div
                style={{
                  flex: 1,
                }}
              >

                <strong>
                  Analysis in progress
                </strong>

                <p
                  style={{
                    margin: "5px 0 0",
                  }}
                >
                  {analysisStatus ||
                    "FastAPI is processing the image..."}
                </p>

              </div>

              <span className="badge">
                RUNNING
              </span>

            </div>

            <div
              style={{
                marginTop: "15px",
                height: "6px",
                width: "100%",
                borderRadius: "999px",
                overflow: "hidden",
                background:
                  "rgba(255,255,255,0.08)",
              }}
            >

              <div
                style={{
                  width: "55%",
                  height: "100%",
                  borderRadius: "999px",
                  animation:
                    "pulse 1.5s ease-in-out infinite",
                }}
              />

            </div>

            <small
              style={{
                display: "block",
                marginTop: "10px",
                opacity: 0.65,
              }}
            >
              You can switch to another page.
              The analysis will continue in the
              background.
            </small>

          </div>

        )}

      {/* =================================================
          RESULTS
      ================================================= */}

      <div
        className="panel"
        style={{
          marginTop: "18px",
        }}
      >

        <div className="panel-head">

          <div>

            <h3>
              Analysis Results
            </h3>

            <p>
              AI-derived forest measurements from
              the FastAPI backend.
            </p>

          </div>

          {hasResult && (

            <span className="badge success">
              LIVE
            </span>

          )}

        </div>

        {/* RESULT CARDS */}

        <div
          className="metrics-grid"
          style={{
            marginTop: "14px",
          }}
        >

          {/* TREE COUNT */}

          <div className="metric-card">

            <div className="metric-icon">
              <TreePine size={20} />
            </div>

            <div className="metric-label">
              Tree Detection
            </div>

            <div className="metric-value">
              {fmt(treeCount, 0)}
            </div>

          </div>

          {/* CROWN */}

          <div className="metric-card">

            <div className="metric-icon">
              <Leaf size={20} />
            </div>

            <div className="metric-label">
              Crown Segmentation
            </div>

            <div className="metric-value">
              {fmt(crownCount, 0)}
            </div>

          </div>

          {/* AGB */}

          <div className="metric-card">

            <div className="metric-icon">
              <TreePine size={20} />
            </div>

            <div className="metric-label">
              Aboveground Biomass
            </div>

            <div className="metric-value">

              {agb !== null &&
              agb !== undefined &&
              !Number.isNaN(Number(agb))
                ? `${fmt(Number(agb), 2)} t`
                : "—"}

            </div>

          </div>

          {/* CARBON */}

          <div className="metric-card">

            <div className="metric-icon">
              <Leaf size={20} />
            </div>

            <div className="metric-label">
              Carbon
            </div>

            <div className="metric-value">

              {carbon !== null &&
              carbon !== undefined &&
              !Number.isNaN(Number(carbon))
                ? `${fmt(Number(carbon), 2)} t C`
                : "—"}

            </div>

          </div>

          {/* CO2 */}

          <div className="metric-card">

            <div className="metric-icon">
              <Database size={20} />
            </div>

            <div className="metric-label">
              CO₂e
            </div>

            <div className="metric-value">

              {co2e !== null &&
              co2e !== undefined &&
              !Number.isNaN(Number(co2e))
                ? `${fmt(Number(co2e), 2)} t`
                : "—"}

            </div>

          </div>

          {/* CANOPY */}

          <div className="metric-card">

            <div className="metric-icon">
              <Leaf size={20} />
            </div>

            <div className="metric-label">
              Canopy Coverage
            </div>

            <div className="metric-value">
              {canopyDisplay}
            </div>

          </div>

        </div>

        {/* DASHBOARD */}

        <button
          className="secondary-btn"
          style={{
            width: "100%",
            justifyContent: "center",
            marginTop: "16px",
          }}
          onClick={() =>
            setPage("dashboard")
          }
        >

          <ChevronRight size={17} />

          View Dashboard

        </button>

      </div>

      {/* =================================================
          RAW BACKEND RESPONSE
      ================================================= */}

      {result && (

        <div
          className="panel"
          style={{
            marginTop: "18px",
          }}
        >

          <div className="panel-head">

            <div>

              <h3>
                Backend Analysis Data
              </h3>

              <p>
                Complete response returned by FastAPI.
              </p>

            </div>

            <span className="badge success">
              API
            </span>

          </div>

          <pre
            className="json-view"
            style={{
              marginTop: "14px",
              maxHeight: "420px",
              overflow: "auto",
              borderRadius: "10px",
              padding: "15px",
              fontSize: "12px",
              lineHeight: 1.5,
            }}
          >
            {JSON.stringify(
              result.raw || result,
              null,
              2
            )}
          </pre>

        </div>

      )}

    </main>
  );
}