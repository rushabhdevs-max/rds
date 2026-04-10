// Screen 3: Broker Chooser — Owner: Smallcase SDK
// SDK method: login() — Non-transactional
// SDK renders: Broker grid, "Open account" CTA, Airpay branding
// SDK returns: smallcaseAuthToken (connected JWT), smallcaseAuthId, broker
// No bottom nav (SDK screen)

import { useNavigate } from "react-router-dom";
import SDKScreen from "../components/SDKScreen";

const brokers = [
  { name: "Zerodha", short: "ZR" },
  { name: "Groww", short: "GR" },
  { name: "HDFC Securities", short: "HD" },
  { name: "ICICI Direct", short: "IC" },
  { name: "Angel One", short: "AO" },
  { name: "Upstox", short: "UP" },
  { name: "Kotak Securities", short: "KT" },
  { name: "Motilal Oswal", short: "MO" },
  { name: "5paisa", short: "5P" },
  { name: "Paytm Money", short: "PM" },
  { name: "IIFL Securities", short: "II" },
  { name: "Axis Direct", short: "AX" },
  { name: "SBI Securities", short: "SB" },
  { name: "Nuvama", short: "NV" },
  { name: "Dhan", short: "DH" },
];

export default function BrokerChooser() {
  const navigate = useNavigate();

  function selectBroker() {
    // Simulate: login() → broker auth page
    navigate("/broker-auth");
  }

  return (
    <SDKScreen title="Connect Your Broker">
      <p className="sdk-desc">
        <code>gw.login()</code> — Smallcase SDK renders this broker selection UI.
      </p>
      <p className="sdk-desc">Select your broker to connect your demat account with Airpay Money.</p>

      <div className="broker-grid">
        {brokers.map((b) => (
          <button key={b.short} className="broker-card" onClick={selectBroker}>
            <div className="broker-card__icon">{b.short}</div>
            <span className="broker-card__name">{b.name}</span>
          </button>
        ))}
      </div>

      <div className="sdk-note">
        <span>Don't have a broker account?</span>
        <button className="btn btn--outline btn--sm">Open Account</button>
      </div>

      <div className="sdk-branding">
        <span>Powered by</span>
        <strong>Smallcase Gateway</strong>
        <span>for</span>
        <strong style={{ color: "#E8440A" }}>Airpay Money</strong>
      </div>
    </SDKScreen>
  );
}
