# Strategy — OnCall fork (codename Mansoor)      drafted-by: fable · 2026-09-03 · approved-by: none yet

metric_now: Grafana stable releases the fork is verified on
· current: 13.2.1 by manual browser check and build; e2e in CI not yet green
  (provenance: session of 2026-09-03, run 33781193418)
· target: e2e green on the current Grafana stable within 14 days of every Grafana minor release,
  held through 2026-12-31

## Bets (≤ 3)

| id | bet (one sentence) | why now | evidence | kill criterion | review date | value |
|---|---|---|---|---|---|---|
| B-01 | The fork keeps working on every current Grafana release, proven by CI, so an upgrade of Grafana never takes on-call notifications down. | Upstream is archived; Grafana 13 (React 19) already broke the archived plugin on mount. | Plugin verified on 13.2.1 in a browser (known); appwrite's e2e passed on 13.2.0 (known); our e2e failed only on a floating MariaDB image (known). | e2e red on the newest Grafana minor for more than 30 days after its release → stop maintaining compatibility ourselves and track appwrite/grafana-oncall wholesale. | 2026-10-15 | risk |
| B-02 | Phone calls and SMS through Twilio work end to end from this fork, including acknowledging an alert by keypress. | The operator named voice as a must-have; the code exists but runs a 2020 SDK and has not been exercised against a real account here. | Twilio provider present with gather/verify/callbacks (known); SDK usage limited to Client, TwiML, RequestValidator (known); no real-account test yet (guessed to pass). | No Twilio account and number available for a real call by 2026-10-31 → park the bet, keep the code as is. | 2026-10-31 | retention |
| B-03 | The engine runs on a supported stack (Django 5.2 LTS, current MySQL/PostgreSQL/Redis/RabbitMQ) with the install-flow security fixes appwrite shipped. | Django 4.2 left extended support in April 2026 (inferred from Django's schedule); the dev compose pins Postgres 14 and Redis 7.0, both near or past end of life. | appwrite's Django 5.2 commit and DB matrix bump exist and their CI is green (known). | pytest not green on Django 5.2 across all three databases within 10 working days of starting → stay on 4.2 and backport only security fixes. | 2026-11-15 | risk |

## Not doing (≥ 3)

| item | reason | revisit trigger |
|---|---|---|
| Discord integration (appwrite has one) | Nobody here asked for it; ~40 commits of surface to maintain. | A user of this fork asks for Discord. |
| Renaming the plugin ID to escape the "deprecated" catalog banner | Rename touches RBAC action names, the engine, Helm and every install; the banner is cosmetic. | Grafana refuses to load plugins flagged deprecated in the catalog. |
| Signing the plugin through grafana.com | Not possible for a fork; unsigned loading is allow-listed in compose and Helm. | Grafana removes the unsigned-plugin allow-list. |
| Swapping webpack/ESLint for Rsbuild/Oxc (appwrite did) | Build works; a toolchain swap buys speed we do not need yet. | Production build exceeds 5 minutes in CI or a dependency forces it. |
| appwrite's release governance (two-phase promotion, SBOM, provenance) | One maintainer, no external consumers yet. | A second organization deploys this fork. |
| Publishing the Helm chart to a chart repository | `helm install ./helm/oncall` from the checkout is enough for one deployment. | A second deployment needs `helm repo add`. |

## Constraints

- runway: one maintainer plus an agent, part time (guessed)
- regulation: DSGVO applies; the engine stores names, emails and phone numbers, and Twilio is a processor that
  needs a DPA if EU persons are called
- licence: AGPL-3.0 inherited from upstream; attribution to Grafana Labs and to appwrite's commits preserved
- platform: Grafana plugin API with a shared React 19 runtime; the unsigned plugin needs
  GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS; GitHub free runners (2 cores, native arm64 available); the
  maintainer's Docker Desktop VM is shared with other projects and too small for the e2e suite

## Decisions

| date | decision | reason |
|---|---|---|
| 2026-09-03 | Cherry-pick appwrite's Grafana 13 fixes instead of adopting their fork | Smallest diff to the archived upstream; their fork carries Discord, Django 5.2, Rsbuild and their own release machinery. |
| 2026-09-03 | Plugin declares Grafana ≥ 12.0; Grafana 10 and 11 dropped | That is what the cherry-picked e2e suite covers; the fork cannot test what it does not run. |
| 2026-09-03 | Engine image on GHCR (ghcr.io/nuved/oncall), plugin archive attached to GitHub releases | Docker Hub grafana/oncall and the grafana.com catalog are frozen at the archived build. |
| 2026-09-03 | Grafana gets 2 GB / 2 CPUs in both compose files | Grafana 13 idles near 400 MiB and peaked at 944 MiB under e2e; the old 500 MB cap restarted it. |
| 2026-09-03 | Workflows run on ubuntu-latest; Grafana-internal workflows deleted | The 16-core label and the vault/Docker Hub/GCS secrets do not exist for this fork. |
| 2026-09-03 | MariaDB subchart pinned to bitnamilegacy 12.0.2 | The floating `latest` became 13.0.1 on 2026-09-03 and fails the chart's own probe. |
