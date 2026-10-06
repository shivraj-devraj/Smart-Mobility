import { useState } from 'react'
import RouteMap from './components/RouteMap.jsx'
import RouteSearch from './components/RouteSearch.jsx'
import RouteSummary from './components/RouteSummary.jsx'
import HistoricalTrafficIntelligence from './components/HistoricalTrafficIntelligence.jsx'
import { getRouteUrl } from './config.js'

function App() {
  const [routeData, setRouteData] = useState(null)
  const [selectedRouteId, setSelectedRouteId] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchNumber, setSearchNumber] = useState(0)

  async function findRoutes({ from, to, originLocation, destinationLocation }) {
    const originQuery = from.trim()
    const destinationQuery = to.trim()
    if (!originQuery) {
      setError('Enter a starting location to find routes.')
      setRouteData(null)
      return
    }
    if (!destinationQuery) {
      setError('Enter a destination to find routes.')
      setRouteData(null)
      return
    }
    const sameQuery = originQuery.localeCompare(destinationQuery, undefined, { sensitivity: 'accent' }) === 0
    const sameCoordinates = originLocation
      && destinationLocation
      && originLocation.latitude === destinationLocation.latitude
      && originLocation.longitude === destinationLocation.longitude
    if (sameQuery || sameCoordinates) {
      setError('Origin and destination should be different.')
      setRouteData(null)
      return
    }

    setLoading(true)
    setError('')
    setRouteData(null)
    setSelectedRouteId(null)

    try {
      const response = await fetch(getRouteUrl(originQuery, destinationQuery, originLocation, destinationLocation))
      const payload = await response.json().catch(() => null)

      if (!response.ok) {
        const message = payload?.detail?.message || payload?.detail || 'Route service could not complete the request.'
        if (payload?.detail?.code === 'ROUTE_NOT_FOUND') {
          setError('No drivable route found.')
        } else {
          setError(typeof message === 'string' ? message : 'Route service could not complete the request.')
        }
        return
      }

      if (!payload || !Array.isArray(payload.routes)) {
        setError('The route service returned an unexpected response. Please try again.')
        return
      }

      setRouteData(payload)
      setSearchNumber((number) => number + 1)
      setSelectedRouteId(payload.recommended_route_id || payload.routes[0]?.id || null)
      if (payload.routes.length === 0) setError('No drivable route found.')
    } catch {
      setError('Could not reach the route service. Check that FastAPI is running, then try again.')
    } finally {
      setLoading(false)
    }
  }

  const selectedRoute = routeData?.routes.find((route) => route.id === selectedRouteId) || null

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Bengaluru Route Advisory home">
          <span className="brand-mark" aria-hidden="true">B</span>
          <span className="brand-name">Bengaluru <strong>Route Advisory</strong></span>
        </a>
        <div className="engine-tag"><span className="engine-dot" /> OPENSTREETMAP <span className="tag-divider">/</span> OSRM</div>
      </header>

      <section className="intro" id="top">
        <div>
          <p className="eyebrow">ROAD-NETWORK ROUTE COMPARISON</p>
          <h1>Find a way across<br className="desktop-break" /> Bengaluru.</h1>
        </div>
        <p className="intro-note">Compare available driving routes with clear distance and estimated time. Route estimates use the OSRM road network, not current traffic conditions.</p>
      </section>

      <RouteSearch onSearch={findRoutes} loading={loading} />

      {error && <div className="error-banner" role="alert"><span className="error-icon">!</span>{error}</div>}

      <section className="workspace" aria-label="Route map and results">
        <div className="map-column">
          <div className="section-heading">
            <div>
              <p className="eyebrow">INTERACTIVE MAP</p>
              <h2>Route overview</h2>
            </div>
            {routeData?.routes?.length > 0 && <span className="route-count">{routeData.routes.length} {routeData.routes.length === 1 ? 'ROUTE' : 'ROUTES'}</span>}
          </div>
          <RouteMap
            key={searchNumber}
            routeData={routeData}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
          />
          <div className="map-legend">
            <span><i className="legend-line legend-recommended" /> Recommended</span>
            <span><i className="legend-line legend-alternative" /> Alternative</span>
            <span className="map-credit">Map data © OpenStreetMap contributors</span>
          </div>
        </div>

        <RouteSummary
          routeData={routeData}
          selectedRoute={selectedRoute}
          selectedRouteId={selectedRouteId}
          onSelectRoute={setSelectedRouteId}
        />
      </section>

      <HistoricalTrafficIntelligence />

      <footer className="page-footer">
        <span>Route options and estimates supplied by OSRM.</span>
        <span>Not live traffic, traffic prediction, or turn-by-turn navigation.</span>
      </footer>
    </main>
  )
}

export default App
