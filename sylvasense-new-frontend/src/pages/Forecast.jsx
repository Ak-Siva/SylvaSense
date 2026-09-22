import React, {
  useMemo,
  useState,
  useEffect,
} from "react";

import {
  BarChart3,
  CheckCircle,
  Leaf,
  RefreshCw,
  Satellite,
  TrendingDown,
  TrendingUp,
  X,
  Search,
  MapPin,
  AlertTriangle,
} from "lucide-react";

import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Circle,
  useMap,
  useMapEvents,
} from "react-leaflet";

import {
  LineChart,
  Line,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import PageHeader from "../components/PageHeader";
import { api } from "../services/api";
import { fmt } from "../utils/normalize";

import "leaflet/dist/leaflet.css";


/* =========================================================
   DEFAULT LOCATION
========================================================= */

const DEFAULT_LAT = 11.0168;
const DEFAULT_LNG = 76.9558;


/* =========================================================
   GEDI YEARS
========================================================= */

const YEARS = [
  2019,
  2020,
  2021,
  2022,
  2023,
  2024,
  2025,
];


/* =========================================================
   MAP CONFIGURATION
========================================================= */

const MAP_MIN_ZOOM = 3;
const MAP_NATIVE_ZOOM = 19;
const MAP_MAX_ZOOM = 25;


/* =========================================================
   MAP CENTER
========================================================= */

function MapCenter({
  latitude,
  longitude,
}) {

  const map = useMap();

  useEffect(() => {

    const lat =
      Number(latitude);

    const lng =
      Number(longitude);

    if (
      Number.isFinite(lat) &&
      Number.isFinite(lng)
    ) {

      map.setView(
        [lat, lng],
        Math.max(
          map.getZoom(),
          15
        ),
        {
          animate: true,
        }
      );

    }

  }, [
    latitude,
    longitude,
    map,
  ]);

  return null;
}


/* =========================================================
   MAP LOCATION PICKER
========================================================= */

function LocationPicker({
  latitude,
  longitude,
  onSelect,
}) {

  useMapEvents({

    click(event) {

      const lat =
        Number(
          event.latlng.lat.toFixed(6)
        );

      const lng =
        Number(
          event.latlng.lng.toFixed(6)
        );

      onSelect(
        lat,
        lng
      );

    },

  });

  return (

    <CircleMarker
      center={[
        Number(latitude),
        Number(longitude),
      ]}
      radius={9}
      pathOptions={{
        weight: 3,
      }}
    />

  );
}


/* =========================================================
   NORMALIZE LOCATION TEXT
========================================================= */

function normalizeLocationText(
  value
) {

  return String(
    value || ""
  )
    .toLowerCase()
    .normalize(
      "NFD"
    )
    .replace(
      /[\u0300-\u036f]/g,
      ""
    )
    .replace(
      /[^a-z0-9\s]/g,
      " "
    )
    .replace(
      /\s+/g,
      " "
    )
    .trim();

}


/* =========================================================
   GET PLACE NAMES
========================================================= */

function getPlaceNames(
  result
) {

  const address =
    result?.address || {};

  return [
    result?.name,
    result?.namedetails?.name,

    address.city,
    address.town,
    address.municipality,
    address.village,
    address.hamlet,
    address.suburb,
    address.county,
    address.state_district,

  ]
    .filter(Boolean)
    .map(
      normalizeLocationText
    );

}


/* =========================================================
   SCORE LOCATION RESULT
========================================================= */

function scoreLocationResult(
  result,
  cityInput,
  stateInput,
  countryInput
) {

  const address =
    result?.address || {};

  const requestedPlace =
    normalizeLocationText(
      cityInput
    );

  const requestedState =
    normalizeLocationText(
      stateInput
    );

  const requestedCountry =
    normalizeLocationText(
      countryInput
    );

  const resultCountry =
    normalizeLocationText(
      address.country
    );

  const resultState =
    normalizeLocationText(
      address.state
    );

  const placeNames =
    getPlaceNames(
      result
    );

  let score = 0;

  if (
    requestedPlace &&
    placeNames.includes(
      requestedPlace
    )
  ) {

    score += 150;

  }

  const resultName =
    normalizeLocationText(
      result?.name
    );

  if (
    requestedPlace &&
    resultName ===
      requestedPlace
  ) {

    score += 100;

  }

  if (
    requestedPlace &&
    placeNames.some(
      name =>
        name.includes(
          requestedPlace
        ) ||
        requestedPlace.includes(
          name
        )
    )
  ) {

    score += 45;

  }

  if (
    requestedState &&
    resultState ===
      requestedState
  ) {

    score += 70;

  } else if (
    requestedState &&
    resultState.includes(
      requestedState
    )
  ) {

    score += 30;

  }

  if (
    requestedCountry &&
    resultCountry ===
      requestedCountry
  ) {

    score += 50;

  } else if (
    requestedCountry &&
    resultCountry.includes(
      requestedCountry
    )
  ) {

    score += 20;

  }

  const type =
    String(
      result?.type || ""
    ).toLowerCase();

  const category =
    String(
      result?.category || ""
    ).toLowerCase();

  const preferredTypes = [
    "city",
    "town",
    "municipality",
    "village",
    "suburb",
    "hamlet",
  ];

  if (
    preferredTypes.includes(
      type
    )
  ) {

    score += 30;

  }

  if (
    category === "place"
  ) {

    score += 20;

  }

  if (
    type ===
      "administrative"
  ) {

    score += 10;

  }

  const lessPreferredTypes = [
    "road",
    "street",
    "building",
    "house",
    "parking",
    "shop",
    "restaurant",
    "school",
    "bus_stop",
    "railway",
  ];

  if (
    lessPreferredTypes.includes(
      type
    )
  ) {

    score -= 100;

  }

  return score;
}


/* =========================================================
   STYLES
========================================================= */

const inputStyle = {
  width: "100%",
  minHeight: "42px",
  boxSizing: "border-box",
};

const labelStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "7px",
  width: "100%",
  minWidth: 0,
};

const controlPanelStyle = {
  width: "100%",
  boxSizing: "border-box",
  padding: "20px",
  borderRadius: "14px",
};


/* =========================================================
   FORECAST PAGE
========================================================= */

