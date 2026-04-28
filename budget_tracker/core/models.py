from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Optional

AccountType = Literal["checking", "savings", "credit", "cash", "wallet"]
CategoryKind = Literal["expense", "income"]
TxKind = Literal["expense", "income", "transfer"]
GoalKind = Literal["savings", "debt"]
SubCycle = Literal["weekly", "monthly", "yearly"]


@dataclass
class Account:
    id: Optional[int]
    name: str
    type: AccountType
    opening_balance: int = 0
    archived: bool = False
    created_at: Optional[str] = None


@dataclass
class Category:
    id: Optional[int]
    name: str
    kind: CategoryKind
    color: str
    icon: str
    parent_id: Optional[int] = None        # None = top-level
    archived: bool = False


@dataclass
class Transaction:
    id: Optional[int]
    occurred_on: date
    kind: TxKind
    amount: int  # minor units
    account_id: int
    transfer_account_id: Optional[int] = None
    category_id: Optional[int] = None
    note: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Budget:
    id: Optional[int]
    category_id: int
    amount: int                    # monthly limit in minor units
    effective_from: str            # YYYY-MM


@dataclass
class Goal:
    id: Optional[int]
    name: str
    kind: GoalKind
    target_amount: int
    current_amount: int = 0
    deadline: Optional[date] = None
    archived: bool = False
    created_at: Optional[str] = None


@dataclass
class Subscription:
    id: Optional[int]
    name: str
    amount: int
    cycle: SubCycle
    next_billing_date: date
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    active: bool = True
