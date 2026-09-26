// ============================================================
// SYLVASENSE - NORMALIZE API RESULTS
// ============================================================

/* ============================================================
   BASIC HELPERS
   ============================================================ */

export function safeNumber(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : fallback;
  }

  if (typeof value === "string") {
    const cleaned = value
      .replace(/,/g, "")
      .replace(/%/g, "")
      .trim();

    if (!cleaned) {
      return fallback;
    }

    const number = Number(cleaned);

    return Number.isFinite(number) ? number : fallback;
  }

  return fallback;
}

export function safeString(value, fallback = "") {
  if (value === null || value === undefined) {
    return fallback;
  }

  return String(value);
}

export function fmt(value, digits = 2) {
  const number = safeNumber(value);

  if (number === null) {
    return "—";
  }

  return number.toFixed(digits);
}

/* ============================================================
   DEEP SEARCH
   ============================================================ */

export function findNumericValue(
  object,
  keys = []
) {
  if (!object || typeof object !== "object") {
    return null;
  }

  for (const key of keys) {
    if (
      Object.prototype.hasOwnProperty.call(
        object,
        key
      )
    ) {
      const number = safeNumber(
        object[key]
      );

      if (number !== null) {
        return number;
      }
    }
  }

  return null;
}

export function findNumericValueDeep(
  value,
  keys = [],
  visited = new Set()
) {
  if (
    value === null ||
    value === undefined
  ) {
    return null;
  }

  if (
    typeof value !== "object"
  ) {
    return null;
  }

  if (visited.has(value)) {
    return null;
  }

  visited.add(value);

  /*
    Check exact keys first.
  */

  for (const key of keys) {
    if (
      Object.prototype.hasOwnProperty.call(
        value,
        key
      )
    ) {
      const number =
        safeNumber(value[key]);

      if (number !== null) {
        return number;
      }
    }
  }

  /*
    Search arrays.
  */

  if (Array.isArray(value)) {
    for (const item of value) {
      const result =
        findNumericValueDeep(
          item,
          keys,
          visited
        );

      if (result !== null) {
        return result;
      }
    }

    return null;
  }

  /*
    Search nested objects.
  */

  for (const child of Object.values(value)) {
    if (
      child &&
      typeof child === "object"
    ) {
      const result =
        findNumericValueDeep(
          child,
          keys,
          visited
        );

      if (result !== null) {
        return result;
      }
    }
  }

  return null;
}

/* ============================================================
   FIND VALUE BY PARTIAL KEY
   ============================================================ */

function findNumericByPartialKey(
  value,
  terms = [],
  visited = new Set()
) {
  if (
    value === null ||
    value === undefined ||
    typeof value !== "object"
  ) {
    return null;
  }

  if (visited.has(value)) {
    return null;
  }

  visited.add(value);

  /*
    Check object keys.
  */

  if (!Array.isArray(value)) {
    for (const [key, child] of Object.entries(value)) {
      const normalizedKey =
        String(key)
          .toLowerCase()
          .replace(/[\s-]/g, "_");

      const matches =
        terms.some((term) =>
          normalizedKey.includes(
            term.toLowerCase()
          )
        );

      if (matches) {
        const number =
          safeNumber(child);

        if (number !== null) {
          return number;
        }
      }

      if (
        child &&
        typeof child === "object"
      ) {
        const nested =
          findNumericByPartialKey(
            child,
            terms,
            visited
          );

        if (nested !== null) {
          return nested;
        }
      }
    }

    return null;
  }

  /*
    Arrays.
  */

  for (const item of value) {
    const result =
      findNumericByPartialKey(
        item,
        terms,
        visited
      );

    if (result !== null) {
      return result;
    }
  }

  return null;
}

/* ============================================================
   UNWRAP RESPONSE
   ============================================================ */

