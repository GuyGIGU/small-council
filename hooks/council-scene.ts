// The council hall: each seat of the run as a small pixel-art critter at a desk, under a lamp that
// lights while they work, with a name tag and a speech bubble; above them the ten stages as a bar.
// The look follows agent-avatars by vanyastaff (MIT): pixel maps of letters turned into runs of
// <rect>, moved by SVG's own animation (SMIL), so the picture lives without any code running.
// Every critter is drawn from the seat's name, so a seat looks the same in every run, and wears the
// gear of its role. The same sprites draw in the terminal as half-block cells (rasterCells).
import type { CouncilReading, CouncilSeat } from '../types'

export const SEAT_WORD: Record<string, string> = {
  done: 'done',
  running: 'working',
  queued: 'queued',
  failed: 'failed',
  blocked: 'blocked',
}

export const fmtTokens = (n: number): string =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n)

export const esc = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export const cut = (s: string, n: number): string => (s.length > n ? s.slice(0, n - 1) + '…' : s)

export const MOST_SEATS = 12

// --- who a seat is ------------------------------------------------------------------------------

export const hash = (s: string): number => {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export type Role = 'builder' | 'verifier' | 'security' | 'architect' | 'performance' | 'tests' | 'data' | 'scholar'

export const roleOf = (s: CouncilSeat): Role => {
  const what = `${s.slug} ${s.name}`.toLowerCase()
  if (/build|implement|fix/.test(what)) return 'builder'
  if (/verif|check|review|audit/.test(what)) return 'verifier'
  if (/secur|guard|safety|threat/.test(what)) return 'security'
  if (/archit|design|struct/.test(what)) return 'architect'
  if (/perf|speed|latency|carmack/.test(what)) return 'performance'
  if (/test|beck|qa\b|quality/.test(what)) return 'tests'
  if (/data|sql|schema|migrat/.test(what)) return 'data'
  return 'scholar'
}

const ROLE_VERB: Record<Role, string> = {
  builder: 'building',
  verifier: 'checking',
  security: 'guarding',
  architect: 'drafting',
  performance: 'timing',
  tests: 'testing',
  data: 'querying',
  scholar: 'reading',
}

// A short line for the squad list, picked by the seat's name so it holds still between redraws.
const QUIPS: Record<string, string[]> = {
  builder: ['measuring twice', 'hammering it out', 'one task at a time', 'sawdust everywhere'],
  verifier: ['squinting at the diff', 'trusting nothing', 'reading it twice', 'following the evidence'],
  security: ['checking the locks', 'thinking like a burglar', 'eyeing the inputs', 'guarding the gate'],
  architect: ['drawing the big picture', 'moving the walls', 'tracing the seams', 'sketching the shape'],
  performance: ['counting milliseconds', 'chasing the slow path', 'stopwatch in hand', 'shaving cycles'],
  tests: ['writing a failing test first', 'poking the edges', 'asking what could break', 'red, then green'],
  data: ['reading the schema', 'following the rows', 'checking the migration', 'counting the nulls'],
  scholar: ['taking notes', 'reading the code', 'thinking it over', 'turning pages'],
  done: ['done, and pleased', 'handed it in', 'feet up', 'job done'],
  queued: ['waiting for a turn', 'napping until called', 'next in line', 'resting the eyes'],
  failed: ['ran into trouble', 'needs a hand', 'that did not go well', 'stuck'],
}

export const quip = (s: CouncilSeat): string => {
  const key = s.state === 'running' ? roleOf(s) : s.state === 'blocked' ? 'failed' : s.state
  const list = QUIPS[key] ?? QUIPS.scholar!
  return list[hash(s.name + key) % list.length]!
}

const COAT = ['#ff8a1f', '#37c871', '#b45cff', '#2fa8ff', '#ffd23f', '#ff5c7a', '#3fc1c9', '#e6e6e6']

export const coatOf = (s: CouncilSeat): string => COAT[hash(s.name) % COAT.length]!

const shade = (hex: string, k: number): string => {
  const n = parseInt(hex.slice(1), 16)
  const ch = (v: number) => Math.max(0, Math.min(255, Math.round(v * k)))
  return '#' + ((1 << 24) | (ch((n >> 16) & 255) << 16) | (ch((n >> 8) & 255) << 8) | ch(n & 255)).toString(16).slice(1)
}

// --- the critter: 14 columns; rows -2 and -1 above the head for hats and antennas -------------------

const TOP = 2
const COLS = 14
const ROWS = TOP + 10

// A species: its body (7 rows) and the row its two-pixel-tall eyes start on. The robot, cat and
// dragon are agent-avatars' shapes; the owl, ghost and frog are ours in the same grid.
type Species = { body: string[]; eyeRow: number }
const SPECIES: Record<string, Species> = {
  robot: {
    body: ['..LLLLLLLLLL..', '..XXXXXXXXXX..', '..XXXXXXXXXX..', 'XXXXXXXXXXXXXX', 'XXXXXXXXXXXXXX', '..XXXXXXXXXX..', '..DDDDDDDDDD..'],
    eyeRow: 1,
  },
  cat: {
    body: ['..XL......LX..', '..XXX....XXX..', '..XXXXXXXXXX..', '..XXXXXXXXXX.X', '..XXXXPPXXXX.X', '..DDDDDDDDDDXX', '..DDDDDDDDDD..'],
    eyeRow: 2,
  },
  dragon: {
    body: ['.LX........XL.', '..XXXXXXXXXX..', '..XXXXXXXXXX..', '..XXXLLLLXXX..', 'DDXXXLDDLXXXDD', 'DDXXXXXXXXXXDD', '..DDDDDDDDDD..'],
    eyeRow: 1,
  },
  owl: {
    body: ['..XX......XX..', '..XXXXXXXXXX..', '..XLLLXXLLLX..', '..XLLLXXLLLX..', '..XXXXOOXXXX..', '..DXXXXXXXXD..', '..DDDDDDDDDD..'],
    eyeRow: 2,
  },
  ghost: {
    body: ['....XXXXXX....', '...XXXXXXXX...', '..XXXXXXXXXX..', '..XXXXXXXXXX..', '..XXXXPPXXXX..', '..XXXXXXXXXX..', '..X.XX.XX.XX..'],
    eyeRow: 2,
  },
  frog: {
    body: ['...XXX..XXX...', '..XXXXXXXXXX..', '..XXXXXXXXXX..', '.XXXXXXXXXXXX.', '.XXXDDDDDDXXX.', '..XXXXXXXXXX..', '..DDDDDDDDDD..'],
    eyeRow: 1,
  },
}
const SPECIES_NAMES = Object.keys(SPECIES)
const LEGS = ['..DD.DD.DD.DD.', '..DD.DD.DD.DD.', '..DD.DD.DD.DD.']

export const eyeRowOf = (s: CouncilSeat): number => SPECIES[speciesOf(s)]!.eyeRow

export const speciesOf = (s: CouncilSeat): string => SPECIES_NAMES[(hash(s.name) >>> 5) % SPECIES_NAMES.length]!

// Gear drawn over the critter: on its head (rows counted from the top of the body, row 0; -1 and -2
// are above it), on its face (rows counted from its eye row) and in its right hand.
type Gear = { head?: [number, string][]; face?: [number, string][]; hand?: [number, string][] }
const GEAR: Record<Role, Gear> = {
  builder: {
    head: [[-2, '....YYYYYY....'], [-1, '...YYYYYYYY...'], [0, '..yYYYYYYYYy..']],
    hand: [[3, '...........ggg'], [4, '............w.'], [5, '............w.']],
  },
  verifier: {
    face: [[0, '...F.FFFF.F...']],
    hand: [[2, '...........GG.'], [3, '..........GllG'], [4, '..........GllG'], [5, '...........GGw']],
  },
  security: {
    head: [[-2, '....KKKKKK....'], [-1, '...KKKKKKKK...'], [0, '..KkKKKKKKkK..']],
    hand: [[3, '...........BBB'], [4, '...........BWB'], [5, '...........BBB']],
  },
  architect: {
    head: [[-2, '.....vvvvv.v..'], [-1, '...vvvvvvvvv..']],
    hand: [[3, '...........ccc'], [4, '...........cbc'], [5, '...........ccc']],
  },
  performance: {
    head: [[-1, '...GGGGGGGG...']],
    face: [[0, '.RR........RR.'], [1, '.RR........RR.']],
    hand: [[3, '............gg'], [4, '...........gWWg'], [5, '............gg']],
  },
  tests: {
    face: [[-1, '...GllGGllG...']],
    hand: [[3, '...........www'], [4, '...........wWw'], [5, '...........www']],
  },
  data: {
    head: [[-2, '.....NNNN.....'], [-1, '...NNNNNNNN...'], [0, '..NnNnNnNnNn..']],
    hand: [[4, '...........Q.Q'], [5, '...........QQQ']],
  },
  scholar: {
    hand: [[3, '...........rrr'], [4, '...........rWr'], [5, '...........rrr']],
  },
}

type Mood = 'work' | 'happy' | 'sad' | 'sleep'

export const moodOf = (s: CouncilSeat): Mood =>
  s.state === 'running' ? 'work' : s.state === 'done' ? 'happy' : s.state === 'failed' || s.state === 'blocked' ? 'sad' : 'sleep'

// The eyes for each mood, as (column, row from the eye row): open and two pixels tall at work,
// ^ ^ when done, x x when stuck, a closed line while asleep.
const EYES: Record<Mood, [number, number][]> = {
  work: [[4, 0], [4, 1], [9, 0], [9, 1]],
  happy: [[3, 1], [4, 0], [5, 1], [8, 1], [9, 0], [10, 1]],
  sad: [[3, 0], [5, 0], [4, 1], [3, 2], [5, 2], [8, 0], [10, 0], [9, 1], [8, 2], [10, 2]],
  sleep: [[3, 1], [4, 1], [9, 1], [10, 1]],
}

// The robot's antenna lamp, by mood, as in agent-avatars: green at work, pink when happy, red when
// stuck, amber at rest.
const LAMP: Record<Mood, string> = { work: '#7dffa0', happy: '#ff8fd0', sad: '#ff5a5a', sleep: '#ffb43a' }

// The critter as a grid of colour letters, rows -TOP..9, and the colours the letters stand for.
export const sprite = (s: CouncilSeat): { grid: string[][]; colors: Record<string, string> } => {
  const role = roleOf(s)
  const kind = speciesOf(s)
  const species = SPECIES[kind]!
  const mood = moodOf(s)
  const coat = kind === 'ghost' ? shade(coatOf(s), 1.35) : coatOf(s)
  const grid = Array.from({ length: ROWS }, () => Array.from({ length: COLS }, () => '.'))
  const lay = (row: number, line: string) => {
    const y = row + TOP
    if (y < 0 || y >= ROWS) return
    for (let x = 0; x < COLS && x < line.length; x++) if (line[x] !== '.') grid[y]![x] = line[x]!
  }
  species.body.forEach((line, row) => lay(row, line))
  if (kind !== 'ghost') LEGS.forEach((line, row) => lay(7 + row, line))
  if (kind === 'robot') {
    lay(-2, '......AA......')
    lay(-1, '.......g......')
  }
  for (const [x, dy] of EYES[mood]) grid[species.eyeRow + dy + TOP]![x] = 'E'
  const gear = GEAR[role]
  for (const [row, line] of gear.head ?? []) lay(row, line)
  for (const [row, line] of gear.face ?? []) lay(species.eyeRow + row, line)
  for (const [row, line] of gear.hand ?? []) lay(row, line)
  const colors: Record<string, string> = {
    X: coat, L: shade(coat, 1.3), D: shade(coat, 0.7), P: '#ff9ab0', O: '#ffb43a', E: '#1d1b22', A: LAMP[mood],
    G: '#22222a', F: '#d9a93a', Y: '#ffc83a', y: '#d99a1e', K: '#3b3f4f', k: '#5b6070', B: '#4f7bd9',
    W: '#ffffff', w: '#8a5a33', g: '#9aa0aa', R: '#e5484d', b: '#2c5aa0', r: '#7a3b2e', N: '#2c3e75', n: '#ffffff', l: '#9fd8ff', c: '#cfe3ff', v: '#c0392b', Q: '#ffd23f',
  }
  return { grid, colors }
}

// The grid as horizontal runs of <rect>, `u` units per pixel.
const runs = (grid: string[][], colors: Record<string, string>, u: number, rowFrom = 0, rowTo = ROWS): string => {
  let out = ''
  for (let y = rowFrom; y < rowTo; y++) {
    const row = grid[y]!
    let x = 0
    while (x < COLS) {
      const c = row[x]!
      if (c === '.' || !colors[c]) {
        x += 1
        continue
      }
      let n = 1
      while (row[x + n] === c) n += 1
      out += `<rect x="${x * u}" y="${(y - TOP) * u}" width="${n * u}" height="${u}" fill="${colors[c]}"/>`
      x += n
    }
  }
  return out
}

// The critter above its legs, for the squad list: a small standalone SVG.
export const headSvg = (s: CouncilSeat): string => {
  const { grid, colors } = sprite(s)
  const u = 2
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${COLS * u}" height="${(TOP + 7) * u}" viewBox="0 ${-TOP * u} ${COLS * u} ${(TOP + 7) * u}" shape-rendering="crispEdges">` +
    runs(grid, colors, u, 0, TOP + 7) +
    '</svg>'
  )
}

