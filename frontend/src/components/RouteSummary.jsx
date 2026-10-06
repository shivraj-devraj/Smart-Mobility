function RouteSummary({ routeData, selectedRoute, selectedRouteId, onSelectRoute }) {
  const routes = routeData?.routes || []

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
                  <span><b>{Number(route.distance_km).toFixed(1)}</b> km</span>
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
          <div className="detail-line"><span>Distance</span><strong>{Number(selectedRoute.distance_km).toFixed(1)} km</strong></div>
          <div className="detail-line"><span>OSRM road-network estimate</span><strong>{selectedRoute.duration_formatted || `${Math.round(selectedRoute.duration_minutes ?? selectedRoute.duration_min)} min`}</strong></div>
          <p className="recommendation-note">{selectedRoute.recommendation_reason || routeData.recommendation_rationale}</p>
          <span className="estimate-label">OSRM road-network estimate</span>
        </div>
      )}
    </aside>
  )
}

export default RouteSummary
