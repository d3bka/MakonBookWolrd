# MakonBook V55.2 — Stage 3: HomeworkSubmission

## Roadmap status

1. Unified Tests — CLOSED
2. Attempt History — CLOSED
3. HomeworkSubmission — V55.2
4. Homework integration — next

## Contract

`ClassroomHomeworkAssignment` describes what the teacher assigned.
`ClassroomHomeworkSubmission` describes one student's personal state for that assignment.

A missing submission row is intentionally equivalent to `not_started`. Rows are created lazily when a student opens an assignment, so assigning homework to a large classroom does not create hundreds/thousands of rows up front.

### States

- `not_started` — no work started yet; normally represented by no DB row.
- `in_progress` — the student opened/started the assignment.
- `completed` — the work is finished, but it has not necessarily been handed in to the teacher yet.
- `submitted` — terminal hand-in state.

`completed` and `submitted` are deliberately separate. Stage 4 will use that distinction when a student finishes a compatible SAT attempt from `/tests/` and MakonBook asks whether to submit it as homework.

### Source

Submission records also store the origin of the work:

- `homework`
- `practice_tests`
- `vocabulary`

### Attempt linkage

The model can bind to:

- SAT `attempt_id`
- final `TestReview`
- `VocabularyQuizAttempt`

This lets Stage 4 attach a normal `/tests/` attempt to one or more compatible homework assignments without duplicating the SAT attempt.

## V55.2 behavior

- Opening any homework lazily creates/updates that student's row to `in_progress`.
- Student Homework cards show `Not started`, `In progress`, `Completed`, or `Submitted`.
- Finishing the existing teacher-assigned vocabulary quiz marks its personal submission `completed`.
- SAT result matching, required Anti-Cheat, deadline countdown, auto-submit and “Submit as homework” are intentionally deferred to Stage 4.

## Database

Migration: `sat.0053_classroomhomeworksubmission_v552`

There is no data backfill and no per-assignment fan-out migration, so migration time should be short.
