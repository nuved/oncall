# Ledger — Mansoor OnCall

One row per unit of work. Status: done-verified (evidence re-run by a second pass), done, ongoing,
awaiting (blocked_on: human), dropped. Evidence is a SHA, tag, run id or file; a row without evidence is not done.

| date | id | bet | value | status | evidence | why_plain |
|---|---|---|---|---|---|---|
| 2026-09-03 | L-01 fork created and cloned | B-01 | velocity | done | <https://github.com/nuved/oncall> | The project has a home the maintainer controls after Grafana archived the original. |
| 2026-09-03 | L-02 Grafana 13 plugin fixes cherry-picked from appwrite (17 commits, author loks0n) | B-01 | risk | done | 4397c8f4..751f49e3 on dev; plugin connected and rendered on Grafana 13.2.1 in a browser | The plugin no longer crashes on the current Grafana, so paging keeps working after an upgrade. |
| 2026-09-03 | L-03 Grafana memory limit 2 GB in both compose files | B-01 | risk | done | ee2a75bb; peak 944 MiB measured during e2e | The Grafana container stops restarting under load on the hobby and developer stacks. |
| 2026-09-03 | L-04 CI on ubuntu-latest, Grafana-internal workflows removed, tests.yml on push to dev | B-01 | velocity | done | 849e9611, 2bb1c082, 5f286a19 | Every push runs the full test suite on GitHub and shows the result on the README badge. |
| 2026-09-03 | L-05 pre-push hook and make targets for local unit tests | B-01 | velocity | done | 2bb1c082 (.githooks/pre-push) | Unit tests run before every push without anyone remembering to start them. |
| 2026-09-03 | L-06 publish.yml: GHCR engine image (amd64, arm64), plugin archive, GitHub release | B-01 | velocity | done | run 33781194386; ghcr.io/nuved/oncall:v1.17.0 pulls anonymously | A release is one tag push; the image and the plugin archive appear without manual steps. |
| 2026-09-03 | L-07 Release v1.17.0 "Mansoor" | B-01 | retention | done | <https://github.com/nuved/oncall/releases/tag/v1.17.0>; sha256 of the zip verified; plugin.json 1.17.0 | Users can install a version of OnCall that works on Grafana 13 instead of the archived build. |
| 2026-09-03 | L-08 compose and Helm pinned to this fork's image and plugin archive; chart Grafana 13.2.1 | B-01 | retention | done | bec1974a | A fresh install pulls the fixed plugin and engine, not the archived ones that crash. |
| 2026-09-03 | L-09 first CI fixes: Helm snapshots, migration check on push, yamllint | B-01 | velocity | done | 561b58db | The lint, Helm and migration jobs pass on this fork's workflows. |
| 2026-09-03 | L-10 MariaDB subchart pinned to bitnamilegacy 12.0.2 after latest became 13.0.1 | B-01 | risk | done | f4d4abe1; bitnami/mariadb:latest image config created 2026-09-03T01:17Z | The e2e database starts again, and Helm users stop depending on a tag that changes under them. |
| 2026-09-03 | L-11 own logo: avatar mark with on-call dot, portrait medallion, dedication in README and release notes | B-01 | retention | done | b0427b32; proposal approved by the operator in chat ("confirmed") | The fork carries its own identity instead of Grafana Labs' mark, and every release names whose memory it honours. |
| 2026-09-03 | L-12 product named Mansoor OnCall; plugin archive ships the AGPL text instead of the Enterprise agreement file | B-01 | risk | done | f4474a94; Grafana Labs: "OnCall (OSS) is licensed under AGPLv3" (blog, grafana-oncall-maintenance-mode) | Users see the fork's own name, and the plugin they download carries the licence that actually applies to it. |
| 2026-09-03 | T-01 tests.yml green on dev | B-01 | risk | ongoing | run pending after L-10 | see backlog |
| 2026-09-03 | T-06 real Twilio call | B-02 | retention | awaiting (blocked_on: human — Twilio account, number, credentials) | — | see backlog |