// --- the terminal: the same sprite as half-block cells ------------------------------------------

const DEFAULT_COLOR = 0x01000000
const rgb = (hex: string | undefined): number => (hex ? parseInt(hex.slice(1), 16) : DEFAULT_COLOR)

// Two pixel rows per terminal row: "▀" in the top pixel's colour over the bottom pixel's colour.
export const rasterCells = (s: CouncilSeat, rowsOfPixels = TOP + 7): { columns: number; rows: number; cells: string } => {
  const { grid, colors } = sprite(s)
  const rows = Math.ceil(rowsOfPixels / 2)
  const words: number[] = []
  for (let r = 0; r < rows; r++) {
    for (let x = 0; x < COLS; x++) {
      const top = grid[r * 2]?.[x] ?? '.'
      const bottom = grid[r * 2 + 1]?.[x] ?? '.'
      const fg = top === '.' ? undefined : colors[top]
      const bg = bottom === '.' ? undefined : colors[bottom]
      if (!fg && !bg) words.push(0x20, DEFAULT_COLOR, DEFAULT_COLOR)
      else if (!fg) words.push(0x2584, rgb(bg), DEFAULT_COLOR)
      else words.push(0x2580, rgb(fg), bg ? rgb(bg) : DEFAULT_COLOR)
    }
  }
  let bin = ''
  for (const w of words) bin += String.fromCharCode(w & 255, (w >>> 8) & 255, (w >>> 16) & 255, (w >>> 24) & 255)
  return { columns: COLS, rows, cells: btoa(bin) }
}

