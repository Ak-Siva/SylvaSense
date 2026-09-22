import React from "react";

export default function MetricCard({
  icon: Icon,
  title,
  value,
  unit,
  accent = "",
}) {
  return (
    <div className={`metric-card ${accent}`}>
      <div className="metric-icon">
        {Icon && <Icon size={20} />}
      </div>

      <div className="metric-label">
        {title}
      </div>

      <div className="metric-value">
        {value}

        {unit && (
          <span>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}