"""
SYLVASENSE - Transparent AGB/Carbon Trend Forecasting

Simple linear trend forecasting using historical AGB observations.

The module accepts either:
    - Calendar years: [2023, 2024, 2025]
    - Date strings: ["2023-01-01", "2024-01-01", "2025-01-01"]

It fits an ordinary least-squares linear trend and projects
the trend into the requested future years/dates.
"""

import numpy as np
import pandas as pd


def _convert_to_dates(values):
    """
    Convert input values into pandas timestamps.

    Numeric values such as 2023, 2024, 2025 are treated as
    calendar years rather than Unix/nanosecond timestamps.
    """

    if values is None or len(values) == 0:
        raise ValueError(
            "Date values cannot be empty."
        )

    converted = []

    for value in values:

        # -----------------------------------------------------
        # Numeric year
        # Example: 2023 -> 2023-01-01
        # -----------------------------------------------------

        if isinstance(
            value,
            (int, float, np.integer, np.floating)
        ):
            if not np.isfinite(float(value)):
                raise ValueError(
                    f"Invalid year value: {value}"
                )

            year = int(value)

            if year < 1900 or year > 2200:
                raise ValueError(
                    f"Invalid calendar year: {value}"
                )

            converted.append(
                pd.Timestamp(
                    year=year,
                    month=1,
                    day=1
                )
            )

        else:
            # -------------------------------------------------
            # String date
            # -------------------------------------------------

            timestamp = pd.to_datetime(
                value,
                errors="coerce"
            )

            if pd.isna(timestamp):
                raise ValueError(
                    f"Invalid date value: {value}"
                )

            converted.append(timestamp)

    return pd.DatetimeIndex(converted)


