import React, { useEffect } from "react";

import {
  AlertCircle,
  Cloud,
  FileImage,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Satellite as SatelliteIcon,
  Send,
  Target,
  Trees,
} from "lucide-react";

import {
  MapContainer,
  TileLayer,
  Marker,
  Circle,
  useMap,
  useMapEvents,
} from "react-leaflet";

import L from "leaflet";

import { api } from "../services/api";

import "leaflet/dist/leaflet.css";


/* =========================================================
   DEFAULT LOCATION
========================================================= */

const DEFAULT_LATITUDE = 10.1;
const DEFAULT_LONGITUDE = 77.05;
const DEFAULT_RADIUS = 2000;
const DEFAULT_CLOUD_PCT = 15;


/* =========================================================
   LEAFLET MARKER
========================================================= */

const markerIcon = new L.Icon({
  iconUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",

  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",

  shadowUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",

  iconSize: [25, 41],

  iconAnchor: [12, 41],

  popupAnchor: [1, -34],

  shadowSize: [41, 41],
});


/* =========================================================
   MAP CENTER
========================================================= */

function MapCenter({
  latitude,
  longitude,
}) {
  const map = useMap();

  useEffect(() => {
    const lat = Number(latitude);
    const lng = Number(longitude);

    if (
      Number.isFinite(lat) &&
      Number.isFinite(lng) &&
      lat >= -90 &&
      lat <= 90 &&
      lng >= -180 &&
      lng <= 180
    ) {
      map.setView(
        [lat, lng],
        Math.max(map.getZoom(), 11),
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
   MAP CLICK SELECTOR
========================================================= */

function MapClickSelector({
  onSelect,
  disabled,
}) {
  useMapEvents({
    click(event) {
      if (disabled) {
        return;
      }

      onSelect(
        event.latlng.lat,
        event.latlng.lng
      );
    },
  });

  return null;
}


/* =========================================================
   SATELLITE PAGE
========================================================= */

function SatellitePage({
  onImageReady,
  onNavigate,

  /* GLOBAL ANALYSIS */
  analysisRunning,
  analysisType,
  analysisStatus,
  analysisError,

  startAnalysis,
  updateAnalysis,
  finishAnalysis,
  failAnalysis,

  /* GLOBAL SATELLITE STATE */
  satelliteState,
  setSatelliteState,
}) {

  /* =======================================================
     SAFE STATE
  ======================================================= */

  const safeState =
    satelliteState || {};


  const latitude =
    safeState.latitude ??
    DEFAULT_LATITUDE;


  const longitude =
    safeState.longitude ??
    DEFAULT_LONGITUDE;


  const radius =
    safeState.radius ??
    DEFAULT_RADIUS;


  const locationName =
    safeState.locationName ||
    "Forest Area";


  const cloudPct =
    safeState.cloudPct ??
    DEFAULT_CLOUD_PCT;


  const result =
    safeState.result ||
    null;


  const satelliteImage =
    safeState.satelliteImage ||
    null;


  const error =
    safeState.error ||
    "";


  const sendingToAnalysis =
    safeState.sendingToAnalysis ||
    false;


  /* =======================================================
     GLOBAL ANALYSIS STATUS
  ======================================================= */

  const satelliteRunning =
    analysisRunning &&
    analysisType ===
      "Satellite Intelligence";


  const analysisLocked =
    analysisRunning;


  /* =======================================================
     STATE UPDATE
  ======================================================= */

  function updateSatelliteState(
    updates
  ) {
    if (
      typeof setSatelliteState !==
      "function"
    ) {
      console.error(
        "setSatelliteState is not available."
      );

      return;
    }

    setSatelliteState(
      previous => ({
        ...previous,
        ...updates,
      })
    );
  }


  /* =======================================================
     MAP LOCATION SELECT
  ======================================================= */

  function selectMapLocation(
    lat,
    lng
  ) {
    if (analysisRunning) {
      return;
    }

    const safeLat =
      Number(lat);

    const safeLng =
      Number(lng);

    if (
      !Number.isFinite(
        safeLat
      ) ||
      !Number.isFinite(
        safeLng
      )
    ) {
      return;
    }

    const newLatitude =
      Number(
        safeLat.toFixed(6)
      );

    const newLongitude =
      Number(
        safeLng.toFixed(6)
      );

    updateSatelliteState({

      latitude:
        newLatitude,

      longitude:
        newLongitude,

      locationName:
        "Selected Forest Area",

      result:
        null,

      satelliteImage:
        null,

      error:
        "",
    });
  }


  /* =======================================================
     RUN SATELLITE ANALYSIS
  ======================================================= */

  async function runSatelliteAnalysis() {

    if (
      analysisRunning
    ) {
      return;
    }

    const numericLatitude =
      Number(latitude);

    const numericLongitude =
      Number(longitude);

    const numericRadius =
      Number(radius);

    const numericCloudPct =
      Number(cloudPct);


    /* -------------------------------------------------------
       VALIDATE COORDINATES
    ------------------------------------------------------- */

    if (
      !Number.isFinite(
        numericLatitude
      ) ||
      !Number.isFinite(
        numericLongitude
      )
    ) {

      updateSatelliteState({
        error:
          "Please enter valid latitude and longitude.",
      });

      return;
    }


    if (
      numericLatitude < -90 ||
      numericLatitude > 90
    ) {

      updateSatelliteState({
        error:
          "Latitude must be between -90 and 90.",
      });

      return;
    }


    if (
      numericLongitude < -180 ||
      numericLongitude > 180
    ) {

      updateSatelliteState({
        error:
          "Longitude must be between -180 and 180.",
      });

      return;
    }


    /* -------------------------------------------------------
       VALIDATE RADIUS
    ------------------------------------------------------- */

    if (
      !Number.isFinite(
        numericRadius
      ) ||
      numericRadius < 100 ||
      numericRadius > 10000
    ) {

      updateSatelliteState({
        error:
          "Radius must be between 100 m and 10,000 m.",
      });

      return;
    }


    /* -------------------------------------------------------
       VALIDATE CLOUD LIMIT
    ------------------------------------------------------- */

    if (
      !Number.isFinite(
        numericCloudPct
      ) ||
      numericCloudPct < 0 ||
      numericCloudPct > 100
    ) {

      updateSatelliteState({
        error:
          "Cloud limit must be between 0 and 100%.",
      });

      return;
    }


    /* -------------------------------------------------------
       START
    ------------------------------------------------------- */

    startAnalysis?.(
      "Satellite Intelligence",
      "Retrieving Sentinel-2 satellite imagery..."
    );


    updateSatelliteState({

      latitude:
        numericLatitude,

      longitude:
        numericLongitude,

      radius:
        numericRadius,

      cloudPct:
        numericCloudPct,

      error:
        "",

      sendingToAnalysis:
        false,
    });


    try {

      updateAnalysis?.(
        "Searching Earth Engine for Sentinel-2 observations..."
      );


      /* -----------------------------------------------------
         BACKEND REQUEST
      ----------------------------------------------------- */

      const response =
        await api.satelliteAnalysis({

          latitude:
            numericLatitude,

          longitude:
            numericLongitude,

          radius_m:
            numericRadius,

          /*
           * Automatic wide observation window.
           * User does not need to select dates.
           */
          start_date:
            "2020-01-01",

          end_date:
            new Date()
              .toISOString()
              .split("T")[0],

          max_cloud_pct:
            numericCloudPct,

          gedi_start_date:
            "2019-03-25",

          gedi_end_date:
            "2024-11-30",

          include_sar:
            true,
        });


      console.log(
        "Satellite Intelligence response:",
        response
      );


      /* -----------------------------------------------------
         RESPONSE CHECK
      ----------------------------------------------------- */

      if (
        response?.status !==
        "success"
      ) {

        throw new Error(
          response?.message ||
          response?.detail ||
          "Satellite analysis was not successful."
        );
      }


      updateAnalysis?.(
        "Satellite image received. Preparing result..."
      );


      /* -----------------------------------------------------
         IMAGE
      ----------------------------------------------------- */

      const image =
        response?.satellite_image;


      if (
        !image?.available
      ) {

        throw new Error(
          "No suitable Sentinel-2 satellite image was found for this location."
        );
      }


      if (
        typeof image.data_url !==
          "string" ||
        !image.data_url.startsWith(
          "data:image/"
        )
      ) {

        throw new Error(
          "The satellite service did not return a valid image."
        );
      }


      /* -----------------------------------------------------
         SAVE RESULT
      ----------------------------------------------------- */

      updateSatelliteState({

        result:
          response,

        satelliteImage:
          image,

        error:
          "",

        sendingToAnalysis:
          false,
      });


      /* -----------------------------------------------------
         COMPLETE
      ----------------------------------------------------- */

      finishAnalysis?.(
        response
      );

    } catch (err) {

      console.error(
        "Satellite analysis failed:",
        err
      );


      const message =
        err?.message ||
        "Unable to retrieve the satellite image.";


      updateSatelliteState({
        error:
          message,

        sendingToAnalysis:
          false,
      });


      failAnalysis?.(
        err
      );
    }
  }


  /* =======================================================
     SEND IMAGE TO IMAGE ANALYSIS
  ======================================================= */

  async function sendToImageAnalysis() {

    if (
      !satelliteImage?.data_url
    ) {

      updateSatelliteState({
        error:
          "No satellite image is available.",
      });

      return;
    }


    updateSatelliteState({

      sendingToAnalysis:
        true,

      error:
        "",
    });


    try {

      const dataUrl =
        satelliteImage.data_url;


      const parts =
        dataUrl.split(",");


      if (
        parts.length !== 2
      ) {

        throw new Error(
          "The satellite image data is invalid."
        );
      }


      const metadata =
        parts[0];


      const base64Data =
        parts[1];


      const mimeMatch =
        metadata.match(
          /data:(.*?);base64/
        );


      const mimeType =
        mimeMatch?.[1] ||
        "image/png";


      const binaryString =
        window.atob(
          base64Data
        );


      const length =
        binaryString.length;


      const bytes =
        new Uint8Array(
          length
        );


      for (
        let i = 0;
        i < length;
        i++
      ) {

        bytes[i] =
          binaryString.charCodeAt(i);
      }


      const blob =
        new Blob(
          [bytes],
          {
            type:
              mimeType,
          }
        );


      const extension =
        mimeType === "image/jpeg"
          ? "jpg"
          : "png";


      const file =
        new File(
          [blob],
          `sentinel-2-${Date.now()}.${extension}`,
          {
            type:
              mimeType,
          }
        );


      console.log(
        "Satellite image converted to File:",
        file
      );


      if (
        typeof onImageReady ===
        "function"
      ) {

        onImageReady(
          file
        );
      }


      if (
        typeof onNavigate ===
        "function"
      ) {

        onNavigate(
          "image"
        );
      }

    } catch (err) {

      console.error(
        "Sending satellite image to Image Analysis failed:",
        err
      );


      updateSatelliteState({
        error:
          err?.message ||
          "The satellite image could not be sent to Image Analysis.",
      });

    } finally {

      updateSatelliteState({
        sendingToAnalysis:
          false,
      });
    }
  }


  /* =======================================================
     CLEAR RESULT
  ======================================================= */

  function clearSatelliteResult() {

    if (
      analysisRunning
    ) {
      return;
    }


    updateSatelliteState({

      result:
        null,

      satelliteImage:
        null,

      error:
        "",

      sendingToAnalysis:
        false,
    });
  }


  /* =======================================================
     SCENE COUNT
  ======================================================= */

  const sceneCount =
    satelliteImage?.scene_count ??
    result?.sentinel
      ?.sentinel_2
      ?.scene_count;


  /* =======================================================
     SATELLITE TYPE
  ======================================================= */

  const satelliteType =
    satelliteImage?.type ||
    "Sentinel-2 RGB";


  /* =======================================================
     IMAGE DATE
  ======================================================= */

  const imageDate =
    satelliteImage?.date ||
    satelliteImage?.acquisition_date ||
    satelliteImage?.scene_date ||
    null;


  /* =======================================================
     GLOBAL ERROR
  ======================================================= */

  const visibleError =
    error ||
    (
      analysisError &&
      analysisType ===
        "Satellite Intelligence"
        ? analysisError
        : ""
    );


  /* =======================================================
     UI
  ======================================================= */

  return (

    <main className="dashboard">

      {/* ===================================================
          HEADER
      =================================================== */}

      <div className="dashboard-header">

        <div>

          <div className="dashboard-title">

            <SatelliteIcon
              size={30}
            />

            <h1>
              Satellite Intelligence
            </h1>

          </div>


          <p>
            Select a forest location and retrieve
            real Sentinel-2 satellite imagery.
          </p>

        </div>


        {satelliteRunning && (

          <div
            className="badge"
            style={{
              display:
                "flex",

              alignItems:
                "center",

              gap:
                "7px",

              padding:
                "9px 13px",
            }}
          >

            <LoaderCircle
              size={16}
              className="spin"
            />

            Retrieving imagery...

          </div>

        )}


        {satelliteImage &&
          !analysisRunning && (

            <button
              className="secondary-btn"
              onClick={
                clearSatelliteResult
              }
            >

              <RefreshCw
                size={17}
              />

              New Image

            </button>

          )}

      </div>


      {/* ===================================================
          GLOBAL STATUS
      =================================================== */}

      {satelliteRunning && (

        <div
          className="panel"
          style={{
            marginBottom:
              "18px",

            border:
              "1px solid rgba(74,211,132,0.25)",

            background:
              "rgba(31,126,76,0.08)",
          }}
        >

          <div
            style={{
              display:
                "flex",

              alignItems:
                "center",

              gap:
                "12px",
            }}
          >

            <LoaderCircle
              size={25}
              className="spin"
            />


            <div>

              <strong>
                Satellite analysis in progress
              </strong>


              <p
                style={{
                  marginTop:
                    "5px",
                }}
              >

                {analysisStatus ||
                  "Retrieving Sentinel-2 satellite imagery..."}

              </p>

            </div>

          </div>

        </div>

      )}


      {/* ===================================================
          ERROR
      =================================================== */}

      {visibleError && (

        <div className="error-box">

          <AlertCircle
            size={19}
          />

          <span>
            {visibleError}
          </span>

        </div>

      )}


      {/* ===================================================
          LOCATION + SQUARE MAP
      =================================================== */}

      <div
        className="dashboard-grid"
        style={{
          gridTemplateColumns:
            "320px minmax(0, 1fr)",

          gap:
            "18px",

          alignItems:
            "start",
        }}
      >

        {/* =================================================
            LEFT SIDE
        ================================================= */}

        <div
          className="panel"
          style={{
            padding:
              "18px",
          }}
        >

          <div className="panel-head">

            <div>

              <h3>
                Forest Location
              </h3>

              <p>
                Set the analysis location.
              </p>

            </div>


            <Target
              size={21}
            />

          </div>


          {/* LOCATION NAME */}

          <div
            style={{
              display:
                "flex",

              alignItems:
                "center",

              gap:
                "8px",

              marginBottom:
                "14px",

              padding:
                "10px 11px",

              borderRadius:
                "9px",

              background:
                "rgba(31,126,76,0.08)",

              border:
                "1px solid rgba(74,211,132,0.16)",
            }}
          >

            <MapPin
              size={17}
            />

            <strong>
              {locationName}
            </strong>

          </div>


          {/* COORDINATES */}

          <div
            style={{
              display:
                "grid",

              gridTemplateColumns:
                "1fr 1fr",

              gap:
                "10px",
            }}
          >

            <label>

              Latitude

              <input
                type="number"
                step="0.000001"
                min="-90"
                max="90"
                value={
                  latitude
                }

                onChange={
                  event => {

                    const value =
                      event.target.value;

                    if (
                      value === ""
                    ) {
                      return;
                    }

                    const number =
                      Number(value);

                    if (
                      Number.isFinite(
                        number
                      ) &&
                      number >= -90 &&
                      number <= 90
                    ) {

                      updateSatelliteState({

                        latitude:
                          number,

                        result:
                          null,

                        satelliteImage:
                          null,

                      });

                    }

                  }
                }

                disabled={
                  analysisLocked
                }

              />

            </label>


            <label>

              Longitude

              <input
                type="number"
                step="0.000001"
                min="-180"
                max="180"
                value={
                  longitude
                }

                onChange={
                  event => {

                    const value =
                      event.target.value;

                    if (
                      value === ""
                    ) {
                      return;
                    }

                    const number =
                      Number(value);

                    if (
                      Number.isFinite(
                        number
                      ) &&
                      number >= -180 &&
                      number <= 180
                    ) {

                      updateSatelliteState({

                        longitude:
                          number,

                        result:
                          null,

                        satelliteImage:
                          null,

                      });

                    }

                  }
                }

                disabled={
                  analysisLocked
                }

              />

            </label>

          </div>


          {/* RADIUS + CLOUD */}

          <div
            style={{
              display:
                "grid",

              gridTemplateColumns:
                "1fr 1fr",

              gap:
                "10px",

              marginTop:
                "11px",
            }}
          >

            <label>

              Radius (m)

              <input
                type="number"
                min="100"
                max="10000"
                value={
                  radius
                }

                onChange={
                  event =>
                    updateSatelliteState({
                      radius:
                        Number(
                          event.target.value
                        ),
                    })
                }

                disabled={
                  analysisLocked
                }

              />

            </label>


            <label>

              Cloud (%)

              <input
                type="number"
                min="0"
                max="100"
                value={
                  cloudPct
                }

                onChange={
                  event =>
                    updateSatelliteState({
                      cloudPct:
                        Number(
                          event.target.value
                        ),
                    })
                }

                disabled={
                  analysisLocked
                }

              />

            </label>

          </div>


          {/* LOCATION HINT */}

          <div
            style={{
              marginTop:
                "13px",

              padding:
                "10px",

              borderRadius:
                "8px",

              background:
                "rgba(255,255,255,0.025)",

              border:
                "1px solid rgba(255,255,255,0.07)",
            }}
          >

            <p
              style={{
                margin:
                  0,

                fontSize:
                  "12px",

                lineHeight:
                  1.45,

                opacity:
                  0.72,
              }}
            >
              Click anywhere on the satellite map to
              change the analysis location.
            </p>

          </div>


          {/* GET IMAGE */}

          <button
            className="primary-btn"

            style={{
              width:
                "100%",

              marginTop:
                "13px",

              justifyContent:
                "center",
            }}

            onClick={
              runSatelliteAnalysis
            }

            disabled={
              analysisLocked
            }
          >

            {satelliteRunning ? (

              <>

                <LoaderCircle
                  size={18}
                  className="spin"
                />

                Retrieving...

              </>

            ) : analysisRunning ? (

              <>

                <LoaderCircle
                  size={18}
                  className="spin"
                />

                Analysis Running...

              </>

            ) : (

              <>

                <SatelliteIcon
                  size={18}
                />

                Get Satellite Image

              </>

            )}

          </button>

        </div>


        {/* =================================================
            RIGHT SIDE — SQUARE MAP
        ================================================= */}

        <div
          className="panel"
          style={{
            padding:
              "12px",

            width:
              "100%",

            boxSizing:
              "border-box",
          }}
        >

          <div
            style={{
              display:
                "flex",

              alignItems:
                "center",

              justifyContent:
                "space-between",

              padding:
                "3px 5px 9px",
            }}
          >

            <div>

              <h3
                style={{
                  margin:
                    0,
                }}
              >
                Select Location on Map
              </h3>

              <p
                style={{
                  margin:
                    "4px 0 0",

                  fontSize:
                    "13px",

                  opacity:
                    0.7,
                }}
              >
                Click the map to move the analysis point.
              </p>

            </div>


            <MapPin
              size={21}
            />

          </div>


          {/* =================================================
              SQUARE MAP
          ================================================= */}

          <div
            className="map-card"
            style={{
              width:
                "100%",

              aspectRatio:
                "1 / 1",

              maxHeight:
                "520px",

              minHeight:
                "300px",

              overflow:
                "hidden",

              borderRadius:
                "12px",

              position:
                "relative",
            }}
          >

            <MapContainer

              center={[
                Number(latitude),
                Number(longitude),
              ]}

              zoom={11}

              minZoom={3}

              maxZoom={19}

              maxBounds={[
                [-85, -180],
                [85, 180],
              ]}

              maxBoundsViscosity={1}

              style={{
                width:
                  "100%",

                height:
                  "100%",
              }}

            >

              <TileLayer

                url={
                  "https://server.arcgisonline.com/ArcGIS/rest/services/" +
                  "World_Imagery/MapServer/tile/{z}/{y}/{x}"
                }

                attribution={
                  "Tiles © Esri"
                }

                maxNativeZoom={
                  19
                }

                maxZoom={
                  19
                }

              />


              <MapCenter
                latitude={
                  latitude
                }

                longitude={
                  longitude
                }
              />


              <MapClickSelector

                onSelect={
                  selectMapLocation
                }

                disabled={
                  analysisRunning
                }

              />


              <Marker

                position={[
                  Number(latitude),
                  Number(longitude),
                ]}

                icon={
                  markerIcon
                }

              />


              <Circle

                center={[
                  Number(latitude),
                  Number(longitude),
                ]}

                radius={
                  Number(radius)
                }

                pathOptions={{
                  color:
                    "#4ade80",

                  fillColor:
                    "#4ade80",

                  fillOpacity:
                    0.10,
                }}

              />

            </MapContainer>


            {/* MAP COORDINATE OVERLAY */}

            <div
              style={{
                position:
                  "absolute",

                left:
                  "10px",

                bottom:
                  "10px",

                zIndex:
                  1000,

                padding:
                  "7px 10px",

                borderRadius:
                  "8px",

                background:
                  "rgba(0,0,0,0.72)",

                backdropFilter:
                  "blur(6px)",

                fontSize:
                  "12px",

                fontWeight:
                  600,
              }}
            >

              {Number(latitude).toFixed(6)}

              {" , "}

              {Number(longitude).toFixed(6)}

            </div>

          </div>

        </div>

      </div>


      {/* ===================================================
          IMAGE RESULT
      =================================================== */}

      {satelliteImage && (

        <div
          className="panel"
          style={{
            marginTop:
              "18px",
          }}
        >

          <div className="panel-head">

            <div>

              <h3>
                Satellite Image
              </h3>

              <p>
                {satelliteType} captured for the selected
                forest region.
              </p>

              {imageDate && (

                <small
                  style={{
                    display:
                      "block",

                    marginTop:
                      "5px",

                    opacity:
                      0.7,
                  }}
                >
                  Acquisition date: {imageDate}
                </small>

              )}

            </div>


            <span
              className="badge success"
            >
              REAL SATELLITE DATA
            </span>

          </div>


          {/* IMAGE */}

          <div
            style={{
              width:
                "100%",

              borderRadius:
                "12px",

              overflow:
                "hidden",

              background:
                "#07110b",

              border:
                "1px solid rgba(255,255,255,0.08)",

              marginTop:
                "16px",
            }}
          >

            <img
              src={
                satelliteImage.data_url
              }

              alt="Sentinel-2 satellite view of selected forest"

              style={{
                display:
                  "block",

                width:
                  "100%",

                maxHeight:
                  "620px",

                objectFit:
                  "contain",
              }}

            />

          </div>


          {/* IMAGE DETAILS */}

          <div
            className="metrics-grid"
            style={{
              marginTop:
                "18px",
            }}
          >

            <div className="metric-card">

              <div className="metric-icon">

                <SatelliteIcon
                  size={20}
                />

              </div>

              <div className="metric-label">
                Source
              </div>

              <div className="metric-value">
                Sentinel-2
              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">

                <Trees
                  size={20}
                />

              </div>

              <div className="metric-label">
                RGB Bands
              </div>

              <div className="metric-value">
                B4 · B3 · B2
              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">

                <Cloud
                  size={20}
                />

              </div>

              <div className="metric-label">
                Cloud Limit
              </div>

              <div className="metric-value">

                {cloudPct}

                <span>
                  %
                </span>

              </div>

            </div>


            <div className="metric-card">

              <div className="metric-icon">

                <FileImage
                  size={20}
                />

              </div>

              <div className="metric-label">
                Scenes Found
              </div>

              <div className="metric-value">

                {sceneCount ??
                  "—"}

              </div>

            </div>

          </div>


          {/* IMAGE ANALYSIS HANDOFF */}

          <div
            style={{
              marginTop:
                "20px",

              padding:
                "18px",

              borderRadius:
                "10px",

              background:
                "rgba(31,126,76,0.09)",

              border:
                "1px solid rgba(74,211,132,0.22)",
            }}
          >

            <div
              style={{
                display:
                  "flex",

                alignItems:
                  "center",

                gap:
                  "12px",
              }}
            >

              <FileImage
                size={24}
              />


              <div
                style={{
                  flex:
                    1,
                }}
              >

                <strong>
                  Ready for Image Analysis
                </strong>


                <p
                  style={{
                    marginTop:
                      "5px",
                  }}
                >
                  Send this satellite image to the Image
                  Analysis module for tree detection, crown
                  analysis and forest measurements.
                </p>

              </div>


              <button
                className="primary-btn"

                onClick={
                  sendToImageAnalysis
                }

                disabled={
                  sendingToAnalysis
                }
              >

                {sendingToAnalysis ? (

                  <>

                    <LoaderCircle
                      size={17}
                      className="spin"
                    />

                    Preparing...

                  </>

                ) : (

                  <>

                    <Send
                      size={17}
                    />

                    Analyze Image

                  </>

                )}

              </button>

            </div>

          </div>

        </div>

      )}


      {/* ===================================================
          LOADING
      =================================================== */}

      {satelliteRunning &&
        !satelliteImage && (

          <div
            className="panel"
            style={{
              marginTop:
                "18px",

              textAlign:
                "center",

              padding:
                "40px",
            }}
          >

            <LoaderCircle
              size={35}
              className="spin"
            />


            <h3
              style={{
                marginTop:
                  "15px",
              }}
            >
              Acquiring satellite imagery
            </h3>


            <p>
              Earth Engine is searching for a suitable
              Sentinel-2 observation for this location.
            </p>


            <p
              style={{
                marginTop:
                  "10px",

                opacity:
                  0.75,
              }}
            >

              {analysisStatus ||
                "Please wait while the satellite data is retrieved."}

            </p>

          </div>

        )}

    </main>
  );
}


export default SatellitePage;