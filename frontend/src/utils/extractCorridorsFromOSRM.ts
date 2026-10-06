export interface AvailableCorridor {
  id: string
  name: string
  roadKeywords: readonly string[]
}

export interface OSRMRouteData {
  legs?: Array<{
    steps?: Array<{
      name?: string | null
    } | null> | null
  } | null> | null
}

function normalizeRoadName(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}

export function extractCorridorsFromOSRM(
  osrmRouteData: OSRMRouteData | null | undefined,
  availableCorridors: readonly AvailableCorridor[],
): AvailableCorridor[] {
  const steps = osrmRouteData?.legs?.[0]?.steps ?? []
  const roadNames = new Set<string>()

  for (const step of steps) {
    const name = step?.name?.trim()
    if (name) roadNames.add(normalizeRoadName(name))
  }
  const normalizedRoadNames = [...roadNames]

  const matchedCorridors = availableCorridors.filter((corridor) =>
    corridor.roadKeywords.some((keyword) => {
      const normalizedKeyword = normalizeRoadName(keyword)
      return normalizedKeyword && normalizedRoadNames.some((roadName) => roadName.includes(normalizedKeyword))
    }),
  )

  if (matchedCorridors.length > 0) return matchedCorridors

  // This fallback is not evidence that the route passes through this corridor.
  const fallbackCorridor = availableCorridors[0]
  return fallbackCorridor ? [fallbackCorridor] : []
}
