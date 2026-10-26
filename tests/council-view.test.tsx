// Run: claude plugin test .
// The world beneath the plugin is a fixture: one council home with an open build run at stage 8, read
// through a status.py answer shaped like the real `--json` reading. Hooks beneath answer `{ value }`.
import { expect, mock, test } from 'claude-code/testing'

const SURFACES = ['terminal', 'desktop'] as const
const BAND = { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 160, scroll: { offset: 0, bodyRows: 3 }, view: {} } as any
const PANE = { title: 'Council', isFocused: false, bodyColumns: 44, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} } as any
const OPEN = '2026-10-05-090000-implement'
const OLD = '2026-10-04-204701-implement'
const CRLF = '\r\n'
// On Windows the engine hands fs hooks the path with backslashes.
const path = (e: any): string => String(e.path).replace(/\\/g, '/')

const STATUS = (over: Record<string, unknown> = {}) => ({
  schema: 'council.run-status/1',
  run: { id: OPEN, project: 'proj', mode_label: 'Build', phase_label: 'Checking the work', stage: { n: 8, of: 10 } },
  state: { key: 'running', label: 'Running', summary: 'Verifiers are checking the build.', role: 'accent' },
  seats: [
    { slug: 'verify-1', name: 'Verifier 1', state: 'done', tokens: 74820 },
    { slug: 'verify-2', name: 'Verifier 2', state: 'running', tokens: null },
  ],
  progress: { working: ['Verifier 2'], checks: '12 passing', next: 'Converge the verdicts' },
  usage: { tokens_known: 164000, share: 200000, estimate: 250000, spend_text: "spent 164k of the agents' 200k share (estimated 250k)" },
  attention: [],
  recent: [{ clock: '16:25', text: 'Check ruff passed' }],
  ...over,
})

type World = {
  status?: string
  session?: string
  codeRoot?: string
  notes?: string
  omit?: string // a header line left out
  reading?: Record<string, unknown>
  calls?: string[][]
  opens?: unknown[]
}

