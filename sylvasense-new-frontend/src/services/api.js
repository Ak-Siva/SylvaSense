const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  "https://sylvasense-backend-kc8t.onrender.com"
).replace(/\/$/, "");

const AI_API_BASE = (
  import.meta.env.VITE_AI_API_BASE_URL ||
  "http://localhost:8002"
).replace(/\/$/, "");

/**
 * ============================================================
 * GENERIC API REQUEST HELPER
 * ============================================================
 */

async function request(path, options = {}, baseUrl = API_BASE) {
  let response;

  try {
    response = await fetch(
      `${baseUrl}${path}`,
      options
    );
  } catch (error) {
    throw new Error(
      `Cannot connect to SylvaSense backend at ${baseUrl}. ` +
        `Make sure the backend is running and accessible.`
    );
  }

  let data = null;

  const contentType =
    response.headers.get("content-type") || "";

  if (
    contentType.includes("application/json")
  ) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    const text = await response.text();

    data = text
      ? { detail: text }
      : null;
  }

  if (!response.ok) {
    let message =
      data?.detail ??
      data?.message ??
      data?.error ??
      `Request failed with HTTP ${response.status}`;

    if (Array.isArray(message)) {
      message = message
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }

          if (item?.loc && item?.msg) {
            return `${item.loc.join(".")}: ${item.msg}`;
          }

          if (item?.msg) {
            return item.msg;
          }

          try {
            return JSON.stringify(item);
          } catch {
            return String(item);
          }
        })
        .join("\n");
    }

    if (typeof message === "object") {
      try {
        message = JSON.stringify(message);
      } catch {
        message = String(message);
      }
    }

    throw new Error(
      message ||
        `Request failed with HTTP ${response.status}`
    );
  }

  return data;
}

/**
 * ============================================================
 * MULTIPART/FORM-DATA REQUEST HELPER
 * ============================================================
 */

function fileRequest(
  path,
  file,
  extra = {},
  baseUrl = API_BASE
) {
  const form = new FormData();

  form.append("file", file);

  Object.entries(extra).forEach(
    ([key, value]) => {
      if (
        value !== undefined &&
        value !== null &&
        value !== ""
      ) {
        form.append(
          key,
          String(value)
        );
      }
    }
  );

  return request(
    path,
    {
      method: "POST",
      body: form,
    },
    baseUrl
  );
}

/**
 * ============================================================
 * CHECK WHETHER ENDPOINT/BACKEND IS UNAVAILABLE
 * ============================================================
 */

export function isEndpointUnavailable(error) {
  const message = String(
    error?.message || ""
  ).toLowerCase();

  return (
    message.includes("failed to fetch") ||
    message.includes("networkerror") ||
    message.includes("err_connection_refused") ||
    message.includes("connection refused") ||
    message.includes("404") ||
    message.includes("not found")
  );
}

/**
 * ============================================================
 * GET CONFIGURED BACKEND URL
 * ============================================================
 */

export function getApiBase() {
  return API_BASE;
}

export function getAiApiBase() {
  return AI_API_BASE;
}

/**
 * ============================================================
 * IMAGE ANALYSIS PROGRESS POLLING
 *
 * AI Backend:
 *
 * POST /api/image-analyze
 *       ↓
 *      job_id
 *       ↓
 * GET /api/image-analysis-progress/{job_id}
 *       ↓
 * current / total
 *       ↓
 * frontend calculates percentage
 *       ↓
 * completed
 *       ↓
 * final result
 *
 * IMPORTANT:
 * This does NOT create fake progress.
 *
 * Example:
 *
 * backend:
 * current = 68
 * total = 130
 *
 * frontend:
 * 68 / 130 = 52.3%
 *
 * ============================================================
 */

