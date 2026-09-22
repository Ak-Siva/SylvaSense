import React, {
  useMemo,
  useState,
} from "react";

import {
  CalendarDays,
  ChevronRight,
  CircleDot,
  Layers3,
  MapPin,
  RefreshCw,
  Ruler,
  Search,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";

import {
  MapContainer,
  TileLayer,
  Circle,
  CircleMarker,
  Popup,
  useMap,
  useMapEvents,
} from "react-leaflet";

import "leaflet/dist/leaflet.css";

import PageHeader from "../components/PageHeader";

import {
  api,
  isEndpointUnavailable,
} from "../services/api";

import { fmt } from "../utils/normalize";


/* =========================================================
   MAP CENTER
========================================================= */

function MapCenter({
  latitude,
  longitude,
  zoom = 12,
}) {
  const map = useMap();

  React.useEffect(() => {
    if (
      Number.isFinite(latitude) &&
      Number.isFinite(longitude)
    ) {
      map.setView(
        [latitude, longitude],
        zoom,
        {
          animate: true,
        }
      );
    }
  }, [
    map,
    latitude,
    longitude,
    zoom,
  ]);

  return null;
}


/* =========================================================
   LOCATION MAP CLICK
========================================================= */

function LocationMapClick({
  onLocationSelect,
}) {
  useMapEvents({
    click(event) {
      const {
        lat,
        lng,
      } = event.latlng;

      onLocationSelect(
        lat,
        lng
      );
    },
  });

  return null;
}


/* =========================================================
   MAIN COMPONENT
========================================================= */

export default function ChangeDetection() {

  /* =======================================================
     OBSERVATION DATES
  ======================================================= */

  const [beforeDate, setBeforeDate] =
    useState("2025-06-01");

  const [afterDate, setAfterDate] =
    useState("2026-02-28");


  /* =======================================================
     PLACE SEARCH
  ======================================================= */

  const [country, setCountry] =
    useState("India");

  const [stateRegion, setStateRegion] =
    useState("Tamil Nadu");

  const [cityPlace, setCityPlace] =
    useState("Karur");

  const [placeSearchBusy, setPlaceSearchBusy] =
    useState(false);

  const [placeSearchMessage, setPlaceSearchMessage] =
    useState("");


  /* =======================================================
     ANALYSIS LOCATION
  ======================================================= */

  const [latitude, setLatitude] =
    useState("10.9601");

  const [longitude, setLongitude] =
    useState("78.0766");

  const [radius, setRadius] =
    useState("2000");


  /* =======================================================
     ANALYSIS STATE
  ======================================================= */

  const [busy, setBusy] =
    useState(() => {
      return (
        sessionStorage.getItem(
          "sylvasense_change_busy"
        ) === "true"
      );
    });

  const [data, setData] =
    useState(() => {
      try {
        const saved =
          sessionStorage.getItem(
            "sylvasense_change_result"
          );

        return saved
          ? JSON.parse(saved)
          : null;
      } catch {
        return null;
      }
    });

  const [error, setError] =
    useState("");

  const [activeLayer, setActiveLayer] =
    useState(() => {
      return (
        sessionStorage.getItem(
          "sylvasense_change_active_layer"
        ) ||
        "ndvi_change"
      );
    });


  /* =======================================================
     SELECT EXACT MAP LOCATION
  ======================================================= */

  function selectMapLocation(
    lat,
    lng
  ) {
    const safeLat =
      Number(lat);

    const safeLng =
      Number(lng);

    if (
      !Number.isFinite(safeLat) ||
      !Number.isFinite(safeLng)
    ) {
      return;
    }

    setLatitude(
      safeLat.toFixed(6)
    );

    setLongitude(
      safeLng.toFixed(6)
    );

    setPlaceSearchMessage(
      "Exact analysis location selected from the map."
    );

    setData(null);
    setError("");

    try {
      sessionStorage.removeItem(
        "sylvasense_change_result"
      );
    } catch {
      // Ignore storage errors.
    }
  }


  /* =======================================================
     PLACE SEARCH
     
     Important:
     We request address details and then rank:
     
     1. city
     2. town
     3. municipality
     4. county
     5. village/locality
     
     This helps "Karur" resolve to Karur city instead
     of a small locality with the same name.
  ======================================================= */

  async function findPlace() {

    const countryValue =
      country.trim();

    const stateValue =
      stateRegion.trim();

    const cityValue =
      cityPlace.trim();

    if (
      !countryValue ||
      !stateValue ||
      !cityValue
    ) {
      setPlaceSearchMessage(
        "Enter country, state/region and city/place."
      );

      return;
    }

    setPlaceSearchBusy(true);
    setPlaceSearchMessage("");
    setError("");

    try {

      /*
       * Use multiple results instead of only the first
       * result. Nominatim can return villages/localities
       * before the actual city.
       */

      const query =
        `${cityValue}, ${stateValue}, ${countryValue}`;

      const url =
        "https://nominatim.openstreetmap.org/search" +
        `?format=jsonv2` +
        `&addressdetails=1` +
        `&limit=10` +
        `&countrycodes=in` +
        `&q=${encodeURIComponent(query)}`;

      const response =
        await fetch(
          url,
          {
            headers: {
              Accept:
                "application/json",
            },
          }
        );

      if (!response.ok) {
        throw new Error(
          "Place search service returned an error."
        );
      }

      const results =
        await response.json();

      if (
        !Array.isArray(results) ||
        results.length === 0
      ) {
        setPlaceSearchMessage(
          "Place not found. Try the city name with its state."
        );

        return;
      }


      /* ---------------------------------------------------
         NORMALIZE SEARCH TEXT
      --------------------------------------------------- */

      const wantedCity =
        cityValue
          .toLowerCase()
          .trim();


      /* ---------------------------------------------------
         SCORE EACH RESULT
         
         Higher score = better match.
      --------------------------------------------------- */

      const scoredResults =
        results.map(
          (result) => {

            const address =
              result.address ||
              {};

            const displayName =
              String(
                result.display_name ||
                ""
              ).toLowerCase();

            const resultName =
              String(
                result.name ||
                ""
              ).toLowerCase();

            const type =
              String(
                result.type ||
                ""
              ).toLowerCase();

            const category =
              String(
                result.category ||
                ""
              ).toLowerCase();


            let score = 0;


            /*
             * Exact name match.
             */

            if (
              resultName ===
              wantedCity
            ) {
              score += 100;
            }


            /*
             * Address city/town match.
             */

            if (
              String(
                address.city ||
                ""
              ).toLowerCase() ===
              wantedCity
            ) {
              score += 95;
            }


            if (
              String(
                address.town ||
                ""
              ).toLowerCase() ===
              wantedCity
            ) {
              score += 95;
            }


            if (
              String(
                address.municipality ||
                ""
              ).toLowerCase() ===
              wantedCity
            ) {
              score += 90;
            }


            if (
              String(
                address.city_district ||
                ""
              ).toLowerCase() ===
              wantedCity
            ) {
              score += 70;
            }


            /*
             * Result display name starts with the city.
             */

            if (
              displayName.startsWith(
                wantedCity + ","
              )
            ) {
              score += 60;
            }


            /*
             * Prefer actual city/town/municipality
             * over village/hamlet.
             */

            if (
              type === "city"
            ) {
              score += 50;
            }

            if (
              type === "town"
            ) {
              score += 45;
            }

            if (
              type === "municipality"
            ) {
              score += 40;
            }

            if (
              type === "administrative"
            ) {
              score += 30;
            }

            if (
              type === "village"
            ) {
              score += 10;
            }

            if (
              type === "hamlet"
            ) {
              score -= 10;
            }


            /*
             * Prefer place categories.
             */

            if (
              category === "place"
            ) {
              score += 20;
            }


            return {
              result,
              score,
            };

          }
        );


      /* ---------------------------------------------------
         SORT BEST RESULT FIRST
      --------------------------------------------------- */

      scoredResults.sort(
        (
          a,
          b
        ) =>
          b.score -
          a.score
      );


      const selected =
        scoredResults[0]?.result;


      if (!selected) {
        setPlaceSearchMessage(
          "Unable to identify the requested city."
        );

        return;
      }


      const foundLat =
        Number(
          selected.lat
        );

      const foundLon =
        Number(
          selected.lon
        );


      if (
        !Number.isFinite(
          foundLat
        ) ||
        !Number.isFinite(
          foundLon
        )
      ) {
        throw new Error(
          "The selected place does not have valid coordinates."
        );
      }


      /* ---------------------------------------------------
         MOVE MAP TO CITY
      --------------------------------------------------- */

      setLatitude(
        foundLat.toFixed(6)
      );

      setLongitude(
        foundLon.toFixed(6)
      );


      /*
       * Do not keep old analysis result after changing
       * location.
       */

      setData(null);


      try {
        sessionStorage.removeItem(
          "sylvasense_change_result"
        );
      } catch {
        // Ignore storage errors.
      }


      /*
       * Tell user to click exact point.
       */

      setPlaceSearchMessage(
        `Found: ${selected.display_name}. Click the map to choose the exact analysis location.`
      );

    } catch (err) {

      setPlaceSearchMessage(
        err?.message ||
        "Unable to find the place."
      );

    } finally {

      setPlaceSearchBusy(false);

    }
  }


  /* =======================================================
     SAVE RESULT
  ======================================================= */

  function saveChangeResult(
    result
  ) {

    setData(result);

    try {

      sessionStorage.setItem(
        "sylvasense_change_result",
        JSON.stringify(result)
      );

    } catch (storageError) {

      console.warn(
        "Unable to save change detection result:",
        storageError
      );

    }
  }


  /* =======================================================
     SAVE ACTIVE LAYER
  ======================================================= */

  function updateActiveLayer(
    layerId
  ) {

    setActiveLayer(
      layerId
    );

    try {

      sessionStorage.setItem(
        "sylvasense_change_active_layer",
        layerId
      );

    } catch {
      // Ignore storage errors.
    }
  }


  /* =======================================================
     RUN CHANGE DETECTION
  ======================================================= */

  async function run() {

    setError("");
    setData(null);

    try {

      sessionStorage.removeItem(
        "sylvasense_change_result"
      );

    } catch {
      // Ignore storage errors.
    }


    /* -----------------------------------------------------
       LOCATION
    ----------------------------------------------------- */

    const lat =
      Number(latitude);

    const lon =
      Number(longitude);

    const radiusValue =
      Number(radius);


    if (
      !Number.isFinite(lat) ||
      lat < -90 ||
      lat > 90
    ) {

      setError(
        "Latitude must be between -90 and 90."
      );

      return;
    }


    if (
      !Number.isFinite(lon) ||
      lon < -180 ||
      lon > 180
    ) {

      setError(
        "Longitude must be between -180 and 180."
      );

      return;
    }


    if (
      !Number.isFinite(radiusValue) ||
      radiusValue < 100 ||
      radiusValue > 10000
    ) {

      setError(
        "Analysis radius must be between 100 m and 10,000 m."
      );

      return;
    }


    /* -----------------------------------------------------
       DATES
    ----------------------------------------------------- */

    if (
      beforeDate >= afterDate
    ) {

      setError(
        "Reference observation date must be earlier than the comparison observation date."
      );

      return;
    }


    /* -----------------------------------------------------
       START
    ----------------------------------------------------- */

    setBusy(true);

    try {

      sessionStorage.setItem(
        "sylvasense_change_busy",
        "true"
      );

    } catch {
      // Ignore storage errors.
    }


    try {

      /*
       * IMPORTANT:
       *
       * Backend payload remains unchanged.
       */

      const response =
        await api.changeDetection({

          before_date:
            beforeDate,

          after_date:
            afterDate,

          latitude:
            lat,

          longitude:
            lon,

          radius_m:
            radiusValue,

          window_days:
            30,

          max_cloud_pct:
            20,

        });


      /* ---------------------------------------------------
         SAVE RESULT
      --------------------------------------------------- */

      saveChangeResult(
        response
      );


      /* ---------------------------------------------------
         DEFAULT CHANGE LAYER
         
         Prefer ndvi_change because that is the layer
         that visually shows the vegetation difference.
      --------------------------------------------------- */

      const changeLayer =
        response?.layers?.find(
          (layer) =>
            layer.id ===
            "ndvi_change"
        );


      const defaultLayer =
        changeLayer ||
        response?.layers?.find(
          (layer) =>
            layer.default_visible
        ) ||
        response?.layers?.[0];


      if (
        defaultLayer?.id
      ) {

        updateActiveLayer(
          defaultLayer.id
        );

      }


    } catch (err) {

      setData(null);

      try {

        sessionStorage.removeItem(
          "sylvasense_change_result"
        );

      } catch {
        // Ignore storage errors.
      }


      setError(
        isEndpointUnavailable(err)
          ? "Change detection is not exposed by the current FastAPI server."
          : err?.message ||
            "Change detection failed."
      );

    } finally {

      setBusy(false);

      try {

        sessionStorage.setItem(
          "sylvasense_change_busy",
          "false"
        );

      } catch {
        // Ignore storage errors.
      }

    }
  }


  /* =======================================================
     RESULT DATA
  ======================================================= */

  const before =
    data?.before || {};

  const after =
    data?.after || {};

  const change =
    data?.change || {};

  const layers =
    Array.isArray(
      data?.layers
    )
      ? data.layers
      : [];


  /* =======================================================
     ACTIVE LAYER
  ======================================================= */

  const activeLayerData =
    useMemo(() => {

      return (
        layers.find(
          (layer) =>
            layer.id ===
            activeLayer
        ) ||
        layers.find(
          (layer) =>
            layer.id ===
            "ndvi_change"
        ) ||
        layers[0] ||
        null
      );

    }, [
      layers,
      activeLayer,
    ]);


  /* =======================================================
     MAP LOCATION
  ======================================================= */

  const mapLatitude =
    Number(
      data?.location?.latitude ??
      latitude
    );

  const mapLongitude =
    Number(
      data?.location?.longitude ??
      longitude
    );

  const mapRadius =
    Number(
      data?.location?.radius_m ??
      radius
    );


  /* =======================================================
     CHANGE VALUES
  ======================================================= */

  const meanChange =
    Number.isFinite(
      Number(
        change.mean_ndvi_change
      )
    )
      ? Number(
          change.mean_ndvi_change
        )
      : null;


  const minChange =
    Number.isFinite(
      Number(
        change.minimum_ndvi_change
      )
    )
      ? Number(
          change.minimum_ndvi_change
        )
      : null;


  const maxChange =
    Number.isFinite(
      Number(
        change.maximum_ndvi_change
      )
    )
      ? Number(
          change.maximum_ndvi_change
        )
      : null;


  const decreasePixels =
    Number.isFinite(
      Number(
        change.decrease_pixel_count
      )
    )
      ? Number(
          change.decrease_pixel_count
        )
      : null;


  const increasePixels =
    Number.isFinite(
      Number(
        change.increase_pixel_count
      )
    )
      ? Number(
          change.increase_pixel_count
        )
      : null;


  /* =======================================================
     INPUT MAP VALUES
  ======================================================= */

  const inputLatitude =
    Number(latitude);

  const inputLongitude =
    Number(longitude);

  const inputRadius =
    Number(radius);


  /* =======================================================
     CHANGE DIRECTION
  ======================================================= */

  const changeDirection =
    decreasePixels !== null &&
    increasePixels !== null
      ? decreasePixels >
        increasePixels
        ? "More vegetation decrease detected"
        : increasePixels >
          decreasePixels
          ? "More vegetation increase detected"
          : "Balanced or mixed change"
      : "Change layer available";


  /* =======================================================
     RENDER
  ======================================================= */

  return (
    <>
      <PageHeader
        icon={Layers3}
        title="Change Detection"
        description="Compare vegetation conditions between two observation periods using Sentinel-2 NDVI."
      />


      {/* =================================================
          MAIN INPUT AREA
      ================================================= */}

      <div
        className="two-column"
        style={{
          alignItems: "stretch",
        }}
      >

        {/* =================================================
            LEFT — INPUTS
        ================================================= */}

        <div
          className="panel"
          style={{
            minWidth: 0,
          }}
        >

          <div className="change-location-header">

            <div>

              <div className="change-section-icon">
                <MapPin size={19} />
              </div>

            </div>

            <div>

              <h3>
                Analysis Location
              </h3>

              <p>
                Find a city, then click the exact
                analysis point on the map.
              </p>

            </div>

          </div>


          {/* =================================================
              PLACE SEARCH
          ================================================= */}

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "1fr",
              gap: "12px",
              marginTop: "20px",
            }}
          >

            <label className="change-input">

              <span>
                Country
              </span>

              <input
                type="text"
                value={country}
                onChange={(event) =>
                  setCountry(
                    event.target.value
                  )
                }
                placeholder="India"
              />

            </label>


            <label className="change-input">

              <span>
                State / Province
              </span>

              <input
                type="text"
                value={stateRegion}
                onChange={(event) =>
                  setStateRegion(
                    event.target.value
                  )
                }
                placeholder="Tamil Nadu"
              />

            </label>


            <label className="change-input">

              <span>
                City
              </span>

              <input
                type="text"
                value={cityPlace}
                onChange={(event) =>
                  setCityPlace(
                    event.target.value
                  )
                }
                onKeyDown={(event) => {
                  if (
                    event.key ===
                    "Enter"
                  ) {
                    findPlace();
                  }
                }}
                placeholder="Karur"
              />

            </label>


            <button
              type="button"
              className="primary-btn"
              onClick={findPlace}
              disabled={
                placeSearchBusy
              }
              style={{
                width: "100%",
                minHeight: "44px",
              }}
            >

              {placeSearchBusy ? (

                <>
                  <RefreshCw
                    size={16}
                    className="spin"
                  />

                  Finding city...
                </>

              ) : (

                <>
                  <Search size={16} />

                  Find City
                </>

              )}

            </button>

          </div>


          {/* Search status */}

          {placeSearchMessage && (

            <div
              className="change-location-summary"
              style={{
                marginTop: "14px",
              }}
            >

              <MapPin size={16} />

              <span>
                {placeSearchMessage}
              </span>

            </div>

          )}


          {/* =================================================
              COORDINATES
          ================================================= */}

          <div
            className="change-location-grid"
            style={{
              marginTop: "20px",
              gridTemplateColumns:
                "1fr",
            }}
          >

            <label className="change-input">

              <span>
                Latitude
              </span>

              <input
                type="number"
                step="0.0001"
                min="-90"
                max="90"
                value={latitude}
                onChange={(event) =>
                  setLatitude(
                    event.target.value
                  )
                }
                placeholder="10.9601"
              />

              <small>
                −90 to +90
              </small>

            </label>


            <label className="change-input">

              <span>
                Longitude
              </span>

              <input
                type="number"
                step="0.0001"
                min="-180"
                max="180"
                value={longitude}
                onChange={(event) =>
                  setLongitude(
                    event.target.value
                  )
                }
                placeholder="78.0766"
              />

              <small>
                −180 to +180
              </small>

            </label>


            <label className="change-input">

              <span>
                Analysis Radius
              </span>

              <div className="input-with-unit">

                <input
                  type="number"
                  min="100"
                  max="10000"
                  step="100"
                  value={radius}
                  onChange={(event) =>
                    setRadius(
                      event.target.value
                    )
                  }
                  placeholder="2000"
                />

                <span>
                  m
                </span>

              </div>

              <small>
                100 m – 10 km
              </small>

            </label>

          </div>


          {/* Location summary */}

          <div
            className="change-location-summary"
            style={{
              marginTop: "18px",
            }}
          >

            <MapPin size={16} />

            <span>
              Selected:
            </span>

            <strong>

              {Number.isFinite(
                inputLatitude
              )
                ? inputLatitude.toFixed(4)
                : "—"}

              °,

              {" "}

              {Number.isFinite(
                inputLongitude
              )
                ? inputLongitude.toFixed(4)
                : "—"}

              °

            </strong>

            <span className="summary-divider">
              •
            </span>

            <Ruler size={15} />

            <strong>

              {Number.isFinite(
                inputRadius
              )
                ? inputRadius.toLocaleString()
                : "—"}

              {" "}m

            </strong>

          </div>


          {/* =================================================
              OBSERVATION DATES
          ================================================= */}

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "1fr",
              gap: "14px",
              marginTop: "22px",
            }}
          >

            <label className="change-input">

              <span>

                <CalendarDays
                  size={15}
                />

                Reference Observation
              </span>

              <input
                type="date"
                value={beforeDate}
                onChange={(event) =>
                  setBeforeDate(
                    event.target.value
                  )
                }
              />

              <small>
                Earlier satellite observation
              </small>

            </label>


            <label className="change-input">

              <span>

                <CalendarDays
                  size={15}
                />

                Comparison Observation
              </span>

              <input
                type="date"
                value={afterDate}
                onChange={(event) =>
                  setAfterDate(
                    event.target.value
                  )
                }
              />

              <small>
                Later satellite observation
              </small>

            </label>

          </div>


          {/* =================================================
              RUN BUTTON
          ================================================= */}

          <button
            className="primary-btn"
            onClick={run}
            disabled={busy}
            style={{
              width: "100%",
              marginTop: "22px",
              minHeight: "46px",
            }}
          >

            {busy ? (

              <>
                <RefreshCw
                  size={17}
                  className="spin"
                />

                Running...
              </>

            ) : (

              <>
                <Layers3 size={17} />

                Run Change Analysis
              </>

            )}

          </button>

        </div>


        {/* =================================================
            RIGHT — SQUARE MAP
        ================================================= */}

        <div
          className="panel"
          style={{
            minWidth: 0,
          }}
        >

          <div className="panel-heading">

            <div>

              <h3>
                Location Map
              </h3>

              <p className="muted">
                Search a city, then click the exact point.
              </p>

            </div>

            <MapPin size={19} />

          </div>


          <div
            className="change-location-picker"
            style={{
              position: "relative",
              marginTop: "16px",
              borderRadius: "14px",
              overflow: "hidden",
              border:
                "1px solid rgba(255,255,255,0.08)",
              width: "100%",
              aspectRatio: "1 / 1",
            }}
          >

            <MapContainer
              center={[
                Number.isFinite(
                  inputLatitude
                )
                  ? inputLatitude
                  : 10.9601,

                Number.isFinite(
                  inputLongitude
                )
                  ? inputLongitude
                  : 78.0766,
              ]}
              zoom={12}
              scrollWheelZoom={true}
              style={{
                height: "100%",
                width: "100%",
              }}
            >

              <TileLayer
                attribution="Tiles © Esri"
                url={
                  "https://server.arcgisonline.com/ArcGIS/rest/services/" +
                  "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                }
                maxNativeZoom={19}
                maxZoom={19}
              />


              <LocationMapClick
                onLocationSelect={
                  selectMapLocation
                }
              />


              <MapCenter
                latitude={
                  Number.isFinite(
                    inputLatitude
                  )
                    ? inputLatitude
                    : 10.9601
                }
                longitude={
                  Number.isFinite(
                    inputLongitude
                  )
                    ? inputLongitude
                    : 78.0766
                }
                zoom={13}
              />


              {/* Analysis radius */}

              {Number.isFinite(
                inputLatitude
              ) &&
                Number.isFinite(
                  inputLongitude
                ) &&
                Number.isFinite(
                  inputRadius
                ) &&
                inputRadius >= 100 && (

                  <Circle
                    center={[
                      inputLatitude,
                      inputLongitude,
                    ]}
                    radius={
                      inputRadius
                    }
                    pathOptions={{
                      color:
                        "#70e6a0",
                      weight: 2,
                      fillColor:
                        "#70e6a0",
                      fillOpacity:
                        0.08,
                    }}
                  />

                )}


              {/* Outer marker */}

              {Number.isFinite(
                inputLatitude
              ) &&
                Number.isFinite(
                  inputLongitude
                ) && (

                  <CircleMarker
                    center={[
                      inputLatitude,
                      inputLongitude,
                    ]}
                    radius={14}
                    pathOptions={{
                      color:
                        "#ffffff",
                      weight: 2,
                      fillColor:
                        "#ffffff",
                      fillOpacity:
                        0.15,
                    }}
                  />

                )}


              {/* Main marker */}

              {Number.isFinite(
                inputLatitude
              ) &&
                Number.isFinite(
                  inputLongitude
                ) && (

                  <CircleMarker
                    center={[
                      inputLatitude,
                      inputLongitude,
                    ]}
                    radius={7}
                    pathOptions={{
                      color:
                        "#70e6a0",
                      weight: 2,
                      fillColor:
                        "#70e6a0",
                      fillOpacity:
                        1,
                    }}
                  >

                    <Popup>

                      <strong>
                        SylvaSense Analysis Location
                      </strong>

                      <br />

                      Latitude:{" "}
                      {inputLatitude.toFixed(6)}

                      <br />

                      Longitude:{" "}
                      {inputLongitude.toFixed(6)}

                      <br />

                      Radius:{" "}
                      {Number.isFinite(
                        inputRadius
                      )
                        ? inputRadius.toLocaleString()
                        : "—"}{" "}
                      m

                    </Popup>

                  </CircleMarker>

                )}

            </MapContainer>


            {/* Instruction */}

            <div
              style={{
                position: "absolute",
                left: "12px",
                top: "12px",
                zIndex: 1000,
                display: "flex",
                alignItems: "center",
                gap: "7px",
                padding: "8px 10px",
                borderRadius: "9px",
                background:
                  "rgba(10,18,15,0.88)",
                color: "#ffffff",
                fontSize: "12px",
                pointerEvents: "none",
                backdropFilter:
                  "blur(8px)",
              }}
            >

              <MapPin size={14} />

              <span>
                Click exact location
              </span>

            </div>


            {/* Coordinates */}

            <div
              style={{
                position: "absolute",
                right: "12px",
                bottom: "12px",
                zIndex: 1000,
                display: "flex",
                alignItems: "center",
                gap: "7px",
                padding: "8px 10px",
                borderRadius: "9px",
                background:
                  "rgba(10,18,15,0.88)",
                color: "#ffffff",
                fontSize: "11px",
                pointerEvents: "none",
                backdropFilter:
                  "blur(8px)",
              }}
            >

              <CircleDot size={13} />

              <span>

                {Number.isFinite(
                  inputLatitude
                )
                  ? inputLatitude.toFixed(5)
                  : "—"}

                {" , "}

                {Number.isFinite(
                  inputLongitude
                )
                  ? inputLongitude.toFixed(5)
                  : "—"}

              </span>

            </div>

          </div>


          {/* Map help */}

          <div
            className="muted"
            style={{
              marginTop: "12px",
              fontSize: "12px",
              lineHeight: 1.5,
            }}
          >

            <strong>
              Workflow:
            </strong>{" "}

            Find city → map moves to city →
            click exact forest/location → run analysis.

          </div>

        </div>

      </div>


      {/* =================================================
          RUNNING
      ================================================= */}

      {busy && (

        <div className="panel">

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
            }}
          >

            <RefreshCw
              size={20}
              className="spin"
            />

            <div>

              <strong>
                Change detection is running
              </strong>

              <p className="muted">
                FastAPI is processing Sentinel-2
                imagery. You can switch pages;
                the backend analysis will continue.
              </p>

            </div>

          </div>

        </div>

      )}


      {/* =================================================
          ERROR
      ================================================= */}

      {error && (

        <div className="error-box">

          <X size={18} />

          <span>
            {error}
          </span>

        </div>

      )}


      {/* =================================================
          RESULTS
      ================================================= */}

      {data && (

        <>

          {/* =================================================
              RESULT LOCATION
          ================================================= */}

          <div className="change-result-location">

            <MapPin size={17} />

            <div>

              <span>
                ANALYSIS LOCATION
              </span>

              <strong>

                {mapLatitude.toFixed(4)}°
                {mapLatitude >= 0
                  ? " N"
                  : " S"}

                {", "}

                {Math.abs(
                  mapLongitude
                ).toFixed(4)}°

                {mapLongitude >= 0
                  ? " E"
                  : " W"}

              </strong>

            </div>


            <div className="result-location-divider" />


            <div>

              <span>
                AREA RADIUS
              </span>

              <strong>
                {mapRadius.toLocaleString()} m
              </strong>

            </div>

          </div>


          {/* =================================================
              METRICS
          ================================================= */}

          <div className="metric-grid change-metrics">

            <div className="metric-card">

              <div className="metric-icon">
                <CalendarDays size={20} />
              </div>

              <div className="metric-label">
                Reference Scenes
              </div>

              <div className="metric-value">
                {before.scene_count ?? "—"}
              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">
                <CalendarDays size={20} />
              </div>

              <div className="metric-label">
                Comparison Scenes
              </div>

              <div className="metric-value">
                {after.scene_count ?? "—"}
              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">

                {meanChange !== null &&
                meanChange < 0 ? (

                  <TrendingDown
                    size={20}
                  />

                ) : (

                  <TrendingUp
                    size={20}
                  />

                )}

              </div>

              <div className="metric-label">
                Mean NDVI Change
              </div>

              <div className="metric-value">

                {meanChange !== null
                  ? meanChange.toFixed(3)
                  : "—"}

              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">
                <TrendingDown
                  size={20}
                />
              </div>

              <div className="metric-label">
                Vegetation Decrease
              </div>

              <div className="metric-value">

                {decreasePixels !== null
                  ? decreasePixels.toLocaleString()
                  : "—"}

              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">
                <TrendingUp
                  size={20}
                />
              </div>

              <div className="metric-label">
                Vegetation Increase
              </div>

              <div className="metric-value">

                {increasePixels !== null
                  ? increasePixels.toLocaleString()
                  : "—"}

              </div>

            </div>

          </div>


          {/* =================================================
              RESULT MAP + LAYERS
          ================================================= */}

          <div className="two-column">

            {/* =================================================
                RESULT MAP
            ================================================= */}

            <div className="panel">

              <div className="panel-heading">

                <div>

                  <h3>
                    NDVI Change Map
                  </h3>

                  <p className="muted">
                    {changeDirection}
                  </p>

                </div>

                <CircleDot size={19} />

              </div>


              <div
                className="change-map"
                style={{
                  position: "relative",
                  width: "100%",
                  aspectRatio: "1 / 1",
                  maxHeight: "620px",
                  overflow: "hidden",
                  borderRadius: "14px",
                }}
              >

                <MapContainer
                  center={[
                    mapLatitude,
                    mapLongitude,
                  ]}
                  zoom={12}
                  scrollWheelZoom={true}
                  className="change-leaflet-map"
                  style={{
                    height: "100%",
                    width: "100%",
                  }}
                >

                  {/* Satellite base */}

                  <TileLayer
                    attribution="Tiles © Esri"
                    url={
                      "https://server.arcgisonline.com/ArcGIS/rest/services/" +
                      "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    }
                    maxNativeZoom={19}
                    maxZoom={19}
                  />


                  {/* Actual backend change layer */}

                  {activeLayerData?.tile_url && (

                    <TileLayer
                      key={
                        activeLayerData.id
                      }
                      url={
                        activeLayerData.tile_url
                      }
                      opacity={0.92}
                      zIndex={10}
                    />

                  )}


                  {/* Analysis radius */}

                  <Circle
                    center={[
                      mapLatitude,
                      mapLongitude,
                    ]}
                    radius={
                      mapRadius
                    }
                    pathOptions={{
                      color:
                        "#70e6a0",
                      weight: 2,
                      fillColor:
                        "#70e6a0",
                      fillOpacity:
                        0.04,
                    }}
                  />


                  {/* Marker */}

                  <CircleMarker
                    center={[
                      mapLatitude,
                      mapLongitude,
                    ]}
                    radius={13}
                    pathOptions={{
                      color:
                        "#ffffff",
                      weight: 2,
                      fillColor:
                        "#ffffff",
                      fillOpacity:
                        0.15,
                    }}
                  />


                  <CircleMarker
                    center={[
                      mapLatitude,
                      mapLongitude,
                    ]}
                    radius={7}
                    pathOptions={{
                      color:
                        "#70e6a0",
                      weight: 2,
                      fillColor:
                        "#70e6a0",
                      fillOpacity:
                        1,
                    }}
                  >

                    <Popup>

                      <strong>
                        SylvaSense Analysis Area
                      </strong>

                      <br />

                      Latitude:{" "}
                      {mapLatitude.toFixed(5)}

                      <br />

                      Longitude:{" "}
                      {mapLongitude.toFixed(5)}

                      <br />

                      Radius:{" "}
                      {mapRadius.toLocaleString()} m

                    </Popup>

                  </CircleMarker>


                  <MapCenter
                    latitude={
                      mapLatitude
                    }
                    longitude={
                      mapLongitude
                    }
                    zoom={12}
                  />

                </MapContainer>


                {/* Location badge */}

                <div className="change-map-location-badge">

                  <MapPin size={15} />

                  <span>

                    {mapLatitude.toFixed(4)}
                    ,
                    {" "}
                    {mapLongitude.toFixed(4)}

                  </span>

                </div>


                {/* Layer badge */}

                <div className="change-map-layer-badge">

                  <Layers3 size={14} />

                  <span>

                    {activeLayerData?.name ||
                      "NDVI Change"}

                  </span>

                </div>


                {/* Change summary */}

                <div
                  style={{
                    position: "absolute",
                    left: "12px",
                    bottom: "12px",
                    zIndex: 1000,
                    padding:
                      "8px 11px",
                    borderRadius:
                      "9px",
                    background:
                      "rgba(10,18,15,0.88)",
                    color:
                      "#ffffff",
                    fontSize:
                      "11px",
                    backdropFilter:
                      "blur(8px)",
                  }}
                >

                  Mean NDVI:{" "}

                  <strong>

                    {meanChange !== null
                      ? meanChange.toFixed(3)
                      : "—"}

                  </strong>

                </div>

              </div>


              {/* Map interpretation */}

              <div
                style={{
                  marginTop: "12px",
                  padding:
                    "10px 12px",
                  borderRadius:
                    "10px",
                  background:
                    "rgba(255,255,255,0.04)",
                  fontSize: "12px",
                }}
              >

                <strong>
                  Change layer:
                </strong>{" "}

                {activeLayerData?.name ||
                  "NDVI Change"}

                <br />

                <span className="muted">

                  Negative values indicate NDVI
                  decrease; positive values indicate
                  NDVI increase.

                </span>

              </div>

            </div>


            {/* =================================================
                LAYERS + PERIODS
            ================================================= */}

            <div className="panel">

              <div className="panel-heading">

                <div>

                  <h3>
                    Analysis Layers
                  </h3>

                  <p className="muted">
                    Select a layer to inspect
                  </p>

                </div>

                <Layers3 size={19} />

              </div>


              <div className="change-layer-list">

                {layers.map(
                  (layer) => (

                    <button
                      key={layer.id}
                      className={
                        activeLayer ===
                        layer.id
                          ? "change-layer-btn active"
                          : "change-layer-btn"
                      }
                      onClick={() =>
                        updateActiveLayer(
                          layer.id
                        )
                      }
                    >

                      <div>

                        <strong>
                          {layer.name}
                        </strong>

                        <span>

                          {layer.type ===
                          "change"
                            ? "Vegetation difference"
                            : "Vegetation index"}

                        </span>

                      </div>

                      <ChevronRight
                        size={18}
                      />

                    </button>

                  )
                )}

              </div>


              {/* =================================================
                  OBSERVATION PERIOD
              ================================================= */}

              <div className="change-date-box">

                <div>

                  <span>
                    REFERENCE OBSERVATION
                  </span>

                  <strong>
                    {before.date ||
                      beforeDate}
                  </strong>

                  <small>

                    {before.scene_count ??
                      0}{" "}
                    scenes

                  </small>

                </div>


                <ChevronRight
                  size={20}
                />


                <div>

                  <span>
                    COMPARISON OBSERVATION
                  </span>

                  <strong>
                    {after.date ||
                      afterDate}
                  </strong>

                  <small>

                    {after.scene_count ??
                      0}{" "}
                    scenes

                  </small>

                </div>

              </div>

            </div>

          </div>


          {/* =================================================
              STATISTICS
          ================================================= */}

          <div className="two-column">

            <div className="panel">

              <h3>
                NDVI Statistics
              </h3>

              <div className="stats-list">

                <div className="stat-row">

                  <span>
                    Mean change
                  </span>

                  <strong>

                    {meanChange !== null
                      ? fmt(
                          meanChange,
                          4
                        )
                      : "—"}

                  </strong>

                </div>


                <div className="stat-row">

                  <span>
                    Minimum change
                  </span>

                  <strong>

                    {minChange !== null
                      ? fmt(
                          minChange,
                          4
                        )
                      : "—"}

                  </strong>

                </div>


                <div className="stat-row">

                  <span>
                    Maximum change
                  </span>

                  <strong>

                    {maxChange !== null
                      ? fmt(
                          maxChange,
                          4
                        )
                      : "—"}

                  </strong>

                </div>


                <div className="stat-row">

                  <span>
                    Decrease threshold
                  </span>

                  <strong>

                    {change.decrease_threshold !==
                    undefined
                      ? fmt(
                          change.decrease_threshold,
                          2
                        )
                      : "—"}

                  </strong>

                </div>


                <div className="stat-row">

                  <span>
                    Increase threshold
                  </span>

                  <strong>

                    {change.increase_threshold !==
                    undefined
                      ? fmt(
                          change.increase_threshold,
                          2
                        )
                      : "—"}

                  </strong>

                </div>

              </div>

            </div>


            <div className="panel">

              <h3>
                Vegetation Change Summary
              </h3>

              <div className="change-pixel-grid">

                <div className="change-pixel-card decrease">

                  <TrendingDown
                    size={22}
                  />

                  <span>
                    Vegetation Decrease
                  </span>

                  <strong>

                    {decreasePixels !== null
                      ? decreasePixels.toLocaleString()
                      : "—"}

                  </strong>

                  <small>
                    pixels beyond decrease threshold
                  </small>

                </div>


                <div className="change-pixel-card increase">

                  <TrendingUp
                    size={22}
                  />

                  <span>
                    Vegetation Increase
                  </span>

                  <strong>

                    {increasePixels !== null
                      ? increasePixels.toLocaleString()
                      : "—"}

                  </strong>

                  <small>
                    pixels beyond increase threshold
                  </small>

                </div>

              </div>

            </div>

          </div>


          {/* =================================================
              INTERPRETATION
          ================================================= */}

          <div className="notice">

            <Layers3 size={19} />

            <span>

              {data?.interpretation?.note ||
                "NDVI change represents the difference between the reference and comparison observation periods."}

            </span>

          </div>

        </>

      )}


      {/* =================================================
          EMPTY STATE
      ================================================= */}

      {!data &&
        !busy &&
        !error && (

          <div className="panel change-empty-panel">

            <Layers3 size={34} />

            <h3>
              Ready for Change Analysis
            </h3>

            <p>

              Enter the country, state/province and
              city. Click Find City, confirm the map
              position, click the exact analysis point,
              select the observation dates, and run
              the analysis.

            </p>

          </div>

        )}

    </>
  );
}