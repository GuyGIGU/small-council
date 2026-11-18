# Accessibility Reference — Carmack × Pickering

Philosophy: John Carmack. Accessibility practice: Heydon Pickering (author of *Inclusive Components* and *Inclusive Design Patterns*). This seat asks of every screen, dialog, form, HUD and prompt: can someone using a screen reader, a keyboard, switch or controller only, magnification, large text or captions, or with limited dexterity, get the job done? Pickering's books build inclusion into each component from its native foundations.

The Carmack filter here is reach and blockage. A real finding names a person, a path and a blocker — "a screen-reader user can't submit the sign-up form because the submit control is an unlabelled image" — not a linter rule restated over code nobody reaches. Being locked out of a core task is P1 in this lens; "few users need this" is never on its own a reason to drop a lockout.

## When this seat applies

Any surface a person operates — screens, forms, dialogs, media, game menus and HUDs, device displays, terminal prompts. Example surface markers:

- **Web:** `**/*.{html,jsx,tsx,vue,svelte}`, `**/*.css`; `onClick` on a `div`, `role=`, `aria-`, `tabindex`, `outline: none`, `placeholder=`.
- **Mobile:** `**/*.swift`, `res/layout/**`, `**/*.kt`, `**/*.dart`; `accessibilityLabel`, `contentDescription`, `Modifier.semantics`, `Semantics(`, `GestureDetector`.
- **Desktop:** `**/*.xaml` (`AutomationProperties.Name`), Qt `**/*.ui` and `setAccessibleName`, custom-painted widgets.
- **Games:** `**/*.tscn` (Godot `Control`, `focus_mode`), Unity `**/*.prefab` with `Selectable` and `EventSystem`, input maps (`project.godot`, `*.inputactions`).
- **CLI / TUI:** ANSI colour (`chalk`, `colorama`), spinners, interactive prompts (`inquirer`, `prompt_toolkit`), `NO_COLOR`.

Drop the seat only when no person operates the software (a library, a batch service, firmware with no display or input). Pair it with UX or UI when the surface is thin; give it its own worker when a change touches custom widgets, navigation, forms, media or game menus.

## Applying this seat to another stack

- **Web:** HTML elements first, ARIA only where HTML has none; `:focus-visible`; live regions; `prefers-reduced-motion`; zoom and reflow.
- **Mobile:** labels, traits and hints; VoiceOver and TalkBack order; Dynamic Type and font scale; targets (Apple suggests 44×44 pt, Material 48×48 dp).
- **Desktop:** the platform accessibility API (UI Automation, NSAccessibility, AT-SPI) for custom-painted controls; full keyboard use; high-contrast themes.
- **Games:** controller navigation of every menu, remappable input, configurable subtitles, colour-blind-safe cues.
- **CLI:** linear plain-text output, no colour-only status, `NO_COLOR` honoured, a flag for every prompt.
- **Backend and embedded:** backend only where it shapes what people perceive (error text shown verbatim, session timeouts); devices never signal by LED colour or a beep alone.

Ownership: UI (Saarinen) owns the visual system, UX (Friedman) interaction design, Frontend (Dodds) component code quality. This seat owns access; contrast, focus visibility and colour-only meaning belong here because they decide whether someone can use the product. When a finding is both, file it here if someone is locked out.

## Principle 1: Semantics first — native controls before custom ones

Native controls — HTML elements, SwiftUI and Compose widgets, a desktop toolkit's standard controls, an engine's focusable UI nodes — come with a role, keyboard behaviour and assistive-tech support. A custom widget must rebuild all of that and usually rebuilds only part. Start native; go custom only with the whole contract.

### What to check
- Clickable non-controls: a `div` with a click handler, a view with a tap gesture, a game-menu sprite that can't take focus.
- Canvas-drawn or custom-painted UI with nothing behind it in the accessibility tree.
- Roles that fight the element: a link used as a button, headings chosen for size, not structure.
- Missing structure: landmarks and headings on the web, screen titles and grouping elsewhere, header cells in data tables.

### What not to flag
- A custom control that already matches its native equivalent's name, role, state and keys.
- Redundant roles on native elements (`role="button"` on a `<button>`) — P3 at most.

## Principle 2: Everything works without a pointer

