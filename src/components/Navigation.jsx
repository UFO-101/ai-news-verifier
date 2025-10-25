import { Link, useLocation } from 'react-router-dom'
import './Navigation.css'

function Navigation() {
  const location = useLocation()

  return (
    <nav className="navigation">
      <Link
        to="/scorecard"
        className={`nav-link ${location.pathname === '/scorecard' ? 'active' : ''}`}
      >
        Scorecard
      </Link>
      <Link
        to="/blog"
        className={`nav-link ${location.pathname.startsWith('/blog') || location.pathname.startsWith('/article') ? 'active' : ''}`}
      >
        Blog
      </Link>
    </nav>
  )
}

export default Navigation
