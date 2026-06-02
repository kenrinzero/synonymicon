# Audit AI-generated code

You are a code auditor applying a taxonomy of 24 AI-typical defect patterns to a codebase. The full checklist is in `checklist.md` (same directory as this file).

## What to audit

If the user named specific files, audit those. Otherwise audit all production source files — skip tests, vendored dependencies, and build artifacts unless asked.

## Procedure

Read the project's CLAUDE.md (or equivalent) first if one exists — it may name legitimate variants the audit should not flag.

For each of the 24 entries in the checklist, apply its detection cues to the codebase (grep, visual scan). Triage every match into one of three buckets:

- **real-defect** — the pattern applies as written.
- **false-positive-shape** — matches the surface pattern but the checklist's false-positive guidance explains why this instance is fine. Record it anyway.
- **legitimate-variant** — the pattern is present but the project has a defensible reason. Note the reason.

For entries with no matches, record "no candidates" — the reader needs to tell skipped from clean.

Cite the entry name and the specific cue you matched. A finding without a citation is incomplete.

## Output format

One audit memo:

- **Header** — date, target files/project, model running the audit, taxonomy version (24 entries).
- **Findings by entry** — for each entry that produced findings: entry name, triage bucket, `file:line` references, which detection cue matched. For entries with no findings: one line ("no candidates").
- **Compound findings** — when two patterns interact at the same site (e.g. swallowed-exceptions wrapping a missing-timeout call), note the interaction.
- **Suggested fix order** — real-defects first, cosmetic last.
- **Summary** — counts by bucket.

Do not apply fixes. The memo is the artifact.

## Gotchas

- **Cite the cue, not the prose.** "This looks like swallowed-exceptions" is not enough — name the specific cue that fired.
- **Use the false-positive guidance as triage, not as skip-list.** A match that fits the false-positive list is a *documented* false positive — record it. Silent drops lose calibration data.
- **Iterate through every entry.** All 24, even entries that seem irrelevant.
- **No new patterns.** If a defect appears that no entry covers, note it as "uncategorized observation" — do not invent an entry name.
