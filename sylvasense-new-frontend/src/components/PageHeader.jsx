import React from "react";

export default function PageHeader({
  icon: Icon,
  title,
  description,
  action,
}) {
  return (
    <div className="page-header">
      <div>
        <div className="eyebrow">
          {Icon && <Icon size={16} />}
          SYLVASENSE
        </div>

        <h1>{title}</h1>

        <p>{description}</p>
      </div>

      {action}
    </div>
  );
}