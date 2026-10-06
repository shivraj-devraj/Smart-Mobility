import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png?url'
import markerIcon from 'leaflet/dist/images/marker-icon.png?url'
import markerShadow from 'leaflet/dist/images/marker-shadow.png?url'
import { formatMetric } from '../utils/formatMetric.js'

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const EMPTY_ROUTES = []

function FitRouteBounds({ points }) {
  const map = useMap()

  useEffect(() => {
    if (points.length === 0) return
    const bounds = L.latLngBounds(points)
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [50, 50] })
  }, [map, points])

  return null
}

function RouteMap({ routeData, selectedRouteId, onSelectRoute }) {
  const routes = routeData?.routes || EMPTY_ROUTES
  const origin = routeData?.origin
  const destination = routeData?.destination

  const points = useMemo(() => {
    if (!origin || !destination) return []
    return [
      [origin.latitude, origin.longitude],
      [destination.latitude, destination.longitude],
      ...routes.flatMap((route) => route.geometry || []),
    ]
  }, [destination, origin, routes])

  if (!origin || !destination || routes.length === 0) {
    return (
      <div className="map-placeholder" role="status">
        <div className="placeholder-route" aria-hidden="true"><span>A</span><i /><span>B</span></div>
        <strong>{routeData && routes.length === 0 ? 'No drivable route found.' : 'Your route map starts here.'}</strong>
        <p>Enter a start and destination to see available roads.</p>
      </div>
    )
  }

  return (
    <div className="map-frame">
      <MapContainer
        className="route-map"
        center={[origin.latitude, origin.longitude]}
        zoom={12}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitRouteBounds points={points} />
        {routes.map((route) => {
          const isRecommended = route.id === routeData.recommended_route_id || route.status === 'Recommended'
          const isSelected = route.id === selectedRouteId
          const isSelectedAlternative = isSelected && !isRecommended
          return (
            <Polyline
              key={route.id}
              positions={route.geometry}
              pathOptions={{
                color: isRecommended ? '#176b8c' : isSelectedAlternative ? '#c66a3d' : '#75838a',
                weight: isSelected ? 7 : isRecommended ? 6 : 4,
                opacity: isSelected ? 1 : isRecommended ? 0.94 : 0.72,
                dashArray: isRecommended || isSelectedAlternative ? undefined : '8 9',
              }}
              eventHandlers={{ click: () => onSelectRoute(route.id) }}
            >
              <Popup>
                <strong>{route.status}</strong><br />
                {route.summary}<br />
                {formatMetric(route.distance_km, 'distance')} · {route.duration_formatted}
              </Popup>
            </Polyline>
          )
        })}
        <Marker position={[origin.latitude, origin.longitude]}>
          <Popup><strong>Start</strong><br />{origin.display_name}</Popup>
        </Marker>
        <Marker position={[destination.latitude, destination.longitude]}>
          <Popup><strong>Destination</strong><br />{destination.display_name}</Popup>
        </Marker>
      </MapContainer>
      <div className="map-corner-label">OSM ROAD NETWORK</div>
    </div>
  )
}

export default RouteMap
