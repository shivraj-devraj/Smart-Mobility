import styles from './RouteAdvisoryCard.module.css'

const ADVISORY_BY_CLASS = {
  Low: {
    level: 'Normal Advisory',
    personnel: 'Routine traffic personnel',
    roadwork: 'No special roadwork restriction recommended',
    diversion: 'No special diversion recommended',
  },
  Medium: {
    level: 'Moderate Advisory',
    personnel: 'Consider additional traffic personnel',
    roadwork: 'Review non-essential roadwork scheduling',
    diversion: 'Consider diversion planning if congestion persists',
  },
  High: {
    level: 'High Advisory',
    personnel: 'Additional traffic personnel recommended',
    roadwork: 'Suspend or reschedule non-essential roadwork where operationally appropriate',
    diversion: 'Prepare/activate suitable diversion planning',
  },
}

const CONTEXT_LABELS = [
  ['isRainy', 'Rain or fog'],
  ['isFestival', 'Festival'],
  ['isHoliday', 'Holiday'],
  ['hasRoadwork', 'Roadwork'],
]

function RouteAdvisoryCard({ corridorName, congestionClass, contextFlags = {} }) {
  const advisory = ADVISORY_BY_CLASS[congestionClass]
  if (!advisory || typeof corridorName !== 'string') return null

  const activeConditions = CONTEXT_LABELS
    .filter(([flag]) => contextFlags[flag])
    .map(([, label]) => label)

  return (
    <section className={styles.card} aria-label={`Historical advisory for ${corridorName}`}>
      {activeConditions.length > 0 && (
        <div className={styles.contextAlert} role="note" aria-label="Active historical context">
          <span className={styles.alertLabel}>CONTEXT</span>
          <span>{activeConditions.join(' · ')}</span>
        </div>
      )}

      <header className={styles.header}>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>CORRIDOR ADVISORY</p>
          <h2 className={styles.title}>{advisory.level}</h2>
          <p className={styles.corridor}>{corridorName}</p>
        </div>
        <span className={`${styles.severity} ${styles[congestionClass.toLowerCase()]}`}>
          {congestionClass}
        </span>
      </header>

      <div className={styles.actions} aria-label="Recommended actions">
        <div className={styles.actionRow}>
          <span className={styles.actionIcon} aria-hidden="true">👮</span>
          <div className={styles.actionContent}>
            <h3>Personnel Action</h3>
            <p>{advisory.personnel}</p>
          </div>
        </div>
        <div className={styles.actionRow}>
          <span className={styles.actionIcon} aria-hidden="true">🚧</span>
          <div className={styles.actionContent}>
            <h3>Roadwork Action</h3>
            <p>{advisory.roadwork}</p>
          </div>
        </div>
        <div className={styles.actionRow}>
          <span className={styles.actionIcon} aria-hidden="true">🔀</span>
          <div className={styles.actionContent}>
            <h3>Diversion Planning</h3>
            <p>{advisory.diversion}</p>
          </div>
        </div>
      </div>

      <p className={styles.disclaimer}>
        Deterministic rule-based recommendations for municipal management; these are not physical
        dispatch triggers or confirmed operational actions.
      </p>
    </section>
  )
}

export default RouteAdvisoryCard
