# Deploying MakonBook to makonbook.uz

This repository is the MakonBook web app (Django). It is the newer version of
makonBook-2.0 and replaces it **in place**: same image name, same Compose
project, same database, same nginx.

```
                         :80/:443
Internet ──▶ makonbook-nginx ──┬─▶ makonbook-web:8000      makonbook.uz          (this repo)
             (/opt/sat-makon/  ├─▶ makonbook-api:8080      api/admin.makonbook.uz (makonbook-api)
              makonbook)       └─▶ sat-makon-site:80       sat-makon.uz

sat_makon_network ──▶ db (PostgreSQL 16)
                       ├─ makonbook       this app's database (read/write, migrated by this app)
                       └─ makonbook_api   makonbook-api's database — this app only READS it
```

The image is `nazacd/makonbook`. The VPS never builds anything: it pulls the
image and starts it.

## What this app takes from makonbook-api

Practice tests and vocabulary come from makonbook-api — the reviewed, fixed
and approved content of the question bank, and the vocabulary lists with their
pictures. `apps/content_sync` copies them into this app every 10 minutes
(Celery Beat):

- **Practice tests:** the latest *published* version of every test
  (`practice_test_versions`, so only tests whose every question is approved).
  Each becomes a regular test of the same name (DAY12, …) with its questions.
  The text keeps makonbook-api's format and is rendered when a page shows it
  (`apps/sat/rich_text.py`): math, tables, lists, figures. When makonbook-api
  publishes a new version, the test is updated in place.
- **Vocabulary:** the lists become vocabulary units with their words, parts of
  speech and pictures. They replace the units made in this app (those are
  switched off, not deleted).
- **Images** (question figures, word pictures) are in makonbook-api's private
  R2 bucket. Each file is copied once into this site's public bucket under
  `media/makonbook-api/`.

Nothing is ever written to makonbook-api's database or bucket. The database
connection is read only (`default_transaction_read_only=on`), and Django never
migrates it. makonbook-api, its database and its deploy are not touched.

---

## First deploy (replacing makonBook-2.0)

Everything happens in `/opt/sat-makon/makonbook/` on the VPS.
**`docker-compose.yml` and `nginx/` there stay exactly as they are.** The
VPS file runs `web`, `telegram-bot`, `nginx` and `certbot` only. The background
services (Redis, Celery worker, Celery Beat) come from one extra file,
`deploy/docker-compose.override.yml`, saved next to it as
`docker-compose.override.yml` (step 6). `docker compose` merges the two by
itself.
Never copy this repo's `nginx/default.conf` over the VPS one: the VPS file also
holds the api/admin.makonbook.uz blocks.

### 1. Keep the current image for a rollback

On any machine logged in to Docker Hub as `nazacd`:

```bash
docker pull nazacd/makonbook:latest
docker tag nazacd/makonbook:latest nazacd/makonbook:2.0-final
docker push nazacd/makonbook:2.0-final
```

### 2. Back up the databases

```bash
/opt/makonbook-api/backup-postgres.sh
ls -lh /opt/backups/postgres | tail
```

Step 7 deletes the old practice tests and their results, and that cannot be
undone without this backup.

### 3. A read-only R2 token for makonbook-api's bucket

In Cloudflare → R2 → Manage API tokens, create a token with **Object Read
only**, scoped to makonbook-api's bucket (`R2_UPLOADS_BUCKET` in
`/opt/makonbook-api/.env`). Keep its access key ID and secret for step 4.

### 4. Add the new settings to `.env`

Append them to `/opt/sat-makon/makonbook/.env`. Don't replace the file: it has
the live secrets.

```bash
cd /opt/sat-makon/makonbook
cat >> .env <<'EOF'

# --- makonbook-api content (practice tests, vocabulary) ---
MAKONBOOK_API_SYNC_ENABLED=true
MAKONBOOK_API_SYNC_INTERVAL_MINUTES=10
MAKONBOOK_API_R2_BUCKET=<makonbook-api's bucket name>
MAKONBOOK_API_R2_ACCESS_KEY_ID=<read-only token id>
MAKONBOOK_API_R2_SECRET_ACCESS_KEY=<read-only token secret>
EOF
chmod 600 .env
```

The database needs no setting. This app reads `makonbook_api` on the same
server with the same login as its own database. On this VPS that login is
`postgres`, which can already read it. To use another login, set
`MAKONBOOK_API_DATABASE_URL=postgres://user:pass@db:5432/makonbook_api?sslmode=disable`.
`MAKONBOOK_API_R2_ENDPOINT_URL` defaults to `R2_ENDPOINT_URL` (same
Cloudflare account). Set it only if the bucket is in another account.

### 5. Build and push the image

Merging to `main` does it: `.github/workflows/docker.yml` runs the tests,
then pushes `nazacd/makonbook:latest` and `:sha-<commit>`. It needs the
repository secrets `DOCKERHUB_USERNAME` (`nazacd`) and `DOCKERHUB_TOKEN`.

Or by hand, from a checkout:

```bash
docker build -t nazacd/makonbook:latest .
docker push nazacd/makonbook:latest
```

### 6. Start it

Once, add the background services, from your computer in a checkout of this repo:

```bash
scp deploy/docker-compose.override.yml root@188.245.175.83:/opt/sat-makon/makonbook/docker-compose.override.yml
```

`.env` must point Celery and the rate-limit cache at that Redis
(`CELERY_BROKER_URL=redis://redis:6379/1`, `CELERY_RESULT_BACKEND=redis://redis:6379/2`,
`REGISTRATION_RATE_LIMIT_CACHE_URL=redis://redis:6379/3`). Then:

