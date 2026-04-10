export default function FilterChips({ options, active, onChange }) {
  return (
    <div className="filter-chips">
      {options.map((opt) => (
        <button
          key={opt}
          className={`filter-chip ${active === opt ? "filter-chip--active" : ""}`}
          onClick={() => onChange(opt)}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
