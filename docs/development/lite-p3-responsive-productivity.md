# P3 — Responsive productivity and premium interaction

**Status: COMMITTED CODE; UNVALIDATED.** No tests, builds, CI monitoring or device/runtime qualification were performed.

## Objective

Add light, accessible desktop productivity without compromising Pocket Lab's existing mobile dock, sidebar, app workspace switcher, portal/sheet system or battery-sensitive performance design.

## Added

- A section-only quick navigation surface, launched via an explicit **Find** control on the main shell.
- Ctrl+K / Cmd+K shortcut for non-editable contexts only; repeat, composition, modified combinations, form entry and existing modal surfaces are respected.
- Type-to-filter existing canonical `NAV_ITEMS`; Enter activates first matching section; native buttons allow pointer/keyboard navigation.
- Reuses `LiteSheet` and existing `commitScreenNavigation` for Escape, focus trap/return, URL normalization, prefetch and view transitions.
- Uses responsive width, safe scrolling, 44px controls, focus indicators and reduced-motion styles.
- No new UI framework, device commands, backend API, persistence, secrets or client-side authority.

## Preserved

- Existing 7-tab desktop rail / mobile dock / More navigation, app-workspace embedded switcher and route semantics.
- Current sheet portal and keyboard ownership, reduced-motion and performance-mode behavior.
- Frontend never connects to NATS or executes shell commands.
- Actions remain in existing screen-specific Manage flows; quick navigation contains **no action commands**.

## Deferred and not claimed

A universal action command palette, role/capability-backed commands, user-configurable navigation, persistent compact-density mode, per-screen deep-link overlays, complex gesture effects and screen-wide container-query refactors are out of P3 scope. These would need additional policy and accessibility design. P4 qualification is not performed.

## Future validation tasks — defined, not executed

```bash
task lite:ui:p3:unit
task lite:ui:p3:regression
npm run test:mock-regression
npm run test:a11y:states
npm run test:perf
npm run build:budget
task lite:check
```

Inspect narrow phones, mobile soft-keyboard overlays, focus restoration, pre-existing dialog precedence, desktop keyboard handling, accessibility and performance before merge.
