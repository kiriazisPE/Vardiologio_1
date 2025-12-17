import { Link, useLocation } from 'react-router-dom';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="app-container">
      <nav className="sidebar">
        <div className="logo">
          <h2>⏰ Shift Planner</h2>
          <p className="version">v2.0 • DSPy Powered</p>
        </div>
        
        <ul className="nav-menu">
          <li className={isActive('/') ? 'active' : ''}>
            <Link to="/">
              <span className="icon">📅</span>
              <span>Schedule</span>
            </Link>
          </li>
          <li className={isActive('/employees') ? 'active' : ''}>
            <Link to="/employees">
              <span className="icon">👥</span>
              <span>Employees</span>
            </Link>
          </li>
          <li className={isActive('/settings') ? 'active' : ''}>
            <Link to="/settings">
              <span className="icon">⚙️</span>
              <span>Company Settings</span>
            </Link>
          </li>
          <li className={isActive('/analytics') ? 'active' : ''}>
            <Link to="/analytics">
              <span className="icon">📊</span>
              <span>Analytics</span>
            </Link>
          </li>
        </ul>

        <div className="sidebar-footer">
          <p className="footer-text">
            <strong>Decision Engine</strong><br/>
            No direct OpenAI calls<br/>
            Versioned reasoning artifacts
          </p>
        </div>
      </nav>

      <main className="content">
        {children}
      </main>
    </div>
  );
}
