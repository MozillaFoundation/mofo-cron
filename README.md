# MoFo Cron

A collection of maintenance tasks that Mozilla Foundation runs at regular intervals. Each task is a standalone script — bash, Python, or Node — invoked by the **Heroku Scheduler** addon on the `mofo-cron` app.

- **Heroku app:** `mofo-cron` (scheduler addon `scheduler-adjacent-74050`)
- **Config:** entirely environment variables, set as Heroku config vars. See [`env.dist`](env.dist).
- **Deploys:** pushed manually; the scheduler runs whatever is in the current slug.

## Scheduled processes

The scheduler config is not in this repo — it lives in the Heroku dashboard. The table below is what was actually observed running, reconstructed from `heroku logs -a mofo-cron` on 2026-09-07. All times UTC.

| When | Command | Purpose |
| --- | --- | --- |
| Mondays 06:00 | `./tasks/clone_foundation_site/task.sh --only-monday` | Clone + scrub prod foundation DB to staging. Pings healthchecks.io on success. |
| Daily 09:00 | `./tasks/redeploy_site/task.sh donate-wagtail-production <tarball>` | Rebuild donate-wagtail production from `master`. |
| Daily 14:00, 20:00 | `python tasks/heroku_pipelines_check/slack_webhook.py` | Post to Slack when staging can be promoted to prod. Script self-limits to Mon–Thu. |
| Hourly :20 | `ssl-date-checker donate.mozilla.org` (3- and 30-day thresholds) | Certificate expiry watch, pings hchk.io. |
| Hourly :20 and :30 | `ssl-date-checker changecopyright.org` (3- and 30-day thresholds) | Certificate expiry watch. |
| Daily 18:30 | `ssl-date-checker togetherjs.com` (30-day threshold) | Certificate expiry watch. |

The SSL checks are inline scheduler commands, not scripts in this repo — they use the `ssl-date-checker` npm dependency and `jq` (from [`Aptfile`](Aptfile)) directly.

**Not currently scheduled**, though the code is still here: `tasks/typeform/delete_responses.py` and `tasks/create_image.js`. Neither appeared in a full 48-hour log window covering a Monday.

## Task reference

### `tasks/clone_foundation_site/task.sh`

Copies production foundation-site data to staging, scrubbing PII on the way. Steps:

1. Install the Heroku CLI and awscli into the dyno if absent.
2. Put staging into maintenance mode and scale `web` to 0.
3. Capture a backup of prod, then of staging (the staging one is the rollback point).
4. Restore the prod backup over staging.
5. Run [`cleanup.sql`](tasks/clone_foundation_site/cleanup.sql) to scrub the restored data.
6. `aws s3 sync` prod media bucket to staging.
7. Run `manage.py migrate`, then `manage.py update_staging_site_hostnames`.
8. Scale `web` back to 1 and leave maintenance mode.

An `on_exit` trap makes failure safe rather than silent: on any non-zero exit it restores the staging backup from step 3, rescales the dynos and clears maintenance mode. A failed run therefore leaves staging **working but stale**, never broken.

Usage: `./tasks/clone_foundation_site/task.sh [--only-monday]`

