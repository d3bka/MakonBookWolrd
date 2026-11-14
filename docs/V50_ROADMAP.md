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

## Status (2026-11-14)
- V50.1–V50.4 are live in the V64–V68 releases (student shell, gamification, World 1v1 Quick/Ranked, multiplayer FFA/2v2/Survival/Classroom).
- V50.5 Mako: first iteration shipped (below). V50.6 MakonRoom shipped in V71 (below). V50.7 Friends + World Events is next.

## V50.5.1 — Mako companion (first iteration)
- `apps/gamification/mako.py`: `mako_state()` is a pure, rule-based function over the Home context the view already builds — no extra queries, no writes, no AI/LLM, no invented scores or predictions.
- States tied to real product events, most meaningful first: level reached today → deadline within 24 h → all daily quests done → streak at risk (streak ≥ 2, no XP today) → weakest topic (≥ 3 answers, ≤ 70 % correct) → welcome (no classroom or no goal) → idle.
- Up to three deduplicated next steps: nearest homework, weakest topic practice, vocabulary review, goal setup, joining a classroom, unfinished daily quests.
- Home widget `templates/sat/_mako_widget.html` joins the existing widget customizer (`data-dashboard-widget="mako"`), so students can move or hide it. Original SVG mascot; celebrate/nudge/focus/welcome/idle expressions; tapping Mako spotlights the next step; entrance animation plays once per event (localStorage, optional).
- Styles live only in `static/assets/css/mako-v505.css`, scoped to `.mb66-dashboard` and the V66 theme tokens (light/dark), with tablet/phone layouts and `prefers-reduced-motion`. Staff layouts never load it.
- Tests: `apps/gamification/test_mako_v505.py` (every rule, step limits, no AI/prediction wording, no added queries, staff exclusion).

## V70 — Seasonal themes + Mako the panda (2026-11-14)

**Seasonal themes** (`apps/base/seasons.py`, `SeasonalTheme` singleton, `season-v70.css/js`)
- Four Uzbek-inspired themes, each in light and dark mode:
  - Winter / Qish: snow on a blue dome and minaret, a tandir with non; snowflakes and girih stars.
  - Spring / Bahor: Navro'z — sumalak in the kazan, peach blossom, tulips, ko'k; red-pink petals.
  - Summer / Yoz: ishkom grapevine, turquoise peshtoq, melons, paxta choynak; pollen by day, fireflies by night.
  - Autumn / Kuz: pomegranate branch, cotton in a ko'za, a savat of anor; tumbling chinar leaves.
- Automatic by the Tashkent calendar; Admin/Manager can pin a season at `/manager/seasonal-theme/`
  (nobody else can). Holidays (Navro'z, Yangi yil, Mustaqillik, O'qituvchilar kuni) are detected.
- Decor sits at z-index -1 inside `.mb50-workspace`, under every card. Each viewer can switch the
  particles off in Settings; `prefers-reduced-motion` turns all motion off.

**Mako the panda** (`templates/base/mascot/_panda.html`, `mascot-v70.css/js`)
- Vector rig redrawn from the six reference poses, with 13 emotions: idle, happy, greet, celebrate,
  surprised, sad, angry, skeptical, bored, sleepy, thinking, love, worried.
- Eyes follow the pointer, he blinks and talks, wears a seasonal accessory (blossom, do'ppi,
  chinar leaf, scarf).
- Corner companion on student pages: greets once per session (time of day or holiday). Pokes make
  him giggle; five quick pokes make him angry. He gets bored after 1 min and sleeps after 3 min.
  He reacts to dark/light, toasts and the connection. He can be tucked away.
- Home: the Mako card is gone (in saved widget layouts it sank to the bottom). Mako now greets from the
  header next to "Welcome back": a speech bubble with his daily line and next step; pressing him cycles the steps.

## V50.6 — MakonRoom (V71, 2026-11-15)
- `/room/` (student sidebar → MakonRoom): Mako's study room, an SVG scene with six slots: wallpaper, wall art,
  rug, furniture, light and plant. Each slot has a free starter and 2–3 Uzbek-flavoured unlocks: atlas ikat, girih
  tiles, suzani, Registan print, Bukhara gilam, tapchan with choynak, chiroq lantern, tulips, pomegranate tree…
- Unlocks come only from existing progress (XP, level, best streak, mastered words, completed quests). Items are
  cosmetic; nothing touches SAT/AP scoring (guardrail 2).
- `apps/gamification/room.py` holds the catalog and rules; `RoomLayout` stores the student's choice. The server
  accepts only unlocked items and falls back to the starter if a saved item is invalid.
- Every achievement is a trophy on the shelf; locked ones are silhouettes. New unlocks are announced once with a
  celebration.
- The window shows the current season; in dark mode the room dims and its lamps glow. Mako sits in the room,
  reacts to choices and pokes, and the corner companion is hidden on this page.
- Tests: `apps/gamification/test_makon_room_v506.py`.