function world(on: any, opts: World = {}) {
  const state =
    [
      `status: ${opts.status ?? 'in-progress'}`,
      'mode: council-implement',
      `session: ${opts.session ?? 'sess-1'}`,
      `code-root: ${opts.codeRoot ?? 'C:/elsewhere'}`,
    ]
      .filter(line => !opts.omit || !line.startsWith(opts.omit + ':'))
      .join(CRLF) + CRLF + (opts.notes ?? '')
  const value = (v: unknown) => ({ value: v })
  const ran = (exitCode: number, stdout: string) =>
    value({ exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false })

  on('session.start', async (_$: any, e: any) => ({ cwd: e.cwd }))
  on('session.id', async () => value('sess-1'))
  on('command.register', async () => value({ command: 'council-view' }))
  on('ui.open', async (_$: any, e: any) => {
    opts.opens?.push(e)
    return value({ isPlaced: true })
  })
  // The engine's own drawing beneath the view: an empty box.
  on('ui.render', async ($: any, e: any) => {
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
  on('fs.exists', async (_$: any, e: any) => value(path(e).endsWith('/.council/runs')))
  on('fs.list', async () =>
    value([
      { name: OLD, kind: 'dir', size: 0 },
      { name: OPEN, kind: 'dir', size: 0 },
    ]),
  )
  on('fs.read', async (_$: any, e: any) =>
    value(path(e).includes(OPEN) ? state : 'status: complete\nsession: other\n'),
  )
  on('process.run', async (_$: any, e: any) => {
    const argv = [...e.argv] as string[]
    opts.calls?.push(argv)
    if (argv[0] === 'git') return ran(0, 'C:/proj/.git\nC:/proj\n')
    if (argv.some(a => a.endsWith('/scripts/status.py'))) return ran(0, JSON.stringify(STATUS(opts.reading)))
    return ran(127, '')
  })
}

async function start($: any, on: any) {
  const clock = mock.clock(on)
  await $.session.start({ cwd: 'C:/proj', surface: 'terminal', isInteractive: true })
  await clock.advance(2000)
  return clock
}

const band = ($: any, surface: (typeof SURFACES)[number]) =>
  $.ui.mount({ plugin: 'small-council', surface, component: 'AbovePrompt', props: BAND })
const pane = ($: any, surface: (typeof SURFACES)[number]) =>
  $.ui.mount({ plugin: 'small-council', surface, component: 'Pane', requestId: 'council', props: PANE })

// The pane's hall: of its pictures, the one that is the hall.
const table = async (ui: any) =>
  (await ui.findAll({ type: 'Svg' })).find((x: any) => String(x.props?.source ?? '').includes('id="hall"'))

const drew = async (ui: any) => JSON.stringify((await ui.findAll({})).map((x: any) => [x.type, x.text]))

test("the bar draws this session's open run: stage, the agent at work, tokens against the share", async ($, on) => {
  const calls: string[][] = []
  world(on, { calls })
  await start($, on)
  for (const surface of SURFACES) {
    const ui = await band($, surface)
    const has = async (q: any, what: string) => {
      if (!(await ui.find(q))) throw new Error(`${surface}: no ${what}; drew ${await drew(ui)}`)
    }
    await has({ type: 'Text', text: 'Council' }, 'title')
    await has({ type: 'Text', text: 'Build · stage 8 of 10: Checking the work · Verifier 2 working · 164k of 200k' }, 'words')
    if (surface === 'terminal') await has({ type: 'Text', text: '■■■■■■■▣□□' }, 'stage strip')
    else await has({ type: 'Svg' }, 'stage picture')
    await ui.unmount()
  }
  const status = calls.find(a => a.some(x => x.endsWith('/scripts/status.py'))) ?? []
  expect(status.slice(-5)).toEqual(['--run', `C:/proj/.council/runs/${OPEN}`, '--home', 'C:/proj/.council', '--json'])
})

test('the pane lists the seats in the terminal and draws the table elsewhere', async ($, on) => {
  world(on)
  await start($, on)
  const term = await pane($, 'terminal')
  for (const words of [/Verifier 1\s+done\s+75k/, /Verifier 2\s+working/, /Needs you: nothing right now/, /Checks 12 passing/, /Next: Converge/]) {
    if (!(await term.find({ type: 'Text', text: words }))) throw new Error(`terminal pane: no ${words}; drew ${await drew(term)}`)
  }
  expect(await term.find({ type: 'Text', text: /^Tokens █{13}░{3} 164k of 200k$/ })).toBeDefined()
  await term.unmount()

  const desk = await pane($, 'desktop')
  const svg: any = await table(desk)
  if (!svg) throw new Error(`desktop pane: no table; drew ${await drew(desk)}`)
  expect(svg.props.alt).toContain('Verifier 1 done, Verifier 2 working')
  expect(svg.props.source).toContain('<title>Verifier 1: done, 75k tokens</title>')
  expect(await desk.find({ type: 'Text', text: /Verifier 1\s+done/ })).toBeUndefined()
  await desk.unmount()
})

test('a seat name is drawn as text, never as markup', async ($, on) => {
  world(on, { reading: { seats: [{ slug: 'x', name: 'A <b>"bold"</b> seat', state: 'done', tokens: 0 }] } })
  await start($, on)
  const ui = await pane($, 'desktop')
  const svg: any = await table(ui)
  expect(svg.props.source).toContain('A &lt;b&gt;&quot;bold&quot;&lt;/b&gt; seat')
  expect(svg.props.source).not.toContain('<b>')
})

test('only items of severity 2 and up read as "needs you"; the rest are notes', async ($, on) => {
  world(on, {
    reading: {
      state: { key: 'running', label: 'Running', role: 'accent' },
      attention: [{ kind: 'estimate', severity: 1, text: 'Spend passed the estimate.' }],
    },
  })
  await start($, on)
  const ui = await band($, 'terminal')
  expect(await ui.find({ type: 'Text', text: /needs you/ })).toBeUndefined()
  const p = await pane($, 'terminal')
  expect(await p.find({ type: 'Text', text: 'Note: Spend passed the estimate.' })).toBeDefined()
  expect(await p.find({ type: 'Text', text: 'Needs you: nothing right now.' })).toBeDefined()
})

test('a run waiting on the person says so in the bar and the pane', async ($, on) => {
  world(on, {
    reading: {
      state: { key: 'waiting', label: 'Waiting for you', role: 'warning' },
      attention: [{ kind: 'waiting', severity: 2, text: 'Waiting for your answer: ship it?' }],
      progress: { working: [] },
    },
  })
  await start($, on)
  const ui = await band($, 'terminal')
  expect(await ui.find({ type: 'Text', text: /· needs you/ })).toBeDefined()
  const p = await pane($, 'terminal')
  expect(await p.find({ type: 'Text', text: 'Needs you: Waiting for your answer: ship it?' })).toBeDefined()
})

test("another session's open run on this tree shows too", async ($, on) => {
  world(on, { session: 'someone-else', codeRoot: 'C:\\proj\\' })
  await start($, on)
  const ui = await band($, 'terminal')
  expect(await ui.find({ type: 'Text', text: /stage 8 of 10/ })).toBeDefined()
})

test("another session's run on another tree does not", async ($, on) => {
  world(on, { session: 'someone-else', codeRoot: 'D:/other' })
  await start($, on)
  const ui = await band($, 'terminal')
  expect(await ui.find({ type: 'Text', text: 'Council' })).toBeUndefined()
})

test("a session line in the run's notes is not its session (header only)", async ($, on) => {
  world(on, { omit: 'session', codeRoot: 'D:/other', notes: '## Notes' + CRLF + 'session: sess-1' + CRLF })
  await start($, on)
  const ui = await band($, 'terminal')
  expect(await ui.find({ type: 'Text', text: 'Council' })).toBeUndefined()
})

test('no open run: no bar, and the pane says so', async ($, on) => {
  world(on, { status: 'complete' })
  await start($, on)
  for (const surface of SURFACES) {
    const ui = await band($, surface)
    expect(await ui.find({ type: 'Text', text: 'Council' })).toBeUndefined()
    const p = await pane($, surface)
    expect(await p.find({ type: 'Text', text: /No open council run/ })).toBeDefined()
  }
})

test('the pane opens by itself once per run, not on every refresh', async ($, on) => {
  const opens: unknown[] = []
  world(on, { opens })
  const clock = await start($, on)
  await clock.advance(30000)
  expect(opens.length).toBe(1)
})

test('no open run never opens the pane by itself', async ($, on) => {
  const opens: unknown[] = []
  world(on, { status: 'complete', opens })
  const clock = await start($, on)
  await clock.advance(30000)
  expect(opens.length).toBe(0)
})

test("the bar's Pane button opens the pane, and its close button hides the bar for that run", async ($, on) => {
  const opens: unknown[] = []
  world(on, { opens })
  await start($, on)
  const ui = await band($, 'terminal')
  await ui.press({ key: 'council-bar-pane' })
  expect(opens.length).toBe(2)
  await ui.press({ key: 'council-bar-dismiss' })
  expect(await ui.find({ type: 'Text', text: 'Council' })).toBeUndefined()
})
