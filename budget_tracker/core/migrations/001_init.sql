-- 001_init.sql
-- Initial schema for budget tracker. All amounts are stored as INTEGER
-- minor units (paise / cents) to avoid floating-point errors.

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    type            TEXT    NOT NULL CHECK (type IN ('checking','savings','credit','cash','wallet')),
    opening_balance INTEGER NOT NULL DEFAULT 0,
    archived        INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS categories (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL,
    kind     TEXT    NOT NULL CHECK (kind IN ('expense','income')),
    color    TEXT    NOT NULL,
    icon     TEXT    NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
);

CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_on         TEXT    NOT NULL,
    kind                TEXT    NOT NULL CHECK (kind IN ('expense','income','transfer')),
    amount              INTEGER NOT NULL CHECK (amount >= 0),
    account_id          INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    transfer_account_id INTEGER          REFERENCES accounts(id) ON DELETE RESTRICT,
    category_id         INTEGER          REFERENCES categories(id) ON DELETE SET NULL,
    note                TEXT,
    created_at          TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_tx_date     ON transactions(occurred_on);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_tx_account  ON transactions(account_id);

CREATE TABLE IF NOT EXISTS budgets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id    INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    amount         INTEGER NOT NULL CHECK (amount >= 0),
    effective_from TEXT    NOT NULL,                     -- YYYY-MM
    UNIQUE(category_id, effective_from)
);

CREATE TABLE IF NOT EXISTS goals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    kind           TEXT    NOT NULL CHECK (kind IN ('savings','debt')),
    target_amount  INTEGER NOT NULL CHECK (target_amount > 0),
    current_amount INTEGER NOT NULL DEFAULT 0,
    deadline       TEXT,
    created_at     TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    archived       INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL,
    amount            INTEGER NOT NULL CHECK (amount >= 0),
    cycle             TEXT    NOT NULL CHECK (cycle IN ('weekly','monthly','yearly')),
    next_billing_date TEXT    NOT NULL,
    category_id       INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    account_id        INTEGER REFERENCES accounts(id)   ON DELETE SET NULL,
    active            INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);
