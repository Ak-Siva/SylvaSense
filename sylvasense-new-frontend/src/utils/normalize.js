// src/utils/normalize.js

export function fmt(value, digits = 2) {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  const number = Number(value);

  return number.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}


/* =========================================================
   SAFE NUMERIC VALUE
========================================================= */

export function safeNumber(value, fallback = null) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : fallback;
}


/* =========================================================
   SAFE STRING
========================================================= */

export function safeString(value, fallback = "") {
  if (
    value === null ||
    value === undefined
  ) {
    return fallback;
  }

  return String(value);
}


/* =========================================================
   FIND NUMERIC VALUE
========================================================= */

export function findNumericValue(
  object,
  keys = [],
  fallback = null
) {
  if (!object || typeof object !== "object") {
    return fallback;
  }

  for (const key of keys) {
    const value = object[key];

    if (
      value !== null &&
      value !== undefined &&
      value !== "" &&
      Number.isFinite(Number(value))
    ) {
      return Number(value);
    }
  }

  return fallback;
}


/* =========================================================
   CANOPY COVERAGE
========================================================= */

export function getCanopyCoverage(result) {
  if (!result) {
    return null;
  }

  const directValue = findNumericValue(result, [
    "canopy_coverage_percent",
    "canopyCoveragePercent",
    "canopy_coverage",
    "canopyCoverage",
  ]);

  if (directValue !== null) {
    return directValue;
  }

  const canopyPixels = findNumericValue(result, [
    "canopy_pixels",
    "canopyPixels",
  ]);

  const totalPixels = findNumericValue(result, [
    "total_image_pixels",
    "totalImagePixels",
    "image_pixels",
    "total_pixels",
  ]);

  if (
    canopyPixels !== null &&
    totalPixels !== null &&
    totalPixels > 0
  ) {
    return (canopyPixels / totalPixels) * 100;
  }

  return null;
}


/* =========================================================
   FORMAT CANOPY
========================================================= */

export function formatCanopyCoverage(result) {
  const value = getCanopyCoverage(result);

  if (value === null) {
    return "—";
  }

  return `${fmt(value, 2)}%`;
}


/* =========================================================
   NORMALIZE IMAGE ANALYSIS
========================================================= */

export function normalizeAnalysis(raw) {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  /*
   * Backend may return data directly or inside
   * result/data/analysis.
   */

  const source =
    raw.result ||
    raw.data ||
    raw.analysis ||
    raw;

  const treeCount = findNumericValue(source, [
    "tree_count",
    "treeCount",
    "trees_detected",
    "treesDetected",
    "detected_trees",
    "number_of_trees",
  ], 0);

  const crownCount = findNumericValue(source, [
    "crown_count",
    "crownCount",
    "crowns_detected",
    "crownsDetected",
    "detected_crowns",
    "number_of_crowns",
  ], treeCount);

  const agb = findNumericValue(source, [
    "total_agb_tonnes",
    "total_agb",
    "agb_tonnes",
    "agb",
    "aboveground_biomass",
    "aboveground_biomass_tonnes",
  ]);

  const carbon = findNumericValue(source, [
    "carbon_tonnes",
    "carbon",
    "total_carbon",
    "total_carbon_tonnes",
  ]);

  const co2e = findNumericValue(source, [
    "total_co2e_tonnes",
    "co2e_tonnes",
    "co2e",
    "total_co2e",
    "carbon_dioxide_equivalent",
  ]);

  const canopyCoverage = getCanopyCoverage(source);

  const totalCrownArea = findNumericValue(source, [
    "total_crown_area_m2",
    "total_crown_area",
    "crown_area_m2",
  ]);

  const canopyPixels = findNumericValue(source, [
    "canopy_pixels",
    "canopyPixels",
  ]);

  const totalImagePixels = findNumericValue(source, [
    "total_image_pixels",
    "totalImagePixels",
    "image_pixels",
    "total_pixels",
  ]);

  return {
    ...source,

    // Standard names
    tree_count: treeCount,
    crown_count: crownCount,

    total_agb_tonnes: agb,
    carbon: carbon,
    carbon_tonnes: carbon,

    total_co2e_tonnes: co2e,
    co2e: co2e,

    canopy_coverage_percent: canopyCoverage,

    total_crown_area_m2: totalCrownArea,

    canopy_pixels: canopyPixels,
    total_image_pixels: totalImagePixels,

    // Compatibility with older Dashboard code
    treeCount: treeCount,
    crownCount: crownCount,

    agb: agb,
    carbonValue: carbon,
    co2eValue: co2e,

    canopyCoveragePercent: canopyCoverage,
  };
}


