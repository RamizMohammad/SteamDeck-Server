# Linkium server (FastAPI + PostgreSQL)

One repo, one Docker image, **two separate applications** on the VPS:

| Container | Code | Port | Replaces |
|---|---|---|---|
| `steamdeck-server` | `app/` (REST API + `/ws`) | 8002 | `SteamDeck-Server` (Express + Mongo) |
| `linkium-relay` | `relay/` (WebSocket relay) | 8003 | `ssh_linkium_server/DeployServer.py` (FastAPI + Mongo) |

Both use the existing `central-postgres` (API: `users`, `programs`, `activity_log`; relay: `relay_*`).
They share `.env`, deploy together, and restart and fail independently.


A drop-in replacement for the old Express + MongoDB server (`old server/`). It uses the
same URLs, JSON shapes (down to key order), error strings, status codes, CORS headers,
JWTs and WebSocket protocol, so the web frontend and the desktop receiver don't need any
changes. Data now lives in PostgreSQL. `scripts/migrate_mongo_to_postgres.py` moves it
over and verifies every user afterwards.

## Run

```bash
cp .env.example .env              # set DATABASE_URL, JWT_SECRET
docker compose up -d --build      # API only; it uses the existing central-postgres container
```

Without Docker: `pip install -r requirements.txt && uvicorn app.asgi:app --port 8002 --proxy-headers`.
The schema (`app/schema.sql`) is applied automatically on startup and is safe to re-run.

Set `CONTAINER_NAME` in `.env` to whatever `central_nginx` already
proxies to. Always run **one worker**: WebSocket pairing groups live in process memory.

## Moving the data off MongoDB (cutover runbook)

The script copies everything in **one transaction**. It then rebuilds every user from
Postgres and compares it field by field with the Mongo document, and rolls back if
anything differs.

```bash
# 0. Change the Atlas password first (the old one is in a public repo), then put the new URI in .env
# 1. Check the data without writing anything (runs inside Docker so central-postgres resolves)
docker compose run --rm steamdeck-server python scripts/migrate_mongo_to_postgres.py --dry-run

# 2. Cutover (a few seconds of downtime)
docker stop <old-server-container>        # stop writes to Mongo
docker compose run --rm steamdeck-server python scripts/migrate_mongo_to_postgres.py
docker compose up -d --build              # start the new API
docker restart central_nginx              # if the upstream name changed
```

What the report tells you:
- **Duplicate emails:** Mongo had no unique index. The first user in Mongo's natural
  order is kept (the only one the old login could ever reach); the others are listed and
  skipped.
- **Duplicate pairing codes:** the first user keeps the live code, matching what the old
  `findOne` returned. Later users still show their code in `/api/me` but no longer
  receive receiver syncs.
- **Extra data:** values with unexpected types and unknown fields are stored verbatim
  in an `extra` column, so nothing is lost.
- **Skipped `_id`s:** documents whose `_id` isn't an ObjectId can't be users of the old
  server, so they're listed and skipped.

**Rollback:** leave Atlas untouched for a while. Pointing nginx back at the old server
works immediately, but anything written to Postgres after the cutover won't be in Mongo.

**Backups:** `docker exec central-postgres pg_dump -U linkium -Fc linkium > linkium-$(date +%F).dump`
(nightly cron recommended). Restore with `pg_restore -d linkium`.

## Schema

| Table | Holds |
|---|---|
| `users` | `id` (ObjectId hex, the same value inside existing JWTs), `email` (unique), `password_hash` (bcrypt), `pairing_code` (jsonb, unique), `programs_fetched`, `created_at`, `extra` |
| `programs` | One row per program, ordered by `position`: `program_id`, `name`, `icon_url`, `exec`, `meta` (json), `added_at`, `extra` |
| `activity_log` | One row per entry, ordered by `seq`: `ts`, `type`, `msg`, `raw` (json), `extra` |

`meta` and `raw` use `json`, not `jsonb`, so their key order comes back exactly as it
was written. Every write locks the user's row, so concurrent requests can't reorder
programs or race signups.

## Tested

| Check | Result |
|---|---|
| `tests/diff_harness.py`: same HTTP + WebSocket traffic to old (Mongo) and new (Postgres) | 46/49 byte-identical, key order included; the 3 differences are intended (below) |
| `tests/migration_e2e.py`: every migrated user via both servers, before and after identical writes | Identical for all data the old server could produce |
| Migration verifier on deliberately messy data (duplicates, odd types, unknown fields, unicode, 50 KB icons) | 26/26 users rebuilt exactly |
| `tests/test_upgrades.py` | 11/11 |
| 40 concurrent writes to one user; 10 simultaneous signups with the same email | Ordered, nothing lost; exactly one account |
| Postgres restarted under a running API | Recovers on its own |

