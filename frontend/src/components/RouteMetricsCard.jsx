import styles from './RouteMetricsCard.module.css'
import { formatMetric } from '../utils/formatMetric.js'

const CONGESTION_MULTIPLIERS = {
  Low: 1.1,
  Medium: 1.5,
  High: 2.1,
}

function RouteMetricsCard({ osrmDurationMinutes, osrmDistanceKm, predictedCongestionClass }) {
  const multiplier = CONGESTION_MULTIPLIERS[predictedCongestionClass]
  const hasValidDuration = Number.isFinite(osrmDurationMinutes) && osrmDurationMinutes >= 0
  const hasValidDistance = Number.isFinite(osrmDistanceKm) && osrmDistanceKm >= 0
  const hasValidClass = multiplier !== undefined

  if (!hasValidDuration || !hasValidDistance || !hasValidClass) return null

  const standardMinutes = Math.round(osrmDurationMinutes)
  const adjustedMinutes = Math.round(osrmDurationMinutes * multiplier)
  const delayPercent = standardMinutes > 0
    ? Math.round(((adjustedMinutes - standardMinutes) / standardMinutes) * 100)
    : 0

  return (
    <section className={styles.card} aria-label="Route timing illustration">
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>ROUTE TIMING</p>
          <h2 className={styles.title}>Estimated journey</h2>
        </div>
        <span className={`${styles.severity} ${styles[predictedCongestionClass.toLowerCase()]}`}>
          {predictedCongestionClass} severity
        </span>
      </div>

      <p className={styles.disclaimer}>
        Illustrative multiplier only—not an ML forecast, live traffic reading, or route-specific
        congestion estimate.
      </p>

      <div className={styles.metrics}>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Standard OSRM time</span>
          <strong className={styles.metricValue}>{standardMinutes} mins</strong>
          <span className={styles.metricHint}>Road-network estimate</span>
        </div>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Illustrative adjusted time</span>
          <strong className={styles.metricValue}>{adjustedMinutes} mins</strong>
          <span className={styles.metricHint}>Applied {multiplier}× scenario multiplier</span>
        </div>
      </div>

      <div className={styles.footer}>
        <span className={styles.distance}>{formatMetric(osrmDistanceKm, 'distance')}</span>
        <span className={`${styles.delay} ${styles[predictedCongestionClass.toLowerCase()]}`}>
          +{delayPercent}% Delay
        </span>
      </div>
    </section>
  )
}

export default RouteMetricsCard
