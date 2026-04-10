// Screen 1: Home Screen — Owner: Airpay
// Static investments grid. Indian Stocks has NEW badge. Tap → Landing (Screen 2).

import { useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";

const investments = [
  { id: "mf", label: "Mutual Funds", icon: "chart", enabled: false },
  { id: "gold", label: "Digital Gold", icon: "diamond", enabled: false },
  { id: "us", label: "US Stocks", icon: "globe", enabled: false },
  { id: "indian", label: "Indian Stocks", icon: "trending", enabled: true, isNew: true },
  { id: "nps", label: "NPS", icon: "shield", enabled: false },
  { id: "fd", label: "Fixed Deposits", icon: "lock", enabled: false },
];

const iconMap = {
  chart: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  diamond: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 3h12l4 6-10 13L2 9z"/></svg>,
  globe: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>,
  trending: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>,
  shield: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  lock: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>,
};

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="page">
      <div className="page__content">
        <header className="home-header">
          <div className="home-header__logo">
            <span className="logo-text">airpay</span>
            <span className="logo-sub">money</span>
          </div>
        </header>

        <section className="home-section">
          <h2 className="section-title">Investments</h2>
          <div className="investment-grid">
            {investments.map((item) => (
              <button
                key={item.id}
                className={`investment-card ${!item.enabled ? "investment-card--disabled" : ""}`}
                onClick={() => item.enabled && navigate("/landing")}
              >
                <div className="investment-card__icon">
                  {iconMap[item.icon]}
                </div>
                <span className="investment-card__label">{item.label}</span>
                {item.isNew && <span className="new-badge">NEW</span>}
              </button>
            ))}
          </div>
        </section>

        <section className="home-section">
          <h2 className="section-title">Insurance</h2>
          <div className="insurance-banner">
            <div className="insurance-banner__content">
              <span className="insurance-banner__title">Protect your investments</span>
              <span className="insurance-banner__sub">Health & Life insurance plans</span>
            </div>
            <span className="insurance-banner__tag">Coming Soon</span>
          </div>
        </section>
      </div>
      <BottomNav />
    </div>
  );
}