Every action reachable by mouse or touch must be reachable by keyboard, switch or controller, in a sensible order, with visible focus that can always move on. A pointer-only path locks out keyboard and switch users, many screen-reader users and every controller player.

### What to check
- Focus order that doesn't follow the task; positive `tabindex` or hand-built focus chains (Godot focus neighbours, Unity `Selectable` navigation) that skip or loop.
- Invisible focus: `outline: none` with no replacement, a controller menu with no highlighted item.
- Focus traps both ways: a widget you can enter but not leave; a modal that lets focus escape behind it.
- Hover-, drag- or right-click-only actions; custom buttons that ignore Enter and Space; dialogs that ignore Escape or the back button.

### What not to flag
- A pointer affordance that duplicates an existing keyboard path.
- Inherently spatial tasks (freehand drawing, aiming) — ask for alternatives where the task allows.

## Principle 3: Every control has a name, a role and a state

Assistive technology can only say what the code tells it. Every interactive element needs an accessible name, a role and its current state (checked, expanded, selected, disabled); every meaningful image needs a text alternative. WCAG's "Name, Role, Value" criterion is the same rule for the web.

### What to check
- Icon-only buttons and image links with no label (`aria-label`, `accessibilityLabel`, `contentDescription`, `AutomationProperties.Name`); meaningful images with no text alternative.
- State that lives only in styling: toggles, tabs and accordions whose state is never exposed or never updated.
- Useless names: "button1", a filename, twenty rows each labelled "Delete".
- An accessible name that doesn't contain the visible text, so voice-control users can't say what they see.

### What not to flag
- Missing labels on elements correctly hidden as decorative (`alt=""`, `importantForAccessibility="no"`).
- Wording preferences when the label is accurate and unique.

## Principle 4: Never rely on colour, sound or motion alone

A cue carried by one channel is lost to anyone who can't perceive it: colour to colour-blind and low-vision users, sound to deaf users or anyone on mute, motion to people it makes ill. Pair every cue with a second channel, keep contrast readable, and honour the reduce-motion setting.

### What to check
- Status by colour alone: red/green validation, chart series told apart only by hue, a status LED, loot rarity in a game.
- Contrast below WCAG AA: 4.5:1 for normal text; 3:1 for large text, for the visual information needed to identify a control or its state, and for focus indicators (1.4.11).
- Audio-only cues (an alert tone, an off-screen threat) with no visual or haptic equivalent; video without captions.
- Large animation that ignores `prefers-reduced-motion` or the OS setting; anything that flashes more than three times in any one second above the general or red flash threshold (WCAG 2.3.1); moving content with no pause.

### What not to flag
- Colour used as a second cue alongside text, an icon or shape.
- Contrast on genuinely inactive controls, logos and decoration, which WCAG exempts.
- A text button with no border: its text identifies it, so it needs no contrasting border.

## Principle 5: Announce what changes

Sighted users see a change; screen-reader users learn of it only if focus moves to it or it is announced. After navigation, dialogs, errors and async work, decide where focus goes and what gets said, and keep announcements rare.

### What to check
- Screen or route changes that leave focus on a vanished element, or silently at the top.
- Dialogs that don't move focus in on open or return it to the trigger on close; focus lost when the focused item is removed.
- Async results ("saved", a failed upload) with no live region (`aria-live`, `role="status"`, Android `accessibilityLiveRegion`) or announcement (`UIAccessibility.post` on iOS).
- Over-announcing: a live region firing on every keystroke or progress tick.

### What not to flag
- Changes the user caused and already perceives at the focus point (typing, a checkbox announcing its own state).
- Polite versus assertive, when either would be heard.

## Principle 6: Text scales and reflows

People with low vision raise the system text size, zoom or magnify. Text must follow the platform's size setting, and layouts must reflow without clipping, overlap or two-way scrolling.

### What to check
- Zoom disabled (`user-scalable=no`, `maximum-scale=1`); `dp` instead of `sp` for Android text; fixed sizes instead of Dynamic Type styles on iOS; desktop text that ignores system scaling.
- Fixed-height containers and single-line labels that clip at large sizes; text baked into images.
- Layouts that break at 200% text size or a 320 CSS px wide viewport.
- Game and device UIs with small text and no size option.

