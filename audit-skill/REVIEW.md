# Skill Review: Audit AI-generated code

**Date:** 2026-06-02
**Skill tested:** `audit-skill/SKILL.md` + `audit-skill/checklist.md`
**Auditor:** kat-coder-pro-v2

## What worked well

1. **The 24-entry taxonomy is comprehensive and well-calibrated.** Every entry has clear detection cues and false-positive guidance. The checklist caught real patterns (broad `except Exception` in `/health`) while correctly triaging legitimate variants (corpus loading degradation, bootstrap-time print statements).

2. **The false-positive guidance is essential.** Without it, the audit would have over-reported defects. For example, `except Exception` in the corpus loaders is a deliberate design choice (graceful degradation), and the checklist's guidance correctly classifies this as a legitimate-variant.

3. **The output format requirement (memo, not fixes) keeps the audit focused.** The artifact is the memo itself — findings, triage, fix order, summary. This separates analysis from implementation cleanly.

4. **The "cite the cue, not the prose" rule is excellent.** It forces precision: you can't just say "this looks like swallowed-exceptions" — you must name which detection cue fired (e.g., "`except Exception:` with a justifying comment").

5. **The "iterate through every entry" requirement prevents cherry-picking.** Even entries that seem irrelevant (tarfile, subprocess, SQL) must be checked and recorded as "no candidates." This builds trust in the audit's thoroughness.

## What could be improved

1. **No guidance for multi-file patterns.** Entries like `convention-drift` and `inconsistent-error-handling` require comparing conventions across files. The skill describes what to look for but doesn't provide a systematic method for cross-file analysis. I ended up grepping for patterns across all files, which worked but felt ad-hoc.

2. **The "legitimate-variant" bucket is ambiguous with "false-positive-shape."** Both represent "not a real defect," but the distinction (defensible reason vs. checklist explicitly exempts this case) is subtle. In practice, I found myself debating whether something was a false-positive-shape or a legitimate-variant. More examples in the checklist would help.

3. **No handling for "fixed since last audit" patterns.** The May-31 audit found 8 correctness bugs that were all fixed. This audit found the codebase clean on those dimensions, but the memo format doesn't have a natural place to note "this was a real defect in the previous audit and is now resolved." I added it as narrative context in the summary.

4. **The skill assumes the auditor has read access to the full codebase.** For larger projects, this would be impractical. A sampling strategy or scoped-audit mode (e.g., "audit only network-facing code") would make the skill more scalable.

5. **The compound findings section is under-specified.** The skill says to note when two patterns interact, but doesn't provide guidance on how to identify interactions. I found one (swallowed-exceptions + hardcoded-config-values in `/health`), but it's unclear whether this is the right threshold for reporting compounds.

## Overall assessment

The skill is **high-quality and production-ready** for small-to-medium codebases. The 24-entry taxonomy covers the most common AI-generated defect patterns, the false-positive guidance prevents over-reporting, and the memo format produces a clean artifact. For the Synonymicon codebase (~600 LOC of production Python), the audit took approximately 15 minutes of focused work and produced a thorough, actionable memo.

**Rating: 8/10** — excellent foundation, needs refinement for cross-file analysis and scalability.
