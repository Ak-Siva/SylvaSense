import React, {
  useEffect,
  useState,
} from "react";

import {
  Database,
  Gauge,
  Layers3,
  LineChart,
  Menu,
  RefreshCw,
  Satellite,
  ScanSearch,
  Settings,
  TreePine,
  LoaderCircle,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

import Dashboard from "./pages/Dashboard";
import ImageAnalysis from "./pages/ImageAnalysis";
import SatellitePage from "./pages/Satellite";
import ChangeDetection from "./pages/ChangeDetection";
import Forecast from "./pages/Forecast";

import StatusDot from "./components/StatusDot";

import {
  api,
  getApiBase,
} from "./services/api";

import {
  extractStatusItems,
} from "./utils/normalize";


/* =========================================================
   NAVIGATION
========================================================= */

const navItems = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: Gauge,
  },
  {
    id: "image",
    label: "Image Analysis",
    icon: ScanSearch,
  },
  {
    id: "satellite",
    label: "Satellite Intelligence",
    icon: Satellite,
  },
  {
    id: "change",
    label: "Change Detection",
    icon: Layers3,
  },
  {
    id: "forecast",
    label: "AGB Forecast",
    icon: LineChart,
  },
];


/* =========================================================
   DEFAULT FORECAST STATE
========================================================= */

const DEFAULT_FORECAST_STATE = {
  latitude: 11.0168,
  longitude: 76.9558,

  country: "India",
  stateName: "Tamil Nadu",
  city: "Coimbatore",

  locationMessage: "",

  year: 2023,

  radius: 1000,

  result: null,

  error: "",
};


/* =========================================================
   DEFAULT SATELLITE STATE
========================================================= */

const DEFAULT_SATELLITE_STATE = {
  latitude:
    10.1,

  longitude:
    77.05,

  radius:
    2000,

  locationName:
    "Forest Area",

  startDate:
    "2025-06-01",

  endDate:
    "2026-02-28",

  cloudPct:
    15,

  result:
    null,

  satelliteImage:
    null,

  error:
    "",

  sendingToAnalysis:
    false,
};


/* =========================================================
   APP
========================================================= */