export function unwrapAnalysis(raw) {
  if (
    !raw ||
    typeof raw !== "object"
  ) {
    return raw;
  }

  let current = raw;

  const wrapperKeys = [
    "result",
    "data",
    "analysis",
    "response",
    "output",
  ];

  for (let i = 0; i < 10; i++) {
    let changed = false;

    for (const key of wrapperKeys) {
      const next =
        current?.[key];

      if (
        next &&
        typeof next === "object"
      ) {
        /*
          Only unwrap objects.
          Do not unwrap arrays because tree/crown
          arrays themselves may contain the required values.
        */

        if (!Array.isArray(next)) {
          current = next;
          changed = true;
          break;
        }
      }
    }

    if (!changed) {
      break;
    }
  }

  return current;
}

/* ============================================================
   TREE COUNT
   ============================================================ */

function getTreeCount(raw) {
  const keys = [
    "tree_count",
    "treeCount",
    "trees_detected",
    "treesDetected",
    "detected_trees",
    "detectedTrees",
    "number_of_trees",
    "numberOfTrees",
    "total_trees",
    "totalTrees",
    "tree_total",
    "treeTotal",
  ];

  let value =
    findNumericValueDeep(
      raw,
      keys
    );

  if (value !== null) {
    return value;
  }

  /*
    Try partial matching.
  */

  value =
    findNumericByPartialKey(
      raw,
      [
        "tree_count",
        "trees_detected",
        "detected_trees",
        "number_of_trees",
      ]
    );

  return value ?? 0;
}

/* ============================================================
   CROWN COUNT
   ============================================================ */

function getCrownCount(
  raw,
  treeCount
) {
  const keys = [
    "crown_count",
    "crownCount",
    "crowns_detected",
    "crownsDetected",
    "detected_crowns",
    "detectedCrowns",
    "number_of_crowns",
    "numberOfCrowns",
    "total_crowns",
    "totalCrowns",
    "crown_total",
    "crownTotal",
  ];

  let value =
    findNumericValueDeep(
      raw,
      keys
    );

  if (value !== null) {
    return value;
  }

  value =
    findNumericByPartialKey(
      raw,
      [
        "crown_count",
        "crowns_detected",
        "detected_crowns",
        "number_of_crowns",
      ]
    );

  return value ?? treeCount;
}

/* ============================================================
   ABOVEGROUND BIOMASS
   ============================================================ */

function getAGB(raw) {
  /*
    Exact fields.
  */

  const exactKeys = [
    "agb",
    "AGB",

    "agb_t",
    "agbT",

    "agb_ton",
    "agbTon",

    "agb_tons",
    "agbTons",

    "agb_tonne",
    "agbTonne",

    "agb_tonnes",
    "agbTonnes",

    "agb_kg",
    "agbKg",

    "aboveground_biomass",
    "abovegroundBiomass",

    "aboveground_biomass_t",
    "abovegroundBiomassT",

    "aboveground_biomass_tonnes",
    "abovegroundBiomassTonnes",

    "total_agb",
    "totalAgb",

    "total_agb_t",
    "totalAgbT",

    "biomass",
    "biomass_t",
    "biomassT",

    "biomass_tonnes",
    "biomassTonnes",
  ];

  let value =
    findNumericValueDeep(
      raw,
      exactKeys
    );

  if (value !== null) {
    /*
      If explicit kg field was found, convert kg -> tonnes.
    */

    const kgValue =
      findNumericValueDeep(
        raw,
        [
          "agb_kg",
          "agbKg",
          "aboveground_biomass_kg",
          "abovegroundBiomassKg",
          "total_agb_kg",
          "totalAgbKg",
          "biomass_kg",
          "biomassKg",
        ]
      );

    if (
      kgValue !== null &&
      kgValue === value
    ) {
      return kgValue / 1000;
    }

    return value;
  }

  /*
    Partial-key fallback.
  */

  value =
    findNumericByPartialKey(
      raw,
      [
        "agb",
        "aboveground_biomass",
        "abovegroundbiomass",
      ]
    );

  if (value !== null) {
    return value;
  }

  /*
    Try biomass fields.
  */

  value =
    findNumericByPartialKey(
      raw,
      [
        "biomass",
      ]
    );

  if (value !== null) {
    return value;
  }

  return null;
}

