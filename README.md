# Budget Tracker

A modern, locally-stored personal budget tracker built with PySide 6.

## Features (v1)

- Transactions, accounts, categories, search/filter
- Monthly budgets per category with progress
- Savings goals & debt payoff tracker
- Subscription audit
- Modern themed UI (dark + light), sidebar navigation
- Local SQLite storage, fully offline

## Setup

Requires Python **3.13+**.

```bash
# Create venv
py -3.13 -m venv .venv
. .venv/Scripts/activate    # PowerShell: .venv\Scripts\Activate.ps1

# Install runtime + dev dependencies
pip install -r requirements-dev.txt
```

## Run

```bash
python -m budget_tracker
```

## Test

```bash
pytest
```

## Project Layout

```
budget_tracker/
├── main.py                # entry point
├── config.py              # paths & constants
├── core/                  # db, models, money, repositories
├── services/              # budget/goal/summary/settings logic
└── ui/                    # views, widgets, dialogs, theme
tests/                     # pytest suite
```