// --- the hall -------------------------------------------------------------------------------------

const U = 5 // scene units per sprite pixel
const W = 360
const STATION = 120
const STATION_H = 156
const HEAD = 40 // the stage bar's strip at the top
const WALL = '#2b2a33'
const FLOOR = '#3a3140'
const BEAM = '#8a6a4a'
const DESK = '#7a5232'
const MONO = "ui-monospace, 'Cascadia Mono', Menlo, Consolas, monospace"
const EASE = '0.45 0 0.55 1'

// Small glyphs, '#' cells.
const ZED = ['###', '..#', '.#.', '#..', '###']
const BANG = ['#', '#', '#', '.', '#']
const glyph = (rows: string[], x: number, y: number, size: number, fill: string): string =>
  rows
    .map((row, j) =>
      row
        .split('')
        .map((c, i) => (c === '#' ? `<rect x="${x + i * size}" y="${y + j * size}" width="${size}" height="${size}" fill="${fill}"/>` : ''))
        .join(''),
    )
    .join('')

const bubble = (cx: number, y: number, words: string, ink: string, edge: string): string => {
  const w = Math.round(words.length * 6.2 + 12)
  return (
    `<g><rect x="${cx - w / 2}" y="${y}" width="${w}" height="15" fill="#ffffff" stroke="${edge}" stroke-width="1.5"/>` +
    `<rect x="${cx - 2}" y="${y + 15}" width="4" height="3" fill="#ffffff"/>` +
    `<text x="${cx}" y="${y + 11}" text-anchor="middle" font-size="10" font-family="${MONO}" fill="${ink}">${esc(words)}</text></g>`
  )
}