/* ============================================================
   CARBON
   ============================================================ */

function getCarbon(raw) {
  const keys = [
    "carbon",
    "carbon_t",
    "carbonT",
    "carbon_tonnes",
    "carbonTonnes",
    "total_carbon",
    "totalCarbon",
    "carbon_stock",
    "carbonStock",
    "carbon_stock_t",
    "carbonStockT",
    "carbon_kg",
    "carbonKg",
  ];

  let value =
    findNumericValueDeep(
      raw,
      keys
    );

  if (value !== null) {
    const kg =
      findNumericValueDeep(
        raw,
        [
          "carbon_kg",
          "carbonKg",
          "total_carbon_kg",
          "totalCarbonKg",
        ]
      );

    if (
      kg !== null &&
      kg === value
    ) {
      return kg / 1000;
    }

    return value;
  }

  return findNumericByPartialKey(
    raw,
    [
      "carbon",
    ]
  );
}

/* ============================================================
   CO2E
   ============================================================ */

function getCO2e(raw) {
  const keys = [
    "co2e",
    "CO2e",

    "co2e_t",
    "co2eT",

    "co2e_tonnes",
    "co2eTonnes",

    "co2",
    "CO2",

    "co2_t",
    "co2T",

    "co2_tonnes",
    "co2Tonnes",

    "total_co2e",
    "totalCo2e",

    "total_co2",
    "totalCo2",

    "co2e_kg",
    "co2eKg",
  ];

  let value =
    findNumericValueDeep(
      raw,
      keys
    );

  if (value !== null) {
    const kg =
      findNumericValueDeep(
        raw,
        [
          "co2e_kg",
          "co2eKg",
          "co2_kg",
          "co2Kg",
          "total_co2e_kg",
          "totalCo2eKg",
        ]
      );

    if (
      kg !== null &&
      kg === value
    ) {
      return kg / 1000;
    }

    return value;
  }

  return findNumericByPartialKey(
    raw,
    [
      "co2e",
      "co2",
    ]
  );
}

/* ============================================================
   CANOPY COVERAGE
   ============================================================ */

export function getCanopyCoverage(raw) {
  if (!raw) {
    return null;
  }

  /*
    EXACT BACKEND FIELD:

      canopy_coverage_percent: 38.364375
  */

  const percentageKeys = [
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

    "canopy_coverage_pct",
    "canopyCoveragePct",

    "coverage",
  ];

  let value =
    findNumericValueDeep(
      raw,
      percentageKeys
    );

  if (value !== null) {
    /*
      Normally this is already percentage.

      Example:
        38.364375 -> 38.36%
    */

    return value;
  }

  /*
    Partial key fallback.
  */

  value =
    findNumericByPartialKey(
      raw,
      [
        "canopy_coverage_percent",
        "canopy_coverage_percentage",
        "canopy_percent",
      ]
    );

  if (value !== null) {
    return value;
  }

  /*
    Pixel fallback.

    61383 / 160000 * 100
    = 38.364375
  */

  const canopyPixels =
    findNumericValueDeep(
      raw,
      [
        "canopy_pixels",
        "canopyPixels",
        "covered_pixels",
        "coveredPixels",
      ]
    );

  const totalPixels =
    findNumericValueDeep(
      raw,
      [
        "total_image_pixels",
        "totalImagePixels",
        "image_pixels",
        "imagePixels",
        "total_pixels",
        "totalPixels",
      ]
    );

  if (
    canopyPixels !== null &&
    totalPixels !== null &&
    totalPixels > 0
  ) {
    return (
      (canopyPixels / totalPixels) *
      100
    );
  }

  /*
    Fraction fallback.

    Example:
      0.38364375 -> 38.364375%
  */

  const fraction =
    findNumericValueDeep(
      raw,
      [
        "canopy_fraction",
        "canopyFraction",
        "canopy_mask_fraction",
        "canopyMaskFraction",
      ]
    );

  if (
    fraction !== null &&
    fraction >= 0 &&
    fraction <= 1
  ) {
    return fraction * 100;
  }

  return null;
}

