# Trusted Lifecycle T3–T5 physical System evidence

This evidence was captured from the exact code-bearing candidate
`1c9ee06818fb396e56ccd86ecfd99bab85c32a4d` against base
`9bc53ce047c800be71cd76f1a37e79659af1ca4d` on 2026-11-27.

The run is a sanitized, isolated Android Chrome System-only qualification:

- Browser: Chrome 158.0.8127.42, Android package `com.android.chrome`, CDP
  protocol 1.3, standard Windows user, localhost-only CDP.
- Surface: System tab and System Manage, including safe disclosure,
  navigation, nested-scroll, theme, refresh-status and cancellation
  interactions; 13 interactions completed.
- Identity: manifest response, rendered page response and rendered page meta
  all reported the candidate SHA. The backend was an isolated candidate UI
  fixture; this is not production runtime proof.
- SQLite fixture: schema 42 → 69, migrations 43–69, integrity and quick
  checks `ok`, zero foreign-key errors, repeat application empty, and no
  production database mutation.
- Cleanup: candidate processes and temporary qualification material removed;
  synthetic session revoked; destructive actions were disabled.

The performance collection executed three repetitions across nine System
interactions and produced sanitized reports. It is execution evidence, not a
passing performance result: absolute target passes `0`, hard-gate passes `0`,
with eight `MIXED` and one `PLATFORM_DOMINATED` classifications and no
`APP_INCREMENTAL_COST` classification. The retained target/gate misses are
documented as a residual and are not relabeled as compliant.

## Files

- [`android-system-qualification.json`](android-system-qualification.json)
- [`trusted-lifecycle-before-manage.png`](trusted-lifecycle-before-manage.png)
- [`trusted-lifecycle-light.png`](trusted-lifecycle-light.png)
- [`trusted-lifecycle-dark.png`](trusted-lifecycle-dark.png)

The JSON is sanitized by the repository-owned qualifier. It contains no
published credential material, device serial, cookie, token or private key.