Required env: `STAGING_APP_NAME`, `PRODUCTION_APP_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `STAGING_S3_BUCKET`, `PRODUCTION_S3_BUCKET`, `STAGING_S3_PREFIX`, `PRODUCTION_S3_PREFIX`, `S3_REGION`.

#### What `cleanup.sql` scrubs

- `TRUNCATE django_session`
- Deletes `social_auth_usersocialauth` rows whose `uid` is not `@mozillafoundation.org`
- Rewrites every non-staff `auth_user` to `anonymouse<N>` with a random email and bcrypt hash

> The two `wagtailcore_site` / `django_site` hostname `UPDATE`s in this file are **dead code**. They match on `foundation.mozilla.org`, but production's hostname is now `www.mozillafoundation.org`, so they update zero rows. Staging hostnames are set correctly by the `update_staging_site_hostnames` management command in step 7, added in `695febf`.

### `tasks/heroku_pipelines_check/slack_webhook.py`

Runs `heroku pipelines:diff` against each pipeline listed at the top of the script (`foundation-site`, `network-pulse`, `network-pulse-api`, `donate-wagtail`) and posts a Slack Block Kit message to #mofo-production when prod is behind staging. Self-limits to Monday–Thursday.

Required env: `SLACK_PIPELINES_WEBHOOK`.

Usage: `python tasks/heroku_pipelines_check/slack_webhook.py`

### `tasks/redeploy_site/task.sh`

Nine-line `curl` that POSTs to the Heroku Build API to rebuild an app from a source tarball.

Usage: `./tasks/redeploy_site/task.sh <app-name> <tarball-url>`

Required env: `HEROKU_API_KEY`.

### `tasks/typeform/delete_responses.py`

Deletes **all** responses from **every** form in the authenticated Typeform account. Paginates forms, paginates responses, deletes in batches of 25. Self-limits to Mondays. See the docstrings in the source for the API endpoints used.

Required env: `TYPEFORM_AUTH_TOKEN`.

Usage: `TYPEFORM_AUTH_TOKEN=... python tasks/typeform/delete_responses.py`

Tests: `python tasks/typeform/test_delete_responses.py`

### `tasks/create_image.js`

Creates an EC2 AMI of an instance. The oldest file in the repo (2016).

Usage: `node tasks/create_image.js <region> <instanceId> <name> <deviceName> <dayOfWeek> [noReboot] [dryRun]`

Note the `deviceName` argument in position 4 — earlier revisions of this README omitted it, which shifts every subsequent argument by one.

- `dayOfWeek` — only run when it matches `(new Date()).getDay()`; 1–7.
- `noReboot`, `dryRun` — optional, `true|false`, default `false`.

Required env: `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, for an IAM user with `ec2:Describe*`, `ec2:CreateSnapshot` and `ec2:CreateImage`.

## Known issues

### The clone and Slack tasks have been failing since 2026-06-25

Release **v73** (`18d804f`, deployed 2026-06-25) bumped `runtime.txt` from `python-3.9` to `python-3.12`. [`requirements.txt`](requirements.txt) still pins `urllib3==1.25.9`, which is not compatible with Python 3.12 — importing it raises:

```text
ModuleNotFoundError: No module named 'urllib3.packages.six.moves'
```

This breaks any task that imports `requests` or `awscli`:

- **`slack_webhook.py`** fails on its `import requests` line and exits 1. Both the 14:00 and 20:00 runs have been dying immediately, so **no pipeline-promotion notifications are reaching Slack.**
- **`clone_foundation_site/task.sh`** gets as far as step 6, the S3 sync, before `python -m awscli` hits the same error. `set -e` then fires the `on_exit` trap, which rolls staging back to the backup taken in step 3 — undoing the restore and the scrub that had already succeeded.

The last clone that was **not** rolled back was Monday **2026-06-22**, the Monday before v73 deployed. Every Monday run since (11 as of 2026-09-07) has restored prod, scrubbed it, failed the sync, and reverted. Staging's newest content is 2026-08-26 against production's 2026-09-07.

Dating method: `cleanup.sql` truncates `django_session`, so the oldest surviving session in staging marks the last run that stuck. That row was created 2026-06-23 21:27 UTC.

**Fix:** regenerate `requirements.txt` from `requirements.in` with `pip-compile` so `urllib3` and `certifi` (also pinned to 2020 versions) resolve to something Python 3.12 supports. The task installs `awscli` at runtime, which drags in its own botocore that then imports the stale pinned `urllib3` from the slug — so both the pinned deps and the runtime `pip install awscli` need to agree.

### No historical logs

`heroku logs` retains roughly two hours on this app, and the window is dominated by the hourly SSL checks. Papertrail is attached but returns **zero events for every system**, including busy production apps, so past runs cannot be audited. Either the drain is dead or the `PAPERTRAIL_API_TOKEN` config var lacks log-read scope. Worth fixing before the next incident.

### Stale dependencies

