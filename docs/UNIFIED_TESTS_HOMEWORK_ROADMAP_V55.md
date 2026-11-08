# MakonBook V55 — Unified Tests & Homework roadmap

This roadmap is intentionally split into four stages. Each stage must keep the
previous stage green before the next one closes.

## Stage 1 — Unified Tests ✅ CLOSED

Goal: one student SAT library and one student SAT runner.

Contract:
- `/tests/` is the only visible student SAT library.
- Accessible tests are the union of all approved classroom grants.
- The same test granted by two classrooms appears once.
- Normal test attempts are not classroom-scoped.
- Student chooses Off / Standard / Strict for ordinary `/tests/` practice.
- Classroom Anti-Cheat policy does not control ordinary practice.
- Old classroom test URLs are transition aliases only and redirect to canonical
  `/tests/...` URLs; they must not create classroom-scoped attempts.
- An unfinished legacy classroom attempt may be adopted into the canonical runner.

## Stage 2 — Attempt History ✅ CLOSED

Goal: attempt-centric state instead of the old Active/Past interpretation.

Contract:
- Available — unique tests the student can currently start.
- In Progress — unfinished attempts only.
- History — one row/card per completed attempt_id.
- History survives if current classroom test access is later removed.
- TestReview snapshots run mode and Anti-Cheat metadata so retakes cannot rewrite
  historical attempt metadata.
- Historical results use canonical `/tests/.../results/` URLs.

## Stage 3 — HomeworkSubmission ✅ CLOSED

Goal: separate a homework requirement from the work/attempt used to satisfy it.

Contract:
- one personal row per `(assignment, student)`;
- missing row = Not started;
- statuses: Not started / In progress / Completed / Submitted;
- `Completed` is intentionally distinct from `Submitted`;
- SAT attempt UUID / TestReview and vocabulary quiz attempt can be linked;
- one student's state never changes another student's state;
- Submitted is terminal.

## Stage 4 — Homework integration 🟣 IMPLEMENTED / PENDING QA

Goal: connect assignments, deadlines and SAT attempts cleanly.

Implemented contract:
- Teacher chooses required SAT mode and Anti-Cheat for SAT Homework.
- Existing pre-V55.3 homework migrates to Anti-Cheat Off rather than silently
  becoming protected.
- Homework launch uses the canonical `/tests/` runner and locks its requirements.
- Ordinary `/tests/` remains student-controlled.
- Homework-launched compatible attempts auto-submit after a valid finish.
- Ordinary compatible attempts become Completed candidates and Results asks the
  student whether to submit them as homework.
- One attempt may satisfy multiple compatible assignments.
- Match rules enforce assignment creation time, deadline, test, mode coverage,
  minimum Anti-Cheat level, and integrity termination state.
- Homework shows live deadline countdowns, with backend deadline enforcement.
- Submitted work leaves To do and remains under Completed history.
- Dashboard homework excludes already-submitted assignments.

## V55 implementation status

- Stage 1 — Unified Tests: **CLOSED**
- Stage 2 — Attempt History: **CLOSED**
- Stage 3 — HomeworkSubmission: **CLOSED**
- Stage 4 — Homework integration: **V55.3 implemented / pending tests + UI QA**
