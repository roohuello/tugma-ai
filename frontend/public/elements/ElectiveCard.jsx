// ElectiveCard.jsx — Renders an SSHS elective subject recommendation
// Used by Chainlit's cl.CustomElement(name="ElectiveCard")

export default function ElectiveCard({ props }) {
  const { name, cluster, track, hours, semester, description_snippet, relevance_reason } = props;

  const trackColor = track === "Academic" ? "#2563eb" : "#059669";
  const hoursLabel = hours === 320 ? "Year-long" : `${hours}h`;

  return (
    <div style={{
      border: `2px solid ${trackColor}`,
      borderRadius: "12px",
      padding: "16px",
      marginBottom: "12px",
      maxWidth: "480px",
      fontFamily: "system-ui, sans-serif",
      backgroundColor: "#fff",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h3 style={{ margin: 0, fontSize: "18px", fontWeight: 700 }}>{name}</h3>
        <span style={{
          backgroundColor: trackColor,
          color: "#fff",
          padding: "2px 10px",
          borderRadius: "999px",
          fontSize: "12px",
          fontWeight: 600,
        }}>
          {track}
        </span>
      </div>

      <div style={{ display: "flex", gap: "12px", marginBottom: "8px", fontSize: "13px", color: "#6b7280" }}>
        <span>{cluster}</span>
        <span>{semester} Semester</span>
        <span>{hoursLabel}</span>
      </div>

      <p style={{ fontSize: "14px", color: "#374151", marginBottom: "8px", lineHeight: 1.5 }}>
        {description_snippet}
      </p>

      <div style={{
        backgroundColor: "#f0fdf4",
        borderLeft: `3px solid ${trackColor}`,
        padding: "8px 12px",
        borderRadius: "6px",
        fontSize: "13px",
        color: "#1e293b",
      }}>
        <strong>Why this fits you:</strong> {relevance_reason}
      </div>
    </div>
  );
}