/* =========================================================
   BACKEND STATUS
========================================================= */

export function extractStatusItems(status) {
  if (!status || typeof status !== "object") {
    return [];
  }

  const items = [];

  const source =
    status.modules ||
    status.services ||
    status.components ||
    status;

  if (
    source &&
    typeof source === "object" &&
    !Array.isArray(source)
  ) {
    Object.entries(source).forEach(
      ([name, value]) => {
        if (
          value === null ||
          value === undefined
        ) {
          return;
        }

        if (
          typeof value === "object" &&
          !Array.isArray(value)
        ) {
          const statusValue =
            value.status ??
            value.state ??
            value.available ??
            value.ready;

          if (
            statusValue !== undefined
          ) {
            items.push({
              name,
              value: statusValue
                ? "ready"
                : "offline",
            });
          }
        } else {
          items.push({
            name,
            value:
              typeof value === "boolean"
                ? value
                  ? "ready"
                  : "offline"
                : String(value),
          });
        }
      }
    );
  }

  return items;
}


/* =========================================================
   SATELLITE LAYER NORMALIZATION
========================================================= */

export function normalizeSatelliteLayers(
  satelliteResult
) {
  if (!satelliteResult) {
    return [];
  }

  const layers =
    satelliteResult.layers ||
    satelliteResult.layer_data ||
    satelliteResult.visualizations ||
    [];

  if (Array.isArray(layers)) {
    return layers.map((layer, index) => ({
      id:
        layer.id ||
        layer.name ||
        `layer-${index}`,

      name:
        layer.name ||
        layer.id ||
        `Layer ${index + 1}`,

      title:
        layer.title ||
        layer.name ||
        layer.id ||
        `Layer ${index + 1}`,

      tile_url:
        layer.tile_url ||
        layer.tileUrl ||
        layer.url ||
        layer.map_url ||
        "",

      url:
        layer.url ||
        layer.tile_url ||
        layer.tileUrl ||
        layer.map_url ||
        "",

      min:
        safeNumber(
          layer.min ??
          layer.minimum
        ),

      max:
        safeNumber(
          layer.max ??
          layer.maximum
        ),

      mean:
        safeNumber(
          layer.mean ??
          layer.average
        ),

      available:
        layer.available !== false,
    }));
  }

  /*
   * Some backend versions return layers as an object:
   *
   * {
   *   ndvi: {...},
   *   nir: {...}
   * }
   */

  if (
    typeof layers === "object" &&
    !Array.isArray(layers)
  ) {
    return Object.entries(layers).map(
      ([key, layer]) => {
        const value =
          layer && typeof layer === "object"
            ? layer
            : {};

        return {
          id: key,

          name:
            value.name ||
            key,

          title:
            value.title ||
            value.name ||
            key,

          tile_url:
            value.tile_url ||
            value.tileUrl ||
            value.url ||
            value.map_url ||
            "",

          url:
            value.url ||
            value.tile_url ||
            value.tileUrl ||
            value.map_url ||
            "",

          min: safeNumber(
            value.min ??
            value.minimum
          ),

          max: safeNumber(
            value.max ??
            value.maximum
          ),

          mean: safeNumber(
            value.mean ??
            value.average
          ),

          available:
            value.available !== false,
        };
      }
    );
  }

  return [];
}


/* =========================================================
   FIND SATELLITE LAYER
========================================================= */

export function findSatelliteLayer(
  layers,
  search
) {
  if (!Array.isArray(layers)) {
    return null;
  }

  const target =
    String(search || "")
      .trim()
      .toLowerCase();

  if (!target) {
    return null;
  }

  return (
    layers.find((layer) => {
      const text = [
        layer.id,
        layer.name,
        layer.title,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return (
        text === target ||
        text.includes(target)
      );
    }) || null
  );
}