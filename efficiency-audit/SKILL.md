---
name: efficiency-audit
description: Audits a skill (or every skill in a directory) to find steps that don't need the current/full model, and proposes delegating only those to a cheaper model or, where a step is really just deterministic filtering, to no model call at all. Use when a skill feels heavy (slow, expensive, context-hungry), when the user asks to "make this more efficient," "use a cheaper model for X," or "cut costs on this skill," or after writing/updating a multi-step skill. Reports findings and asks before editing anything — never pushes judgment, writing, or decision-gating steps onto a cheaper model just to save cost.
---

# Efficiency Audit

Finds which parts of a skill's workflow are cheap enough to run on a smaller model — or
cheap enough to need no model at all — without quietly degrading the parts that need real
judgment. The failure mode this guards against: delegating by step *label* ("screening",
"formatting") instead of by what the step actually asks for, which is how a scoring or
writing step ends up on a model too weak to do it well.

## Scope

Ask if not specified: audit one named skill (path or name), every skill under a given
`.claude/skills/` directory (project and/or global), or both. Read each target's full
`SKILL.md` plus any scripts it shells out to — a step that already delegates to a script
is already at the bottom of the ladder and needs no further note.

## The Efficiency Ladder

Classify each concrete sub-step, not each named step — a single step like "screen
results" often bundles a mechanical filter with a judgment call that produces text a
person reads; rate the sub-parts separately, not the step by its most eye-catching half.

Stop at the first rung that fits:

1. **No model at all.** Exact/fuzzy string match against a fixed list, a numeric
   threshold, a boolean field check, dedup, sort/filter over already-structured data.
   This is plain code — a model call, even the cheapest, is pure overhead and a source of
   inconsistency on something that has one right answer.
   → `no-model: <what> — replace with inline code/regex/script.`
2. **Cheap model is safe.** Reading unstructured text but only to classify or extract
   against an explicit, enumerated rubric the skill already spells out (a fixed keyword
   list, a named set of red flags, a literal formatting checklist). No creative
   synthesis, no prose a person reads as final output, no score that alone decides
   something real.
   → `haiku: <what> — delegate via Agent(model: "haiku"); spot-check the first few
   outputs, since a miss here is a silent quality loss, not a crash.`
3. **Keep it on the current model.** Produces text a person reads directly (notes,
   letters, summaries that set tone), a score or verdict that by itself gates a real
   decision, or requires weighing multiple ambiguous signals into a judgment call. Don't
   flag these — or if the user will likely wonder why, say in one line why it was
   considered and rejected.

Volume matters as much as mechanicalness: a step that runs once per invocation (a single
resume scored against a single JD) gains little from delegation and inherits the cheap
model's weaker judgment for no real savings. A step that runs once per item in a batch of
many (screening N search results) is where delegation actually pays off. Weigh both
before flagging rung 2 — mechanical-but-rare is often not worth the risk.

## Common Mistakes (calibration)

- **Don't rate a whole skill by its most mechanical-sounding step.** A skill can look
  like "just keyword matching" and still end with a score that gates whether someone
  applies to a job, ships a feature, or sends something — that score is rung 3 even if
  the extraction feeding it is rung 2.
- **Don't route pure boolean/string/number filtering through any model, even the
  cheapest.** If the answer is fully determined by fields already in hand, it's rung 1,
  not rung 2 — no LLM call belongs there at all.
- **Don't delegate a step just because the *read* is simple if the *output* is
  permanent, human-facing record text** (a tracker note, a cover-letter hook, a summary
  that shapes a later writing step). The writing quality is what matters, not the
  reading effort.
- **A one-shot step and a per-item batch step that look equally mechanical are not
  equally good delegation candidates** — see Volume above.

## Output

One-shot report, ranked, most-impactful first. No edits without confirmation.

```
<rung> <file>: <sub-step> — <action>
```

End with a one-line tally: `N sub-steps: X no-model, Y haiku, Z stay on current model.`
If everything already belongs where it is, say so and stop — don't invent findings to
have something to report.

On approval, apply only the confirmed changes: for `no-model` findings, note in the skill
that the step is plain filtering (or actually inline the logic if asked); for `haiku`
findings, add or extend a `## Model` section in the skill's `SKILL.md` naming the exact
sub-step and the model, following whatever house style the skill's other sections
already use. Never touch the substance of a rung-3 step.

## Rules

- Never recommend delegating a step whose output a person reads as-is, or a score/verdict
  that alone decides a real outcome — no exception for "it's cheaper."
- If genuinely unsure whether a step is rung 2 or rung 3, default to rung 3. Quality
  loss is harder to notice and undo than a slightly higher model bill.
- This audits model routing only. Don't fold in unrelated cleanup (dead files, naming,
  duplicate skills) — that's `skill-audit`'s job; if both are wanted, mention it can be
  run alongside.

## How to invoke

`/efficiency-audit <skill-name>` — audit one skill.
`/efficiency-audit --global` / `--project` / `--all` — audit a whole skills directory.
