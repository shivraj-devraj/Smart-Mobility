import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config.js'

async function fetchJson(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error('Historical traffic request failed.')
  return response.json()
}

function MetricList({ entries }) {
  return (
    <dl className="historical-metrics">
      {entries.map(([label, value, help]) => (
        <div className="historical-metric" key={label}>
          <dt title={help}>{label}</dt>
          <dd>{String(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

function DayTypeCard({ row }) {
  return (
    <article className="historical-temporal-card">
      <h4>{row.day_type}</h4>
      <MetricList
        entries={[
          ['Average congestion level', row.average_congestion_level, 'Average congestion level in historical observations.'],
          ['Average speed', row.average_speed, 'Average recorded speed in the historical dataset.'],
          ['Average traffic volume', row.average_traffic_volume, 'Average observed traffic volume in historical records.'],
          ['Average travel time index', row.average_travel_time_index, 'Historical travel-time indicator available in the dataset.'],
          ['Records', row.record_count],
          ['High-congestion records', row.high_congestion_count],
          ['High-congestion percentage', `${row.high_congestion_percentage}%`],
        ]}
      />
    </article>
  )
}

function DayOfWeekCard({ row }) {
  return (
    <article className="historical-temporal-card">
      <h4>Day {row.day_of_week}</h4>
      <MetricList
        entries={[
          ['Average congestion level', row.average_congestion_level, 'Average congestion level in historical observations.'],
          ['Average speed', row.average_speed, 'Average recorded speed in the historical dataset.'],
          ['Average traffic volume', row.average_traffic_volume, 'Average observed traffic volume in historical records.'],
          ['Records', row.record_count],
          ['High-congestion percentage', `${row.high_congestion_percentage}%`],
        ]}
      />
    </article>
  )
}

function HistoricalTrafficIntelligence() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [selectedCorridor, setSelectedCorridor] = useState('')
  const [advisoryData, setAdvisoryData] = useState(null)
  const [advisoryLoading, setAdvisoryLoading] = useState(false)
  const [advisoryError, setAdvisoryError] = useState(false)
  const [advisoryEmpty, setAdvisoryEmpty] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const temporalUrl = `${API_BASE_URL}/api/traffic/temporal`
    const requests = [
      fetchJson(`${API_BASE_URL}/api/traffic/high-congestion-corridors`, controller.signal),
      fetchJson(`${API_BASE_URL}/api/traffic/corridors`, controller.signal),
      fetchJson(`${temporalUrl}?dimension=day-type`, controller.signal),
      fetchJson(`${temporalUrl}?dimension=day-of-week`, controller.signal),
    ]

    Promise.all(requests)
      .then(([highCongestion, corridorSummaries, dayType, dayOfWeek]) => {
        if (
          !Array.isArray(highCongestion?.corridors)
          || !Array.isArray(corridorSummaries?.corridors)
          || !Array.isArray(dayType?.rows)
          || !Array.isArray(dayOfWeek?.rows)
        ) {
          throw new Error('Historical traffic response was invalid.')
        }
        setData({ highCongestion, corridorSummaries, dayType, dayOfWeek })
        const initialCorridor = corridorSummaries.corridors[0]?.corridor || ''
        setSelectedCorridor(initialCorridor)
        setAdvisoryLoading(Boolean(initialCorridor))
      })
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setError(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!selectedCorridor) return undefined

    const controller = new AbortController()
    const encodedCorridor = encodeURIComponent(selectedCorridor)

    fetch(`${API_BASE_URL}/api/advisory/corridors/${encodedCorridor}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (controller.signal.aborted) return null
        if (response.status === 404) {
          setAdvisoryEmpty(true)
          return null
        }
        if (!response.ok) throw new Error('Historical advisory request failed.')
        return response.json()
      })
      .then((payload) => {
        if (controller.signal.aborted || !payload) return
        if (!Array.isArray(payload.congestion_actions) || !payload.context_counts) {
          throw new Error('Historical advisory response was invalid.')
        }
        setAdvisoryData(payload)
      })
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setAdvisoryError(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) setAdvisoryLoading(false)
      })

    return () => controller.abort()
  }, [selectedCorridor])

  const corridorRows = data?.corridorSummaries.corridors || []
  const selectedSummary = corridorRows.find((row) => row.corridor === selectedCorridor)
  const advisoryActions = advisoryData?.congestion_actions || []

  return (
    <section className="historical-section" aria-labelledby="historical-title">
      <div className="section-heading historical-heading">
        <div>
          <p className="eyebrow">PERSISTED TRAFFIC ANALYTICS</p>
          <h2 id="historical-title">Historical Traffic Intelligence</h2>
          <p className="historical-subtitle">
            Historical analysis of Bengaluru traffic patterns from the project dataset. These
            insights are not live traffic conditions and are not specific to the selected route.
          </p>
        </div>
        <span className="historical-badge">HISTORICAL DATA</span>
      </div>

      <aside className="historical-scope-note" aria-label="Historical data scope">
        <span className="scope-note-mark" aria-hidden="true">i</span>
        <p>
          Historical intelligence is based on the project&apos;s traffic dataset. It provides
          corridor-level and temporal patterns for analysis; it does not represent live traffic
          or automatically describe the selected OSRM route.
        </p>
      </aside>

      {loading && (
        <p className="historical-message" role="status">
          <span className="button-spinner historical-spinner" aria-hidden="true" />
          Loading historical traffic intelligence...
        </p>
      )}

      {!loading && error && (
        <p className="historical-message historical-error" role="alert">
          Historical traffic intelligence could not be loaded. Route search and map functionality
          are still available.
        </p>
      )}

      {!loading && !error && data && (
        <div className="historical-content">
          <section className="historical-block" aria-labelledby="high-congestion-title">
            <div className="historical-block-heading">
              <h3 id="high-congestion-title">High-Congestion Corridors</h3>
              <span>Historical observations from the project dataset</span>
            </div>
            {data.highCongestion.corridors.length === 0 ? (
              <p className="historical-empty">No historical data available.</p>
            ) : (
              <ol className="high-congestion-list">
                {data.highCongestion.corridors.map((corridor) => (
                  <li className="high-congestion-card" key={corridor.corridor}>
                    <strong>{corridor.corridor}</strong>
                    <div className="high-congestion-rate">
                      <span>High congestion</span>
                      <strong>{corridor.high_congestion_percentage}%</strong>
                    </div>
                    <p className="high-congestion-explainer">
                      Historical observations classified as high congestion.
                    </p>
                    <div className="high-congestion-counts">
                      <div>
                        <span>Total records</span>
                        <strong>{corridor.total_records}</strong>
                      </div>
                      <div>
                        <span>High-congestion observations</span>
                        <strong>{corridor.high_congestion_count}</strong>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="historical-block" aria-labelledby="corridor-summary-title">
            <div className="historical-block-heading">
              <h3 id="corridor-summary-title">Historical Corridor Summary</h3>
              <span>Independent of the selected OSRM route</span>
            </div>
            {corridorRows.length === 0 ? (
              <p className="historical-empty">No historical data available.</p>
            ) : (
              <div className="corridor-summary-panel">
                <label className="corridor-select-label" htmlFor="historical-corridor-select">
                  Choose a corridor to view its historical summary
                </label>
                <select
                  id="historical-corridor-select"
                  value={selectedCorridor}
                  onChange={(event) => {
                    setAdvisoryData(null)
                    setAdvisoryLoading(Boolean(event.target.value))
                    setAdvisoryError(false)
                    setAdvisoryEmpty(false)
                    setSelectedCorridor(event.target.value)
                  }}
                  aria-describedby="corridor-selection-note"
                >
                  {corridorRows.map((row) => (
                    <option value={row.corridor} key={row.corridor}>{row.corridor}</option>
                  ))}
                </select>
                <p className="corridor-selection-note" id="corridor-selection-note">
                  This selection changes historical details only; it does not affect the route or map.
                </p>
                {selectedSummary && (
                  <article className="selected-corridor-card" aria-live="polite">
                    <div className="selected-corridor-heading">
                      <span className="selected-corridor-label">Selected historical corridor</span>
                      <h4 className="selected-corridor-name">{selectedSummary.corridor}</h4>
                    </div>
                    <span className="historical-summary-label">Historical corridor summary · not route-specific</span>
                    <dl className="historical-kpi-grid">
                      <div className="historical-kpi">
                        <dt>Records</dt>
                        <dd>{String(selectedSummary.record_count)}</dd>
                      </div>
                      <div className="historical-kpi">
                        <dt title="Average recorded speed in the historical dataset.">Average speed</dt>
                        <dd>{String(selectedSummary.average_speed)}</dd>
                        <small>Observed in historical records</small>
                      </div>
                      <div className="historical-kpi">
                        <dt title="Average observed traffic volume in historical records.">Average traffic volume</dt>
                        <dd>{String(selectedSummary.average_traffic_volume)}</dd>
                        <small>Historical observed average</small>
                      </div>
                      <div className="historical-kpi">
                        <dt title="Average congestion level in the historical dataset.">Average congestion</dt>
                        <dd>{String(selectedSummary.average_congestion_level)}</dd>
                        <small>Historical observed average</small>
                      </div>
                      <div className="historical-kpi">
                        <dt title="Historical travel-time indicator available in the dataset.">Travel time index</dt>
                        <dd>{String(selectedSummary.average_travel_time_index)}</dd>
                        <small>Dataset indicator</small>
                      </div>
                    </dl>
                    <div className="congestion-distribution">
                      <h5>Historical congestion distribution</h5>
                      <dl>
                        <div><dt>Low</dt><dd>{String(selectedSummary.low_congestion_count)}</dd></div>
                        <div><dt>Medium</dt><dd>{String(selectedSummary.medium_congestion_count)}</dd></div>
                        <div><dt>High</dt><dd>{String(selectedSummary.high_congestion_count)}</dd></div>
                      </dl>
                    </div>
                  </article>
                )}
                {selectedSummary && (
                  <section className="historical-advisory" aria-labelledby="historical-advisory-title">
                    <div className="historical-advisory-heading">
                      <div>
                        <p className="eyebrow">HISTORICAL RULE-BASED ADVISORY</p>
                        <h4 id="historical-advisory-title">Historical Advisory Intelligence</h4>
                      </div>
                      <span>{selectedCorridor}</span>
                    </div>
                    <p className="historical-advisory-disclaimer">
                      Historical advisory based on past Bengaluru traffic data. This is not live traffic for the selected route.
                    </p>

                    {advisoryLoading && (
                      <p className="historical-message" role="status">
                        <span className="button-spinner historical-spinner" aria-hidden="true" />
                        Loading historical advisory information...
                      </p>
                    )}
                    {!advisoryLoading && advisoryError && (
                      <p className="historical-message historical-error" role="alert">
                        Historical advisory information is currently unavailable.
                      </p>
                    )}
                    {!advisoryLoading && !advisoryError && advisoryEmpty && (
                      <p className="historical-empty" role="status">
                        No historical advisory data available for this corridor.
                      </p>
                    )}
                    {!advisoryLoading && !advisoryError && !advisoryEmpty && advisoryData && (
                      <>
                        <dl className="historical-advisory-meta">
                          <div><dt>Observed period</dt><dd>{advisoryData.date_start} to {advisoryData.date_end}</dd></div>
                          <div><dt>Historical records</dt><dd>{advisoryData.record_count}</dd></div>
                        </dl>
                        <div className="advisory-class-grid">
                          {['Low', 'Medium', 'High'].map((congestionClass) => {
                            const action = advisoryActions.find(
                              (item) => item.congestion_class === congestionClass,
                            )
                            return (
                              <article className="advisory-class-card" key={congestionClass}>
                                <div className="advisory-class-heading">
                                  <h5>{congestionClass}</h5>
                                  <span>{action ? `${action.record_count} historical records` : 'No historical records'}</span>
                                </div>
                                {action ? (
                                  <dl className="advisory-action-list">
                                    <div><dt>Advisory level</dt><dd>{action.advisory_level}</dd></div>
                                    <div><dt>Recommendation</dt><dd>{action.recommendation}</dd></div>
                                    <div><dt>Personnel action</dt><dd>{action.personnel_action}</dd></div>
                                    <div><dt>Diversion action</dt><dd>{action.diversion_action}</dd></div>
                                    <div><dt>Roadwork action</dt><dd>{action.roadwork_action}</dd></div>
                                  </dl>
                                ) : (
                                  <p className="advisory-class-empty">
                                    No persisted advisory wording for this class and corridor.
                                  </p>
                                )}
                              </article>
                            )
                          })}
                        </div>
                        <section className="historical-context" aria-labelledby="historical-context-title">
                          <div className="historical-advisory-heading">
                            <h5 id="historical-context-title">Historical Context Indicators</h5>
                            <span>Counts are historical observations and may overlap.</span>
                          </div>
                          <dl className="historical-context-counts">
                            <div><dt>Festival</dt><dd>{advisoryData.context_counts.festival}</dd></div>
                            <div><dt>Holiday</dt><dd>{advisoryData.context_counts.holiday}</dd></div>
                            <div><dt>Roadwork</dt><dd>{advisoryData.context_counts.roadwork}</dd></div>
                            <div><dt>Rain/Fog</dt><dd>{advisoryData.context_counts.rain_or_fog}</dd></div>
                          </dl>
                        </section>
                      </>
                    )}
                  </section>
                )}
              </div>
            )}
          </section>

          <div className="historical-temporal-grid">
            <section className="historical-block" aria-labelledby="day-type-title">
              <div className="historical-block-heading">
                <h3 id="day-type-title">Historical Day-Type Patterns</h3>
                <span>Based on historical observations</span>
              </div>
              {data.dayType.rows.length === 0 ? (
                <p className="historical-empty">No historical data available.</p>
              ) : (
                <div className="historical-temporal-list day-type-list">
                  {data.dayType.rows.map((row) => <DayTypeCard key={row.day_type} row={row} />)}
                </div>
              )}
            </section>

            <section className="historical-block" aria-labelledby="day-of-week-title">
              <div className="historical-block-heading">
                <h3 id="day-of-week-title">Historical Day-of-Week Patterns</h3>
                <span>Historical averages by day of week</span>
              </div>
              {data.dayOfWeek.rows.length === 0 ? (
                <p className="historical-empty">No historical data available.</p>
              ) : (
                <div className="historical-temporal-list day-of-week-list">
                  {data.dayOfWeek.rows.map((row) => (
                    <DayOfWeekCard key={row.day_of_week} row={row} />
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </section>
  )
}

export default HistoricalTrafficIntelligence
