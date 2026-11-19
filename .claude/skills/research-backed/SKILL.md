---
name: research-backed
description: Grove's evidence rule. Use whenever designing, building or changing a user-facing feature, writing coach prompts, in-app copy or marketing text, or making any claim about health, habits, learning or fitness. Covers finding and grading studies, adding them to docs/research/EVIDENCE.md, citing evidence IDs, and what claims are allowed.
---

# Research-backed

Grove's promise: everything we build is backed by research, and we can show it. This skill is how we keep that promise honestly.

## The rule

Every user-facing mechanic (a feature behavior, a default, a target, a coach suggestion) must either:
1. cite one or more evidence IDs from `docs/research/EVIDENCE.md`, or
2. be labeled **product choice** in its feature spec, with no research claimed.

Option 2 is fine. Pretending option 1 is not.

## Steps when building or changing a feature

1. **Read** `docs/research/EVIDENCE.md` and the feature's spec in `docs/features/`.
2. **For each mechanic**, find the evidence ID that supports it. If none exists:
   - Look for a real source: prefer meta-analyses, systematic reviews and official guidelines (WHO, ACSM, AASM),
     then randomized trials. Use web search and read the abstract or the paper itself.
   - **Never invent or guess a citation, number or DOI.** If a detail can't be verified, omit it.
   - Add an entry (format below) or mark the mechanic "product choice."
3. **Put the IDs** in the spec's "Mechanics → evidence" table and in a short code comment next to the logic
   (for example `# HAB-1: one missed day is normal; two in a row triggers a restart plan`).
4. **Show it in the app.** Each tracker has a "Why this works" panel listing its evidence IDs with a one-line,
   plain-language finding and the citation.
5. **Word findings carefully:** match the study's population and strength. "In older adults, one trial found..."
   is correct; "exercise grows your brain" is not.

## Evidence entry format

```
### ABC-n · One-line plain-language finding · **A|B|C**
Full citation (authors, year, title, journal, volume(issue), pages).
- **Finding:** what the study actually found, with numbers only if verified.
- **We use it for:** which Grove mechanic relies on it.
```
Prefixes: HAB habits, MON monitoring, REM reminders, BCT techniques, MOT motivation, GAM gamification,
LRN learning, FIT fitness, WT weight, COG cognition, RUN running, SLP sleep, MND mindfulness, SOC social. Add new prefixes as needed.

## Grades
- **A:** meta-analysis, systematic review, official guideline or consensus statement
- **B:** randomized trial or strong single study
- **C:** practitioner framework or popular program. Design input only

## Claims in marketing and in-app copy
- Only grade **A** or **B** evidence may support a public claim. Grade B is worded as "a study found."
- Every claim links to its evidence ID (the public Research page shows the full citation).
- No medical claims: Grove does not treat, cure, diagnose or prevent any condition.
- No promises of outcomes ("lose 10 lb", "double your memory"). Describe what the research found, for whom.
- Effect sizes and percentages must be copied from the source, never rounded up.

## Coach (AI) rules
- The coach's system prompt includes the evidence library summaries; it cites IDs for factual claims.
- If asked about something outside the library, the coach says what general guidance exists and that it's not
  personalized medical advice, and doesn't fabricate studies.

## Checklist before merging
- [ ] Every mechanic in the spec has an evidence ID or "product choice"
- [ ] New evidence entries are real, graded, and fully cited
- [ ] Copy matches the strength and population of the evidence
- [ ] "Why this works" panel lists the IDs
