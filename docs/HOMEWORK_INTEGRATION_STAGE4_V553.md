# MakonBook V55.3 — Stage 4: Homework integration

Status: **IMPLEMENTED / PENDING QA**

This stage connects teacher assignments to the canonical `/tests/` runner without
bringing classroom-scoped SAT attempts back.

## 1. Teacher SAT homework contract

A SAT homework assignment now stores two explicit requirements:

- `required_test_mode`
  - Full Test
  - Reading & Writing
  - Math
  - Reading & Writing Module 1 / Module 2
  - Math Module 1 / Module 2
- `required_integrity_mode`
  - Off
  - Standard
  - Strict

The teacher chooses Anti-Cheat when creating SAT homework. New forms require an
explicit selection. Existing assignments migrate conservatively to `Off`, so the
migration does not silently impose protection that the teacher never selected.

Ordinary `/tests/` practice remains student-controlled. Homework requirements are
applied only when a student launches an assignment from Homework.

## 2. Matching rules

One scored SAT attempt may satisfy one or more homework assignments when all of
the following are true:

1. The assignment belongs to the student and points to the same Test.
2. The attempt started on or after the assignment was created.
3. The attempt finished by the assignment deadline, when a deadline exists.
4. The attempt covers every module required by the homework.
5. The attempt's Anti-Cheat level meets or exceeds the homework requirement:
   `Off < Standard < Strict`.
6. A Standard/Strict homework is not accepted from an integrity-terminated
   attempt.

Mode coverage is set-based. Example: a Full Test can satisfy Math-only homework;
a single Math Module 1 attempt cannot satisfy Math-only homework.

## 3. Launch from Homework

Flow:

`Homework -> /tests/<DAY>/start/?homework=<id> -> cover -> exam -> results`

- The canonical `/tests/` runner is used.
- Required mode and Anti-Cheat are locked.
- A compatible unfinished canonical attempt can be claimed by the homework.
- A conflicting unfinished attempt is not overwritten.
- If the previous attempt is already complete, a new attempt UUID is created.
- The `ClassroomHomeworkSubmission` row is linked to the immutable `attempt_id`.
- A valid finished homework-launched attempt is submitted automatically.

The classroom is an access/assignment source only; it is not reintroduced as the
execution scope of the SAT attempt.

## 4. Launch from ordinary /tests/

Ordinary practice still lets the student choose Test mode and Anti-Cheat.

When Results are produced, MakonBook checks all compatible open homework:

- matching work becomes `Completed` first;
- Results shows **Submit this attempt as homework?**;
- the student may select one or multiple matching assignments;
- only explicit confirmation moves those submissions to `Submitted`.

This preserves student intent and allows one strong attempt to satisfy multiple
compatible assignments from different classrooms.

## 5. Deadlines

Homework cards expose a live countdown in days / hours / minutes / seconds.
Frontend countdown is visual only. Backend rules are authoritative:

- expired homework cannot start a new homework-bound SAT/vocabulary attempt;
- an ordinary SAT result cannot be handed in after the deadline;
- work completed after the deadline is not accepted as submitted;
- ordinary `/tests/` practice remains available if the test itself is accessible.

## 6. To do / Completed

Student Homework is split into:

- **To do** — all assigned work except `Submitted`;
- **Completed** — submitted history.

A `Completed` but not yet `Submitted` SAT result stays in To do so the student can
finish the hand-in step. A submitted assignment disappears from To do and remains
available under Completed.

## 7. Attempt start timestamp

Stage 4 adds `attempt_started_at` to `TestStage` and snapshots it to `TestReview`.
This is needed to prove that an attempt did not predate a newly-created homework
assignment. New attempt UUIDs reset this timestamp.

## Migration

`0054_homework_integration_v553`

The migration only adds columns; it contains no historical data loop/backfill.