export default function App() {


  /* =======================================================
     CURRENT PAGE
  ======================================================= */

  const [
    page,
    setPage,
  ] = useState(
    "dashboard"
  );


  /* =======================================================
     MOBILE MENU
  ======================================================= */

  const [
    mobileOpen,
    setMobileOpen,
  ] = useState(
    false
  );


  /* =======================================================
     BACKEND
  ======================================================= */

  const [
    backendOnline,
    setBackendOnline,
  ] = useState(
    false
  );


  const [
    backendStatus,
    setBackendStatus,
  ] = useState(
    null
  );


  /* =======================================================
     GLOBAL ANALYSIS RESULT
  ======================================================= */

  const [
    analysis,
    setAnalysis,
  ] = useState(
    null
  );


  /* =======================================================
     GLOBAL ANALYSIS STATE
  ======================================================= */

  const [
    analysisRunning,
    setAnalysisRunning,
  ] = useState(
    false
  );


  const [
    analysisType,
    setAnalysisType,
  ] = useState(
    ""
  );


  const [
    analysisStatus,
    setAnalysisStatus,
  ] = useState(
    ""
  );


  const [
    analysisError,
    setAnalysisError,
  ] = useState(
    ""
  );


  /* =======================================================
     IMAGE STATE
  ======================================================= */

  const [
    selectedFile,
    setSelectedFile,
  ] = useState(
    null
  );


  const [
    selectedFileUrl,
    setSelectedFileUrl,
  ] = useState(
    ""
  );


  /* =======================================================
     FORECAST STATE
  ======================================================= */

  const [
    forecastState,
    setForecastState,
  ] = useState(
    DEFAULT_FORECAST_STATE
  );


  function updateForecastState(
    updates
  ) {

    setForecastState(
      previous => ({
        ...previous,
        ...updates,
      })
    );

  }


  /* =======================================================
     SATELLITE STATE
     
     IMPORTANT:
     This state belongs to App so it survives
     page navigation.
  ======================================================= */

  const [
    satelliteState,
    setSatelliteState,
  ] = useState(
    DEFAULT_SATELLITE_STATE
  );


  /* =======================================================
     BACKEND HEALTH
  ======================================================= */

  async function checkBackend() {

    try {

      const data =
        await api.status();


      setBackendStatus(
        data
      );


      setBackendOnline(
        true
      );

    } catch {

      setBackendOnline(
        false
      );

    }

  }


  useEffect(() => {

    let mounted =
      true;


    async function initialCheck() {

      try {

        const data =
          await api.status();


        if (!mounted) {
          return;
        }


        setBackendStatus(
          data
        );


        setBackendOnline(
          true
        );

      } catch {

        if (!mounted) {
          return;
        }


        setBackendOnline(
          false
        );

      }

    }


    initialCheck();


    const timer =
      setInterval(
        () => {

          if (mounted) {

            checkBackend();

          }

        },
        15000
      );


    return () => {

      mounted =
        false;

      clearInterval(
        timer
      );

    };

  }, []);


  /* =======================================================
     CLEAN IMAGE PREVIEW
  ======================================================= */

  useEffect(() => {

    return () => {

      if (
        selectedFileUrl &&
        selectedFileUrl.startsWith(
          "blob:"
        )
      ) {

        URL.revokeObjectURL(
          selectedFileUrl
        );

      }

    };

  }, [
    selectedFileUrl,
  ]);


  /* =======================================================
     STATUS
  ======================================================= */

  const normalizedStatus =
    extractStatusItems(
      backendStatus
    );


  /* =======================================================
     NAVIGATION
  ======================================================= */

  function navigate(
    nextPage
  ) {

    setPage(
      nextPage
    );

    setMobileOpen(
      false
    );

  }


  /* =======================================================
     SATELLITE IMAGE HANDOFF
  ======================================================= */

  function handleSatelliteImageReady(
    file
  ) {

    if (!file) {
      return;
    }


    console.log(
      "Satellite image received by App:",
      file
    );


    setSelectedFile(
      file
    );


    const previewUrl =
      URL.createObjectURL(
        file
      );


    setSelectedFileUrl(
      previousUrl => {

        if (
          previousUrl &&
          previousUrl.startsWith(
            "blob:"
          )
        ) {

          URL.revokeObjectURL(
            previousUrl
          );

        }


        return previewUrl;

      }
    );


    setAnalysisError(
      ""
    );

  }


  /* =======================================================
     GLOBAL ANALYSIS FUNCTIONS
  ======================================================= */

  function startGlobalAnalysis(
    type,
    message = "Analysis running..."
  ) {

    setAnalysisRunning(
      true
    );


    setAnalysisType(
      type
    );


    setAnalysisStatus(
      message
    );


    setAnalysisError(
      ""
    );

  }


  function updateGlobalAnalysis(
    message
  ) {

    setAnalysisStatus(
      message
    );

  }


  function finishGlobalAnalysis(
    result = null
  ) {

    if (
      result !== null &&
      result !== undefined
    ) {

      setAnalysis(
        result
      );

    }


    setAnalysisRunning(
      false
    );


    setAnalysisStatus(
      "Analysis completed"
    );


    setAnalysisError(
      ""
    );

  }


  function failGlobalAnalysis(
    error
  ) {

    setAnalysisRunning(
      false
    );


    setAnalysisError(
      error?.message ||
      String(error) ||
      "Analysis failed."
    );


    setAnalysisStatus(
      "Analysis failed"
    );

  }


  /* =======================================================
     CLEAR GLOBAL ANALYSIS
  ======================================================= */

  function clearAnalysis() {

    if (
      analysisRunning
    ) {

      return;

    }


    setAnalysis(
      null
    );


    setAnalysisType(
      ""
    );


    setAnalysisStatus(
      ""
    );


    setAnalysisError(
      ""
    );

  }


  /* =======================================================
     CLEAR SELECTED IMAGE
  ======================================================= */

  function clearSelectedImage() {

    setSelectedFile(
      null
    );


    setSelectedFileUrl(
      previousUrl => {

        if (
          previousUrl &&
          previousUrl.startsWith(
            "blob:"
          )
        ) {

          URL.revokeObjectURL(
            previousUrl
          );

        }


        return "";

      }
    );

  }


  /* =======================================================
     RENDER PAGE
  ======================================================= */

  function renderPage() {

    switch (page) {


      /* ===================================================
         IMAGE ANALYSIS
      =================================================== */

      case "image":

        return (

          <ImageAnalysis

            result={
              analysis
            }

            setResult={
              setAnalysis
            }

            setPage={
              navigate
            }

            file={
              selectedFile
            }

            setFile={
              setSelectedFile
            }

            fileUrl={
              selectedFileUrl
            }

            setFileUrl={
              setSelectedFileUrl
            }

            analysisRunning={
              analysisRunning
            }

            analysisType={
              analysisType
            }

            analysisStatus={
              analysisStatus
            }

            analysisError={
              analysisError
            }

            startAnalysis={
              startGlobalAnalysis
            }

            updateAnalysis={
              updateGlobalAnalysis
            }

            finishAnalysis={
              finishGlobalAnalysis
            }

            failAnalysis={
              failGlobalAnalysis
            }

            clearAnalysis={
              clearAnalysis
            }

          />

        );


      /* ===================================================
         SATELLITE INTELLIGENCE
      =================================================== */

      case "satellite":

        return (

          <SatellitePage

            onImageReady={
              handleSatelliteImageReady
            }

            onNavigate={
              navigate
            }


            /* GLOBAL ANALYSIS */

            analysis={
              analysis
            }

            analysisRunning={
              analysisRunning
            }

            analysisType={
              analysisType
            }

            analysisStatus={
              analysisStatus
            }

            analysisError={
              analysisError
            }

            startAnalysis={
              startGlobalAnalysis
            }

            updateAnalysis={
              updateGlobalAnalysis
            }

            finishAnalysis={
              finishGlobalAnalysis
            }

            failAnalysis={
              failGlobalAnalysis
            }

            clearAnalysis={
              clearAnalysis
            }


            /* =================================================
               IMPORTANT FIX
               
               Pass the REAL React state setter.
               
               OLD:
               setSatelliteState={updateSatelliteState}
               
               NEW:
               setSatelliteState={setSatelliteState}
            ================================================= */

            satelliteState={
              satelliteState
            }

            setSatelliteState={
              setSatelliteState
            }

          />

        );


      /* ===================================================
         CHANGE DETECTION
      =================================================== */

      case "change":

        return (

          <ChangeDetection

            analysis={
              analysis
            }

            setAnalysis={
              setAnalysis
            }

            analysisRunning={
              analysisRunning
            }

            analysisType={
              analysisType
            }

            analysisStatus={
              analysisStatus
            }

            analysisError={
              analysisError
            }

            startAnalysis={
              startGlobalAnalysis
            }

            updateAnalysis={
              updateGlobalAnalysis
            }

            finishAnalysis={
              finishGlobalAnalysis
            }

            failAnalysis={
              failGlobalAnalysis
            }

            clearAnalysis={
              clearAnalysis
            }

          />

        );


      /* ===================================================
         AGB FORECAST
      =================================================== */

      case "forecast":

        return (

          <Forecast

            forecastState={
              forecastState
            }

            setForecastState={
              updateForecastState
            }

            analysis={
              analysis
            }

            analysisRunning={
              analysisRunning
            }

            analysisType={
              analysisType
            }

            analysisStatus={
              analysisStatus
            }

            analysisError={
              analysisError
            }

            startAnalysis={
              startGlobalAnalysis
            }

            updateAnalysis={
              updateGlobalAnalysis
            }

            finishAnalysis={
              finishGlobalAnalysis
            }

            failAnalysis={
              failGlobalAnalysis
            }

            clearAnalysis={
              clearAnalysis
            }

          />

        );


      /* ===================================================
         DASHBOARD
      =================================================== */

      case "dashboard":

      default:

        return (

          <Dashboard

            result={
              analysis
            }

            backendOnline={
              backendOnline
            }

            setPage={
              navigate
            }

            analysisRunning={
              analysisRunning
            }

            analysisType={
              analysisType
            }

            analysisStatus={
              analysisStatus
            }

            analysisError={
              analysisError
            }

            clearAnalysis={
              clearAnalysis
            }

          />

        );

    }

  }


  /* =======================================================
     UI
  ======================================================= */

  return (

    <div className="app-shell">


      {/* =================================================
          SIDEBAR
      ================================================= */}

      <aside
        className={
          `sidebar ${
            mobileOpen
              ? "open"
              : ""
          }`
        }
      >

        <div className="brand">

          <div className="brand-mark">

            <TreePine
              size={26}
            />

          </div>


          <div>

            <strong>
              SylvaSense
            </strong>

            <span>
              FOREST INTELLIGENCE
            </span>

          </div>

        </div>


        <nav>

          {navItems.map(
            ({
              id,
              label,
              icon: Icon,
            }) => (

              <button
                key={id}

                className={
                  page === id
                    ? "nav-item active"
                    : "nav-item"
                }

                onClick={() =>
                  navigate(
                    id
                  )
                }
              >

                <Icon
                  size={18}
                />

                <span>
                  {label}
                </span>

              </button>

            )
          )}

        </nav>


        <div className="sidebar-status">

          <div>

            <StatusDot
              status={
                backendOnline
              }
            />

            <span>
              FastAPI
            </span>

            <strong>

              {backendOnline
                ? "ONLINE"
                : "OFFLINE"}

            </strong>

          </div>


          <small>
            {getApiBase()}
          </small>

        </div>

      </aside>


      {/* =================================================
          MOBILE OVERLAY
      ================================================= */}

      {mobileOpen && (

        <button
          className="mobile-overlay"

          onClick={() =>
            setMobileOpen(
              false
            )
          }

          aria-label="Close menu"
        />

      )}


      {/* =================================================
          MAIN CONTENT
      ================================================= */}

      <main className="content">


        {/* =================================================
            TOPBAR
        ================================================= */}

        <header className="topbar">

          <button
            className="menu-btn"

            onClick={() =>
              setMobileOpen(
                true
              )
            }

            aria-label="Open menu"
          >

            <Menu
              size={21}
            />

          </button>


          <div className="topbar-right">

            {analysisRunning && (

              <div
                className="global-analysis-indicator"
              >

                <LoaderCircle
                  size={17}
                  className="spin"
                />

                <span>

                  {analysisType
                    ? `${analysisType}: `
                    : ""}

                  {analysisStatus ||
                    "Analysis running..."}

                </span>

              </div>

            )}


            <div className="connection">

              <StatusDot
                status={
                  backendOnline
                }
              />

              <span>

                {backendOnline
                  ? "SYSTEM ONLINE"
                  : "BACKEND OFFLINE"}

              </span>

            </div>


            <button
              className="icon-btn"

              title="Refresh backend status"

              onClick={
                checkBackend
              }
            >

              <RefreshCw
                size={18}
              />

            </button>


            <button
              className="icon-btn"

              title="Settings"
            >

              <Settings
                size={18}
              />

            </button>

          </div>

        </header>


        {/* =================================================
            GLOBAL ANALYSIS BAR
        ================================================= */}

        {(analysisRunning ||
          analysisStatus ||
          analysisError) && (

          <div
            className={
              analysisError
                ? "global-analysis-bar error"
                : analysisRunning
                ? "global-analysis-bar running"
                : "global-analysis-bar complete"
            }
          >

            {analysisError ? (

              <AlertCircle
                size={18}
              />

            ) : analysisRunning ? (

              <LoaderCircle
                size={18}
                className="spin"
              />

            ) : (

              <CheckCircle2
                size={18}
              />

            )}


            <div>

              <strong>

                {analysisType ||
                  "Analysis"}

              </strong>


              <span>

                {analysisError ||
                  analysisStatus ||
                  "Ready"}

              </span>

            </div>


            {!analysisRunning && (

              <button
                type="button"

                onClick={() => {

                  setAnalysisStatus(
                    ""
                  );

                  setAnalysisType(
                    ""
                  );

                  setAnalysisError(
                    ""
                  );

                }}

                aria-label="Close analysis status"
              >

                ×

              </button>

            )}

          </div>

        )}


        {/* =================================================
            PAGE
        ================================================= */}

        <div className="page">

          {renderPage()}

        </div>


        {/* =================================================
            FOOTER STATUS
        ================================================= */}

        {normalizedStatus.length >
          0 && (

          <div className="footer-status">

            <Database
              size={15}
            />

            <span>
              Backend modules:
            </span>

            <span>

              {normalizedStatus
                .map(
                  item =>
                    `${item.name}: ${item.value}`
                )
                .join(
                  " • "
                )}

            </span>

          </div>

        )}

      </main>

    </div>

  );

}