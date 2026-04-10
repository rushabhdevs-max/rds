// Screen 4: Broker Login / Authorization — Owner: Smallcase SDK
// SDK method: login() continuation
// Broker's own OAuth page. SDK handles redirect + callback.
// Returns smallcaseAuthToken (connected JWT) + smallcaseAuthId
// No bottom nav (SDK screen)

import { useNavigate } from "react-router-dom";
import SDKScreen from "../components/SDKScreen";

export default function BrokerAuth() {
  const navigate = useNavigate();

  function handleAuthorize() {
    // Simulate: OAuth complete → holdings fetch loading
    navigate("/holdings-loading");
  }

  return (
    <SDKScreen title="Broker Authorization" onContinue={handleAuthorize} continueLabel="Authorize & Continue">
      <p className="sdk-desc">
        <code>login()</code> continuation — Broker's OAuth consent page.
      </p>

      <div className="auth-sim">
        <div className="auth-sim__header">
          <div className="auth-sim__broker-icon">ZR</div>
          <span className="auth-sim__broker-name">Zerodha Kite</span>
        </div>

        <div className="auth-sim__consent">
          <h4>Airpay Money is requesting access to:</h4>
          <ul className="auth-sim__permissions">
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              Place, modify & cancel orders
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              Access portfolio holdings
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              View balance & margins
            </li>
            <li>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D9E75" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              View profile details
            </li>
          </ul>
        </div>

        <div className="auth-sim__session-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#378ADD" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>Zerodha sessions are long-lived. Other brokers require re-auth each session.</span>
        </div>
      </div>
    </SDKScreen>
  );
}
