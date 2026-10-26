// The council view: a pane beside the chat and a one-line bar above the prompt, both showing the open
// council run. It only reads: it finds the run the helper would pick and asks the council's own status
// reader (scripts/status.py --json) for it, so both say exactly what the status card says. Nothing
// here writes a council file. If a Claude Code update breaks it, only the view disappears; the council
// keeps working through its helper and its settings hooks.
import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'
import type { CouncilReading, CouncilSeat } from '../types'
import { MOST_SEATS, SEAT_WORD, cut, fmtTokens, headSvg, quip, rasterCells, sceneSvg } from './council-scene'

const reading = atom({ plugin: 'small-council', key: 'reading' } as const, null)
const dismissed = atom({ plugin: 'small-council', key: 'dismissed' } as const, '')
const paneClosed = atom({ plugin: 'small-council', key: 'paneClosed' } as const, '')

const PANE = 'council'
const COMMAND = 'council-view'
// The terminal's colours for the words: mid tones, readable on a light or a dark terminal.
const ROLE_COLOR: Record<string, string> = {
  accent: '#7f77dd',
  success: '#1d9e75',
  warning: '#ba7517',
  danger: '#e24b4a',
  neutral: '#888780',
}
const SEAT_COLOR: Record<string, string> = {
  done: '#1d9e75',
  running: '#7f77dd',
  queued: '#888780',
  failed: '#e24b4a',
  blocked: '#e24b4a',
}
const SEAT_MARK: Record<string, string> = { done: '●', running: '◐', queued: '○', failed: '✕', blocked: '✕' }
const INK = '#888780'
const WARN = '#ba7517'
const TICK_MS = 2000
const OPEN_EVERY = 5 // ticks: an open run is re-read every 10 s even when nothing in this session moved

// Per module load; a reload starts them again, which is fine for caches.
let home: string | null | undefined
let startCwd = ''
let tree = ''
let python: string[] | null = null
let lastShown = ''
let openedFor = ''
let problem = '' // why the last refresh found nothing to show, for /council-view to say
let isDirty = true
let isBusy = false
let ticks = 0

const slashes = (p: string): string => p.replace(/\\/g, '/').replace(/\/+$/, '')
const same = (a: string, b: string): boolean => slashes(a).toLowerCase() === slashes(b).toLowerCase()

// A run's state is read by its header only, above its first "## " heading (convention EC-5): a
// "status:" line in the notes below is never the run's status.
const field = (text: string, name: string): string => {
  const head = text.split(/\r?\n## /)[0] ?? ''
  const m = head.match(new RegExp(`^(?:\\uFEFF)?${name}:[ \\t]*(.*)$`, 'm'))
  return m ? (m[1] ?? '').trim().replace(/[ \t][ \t]+#.*$/, '') : ''
}

// The main checkout's .council, as the helper's council_home finds it, even from a linked worktree.
async function findHome($: any): Promise<string | null> {
  const cwd = slashes(startCwd || (await $.session.cwd()))
  tree = cwd
  try {
    const r = await $.process.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir', '--show-toplevel'], {
      cwd,
      timeoutMs: 5000,
    })
    if (r.exitCode === 0) {
      const [common = '', top = ''] = r.stdout.split(/\r?\n/).map((s: string) => slashes(s.trim()))
      if (top) tree = top
      const main = common.replace(/\/\.git$/, '')
      if (main && main !== common && (await $.fs.exists(`${main}/.council/runs`))) return `${main}/.council`
    }
  } catch {
    // no git: fall back to the folder itself
  }
  try {
    return (await $.fs.exists(`${cwd}/.council/runs`)) ? `${cwd}/.council` : null
  } catch {
    return null
  }
}

type Found = { path: string; name: string; isOpen: boolean }

