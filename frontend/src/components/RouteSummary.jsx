import { formatMetric } from '../utils/formatMetric.js'

function RouteSummary({ routeData, selectedRoute, selectedRouteId, onSelectRoute }) {
  const routes = routeData?.routes || []
  const recommendedRoute = routes.find((route) => route.id === routeData?.recommended_route_id)
    || routes.find((route) => route.status === 'Recommended')

  return (
    <aside className="route-panel">
      <div className="section-heading results-heading">
        <div>
          <p className="eyebrow">COMPARE OPTIONS</p>
          <h2>Available routes</h2>
        </div>
        {routes.length > 0 && <span className="route-count">{routes.length}</span>}
      </div>
      <p className="route-basis-note">
        Route distance and duration are OSRM road-network estimates, not live traffic conditions.
      </p>

      {recommendedRoute && (
        <section className="best-route-recommendation" aria-label="Best route recommendation">
          <span className="recommendation-kicker">Best Route Recommendation</span>
          <strong>{recommendedRoute.summary || 'Recommended OSRM route'}</strong>
          <span>
            Recommended by the existing OSRM duration-bucket and distance ranking. This does not
            include live traffic, historical corridor matching, or roadwork status.
          </span>
        </section>
      )}

      {routes.length === 0 ? (
        <div className="results-empty">
          <span className="empty-index">01</span>
          <p>{routeData ? 'No drivable route found.' : 'Route options will appear here after your search.'}</p>
        </div>
      ) : (
        <div className="route-list" aria-label="Route options">
          {routes.map((route, index) => {
            const isSelected = route.id === selectedRouteId
            const isRecommended = route.id === routeData.recommended_route_id || route.status === 'Recommended'
            return (
              <button
                className={`route-card${isSelected ? ' is-selected' : ''}${isRecommended ? ' is-recommended' : ''}`}
                type="button"
                key={route.id}
                aria-pressed={isSelected}
                onClick={() => onSelectRoute(route.id)}
              >
                <span className="route-card-topline">
                  <span className={`route-status${isRecommended ? ' recommended-status' : ''}`}>
                    {isRecommended ? 'Recommended' : route.status || 'Alternative'}
                  </span>
                  <span className="route-index">0{index + 1}</span>
                </span>
                <strong className="route-name">{route.summary || `Route ${index + 1}`}</strong>
                <span className="route-metrics">
                  <span><b>{formatMetric(route.distance_km, 'distance')}</b></span>
                  <span><b>{route.duration_formatted || `${Math.round(route.duration_minutes ?? route.duration_min)} min`}</b></span>
                </span>
                <span className="route-select-hint">{isSelected ? 'Selected route' : 'View this route'}</span>
              </button>
            )
          })}
        </div>
      )}

      {selectedRoute && (
        <div className="selected-details" aria-live="polite">
          <p className="eyebrow">SELECTED ROUTE DETAILS</p>
          <div className="detail-line"><span>Distance</span><strong>{formatMetric(selectedRoute.distance_km, 'distance')}</strong></div>
          <div className="detail-line"><span>OSRM road-network estimate</span><strong>{selectedRoute.duration_formatted || `${Math.round(selectedRoute.duration_minutes ?? selectedRoute.duration_min)} min`}</strong></div>
          <p className="recommendation-note">{selectedRoute.recommendation_reason || routeData.recommendation_rationale}</p>
          <span className="estimate-label">OSRM road-network estimate</span>
        </div>
      )}
    </aside>
  )
}

export default RouteSummary
