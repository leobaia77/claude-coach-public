const BASE = 'https://api.hevyapp.com/v1'

interface HevyCreds {
  apiKey: string
}

async function hevyGet(apiKey: string, path: string): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, { headers: { 'api-key': apiKey } })
  if (!res.ok) throw new Error(`Hevy ${path} → HTTP ${res.status}`)
  return res.json()
}

// Validate a Hevy API key by hitting the cheap workout-count endpoint.
export async function testHevyKey(apiKey: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/workouts/count`, { headers: { 'api-key': apiKey } })
    return res.status === 200
  } catch {
    return false
  }
}

export const hevy = {
  getWorkouts: (c: HevyCreds, page = 1, pageSize = 10) =>
    hevyGet(c.apiKey, `/workouts?page=${page}&pageSize=${pageSize}`),
  getWorkoutCount: (c: HevyCreds) => hevyGet(c.apiKey, '/workouts/count'),
  getRoutines: (c: HevyCreds, page = 1, pageSize = 10) =>
    hevyGet(c.apiKey, `/routines?page=${page}&pageSize=${pageSize}`),
  createRoutine: async (c: HevyCreds, routine: unknown) => {
    const res = await fetch(`${BASE}/routines`, {
      method: 'POST',
      headers: { 'api-key': c.apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify(routine),
    })
    if (!res.ok) throw new Error(`Hevy create routine → HTTP ${res.status}: ${await res.text()}`)
    return res.json()
  },
}

export type { HevyCreds }