export default function Forecast({
  forecastState,
  setForecastState,

  /*
   * GLOBAL ANALYSIS STATE
   *
   * These come from App.jsx.
   * They do NOT disappear when Forecast.jsx
   * is unmounted during page switching.
   */
  analysisRunning,
  analysisType,
  analysisStatus,
  analysisError,

  /*
   * GLOBAL ANALYSIS FUNCTIONS
   */
  startAnalysis,
  updateAnalysis,
  finishAnalysis,
  failAnalysis,
}) {

  /* =======================================================
     PERSISTENT STATE FROM APP
  ======================================================= */

  const {
    latitude = DEFAULT_LAT,
    longitude = DEFAULT_LNG,

    country = "India",

    stateName = "Tamil Nadu",

    city = "Coimbatore",

    locationMessage = "",

    year = 2023,

    radius = 1000,

    result = null,

    error = "",
  } = forecastState || {};


  /* =======================================================
     GLOBAL FORECAST ANALYSIS STATE
  ======================================================= */

  const forecastAnalysisRunning =
    analysisRunning === true &&
    analysisType === "Satellite AGB";


  /*
   * Prevent another analysis from starting while ANY
   * global analysis is already running.
   */
  const analysisLocked =
    analysisRunning === true;


  /* =======================================================
     STATE UPDATE
  ======================================================= */

  function updateForecast(
    updates
  ) {

    setForecastState(
      updates
    );

  }


  /* =======================================================
     TEMPORARY UI STATE
  ======================================================= */

  const [
    locationSearching,
    setLocationSearching,
  ] = useState(false);


  /* =======================================================
     SELECT MAP LOCATION
  ======================================================= */

  function selectLocation(
    lat,
    lng
  ) {

    updateForecast({

      latitude:
        lat,

      longitude:
        lng,

      result:
        null,

      error:
        "",

      locationMessage:
        "Exact analysis location selected from the map.",

    });

  }


  /* =======================================================
     SEARCH LOCATION
  ======================================================= */

  async function searchLocation() {

    const placeInput =
      city.trim();

    const stateInput =
      stateName.trim();

    const countryInput =
      country.trim();

    const parts = [
      placeInput,
      stateInput,
      countryInput,
    ].filter(Boolean);

    if (
      parts.length === 0
    ) {

      updateForecast({

        locationMessage:
          "Enter a country, state/province, or city.",

      });

      return;

    }


    setLocationSearching(
      true
    );

    updateForecast({

      locationMessage:
        "",

      error:
        "",

    });


    try {

      const query =
        parts.join(
          ", "
        );

      const url =
        `https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&namedetails=1&dedupe=1&limit=15&q=${encodeURIComponent(
          query
        )}`;


      const response =
        await fetch(
          url,
          {
            headers: {
              Accept:
                "application/json",

              "Accept-Language":
                "en",
            },
          }
        );


      if (
        !response.ok
      ) {

        throw new Error(
          "Location search failed."
        );

      }


      const data =
        await response.json();


      if (
        !Array.isArray(data) ||
        data.length === 0
      ) {

        throw new Error(
          `Location "${query}" was not found. Try entering the city and state/province.`
        );

      }


      const scoredResults =
        data
          .map(
            item => ({

              item,

              score:
                scoreLocationResult(
                  item,
                  placeInput,
                  stateInput,
                  countryInput
                ),

            })
          )
          .sort(
            (a, b) =>
              b.score -
              a.score
          );


      console.log(
        "SylvaSense location candidates:",
        scoredResults
      );


      const best =
        scoredResults[0]?.item;


      if (!best) {

        throw new Error(
          "No suitable location was found."
        );

      }


      const lat =
        Number(
          Number(
            best.lat
          ).toFixed(6)
        );


      const lng =
        Number(
          Number(
            best.lon
          ).toFixed(6)
        );


      if (
        !Number.isFinite(lat) ||
        !Number.isFinite(lng)
      ) {

        throw new Error(
          "The selected location has invalid coordinates."
        );

      }


      const selectedName =
        best.display_name ||
        best.name ||
        query;


      updateForecast({

        latitude:
          lat,

        longitude:
          lng,

        result:
          null,

        error:
          "",

        locationMessage:
          `Found: ${selectedName}. You can click the map to choose the exact analysis point.`,

      });

    } catch (err) {

      console.error(
        "Location search error:",
        err
      );


      updateForecast({

        locationMessage:
          err?.message ||
          "Unable to find this location.",

      });

    } finally {

      setLocationSearching(
        false
      );

    }

  }


  /* =======================================================
     API HELPER
  ======================================================= */

  async function requestAGB(
    lat,
    lng,
    selectedRadius,
    selectedYear
  ) {

    return await api.satelliteAnalysis({

      latitude:
        lat,

      longitude:
        lng,

      radius_m:
        selectedRadius,

      year:
        selectedYear,

      max_cloud_pct:
        20,

    });

  }


  /* =======================================================
     CHECK SELECTED YEAR
  ======================================================= */

  function resultHasSelectedYearData(
    data
  ) {

    return (

      data?.selected_year?.available === true &&

      Number.isFinite(
        Number(
          data?.selected_year?.agbd_mg_ha
        )
      )

    );

  }


  /* =======================================================
     CHECK ANY GEDI DATA
  ======================================================= */

  function resultHasAnyGediData(
    data
  ) {

    if (
      resultHasSelectedYearData(
        data
      )
    ) {

      return true;

    }


    const latestAvailable =
      data?.latest_available;


    if (
      latestAvailable &&
      Number.isFinite(
        Number(
          latestAvailable.agbd_mg_ha
        )
      )
    ) {

      return true;

    }


    const historical =
      Array.isArray(
        data?.historical
      )
        ? data.historical
        : [];


    return historical.some(
      item =>
        item?.available === true &&
        Number.isFinite(
          Number(
            item?.agbd_mg_ha
          )
        )
    );

  }


  /* =======================================================
     RUN ANALYSIS
========================================================= */

  async function runAnalysis() {

    /*
     * IMPORTANT:
     *
     * Do not start another analysis while a global
     * analysis is already running.
     */
    if (
      analysisRunning
    ) {

      return;

    }


    const lat =
      Number(
        latitude
      );

    const lng =
      Number(
        longitude
      );

    const selectedYear =
      Number(
        year
      );

    const selectedRadius =
      Number(
        radius
      );


    /* =====================================================
       VALIDATION
    ===================================================== */

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lng)
    ) {

      updateForecast({

        error:
          "Please select a valid location on the map.",

      });

      return;

    }


    if (
      lat < -90 ||
      lat > 90
    ) {

      updateForecast({

        error:
          "Latitude must be between -90 and 90.",

      });

      return;

    }


    if (
      lng < -180 ||
      lng > 180
    ) {

      updateForecast({

        error:
          "Longitude must be between -180 and 180.",

      });

      return;

    }


    if (
      !Number.isFinite(
        selectedRadius
      ) ||
      selectedRadius <= 0
    ) {

      updateForecast({

        error:
          "Please select a valid analysis radius.",

      });

      return;

    }


    if (
      !YEARS.includes(
        selectedYear
      )
    ) {

      updateForecast({

        error:
          "Please select a valid analysis year.",

      });

      return;

    }


    /* =====================================================
       START GLOBAL ANALYSIS
    ===================================================== */

    /*
     * This state lives inside App.jsx.
     *
     * Therefore:
     *
     * Forecast -> Dashboard -> Forecast
     *
     * will NOT reset the button.
     */
    startAnalysis?.(
      "Satellite AGB",
      "Analyzing satellite AGB..."
    );


    updateForecast({

      error:
        "",

    });


    try {

      /* ===================================================
         UPDATE GLOBAL STATUS
      =================================================== */

      updateAnalysis?.(
        "Requesting GEDI + Sentinel-2 data..."
      );


      /* ===================================================
         BACKEND REQUEST
         
         IMPORTANT:
         There is NO abort/cancel here.
         
         If the user switches pages, this request continues
         until the backend responds.
      =================================================== */

      const data =
        await requestAGB(

          lat,

          lng,

          selectedRadius,

          selectedYear

        );


      console.log(
        "🔥 SATELLITE AGB BACKEND RESPONSE:",
        data
      );


      if (!data) {

        throw new Error(
          "The backend returned an empty response."
        );

      }


      if (
        data.status &&
        data.status !==
          "success"
      ) {

        throw new Error(

          data.message ||
          "Satellite AGB analysis failed."

        );

      }


      /* =================================================
         SAVE COMPLETE ORIGINAL RESPONSE
      ================================================= */

      updateForecast({

        result:
          data,

        error:
          "",

      });


      /* =================================================
         DETERMINE FALLBACK
      ================================================= */

      const requestedYearAvailable =
        data
          ?.requested_year_available === true;


      const effectiveYear =
        Number(
          data?.effective_year
        );


      const selectedYearFromBackend =
        Number(
          data
            ?.selected_year
            ?.year
        );


      const isFallback =
        data
          ?.selected_year
          ?.is_fallback === true ||

        (
          Number.isFinite(
            effectiveYear
          ) &&
          effectiveYear !==
            selectedYear
        ) ||

        (
          Number.isFinite(
            selectedYearFromBackend
          ) &&
          selectedYearFromBackend !==
            selectedYear
        );


      if (
        isFallback &&
        Number.isFinite(
          selectedYearFromBackend
        )
      ) {

        updateForecast({

          locationMessage:
            `The requested year ${selectedYear} has no valid GEDI observation here. Showing the nearest available GEDI observation from ${selectedYearFromBackend}.`,

        });

      } else if (
        requestedYearAvailable
      ) {

        updateForecast({

          locationMessage:
            `GEDI analysis completed for ${selectedYear}.`,

        });

      } else if (
        !resultHasAnyGediData(
          data
        )
      ) {

        updateForecast({

          locationMessage:
            `No valid GEDI AGB observation was found for ${selectedYear} or any available fallback year.`,

        });

      }


      /* =================================================
         FINISH GLOBAL ANALYSIS
         
         This changes:
           analysisRunning -> false
           analysisStatus -> completed
         
         and stores the result globally.
      ================================================= */

      finishAnalysis?.(
        data
      );

    } catch (err) {

      console.error(
        "Satellite AGB error:",
        err
      );


      updateForecast({

        error:
          err?.message ||
          "Satellite AGB analysis failed.",

      });


      /* =================================================
         GLOBAL FAILURE
      ================================================= */

      failAnalysis?.(
        err
      );

    }

    /*
     * NO finally/setBusy(false) HERE.
     *
     * The global App.jsx analysis state is responsible
     * for ending the loading state.
     */
  }


  /* =======================================================
     RESULT VALUES
  ======================================================= */

  const selectedYearData =
    result?.selected_year ||
    null;


  const selectedAgb =
    selectedYearData
      ?.agbd_mg_ha ??
    null;


  const selectedYearAvailable =
    selectedYearData
      ?.available === true &&
    Number.isFinite(
      Number(
        selectedAgb
      )
    );


  const selectedYearReturned =
    selectedYearData
      ?.year ??
    null;


  const selectedObservationCount =
    selectedYearData
      ?.image_count ??
    0;


  const selectedValidPixelCount =
    selectedYearData
      ?.valid_pixel_count ??
    0;


  const selectedSearchRadius =
    selectedYearData
      ?.search_radius_m ??
    null;


  const requestedYear =
    result
      ?.requested_year ??
    Number(
      year
    );


  const requestedYearAvailable =
    result
      ?.requested_year_available === true;


  const effectiveYear =
    result
      ?.effective_year ??
    selectedYearReturned ??
    null;


  const isFallback =
    selectedYearData
      ?.is_fallback === true ||

    (
      selectedYearAvailable &&
      selectedYearReturned !== null &&
      Number(
        selectedYearReturned
      ) !==
        Number(
          result?.requested_year ??
          year
        )
    );


  /* =======================================================
     LATEST AVAILABLE
  ======================================================= */

  const latestAgb =
    result
      ?.latest_available
      ?.agbd_mg_ha ??
    null;


  const latestYear =
    result
      ?.latest_available
      ?.year ??
    null;


  const latestObservationCount =
    result
      ?.latest_available
      ?.image_count ??
    0;


  const latestValidPixelCount =
    result
      ?.latest_available
      ?.valid_pixel_count ??
    0;


  /* =======================================================
     PREVIOUS
  ======================================================= */

  const previousAgb =
    result
      ?.previous_available
      ?.agbd_mg_ha ??
    null;


  const previousYear =
    result
      ?.previous_available
      ?.year ??
    null;


  /* =======================================================
     CHANGE
  ======================================================= */

  const changePercent =
    result
      ?.change
      ?.percent ??
    null;


  const changeAbsolute =
    result
      ?.change
      ?.absolute_mg_ha ??
    null;


  const changeFromYear =
    result
      ?.change
      ?.from_year ??
    null;


  const changeToYear =
    result
      ?.change
      ?.to_year ??
    null;


  /* =======================================================
     HISTORICAL
  ======================================================= */

  const chartData =
    useMemo(() => {

      const historical =
        result?.historical;


      if (
        !Array.isArray(
          historical
        )
      ) {

        return [];

      }


      return historical

        .filter(
          item =>
            item?.agbd_mg_ha !==
              null &&
            item?.agbd_mg_ha !==
              undefined &&
            Number.isFinite(
              Number(
                item.agbd_mg_ha
              )
            )
        )

        .map(
          item => ({

            year:
              Number(
                item.year
              ),

            agb:
              Number(
                item.agbd_mg_ha
              ),

          })
        );

    }, [
      result,
    ]);


  /* =======================================================
     SATELLITE TILE
  ======================================================= */

  const satelliteTile =
    result
      ?.satellite
      ?.tile_url ??
    null;


  /* =======================================================
     CHANGE LABEL
  ======================================================= */

  const changeLabel =
    changeFromYear !== null &&
    changeToYear !== null

      ? `${changeFromYear} → ${changeToYear}`

      : "No comparison available";


  /* =======================================================
     AVAILABLE YEARS
  ======================================================= */

  const availableYears =
    Array.isArray(
      result?.available_years
    )

      ? result.available_years

      : [];


  /* =======================================================
     ANY DATA
  ======================================================= */

  const hasAnyData =
    resultHasAnyGediData(
      result
    );


  /* =======================================================
     RENDER
  ======================================================= */

  return (

    <>

      <PageHeader
        icon={BarChart3}
        title="AGB Forecast"
        description="Select a location from satellite imagery and analyze aboveground biomass using real Earth observation data."
      />


      {/* ===================================================
          GLOBAL ANALYSIS STATUS
          
          This remains visible after returning to this page.
      =================================================== */}

      {forecastAnalysisRunning && (

        <div
          className="notice"
          style={{
            marginBottom:
              "20px",

            display:
              "flex",

            alignItems:
              "center",

            gap:
              "12px",
          }}
        >

          <RefreshCw
            size={20}
            className="spin"
          />

          <div>

            <strong>
              Analyzing satellite AGB...
            </strong>

            <p
              style={{
                margin:
                  "4px 0 0",

                opacity:
                  0.75,
              }}
            >

              {analysisStatus ||
                "Waiting for the Earth observation backend to return."}

            </p>

          </div>

        </div>

      )}


      {/* ===================================================
          LOCATION + CONTROLS + MAP
      =================================================== */}

      <div
        className="panel"
        style={{
          marginBottom:
            "20px",

          width:
            "100%",

          boxSizing:
            "border-box",
        }}
      >

        <div
          className="panel-head"
          style={{
            marginBottom:
              "20px",
          }}
        >

          <div>

            <h3>
              Satellite Location Selection
            </h3>

            <p>
              Search for a location, adjust the
              coordinates and analysis parameters,
              or click directly on the satellite map.
            </p>

          </div>

          <span className="badge">
            SATELLITE
          </span>

        </div>


        <div
          style={{
            display:
              "grid",

            gridTemplateColumns:
              "minmax(320px, 0.85fr) minmax(360px, 1.15fr)",

            gap:
              "24px",

            alignItems:
              "start",

            width:
              "100%",

            boxSizing:
              "border-box",
          }}
        >


          {/* =================================================
              LEFT
          ================================================= */}

          <div
            style={{
              display:
                "flex",

              flexDirection:
                "column",

              gap:
                "16px",

              width:
                "100%",

              minWidth:
                0,
            }}
          >


            {/* LOCATION */}

            <div
              className="control-panel"
              style={{
                ...controlPanelStyle,

                display:
                  "block",

                height:
                  "auto",

                minHeight:
                  "auto",

                overflow:
                  "visible",
              }}
            >

              <div
                style={{
                  display:
                    "block",

                  width:
                    "100%",

                  marginBottom:
                    "18px",
                }}
              >

                <h3
                  style={{
                    margin:
                      "0 0 6px",

                    fontSize:
                      "18px",

                    lineHeight:
                      "1.3",
                  }}
                >
                  Find Analysis Location
                </h3>

                <p
                  style={{
                    margin:
                      0,

                    lineHeight:
                      "1.5",
                  }}
                >
                  Search by country, state/province,
                  and city.
                </p>

              </div>


              {/* COUNTRY */}

              <div
                style={{
                  marginBottom:
                    "14px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    Country
                  </span>

                  <input
                    type="text"
                    value={
                      country
                    }
                    placeholder="Country"
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          country:
                            event.target.value,

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  />

                </label>

              </div>


              {/* STATE */}

              <div
                style={{
                  marginBottom:
                    "14px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    State / Province
                  </span>

                  <input
                    type="text"
                    value={
                      stateName
                    }
                    placeholder="State / Province"
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          stateName:
                            event.target.value,

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  />

                </label>

              </div>


              {/* CITY */}

              <div
                style={{
                  marginBottom:
                    "16px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    City / Town / Village
                  </span>

                  <input
                    type="text"
                    value={
                      city
                    }
                    placeholder="City, town, or village"
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          city:
                            event.target.value,

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  />

                </label>

              </div>


              <button
                className="primary-btn"
                type="button"
                disabled={
                  locationSearching ||
                  analysisLocked
                }
                onClick={
                  searchLocation
                }
                style={{
                  width:
                    "100%",

                  minHeight:
                    "44px",

                  display:
                    "flex",

                  alignItems:
                    "center",

                  justifyContent:
                    "center",

                  gap:
                    "8px",
                }}
              >

                {locationSearching ? (

                  <>

                    <RefreshCw
                      size={17}
                      className="spin"
                    />

                    Finding...

                  </>

                ) : (

                  <>

                    <Search
                      size={17}
                    />

                    Find Location

                  </>

                )}

              </button>


              {locationMessage && (

                <div
                  style={{
                    marginTop:
                      "12px",

                    display:
                      "flex",

                    alignItems:
                      "flex-start",

                    gap:
                      "8px",

                    fontSize:
                      "13px",

                    lineHeight:
                      "1.5",

                    opacity:
                      0.8,

                    width:
                      "100%",
                  }}
                >

                  <MapPin
                    size={16}
                    style={{
                      flexShrink:
                        0,

                      marginTop:
                        "2px",
                    }}
                  />

                  <span>
                    {
                      locationMessage
                    }
                  </span>

                </div>

              )}

            </div>


            {/* =================================================
                PARAMETERS
            ================================================= */}

            <div
              className="control-panel"
              style={{
                ...controlPanelStyle,

                display:
                  "block",

                height:
                  "auto",

                minHeight:
                  "auto",

                overflow:
                  "visible",
              }}
            >

              <div
                style={{
                  display:
                    "block",

                  width:
                    "100%",

                  marginBottom:
                    "18px",
                }}
              >

                <h3
                  style={{
                    margin:
                      "0 0 6px",

                    fontSize:
                      "18px",

                    lineHeight:
                      "1.3",
                  }}
                >
                  Analysis Parameters
                </h3>

                <p
                  style={{
                    margin:
                      0,

                    lineHeight:
                      "1.5",
                  }}
                >
                  Set the exact coordinates, year,
                  and analysis radius.
                </p>

              </div>


              {/* LATITUDE */}

              <div
                style={{
                  marginBottom:
                    "14px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    Selected latitude
                  </span>

                  <input
                    type="number"
                    step="0.000001"
                    value={
                      latitude
                    }
                    disabled={
                      analysisLocked
                    }
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          latitude:
                            event.target.value,

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  />

                </label>

              </div>


              {/* LONGITUDE */}

              <div
                style={{
                  marginBottom:
                    "14px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    Selected longitude
                  </span>

                  <input
                    type="number"
                    step="0.000001"
                    value={
                      longitude
                    }
                    disabled={
                      analysisLocked
                    }
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          longitude:
                            event.target.value,

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  />

                </label>

              </div>


              {/* YEAR */}

              <div
                style={{
                  marginBottom:
                    "14px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    Analysis year
                  </span>

                  <select
                    value={
                      year
                    }
                    disabled={
                      analysisLocked
                    }
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          year:
                            Number(
                              event.target.value
                            ),

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  >

                    {YEARS.map(
                      item => (

                        <option
                          key={
                            item
                          }
                          value={
                            item
                          }
                        >
                          {
                            item
                          }
                        </option>

                      )
                    )}

                  </select>

                </label>

              </div>


              {/* RADIUS */}

              <div
                style={{
                  marginBottom:
                    "16px",

                  width:
                    "100%",
                }}
              >

                <label
                  style={
                    labelStyle
                  }>

                  <span>
                    Analysis radius
                  </span>

                  <select
                    value={
                      radius
                    }
                    disabled={
                      analysisLocked
                    }
                    style={
                      inputStyle
                    }
                    onChange={
                      event =>
                        updateForecast({

                          radius:
                            Number(
                              event.target.value
                            ),

                          result:
                            null,

                          error:
                            "",

                        })
                    }
                  >

                    <option value="500">
                      500 m
                    </option>

                    <option value="1000">
                      1 km
                    </option>

                    <option value="2000">
                      2 km
                    </option>

                    <option value="3000">
                      3 km
                    </option>

                  </select>

                </label>

              </div>


              {/* AVAILABLE YEARS */}

              {availableYears.length >
                0 && (

                <div
                  style={{
                    marginBottom:
                      "16px",

                    padding:
                      "10px 12px",

                    borderRadius:
                      "8px",

                    fontSize:
                      "12px",

                    lineHeight:
                      "1.5",

                    opacity:
                      0.8,
                  }}
                >

                  Available GEDI years:

                  {" "}

                  {availableYears.join(
                    ", "
                  )}

                </div>

              )}


              {/* =================================================
                  ANALYZE BUTTON
              ================================================= */}

              <button
                className="primary-btn"
                type="button"
                disabled={
                  analysisLocked
                }
                onClick={
                  runAnalysis
                }
                style={{
                  width:
                    "100%",

                  minHeight:
                    "44px",

                  display:
                    "flex",

                  alignItems:
                    "center",

                  justifyContent:
                    "center",

                  gap:
                    "8px",
                }}
              >

                {forecastAnalysisRunning ? (

                  <>

                    <RefreshCw
                      size={17}
                      className="spin"
                    />

                    Analyzing...

                  </>

                ) : analysisLocked ? (

                  <>

                    <RefreshCw
                      size={17}
                      className="spin"
                    />

                    Another analysis is running...

                  </>

                ) : (

                  <>

                    <Satellite
                      size={17}
                    />

                    Analyze Satellite AGB

                  </>

                )}

              </button>


              {/* GLOBAL STATUS */}

              {forecastAnalysisRunning && (

                <div
                  style={{
                    marginTop:
                      "10px",

                    fontSize:
                      "12px",

                    opacity:
                      0.7,

                    textAlign:
                      "center",
                  }}
                >

                  {analysisStatus ||
                    "Analysis is still running..."}

                </div>

              )}

            </div>


            {/* ERROR */}

            {error && (

              <div
                className="error-box"
                style={{
                  width:
                    "100%",

                  boxSizing:
                    "border-box",
                }}
              >

                <X
                  size={18}
                />

                <span>
                  {
                    error
                  }
                </span>

              </div>

            )}

            {analysisError &&
              !forecastAnalysisRunning && (
                <div
                  className="error-box"
                  style={{
                    width:
                      "100%",

                    boxSizing:
                      "border-box",
                  }}
                >

                  <X
                    size={18}
                  />

                  <span>
                    {analysisError}
                  </span>

                </div>
              )}

          </div>


          {/* =================================================
              MAP
          ================================================= */}

          <div
            style={{
              minWidth:
                0,

              width:
                "100%",

              display:
                "flex",

              flexDirection:
                "column",
            }}
          >

            <div
              style={{
                width:
                  "100%",

                aspectRatio:
                  "1 / 1",

                minHeight:
                  "360px",

                maxHeight:
                  "620px",

                overflow:
                  "hidden",

                borderRadius:
                  "14px",

                position:
                  "relative",
              }}
            >

              <MapContainer
                center={[
                  Number(
                    latitude
                  ),
                  Number(
                    longitude
                  ),
                ]}
                zoom={11}
                minZoom={
                  MAP_MIN_ZOOM
                }
                maxZoom={
                  MAP_MAX_ZOOM
                }
                scrollWheelZoom={
                  true
                }
                doubleClickZoom={
                  true
                }
                dragging={
                  true
                }
                zoomControl={
                  true
                }
                attributionControl={
                  true
                }
                preferCanvas={
                  true
                }
                style={{
                  height:
                    "100%",

                  width:
                    "100%",

                  background:
                    "#0a120d",
                }}
              >

                <MapCenter
                  latitude={
                    latitude
                  }
                  longitude={
                    longitude
                  }
                />


                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution="Tiles &copy; Esri"
                  maxNativeZoom={
                    MAP_NATIVE_ZOOM
                  }
                  maxZoom={
                    MAP_MAX_ZOOM
                  }
                  detectRetina={
                    true
                  }
                  updateWhenZooming={
                    true
                  }
                  updateWhenIdle={
                    true
                  }
                  keepBuffer={
                    8
                  }
                  noWrap={
                    true
                  }
                />


                {satelliteTile && (

                  <TileLayer
                    key={
                      satelliteTile
                    }
                    url={
                      satelliteTile
                    }
                    opacity={
                      0.30
                    }
                    maxNativeZoom={
                      MAP_NATIVE_ZOOM
                    }
                    maxZoom={
                      MAP_MAX_ZOOM
                    }
                    detectRetina={
                      true
                    }
                    updateWhenZooming={
                      true
                    }
                    updateWhenIdle={
                      true
                    }
                    keepBuffer={
                      8
                    }
                    noWrap={
                      true
                    }
                    attribution="Sentinel-2 / Copernicus / Google Earth Engine"
                  />

                )}


                <LocationPicker
                  latitude={
                    latitude
                  }
                  longitude={
                    longitude
                  }
                  onSelect={
                    selectLocation
                  }
                />


                <Circle
                  center={[
                    Number(
                      latitude
                    ),
                    Number(
                      longitude
                    ),
                  ]}
                  radius={
                    Number(
                      radius
                    )
                  }
                  pathOptions={{
                    weight:
                      2,

                    opacity:
                      0.85,

                    fillOpacity:
                      0.08,
                  }}
                />

              </MapContainer>


              <div
                style={{
                  position:
                    "absolute",

                  left:
                    "15px",

                  bottom:
                    "15px",

                  zIndex:
                    1000,

                  padding:
                    "9px 12px",

                  borderRadius:
                    "8px",

                  background:
                    "rgba(0,0,0,0.72)",

                  color:
                    "#fff",

                  fontSize:
                    "12px",

                  display:
                    "flex",

                  alignItems:
                    "center",

                  gap:
                    "7px",

                  pointerEvents:
                    "none",
                }}
              >

                <MapPin
                  size={15}
                />

                Click anywhere to select the
                exact analysis location

              </div>

            </div>


            <div
              style={{
                marginTop:
                  "10px",

                display:
                  "flex",

                flexWrap:
                  "wrap",

                gap:
                  "8px",

                fontSize:
                  "12px",

                opacity:
                  0.75,
              }}
            >

              <span>
                Satellite imagery
              </span>

              <span>
                •
              </span>

              <span>
                Zoom 11–25
              </span>

              <span>
                •
              </span>

              <span>
                Click map to change location
              </span>

            </div>

          </div>

        </div>

      </div>


      {/* ===================================================
          RESULTS
      =================================================== */}

      {result && (

        <>

          {!hasAnyData ? (

            <div
              className="notice"
              style={{
                marginBottom:
                  "20px",

                display:
                  "flex",

                alignItems:
                  "flex-start",

                gap:
                  "10px",
              }}
            >

              <Satellite
                size={19}
                style={{
                  flexShrink:
                    0,
                }}
              />

              <div>

                <strong>
                  No valid GEDI data found for this location
                </strong>

                <p
                  style={{
                    margin:
                      "6px 0 0",
                  }}
                >

                  The backend did not return a valid
                  GEDI AGB observation for the requested
                  year or any available fallback year.

                  {availableYears.length >
                    0 && (

                    <>
                      {" "}
                      Available GEDI years returned by
                      the backend:{" "}
                      <strong>
                        {availableYears.join(
                          ", "
                        )}
                      </strong>.
                    </>

                  )}

                </p>

              </div>

            </div>

          ) : (

            <>


              {/* =================================================
                  FALLBACK NOTICE
              ================================================= */}

              {isFallback && (

                <div
                  className="notice"
                  style={{
                    marginBottom:
                      "20px",

                    display:
                      "flex",

                    alignItems:
                      "flex-start",

                    gap:
                      "10px",
                  }}
                >

                  <AlertTriangle
                    size={20}
                    style={{
                      flexShrink:
                        0,
                    }}
                  />

                  <div>

                    <strong>
                      Requested year {requestedYear} is unavailable
                    </strong>

                    <p
                      style={{
                        margin:
                          "6px 0 0",

                        lineHeight:
                          "1.5",
                      }}
                    >

                      No valid GEDI observation was found
                      for {requestedYear} in the searched
                      area.

                      {" "}

                      Showing the nearest available actual
                      GEDI observation from{" "}

                      <strong>
                        {effectiveYear}
                      </strong>.

                    </p>

                  </div>

                </div>

              )}


              {/* =================================================
                  METRIC CARDS
              ================================================= */}

              <div
                className="metric-grid"
              >

                <div
                  className="metric-card"
                >

                  <div
                    className="metric-icon"
                  >

                    <Leaf
                      size={20}
                    />

                  </div>


                  <div
                    className="metric-label"
                  >

                    {isFallback
                      ? "AGB for Data Year Used"
                      : "Selected Year AGB"}

                  </div>


                  <div
                    className="metric-value"
                  >

                    {selectedAgb !== null
                      ? fmt(
                          selectedAgb
                        )
                      : "—"}

                    {selectedAgb !== null && (

                      <span>
                        Mg/ha
                      </span>

                    )}

                  </div>


                  {selectedYearReturned !==
                    null && (

                    <small
                      style={{
                        opacity:
                          0.7,
                      }}
                    >

                      Data year:{" "}
                      {selectedYearReturned}

                    </small>

                  )}

                </div>


                <div
                  className="metric-card"
                >

                  <div
                    className="metric-icon"
                  >

                    <Satellite
                      size={20}
                    />

                  </div>


                  <div
                    className="metric-label"
                  >
                    Latest Available AGB
                  </div>


                  <div
                    className="metric-value"
                  >

                    {latestAgb !== null
                      ? fmt(
                          latestAgb
                        )
                      : "—"}

                    {latestAgb !== null && (

                      <span>
                        Mg/ha · {latestYear}
                      </span>

                    )}

                  </div>

                </div>


                <div
                  className="metric-card"
                >

                  <div
                    className="metric-icon"
                  >

                    {changePercent !== null &&
                    changePercent < 0 ? (

                      <TrendingDown
                        size={20}
                      />

                    ) : (

                      <TrendingUp
                        size={20}
                      />

                    )}

                  </div>


                  <div
                    className="metric-label"
                  >
                    Actual Available-Year Change
                  </div>


                  <div
                    className="metric-value"
                  >

                    {changePercent !== null

                      ? `${
                          changePercent >=
                          0
                            ? "+"
                            : ""
                        }${fmt(
                          changePercent
                        )}%`

                      : "—"}

                  </div>


                  {changeFromYear !== null &&
                    changeToYear !== null && (

                    <small
                      style={{
                        opacity:
                          0.7,
                      }}
                    >

                      {changeFromYear}
                      {" → "}
                      {changeToYear}

                    </small>

                  )}

                </div>


                <div
                  className="metric-card"
                >

                  <div
                    className="metric-icon"
                  >

                    <BarChart3
                      size={20}
                    />

                  </div>


                  <div
                    className="metric-label"
                  >
                    GEDI Observations
                  </div>


                  <div
                    className="metric-value"
                  >

                    {
                      selectedObservationCount
                    }

                  </div>


                  <small
                    style={{
                      opacity:
                        0.7,
                    }}
                  >

                    Valid pixels:{" "}
                    {
                      selectedValidPixelCount
                    }

                  </small>

                </div>

              </div>


              {/* =================================================
                  SELECTED YEAR + LATEST
              ================================================= */}

              <div
                className="two-column"
              >

                <div
                  className="panel"
                >

                  <div
                    className="panel-head"
                  >

                    <div>

                      <h3>
                        Selected Year Analysis
                      </h3>

                      <p>
                        Actual GEDI result returned
                        for the requested year or the
                        backend-selected fallback year.
                      </p>

                    </div>


                    <span
                      className={
                        isFallback
                          ? "badge"
                          : "badge success"
                      }
                    >

                      {isFallback
                        ? "FALLBACK DATA"
                        : "DATA AVAILABLE"}

                    </span>

                  </div>


                  <div
                    className="result-stack"
                  >

                    <div>

                      <span>
                        Latitude
                      </span>

                      <strong>
                        {fmt(
                          latitude,
                          6
                        )}
                      </strong>

                    </div>


                    <div>

                      <span>
                        Longitude
                      </span>

                      <strong>
                        {fmt(
                          longitude,
                          6
                        )}
                      </strong>

                    </div>


                    <div>

                      <span>
                        Requested year
                      </span>

                      <strong>
                        {requestedYear}
                      </strong>

                    </div>


                    <div>

                      <span>
                        Requested-year data
                      </span>

                      <strong>

                        {requestedYearAvailable
                          ? "Available"
                          : "Unavailable"}

                      </strong>

                    </div>


                    <div>

                      <span>
                        Data year actually used
                      </span>

                      <strong>
                        {selectedYearReturned ??
                          "—"}
                      </strong>

                    </div>


                    <div>

                      <span>
                        Aboveground biomass density
                      </span>

                      <strong>

                        {selectedAgb !== null

                          ? `${fmt(
                              selectedAgb
                            )} Mg/ha`

                          : "No valid GEDI data"}

                      </strong>

                    </div>


                    <div>

                      <span>
                        GEDI images
                      </span>

                      <strong>
                        {
                          selectedObservationCount
                        }
                      </strong>

                    </div>


                    <div>

                      <span>
                        Valid GEDI pixels
                      </span>

                      <strong>
                        {
                          selectedValidPixelCount
                        }
                      </strong>

                    </div>


                    {selectedSearchRadius !==
                      null && (

                      <div>

                        <span>
                          GEDI search radius
                        </span>

                        <strong>

                          {selectedSearchRadius >=
                          1000

                            ? `${selectedSearchRadius / 1000} km`

                            : `${selectedSearchRadius} m`}

                        </strong>

                      </div>

                    )}

                  </div>

                </div>


                <div
                  className="panel"
                >

                  <div
                    className="panel-head"
                  >

                    <div>

                      <h3>
                        Latest Available Observation
                      </h3>

                      <p>
                        Latest actual GEDI observation
                        returned for this area.
                      </p>

                    </div>

                    <CheckCircle
                      size={20}
                    />

                  </div>


                  <div
                    style={{
                      padding:
                        "25px 0",

                      textAlign:
                        "center",
                    }}
                  >

                    <div
                      style={{
                        fontSize:
                          "38px",

                        fontWeight:
                          700,
                      }}
                    >

                      {latestAgb !== null
                        ? fmt(
                            latestAgb
                          )
                        : "—"}

                    </div>


                    <p>

                      {latestAgb !== null
                        ? `Mg/ha · ${latestYear}`
                        : "No valid GEDI observation"}

                    </p>


                    <small>

                      GEDI images:{" "}

                      {
                        latestObservationCount
                      }

                    </small>

                    <br />

                    <small>

                      Valid pixels:{" "}

                      {
                        latestValidPixelCount
                      }

                    </small>

                  </div>

                </div>

              </div>


              {/* =================================================
                  CHANGE
              ================================================= */}

              <div
                className="panel"
                style={{
                  marginTop:
                    "20px",
                }}
              >

                <div
                  className="panel-head"
                >

                  <div>

                    <h3>
                      Actual AGB Change
                    </h3>

                    <p>
                      Change between consecutive
                      available GEDI observations.
                    </p>

                  </div>


                  {changePercent !== null && (

                    changePercent >= 0

                      ? (
                        <TrendingUp
                          size={22}
                        />
                      )

                      : (
                        <TrendingDown
                          size={22}
                        />
                      )

                  )}

                </div>


                {changePercent !== null ? (

                  <div
                    style={{
                      padding:
                        "25px 0",

                      textAlign:
                        "center",
                    }}
                  >

                    <div
                      style={{
                        fontSize:
                          "38px",

                        fontWeight:
                          700,
                      }}
                    >

                      {changePercent >= 0
                        ? "+"
                        : ""}

                      {fmt(
                        changePercent
                      )}

                      %

                    </div>


                    <p>
                      {changeLabel}
                    </p>


                    <small>

                      {previousAgb !== null
                        ? `${fmt(
                            previousAgb
                          )} Mg/ha`
                        : "—"}

                      {" → "}

                      {latestAgb !== null
                        ? `${fmt(
                            latestAgb
                          )} Mg/ha`
                        : "—"}

                    </small>

                    <br />

                    <small>

                      Absolute change:{" "}

                      {changeAbsolute !== null
                        ? `${fmt(
                            changeAbsolute
                          )} Mg/ha`
                        : "—"}

                    </small>


                    {previousYear !== null &&
                      latestYear !== null && (

                      <>

                        <br />

                        <small>

                          Based on actual GEDI
                          observations from{" "}
                          {previousYear}
                          {" → "}
                          {latestYear}

                        </small>

                      </>

                    )}

                  </div>

                ) : (

                  <div
                    style={{
                      padding:
                        "35px",

                      textAlign:
                        "center",
                    }}
                  >

                    There are not enough actual
                    GEDI observations to calculate
                    a year-to-year change.

                  </div>

                )}

              </div>


              {/* =================================================
                  HISTORICAL
              ================================================= */}

              <div
                className="panel"
                style={{
                  marginTop:
                    "20px",
                }}
              >

                <div
                  className="panel-head"
                >

                  <div>

                    <h3>
                      Historical AGB Trend
                    </h3>

                    <p>
                      Only years containing actual GEDI
                      AGB observations are shown.
                    </p>

                  </div>

                  <CheckCircle
                    size={20}
                  />

                </div>


                {chartData.length >
                0 ? (

                  <div
                    style={{
                      width:
                        "100%",

                      height:
                        "360px",
                    }}
                  >

                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                    >

                      <LineChart
                        data={
                          chartData
                        }
                        margin={{
                          top:
                            15,

                          right:
                            25,

                          left:
                            10,

                          bottom:
                            10,
                        }}
                      >

                        <CartesianGrid
                          strokeDasharray="3 3"
                        />

                        <XAxis
                          dataKey="year"
                        />

                        <YAxis
                          label={{
                            value:
                              "Mg/ha",

                            angle:
                              -90,

                            position:
                              "insideLeft",
                          }}
                        />

                        <Tooltip
                          formatter={(
                            value
                          ) => [
                            `${fmt(
                              value
                            )} Mg/ha`,
                            "AGB",
                          ]}
                        />

                        <Line
                          type="monotone"
                          dataKey="agb"
                          stroke="currentColor"
                          strokeWidth={3}
                          dot={{
                            r: 5,
                          }}
                          activeDot={{
                            r: 7,
                          }}
                        />

                      </LineChart>

                    </ResponsiveContainer>

                  </div>

                ) : (

                  <div
                    style={{
                      padding:
                        "50px",

                      textAlign:
                        "center",
                    }}
                  >

                    No actual GEDI AGB observations
                    were returned for this location.

                  </div>

                )}

              </div>


              {/* =================================================
                  SATELLITE + REGION
              ================================================= */}

              <div
                className="two-column"
                style={{
                  marginTop:
                    "20px",
                }}
              >

                <div
                  className="panel"
                >

                  <div
                    className="panel-head"
                  >

                    <div>

                      <h3>
                        Satellite Imagery
                      </h3>

                      <p>
                        Sentinel-2 imagery associated
                        with the requested analysis year.
                      </p>

                    </div>

                    <Satellite
                      size={20}
                    />

                  </div>


                  <div
                    className="result-stack"
                  >

                    <div>

                      <span>
                        Collection
                      </span>

                      <strong>
                        Sentinel-2
                      </strong>

                    </div>


                    <div>

                      <span>
                        Scenes
                      </span>

                      <strong>
                        {
                          result
                            ?.satellite
                            ?.scene_count ??
                          0
                        }
                      </strong>

                    </div>


                    <div>

                      <span>
                        Imagery year
                      </span>

                      <strong>
                        {
                          result
                            ?.satellite
                            ?.year ??
                          "—"
                        }
                      </strong>

                    </div>


                    <div>

                      <span>
                        Cloud threshold
                      </span>

                      <strong>
                        20%
                      </strong>

                    </div>

                  </div>

                </div>


                <div
                  className="panel"
                >

                  <div
                    className="panel-head"
                  >

                    <div>

                      <h3>
                        Analysis Region
                      </h3>

                      <p>
                        Area used for GEDI aggregation.
                      </p>

                    </div>

                    <BarChart3
                      size={20}
                    />

                  </div>


                  <div
                    className="result-stack"
                  >

                    <div>

                      <span>
                        Requested radius
                      </span>

                      <strong>

                        {radius >= 1000

                          ? `${radius / 1000} km`

                          : `${radius} m`}

                      </strong>

                    </div>


                    <div>

                      <span>
                        Effective GEDI radius
                      </span>

                      <strong>

                        {selectedSearchRadius !==
                        null

                          ? selectedSearchRadius >=
                            1000

                            ? `${selectedSearchRadius / 1000} km`

                            : `${selectedSearchRadius} m`

                          : "—"}

                      </strong>

                    </div>


                    <div>

                      <span>
                        Available GEDI years
                      </span>

                      <strong>

                        {availableYears.length >
                        0

                          ? availableYears.join(
                              ", "
                            )

                          : "—"}

                      </strong>

                    </div>

                  </div>

                </div>

              </div>


              {/* =================================================
                  DATA POLICY
              ================================================= */}

              <div
                className="notice"
                style={{
                  marginTop:
                    "20px",
                }}
              >

                <Satellite
                  size={19}
                />

                <span>

                  AGB values come only from actual
                  quality-filtered GEDI L4A observations.
                  Missing years are displayed as unavailable
                  rather than being estimated or fabricated.

                  {isFallback && (

                    <>
                      {" "}
                      The requested year {requestedYear}
                      was unavailable, so the backend
                      returned the actual observation from{" "}
                      {selectedYearReturned}.
                    </>

                  )}

                </span>

              </div>


              {/* =================================================
                  RAW BACKEND DATA
              ================================================= */}

              <details
                className="panel"
                style={{
                  marginTop:
                    "20px",
                }}
              >

                <summary>
                  Backend Analysis Data
                </summary>

                <pre
                  className="json-view"
                >
                  {JSON.stringify(
                    result,
                    null,
                    2
                  )}
                </pre>

              </details>

            </>

          )}

        </>

      )}

    </>

  );

}