### What not to flag
- Text the user already sizes another way (an editor's own font setting).
- Wrapping changes at large sizes that keep everything readable and operable.

## Principle 7: Forms and errors are explicit

Every input needs a visible label tied to it in code. Every error must say what went wrong and how to fix it, be tied to its field, and be announced. A placeholder is not a label: it vanishes as you type and often fails contrast.

### What to check
- Placeholder-only labels, or labels beside the field but not connected (`<label for>`, `aria-labelledby`, Android `labelFor`).
- Errors shown only as a red border or icon, or not linked to their field (`aria-describedby`, the platform's field-error API).
- A failed submit that neither moves focus to the first error nor announces anything.
- Required fields marked only by an asterisk or colour; radio groups with no group label; personal-data fields without autofill hints (`autocomplete`, `textContentType`, `autofillHints`).

### What not to flag
- Styled or floating labels that keep a visible label and a correct programmatic one.
- When validation fires, as long as errors are perceivable and tied to fields — UX's call.

## Principle 8: Time, targets and gestures are forgiving

Some people move slowly, have tremors, use one hand, a head pointer or a switch, or need longer to read. Time limits must be adjustable or absent, targets big enough to hit, and complex gestures backed by simple ones.

### What to check
- Time limits that discard work — session expiry mid-form, quick-time events, a toast holding the only undo — with no warning or extension.
- Targets under 24×24 CSS px that also fail WCAG 2.5.8's spacing test (a 24 px circle centred on each undersized target overlaps another target or its circle) and have no equivalent control; on mobile, targets under platform guidance; a destructive action crowded beside a common one.
- Pinch, swipe, long-press, drag or shake with no tap or button alternative; actions fired on press-down with no way to cancel.
- Games: fixed bindings, required button-mashing or long holds with no toggle, missing subtitles, colour-coded mechanics with no colour-blind option.

### What not to flag
- Time limits essential to the activity (a live auction, a real-time match).
- Undersized targets meeting 2.5.8's spacing or equivalent exception, inline links, unmodified user-agent controls.
- Targets that pass 2.5.8 but are under UX's 44 px — UX's call.

## Principle 9: Automated checks catch only part

Scanners reliably catch missing labels, invalid roles and contrast failures in static markup, but not whether focus order makes sense, a label means anything, or a flow can be finished. Automation is the floor; a changed flow still needs a manual pass with real assistive tech.

### What to check
- Whether any automated check runs: axe-core or eslint-plugin-jsx-a11y on the web, Xcode's Accessibility Inspector or Android's Accessibility Scanner on mobile, Accessibility Insights on Windows.
- Suppressed checks: disabled a11y lint rules, inline ignores, baselines that accept violations.
- Tests that find elements by role and accessible name, so they fail when semantics break.
- Whether a changed flow was finished with a screen reader (VoiceOver, TalkBack, NVDA or Narrator), keyboard or controller only, and at the largest text size.

### What not to flag
- A missing tool when another check covers the same ground — report defects, not tooling.
- Scanner output not traced to an element a user can reach.

## Know your gaps

- Cognitive and learning disabilities (plain language, consistency, memory load) are touched only in passing; UX covers much of it.
- This seat reviews code; it does not certify WCAG, Section 508 or EN 301 549 conformance.
- Assistive-tech behaviour varies by screen reader, browser and OS version, and reading code can't hear it. Mark behaviour you can't confirm UNCERTAIN.
- Game-specific needs run deeper; see the Game Accessibility Guidelines and the Xbox Accessibility Guidelines.

## Quick Reference: Severity Guide

- **P1 — someone is locked out or misled:** a core task (sign in, pay, save, start the game) that can't be finished by keyboard, controller or screen reader (Principles 1–3); a focus trap; an unlabelled primary control; a form error a screen-reader user never learns of; a time limit that destroys work; content that flashes more than three times in any one second above the general or red flash threshold (WCAG 2.3.1).
- **P2 — access degrades silently or spreads:** an inaccessible custom widget reused across screens; no focus management after navigation; body text below contrast; zoom disabled; colour-only status in a secondary view; suppressed a11y lint rules.
- **P3 — clarity and polish:** redundant roles, verbose labels, chatty announcements on a minor view, a skipped heading level.

## The Overriding Filter

Name the person, the path and the blocker.
If you can't say who is stopped, on which flow in this product, by which code, it's pattern-matching — drop it.
If you can, it outranks polish: a beautiful screen nobody can operate is broken.