const station = (s: CouncilSeat, x0: number, y0: number, i: number): string => {
  const mood = moodOf(s)
  const role = roleOf(s)
  const coat = coatOf(s)
  const { grid, colors } = sprite(s)
  const cx = x0 + STATION / 2
  // Top down: lamp (y0..15), bubble (20..38), name tag (40..54), the critter, the desk, the floor.
  const floorY = y0 + STATION_H - 12
  const deskY = floorY - 40
  const px = cx - (COLS * U) / 2
  const py = deskY - 7 * U + 3 // the whole body above the desk top, the legs behind it
  const at = (dur: number) => `begin="${-((hash(s.name) % 997) / 997) * dur}s"`
  const tip = esc(`${s.name}: ${SEAT_WORD[s.state] ?? s.state}${s.tokens ? `, ${fmtTokens(s.tokens)} tokens` : ''}`)

  // The lamp over the desk: lit and softly flickering while the seat works.
  const isLit = mood === 'work'
  const lamp =
    `<rect x="${cx - 1}" y="${y0}" width="2" height="12" fill="${BEAM}"/>` +
    `<rect x="${cx - 10}" y="${y0 + 12}" width="20" height="5" fill="${isLit ? '#ffd27a' : '#6b5a48'}"/>` +
    (isLit
      ? `<polygon points="${cx - 10},${y0 + 17} ${cx + 10},${y0 + 17} ${cx + 34},${deskY} ${cx - 34},${deskY}" fill="#ffd27a" opacity=".13">` +
        `<animate attributeName="opacity" values=".13;.09;.13;.11;.13" dur="3.2s" ${at(3.2)} repeatCount="indefinite"/></polygon>`
      : '')

  // How the body moves: a working bob, a happy hop now and then, a sad shake, a sleeper's breath.
  const motion =
    mood === 'work'
      ? `<animateTransform attributeName="transform" type="translate" values="0 0;0 ${U / 2};0 0" dur="0.9s" ${at(0.9)} calcMode="spline" keySplines="${EASE};${EASE}" repeatCount="indefinite"/>`
      : mood === 'happy'
        ? `<animateTransform attributeName="transform" type="translate" values="0 0;0 0;0 ${-2 * U};0 0;0 0" keyTimes="0;0.8;0.86;0.92;1" dur="5s" ${at(5)} calcMode="spline" keySplines="${EASE};0.2 0.7 0.4 1;0.6 0 0.8 0.4;${EASE}" repeatCount="indefinite"/>`
        : mood === 'sad'
          ? `<animateTransform attributeName="transform" type="translate" values="0 0;${-U / 2} 0;${U / 2} 0;${-U / 2} 0;0 0;0 0" keyTimes="0;0.05;0.1;0.15;0.2;1" dur="3s" ${at(3)} repeatCount="indefinite"/>`
          : `<animateTransform attributeName="transform" type="translate" values="0 0;0 ${U / 3};0 0" dur="3.6s" ${at(3.6)} calcMode="spline" keySplines="${EASE};${EASE}" repeatCount="indefinite"/>`
  // A blink for open eyes: for a moment the top half of each eye takes the colour beside it.
  const eyeY = eyeRowOf(s)
  const lid = colors[grid[eyeY + TOP]?.[3] ?? 'X'] ?? colors.X
  const blink =
    mood === 'work'
      ? `<g opacity="0"><rect x="${4 * U}" y="${eyeY * U}" width="${U}" height="${U}" fill="${lid}"/><rect x="${9 * U}" y="${eyeY * U}" width="${U}" height="${U}" fill="${lid}"/>` +
        `<animate attributeName="opacity" values="0;1;0" keyTimes="0;0.96;1" calcMode="discrete" dur="4.3s" ${at(4.3)} repeatCount="indefinite"/></g>`
      : ''
  // The place on an outer group, the movement on an inner one: an animateTransform replaces the
  // transform of the element it sits in rather than adding to it.
  const critter = `<g transform="translate(${px},${py})"><g>${motion}${runs(grid, colors, U)}${blink}</g></g>`

  // The desk in front, with the role's thing on it: papers that shuffle while someone works.
  const desk =
    `<rect x="${cx - 40}" y="${deskY}" width="80" height="6" fill="${DESK}"/>` +
    `<rect x="${cx - 36}" y="${deskY + 6}" width="72" height="22" fill="${shade(DESK, 0.78)}"/>` +
    `<rect x="${cx - 36}" y="${deskY + 6}" width="72" height="2" fill="${shade(DESK, 0.6)}"/>` +
    `<rect x="${cx - 6}" y="${deskY + 14}" width="12" height="3" fill="${shade(DESK, 1.25)}"/>` +
    `<rect x="${cx - 34}" y="${deskY + 28}" width="5" height="${floorY - deskY - 28}" fill="${shade(DESK, 0.7)}"/>` +
    `<rect x="${cx + 29}" y="${deskY + 28}" width="5" height="${floorY - deskY - 28}" fill="${shade(DESK, 0.7)}"/>` +
    `<rect x="${cx - 26}" y="${deskY - 3}" width="14" height="3" fill="#e9e1d0"/>` +
    (mood === 'work'
      ? `<rect x="${cx - 24}" y="${deskY - 5}" width="10" height="2" fill="#ffffff"><animate attributeName="opacity" values="1;0;1" dur="1.1s" ${at(1.1)} calcMode="discrete" repeatCount="indefinite"/></rect>`
      : '')

  // Above the head: the name tag, then a bubble for what the seat is doing.
  const tagY = y0 + 40
  const name = cut(s.name, 13)
  const tw = Math.round(name.length * 6.2 + 12)
  const tag =
    `<rect x="${cx - tw / 2}" y="${tagY}" width="${tw}" height="14" fill="#16151b"/>` +
    `<rect x="${cx - tw / 2}" y="${tagY}" width="${tw}" height="2" fill="${coat}"/>` +
    `<text x="${cx}" y="${tagY + 11}" text-anchor="middle" font-size="10" font-weight="700" font-family="${MONO}" fill="#ffffff">${esc(name)}</text>`
  // A bubble only for what is happening now; a finished seat gets a gold sparkle instead.
  const say = mood === 'work' ? `${ROLE_VERB[role]}…` : mood === 'sad' ? 'oops' : ''
  const talk = say ? bubble(cx, y0 + 20, say, mood === 'sad' ? '#c0392b' : '#1d1b22', mood === 'sad' ? '#e5484d' : coat) : ''
  const sparkle =
    mood === 'happy'
      ? `<g fill="#ffd23f"><rect x="${px + 13 * U}" y="${py - U}" width="2" height="8"/><rect x="${px + 13 * U - 3}" y="${py + 2}" width="8" height="2"/>` +
        `<animate attributeName="opacity" values="1;0.2;1" dur="2.4s" ${at(2.4)} repeatCount="indefinite"/></g>`
      : ''
  // A sleeper's z z, drifting up; a failed seat's red bang.
  const zzz =
    mood === 'sleep'
      ? [0, 1, 2]
          .map(
            k =>
              `<g opacity="0"><animate attributeName="opacity" values="0;0.9;0" dur="3s" begin="${k}s" repeatCount="indefinite"/>` +
              `<animateTransform attributeName="transform" type="translate" values="0 0;${6 + k * 2} -14" dur="3s" begin="${k}s" repeatCount="indefinite"/>` +
              glyph(ZED, px + 12 * U, py + U, 2, '#b8c7d0') +
              '</g>',
          )
          .join('')
      : ''
  const bang =
    mood === 'sad'
      ? `<g>${glyph(BANG, px + 13 * U, py, 3, '#e5484d')}<animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite"/></g>`
      : ''

  return `<g><title>${tip}</title>${lamp}${critter}${desk}${zzz}${bang}${sparkle}${tag}${talk}</g>`
}

