// The council view's values in $.state (hooks/council-view.tsx). One reading of the open run, taken
// from scripts/status.py --json, so the pane and the bar say what the status card says.
export type CouncilSeat = {
  slug: string
  name: string
  state: string // done, running, queued, failed, blocked
  tokens: number
}

export type CouncilReading = {
  runId: string
  project: string
  mode: string
  phase: string
  stage: number
  stages: number
  state: string
  summary: string
  role: string // accent, success, warning, danger, neutral
  seats: CouncilSeat[]
  working: string[]
  tokens: number
  budget: number // the agents' share, else the estimate; 0 when the run has neither
  spend: string
  checks: string
  next: string
  needsYou: string[] // the status card's items of severity 2 and up
  notes: string[] // the rest of its attention items
  recent: string[]
  isClosed: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'small-council': {
      reading: CouncilReading | null
      dismissed: string // the run whose bar the person closed
      paneClosed: string // the run whose pane the person closed: not opened again unasked
    }
  }
}
