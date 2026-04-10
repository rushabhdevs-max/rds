// Screen 2: Landing Page — Owner: Airpay
// Two choice cards: Equity Stocks (active, Smallcase Gateway badge) and IPO Investing (coming soon).
// Info box about Smallcase + Nuvama. Tap Equity → Broker Chooser (Screen 3).

import { useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <button className="back-btn" onClick={() => navigate(-1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <h1 className="page-header__title">Indian Stocks</h1>
        </header>

        <div className="landing-cards">
          <button className="landing-card landing-card--active" onClick={() => navigate("/broker-chooser")}>
            <div className="landing-card__icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#E8440A" strokeWidth="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            </div>
            <div className="landing-card__text">
              <span className="landing-card__title">Equity Stocks</span>
              <span className="landing-card__sub">Trade stocks & ETFs via your broker</span>
            </div>
            <span className="gateway-badge">Smallcase Gateway</span>
          </button>

          <div className="landing-card landing-card--disabled">
            <div className="landing-card__icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div className="landing-card__text">
              <span className="landing-card__title">IPO Investing</span>
              <span className="landing-card__sub">Apply for upcoming IPOs</span>
            </div>
            <span className="coming-soon-badge">Coming Soon</span>
          </div>
        </div>

        <div className="info-box">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#378ADD" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <div className="info-box__text">
            <span className="info-box__title">Powered by Smallcase Gateway</span>
            <span className="info-box__sub">Connect your existing broker account (Zerodha, Groww, HDFC Sec, Angel One, and more) to trade directly. Orders execute on NSE via your broker. Airpay does not hold your funds or securities.</span>
          </div>
        </div>
      </div>
      <BottomNav />
    </div>
  );
}