// The helper's own order (resolve_run in bin/council): the open run on this tree (a run with no
// code-root counts as this tree's), else this session's open run on another tree. A run the view was
// showing stays (as finished) after it closes, so its last state can still be read in the pane.
async function findRun($: any, at: string): Promise<Found | null> {
  let entries: { name: string; kind: string }[]
  try {
    entries = await $.fs.list(`${at}/runs`)
  } catch {
    return null
  }
  let session = ''
  try {
    session = String(await $.session.id())
  } catch {
    // no id: the open run on this tree still shows
  }
  // The newest 60 folders: an open run is nearly always among them, and each refresh stays cheap.
  const names = entries.filter(x => x.kind === 'dir').map(x => x.name).sort().reverse().slice(0, 60)
  let mine: Found | null = null
  let shown: Found | null = null
  for (const name of names) {
    const path = `${at}/runs/${name}`
    let text = ''
    try {
      text = await $.fs.read(`${path}/session-state.md`)
    } catch {
      continue
    }
    const isOpen = field(text, 'status').split(' ')[0] === 'in-progress'
    const root = field(text, 'code-root')
    if (isOpen && (!root || same(root, tree))) return { path, name, isOpen }
    if (isOpen && !mine && session && field(text, 'session') === session) mine = { path, name, isOpen }
    if (name === lastShown) shown = { path, name, isOpen }
  }
  return mine ?? shown
}

async function readStatus($: any, at: string, run: string): Promise<any | null> {
  const root = slashes(String($.plugin.root))
  const args = [`${root}/scripts/status.py`, '--run', run, '--home', at, '--json']
  const candidates = python ? [python] : [['python'], ['py', '-3'], ['python3']]
  const tried: string[] = []
  for (const py of candidates) {
    try {
      const r = await $.process.run([...py, ...args], { timeoutMs: 20000 })
      if (r.exitCode !== 0) {
        tried.push(`${py.join(' ')} exited ${r.exitCode}${r.stderr ? ': ' + cut(String(r.stderr).trim(), 120) : ''}`)
        continue
      }
      python = py
      return JSON.parse(r.stdout)
    } catch (err) {
      // not installed under this name, or not a reading: try the next
      tried.push(`${py.join(' ')}: ${cut(String((err as any)?.message ?? err), 120)}`)
    }
  }
  problem = `the status reader could not run (${tried.join('; ')})`
  return null
}

const list = (v: unknown): any[] => (Array.isArray(v) ? v : [])

export const toReading = (d: any, isOpen: boolean): CouncilReading => {
  const attention = list(d?.attention).filter(a => a && typeof a.text === 'string')
  const usage = d?.usage ?? {}
  return {
    runId: String(d?.run?.id ?? ''),
    project: String(d?.run?.project ?? ''),
    mode: String(d?.run?.mode_label ?? d?.run?.mode ?? 'Council'),
    phase: String(d?.run?.phase_label ?? d?.run?.phase ?? ''),
    stage: Number(d?.run?.stage?.n ?? 0) || 0,
    stages: Number(d?.run?.stage?.of ?? 10) || 10,
    state: String(d?.state?.label ?? ''),
    summary: String(d?.state?.summary ?? ''),
    role: String(d?.state?.role ?? 'neutral'),
    seats: list(d?.seats).map(
      (s): CouncilSeat => ({
        slug: String(s?.slug ?? ''),
        name: String(s?.name ?? s?.slug ?? ''),
        state: String(s?.state ?? ''),
        tokens: Number(s?.tokens ?? 0) || 0,
      }),
    ),
    working: list(d?.progress?.working).map(String).filter(Boolean),
    tokens: Number(usage.tokens_known ?? usage.tokens ?? 0) || 0,
    budget: Number(usage.share ?? 0) || Number(usage.estimate ?? 0) || 0,
    spend: String(usage.spend_text ?? usage.text ?? ''),
    checks: String(d?.progress?.checks ?? ''),
    next: String(d?.progress?.next ?? ''),
    needsYou: attention.filter(a => Number(a.severity) >= 2).map(a => String(a.text)),
    notes: attention.filter(a => !(Number(a.severity) >= 2)).map(a => String(a.text)),
    recent: list(d?.recent).slice(-3).map(i => `${i?.clock ?? ''} ${i?.text ?? ''}`.trim()),
    isClosed: !isOpen,
  }
}