def forecast_agb(
    dates,
    agb_tonnes,
    forecast_dates,
    carbon_fraction=0.47,
    co2_factor=3.6663,
):
    # ---------------------------------------------------------
    # 1. Basic validation
    # ---------------------------------------------------------

    if dates is None or agb_tonnes is None:
        raise ValueError(
            "Historical dates and AGB values are required."
        )

    if len(dates) != len(agb_tonnes):
        raise ValueError(
            "Historical dates and AGB values must have "
            "the same length."
        )

    if len(dates) < 2:
        raise ValueError(
            "Provide at least two historical AGB observations."
        )

    if (
        forecast_dates is None
        or len(forecast_dates) == 0
    ):
        raise ValueError(
            "At least one forecast date is required."
        )

    # ---------------------------------------------------------
    # 2. Convert dates
    # ---------------------------------------------------------

    parsed_dates = _convert_to_dates(
        dates
    )

    parsed_forecast_dates = _convert_to_dates(
        forecast_dates
    )

    # ---------------------------------------------------------
    # 3. Convert AGB values to numbers
    # ---------------------------------------------------------

    agb_series = pd.to_numeric(
        agb_tonnes,
        errors="coerce"
    )

    agb_values = np.asarray(
        agb_series,
        dtype=np.float64
    )

    # ---------------------------------------------------------
    # 4. Validate AGB values
    # ---------------------------------------------------------

    if not np.all(
        np.isfinite(agb_values)
    ):
        raise ValueError(
            "Historical AGB values contain "
            "invalid numbers."
        )

    if np.any(agb_values < 0):
        raise ValueError(
            "Historical AGB values cannot be negative."
        )

    # ---------------------------------------------------------
    # 5. Create historical dataframe
    # ---------------------------------------------------------

    hist = pd.DataFrame(
        {
            "date": parsed_dates,
            "agb_tonnes": agb_values,
        }
    )

    # Sort by date.
    hist = hist.sort_values(
        "date"
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # 6. Check duplicate dates
    # ---------------------------------------------------------

    if hist["date"].duplicated().any():
        raise ValueError(
            "Historical dates must be unique."
        )

    # ---------------------------------------------------------
    # 7. Convert dates into numerical years
    #
    # First historical observation = year 0.
    # ---------------------------------------------------------

    start_date = hist["date"].iloc[0]

    x = (
        hist["date"] - start_date
    ).dt.days.to_numpy(
        dtype=np.float64
    ) / 365.25

    y = hist[
        "agb_tonnes"
    ].to_numpy(
        dtype=np.float64
    )

    # ---------------------------------------------------------
    # 8. Validate regression data
    # ---------------------------------------------------------

    if not np.all(
        np.isfinite(x)
    ):
        raise ValueError(
            "Historical dates produced invalid values."
        )

    if not np.all(
        np.isfinite(y)
    ):
        raise ValueError(
            "Historical AGB values produced invalid values."
        )

    if len(np.unique(x)) < 2:
        raise ValueError(
            "Historical dates must contain at least "
            "two different dates."
        )

    # ---------------------------------------------------------
    # 9. Linear regression
    #
    # y = slope*x + intercept
    # ---------------------------------------------------------

    try:

        slope, intercept = np.polyfit(
            x,
            y,
            1
        )

    except np.linalg.LinAlgError:

        # -----------------------------------------------------
        # Fallback calculation
        # -----------------------------------------------------

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        denominator = np.sum(
            (x - x_mean) ** 2
        )

        if denominator <= 0:
            raise ValueError(
                "Historical dates do not contain enough "
                "variation for forecasting."
            )

        slope = (
            np.sum(
                (x - x_mean) *
                (y - y_mean)
            )
            / denominator
        )

        intercept = (
            y_mean -
            slope * x_mean
        )

    slope = float(slope)
    intercept = float(intercept)

    # ---------------------------------------------------------
    # 10. Validate regression result
    # ---------------------------------------------------------

    if not np.isfinite(slope):
        raise ValueError(
            "The calculated AGB trend is invalid."
        )

    if not np.isfinite(intercept):
        raise ValueError(
            "The calculated AGB intercept is invalid."
        )

    # ---------------------------------------------------------
    # 11. Convert forecast dates to numerical years
    # ---------------------------------------------------------

    future = parsed_forecast_dates

    fx = (
        future - start_date
    ).days.to_numpy(
        dtype=np.float64
    ) / 365.25

    if not np.all(
        np.isfinite(fx)
    ):
        raise ValueError(
            "Forecast dates produced invalid values."
        )

    # ---------------------------------------------------------
    # 12. Calculate predicted AGB
    # ---------------------------------------------------------

    predicted_agb = (
        intercept +
        slope * fx
    )

    if not np.all(
        np.isfinite(predicted_agb)
    ):
        raise ValueError(
            "Forecast produced invalid AGB values."
        )

    # AGB cannot be negative.
    predicted_agb = np.maximum(
        predicted_agb,
        0.0
    )

    # ---------------------------------------------------------
    # 13. Calculate carbon
    # ---------------------------------------------------------

    predicted_carbon = (
        predicted_agb *
        float(carbon_fraction)
    )

    # ---------------------------------------------------------
    # 14. Calculate CO2 equivalent
    # ---------------------------------------------------------

    predicted_co2e = (
        predicted_carbon *
        float(co2_factor)
    )

    # ---------------------------------------------------------
    # 15. Create forecast dataframe
    # ---------------------------------------------------------

    out = pd.DataFrame(
        {
            "date": future,

            "predicted_agb_tonnes":
                predicted_agb,

            "predicted_carbon_tonnes":
                predicted_carbon,

            "predicted_co2e_tonnes":
                predicted_co2e,
        }
    )

    # ---------------------------------------------------------
    # 16. Return
    # ---------------------------------------------------------

    return {
        "historical": hist,

        "forecast": out,

        "agb_change_per_year":
            float(slope),

        "method":
            "ordinary least-squares linear trend",
    }


def forecast_from_periods(periods):
    """
    Convenience wrapper.

    Example:

        periods = [
            ("2020-01-01", 180.0),
            ("2021-01-01", 186.0),
            ("2022-01-01", 191.0),
        ]
    """

    if periods is None or len(periods) < 2:
        raise ValueError(
            "Provide at least two historical periods."
        )

    dates, agb = zip(*periods)

    last_date = max(
        _convert_to_dates(dates)
    )

    future_dates = [
        (
            last_date +
            pd.DateOffset(years=i)
        ).strftime("%Y-%m-%d")
        for i in range(1, 4)
    ]

    return forecast_agb(
        dates,
        agb,
        future_dates
    )


def calculate_forecast_summary(result):
    """
    Create a compact summary from forecast_agb().
    """

    historical = result.get(
        "historical"
    )

    forecast = result.get(
        "forecast"
    )

    summary = {
        "method":
            result.get("method"),

        "agb_change_per_year":
            result.get(
                "agb_change_per_year"
            ),
    }

    # ---------------------------------------------------------
    # Historical summary
    # ---------------------------------------------------------

    if (
        historical is not None
        and len(historical) > 0
    ):

        summary[
            "historical_start_agb_tonnes"
        ] = float(
            historical[
                "agb_tonnes"
            ].iloc[0]
        )

        summary[
            "historical_end_agb_tonnes"
        ] = float(
            historical[
                "agb_tonnes"
            ].iloc[-1]
        )

    # ---------------------------------------------------------
    # Forecast summary
    # ---------------------------------------------------------

    if (
        forecast is not None
        and len(forecast) > 0
    ):

        summary[
            "forecast_start_agb_tonnes"
        ] = float(
            forecast[
                "predicted_agb_tonnes"
            ].iloc[0]
        )

        summary[
            "forecast_end_agb_tonnes"
        ] = float(
            forecast[
                "predicted_agb_tonnes"
            ].iloc[-1]
        )

        summary[
            "forecast_end_carbon_tonnes"
        ] = float(
            forecast[
                "predicted_carbon_tonnes"
            ].iloc[-1]
        )

        summary[
            "forecast_end_co2e_tonnes"
        ] = float(
            forecast[
                "predicted_co2e_tonnes"
            ].iloc[-1]
        )

    return summary