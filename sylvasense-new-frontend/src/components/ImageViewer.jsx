import React from "react";

export default function ImageViewer({
  src,
  alt = "Analysis result",
  title,
  className = "",
}) {
  if (!src) {
    return (
      <div className={`image-viewer empty ${className}`}>
        <div className="image-viewer-placeholder">
          No image available
        </div>
      </div>
    );
  }

  return (
    <div className={`image-viewer ${className}`}>
      {title && (
        <div className="image-viewer-title">
          {title}
        </div>
      )}

      <div className="image-viewer-content">
        <img
          src={src}
          alt={alt}
          className="image-viewer-image"
        />
      </div>
    </div>
  );
}