// The pane opens by itself once per run (unasked: Claude Code seats it where there is room), never
// again for a run whose pane the person closed; /council-view and the bar's button open it on asking.
async function openUnasked($: any, r: CouncilReading): Promise<void> {
  if (r.isClosed || openedFor === r.runId || (await read($, paneClosed)) === r.runId) return
  openedFor = r.runId
  try {
    await $.ui.open({ id: PANE, title: 'Council' })
  } catch {
    // no surface places panes here: the bar still shows
  }
}

async function refreshOnce($: any): Promise<void> {
  // A home once found is kept; none found is looked for again, as a run may open the council later.
  if (!home) home = await findHome($)
  const found = home ? await findRun($, home) : null
  problem = home ? (found ? '' : `no open run for this session or for ${tree}`) : `no .council folder found from ${tree}`
  if (!found) {
    if ((await read($, reading)) !== null) await update($, reading, () => null)
    return
  }
  const d = await readStatus($, home as string, found.path)
  if (!d) return // keep the last reading rather than guess
  lastShown = found.name
  const r = toReading(d, found.isOpen)
  await update($, reading, () => r)
  await openUnasked($, r)
}

async function refresh($: any): Promise<void> {
  if (isBusy) {
    isDirty = true
    return
  }
  isBusy = true
  try {
    await refreshOnce($)
  } catch (err) {
    // The timer calls this every few seconds: a fault keeps the last reading and says why on asking.
    problem = `the view could not refresh: ${cut(String((err as any)?.message ?? err), 120)}`
  } finally {
    isBusy = false
  }
}

const stageWords = (r: CouncilReading): string =>
  r.isClosed ? r.state || 'Finished' : r.stage ? `stage ${r.stage} of ${r.stages}: ${r.phase}` : r.phase

const spendShort = (r: CouncilReading): string =>
  r.tokens ? (r.budget ? `${fmtTokens(r.tokens)} of ${fmtTokens(r.budget)}` : `${fmtTokens(r.tokens)} tokens`) : ''

export const barWords = (r: CouncilReading): string => {
  const parts = [r.mode, stageWords(r)]
  if (!r.isClosed && r.needsYou.length) parts.push('needs you')
  if (!r.isClosed && r.working.length === 1) parts.push(`${r.working[0]} working`)
  if (!r.isClosed && r.working.length > 1) parts.push(`${r.working.length} agents working`)
  const spent = spendShort(r)
  if (spent) parts.push(spent)
  return parts.join(' · ')
}

const done = (r: CouncilReading, i: number): boolean => r.isClosed || i < r.stage - 1
const current = (r: CouncilReading, i: number): boolean => !r.isClosed && i === r.stage - 1

export const stripText = (r: CouncilReading): string =>
  Array.from({ length: r.stages }, (_, i) => (done(r, i) ? '■' : current(r, i) ? '▣' : '□')).join('')

// The desktop and the editor draw an Svg as a picture, so it brings its own colours: one palette for a
// light page and one for a dark page, picked by the page's own colour scheme.
const SVG_STYLE =
  '<style>' +
  '.ink{fill:#3d3d3a}.sub{fill:#73726c}.line{stroke:#d3d1c7}.well{fill:#f1efe8}.track{fill:#e4e2da}' +
  '.done{fill:#1d9e75}.running{fill:#7f77dd}.failed,.blocked{fill:#e24b4a}.queued{fill:none;stroke:#b4b2a9}' +
  '.on{fill:#ffffff}.off{fill:#888780}.halo{fill:#7f77dd;opacity:.25}' +
  '@media (prefers-color-scheme: dark){' +
  '.ink{fill:#e8e6dc}.sub{fill:#a3a29b}.line{stroke:#444441}.well{fill:#262624}.track{fill:#3a3a37}' +
  '.done{fill:#2bb487}.running{fill:#9c95ec}.queued{stroke:#5f5e5a}.off{fill:#a3a29b}.halo{fill:#9c95ec}}' +
  '</style>'

const svgDoc = (w: number, h: number, body: string): string =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" ` +
  `font-family="system-ui, -apple-system, 'Segoe UI', sans-serif">${SVG_STYLE}${body}</svg>`

