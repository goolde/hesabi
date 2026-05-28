from datetime import datetime, timedelta
from typing import Optional

import sqlite3
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel


DB_NAME = "hesabi.db"
SECRET_KEY = "CHANGE_THIS_SECRET_KEY_TO_LONG_RANDOM_VALUE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

app = FastAPI(title="Hesabi API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        contact_type TEXT DEFAULT 'عميل',
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        contact_id INTEGER,
        tx_type TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'ر.س',
        tx_date TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(owner_id) REFERENCES users(id),
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    )
    """)

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


class RegisterIn(BaseModel):
    full_name: str
    phone: str
    password: str
    email: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ContactIn(BaseModel):
    name: str
    phone: Optional[str] = None
    contact_type: str = "عميل"
    notes: Optional[str] = None


class TransactionIn(BaseModel):
    contact_id: Optional[int] = None
    tx_type: str
    amount: float
    currency: str = "ر.س"
    tx_date: Optional[str] = None
    due_date: Optional[str] = None
    status: str = "pending"
    notes: Optional[str] = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="توكن غير صالح")

    conn = db()
    user = conn.execute(
        "SELECT id, full_name, phone, email, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")

    return dict(user)


@app.get("/")
def home():
    return {"message": "Hesabi API is running"}


@app.post("/auth/register", response_model=Token)
def register(data: RegisterIn):
    conn = db()

    exists = conn.execute(
        "SELECT id FROM users WHERE phone = ?",
        (data.phone,)
    ).fetchone()

    if exists:
        conn.close()
        raise HTTPException(status_code=400, detail="رقم الجوال مسجل مسبقاً")

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (full_name, phone, email, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data.full_name,
            data.phone,
            data.email,
            hash_password(data.password),
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    return Token(access_token=create_token(user_id))


@app.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    phone = form.username
    password = form.password

    conn = db()
    user = conn.execute(
        "SELECT * FROM users WHERE phone = ?",
        (phone,)
    ).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="رقم الجوال أو كلمة المرور غير صحيحة")

    return Token(access_token=create_token(user["id"]))


@app.get("/me")
def me(user=Depends(get_current_user)):
    return user


@app.post("/contacts")
def create_contact(data: ContactIn, user=Depends(get_current_user)):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO contacts (owner_id, name, phone, contact_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            data.name,
            data.phone,
            data.contact_type,
            data.notes,
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    contact_id = cur.lastrowid
    conn.close()
    return {"id": contact_id, "message": "تمت إضافة جهة الاتصال"}


@app.get("/contacts")
def list_contacts(user=Depends(get_current_user)):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM contacts WHERE owner_id = ? ORDER BY id DESC",
        (user["id"],)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, user=Depends(get_current_user)):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM contacts WHERE id = ? AND owner_id = ?",
        (contact_id, user["id"])
    )
    conn.commit()
    conn.close()
    return {"message": "تم الحذف"}


@app.post("/transactions")
def create_transaction(data: TransactionIn, user=Depends(get_current_user)):
    conn = db()
    cur = conn.cursor()

    tx_date = data.tx_date or datetime.utcnow().date().isoformat()

    cur.execute(
        """
        INSERT INTO transactions
        (owner_id, contact_id, tx_type, amount, currency, tx_date, due_date, status, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            data.contact_id,
            data.tx_type,
            data.amount,
            data.currency,
            tx_date,
            data.due_date,
            data.status,
            data.notes,
            datetime.utcnow().isoformat()
        )
    )

    conn.commit()
    tx_id = cur.lastrowid
    conn.close()

    return {"id": tx_id, "message": "تمت إضافة المعاملة"}


@app.get("/transactions")
def list_transactions(user=Depends(get_current_user)):
    conn = db()
    rows = conn.execute(
        """
        SELECT t.*, c.name AS contact_name
        FROM transactions t
        LEFT JOIN contacts c ON c.id = t.contact_id
        WHERE t.owner_id = ?
        ORDER BY t.id DESC
        """,
        (user["id"],)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, user=Depends(get_current_user)):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM transactions WHERE id = ? AND owner_id = ?",
        (tx_id, user["id"])
    )
    conn.commit()
    conn.close()
    return {"message": "تم الحذف"}


@app.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    conn = db()

    incoming = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE owner_id = ? AND tx_type = 'incoming'",
        (user["id"],)
    ).fetchone()["total"]

    outgoing = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE owner_id = ? AND tx_type = 'outgoing'",
        (user["id"],)
    ).fetchone()["total"]

    contacts_count = conn.execute(
        "SELECT COUNT(*) AS total FROM contacts WHERE owner_id = ?",
        (user["id"],)
    ).fetchone()["total"]

    tx_count = conn.execute(
        "SELECT COUNT(*) AS total FROM transactions WHERE owner_id = ?",
        (user["id"],)
    ).fetchone()["total"]

    conn.close()

    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "net": incoming - outgoing,
        "contacts_count": contacts_count,
        "transactions_count": tx_count
    }