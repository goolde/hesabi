from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    phone: str = Field(index=True, unique=True)
    email: Optional[str] = Field(default=None, index=True)
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(index=True, foreign_key="user.id")
    name: str = Field(index=True)
    phone: Optional[str] = None
    contact_type: str = "عميل"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    owner_id: int = Field(
        index=True,
        foreign_key="user.id"
    )

    contact_id: Optional[int] = Field(
        default=None,
        foreign_key="contact.id"
    )

    tx_type: str
    amount: float
    currency: str = "ر.س"

    tx_date: date = Field(
        default_factory=date.today
    )

    due_date: Optional[date] = None

    status: str = "pending"

    notes: Optional[str] = None

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class RegisterIn(SQLModel):
    full_name: str
    phone: str
    password: str
    email: Optional[str] = None


class ContactIn(SQLModel):
    name: str
    phone: Optional[str] = None
    contact_type: str = "عميل"
    notes: Optional[str] = None


class TransactionIn(SQLModel):
    contact_id: Optional[int] = None
    tx_type: str
    amount: float
    currency: str = "ر.س"

    tx_date: Optional[date] = None
    due_date: Optional[date] = None

    status: str = "pending"
    notes: Optional[str] = None