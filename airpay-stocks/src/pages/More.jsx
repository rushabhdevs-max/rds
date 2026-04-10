// More page — placeholder
import BottomNav from "../components/BottomNav";

export default function More() {
  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <h1 className="page-header__title">More</h1>
        </header>
        <div className="more-list">
          <div className="more-item">
            <span>Account Settings</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          </div>
          <div className="more-item">
            <span>Broker Connection</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          </div>
          <div className="more-item">
            <span>Help & Support</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          </div>
          <div className="more-item">
            <span>About</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          </div>
        </div>
      </div>
      <BottomNav />
    </div>
  );
}
