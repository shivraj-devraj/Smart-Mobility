import { useEffect, useRef, useState } from 'react'
import { getLocationResolveUrl, getLocationSuggestionsUrl } from '../config.js'

const MIN_QUERY_CHARACTERS = 3
const SEARCH_DEBOUNCE_MS = 450
const suggestionCache = new Map()
const BENGALURU_LOCATION_HINTS = [
  'Koramangala',
  'Whitefield',
  'Indiranagar',
  'Hebbal',
  'Jayanagar',
  'Electronic City',
  'Yeshwanthpur',
  'M.G. Road',
  'Marathahalli',
  'HSR Layout',
  'Banashankari',
  'Vijayanagar',
  'Rajajinagar',
  'Bellandur',
  'Sarjapur Road',
  'Silk Board',
  'KR Puram',
]

function hasMeaningfulQuery(query) {
  return (query.match(/[\p{L}\p{N}]/gu) || []).length >= MIN_QUERY_CHARACTERS
}

function primaryLocationName(displayName) {
  return displayName
    .split(',')[0]
    .replace(/\s*\([^)]*\)/g, '')
    .trim()
    .toLocaleLowerCase()
}

function mergeLocationSuggestions(results, query) {
  const merged = []
  const seenNames = new Set()

  for (const result of results) {
    const key = result.display_name.trim().toLocaleLowerCase()
    if (!seenNames.has(key)) {
      merged.push(result)
      seenNames.add(key)
    }
  }

  const matchingHints = BENGALURU_LOCATION_HINTS
    .filter((name) => name.toLocaleLowerCase().startsWith(query.toLocaleLowerCase()))

  for (const name of matchingHints) {
    const key = name.toLocaleLowerCase()
    if (merged.some((result) => primaryLocationName(result.display_name) === key)) continue
    if (seenNames.has(key)) continue

    merged.push({
      display_name: `${name}, Bengaluru`,
      source: 'hint',
    })
    seenNames.add(key)
  }

  return merged
}

