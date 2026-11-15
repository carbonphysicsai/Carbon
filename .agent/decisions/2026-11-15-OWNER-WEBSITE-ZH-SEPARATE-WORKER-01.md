## 2026-11-15 — OWNER-WEBSITE-ZH-SEPARATE-WORKER-01: `/zh/` is the `carbon-zh-preview` Worker, not part of the carbonwebsite deploy

Amends OWNER-WEBSITE-DASHBOARD-01.

**What happened.** The first `Website deploy` run (carbonwebsite version
`1444aaa8-efe6-493d-a0a0-0663a1db5828`) put Dashboard and the new Miners button
live on every English page. The two Chinese pages did not change: every path
under `/zh/` is served with `x-robots-tag: noindex, nofollow, noarchive` and the
earlier content. The owner confirmed in session, with a Cloudflare screenshot,
that a separate Worker, `carbon-zh-preview` (`zh-preview.carbonphysics.ai` plus
four other routes), serves them: "Yes there is a seperate worker for the Chinese
pages". The run's final check failed only on those two pages; nothing was rolled
back, since the English change was correct and nothing broke.

**Change.** `website/carbonwebsite/site/zh/` (62 files) is removed. A deploy
of that folder cannot change `/zh/`, and keeping the copy made the next deploy's
live check fail. `compare-live.mjs` skips `zh/` (`SERVED_ELSEWHERE`), including
in a `--site` copy from before the removal. With that, live matches both
`main` and this change, so the workflow finds nothing to deploy.

**Open.** The Chinese pages' nav does not show 仪表盘 (Dashboard). Their source
is not in this repository; changing them means deploying `carbon-zh-preview`.
That is the owner's call.