Intended differences from the old server:
1. Unknown routes return JSON `{"error":"Not found"}` instead of Express's HTML page.
2. A request from a disallowed CORS origin gets a normal response without CORS headers
   instead of a 500. The browser blocks it either way.
3. After a receiver sends `new_code`, its later `programs` syncs are saved. The old server
   silently lost them.

## Upgrades over the old server

**Security**
- No secrets in code. The server refuses to start without `DATABASE_URL`, or if
  `JWT_SECRET` is missing or set to the old default.
- Rate limiting on `/api/auth`: per IP, plus a lockout per email after repeated wrong
  passwords (429).
- Rejects injection attempts through auth, pairing and WebSocket inputs.
- Email and pairing code are unique at the database level (`409` on a taken code,
  including through a receiver's `new_code`).
- WebSocket: unknown roles are ignored; there's a 16 MB message cap, a per-connection
  rate limit, and send timeouts so one slow client can't stall a group.
- Optional strict mode, once the frontend supports it:
  - `WS_REQUIRE_AUTH=true`: senders must send their JWT (`{"role":"sender","code":"…","token":"<jwt>"}`
    or `/ws?token=<jwt>`), and it must belong to the account that owns the code.
  - `WS_ENFORCE_ORIGIN=true`: browser origins are checked. Clients without an `Origin`
    header, such as the desktop app, are still allowed.
- The API reaches Postgres over its Docker network only. The API runs as non-root,
  and the API docs pages are disabled.

**Bug fixes**
- Re-registering a socket no longer leaves a ghost copy in its old group.
- The activity log is capped at the newest `ACTIVITY_LOG_MAX` entries (default 1000).
  Users who already have more than that are trimmed on their next write.
- Every multi-step write is one transaction.
- Graceful shutdown closes sockets with 1001.
- Malformed bodies return 400/413 instead of 500.
- `PRESERVE_USER_PROGRAMS=true` keeps hand-added programs when the receiver syncs. It's
  off by default, matching the old behaviour.

## Tests

```bash
pip install -r requirements-dev.txt
AUTH_RATE_PER_MINUTE=1000 AUTH_FAIL_PER_15MIN=3 ACTIVITY_LOG_MAX=5 uvicorn app.asgi:app --port 8104 &
BASE_URL=http://localhost:8104 pytest tests/test_upgrades.py           # needs a reachable Postgres
python tests/diff_harness.py http://localhost:8101 http://localhost:8102     # old vs new
python tests/migration_e2e.py <old-url> <new-url> <mongo-uri>                # after a migration
```


## Relay (`relay/`)

Same protocol as the old relay: identical replies (`{"status":"registered",...}`,
`{"status":"linked",...}`, the same `{"error": ...}` strings), payloads forwarded
verbatim, and the same `GET /`, `/ping` and `/status` shapes.
`tests/relay_diff_harness.py` sends identical traffic to the old and new relays:
33/38 byte-identical, and the rest are these intended fixes:

- `/status` no longer lists live pairing codes (anyone could read one and take over a
  receiver). Counts stay public; codes appear only with `Authorization: Bearer $RELAY_STATUS_TOKEN`.
- The client IP is the `X-Forwarded-For` entry nginx appended, so the 10-connections-per-IP
  limit can't be dodged by sending a fake header. The API's login rate limit uses the same
  rule. Both apps run uvicorn with `--no-proxy-headers` for this.
- Failed sender links are slowed down (1 s after 5 per socket, 5 s after 120 per IP in
  10 min), so codes can't be brute-forced. The reply text is unchanged.
- A socket that registers a second code releases the first. The old relay left a ghost
  receiver holding the code ("Code already in use") until it was restarted.
- A non-string `code` or a binary frame now gets a normal reply instead of dropping the
  connection.
- Sends run concurrently with a 10 s timeout, so one slow client can't stall the others.
  A flood is capped per socket (200 msg/s, burst 1000).

Persistence never blocks relaying: events are written in the background, and if
Postgres is down the relay keeps working and reconnects within 30 s (tested).
Message metadata is pruned after `RELAY_MESSAGE_RETENTION_DAYS`, and sender history
is capped per code. Payloads are never stored.

**Moving the relay over**

```bash
# optional: copy the old relay's Mongo history (pairings + message metadata)
docker compose run --rm linkium-relay python scripts/migrate_relay_mongo_to_postgres.py --dry-run
docker compose run --rm linkium-relay python scripts/migrate_relay_mongo_to_postgres.py

# switch: stop the old relay, then point nginx at linkium-relay:8003
#   (or set RELAY_CONTAINER_NAME / RELAY_PORT to the old values so nginx needs no change)
cd /root/Projects/Linkium/ssh_linkium_server && docker compose down
cd /root/Projects/SteamDeck-Server && docker compose up -d linkium-relay
```

Relay tests: `RELAY_URL=http://localhost:8003 DATABASE_URL=... pytest tests/test_relay.py`
