# Build plan — Mansoor OnCall    drafted-by: fable · 2026-09-03 · approved-by: none yet

## B-01 The fork keeps working on every current Grafana release, proven by CI

### Architecture bets

| bet | door type | undo | build-vs-buy | reason |
|---|---|---|---|---|
| Compile the plugin against @grafana/* 11.1.3 types while running on Grafana 13 | two-way | bump the packages to 13.x and fix type errors | build | Grafana provides these packages at runtime; the older types compile and appwrite ships the same way. |
| Keep upstream's webpack/swc toolchain | two-way | cherry-pick appwrite's Rsbuild migration | build | Working today; swapping it now adds a second variable while e2e is not yet green. |
| Full upstream e2e suite (kind + tilt + helm) on GitHub free runners | two-way | run e2e on docker-compose instead of kind | buy (GitHub runners) | Reuses the suite appwrite already adapted to Grafana 12/13; free for a public repo. |
| Compatibility policy: test the newest patch of each supported Grafana minor, nothing older than 12 | one-way for users on 10/11 | restore grafanaDependency ≥ 10.2.5 and re-add 11.x to the matrix | build | Cost of the matrix is per Grafana version; every version tested must stay green. |

### Unknowns — spike before scheduling

| unknown | spike (≤ 1 day) | settling evidence | order |
|---|---|---|---|
| Does the e2e suite pass on 2-core runners with kind? Upstream's comment says small runners produced backend 504s. | Re-run tests.yml with the MariaDB pin (already pushed). | Both e2e jobs green in one run, or the flaky-test names. | 1 |
| Does the Insights page render on Grafana 13 with @grafana/scenes 1.28? | Start the dev stack with the Prometheus profile and open Insights. | Panels render and the console shows no scenes error. | 2 |
| Does the next Grafana minor (13.3 / 14) break the plugin? | A scheduled workflow running e2e weekly against grafana:latest and grafana:main. | A green or red scheduled run with a job name that says which image. | 3 |

### Milestones

| id | milestone | acceptance check | class | est_min | depends_on | ui_surface |
|---|---|---|---|---|---|---|
| M-01 | tests.yml green on dev, including e2e on 12.4.8 and 13.2.1 | `gh run list -R nuved/oncall --workflow tests.yml --branch dev --limit 1` shows conclusion success | standard | 120 | — | no |
| M-02 | Weekly scheduled compatibility run against grafana:latest and grafana:main | Workflow file with `schedule:`; one completed run visible in Actions | mechanical | 45 | M-01 | no |
| M-03 | Insights page verified on Grafana 13 | Screenshot of the Insights page with data from the local Prometheus profile; no console error | standard | 60 | — | yes |
| M-04 | Plugin compiled against @grafana/* 13.2.x with react-detect reporting nothing but third-party propTypes | `pnpm type-check`, `pnpm build`, `npx @grafana/react-detect` all exit 0 except known propTypes notes; e2e green | standard | 240 | M-01 | no |

### Debt

| item | carrying cost / month | pay trigger |
|---|---|---|
| Bitnami subcharts (postgresql 14.5, rabbitmq 3.12, redis 6.2) still pull from docker.io/bitnami tags that Bitnami has announced it deletes | one outage-shaped surprise when a tag disappears (0 h until then) | The first ImagePullBackOff, or before the next Helm-based deployment |
| CI actions pinned to node20-era versions (setup-node@v4, cache@v4) emit deprecation warnings | 0 h now; a red CI day when GitHub enforces node24 | GitHub's enforcement date announcement |
| Local pnpm 11 rewrites the lockfile that CI's pnpm 9.1.4 expects | ~15 min per contributor confusion | Adding `packageManager` to package.json (T-11) |

## B-02 Phone calls and SMS through Twilio work end to end

### Architecture bets

| bet | door type | undo | build-vs-buy | reason |
|---|---|---|---|---|
| Keep the built-in Twilio provider (calls with TwiML gather, SMS, Verify) rather than a new telephony layer | two-way | add another provider class behind PHONE_PROVIDER | buy (Twilio) | The provider, callbacks and keypress handling already exist and have unit tests. |
| Engine must be reachable from the internet at BASE_URL for callbacks and keypress | one-way for deployment topology | none: without it calls still go out but cannot be acknowledged by key | build | Twilio posts status callbacks and gather results to BASE_URL. |

### Unknowns — spike before scheduling

| unknown | spike (≤ 1 day) | settling evidence | order |
|---|---|---|---|
| Does the engine's Twilio code run on SDK 9.x unchanged? | Bump `twilio` in requirements, run `pytest engine/apps/twilioapp`. | Tests green; import of `twilio.request_validator` and `twilio.twiml.voice_response` unchanged. | 1 |
| Does a real call reach a phone and does pressing 1 acknowledge the alert? | With a Twilio trial account and a tunnel (e.g. cloudflared) to BASE_URL, page a user. | Alert group shows "acknowledged by phone" in its timeline. | 2 |

### Milestones

| id | milestone | acceptance check | class | est_min | depends_on | ui_surface |
|---|---|---|---|---|---|---|
| M-05 | Twilio SDK upgraded from 6.37.0 to the current 9.x | `pytest engine/apps/twilioapp engine/apps/phone_notifications` green on SQLite in CI | standard | 120 | — | no |
| M-06 | A real notification call and SMS verified from a dev stack | Timeline entry "acknowledged by phone" plus an SMS received; credentials supplied by the operator | standard | 120 | M-05, human: Twilio credentials | no |
| M-07 | OSS Twilio setup documented for this fork (env vars, BASE_URL reachability, Verify service) | Page under docs/sources/set-up/open-source with the variable list; markdownlint passes | mechanical | 45 | M-06 | no |

### Debt

| item | carrying cost / month | pay trigger |
|---|---|---|
| Twilio SDK 6.37.0 (2020) | security exposure with no fixes available | M-05 |

## B-03 The engine runs on a supported stack with appwrite's install-flow security fixes

### Architecture bets

| bet | door type | undo | build-vs-buy | reason |
|---|---|---|---|---|
| Django 5.2 LTS via appwrite's migration commits | two-way until a 5.x-only migration lands | revert the cherry-picks before any new migration | build | Their commits exist and their CI is green; redoing it is waste. |
| Database versions follow the vendor's current LTS lines (MySQL 8.4, PostgreSQL 17, Redis 8, RabbitMQ 4) | two-way in dev/CI, one-way for a deployed database (upgrade, not downgrade) | pin back in compose | buy | Supported lines get security fixes; the pins today are past end of life. |

### Unknowns — spike before scheduling

| unknown | spike (≤ 1 day) | settling evidence | order |
|---|---|---|---|
| Do appwrite's three install-flow security commits apply cleanly on our dev? | `git cherry-pick 8f1f8292 6c01383a a311a2e3` on a branch, run Go and Python tests. | Clean pick or a conflict list; `go test ./...` and `pytest engine/apps/grafana_plugin` green. | 1 |
| Does Django 5.2 pass pytest on MySQL, PostgreSQL and SQLite here? | Cherry-pick ef45a066 c0d7242f d48acbd8 on a branch, push, read tests.yml. | Three green backend jobs. | 2 |

### Milestones

| id | milestone | acceptance check | class | est_min | depends_on | ui_surface |
|---|---|---|---|---|---|---|
| M-08 | Install-flow security fixes merged | Go and Python tests green; plugin connects on a fresh dev stack | standard | 90 | M-01 | no |
| M-09 | Django 5.2 LTS | tests.yml green with all backend jobs; `django==5.2.*` in requirements | standard | 180 | M-01 | no |
| M-10 | Dev compose and CI databases on supported versions | compose files and linting-and-tests.yml reference the new images; tests.yml green | mechanical | 60 | M-09 | no |

### Debt

| item | carrying cost / month | pay trigger |
|---|---|---|
| Django 4.2 out of support | every published Django CVE becomes a manual backport (est. 2 h each) | M-09 |
| celery 5.3, redis-py 5.0, DRF 3.15 pinned two years back | rising conflict cost with each other upgrade | M-09 |
