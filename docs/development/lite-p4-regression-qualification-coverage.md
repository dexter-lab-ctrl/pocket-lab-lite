# P4 — Production regression and qualification coverage

**IMPLEMENTED AS TEST AND TASK DEFINITIONS; NOT EXECUTED.** No results, baselines, CI pass evidence, browser qualification or Server Phone/Android mutation are asserted.

## Objective

Codify strict staged regression coverage for P0–P3 across all seven Lite tabs and desktop/mobile, while keeping existing 60 FPS and exact-SHA qualification infrastructure authoritative. This increment does **not** run qualification or change the product's execution architecture.

## Added coverage

- `lite-p4-regression.spec.ts` exercises all seven screens with healthy mocked projections, Axe serious/critical failures, reduced motion and root viewport overflow.
- Conditional, evidence-honest P1/P2 guide checks on screen scenarios, without manufacturing absent findings.
- Quick navigation open/filter/select; Ctrl+K/Escape and focus return; no operational commands exposed.
- Saved/offline Home guidance not actionable.
- 320px width with 200% root font scaling.
- Wired `lite-p4-regression.spec.ts` into the repository's Playwright mocked-desktop/mobile project testMatch.
- P4 npm and Taskfile entries integrate component tests and existing suites. Live and Android lanes reuse current repository tools, not new qualification bypasses.

## Coverage policy / qualification phases

| Phase | Planned evidence | Invocation | Executed |
|---|---|---|---|
| P4 component | Vitest shared P0–P3 | `task lite:ui:p4:unit` | NO |
| Mocked E2E | New P4 cross-tab suite, 7 screens, desktop/mobile | `task lite:ui:p4:mocked` | NO |
| Complete mocked | Existing Storybook/Playwright snapshots, a11y, content-stress and 60 FPS | `task lite:ui:p4:full-mocked` | NO |
| Live read-only | Established authorized live screen and perf suites | `task lite:ui:p4:live` | NO |
| Physical Android | Existing repository-owned CDP qualification | `task lite:ui:p4:android` | NO |
| Repository gates | `npm run build:budget`, `task lite:check` | explicit later run | NO |

## Production gates before any future merge

- WCAG 2.2 AA review; zero serious/critical Axe findings on affected states, with scoped color-contrast reviews (existing repository global rules differ).
- Desktop, narrow mobile, large text, landscape, keyboard-only, focus trap and return, overlay layering, touch target checks.
- All seven tabs across online, saved, stale, error, pending, blocked and command-undeliverable states.
- Storybook fixtures and explicit reviewer-approved visual baselines; do not regenerate snapshots silently.
- Live/synthetic-owner qualification only with repo-owned session/authority gates and non-destructive scope.
- Android/Termux ARM64, Tailnet/Same-Origin, NATS connectivity, low-power responsiveness and performance budget metrics.
- Only exact current feature head with sanitized evidence; no release or merge until results reviewed.

## Risks and remaining coverage

P4 coverage has not been executed: new assertions and changed P0–P3 product code may fail or require refinement. The newly defined suite intentionally adds no snapshots without reviewed baselines. Expanded role/session-impact, scanner partial states, rule conflicts, recovery destructive workflows and device recovery require further scenario-specific fixtures; current P4 coverage does not claim exhaustive backend proof.

## Architecture

React/Vite PWA → Caddy → FastAPI `/api/lite/*` → NATS/JetStream → worker/agent/supervisor → sanitized events/heartbeats → FastAPI → UI. No frontend direct NATS/shell, secrets, unsafe write queue, or authorization bypass.