// The ten stages as one segmented track: done ones filled, the current one pulsing.
const stripSvg = (r: CouncilReading, width = 150): string => {
  const G = 3
  const w = (width - G * (r.stages - 1)) / r.stages
  const cells = Array.from({ length: r.stages }, (_, i) => {
    const x = (i * (w + G)).toFixed(1)
    const cls = done(r, i) ? 'done' : current(r, i) ? 'running' : 'track'
    const pulse = current(r, i)
      ? '<animate attributeName="opacity" values="1;.45;1" dur="2s" repeatCount="indefinite"/>'
      : ''
    return `<rect class="${cls}" x="${x}" y="1" width="${w.toFixed(1)}" height="6" rx="3">${pulse}</rect>`
  }).join('')
  return svgDoc(width, 8, cells)
}

export const meter = (r: CouncilReading, cells = 16): string => {
  if (!r.budget) return ''
  const filled = Math.min(cells, Math.round((r.tokens / r.budget) * cells))
  return '█'.repeat(filled) + '░'.repeat(cells - filled)
}

// The theme's own colours, so words follow the person's light or dark theme.
const ROLE_THEME: Record<string, string> = { accent: 'suggestion', success: 'success', warning: 'warning', danger: 'error' }

const STATE_THEME: Record<string, string> = { running: 'suggestion', done: 'success', failed: 'error', blocked: 'error' }

// The squad: one row per seat, its head, its name and state, its tokens and a line about it.
function squad(ui: any, r: CouncilReading): any {
  const { Box, Text, Svg } = ui
  return (
    <Box flexDirection="column" gap={0}>
      {r.seats.slice(0, MOST_SEATS).map(s => (
        <Box flexDirection="row" gap={1} alignItems="center">
          <Svg source={headSvg(s)} alt={s.name} width={28} height={24} />
          <Box flexDirection="column" flexGrow={1}>
            <Box flexDirection="row" gap={1}>
              <Text size="footnote" weight={s.state === 'running' ? 'semibold' : 'medium'} wrap="truncate-end">
                {s.name}
              </Text>
              <Text size="footnote" color={STATE_THEME[s.state] ?? 'inactive'}>
                {SEAT_WORD[s.state] ?? s.state}
              </Text>
            </Box>
            <Text size="caption" dimColor italic wrap="truncate-end">
              {quip(s)}
            </Text>
          </Box>
          <Text size="footnote" dimColor tabular>
            {s.tokens ? fmtTokens(s.tokens) : ''}
          </Text>
        </Box>
      ))}
    </Box>
  )
}

