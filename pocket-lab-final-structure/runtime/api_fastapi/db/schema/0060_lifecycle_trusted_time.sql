-- Durable trusted time high-water, independent of wall-clock observation stamps.
CREATE TABLE lite_release_trusted_time (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    trusted_at TEXT NOT NULL
);
