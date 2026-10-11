# Sections 4–6 — shared controls, Home, Apps

Status: **PATCH-PROVIDED / UNVALIDATED**. This follow-up is additive and intentionally does not claim the entire universal app platform or durable history is complete.

- Shared `LiteField` and `LiteConfirmationSummary` are accessible presentation primitives; FastAPI owns validation, identity, permissions, confirmations and execution.
- Home prioritizes already-projected danger/review areas deterministically. This does **not** invent change-since-last-visit events or personalization.
- Apps search and stable alphabetic presentation work with generic catalog objects without forcing PhotoPrism to be featured. Existing PhotoPrism-specific lifecycle operations are retained. Universal runtime adapter support requires separate backend-owned implementation and proof with a second app.

Tests added but **not executed**: `src/lite/components/LiteSafeForms.test.jsx`, `src/lite/catalog/catalogPresentation.test.js`, `src/lite/homeAttentionPriority.test.js`. Future: `npm run test -- src/lite/components/LiteSafeForms.test.jsx src/lite/catalog/catalogPresentation.test.js src/lite/homeAttentionPriority.test.js`; `task lite:check`.

Production completion **missing/unvalidated**: migration of screen-specific forms to shared primitives; full modal stacking and form validation; audit-backed Home change history; universal multi-app adapter and action lifecycle; desktop/mobile/Android visual qualification. Maintain PR draft status until separately reviewed.
