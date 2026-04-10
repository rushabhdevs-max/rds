// Screen 5: Holdings Fetch Loading — Owner: Smallcase SDK
// SDK method: triggerTransaction({ transactionId }) with HOLDINGS_IMPORT intent
// Backend flow:
//   1. POST /gateway/airpaymoneyprivatelimited/transaction { intent: "HOLDINGS_IMPORT" }
//   2. Frontend: triggerTransaction({ transactionId }) → SDK shows loading
//   3. On success: backend calls GET holdings API
// CRITICAL: Holdings import webhook does NOT contain holdings data. Must call API separately.
// No bottom nav (SDK screen)

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function HoldingsLoading() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/portfolio", { replace: true });
    }, 2500);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="sdk-screen">
      <div className="sdk-screen__banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
        <span>Smallcase SDK Screen</span>
      </div>
      <div className="sdk-screen__content loading-screen">
        <div className="loading-spinner" />
        <h2 className="loading-screen__title">Importing Holdings</h2>
        <p className="sdk-desc">
          <code>triggerTransaction({"{"} transactionId {"}"})
          </code>
        </p>
        <p className="loading-screen__sub">Fetching your portfolio from broker...</p>

        <div className="loading-steps">
          <div className="loading-step loading-step--done">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Broker connected</span>
          </div>
          <div className="loading-step loading-step--done">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Transaction created (HOLDINGS_IMPORT)</span>
          </div>
          <div className="loading-step loading-step--active">
            <div className="loading-dot" />
            <span>Importing holdings from broker...</span>
          </div>
          <div className="loading-step">
            <div className="loading-dot loading-dot--pending" />
            <span>Fetch Holdings API call</span>
          </div>
        </div>
      </div>
    </div>
  );
}