/* ============================================================
   CANOPY FORMATTER
   ============================================================ */

export function formatCanopyCoverage(value) {
  const number =
    safeNumber(value);

  if (number === null) {
    return "—";
  }

  return `${number.toFixed(2)}%`;
}

/* ============================================================
   CROWN AREA
   ============================================================ */

function getCrownArea(raw) {
  return findNumericValueDeep(
    raw,
    [
      "total_crown_area_m2",
      "totalCrownAreaM2",

      "crown_area_m2",
      "crownAreaM2",

      "total_crown_area",
      "totalCrownArea",

      "segmentation_area_m2",
      "segmentationAreaM2",
    ]
  );
}

/* ============================================================
   CANOPY PIXELS
   ============================================================ */

function getCanopyPixels(raw) {
  return findNumericValueDeep(
    raw,
    [
      "canopy_pixels",
      "canopyPixels",

      "covered_pixels",
      "coveredPixels",
    ]
  );
}

/* ============================================================
   TOTAL IMAGE PIXELS
   ============================================================ */

function getTotalImagePixels(raw) {
  return findNumericValueDeep(
    raw,
    [
      "total_image_pixels",
      "totalImagePixels",

      "image_pixels",
      "imagePixels",

      "total_pixels",
      "totalPixels",
    ]
  );
}

/* ============================================================
   MAIN NORMALIZER
   ============================================================ */

export function normalizeAnalysis(raw) {
  if (!raw) {
    return {
      treeCount: 0,
      crownCount: 0,

      agb: null,
      carbon: null,
      co2e: null,

      canopyCoverage: null,
      canopyCoveragePercent: null,
      canopy_coverage_percent: null,

      crownArea: null,
      canopyPixels: null,
      totalImagePixels: null,

      raw: null,
    };
  }

  /*
    IMPORTANT:
    Search the ORIGINAL raw response, not only the unwrapped
    result. This prevents losing values stored inside arrays.
  */

  const source = raw;

  const treeCount =
    getTreeCount(source);

  const crownCount =
    getCrownCount(
      source,
      treeCount
    );

  const agb =
    getAGB(source);

  const carbon =
    getCarbon(source);

  const co2e =
    getCO2e(source);

  const canopyCoverage =
    getCanopyCoverage(source);

  const crownArea =
    getCrownArea(source);

  const canopyPixels =
    getCanopyPixels(source);

  const totalImagePixels =
    getTotalImagePixels(source);

  /*
    Return ALL aliases.

    This is intentional because your existing
    ImageAnalysis.jsx may use one of these names.
  */

  return {
    /* Tree */
    treeCount,
    tree_count: treeCount,
    treesDetected: treeCount,
    trees_detected: treeCount,

    /* Crown */
    crownCount,
    crown_count: crownCount,
    crownsDetected: crownCount,
    crowns_detected: crownCount,

    /* AGB */
    agb,
    agb_t: agb,
    agb_tonnes: agb,
    agbTonnes: agb,

    abovegroundBiomass: agb,
    aboveground_biomass: agb,
    abovegroundBiomassTonnes: agb,
    aboveground_biomass_tonnes: agb,

    totalAgb: agb,
    total_agb: agb,

    /* Carbon */
    carbon,
    carbon_t: carbon,
    carbon_tonnes: carbon,
    carbonTonnes: carbon,

    totalCarbon: carbon,
    total_carbon: carbon,

    /* CO2e */
    co2e,
    co2e_t: co2e,
    co2e_tonnes: co2e,
    co2eTonnes: co2e,

    co2: co2e,

    totalCo2e: co2e,
    total_co2e: co2e,

    /* Canopy */
    canopyCoverage,
    canopyCoveragePercent: canopyCoverage,
    canopy_coverage_percent: canopyCoverage,

    canopyCoveragePercentage: canopyCoverage,
    canopy_coverage_percentage: canopyCoverage,

    canopyPercent: canopyCoverage,
    canopy_coverage: canopyCoverage,

    coveragePercent: canopyCoverage,
    coverage_percentage: canopyCoverage,
    coverage: canopyCoverage,

    /* Other metrics */
    crownArea,
    crown_area_m2: crownArea,
    total_crown_area_m2: crownArea,

    canopyPixels,
    canopy_pixels: canopyPixels,

    totalImagePixels,
    total_image_pixels: totalImagePixels,

    /* Original response */
    raw,
  };
}