// The pane where pictures draw (desktop, editor): the hall, a heading line, what needs the person,
// the squad, then the spend, the next step and the latest events in words.
function drawnPane(ui: any, r: CouncilReading): any {
  const { Box, Text, Svg } = ui
  const alt =
    `${r.mode}, ${r.state}${r.isClosed ? '' : r.stage ? `, stage ${r.stage} of ${r.stages}: ${r.phase}` : ''}. ` +
    (r.seats.length ? r.seats.map(s => `${s.name} ${SEAT_WORD[s.state] ?? s.state}`).join(', ') : 'No seats yet')
  const label = (words: string) => (
    <Text size="caption" weight="medium" dimColor>
      {words}
    </Text>
  )
  return (
    <Box flexDirection="column" gap={1}>
      <Box flexDirection="row" justifyContent="space-between" alignItems="center">
        <Text weight="semibold">{`${r.mode}${r.isClosed || !r.phase ? '' : ' · ' + r.phase}`}</Text>
        <Text size="footnote" weight="medium" color={ROLE_THEME[r.role] ?? 'inactive'}>
          {r.state}
        </Text>
      </Box>
      <Svg source={sceneSvg(r)} alt={alt} isInteractive />
      {r.summary && r.summary !== r.state ? (
        <Text size="footnote" wrap="wrap">
          {r.summary}
        </Text>
      ) : null}
      {r.needsYou.length ? (
        <Box flexDirection="column" borderStyle="round" borderColor="warning" paddingX={1}>
          <Text size="footnote" weight="semibold" color="warning">
            Needs you
          </Text>
          {r.needsYou.map(item => (
            <Text size="footnote" wrap="wrap">
              {item}
            </Text>
          ))}
        </Box>
      ) : r.isClosed ? null : (
        <Text size="footnote" color="success">
          ✓ Nothing needs you right now
        </Text>
      )}
      {r.seats.length ? squad(ui, r) : null}
      {r.spend ? (
        <Text size="caption" dimColor wrap="wrap">
          {r.spend}
        </Text>
      ) : null}
      {r.notes.length ? (
        <Box flexDirection="column">
          {r.notes.slice(0, 2).map(item => (
            <Text size="footnote" dimColor wrap="wrap">
              {`Note: ${item}`}
            </Text>
          ))}
        </Box>
      ) : null}
      {r.next && !r.isClosed ? (
        <Box flexDirection="column">
          {label('Next')}
          <Text size="footnote" wrap="wrap">
            {cut(r.next, 200)}
          </Text>
        </Box>
      ) : null}
      {r.recent.length ? (
        <Box flexDirection="column">
          {label('Recent')}
          {r.recent.map(item => (
            <Text size="footnote" dimColor tabular wrap="truncate-end">
              {item}
            </Text>
          ))}
        </Box>
      ) : null}
    </Box>
  )
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    startCwd = String((started as any)?.cwd ?? (e as any).cwd ?? '')
    try {
      await $.command.register({ name: COMMAND, description: 'Show the open council run in a pane beside the chat' })
    } catch {
      // the bar still shows, and the pane still opens by itself
    }
    $.clock.every(TICK_MS, () => {
      void (async () => {
        ticks += 1
        const r = await read($, reading)
        const isDue = isDirty || (r !== null && !r.isClosed && ticks % OPEN_EVERY === 0)
        if (!isDue) return
        isDirty = false
        await refresh($)
      })()
    })
    return started
  })

  on('command.run', { command: COMMAND }, async $ => {
    await refresh($)
    const r = await read($, reading)
    if (!r) return { text: `No open council run on this working tree or in this session${problem ? ` (${problem})` : ''}.` }
    await update($, paneClosed, () => '')
    await $.ui.open({ id: PANE, title: 'Council' })
    return { text: `Council pane opened: ${barWords(r)}` }
  })

  // The person closed the pane: it stays closed for this run, until they ask for it again.
  on('ui.close', async ($, e, next) => {
    try {
      if (e.id === PANE && e.origin.kind === 'person') {
        const r = await read($, reading)
        if (r) await update($, paneClosed, () => r.runId)
      }
    } catch {
      // remembering is a nicety: the pane closes either way
    }
    return next(e)
  })

  // The council moves through its helper and its agents: re-read after either, and after each turn.
  on('tool.call', { tool: /^(Bash|PowerShell)$/ }, async ($, e, next) => {
    const result = await next(e)
    if (/\bcouncil\b/.test(String((e as any).command ?? ''))) isDirty = true
    return result
  })
  on('tool.call', { tool: /^(Agent|SendMessage|Workflow)$/ }, async ($, e, next) => {
    try {
      return await next(e)
    } finally {
      isDirty = true
    }
  })
  on('turn.complete', async ($, e, next) => {
    isDirty = true
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const r = await read($, reading)
    const gone = await read($, dismissed)
    // A finished run leaves the bar; the pane keeps its last reading for whoever looks.
    if (r === null || r.isClosed || r.runId === gone || e.props.hasSurvey) return next(e)

    const ui = $.ui.resolve(e)
    const { Box, Text, Button } = ui
    const color = ROLE_COLOR[r.role] ?? INK
    const line = barWords(r)
    const buttons = [
      <Button
        key="council-bar-pane"
        label="Pane"
        plain
        onPress={async () => {
          await update($, paneClosed, () => '')
          await $.ui.open({ id: PANE, title: 'Council' })
        }}
      />,
      <Button key="council-bar-dismiss" label="✕" plain role="dismiss" onPress={() => update($, dismissed, () => r.runId)} />,
    ]

    // The terminal's table has no Svg: text there, the picture elsewhere.
    if (e.surface !== 'terminal' && 'Svg' in ui) {
      const { Svg } = ui as any
      return (
        <Box flexDirection="row" alignItems="center" gap={1}>
          <Text bold>Council</Text>
          <Svg source={stripSvg(r, 120)} alt={`stage ${r.stage} of ${r.stages}`} width={120} height={8} />
          <Text wrap="truncate-end">{line}</Text>
          {buttons}
        </Box>
      )
    }
    return (
      <Box flexDirection="row" gap={1}>
        <Text color={color}>●</Text>
        <Text bold>Council</Text>
        <Text color={color}>{stripText(r)}</Text>
        <Text wrap="truncate-end">{line}</Text>
        {buttons}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const ui = $.ui.resolve(e)
    const { Box, Text } = ui
    const r = await read($, reading)
    if (!r) {
      return (
        <Box flexDirection="column">
          <Text dimColor>No open council run on this working tree or in this session.</Text>
        </Box>
      )
    }
    const color = ROLE_COLOR[r.role] ?? INK
    const hasSvg = e.surface !== 'terminal' && 'Svg' in ui
    if (hasSvg) return drawnPane(ui, r)
    const width = Math.max(20, (e.props.bodyColumns ?? 40) - 2)
    const rows: any[] = []
    rows.push(
      <Text bold wrap="truncate-end">
        {cut(`${r.project ? r.project + ' · ' : ''}${r.mode}`, width)}
      </Text>,
    )
    rows.push(
      <Text color={color} wrap="wrap">
        {r.state}
        {r.summary && r.summary !== r.state ? ` — ${r.summary}` : ''}
      </Text>,
    )
    if (!r.isClosed) rows.push(<Text wrap="truncate-end">{`${stripText(r)} ${stageWords(r)}`}</Text>)
    if (r.seats.length) {
      // Each seat's person in half-block cells beside its line, where the terminal has room for them.
      const { Raster } = ui as any
      const roomy = Raster && width >= 36
      for (const [i, s] of r.seats.slice(0, MOST_SEATS).entries()) {
        const line = (
          <Box flexDirection="row" gap={1}>
            <Text color={SEAT_COLOR[s.state] ?? INK}>{SEAT_MARK[s.state] ?? '·'}</Text>
            <Text wrap="truncate-end">
              {`${cut(s.name, 18).padEnd(18)} ${(SEAT_WORD[s.state] ?? s.state).padEnd(8)}${s.tokens ? ' ' + fmtTokens(s.tokens) : ''}`}
            </Text>
          </Box>
        )
        if (!roomy) {
          rows.push(line)
          continue
        }
        const art = rasterCells(s)
        rows.push(
          <Box flexDirection="row" gap={1}>
            <Raster key={`council-seat-${i}`} columns={art.columns} rows={art.rows} cells={art.cells} />
            <Box flexDirection="column" justifyContent="center">
              {line}
              <Text dimColor italic wrap="truncate-end">
                {`  ${quip(s)}`}
              </Text>
            </Box>
          </Box>,
        )
      }
      if (r.seats.length > MOST_SEATS) rows.push(<Text dimColor>{`+${r.seats.length - MOST_SEATS} more seats`}</Text>)
    } else {
      rows.push(<Text dimColor>No seats yet.</Text>)
    }
    if (r.needsYou.length) {
      for (const item of r.needsYou) rows.push(<Text color={WARN} wrap="wrap">{`Needs you: ${item}`}</Text>)
    } else if (!r.isClosed) {
      rows.push(<Text dimColor>Needs you: nothing right now.</Text>)
    }
    for (const item of r.notes.slice(0, 2)) rows.push(<Text dimColor wrap="wrap">{`Note: ${item}`}</Text>)
    if (r.tokens) {
      const bar = meter(r)
      rows.push(<Text wrap="truncate-end">{`Tokens ${bar ? bar + ' ' : ''}${spendShort(r)}`}</Text>)
      if (r.spend) rows.push(<Text dimColor wrap="wrap">{r.spend}</Text>)
    }
    if (r.checks) rows.push(<Text wrap="truncate-end">{`Checks ${r.checks}`}</Text>)
    if (r.next && !r.isClosed) rows.push(<Text dimColor wrap="wrap">{`Next: ${cut(r.next, 200)}`}</Text>)
    for (const item of r.recent) rows.push(<Text dimColor wrap="truncate-end">{item}</Text>)
    return <Box flexDirection="column">{rows}</Box>
  })
}
