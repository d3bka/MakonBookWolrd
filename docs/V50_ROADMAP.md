# MakonBook V50 — Student Experience Roadmap

## Product rule
V50 is shipped incrementally. Existing stable SAT test runner, classroom, teacher, manager, admin, HolliHop, booking, and import workflows must not be redesigned as collateral changes.

## V50.1 — Student Dashboard Redesign
- Replace the current student landing experience with a real command center.
- Introduce a student-only navigation/sidebar shell without changing staff navigation.
- Prioritize: Continue Learning, Today, Progress, Classrooms, and future game surfaces.
- Reserve intentional UI slots for World, XP/level, quests, Mako, and achievements before those systems become live.
- Preserve current SAT goal, classroom membership/join-code, attendance, and access-control behavior.
- Mobile navigation must be explicitly designed, not a squeezed desktop sidebar.

## V50.2 — Gamification Core
- XP and levels
- Streaks
- Achievements
- Daily and weekly quests
- Academic scores remain separate from game progression.

## V50.3 — MakonBook World MVP
- 1v1
- SAT Math / Reading & Writing
- Quick Match / Ranked
- Separate skill ratings plus overall rating
- Leaderboards
- Curated/verified question pool only
- Server-authoritative scoring and anti-cheat basics

## V50.4 — Multiplayer
- 3–4 player matches
- 2v2
- Survival
- Classroom Battles

## V50.5 — Mako
- MakonBook-specific interactive teacher/mascot
- Context-aware recommendations based on student activity and weak areas
- States/animations tied to meaningful product events

## V50.6 — MakonRoom
- Cosmetic progression
- Trophies and achievement objects
- Room customization earned through learning/game progress

## V50.7 — Friends + World Events
- Friends and direct challenges
- Global/cooperative events
- Seasonal competition

## Guardrails
1. Stability before novelty.
2. No game feature may corrupt SAT/AP academic scoring.
3. New schema changes require migrations and tests.
4. Avoid hidden coupling to staff roles or HolliHop-managed classrooms.
5. World questions must come from a quality-controlled pool, not raw random DB selection.
6. Mobile and dark mode are first-class acceptance criteria.

## V50.1 locked navigation (2026-09-02)
Primary student sidebar order:
1. Home
2. Learn
3. Practice
4. Tests
5. MakonBook World
6. Classrooms
7. Vocabulary
8. AP Classes
9. Progress

Secondary navigation stays visually separated at the bottom:
- Bookings
- Messages
- Settings

Desktop: persistent collapsible sidebar. Mobile: off-canvas navigation opened from a compact app header.

### V50.1 visual/product direction
- Dense modern app workspace rather than large marketing-style hero cards.
- Continue Learning and Today outrank SAT university/goal information.
- SAT goal remains available, but as a compact contextual widget.
- SAT and AP share one student home.
- World and Mako receive honest preview surfaces only; no fabricated XP, rating, matchmaking, or AI claims before their backend stages ship.
- Dashboard customization may hide optional widgets locally; core Continue Learning stays fixed.
- Inspiration may come from competitive learning products, but MakonBook keeps its own navigation, typography, accent system, and information hierarchy.

### V50.1 implementation checkpoints
- Part 1: student-only Home workspace and collapsible/mobile sidebar.
- Part 2: denser Home, white sidebar brand mark, Student Classroom and Progress shell adoption.
- Part 3: shared role-aware workspace context; student Practice Tests, Vocabulary flows, and AP event library/details use the V50 shell while staff-side layouts remain unchanged. Timed SAT/AP runners stay distraction-free outside the shell by design.

### V50.1.4 — Workspace polish + Vocabulary Decks
- Fixed-width SAT test cards so sparse libraries do not stretch cards across the screen.
- Shared content gutters for SAT Practice, Vocabulary, and AP Classes.
- Richer AP Classes command-center presentation while keeping the timed runner distraction-free.
- Personal Vocabulary Decks: create a private deck, add/remove words, study it with tracked recall, or clone an official VocabularyUnit from the MakonBook library.
- Community publishing is intentionally deferred until moderation/reporting rules exist.

## V50.2.1 — Gamification foundation
- Server-backed XP ledger with idempotent source keys; academic SAT/AP scores remain untouched.
- Deterministic levels: cumulative thresholds 100 / 300 / 600 / 1000 XP for Levels 2–5.
- Student streak profile with current/best streak and one-time bootstrap from saved vocabulary activity.
- Daily quests: review 10 vocabulary cards; master 3 words.
- Weekly quests: review 50 vocabulary cards; master 15 words.
- Quest progress counts unique vocabulary items per period so retries/repeated clicks cannot farm completion.
- Initial achievements: First Step, Word Builder, Three-Day Spark, Week Warrior, Level Five.
- Existing V50 vocabulary progress is converted once into starting XP (5 XP learning, 15 XP mastered) so current students do not restart at zero.
- Home dashboard and student sidebar expose the live level/XP/streak/quest state.
