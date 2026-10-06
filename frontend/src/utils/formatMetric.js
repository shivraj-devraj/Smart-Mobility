const NUMBER_FORMATTER = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatMetric(value, type = 'decimal') {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'N/A'

  switch (type) {
    case 'percentage':
      return `${value.toFixed(1)}%`
    case 'speed':
      return `${value.toFixed(1)} km/h`
    case 'volume':
    case 'count':
      return NUMBER_FORMATTER.format(Math.round(value))
    case 'distance':
      return `${value.toFixed(1)} km`
    case 'decimal':
    default:
      return value.toFixed(1)
  }
}