```bash
cd /opt/sat-makon/makonbook
docker compose pull
docker compose up -d
docker compose logs -f web      # "Applying database migrations..." then gunicorn
```

`docker compose ps` should list 7 containers: web, telegram-bot, nginx,
certbot, redis, celery-worker and celery-beat.

The web container applies this version's migrations to `makonbook` when it
starts (`RUN_MIGRATIONS=1`). They only add tables and columns.

### 7. Remove the old practice tests (once)

The regular practice tests made in this app are removed with their questions
and results (attempts, scores, reviews, homework that assigned them), so the
synced tests can take their names. Placement, event and makeup tests and
their results stay. Questions that a makeup test uses also stay. Look first,
then confirm:

```bash
docker compose exec web python manage.py remove_legacy_tests
docker compose exec web python manage.py remove_legacy_tests --confirm
```

A regular test that an event runs on is kept and listed, because deleting it
would delete the event. Its synced namesake can't be created until the event
uses another test or is over and removed. `sync_makonbook_api` lists those
names as conflicts.

### 8. First sync from makonbook-api

```bash
docker compose exec web python manage.py sync_makonbook_api --dry-run
docker compose exec web python manage.py sync_makonbook_api
```

It prints what it created. From now on `celery-beat` runs it every 10 minutes
and it only does work when something changed. State and the last error are in
Django admin → *makonbook-api content sync*.

### 9. Give classes their tests

Practice tests are opened per classroom, as before. Classrooms set to *All
practice tests* get new tests automatically. For the others, teachers choose
them in the classroom's settings.

---

## HolliHop

HolliHop sync only reads HolliHop, and only in one direction, HolliHop →
MakonBook. It creates and updates students, teachers, managers, one classroom
per HolliHop GROUP, memberships and attendance. It never writes to HolliHop.
It runs next to makonbook-api's own HolliHop sync, and the two share
HolliHop's rate limit (600 requests per 30 s) comfortably.

How it runs once it's on:

- `celery-beat` starts a smart sync every 5 minutes: changes since the last
  run, plus slower safety sweeps.
- HolliHop's webhook (`/integrations/hollihop/webhook/`) applies student
  changes immediately.
- Both stay blocked until the **initial sync** has finished once.
- Nothing runs when containers start.

### Turning it on (first time)

1. Add to `.env`, keeping `SCHOOL_DATA_PROVIDER=local` for now:

   ```
   HOLLIHOP_ENABLED=true
   HOLLIHOP_API_URL=https://satmakon.t8s.ru/Api/V2
   HOLLIHOP_AUTH_KEY=<same key as HOLLIHOP_AUTHKEY in /opt/makonbook-api/.env>
   HOLLIHOP_WEBHOOK_SECRET=<openssl rand -hex 24>
   HOLLIHOP_SEND_CREDENTIALS=false
   HOLLIHOP_AUTO_SEND_CREDENTIALS=false
   ```

   Then run `docker compose up -d` so the containers read it.

2. Dry run. It reads HolliHop and reports, without writing anything:

   ```bash
   docker compose exec web python manage.py sync_hollihop --all --dry-run
   ```

3. When the report looks right, set `SCHOOL_DATA_PROVIDER=hollihop` in `.env`
   and run `docker compose up -d`.

4. Run the initial import once. Either use **Manager → HolliHop Integration →
   Run initial sync**, or run:

   ```bash
   docker compose exec web python manage.py sync_hollihop --all --mark-initial
   ```

5. In HolliHop, set the webhook for StudentClient events to
   `https://makonbook.uz/integrations/hollihop/webhook/?key=<HOLLIHOP_WEBHOOK_SECRET>`.

**Logins for HolliHop students:** each new account gets a temporary password,
which must be changed at first login. It is delivered only by SMS (Eskiz,
`MAKONBOOK_SMS_PROVIDER=eskiz` with `HOLLIHOP_SEND_CREDENTIALS=true`) or from
the Manager panel (resend credentials). Public sign-up is closed in this
version, so until SMS is on, managers hand out the logins.

---

## Every later release

```bash
# build machine (or just merge to main)
docker build -t nazacd/makonbook:latest . && docker push nazacd/makonbook:latest

# VPS
cd /opt/sat-makon/makonbook && docker compose pull && docker compose up -d
```

Migrations run by themselves. To pin a build, set
`APP_IMAGE=nazacd/makonbook:sha-<commit>` in `.env`.

## Rollback

**To an earlier build of this app:** set `APP_IMAGE=nazacd/makonbook:sha-<commit>`
in `.env` and run `docker compose up -d`.

**Back to makonBook-2.0:** the image alone is not enough. This app's
migrations add required columns that makonBook-2.0 doesn't fill (for example
`teststage.integrity_mode`, `testreview.run_mode`), so 2.0 fails when it saves
an attempt. Restore the `makonbook` database from the step 2 backup, then
start 2.0's image:

```bash
cd /opt/sat-makon/makonbook
docker compose stop web celery-worker celery-beat telegram-bot
docker exec -i db pg_restore -U postgres --clean --if-exists -d makonbook < /opt/backups/postgres/makonbook-<stamp>.dump
sed -i 's|^APP_IMAGE=.*|APP_IMAGE=nazacd/makonbook:2.0-final|' .env   # add the line if .env has none
docker compose up -d
```

Anything people did on the new version after the backup is lost by a restore.