export const hallHeight = (seats: number): number => HEAD + Math.max(1, Math.ceil(seats / 3)) * STATION_H

export const sceneSvg = (r: CouncilReading): string => {
  const seats = r.seats.slice(0, MOST_SEATS)
  const rows = Math.max(1, Math.ceil(seats.length / 3))
  const H = hallHeight(seats.length)

  // The stage bar: ten blocks, the passed ones gold, the current one blinking.
  const bw = 22
  const gap = 4
  const bx = W - 14 - r.stages * (bw + gap) + gap
  const stages = Array.from({ length: r.stages }, (_, i) => {
    const isDone = r.isClosed || i < r.stage - 1
    const isNow = !r.isClosed && i === r.stage - 1
    const fill = isDone ? '#ffd23f' : isNow ? '#ffffff' : '#4a4553'
    const blink = isNow ? `<animate attributeName="opacity" values="1;0.35;1" dur="1.2s" calcMode="discrete" repeatCount="indefinite"/>` : ''
    return `<rect x="${bx + i * (bw + gap)}" y="14" width="${bw}" height="8" fill="${fill}">${blink}</rect>`
  }).join('')
  const label = r.isClosed ? 'done' : r.stage ? `${r.stage}/${r.stages}` : ''
  const head =
    `<rect x="0" y="0" width="${W}" height="${HEAD}" fill="#211f27"/>` +
    `<text x="14" y="22" font-size="11" font-weight="700" font-family="${MONO}" fill="#ffffff">${esc(label)}</text>` +
    stages

  // The hall: wall, a beam per row of stations, the floor under each.
  let hall = ''
  for (let row = 0; row < rows; row++) {
    const y = HEAD + row * STATION_H
    hall +=
      `<rect x="0" y="${y}" width="${W}" height="${STATION_H}" fill="${WALL}"/>` +
      `<rect x="10" y="${y + 6}" width="${W - 20}" height="3" fill="${BEAM}"/>` +
      `<rect x="0" y="${y + STATION_H - 8}" width="${W}" height="4" fill="${FLOOR}"/>` +
      `<rect x="0" y="${y + STATION_H - 4}" width="${W}" height="4" fill="${shade(FLOOR, 0.75)}"/>`
  }
  // Dust in the air, so the room never stands quite still.
  const dust = [0, 1, 2, 3, 4]
    .map(k => {
      const x = (37 + k * 71) % W
      const y = HEAD + 20 + ((k * 53) % Math.max(40, rows * STATION_H - 50))
      return `<rect x="${x}" y="${y}" width="2" height="2" fill="#ffffff" opacity=".18"><animateTransform attributeName="transform" type="translate" values="0 0;6 -10;0 0" dur="${7 + k}s" repeatCount="indefinite"/></rect>`
    })
    .join('')

  const people = seats
    .map((s, i) => {
      const row = Math.floor(i / 3)
      const inRow = Math.min(3, seats.length - row * 3)
      const x0 = (W - inRow * STATION) / 2 + (i % 3) * STATION
      return station(s, x0, HEAD + row * STATION_H + 4, i)
    })
    .join('')
  const empty = seats.length
    ? ''
    : `<text x="${W / 2}" y="${HEAD + STATION_H / 2}" text-anchor="middle" font-size="11" font-family="${MONO}" fill="#b8b3c2">the hall is empty: no seats yet</text>`
  const more =
    r.seats.length > MOST_SEATS
      ? `<text x="${W - 12}" y="${H - 12}" text-anchor="end" font-size="10" font-family="${MONO}" fill="#b8b3c2">+${r.seats.length - MOST_SEATS} more</text>`
      : ''

  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges">` +
    `<clipPath id="hall"><rect width="${W}" height="${H}" rx="10"/></clipPath><g clip-path="url(#hall)">` +
    head +
    hall +
    dust +
    people +
    empty +
    more +
    '</g></svg>'
  )
}
