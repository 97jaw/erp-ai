# SESSION KICKOFF PROMPT

> **Purpose:** Paste the content below as your FIRST message in every new Cursor session. It forces Cursor to read the right files, understand context, and confirm before coding.

> **Usage:** Copy everything between the START and END markers.

---

## 📋 HOW TO USE

1. Open a fresh Cursor chat
2. Copy everything between `=== START ===` and `=== END ===` below
3. Paste it as your first message
4. Wait for Cursor's structured response
5. Verify Cursor understood correctly
6. Then tell Cursor which step to start

---

## =========================
## === START — PASTE THIS ===
## =========================

```
Session kickoff. Before writing any code, complete this checklist:

STEP 1: READ THESE FILES IN THIS EXACT ORDER

1. `.cursorrules` — Permanent rules for this project
2. `CURRENT_PHASE.md` — What we are actively working on right now
3. The active plan file mentioned in `CURRENT_PHASE.md` — but ONLY the section for the current phase
4. `PROJECT_CONTEXT.md` — Architecture and patterns (skim, reference as needed)

Do not read other plan files unless I explicitly ask.

STEP 2: TELL ME (in this exact structure)

After reading, respond with:

### What I Understood

**Active Plan:** [plan file name]
**Current Phase:** [phase name and number]
**Current Step:** [step number and name]
**What this step builds:** [1-2 sentences]
**Why it matters:** [1 sentence]

### What I Plan To Build

[Bullet list of specific things to create/modify, with file paths]

### Acceptance Criteria

[List from CURRENT_PHASE.md that this step must satisfy]

### Risks / Questions

[Anything you are unsure about — ask before coding]

### Tests I Will Write

[Specific test cases you plan to cover]

STEP 3: WAIT FOR APPROVAL

Do not write any code until I respond with one of:
- "Go ahead" — proceed as planned
- "Adjust X" — modify based on my feedback
- "Stop, let's discuss" — pause for conversation

CRITICAL RULES (repeat back to me to confirm):
1. Never fabricate error messages
2. Quality bar: senior management consultant + CFO's chief of staff
3. Test with real Elrace data, not mock
4. Update CURRENT_PHASE.md as you progress
5. Each step must be testable and verified before moving on
6. Never deviate from the plan without asking first
7. No motion animations except Visualize Siri border + smooth chat scroll
8. No cream colors in light theme — use sky blue

Confirm you have read everything and respond with the structured output above.
```

## =======================
## === END — PASTE THIS ===
## =======================

---

## 🔁 ALTERNATIVE KICKOFFS

### Quick Continue (when you are mid-step)

If you are just continuing where you left off in the same day:

```
Quick continue session.

Read CURRENT_PHASE.md only. 

Tell me:
- What step we are on
- What was the last thing completed
- What is the next atomic action

Then wait for my go-ahead.
```

### Bug Fix Session

When you need Cursor to fix a specific bug instead of building forward:

```
Bug fix session — not building new features.

Read:
1. .cursorrules
2. The specific file that has the bug

Bug description: [paste here]

Steps to reproduce: [paste here]

Expected vs actual behavior: [paste here]

Tell me:
- Your diagnosis
- Proposed fix
- Test you will add to prevent regression

Wait for my approval before changing code.
```

### Architecture Discussion (no code)

When you want to think through a design before building:

```
Architecture discussion mode — no code today.

Topic: [what you want to discuss]

Read:
1. .cursorrules
2. Relevant plan section: [file name and section]

Help me think through:
- [question 1]
- [question 2]
- [question 3]

Respond with analysis, options, recommendations.
Do not write code.
```

### Review Mode

When you want Cursor to review what was already built:

```
Review mode — no new code today.

I want you to review [file path or feature].

Check for:
- Quality bar: senior consultant level?
- Honest failure handling?
- Multi-tool orchestration?
- Test coverage?
- Code clarity?
- Performance?
- Security?

Provide a structured review with:
- What is good
- What needs improvement
- Priority of fixes
- Specific code changes recommended

Do not change code yet.
```

---

## 📝 END-OF-SESSION RITUAL

At the end of every Cursor session, paste this:

```
End of session ritual:

1. Update CURRENT_PHASE.md:
   - Mark completed steps as done
   - Update "Files Touched" section
   - Update "Tests Written" section
   - Add to "Session Log" what was done today
   - Note any blockers or deviations
   - Update time tracking
   - Add any "parking lot" items

2. Commit all work with this message format:
   "Phase X.Y: [brief description of what was done]"
   
   Example:
   "Phase 1.2: Build UserContext with role-aware behavior"

3. Push to repo

4. Tell me:
   - What was completed today
   - What is the next step
   - Any concerns going forward
   - What I should review before next session
```

---

## 🎯 GOLDEN RULES FOR EVERY SESSION

These should be in your head every time:

1. **Read before building** — never skip the checklist
2. **One step at a time** — atomic, testable, verifiable
3. **Verify before claiming complete** — run tests, show output
4. **Ask when unsure** — better 5 minutes asking than 5 hours rebuilding
5. **Update the tracker** — CURRENT_PHASE.md is the single source of truth
6. **Commit often** — small clear commits beat one massive commit
7. **Quality bar non-negotiable** — every line meets the standard or it does not ship

---

## 📊 SESSION HEALTH CHECK

If you notice any of these signs, STOP and reset:

- Cursor is writing code without first showing the plan
- Cursor is skipping tests
- Cursor is building features not in the current phase
- Cursor is making architectural decisions without asking
- Cursor's responses are getting longer and less specific
- You are accepting code without checking it

When you see these, use the **Quick Continue** kickoff to reset:

```
Stop. Reset session.

Re-read .cursorrules and CURRENT_PHASE.md.

Tell me where we are, what was last completed, and what is next.

Do not write code until I confirm.
```

---

## 💡 WHY THIS WORKS

This system fights five specific failure modes:

1. **Memory loss between sessions** → `.cursorrules` is permanent context
2. **Drift mid-session** → `CURRENT_PHASE.md` is the GPS
3. **Skipping the "boring" parts** → Acceptance criteria explicit
4. **Building ahead** → Atomic steps with checkpoints
5. **Architecture drift** → Mandatory ask-before-deviate rule

Use this religiously for the first month. After that, it becomes automatic.