- `requirements.txt` pins are from 2020: `requests 2.23.0`, `urllib3 1.25.9`, `certifi 2020.4.5.1`.
- `package.json` declares `"node": "^8.11.2"` (long EOL) and `aws-sdk` v2 (maintenance mode).
- The `heroku` CLI installed by `task.sh` reports itself as 7.69.1 against a current 11.10.0.

## Production vs staging database size

A recurring question: why is production ~3.6 GB when staging is ~1.6 GB, if staging is a copy?

```text
                       prod                     staging
Data size              3.62 GB                  1.61 GB
Tables                 268                      268
Latest logical dump    638 MB                   520 MB
```

The gap is **not** missing data. Table counts match exactly, and row counts track closely (`wagtailpages_blogpage` 12,409 on both; `wagtailpages_productvote` 571,255 vs 571,239; `wagtailcore_referenceindex` 368,072 vs 366,505). The compressed dumps differ by only 1.23×, versus 2.25× on disk — the data is comparable, the storage is not. Two causes:

### 1. `django_session` — ~812 MB, removed by design

`cleanup.sql` truncates it, so staging never carries it.

```text
total sessions   2,271,695
expired          2,271,031   (99.97%)
active                 664
oldest expiry    2017-03-24
table size          812 MB   (344 MB heap + 437 MB indexes)
actual payload      195 MB   (avg 90 bytes/row)
```

Django never deletes expired sessions on its own — `expire_date` is only consulted on read. `manage.py clearsessions` has apparently never run against this database.

Decoding a stratified sample of the payloads shows what they are:

| Era | Rows | Content |
| --- | --- | --- |
| 2017–18 | ~700 | Real staff logins (`_auth_user_id`, `google-oauth2_state`) |
| 2019–2024 | ~2.27M | **`_language` and nothing else** |
| 2025–26 | ~2,450 | `auth0_state` + `next` |

Ninety-two percent of the table is one key. Every anonymous visitor got a database row created to remember a language preference: 1,432,788 in 2020 and 668,872 in 2021 alone. That behaviour tapered off after 2021. Current sessions are abandoned Auth0 handshakes — the site stashes the OAuth state and post-login redirect before bouncing to Auth0, and the row is orphaned if the login is never completed. Only ~1,500 so far in 2026, so it is a trickle rather than a leak.

### 2. Bloat — ~1,200 MB

Production has never been repacked. Staging is rebuilt by `pg_restore`, which rewrites every table and index tightly packed. The clearest example:

```text
wagtailsearch_indexentry
  prod      902 MB   (118 MB heap, 261 MB idx)    88,932 rows
  staging   272 MB   ( 31 MB heap,  56 MB idx)   101,239 rows
```

Staging holds *more* rows in under a third of the space. The same pattern appears in `wagtailcore_revision` (999 MB → 754 MB), `wagtailpages_blogpage` (157 MB → 61 MB) and `wagtailpages_articlepage` (63 MB → 24 MB). Production also carries live dead tuples — 218k in `django_session`, 23k in `wagtailcore_pagelogentry`, 15k in `wagtailcore_revision` — where staging is at zero across the board.

### Reclaiming it

Deleting rows will not shrink the files on its own; both steps are needed.

1. **Delete expired sessions.** `clearsessions` only touches rows past `expire_date`, so the 664 live sessions are safe. Do not run it as a single statement against 2.27M rows — batch it (`DELETE ... WHERE session_key IN (SELECT ... LIMIT 50000)` in a loop) during a quiet window, or the WAL burst will add more dead tuples than it clears.
2. **Repack.** `pg_repack` on `django_session` afterwards, and on `wagtailsearch_indexentry` for another ~630 MB.

Then schedule `clearsessions` weekly. It belongs as a scheduler job on `foundation-mozilla-org` rather than in this repo, since it needs the Django app context.

Until production is cleaned up, the prod/staging size comparison is not a useful health signal — it mostly measures how long it has been since production was repacked.

## Local development

```sh
python -m venv venv && source venv/bin/activate
pip install pip-tools
pip-sync requirements.txt dev-requirements.txt
```

Dependencies are managed with `pip-compile`: edit `requirements.in` / `dev-requirements.in`, then regenerate the `.txt` files. Copy `env.dist` to `.env` and fill it in.
