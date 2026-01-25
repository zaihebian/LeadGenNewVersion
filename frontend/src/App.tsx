import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Search, Users, Inbox, LayoutDashboard, Mail } from 'lucide-react'
import SearchPage from './pages/SearchPage'
import LeadsPage from './pages/LeadsPage'
import InboxPage from './pages/InboxPage'
import DashboardPage from './pages/DashboardPage'

function App() {
  const location = useLocation()

  const navItems = [
    { path: '/', icon: Search, label: 'Search' },
    { path: '/leads', icon: Users, label: 'Leads' },
    { path: '/inbox', icon: Inbox, label: 'Inbox' },
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2">
              <Mail className="w-8 h-8 text-blue-600" />
              <span className="text-xl font-bold text-gray-900">LeadGen</span>
            </div>
            <nav className="flex space-x-1">
              {navItems.map(({ path, icon: Icon, label }) => (
                <Link
                  key={path}
                  to={path}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname === path
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
