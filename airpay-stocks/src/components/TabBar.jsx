export default function TabBar({ active, onChange }) {
  const tabs = ["Holdings", "Orders"];
  return (
    <div className="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab}
          className={`tab-bar__tab ${active === tab ? "tab-bar__tab--active" : ""}`}
          onClick={() => onChange(tab)}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