async function pollImageAnalysis(
  jobId,
  onProgress
) {
  while (true) {
    await new Promise(
      (resolve) =>
        setTimeout(resolve, 500)
    );

    let progressResponse;

    try {
      progressResponse =
        await fetch(
          `${AI_API_BASE}/api/image-analysis-progress/${jobId}`
        );
    } catch (error) {
      throw new Error(
        `Lost connection to the SylvaSense AI backend while checking image analysis progress. ` +
          `Make sure the AI backend is still running on port 8002.`
      );
    }

    let progressData = null;

    const contentType =
      progressResponse.headers.get(
        "content-type"
      ) || "";

    if (
      contentType.includes(
        "application/json"
      )
    ) {
      try {
        progressData =
          await progressResponse.json();
      } catch {
        progressData = null;
      }
    } else {
      const text =
        await progressResponse.text();

      progressData = text
        ? { detail: text }
        : null;
    }

    if (!progressResponse.ok) {
      let message =
        progressData?.detail ??
        progressData?.message ??
        progressData?.error ??
        `Unable to read analysis progress. HTTP ${progressResponse.status}`;

      if (
        Array.isArray(message)
      ) {
        message = message
          .map((item) => {
            if (
              typeof item ===
              "string"
            ) {
              return item;
            }

            if (
              item?.loc &&
              item?.msg
            ) {
              return `${item.loc.join(
                "."
              )}: ${item.msg}`;
            }

            if (item?.msg) {
              return item.msg;
            }

            try {
              return JSON.stringify(
                item
              );
            } catch {
              return String(item);
            }
          })
          .join("\n");
      }

      throw new Error(message);
    }

    /**
     * ========================================================
     * NORMALIZE REAL BACKEND PATCH PROGRESS
     * ========================================================
     *
     * Backend can return:
     *
     * {
     *   progress: 52,
     *   current: 68,
     *   total: 130
     * }
     *
     * OR:
     *
     * {
     *   progress: 52,
     *   message: "Detecting trees: 68/130 patches"
     * }
     *
     * We pass everything through.
     */

    let percentage = Number(
      progressData?.progress
    );

    const current = Number(
      progressData?.current
    );

    const total = Number(
      progressData?.total
    );

    if (
      !Number.isFinite(percentage)
    ) {
      if (
        Number.isFinite(current) &&
        Number.isFinite(total) &&
        total > 0
      ) {
        percentage =
          (current / total) * 100;
      } else {
        percentage = 0;
      }
    }

    percentage = Math.max(
      0,
      Math.min(100, percentage)
    );

    const normalizedProgress = {
      ...progressData,
      progress: percentage,
      percentage,
    };

    if (
      typeof onProgress ===
      "function"
    ) {
      onProgress(
        normalizedProgress
      );
    }

    /**
     * ========================================================
     * COMPLETED
     * ========================================================
     */

    if (
      progressData?.status ===
      "completed"
    ) {
      if (
        progressData.result
      ) {
        return progressData.result;
      }

      throw new Error(
        "Image analysis completed, but the backend did not return a result."
      );
    }

    /**
     * ========================================================
     * FAILED
     * ========================================================
     */

    if (
      progressData?.status ===
      "failed"
    ) {
      throw new Error(
        progressData.error ||
          progressData.message ||
          "Image analysis failed."
      );
    }
  }
}

/**
 * ============================================================
 * API
 * ============================================================
 */

