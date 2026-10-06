import { useId, useState } from 'react'
import styles from './TravelContextBar.module.css'

const TRAVEL_CONTEXTS = [
  'Regular Day',
  'Friday Evening Surge',
  'Festival / Long Weekend',
  'Adverse Weather (Monsoon Rain)',
]

function getLocalDateString(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function TravelContextBar({ onContextChange }) {
  const groupId = useId()
  const [date, setDate] = useState(() => getLocalDateString())
  const [contextType, setContextType] = useState(TRAVEL_CONTEXTS[0])

  function updateDate(event) {
    const nextDate = event.target.value
    setDate(nextDate)
    onContextChange?.({ date: nextDate, contextType })
  }

  function updateContext(nextContext) {
    setContextType(nextContext)
    onContextChange?.({ date, contextType: nextContext })
  }

  return (
    <section className={styles.bar} aria-label="Travel context">
      <div className={styles.dateField}>
        <label className={styles.fieldLabel} htmlFor={`${groupId}-date`}>Travel date</label>
        <input
          className={styles.dateInput}
          id={`${groupId}-date`}
          type="date"
          value={date}
          onChange={updateDate}
        />
      </div>

      <fieldset className={styles.contextField}>
        <legend className={styles.fieldLabel}>Travel context</legend>
        <div className={styles.options}>
          {TRAVEL_CONTEXTS.map((context, index) => {
            const optionId = `${groupId}-context-${index}`
            return (
              <label className={styles.option} htmlFor={optionId} key={context}>
                <input
                  className={styles.radio}
                  id={optionId}
                  type="radio"
                  name={`${groupId}-context`}
                  value={context}
                  checked={contextType === context}
                  onChange={() => updateContext(context)}
                />
                <span className={styles.pill}>{context}</span>
              </label>
            )
          })}
        </div>
      </fieldset>
    </section>
  )
}

export default TravelContextBar