/* ============================================================
   STATUS
   ============================================================ */

export function extractStatusItems(raw) {
  if (!raw) {
    return [];
  }

  const source =
    unwrapAnalysis(raw);

  const items = [];

  if (
    source?.status !== undefined
  ) {
    items.push({
      label: "Status",
      value: safeString(
        source.status
      ),
    });
  }

  if (
    source?.message !== undefined
  ) {
    items.push({
      label: "Message",
      value: safeString(
        source.message
      ),
    });
  }

  if (
    source?.model !== undefined
  ) {
    items.push({
      label: "Model",
      value: safeString(
        source.model
      ),
    });
  }

  if (
    source?.version !== undefined
  ) {
    items.push({
      label: "Version",
      value: safeString(
        source.version
      ),
    });
  }

  return items;
}

/* ============================================================
   SATELLITE LAYERS
   ============================================================ */

export function normalizeSatelliteLayers(raw) {
  if (!raw) {
    return [];
  }

  const source =
    unwrapAnalysis(raw);

  let layers =
    source?.layers ??
    source?.satellite_layers ??
    source?.satelliteLayers ??
    source?.data?.layers ??
    [];

  if (!Array.isArray(layers)) {
    layers =
      Object.entries(layers).map(
        ([key, value]) => ({
          id: key,
          name: key,
          ...(value &&
          typeof value === "object"
            ? value
            : { value }),
        })
      );
  }

  return layers.map(
    (layer, index) => ({
      id:
        layer?.id ??
        layer?.layer_id ??
        layer?.layerId ??
        `layer-${index}`,

      name:
        layer?.name ??
        layer?.title ??
        layer?.label ??
        `Layer ${index + 1}`,

      type:
        layer?.type ??
        layer?.layer_type ??
        layer?.layerType ??
        "raster",

      url:
        layer?.url ??
        layer?.tile_url ??
        layer?.tileUrl ??
        layer?.tiles ??
        null,

      ...layer,
    })
  );
}

/* ============================================================
   FIND SATELLITE LAYER
   ============================================================ */

export function findSatelliteLayer(
  layers,
  identifiers = []
) {
  if (!Array.isArray(layers)) {
    return null;
  }

  const normalized =
    identifiers.map(
      (item) =>
        String(item).toLowerCase()
    );

  return (
    layers.find((layer) => {
      const values = [
        layer?.id,
        layer?.name,
        layer?.title,
        layer?.label,
        layer?.type,
      ]
        .filter(
          (value) =>
            value !== null &&
            value !== undefined
        )
        .map((value) =>
          String(value).toLowerCase()
        );

      return normalized.some(
        (identifier) =>
          values.some(
            (value) =>
              value === identifier ||
              value.includes(identifier)
          )
      );
    }) ?? null
  );
}

/* ============================================================
   DEFAULT EXPORT
   ============================================================ */

export default {
  fmt,
  safeNumber,
  safeString,

  findNumericValue,
  findNumericValueDeep,

  unwrapAnalysis,

  getCanopyCoverage,
  formatCanopyCoverage,

  normalizeAnalysis,

  extractStatusItems,

  normalizeSatelliteLayers,
  findSatelliteLayer,
};