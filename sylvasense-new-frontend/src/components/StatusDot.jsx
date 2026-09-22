export default function StatusDot({
  status = true,
  label,
}) {
  const isOnline =
    status === true ||
    status === "online" ||
    status === "healthy" ||
    status === "ready" ||
    status === "available";

  return (
    <div className="status-dot-wrapper">
      <span
        className={`status-dot ${
          isOnline
            ? "status-dot-online"
            : "status-dot-offline"
        }`}
      />

      {label && (
        <span className="status-dot-label">
          {label}
        </span>
      )}
    </div>
  );
}