export const api = {

  /**
   * Backend base URL
   */

  baseUrl: API_BASE,

  // ==========================================================
  // STATUS
  // ==========================================================

  status: () =>
    request(
      "/api/status"
    ),

  // ==========================================================
  // HEALTH
  // ==========================================================

  health: () =>
    request("/health"),

  // ==========================================================
  // IMAGE ANALYSIS
  // ==========================================================

  imageAnalyze: async (
    file,
    onProgress
  ) => {
    if (!file) {
      throw new Error(
        "No image file was provided."
      );
    }

    const form =
      new FormData();

    form.append(
      "file",
      file
    );

    let response;

    try {
      response =
        await fetch(
          `${AI_API_BASE}/api/image-analyze`,
          {
            method: "POST",
            body: form,
          }
        );
    } catch (error) {
      throw new Error(
        `Cannot connect to SylvaSense AI backend at ${AI_API_BASE}. ` +
          `Make sure the AI backend is running on port 8002.`
      );
    }

    let data = null;

    const contentType =
      response.headers.get(
        "content-type"
      ) || "";

    if (
      contentType.includes(
        "application/json"
      )
    ) {
      try {
        data =
          await response.json();
      } catch {
        data = null;
      }
    } else {
      const text =
        await response.text();

      data = text
        ? { detail: text }
        : null;
    }

    if (!response.ok) {
      let message =
        data?.detail ??
        data?.message ??
        data?.error ??
        `Request failed with HTTP ${response.status}`;

      if (
        Array.isArray(message)
      ) {
        message = message
          .map((item) => {
            if (
              typeof item ===
              "string"
            ) {
              return item;
            }

            if (
              item?.loc &&
              item?.msg
            ) {
              return `${item.loc.join(
                "."
              )}: ${item.msg}`;
            }

            if (item?.msg) {
              return item.msg;
            }

            try {
              return JSON.stringify(
                item
              );
            } catch {
              return String(item);
            }
          })
          .join("\n");
      }

      throw new Error(
        message ||
          `Request failed with HTTP ${response.status}`
      );
    }

    /**
     * Backend must return job_id.
     */

    const jobId =
      data?.job_id;

    if (!jobId) {
      throw new Error(
        "Backend did not return an analysis job ID."
      );
    }

    /**
     * Immediately show queued state.
     */

    if (
      typeof onProgress ===
      "function"
    ) {
      onProgress({
        job_id: jobId,

        status:
          data?.status ||
          "queued",

        progress:
          Number(
            data?.progress
          ) || 0,

        percentage:
          Number(
            data?.progress
          ) || 0,

        current:
          Number(
            data?.current
          ) || 0,

        total:
          Number(
            data?.total
          ) || 0,

        stage:
          data?.stage ||
          "Queued",

        message:
          data?.message ||
          "Image analysis started.",

        result: null,

        error: null,
      });
    }

    /**
     * Poll actual backend progress.
     */

    return pollImageAnalysis(
      jobId,
      onProgress
    );
  },

  // ==========================================================
  // TREE DETECTION
  // ==========================================================

  treeDetection: (
    file,
    pixelSizeM,
    woodDensity
  ) =>
    fileRequest(
      "/api/tree-detection",
      file,
      {
        pixel_size_m:
          pixelSizeM,

        wood_density:
          woodDensity,
      },
      AI_API_BASE
    ),

  // ==========================================================
  // OLD AGB FORECAST
  // ==========================================================

  forecast: (
    payload
  ) =>
    request(
      "/api/forecast",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      }
    ),

  // ==========================================================
  // CROWN SEGMENTATION
  // ==========================================================

  crownSegmentation: (
    file
  ) =>
    fileRequest(
      "/api/crown-segmentation",
      file,
      {},
      AI_API_BASE
    ),

  // ==========================================================
  // BIOMASS
  // ==========================================================

  biomass: (
    payload
  ) =>
    request(
      "/api/biomass",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      },
      AI_API_BASE
    ),

  // ==========================================================
  // CARBON
  // ==========================================================

  carbon: (
    payload
  ) =>
    request(
      "/api/carbon",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      },
      AI_API_BASE
    ),

  // ==========================================================
  // SATELLITE INTELLIGENCE
  // ==========================================================

  satelliteAnalysis: (
    payload
  ) =>
    request(
      "/api/satellite-analysis",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      }
    ),

  // ==========================================================
  // SATELLITE AGB / FORECAST
  // ==========================================================

  satelliteAgb: (
    payload
  ) =>
    request(
      "/api/satellite-agb",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      }
    ),

  // ==========================================================
  // CHANGE DETECTION
  // ==========================================================

  changeDetection: (
    payload
  ) =>
    request(
      "/api/change-detection",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      }
    ),

  // ==========================================================
  // VALIDATE
  // ==========================================================

  validate: (
    file,
    iouThreshold = 0.5,
    confidenceThreshold = 0.0
  ) =>
    fileRequest(
      "/api/validate",
      file,
      {
        iou_threshold:
          iouThreshold,

        confidence_threshold:
          confidenceThreshold,
      },
      AI_API_BASE
    ),

  // ==========================================================
  // GENERAL ANALYZE
  // ==========================================================

  analyze: (
    payload
  ) =>
    request(
      "/api/analyze",
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            payload
          ),
      }
    ),
};

/**
 * ============================================================
 * DEFAULT EXPORT
 * ============================================================
 */

export default api;