function LocationAutocomplete({ id, label, marker, placeholder, location, onChange }) {
  const fieldRef = useRef(null)
  const requestId = useRef(0)
  const activeController = useRef(null)
  const [suggestions, setSuggestions] = useState([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [searchError, setSearchError] = useState(false)
  const [searchErrorMessage, setSearchErrorMessage] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const listId = `${id}-suggestions`

  useEffect(() => {
    const query = location.query.trim()
    if (location.selected || !hasMeaningfulQuery(query)) return undefined

    const controller = new AbortController()
    const currentRequestId = ++requestId.current
    activeController.current = controller

    const timer = window.setTimeout(async () => {
      try {
        let results = suggestionCache.get(query.toLocaleLowerCase())
        if (!results) {
          const response = await fetch(getLocationSuggestionsUrl(query), { signal: controller.signal })
          if (!response.ok) throw new Error('Location search failed.')
          const payload = await response.json()
          if (!Array.isArray(payload?.suggestions)) throw new Error('Location search returned invalid data.')
          results = payload.suggestions
          if (suggestionCache.size >= 60) {
            suggestionCache.delete(suggestionCache.keys().next().value)
          }
          suggestionCache.set(query.toLocaleLowerCase(), results)
        }

        if (controller.signal.aborted || currentRequestId !== requestId.current) return
        setSuggestions(mergeLocationSuggestions(results, query))
        setActiveIndex(-1)
        setSearchError(false)
      } catch (requestError) {
        if (requestError.name !== 'AbortError' && currentRequestId === requestId.current) {
          setSuggestions([])
          setSearchError(true)
          setSearchErrorMessage('Unable to search locations. Please try again.')
        }
      } finally {
        if (!controller.signal.aborted && currentRequestId === requestId.current) {
          setLoadingSuggestions(false)
        }
      }
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
      if (activeController.current === controller) activeController.current = null
    }
  }, [location.query, location.selected])

  useEffect(() => {
    function closeOnOutsidePointer(event) {
      if (!fieldRef.current?.contains(event.target)) {
        setIsOpen(false)
        setActiveIndex(-1)
      }
    }

    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer)
  }, [])

  async function selectSuggestion(suggestion) {
    requestId.current += 1
    activeController.current?.abort()
    activeController.current = null

    if (suggestion.source === 'hint') {
      const controller = new AbortController()
      const currentRequestId = requestId.current
      activeController.current = controller
      setSuggestions([])
      setLoadingSuggestions(true)
      setSearchError(false)
      setSearchErrorMessage('')
      setIsOpen(true)
      setActiveIndex(-1)

      try {
        const response = await fetch(getLocationResolveUrl(suggestion.display_name), {
          signal: controller.signal,
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload?.detail?.message || 'Nominatim could not resolve this location.')
        }
        if (
          !Number.isFinite(payload?.latitude)
          || !Number.isFinite(payload?.longitude)
          || payload.latitude < -90
          || payload.latitude > 90
          || payload.longitude < -180
          || payload.longitude > 180
        ) {
          throw new Error('Nominatim returned invalid coordinates for this location.')
        }
        if (controller.signal.aborted || currentRequestId !== requestId.current) return

        onChange({
          query: payload.display_name,
          selected: {
            display_name: payload.display_name,
            latitude: payload.latitude,
            longitude: payload.longitude,
          },
        })
        setSuggestions([])
        setLoadingSuggestions(false)
        setSearchError(false)
        setSearchErrorMessage('')
        setIsOpen(false)
        setActiveIndex(-1)
      } catch (requestError) {
        if (requestError.name !== 'AbortError' && currentRequestId === requestId.current) {
          setSuggestions([])
          setLoadingSuggestions(false)
          setSearchError(true)
          setSearchErrorMessage(requestError.message || 'Nominatim could not resolve this location.')
        }
      } finally {
        if (activeController.current === controller) activeController.current = null
      }
      return
    }

    onChange({
      query: suggestion.display_name,
      selected: {
        display_name: suggestion.display_name,
        latitude: suggestion.latitude,
        longitude: suggestion.longitude,
      },
    })
    setSuggestions([])
    setLoadingSuggestions(false)
    setSearchError(false)
    setSearchErrorMessage('')
    setIsOpen(false)
    setActiveIndex(-1)
  }

  function handleKeyDown(event) {
    if (event.key === 'Escape' && isOpen) {
      event.preventDefault()
      setIsOpen(false)
      setActiveIndex(-1)
      return
    }

    if (!isOpen || suggestions.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => (current + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => (current <= 0 ? suggestions.length - 1 : current - 1))
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault()
      selectSuggestion(suggestions[activeIndex])
    }
  }

  const showSuggestions = !location.selected && isOpen && (
    loadingSuggestions || searchError || suggestions.length > 0 || hasMeaningfulQuery(location.query)
  )

  return (
    <div
      className={`search-field${showSuggestions ? ' is-suggestions-open' : ''}`}
      ref={fieldRef}
    >
      <label className="field-label" htmlFor={id}>
        <span className={`field-marker ${marker}`}>{label === 'From' ? 'A' : 'B'}</span>
        {label}
      </label>
      <div className="location-input-wrap">
        <input
          id={id}
          autoComplete="off"
          name={label === 'From' ? 'from' : 'to'}
          placeholder={placeholder}
          aria-label={label}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={Boolean(showSuggestions)}
          aria-controls={listId}
          aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
          value={location.query}
          onFocus={() => {
            if (!location.selected) setIsOpen(true)
          }}
          onChange={(event) => {
            requestId.current += 1
            activeController.current?.abort()
            activeController.current = null
            const query = event.target.value
            onChange({ query, selected: null })
            setSuggestions([])
            setLoadingSuggestions(hasMeaningfulQuery(query))
            setSearchError(false)
            setSearchErrorMessage('')
            setIsOpen(true)
            setActiveIndex(-1)
          }}
          onKeyDown={handleKeyDown}
        />
        {location.query && (
          <button
            className="location-clear"
            type="button"
            aria-label={`Clear ${label} location`}
            onClick={() => {
              requestId.current += 1
              activeController.current?.abort()
              activeController.current = null
              onChange({ query: '', selected: null })
              setSuggestions([])
              setLoadingSuggestions(false)
              setSearchError(false)
              setSearchErrorMessage('')
              setIsOpen(true)
              setActiveIndex(-1)
            }}
          >
            ×
          </button>
        )}
      </div>
      {showSuggestions && (
        <div className="location-suggestions" id={listId}>
          {loadingSuggestions ? (
            <p className="suggestion-message" role="status">Searching locations...</p>
          ) : searchError ? (
            <p className="suggestion-message suggestion-error" role="status">{searchErrorMessage}</p>
          ) : suggestions.length === 0 ? (
            <p className="suggestion-message" role="status">No locations found</p>
          ) : (
            <div role="listbox" aria-label={`${label} location suggestions`}>
              {suggestions.map((suggestion, index) => {
                const [primary, ...contextParts] = suggestion.display_name.split(',')
                return (
                  <button
                    className={`location-suggestion${activeIndex === index ? ' is-active' : ''}`}
                    id={`${listId}-${index}`}
                    type="button"
                    role="option"
                    aria-selected={activeIndex === index}
                    key={`${suggestion.source || 'nominatim'}-${suggestion.display_name}-${suggestion.latitude ?? ''}-${suggestion.longitude ?? ''}`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectSuggestion(suggestion)}
                  >
                    <strong>{primary.trim()}</strong>
                    {contextParts.length > 0 && <span>{contextParts.join(',').trim()}</span>}
                    {suggestion.source === 'hint' && (
                      <small className="suggestion-hint-label">
                        Locality hint · coordinates verified with Nominatim on selection
                      </small>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function RouteSearch({ onSearch, loading }) {
  const [origin, setOrigin] = useState({ query: '', selected: null })
  const [destination, setDestination] = useState({ query: '', selected: null })

  function submitSearch(event) {
    event.preventDefault()
    onSearch({
      from: origin.query,
      to: destination.query,
      originLocation: origin.selected,
      destinationLocation: destination.selected,
    })
  }

  return (
    <form className="search-panel" onSubmit={submitSearch}>
      <LocationAutocomplete
        id="route-origin"
        label="From"
        marker="origin-marker"
        placeholder="Koramangala, Bengaluru"
        location={origin}
        onChange={setOrigin}
      />
      <LocationAutocomplete
        id="route-destination"
        label="To"
        marker="destination-marker"
        placeholder="Whitefield, Bengaluru"
        location={destination}
        onChange={setDestination}
      />
      <button className="find-button" type="submit" disabled={loading}>
        {loading ? (
          <><span className="button-spinner" aria-hidden="true" /> Finding routes...</>
        ) : (
          <>Find routes <span aria-hidden="true">&#8594;</span></>
        )}
      </button>
    </form>
  )
}

export default RouteSearch
