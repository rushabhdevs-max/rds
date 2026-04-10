// Data source pill tags per spec section 3.4
// Green WH = Webhook / Fetch Holdings API
// Purple BV = NSE Bhavcopy
// Orange INF = Inferred

const tagStyles = {
  WH: { background: "#e6f5ef", color: "#1D9E75", label: "WH" },
  BV: { background: "#ededfa", color: "#534AB7", label: "BV" },
  INF: { background: "#fde8e0", color: "#E8440A", label: "INF" },
};

export default function DataTag({ type }) {
  const style = tagStyles[type];
  if (!style) return null;
  return (
    <span
      className="data-tag"
      style={{ background: style.background, color: style.color }}
    >
      {style.label}
    </span>
  );
}
