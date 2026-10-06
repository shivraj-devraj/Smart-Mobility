const configuredApiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export const API_BASE_URL = configuredApiBase.replace(/\/$/, '')

export function getRouteUrl(origin, destination, originLocation, destinationLocation) {
  const params = new URLSearchParams({ from: origin, to: destination })
  if (originLocation) {
    params.set('origin_latitude', String(originLocation.latitude))
    params.set('origin_longitude', String(originLocation.longitude))
  }
  if (destinationLocation) {
    params.set('destination_latitude', String(destinationLocation.latitude))
    params.set('destination_longitude', String(destinationLocation.longitude))
  }
  return `${API_BASE_URL}/api/route?${params.toString()}`
}

export function getLocationSuggestionsUrl(query) {
  const params = new URLSearchParams({ q: query })
  return `${API_BASE_URL}/api/geocoding/suggestions?${params.toString()}`
}

export function getLocationResolveUrl(query) {
  const params = new URLSearchParams({ q: query })
  return `${API_BASE_URL}/api/geocoding/resolve?${params.toString()}`
}
