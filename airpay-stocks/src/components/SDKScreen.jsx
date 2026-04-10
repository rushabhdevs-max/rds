// Wrapper for SDK-owned screens (3, 4, 5, 12, 13, 14)
// No bottom nav. Shows "Smallcase SDK" badge to indicate SDK ownership.

import { useNavigate } from "react-router-dom";

export default function SDKScreen({ title, children, onContinue, continueLabel }) {
  const navigate = useNavigate();
  return (
    <div className="sdk-screen">
      <div className="sdk-screen__banner">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
        <span>Smallcase SDK Screen</span>
      </div>
      <div className="sdk-screen__content">
        <h2 className="sdk-screen__title">{title}</h2>
        {children}
        <div className="sdk-screen__actions">
          {onContinue && (
            <button className="btn btn--primary" onClick={onContinue}>
              {continueLabel || "Continue"}
            </button>
          )}
          <button className="btn btn--secondary" onClick={() => navigate(-1)}>
            Back
          </button>
        </div>
      </div>
    </div>
  );
}
