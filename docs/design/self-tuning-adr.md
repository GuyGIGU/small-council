# ADR: conservative, inspectable self-tuning

## Problem

The roadmap's last phase asks the council to learn from its outcomes:
- which seats to convene;
- how large a council to run;
- how deep to verify and how much context to give;
- what to budget.

It also says: only after metrics are trustworthy, and conservatively. Today:
- no project has five completed runs with a cost;
- no benchmark has run;
- no paired comparison of any behaviour exists.

A self-tuner built now would act on noise, or on nothing.

## Constraints

- **The user decides every change.** Tuning may propose, never decide.
- **Every change is inspectable and reversible.** It must say what it changed, from what evidence,
  on whose words, and how to undo it.
- **Behaviour waits for proof.** A change that alters what the council does (run size, packs,
  verification) needs outcome evidence — a benchmark — not just a cost record.
- **No new state beyond one log.** No daemon, no model call, Python optional.

## Options

1. **Automatic adaptation** (weights updated after each run). Rejected: it acts on small samples
   and is hard to inspect or undo.
2. **A policy file of learned values the Chair must follow.** Rejected for now: it is a second
   configuration nobody reads, and none of its values can be learned yet.
3. **Proposals by kind.** Each knob gets a stated evidence bar and one write path — for the only
   knob whose evidence exists and whose effect is an estimate, not behaviour.

## Decision

Option 3, as `council tune` (`scripts/tune.py`). It sorts knobs into three kinds:
- **budget** (the only knob it changes): the estimate per worker that `council route recommend`
  budgets with.
  - When it is proposed: once five completed runs measure tokens per worker (`council history`) and
    the median is more than a quarter away from the current estimate.
  - How it is applied: `council tune apply budget --user-said "…"` writes one line,
    `- estimate per worker: <N>k`, under `## Run preferences`.
  - What gets logged: the evidence and the user's redacted words, in `.council/tuning.md`.
  - How it is undone: `council tune revert budget` restores the previous line byte for byte. It
    refuses if the file was edited by hand since.
  - What it affects: the route reads the line for its worker and verifier estimates and for the
    ceilings that shrink a run to fit a user's budget. Without the line, nothing changes.
- **roster:** seats whose `council ledger advice` clears its bar. These are listed only; a roster
  changes only through a council-init refresh, with the numbers shown.
- **held:** context packs, run size and verification depth. These are never proposed without a
  benchmark showing the change helps (Phase 10's harness exists; its pilot awaits a budget).

## Tradeoffs

- One knob is little. It is the one the record can support today.
- The budget estimate can shrink a run to fit a user's ceiling. That is still a size change, but
  one the user asked for through their ceiling, and the estimate itself is only calibrated on
  their words.
- The quarter threshold and the five-run bar are judgements.

## Alternatives rejected

- Learned routing weights.
- Automatic seat drops.
- Model-capability routing: there is no model routing to tune.
- Tuning context depth from byte counts alone: bytes are not outcomes.

## Revisit when

- The benchmark has enough pairs to say that a behaviour change helps (then a held knob can gain an
  evidence bar and a write path of its own).
- Projects reach enough judged runs for seat advice to clear its bar routinely.
