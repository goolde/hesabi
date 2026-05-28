#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════╗
║         حسابي - تطبيق محاسبة            ║
║      بلغة Python + Flask + SQLite        ║
╚══════════════════════════════════════════╝

كيف تشغّله:
  pip install flask openpyxl reportlab
  python3 hesabi.py
ثم افتح المتصفح على:  http://localhost:5000
"""

# ============================================================
# 1) الاستيرادات — كل مكتبة نحتاجها
# ============================================================
import sqlite3          # قاعدة البيانات المحلية
import json             # تحويل البيانات لـ JSON
import os               # التعامل مع الملفات
import hashlib          # تشفير كلمات المرور
import secrets          # توليد رموز عشوائية
import io               # للملفات في الذاكرة
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, request, jsonify, session,
    redirect, url_for, send_file, g
)

# Excel
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment,
    Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

# ============================================================
# 2) إعداد التطبيق وقاعدة البيانات
# ============================================================
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # مفتاح تشفير الجلسة

# مسار قاعدة البيانات
DB_PATH = "hesabi.db"

def get_db():
    """الاتصال بقاعدة البيانات — يُنشئها إن لم تكن موجودة"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row  # نتيجة تعمل كـ dict
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    """أغلق الاتصال بعد كل طلب"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """إنشاء الجداول عند أول تشغيل"""
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        -- جدول المستخدمين
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL,
            phone     TEXT    UNIQUE NOT NULL,
            email     TEXT,
            business  TEXT,
            password  TEXT    NOT NULL,
            created   TEXT    DEFAULT (datetime('now'))
        );

        -- جدول جهات الاتصال
        CREATE TABLE IF NOT EXISTS contacts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            name         TEXT    NOT NULL,
            phone        TEXT,
            email        TEXT,
            type         TEXT    DEFAULT 'عميل',
            notes        TEXT,
            lat          REAL,
            lng          REAL,
            location_text TEXT,
            created      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- جدول المعاملات
        CREATE TABLE IF NOT EXISTS transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            contact_id   INTEGER NOT NULL,
            contact_name TEXT,
            amount       REAL    NOT NULL,
            currency     TEXT    DEFAULT 'ر.س',
            type         TEXT    NOT NULL,   -- incoming / outgoing
            date         TEXT,
            due_date     TEXT,
            notes        TEXT,
            status       TEXT    DEFAULT 'pending',
            reminder     TEXT    DEFAULT 'none',
            created      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id)    REFERENCES users(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        );

        -- جدول الإشعارات
        CREATE TABLE IF NOT EXISTS notifications (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title   TEXT,
            body    TEXT,
            icon    TEXT    DEFAULT '📌',
            is_read INTEGER DEFAULT 0,
            created TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- جدول الإعدادات
        CREATE TABLE IF NOT EXISTS settings (
            user_id  INTEGER PRIMARY KEY,
            data     TEXT    DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    db.commit()
    db.close()
    print("✅ قاعدة البيانات جاهزة")

# ============================================================
# 3) دوال مساعدة
# ============================================================

def hash_password(password: str) -> str:
    """تشفير كلمة المرور بـ SHA-256"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def login_required(f):
    """Decorator — يتحقق من تسجيل الدخول قبل كل endpoint"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجّل الدخول', 'redirect': '/'}), 401
        return f(*args, **kwargs)
    return decorated

def get_user_settings(user_id: int) -> dict:
    """جلب إعدادات المستخدم"""
    db = get_db()
    row = db.execute(
        "SELECT data FROM settings WHERE user_id=?", (user_id,)
    ).fetchone()
    if row:
        try:
            return json.loads(row['data'])
        except:
            return {}
    return {}

def save_user_settings(user_id: int, data: dict):
    """حفظ إعدادات المستخدم"""
    db = get_db()
    db.execute("""
        INSERT INTO settings (user_id, data) VALUES (?,?)
        ON CONFLICT(user_id) DO UPDATE SET data=excluded.data
    """, (user_id, json.dumps(data, ensure_ascii=False)))
    db.commit()

def add_notification(user_id: int, title: str, body: str, icon: str = '📌'):
    """إضافة إشعار"""
    db = get_db()
    db.execute(
        "INSERT INTO notifications (user_id,title,body,icon) VALUES (?,?,?,?)",
        (user_id, title, body, icon)
    )
    db.commit()

def get_contact_balance(user_id: int, contact_id: int) -> dict:
    """حساب رصيد جهة معينة"""
    db = get_db()
    rows = db.execute("""
        SELECT type, SUM(amount) as total
        FROM transactions
        WHERE user_id=? AND contact_id=? AND status != 'settled'
        GROUP BY type
    """, (user_id, contact_id)).fetchall()

    for_me = 0.0
    on_me  = 0.0
    for row in rows:
        if row['type'] == 'incoming':
            for_me = row['total'] or 0
        else:
            on_me = row['total'] or 0

    return {
        'for_me': for_me,
        'on_me':  on_me,
        'net':    for_me - on_me
    }

# ============================================================
# 4) الصفحة الرئيسية — HTML كامل
# ============================================================
HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>حسابي 💰</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Cairo',sans-serif;background:#0a0f1e;color:#e2e8f0;min-height:100vh;}
.container{max-width:960px;margin:0 auto;padding:20px 16px 80px;}
/* HEADER */
.header{background:#111827;border-bottom:1px solid rgba(99,179,237,0.15);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;}
.logo{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:900;color:#f6c90e;}
.logo-icon{width:38px;height:38px;background:linear-gradient(135deg,#f6c90e,#d4a017);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;}
.header-btns{display:flex;gap:8px;}
/* CARDS */
.card{background:#111827;border:1px solid rgba(99,179,237,0.12);border-radius:16px;padding:20px;margin-bottom:16px;}
.balance-card{background:linear-gradient(135deg,#1a2340,#0f1a30);border:1px solid rgba(99,179,237,0.2);border-radius:20px;padding:24px;margin-bottom:20px;}
.balance-amount{font-size:36px;font-weight:900;}
.balance-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px;}
.bal-box{background:rgba(255,255,255,0.05);border-radius:12px;padding:12px;}
.bal-box-label{font-size:11px;color:#a0aec0;margin-bottom:4px;}
.bal-box-val{font-size:20px;font-weight:800;}
/* GRID */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
@media(max-width:600px){.grid-2{grid-template-columns:1fr;}.grid-3{grid-template-columns:1fr 1fr;}}
/* STATS */
.stat-card{background:#111827;border:1px solid rgba(99,179,237,0.12);border-radius:12px;padding:16px;text-align:center;cursor:pointer;transition:all 0.2s;}
.stat-card:hover{border-color:rgba(99,179,237,0.3);transform:translateY(-2px);}
.stat-icon{font-size:28px;margin-bottom:8px;}
.stat-val{font-size:22px;font-weight:800;}
.stat-label{font-size:11px;color:#a0aec0;margin-top:4px;}
/* QUICK ACTIONS */
.quick-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px;}
@media(max-width:480px){.quick-grid{grid-template-columns:repeat(2,1fr);}}
.qa-btn{background:#111827;border:1px solid rgba(99,179,237,0.12);border-radius:12px;padding:16px 8px;display:flex;flex-direction:column;align-items:center;gap:6px;cursor:pointer;transition:all 0.2s;text-decoration:none;}
.qa-btn:hover{border-color:#f6c90e;transform:translateY(-2px);}
.qa-icon{font-size:26px;}
.qa-label{font-size:12px;color:#a0aec0;font-weight:600;}
/* TABLE */
.table-wrap{overflow-x:auto;border-radius:12px;border:1px solid rgba(99,179,237,0.12);}
table{width:100%;border-collapse:collapse;min-width:500px;}
th{background:#1a2340;padding:12px 14px;font-size:12px;color:#a0aec0;font-weight:700;text-align:right;}
td{padding:11px 14px;font-size:13px;border-bottom:1px solid rgba(99,179,237,0.07);}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(255,255,255,0.02);}
/* FORMS */
.form-group{margin-bottom:14px;}
.form-group label{display:block;font-size:12px;color:#a0aec0;margin-bottom:7px;font-weight:600;}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:11px 14px;background:#151d35;border:1px solid rgba(99,179,237,0.15);border-radius:8px;color:#e2e8f0;font-size:14px;font-family:'Cairo',sans-serif;outline:none;transition:all 0.2s;}
.form-group input:focus,.form-group select:focus{border-color:#f6c90e;box-shadow:0 0 0 3px rgba(246,201,14,0.1);}
.form-group select option{background:#151d35;}
/* BUTTONS */
.btn{padding:11px 20px;border:none;border-radius:10px;font-size:14px;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;transition:all 0.2s;display:inline-flex;align-items:center;gap:6px;}
.btn-gold{background:linear-gradient(135deg,#f6c90e,#d4a017);color:#000;}
.btn-gold:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(246,201,14,0.3);}
.btn-outline{background:transparent;border:1px solid rgba(99,179,237,0.3);color:#a0aec0;}
.btn-outline:hover{border-color:#f6c90e;color:#f6c90e;}
.btn-green{background:rgba(72,187,120,0.15);color:#48bb78;border:1px solid rgba(72,187,120,0.3);}
.btn-red{background:rgba(252,129,129,0.15);color:#fc8181;border:1px solid rgba(252,129,129,0.3);}
.btn-blue{background:rgba(99,179,237,0.15);color:#63b3ed;border:1px solid rgba(99,179,237,0.3);}
.btn-sm{padding:7px 14px;font-size:12px;}
/* TABS */
.tabs{display:flex;background:#151d35;border-radius:12px;padding:4px;margin-bottom:20px;gap:4px;}
.tab{flex:1;padding:10px;text-align:center;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;transition:all 0.2s;color:#718096;border:none;background:none;font-family:'Cairo',sans-serif;}
.tab.active{background:#f6c90e;color:#000;}
/* BADGES */
.badge{padding:3px 10px;border-radius:8px;font-size:11px;font-weight:700;display:inline-block;}
.badge-green{background:rgba(72,187,120,0.15);color:#48bb78;}
.badge-red{background:rgba(252,129,129,0.15);color:#fc8181;}
.badge-blue{background:rgba(99,179,237,0.15);color:#63b3ed;}
.badge-gold{background:rgba(246,201,14,0.15);color:#f6c90e;}
.badge-orange{background:rgba(246,173,85,0.15);color:#f6ad55;}
/* MODAL */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:200;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(4px);}
.modal-bg.open{display:flex;}
.modal{background:#111827;border:1px solid rgba(99,179,237,0.2);border-radius:20px;width:100%;max-width:480px;max-height:90vh;overflow-y:auto;padding:24px;animation:modalIn 0.2s ease;}
@keyframes modalIn{from{transform:scale(0.95);opacity:0}to{transform:scale(1);opacity:1}}
.modal-title{font-size:18px;font-weight:800;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;}
.modal-close{cursor:pointer;color:#718096;font-size:22px;line-height:1;}
/* ALERTS */
.alert{padding:12px 16px;border-radius:10px;font-size:13px;margin-bottom:14px;display:none;}
.alert.show{display:block;}
.alert-error{background:rgba(252,129,129,0.15);border:1px solid rgba(252,129,129,0.3);color:#fc8181;}
.alert-success{background:rgba(72,187,120,0.15);border:1px solid rgba(72,187,120,0.3);color:#48bb78;}
/* LOGIN */
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;}
.login-box{background:#111827;border:1px solid rgba(99,179,237,0.2);border-radius:24px;padding:36px 28px;width:100%;max-width:400px;}
.login-logo{text-align:center;margin-bottom:28px;}
.login-logo .icon{width:72px;height:72px;background:linear-gradient(135deg,#f6c90e,#d4a017);border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:34px;margin:0 auto 14px;box-shadow:0 0 30px rgba(246,201,14,0.3);}
.login-logo h1{font-size:26px;font-weight:900;color:#f6c90e;}
/* SECTION HEADER */
.section-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
.section-title{font-size:16px;font-weight:700;}
/* COLORS */
.green{color:#48bb78;} .red{color:#fc8181;} .gold{color:#f6c90e;} .blue{color:#63b3ed;}
/* FILTER CHIPS */
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;}
.chip{padding:6px 14px;border-radius:20px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid rgba(99,179,237,0.2);background:#111827;color:#a0aec0;font-family:'Cairo',sans-serif;transition:all 0.2s;}
.chip.active{background:#f6c90e;color:#000;border-color:#f6c90e;}
/* EMPTY */
.empty{text-align:center;padding:48px 20px;color:#718096;}
.empty-icon{font-size:48px;margin-bottom:12px;opacity:0.5;}
/* SETTINGS ROWS */
.settings-row{display:flex;align-items:center;gap:14px;padding:14px 16px;cursor:pointer;border-bottom:1px solid rgba(99,179,237,0.07);font-size:14px;transition:background 0.15s;}
.settings-row:last-child{border-bottom:none;}
.settings-row:hover{background:rgba(255,255,255,0.03);}
/* MAP */
#mainMap{z-index:1;}
.leaflet-container{background:#0d1117!important;font-family:'Cairo',sans-serif!important;}
.leaflet-tile{filter:brightness(0.8) saturate(1.2);}
.map-popup{font-family:'Cairo',sans-serif;direction:rtl;min-width:160px;}
.map-popup-name{font-size:14px;font-weight:800;margin-bottom:4px;}
.map-popup-bal{font-size:13px;font-weight:700;margin-bottom:8px;}
.leaflet-popup-content-wrapper{background:#1f2937!important;border:1px solid rgba(99,179,237,0.3)!important;border-radius:12px!important;color:#e2e8f0!important;}
.leaflet-popup-tip{background:#1f2937!important;}
.search-input{flex:1;padding:10px 14px;background:#111827;border:1px solid rgba(99,179,237,0.15);border-radius:10px;color:#e2e8f0;font-size:14px;font-family:'Cairo',sans-serif;outline:none;}
.search-input:focus{border-color:#f6c90e;}
/* TOAST */
#toast{position:fixed;top:80px;left:50%;transform:translateX(-50%) translateY(-20px);background:#1f2937;border:1px solid rgba(99,179,237,0.3);border-radius:12px;padding:12px 20px;font-size:14px;font-weight:600;z-index:999;opacity:0;transition:all 0.3s;pointer-events:none;white-space:nowrap;}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0);}
#toast.success{border-color:#48bb78;color:#48bb78;}
#toast.error{border-color:#fc8181;color:#fc8181;}
/* NAV */
.nav-pills{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;}
.nav-pill{padding:8px 18px;border-radius:20px;font-size:13px;font-weight:700;cursor:pointer;border:1px solid rgba(99,179,237,0.2);background:#111827;color:#a0aec0;font-family:'Cairo',sans-serif;transition:all 0.2s;text-decoration:none;}
.nav-pill.active,.nav-pill:hover{background:#f6c90e;color:#000;border-color:#f6c90e;}
</style>
</head>
<body>

<div id="toast"></div>

<!-- =================== LOGIN PAGE =================== -->
<div id="loginPage" style="display:none">
  <div class="login-wrap">
    <div class="login-box">
      <div class="login-logo">
        <div class="icon">💰</div>
        <h1>حسابي</h1>
        <p style="color:#a0aec0;font-size:13px;margin-top:4px;">إدارة مالية ذكية بلغة Python</p>
      </div>

      <div class="tabs">
        <button class="tab active" onclick="switchAuthTab('login')">دخول</button>
        <button class="tab" onclick="switchAuthTab('register')">حساب جديد</button>
      </div>

      <div id="alertAuth" class="alert"></div>

      <!-- Login Form -->
      <div id="loginForm">
        <div class="form-group"><label>رقم الجوال</label>
          <input id="loginPhone" type="tel" placeholder="05xxxxxxxx">
        </div>
        <div class="form-group"><label>كلمة المرور</label>
          <input id="loginPass" type="password" placeholder="••••••••">
        </div>
        <button class="btn btn-gold" style="width:100%;justify-content:center;margin-top:8px" onclick="doLogin()">
          🚀 دخول
        </button>
      </div>

      <!-- Register Form -->
      <div id="registerForm" style="display:none">
        <div class="form-group"><label>الاسم</label>
          <input id="regName" type="text" placeholder="محمد أحمد">
        </div>
        <div class="form-group"><label>رقم الجوال</label>
          <input id="regPhone" type="tel" placeholder="05xxxxxxxx">
        </div>
        <div class="form-group"><label>كلمة المرور</label>
          <input id="regPass" type="password" placeholder="••••••••">
        </div>
        <button class="btn btn-gold" style="width:100%;justify-content:center;margin-top:8px" onclick="doRegister()">
          ✨ إنشاء الحساب
        </button>
      </div>
    </div>
  </div>
</div>

<!-- =================== MAIN APP =================== -->
<div id="mainApp" style="display:none">

  <!-- HEADER -->
  <div class="header">
    <div class="logo">
      <div class="logo-icon">💰</div>
      حسابي
    </div>
    <div class="header-btns">
      <button class="btn btn-outline btn-sm" onclick="showPage('notifications')">🔔</button>
      <button class="btn btn-outline btn-sm" onclick="doLogout()">خروج 🚪</button>
    </div>
  </div>

  <!-- NAV PILLS -->
  <div class="container" style="padding-bottom:0;padding-top:16px;">
    <div class="nav-pills">
      <a class="nav-pill active" onclick="showPage('home')" id="pill-home">🏠 الرئيسية</a>
      <a class="nav-pill" onclick="showPage('contacts')" id="pill-contacts">👥 الجهات</a>
      <a class="nav-pill" onclick="showPage('transactions')" id="pill-transactions">📋 المعاملات</a>
      <a class="nav-pill" onclick="showPage('statements')" id="pill-statements">📑 الكشوف</a>
      <a class="nav-pill" onclick="showPage('reports')" id="pill-reports">📊 التقارير</a>
      <a class="nav-pill" onclick="showPage('map')" id="pill-map">🗺️ الخريطة</a>
      <a class="nav-pill" onclick="showPage('settings')" id="pill-settings">⚙️ الإعدادات</a>
    </div>
    <!-- Search Bar -->
    <div style="display:flex;gap:10px;margin-bottom:12px;">
      <input class="search-input" id="globalSearch" placeholder="🔍 ابحث عن جهة أو معاملة..." oninput="globalSearchFn()" style="flex:1;">
    </div>
    <div id="searchResults" style="display:none;background:#1f2937;border:1px solid rgba(99,179,237,0.2);border-radius:12px;padding:12px;margin-bottom:12px;"></div>
  </div>

  <div class="container">

    <!-- ===== HOME PAGE ===== -->
    <div id="page-home">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <div>
          <div style="font-size:13px;color:#a0aec0;">مرحباً 👋</div>
          <div style="font-size:20px;font-weight:800;" id="welcomeName">—</div>
        </div>
        <div style="font-size:12px;color:#a0aec0;" id="todayDate"></div>
      </div>

      <div class="balance-card">
        <div style="font-size:13px;color:#a0aec0;margin-bottom:8px;">الرصيد الإجمالي</div>
        <div class="balance-amount" id="netBalance">0 ر.س</div>
        <div class="balance-grid">
          <div class="bal-box">
            <div class="bal-box-label">لي (مستحق)</div>
            <div class="bal-box-val green" id="totalFor">0</div>
          </div>
          <div class="bal-box">
            <div class="bal-box-label">علي (مديونية)</div>
            <div class="bal-box-val red" id="totalOn">0</div>
          </div>
        </div>
      </div>

      <div class="quick-grid">
        <a class="qa-btn" onclick="openAddTx('incoming')">
          <div class="qa-icon">📥</div><div class="qa-label">لي</div>
        </a>
        <a class="qa-btn" onclick="openAddTx('outgoing')">
          <div class="qa-icon">📤</div><div class="qa-label">علي</div>
        </a>
        <a class="qa-btn" onclick="showPage('contacts');setTimeout(openAddContact,100)">
          <div class="qa-icon">👤</div><div class="qa-label">جهة جديدة</div>
        </a>
        <a class="qa-btn" onclick="showPage('statements')">
          <div class="qa-icon">📑</div><div class="qa-label">الكشوف</div>
        </a>
      </div>

      <div class="grid-2" style="margin-bottom:20px;" id="statsGrid"></div>

      <div class="section-hdr">
        <div class="section-title">آخر المعاملات</div>
        <button class="btn btn-outline btn-sm" onclick="showPage('transactions')">عرض الكل</button>
      </div>
      <div class="card" id="recentTx"></div>
    </div>

    <!-- ===== CONTACTS PAGE ===== -->
    <div id="page-contacts" style="display:none">
      <div class="section-hdr">
        <div class="section-title">👥 جهات الاتصال</div>
        <button class="btn btn-gold btn-sm" onclick="openAddContact()">+ إضافة</button>
      </div>
      <div class="search-bar">
        <input class="search-input" id="contactSearch" placeholder="بحث بالاسم أو الجوال..." oninput="filterContacts()">
      </div>
      <div class="chips" id="contactTypeChips">
        <button class="chip active" onclick="setContactFilter(this,'all')">الكل</button>
        <button class="chip" onclick="setContactFilter(this,'عميل')">👤 عملاء</button>
        <button class="chip" onclick="setContactFilter(this,'مورد')">🏭 موردون</button>
        <button class="chip" onclick="setContactFilter(this,'مندوب')">🚗 مندوبون</button>
        <button class="chip" onclick="setContactFilter(this,'دائن')">💸 دائنون</button>
        <button class="chip" onclick="setContactFilter(this,'مدين')">🤝 مدينون</button>
      </div>
      <div id="contactsList"></div>
    </div>

    <!-- ===== TRANSACTIONS PAGE ===== -->
    <div id="page-transactions" style="display:none">
      <div class="section-hdr">
        <div class="section-title">📋 المعاملات</div>
        <button class="btn btn-gold btn-sm" onclick="openAddTx()">+ إضافة</button>
      </div>
      <div class="search-bar">
        <input class="search-input" id="txSearch" placeholder="بحث..." oninput="filterTx()">
      </div>
      <div class="chips">
        <button class="chip active" onclick="setTxFilter(this,'all')">الكل</button>
        <button class="chip" onclick="setTxFilter(this,'incoming')">📥 لي</button>
        <button class="chip" onclick="setTxFilter(this,'outgoing')">📤 علي</button>
        <button class="chip" onclick="setTxFilter(this,'settled')">✅ مسوّاة</button>
      </div>
      <div id="txList"></div>
    </div>

    <!-- ===== STATEMENTS PAGE ===== -->
    <div id="page-statements" style="display:none">
      <div class="section-title" style="margin-bottom:16px;">📑 كشوف الحسابات</div>

      <div class="card">
        <div class="grid-2" style="margin-bottom:12px;">
          <div class="form-group" style="margin:0">
            <label>من تاريخ</label>
            <input type="date" id="stFrom">
          </div>
          <div class="form-group" style="margin:0">
            <label>إلى تاريخ</label>
            <input type="date" id="stTo">
          </div>
        </div>
        <div class="form-group">
          <label>الجهة</label>
          <select id="stContact">
            <option value="">الكل</option>
          </select>
        </div>
        <div class="form-group">
          <label>نوع المعاملة</label>
          <select id="stType">
            <option value="">الكل</option>
            <option value="incoming">📥 لي فقط</option>
            <option value="outgoing">📤 علي فقط</option>
          </select>
        </div>
        <div class="form-group">
          <label>الحالة</label>
          <select id="stStatus">
            <option value="">الكل</option>
            <option value="pending">🕐 معلقة</option>
            <option value="settled">✅ مسوّاة</option>
          </select>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <button class="btn btn-gold" onclick="generateStatement()">🔄 توليد الكشف</button>
          <button class="btn btn-outline" onclick="resetStatement()">↺ إعادة تعيين</button>
        </div>
      </div>

      <div class="tabs" id="stTabs">
        <button class="tab active" onclick="switchStTab(this,'total')">إجمالي</button>
        <button class="tab" onclick="switchStTab(this,'analytic')">تحليلي</button>
        <button class="tab" onclick="switchStTab(this,'person')">بالشخص</button>
      </div>

      <div id="stSummary" style="display:none" class="grid-2" style="margin-bottom:16px;"></div>
      <div id="stOutput"></div>

      <div id="stExportBtns" style="display:none;margin-top:16px;">
        <div class="grid-2" style="gap:10px;">
          <button class="btn btn-red" onclick="exportPDF()">📄 تصدير PDF</button>
          <button class="btn btn-green" onclick="exportExcel()">📊 تصدير Excel</button>
        </div>
      </div>
    </div>

    <!-- ===== REPORTS PAGE ===== -->
    <div id="page-reports" style="display:none">
      <div class="section-title" style="margin-bottom:16px;">📊 التقارير</div>
      <div class="grid-2" id="reportSummary" style="margin-bottom:20px;"></div>
      <div class="card" style="margin-bottom:16px;">
        <div class="section-title" style="margin-bottom:16px;">أعلى الأرصدة</div>
        <div id="topBalances"></div>
      </div>
      <div class="card">
        <div class="section-title" style="margin-bottom:16px;">توزيع حسب النوع</div>
        <div id="typeBreakdown"></div>
      </div>
    </div>

    <!-- ===== NOTIFICATIONS PAGE ===== -->
    <div id="page-notifications" style="display:none">
      <div class="section-hdr">
        <div class="section-title">🔔 الإشعارات</div>
        <button class="btn btn-outline btn-sm" onclick="markAllRead()">قراءة الكل</button>
      </div>
      <div id="notifList"></div>
    </div>

    <!-- ===== MAP PAGE ===== -->
    <div id="page-map" style="display:none">
      <div class="section-title" style="margin-bottom:16px;">🗺️ خريطة الجهات</div>
      <div style="background:#111827;border:1px solid rgba(99,179,237,0.15);border-radius:12px;overflow:hidden;margin-bottom:16px;">
        <div id="mainMap" style="height:450px;width:100%;"></div>
      </div>
      <div class="chips" id="mapFilterChips">
        <button class="chip active" onclick="filterMap(this,'all')">الكل</button>
        <button class="chip" onclick="filterMap(this,'عميل')">👤 عملاء</button>
        <button class="chip" onclick="filterMap(this,'مورد')">🏭 موردون</button>
        <button class="chip" onclick="filterMap(this,'مندوب')">🚗 مندوبون</button>
        <button class="chip" onclick="filterMap(this,'دائن')">💸 دائنون</button>
        <button class="chip" onclick="filterMap(this,'مدين')">🤝 مدينون</button>
      </div>
      <div class="grid-2" id="mapStats" style="margin-top:12px;"></div>
    </div>

    <!-- ===== SETTINGS PAGE ===== -->
    <div id="page-settings" style="display:none">
      <div class="section-title" style="margin-bottom:20px;">⚙️ الإعدادات</div>

      <!-- Profile Card -->
      <div class="card" style="display:flex;align-items:center;gap:16px;margin-bottom:20px;">
        <div style="width:64px;height:64px;background:linear-gradient(135deg,#3182ce,#b794f4);border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:800;" id="settingsAvatar">م</div>
        <div style="flex:1;">
          <div style="font-size:18px;font-weight:800;" id="settingsName">—</div>
          <div style="font-size:13px;color:#a0aec0;margin-top:4px;" id="settingsPhone">—</div>
        </div>
        <button class="btn btn-gold btn-sm" onclick="openEditProfile()">✏️ تعديل</button>
      </div>

      <!-- Settings Items -->
      <div class="card" style="padding:0;overflow:hidden;margin-bottom:16px;">
        <div style="padding:12px 16px;font-size:11px;color:#a0aec0;font-weight:700;background:#1a2340;letter-spacing:1px;">الحساب</div>
        <div class="settings-row" onclick="openEditProfile()">
          <span>👤</span><div style="flex:1"><div style="font-weight:600;">تعديل البيانات الشخصية</div><div style="font-size:12px;color:#a0aec0;">الاسم، الجوال</div></div><span style="color:#718096;">›</span>
        </div>
        <div class="settings-row" onclick="openChangePwd()">
          <span>🔐</span><div style="flex:1"><div style="font-weight:600;">تغيير كلمة المرور</div><div style="font-size:12px;color:#a0aec0;">تحديث الأمان</div></div><span style="color:#718096;">›</span>
        </div>
      </div>

      <div class="card" style="padding:0;overflow:hidden;margin-bottom:16px;">
        <div style="padding:12px 16px;font-size:11px;color:#a0aec0;font-weight:700;background:#1a2340;letter-spacing:1px;">المسميات</div>
        <div class="settings-row">
          <span>🏷️</span>
          <div style="flex:1"><div style="font-weight:600;">مسمى "لي"</div></div>
          <input type="text" id="termIncoming" value="لي" style="width:100px;padding:6px 10px;background:#151d35;border:1px solid rgba(99,179,237,0.2);border-radius:8px;color:#e2e8f0;font-family:'Cairo',sans-serif;font-size:13px;text-align:center;">
        </div>
        <div class="settings-row">
          <span>🏷️</span>
          <div style="flex:1"><div style="font-weight:600;">مسمى "علي"</div></div>
          <input type="text" id="termOutgoing" value="علي" style="width:100px;padding:6px 10px;background:#151d35;border:1px solid rgba(99,179,237,0.2);border-radius:8px;color:#e2e8f0;font-family:'Cairo',sans-serif;font-size:13px;text-align:center;">
        </div>
        <div style="padding:12px 16px;">
          <button class="btn btn-gold btn-sm" onclick="saveTerms()">💾 حفظ المسميات</button>
        </div>
      </div>

      <div class="card" style="padding:0;overflow:hidden;margin-bottom:16px;">
        <div style="padding:12px 16px;font-size:11px;color:#a0aec0;font-weight:700;background:#1a2340;letter-spacing:1px;">البيانات</div>
        <div class="settings-row" onclick="backupData()">
          <span>☁️</span><div style="flex:1"><div style="font-weight:600;">تصدير نسخة احتياطية</div><div style="font-size:12px;color:#a0aec0;">تنزيل بياناتك</div></div><span style="color:#718096;">›</span>
        </div>
        <div class="settings-row" onclick="showPage('statements')">
          <span>📑</span><div style="flex:1"><div style="font-weight:600;">كشوف الحسابات</div><div style="font-size:12px;color:#a0aec0;">PDF وExcel</div></div><span style="color:#718096;">›</span>
        </div>
      </div>

      <!-- Developer Contact -->
      <div class="card" style="padding:0;overflow:hidden;margin-bottom:16px;">
        <div style="padding:12px 16px;font-size:11px;color:#a0aec0;font-weight:700;background:#1a2340;letter-spacing:1px;">تواصل مع المطوّر</div>
        <div style="padding:20px 16px;text-align:center;">
          <div style="font-size:36px;margin-bottom:10px;">👨‍💻</div>
          <div style="font-size:16px;font-weight:800;margin-bottom:4px;">وجيه علي</div>
          <div style="font-size:13px;color:#a0aec0;margin-bottom:16px;">مطوّر تطبيق حسابي</div>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
            <a href="https://wa.me/966567867414" target="_blank" class="btn btn-green btn-sm">💬 واتساب</a>
            <a href="tel:+966567867414" class="btn btn-blue btn-sm">📞 اتصال</a>
            <a href="sms:+966567867414" class="btn btn-outline btn-sm">📱 رسالة</a>
          </div>
          <div style="margin-top:14px;font-size:12px;color:#718096;">للاستفسار والدعم الفني: 0567867414</div>
        </div>
      </div>

      <div class="card" style="padding:0;overflow:hidden;">
        <div class="settings-row" onclick="doLogout()" style="color:#fc8181;">
          <span>🚪</span><div style="flex:1;color:#fc8181;font-weight:600;">تسجيل الخروج</div>
        </div>
      </div>
    </div>

  </div><!-- /container -->
</div><!-- /mainApp -->

<!-- ===== MODAL: ADD/EDIT CONTACT ===== -->
<div class="modal-bg" id="modalContact">
  <div class="modal">
    <div class="modal-title">
      <span id="contactModalTitle">إضافة جهة</span>
      <span class="modal-close" onclick="closeModal('modalContact')">✕</span>
    </div>
    <div id="alertContact" class="alert"></div>
    <div class="form-group"><label>الاسم</label><input id="cName" placeholder="اسم الشخص أو الشركة"></div>
    <div class="form-group"><label>الجوال</label><input id="cPhone" type="tel" placeholder="05xxxxxxxx"></div>
    <div class="form-group"><label>البريد (اختياري)</label><input id="cEmail" type="email" placeholder="example@email.com"></div>
    <div class="form-group"><label>النوع</label>
      <select id="cType">
        <option value="عميل">👤 عميل</option>
        <option value="مورد">🏭 مورد</option>
        <option value="مندوب">🚗 مندوب</option>
        <option value="دائن">💸 دائن</option>
        <option value="مدين">🤝 مدين</option>
        <option value="شريك">🤝 شريك</option>
        <option value="أخرى">📌 أخرى</option>
      </select>
    </div>
    <div class="form-group"><label>ملاحظات</label><textarea id="cNotes" rows="2" style="width:100%;padding:11px 14px;background:#151d35;border:1px solid rgba(99,179,237,0.15);border-radius:8px;color:#e2e8f0;font-family:'Cairo',sans-serif;outline:none;resize:vertical;" placeholder="معلومات إضافية..."></textarea></div>
    <input type="hidden" id="cEditId">
    <div style="display:flex;gap:10px;margin-top:8px;">
      <button class="btn btn-outline" style="flex:1;justify-content:center" onclick="closeModal('modalContact')">إلغاء</button>
      <button class="btn btn-gold" style="flex:1;justify-content:center" onclick="saveContact()">💾 حفظ</button>
    </div>
  </div>
</div>

<!-- ===== MODAL: ADD/EDIT TRANSACTION ===== -->
<div class="modal-bg" id="modalTx">
  <div class="modal">
    <div class="modal-title">
      <span id="txModalTitle">إضافة معاملة</span>
      <span class="modal-close" onclick="closeModal('modalTx')">✕</span>
    </div>
    <div id="alertTx" class="alert"></div>
    <div class="form-group"><label>النوع</label>
      <select id="txType">
        <option value="incoming">📥 لي (مستحق عليهم)</option>
        <option value="outgoing">📤 علي (مستحق لهم)</option>
      </select>
    </div>
    <div class="form-group"><label>الجهة</label>
      <select id="txContactSel"></select>
    </div>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:10px;">
      <div class="form-group" style="margin:0"><label>المبلغ</label><input id="txAmount" type="number" placeholder="0.00" min="0"></div>
      <div class="form-group" style="margin:0"><label>العملة</label>
        <select id="txCurrency">
          <option value="ر.س">ر.س</option>
          <option value="$">دولار $</option>
          <option value="€">يورو €</option>
          <option value="£">جنيه £</option>
          <option value="د.إ">درهم</option>
          <option value="د.ك">دينار</option>
        </select>
      </div>
    </div>
    <div class="form-group"><label>التاريخ</label><input id="txDate" type="date"></div>
    <div class="form-group"><label>تاريخ الاستحقاق (اختياري)</label><input id="txDueDate" type="date"></div>
    <div class="form-group"><label>ملاحظات</label><textarea id="txNotes" rows="2" style="width:100%;padding:11px 14px;background:#151d35;border:1px solid rgba(99,179,237,0.15);border-radius:8px;color:#e2e8f0;font-family:'Cairo',sans-serif;outline:none;resize:vertical;" placeholder="وصف المعاملة..."></textarea></div>
    <div class="form-group"><label>الحالة</label>
      <select id="txStatus">
        <option value="pending">🕐 معلقة</option>
        <option value="partial">🔄 جزئية</option>
        <option value="settled">✅ مسوّاة</option>
      </select>
    </div>
    <input type="hidden" id="txEditId">
    <div style="display:flex;gap:10px;margin-top:8px;">
      <button class="btn btn-outline" style="flex:1;justify-content:center" onclick="closeModal('modalTx')">إلغاء</button>
      <button class="btn btn-gold" style="flex:1;justify-content:center" onclick="saveTx()">💾 حفظ</button>
    </div>
  </div>
</div>

<!-- ===== MODAL: CONTACT DETAIL ===== -->
<div class="modal-bg" id="modalContactDetail">
  <div class="modal">
    <div class="modal-title">
      <span id="cdTitle">تفاصيل الجهة</span>
      <span class="modal-close" onclick="closeModal('modalContactDetail')">✕</span>
    </div>
    <div id="cdContent"></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;">
      <button class="btn btn-green btn-sm" id="cdWhatsapp">💬 واتساب</button>
      <button class="btn btn-blue btn-sm" id="cdCall">📞 اتصال</button>
      <button class="btn btn-gold btn-sm" onclick="editCurrentContact()">✏️ تعديل</button>
      <button class="btn btn-red btn-sm" onclick="deleteCurrentContact()">🗑️ حذف</button>
    </div>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- ===== MODAL: OTP ===== -->
<div class="modal-bg" id="modalOTP">
  <div class="modal" style="max-width:360px;text-align:center;">
    <div style="font-size:48px;margin-bottom:12px;">📱</div>
    <div class="modal-title" style="justify-content:center;">رمز التحقق</div>
    <div style="font-size:13px;color:#a0aec0;margin-bottom:20px;" id="otpDesc">تم إرسال رمز مكون من 4 أرقام</div>
    <div id="alertOTP" class="alert"></div>
    <div style="display:flex;gap:12px;justify-content:center;margin-bottom:20px;">
      <input class="otp-box" id="otp0" maxlength="1" oninput="otpNext(0)" type="tel">
      <input class="otp-box" id="otp1" maxlength="1" oninput="otpNext(1)" type="tel">
      <input class="otp-box" id="otp2" maxlength="1" oninput="otpNext(2)" type="tel">
      <input class="otp-box" id="otp3" maxlength="1" oninput="otpNext(3)" type="tel">
    </div>
    <button class="btn btn-gold" style="width:100%;justify-content:center;" onclick="verifyOTP()">✅ تحقق</button>
    <div style="margin-top:12px;font-size:13px;color:#718096;cursor:pointer;" onclick="closeModal('modalOTP')">← رجوع</div>
  </div>
</div>

<!-- ===== MODAL: EDIT PROFILE ===== -->
<div class="modal-bg" id="modalEditProfile">
  <div class="modal">
    <div class="modal-title">
      <span>✏️ تعديل البيانات</span>
      <span class="modal-close" onclick="closeModal('modalEditProfile')">✕</span>
    </div>
    <div id="alertEditProfile" class="alert"></div>
    <div class="form-group"><label>الاسم الكامل</label><input id="epName" type="text" placeholder="اسمك"></div>
    <div class="form-group"><label>رقم الجوال</label><input id="epPhone" type="tel" placeholder="05xxxxxxxx"></div>
    <div class="form-group"><label>اسم المنشأة (اختياري)</label><input id="epBusiness" type="text" placeholder="اسم شركتك أو متجرك"></div>
    <div style="display:flex;gap:10px;margin-top:8px;">
      <button class="btn btn-outline" style="flex:1;justify-content:center" onclick="closeModal('modalEditProfile')">إلغاء</button>
      <button class="btn btn-gold" style="flex:1;justify-content:center" onclick="saveProfile()">💾 حفظ</button>
    </div>
  </div>
</div>

<!-- ===== MODAL: CHANGE PASSWORD ===== -->
<div class="modal-bg" id="modalChangePwd">
  <div class="modal">
    <div class="modal-title">
      <span>🔐 تغيير كلمة المرور</span>
      <span class="modal-close" onclick="closeModal('modalChangePwd')">✕</span>
    </div>
    <div id="alertChangePwd" class="alert"></div>
    <div class="form-group"><label>كلمة المرور الحالية</label><input id="pwdCurrent" type="password" placeholder="••••••••"></div>
    <div class="form-group"><label>كلمة المرور الجديدة</label><input id="pwdNew" type="password" placeholder="••••••••"></div>
    <div class="form-group"><label>تأكيد كلمة المرور الجديدة</label><input id="pwdConfirm" type="password" placeholder="••••••••"></div>
    <div style="display:flex;gap:10px;margin-top:8px;">
      <button class="btn btn-outline" style="flex:1;justify-content:center" onclick="closeModal('modalChangePwd')">إلغاء</button>
      <button class="btn btn-gold" style="flex:1;justify-content:center" onclick="doChangePwd()">💾 تغيير</button>
    </div>
  </div>
</div>

<style>
.otp-box{width:56px;height:60px;text-align:center;font-size:24px;font-weight:800;background:#151d35;border:2px solid rgba(99,179,237,0.2);border-radius:12px;color:#e2e8f0;font-family:'Cairo',sans-serif;outline:none;transition:all 0.2s;}
.otp-box:focus{border-color:#f6c90e;box-shadow:0 0 0 3px rgba(246,201,14,0.15);}
</style>

<script>
// ============================================================
// JAVASCRIPT — التواصل مع السيرفر Python
// ============================================================

// المتغيرات العامة
let allContacts = [];
let allTx = [];
let stData = [];
let currentContactId = null;
let contactTypeFilter = 'all';
let txFilter = 'all';
let stTab = 'total';

// ===== مساعدات =====
const $ = id => document.getElementById(id);
const toast = (msg, type='success') => {
  const el = $('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  setTimeout(() => el.className = '', 2800);
};

const api = async (url, data=null) => {
  const opts = {
    method: data ? 'POST' : 'GET',
    headers: {'Content-Type':'application/json'}
  };
  if (data) opts.body = JSON.stringify(data);
  const res = await fetch(url, opts);
  return res.json();
};

// ===== AUTH =====
function switchAuthTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  $('loginForm').style.display = tab === 'login' ? 'block' : 'none';
  $('registerForm').style.display = tab === 'register' ? 'block' : 'none';
}

async function doLogin() {
  const phone = $('loginPhone').value.trim();
  const pass  = $('loginPass').value;
  if (!phone || !pass) { showAlert('alertAuth','يرجى تعبئة الحقول','error'); return; }
  const r = await api('/api/login', {phone, password: pass});
  if (r.success) { startApp(r.user); }
  else { showAlert('alertAuth', r.error || 'خطأ في الدخول', 'error'); }
}

async function doRegister() {
  const name  = $('regName').value.trim();
  const phone = $('regPhone').value.trim();
  const pass  = $('regPass').value;
  if (!name || !phone || !pass) { showAlert('alertAuth','يرجى تعبئة الحقول','error'); return; }
  const r = await api('/api/register', {name, phone, password: pass});
  if (r.success) { startApp(r.user); }
  else { showAlert('alertAuth', r.error || 'خطأ في التسجيل', 'error'); }
}

async function doLogout() {
  await api('/api/logout');
  location.reload();
}

function showAlert(id, msg, type) {
  const el = $(id);
  el.textContent = msg;
  el.className = `alert show alert-${type}`;
}

// ===== APP START =====
async function startApp(user) {
  $('loginPage').style.display = 'none';
  $('mainApp').style.display = 'block';
  $('welcomeName').textContent = user?.name || 'مستخدم';
  $('todayDate').textContent = new Date().toLocaleDateString('ar-SA', {weekday:'long',year:'numeric',month:'long',day:'numeric'});
  await loadAll();
  showPage('home');
}

async function loadAll() {
  const [contacts, txs] = await Promise.all([
    api('/api/contacts'),
    api('/api/transactions')
  ]);
  allContacts = contacts.data || [];
  allTx       = txs.data || [];
  populateContactSelects();
}

// ===== NAVIGATION =====
const PAGES = ['home','contacts','transactions','statements','reports','notifications','map','settings'];
function showPage(page) {
  PAGES.forEach(p => {
    const el = $('page-' + p);
    if (el) el.style.display = p === page ? 'block' : 'none';
    const pill = $('pill-' + p);
    if (pill) pill.classList.toggle('active', p === page);
  });
  if (page === 'home')          renderHome();
  if (page === 'contacts')      renderContacts();
  if (page === 'transactions')  renderTx();
  if (page === 'reports')       renderReports();
  if (page === 'notifications') renderNotifs();
  if (page === 'statements')    populateStContact();
  if (page === 'map')           setTimeout(initMap, 100);
  if (page === 'settings')      renderSettings();
}

// ===== HOME =====
function renderHome() {
  let forMe=0, onMe=0, settled=0;
  allTx.forEach(t => {
    if (t.status === 'settled') { settled++; return; }
    if (t.type === 'incoming') forMe += parseFloat(t.amount)||0;
    else onMe += parseFloat(t.amount)||0;
  });
  const net = forMe - onMe;
  const nb = $('netBalance');
  nb.textContent = `${net>=0?'+':''}${net.toFixed(2)} ر.س`;
  nb.className = 'balance-amount ' + (net>0?'green':net<0?'red':'');
  $('totalFor').textContent = `${forMe.toFixed(2)} ر.س`;
  $('totalOn').textContent  = `${onMe.toFixed(2)} ر.س`;

  // Stats
  $('statsGrid').innerHTML = [
    {icon:'👥', val: allContacts.length, label:'جهات الاتصال', page:'contacts'},
    {icon:'📋', val: allTx.length,       label:'المعاملات',     page:'transactions'},
    {icon:'✅', val: settled,             label:'مسوّاة',        page:'transactions'},
    {icon:'⏰', val: allTx.filter(t=>t.reminder&&t.reminder!=='none'&&t.status!=='settled').length, label:'تذكيرات', page:'transactions'},
  ].map(s => `<div class="stat-card" onclick="showPage('${s.page}')">
    <div class="stat-icon">${s.icon}</div>
    <div class="stat-val">${s.val}</div>
    <div class="stat-label">${s.label}</div>
  </div>`).join('');

  // Recent
  const recent = allTx.slice(0,6);
  $('recentTx').innerHTML = recent.length ? recent.map(t => txRow(t)).join('') :
    `<div class="empty"><div class="empty-icon">📋</div><p>لا توجد معاملات بعد</p></div>`;
}

// ===== CONTACTS =====
function renderContacts() {
  const q = ($('contactSearch')?.value||'').toLowerCase();
  const list = allContacts.filter(c => {
    const typeOk = contactTypeFilter==='all' || c.type===contactTypeFilter;
    const nameOk = !q || c.name.toLowerCase().includes(q) || (c.phone||'').includes(q);
    return typeOk && nameOk;
  });

  const typeEmojis = {'عميل':'👤','مورد':'🏭','مندوب':'🚗','دائن':'💸','مدين':'🤝','شريك':'🤝','أخرى':'📌'};
  const typeColors2= {'عميل':'blue','مورد':'orange','مندوب':'purple','دائن':'red','مدين':'green','شريك':'gold','أخرى':''};

  $('contactsList').innerHTML = list.length ? list.map(c => {
    const bal = getLocalBalance(c.id);
    const bc  = bal.net>=0?'green':'red';
    const bl  = bal.net>=0?'لي منه':'علي له';
    const em  = typeEmojis[c.type]||'📌';
    const tc  = typeColors2[c.type]||'';
    return `<div class="card" style="cursor:pointer;padding:14px;margin-bottom:10px;" onclick="openContactDetail(${c.id})">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:46px;height:46px;border-radius:12px;background:rgba(99,179,237,0.1);display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;">${em}</div>
        <div style="flex:1;">
          <div style="font-size:15px;font-weight:700;">${c.name}</div>
          <div style="font-size:12px;color:#a0aec0;margin-top:3px;">${c.phone||'بدون رقم'}</div>
        </div>
        <div style="text-align:left;">
          <div style="font-size:15px;font-weight:800;" class="${bc}">${Math.abs(bal.net).toFixed(2)} ر.س</div>
          <div style="font-size:11px;color:#718096;">${bl}</div>
        </div>
      </div>
    </div>`;
  }).join('') :
  `<div class="empty"><div class="empty-icon">👥</div><p>لا توجد جهات</p></div>`;
}

function filterContacts() { renderContacts(); }
function setContactFilter(el, type) {
  document.querySelectorAll('#contactTypeChips .chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  contactTypeFilter = type;
  renderContacts();
}

// ===== TRANSACTIONS =====
function txRow(t) {
  const isIn = t.type==='incoming';
  const statusLabel = {pending:'🕐 معلقة',partial:'🔄 جزئية',settled:'✅ مسوّاة'}[t.status]||'';
  return `<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid rgba(99,179,237,0.07);cursor:pointer;" onclick="editTx(${t.id})">
    <div style="width:42px;height:42px;border-radius:10px;background:${isIn?'rgba(72,187,120,0.15)':'rgba(252,129,129,0.15)'};display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">${isIn?'📥':'📤'}</div>
    <div style="flex:1;">
      <div style="font-size:14px;font-weight:700;">${t.contact_name||'—'}</div>
      <div style="font-size:12px;color:#a0aec0;margin-top:2px;">${t.notes||'—'} · ${t.date||''}</div>
    </div>
    <div style="text-align:left;">
      <div style="font-size:15px;font-weight:800;" class="${isIn?'green':'red'}">${isIn?'+':'-'}${t.amount} ${t.currency}</div>
      <div style="font-size:11px;color:#718096;">${statusLabel}</div>
    </div>
  </div>`;
}

function renderTx() {
  const q = ($('txSearch')?.value||'').toLowerCase();
  const list = allTx.filter(t => {
    const fok = txFilter==='all' || t.type===txFilter || (txFilter==='settled'&&t.status==='settled');
    const nok = !q || (t.contact_name||'').toLowerCase().includes(q) || (t.notes||'').toLowerCase().includes(q);
    return fok && nok;
  });
  $('txList').innerHTML = list.length ?
    `<div class="card">${list.map(t=>txRow(t)).join('')}</div>` :
    `<div class="empty"><div class="empty-icon">📋</div><p>لا توجد معاملات</p></div>`;
}

function filterTx() { renderTx(); }
function setTxFilter(el, f) {
  document.querySelectorAll('#page-transactions .chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  txFilter = f;
  renderTx();
}

// ===== LOCAL BALANCE =====
function getLocalBalance(contactId) {
  let forMe=0, onMe=0;
  allTx.forEach(t => {
    if (t.contact_id===contactId && t.status!=='settled') {
      if (t.type==='incoming') forMe+=parseFloat(t.amount)||0;
      else onMe+=parseFloat(t.amount)||0;
    }
  });
  return {forMe, onMe, net: forMe-onMe};
}

// ===== CONTACT MODALS =====
function openAddContact() {
  $('contactModalTitle').textContent = 'إضافة جهة';
  $('cName').value=''; $('cPhone').value='';
  $('cEmail').value=''; $('cType').value='عميل';
  $('cNotes').value=''; $('cEditId').value='';
  $('alertContact').className='alert';
  openModal('modalContact');
}

async function openContactDetail(id) {
  currentContactId = id;
  const c = allContacts.find(x=>x.id===id);
  if (!c) return;
  const bal = getLocalBalance(id);
  const txs = allTx.filter(t=>t.contact_id===id);
  $('cdTitle').textContent = c.name;
  $('cdContent').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px;">
      <div style="background:rgba(72,187,120,0.1);border-radius:10px;padding:12px;">
        <div style="font-size:11px;color:#48bb78;">لي منه</div>
        <div class="green" style="font-size:18px;font-weight:800;margin-top:4px;">${bal.forMe.toFixed(2)} ر.س</div>
      </div>
      <div style="background:rgba(252,129,129,0.1);border-radius:10px;padding:12px;">
        <div style="font-size:11px;color:#fc8181;">علي له</div>
        <div class="red" style="font-size:18px;font-weight:800;margin-top:4px;">${bal.onMe.toFixed(2)} ر.س</div>
      </div>
    </div>
    <div style="font-size:13px;color:#a0aec0;margin-bottom:4px;">📋 ${txs.length} معاملة</div>
    ${c.phone?`<div style="font-size:13px;color:#a0aec0;">📞 ${c.phone}</div>`:''}
    ${c.notes?`<div style="font-size:13px;color:#a0aec0;margin-top:6px;">📝 ${c.notes}</div>`:''}`;
  $('cdWhatsapp').onclick = () => {
    if (c.phone) window.open(`https://wa.me/${c.phone.replace(/^0/,'966')}`, '_blank');
    else toast('لا يوجد رقم جوال','error');
  };
  $('cdCall').onclick = () => { if (c.phone) window.location.href=`tel:${c.phone}`; };
  openModal('modalContactDetail');
}

function editCurrentContact() {
  closeModal('modalContactDetail');
  const c = allContacts.find(x=>x.id===currentContactId);
  if (!c) return;
  $('contactModalTitle').textContent = 'تعديل الجهة';
  $('cName').value=c.name; $('cPhone').value=c.phone||'';
  $('cEmail').value=c.email||''; $('cType').value=c.type;
  $('cNotes').value=c.notes||''; $('cEditId').value=c.id;
  openModal('modalContact');
}

async function saveContact() {
  const name  = $('cName').value.trim();
  const phone = $('cPhone').value.trim();
  const type  = $('cType').value;
  const email = $('cEmail').value.trim();
  const notes = $('cNotes').value.trim();
  const editId= $('cEditId').value;
  if (!name) { showAlert('alertContact','يرجى إدخال الاسم','error'); return; }
  const url = editId ? `/api/contacts/${editId}` : '/api/contacts';
  const r = await api(url, {name,phone,type,email,notes});
  if (r.success) {
    closeModal('modalContact');
    await loadAll();
    renderContacts();
    renderHome();
    toast(editId ? 'تم التعديل ✅' : 'تمت الإضافة ✅');
  } else {
    showAlert('alertContact', r.error||'خطأ', 'error');
  }
}

async function deleteCurrentContact() {
  if (!confirm('حذف هذه الجهة؟')) return;
  const r = await api(`/api/contacts/${currentContactId}`, {_method:'DELETE'});
  if (r.success) {
    closeModal('modalContactDetail');
    await loadAll();
    renderContacts();
    renderHome();
    toast('تم الحذف');
  }
}

// ===== TRANSACTION MODALS =====
function populateContactSelects() {
  ['txContactSel','stContact'].forEach(selId => {
    const sel = $(selId);
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="">-- اختر --</option>';
    if (selId==='stContact') sel.innerHTML = '<option value="">الكل</option>';
    allContacts.forEach(c => {
      const opt = document.createElement('option');
      opt.value=c.id; opt.textContent=`${c.name} (${c.type})`;
      sel.appendChild(opt);
    });
    if (prev) sel.value=prev;
  });
}

function openAddTx(type='incoming') {
  $('txModalTitle').textContent = 'إضافة معاملة';
  $('txType').value=type;
  $('txContactSel').value=''; $('txAmount').value='';
  $('txDate').value=new Date().toISOString().split('T')[0];
  $('txDueDate').value=''; $('txNotes').value='';
  $('txStatus').value='pending'; $('txEditId').value='';
  $('alertTx').className='alert';
  openModal('modalTx');
}

async function editTx(id) {
  const t = allTx.find(x=>x.id===id);
  if (!t) return;
  $('txModalTitle').textContent = 'تعديل المعاملة';
  $('txType').value=t.type;
  $('txContactSel').value=t.contact_id;
  $('txAmount').value=t.amount;
  $('txCurrency').value=t.currency;
  $('txDate').value=t.date||'';
  $('txDueDate').value=t.due_date||'';
  $('txNotes').value=t.notes||'';
  $('txStatus').value=t.status;
  $('txEditId').value=t.id;
  openModal('modalTx');
}

async function saveTx() {
  const contactId = $('txContactSel').value;
  const amount    = parseFloat($('txAmount').value);
  const type      = $('txType').value;
  const currency  = $('txCurrency').value;
  const date      = $('txDate').value;
  const dueDate   = $('txDueDate').value;
  const notes     = $('txNotes').value.trim();
  const status    = $('txStatus').value;
  const editId    = $('txEditId').value;
  if (!contactId) { showAlert('alertTx','اختر الجهة','error'); return; }
  if (!amount||amount<=0) { showAlert('alertTx','أدخل مبلغاً صحيحاً','error'); return; }
  const url = editId ? `/api/transactions/${editId}` : '/api/transactions';
  const r = await api(url, {contact_id:contactId,amount,type,currency,date,due_date:dueDate,notes,status});
  if (r.success) {
    closeModal('modalTx');
    await loadAll();
    renderTx();
    renderHome();
    toast(editId ? 'تم التعديل ✅' : 'تمت الإضافة ✅');
  } else {
    showAlert('alertTx', r.error||'خطأ', 'error');
  }
}

// ===== STATEMENTS =====
function populateStContact() { populateContactSelects(); }
function switchStTab(el, tab) {
  document.querySelectorAll('#stTabs .tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  stTab=tab;
  if (stData.length) renderStatement();
}
function resetStatement() {
  $('stFrom').value=''; $('stTo').value='';
  $('stContact').value=''; $('stType').value=''; $('stStatus').value='';
  $('stOutput').innerHTML=''; $('stSummary').style.display='none';
  $('stExportBtns').style.display='none'; stData=[];
}
async function generateStatement() {
  const r = await api('/api/statements', {
    from: $('stFrom').value, to: $('stTo').value,
    contact_id: $('stContact').value,
    type: $('stType').value, status: $('stStatus').value
  });
  stData = r.data || [];
  if (!stData.length) {
    $('stOutput').innerHTML=`<div class="empty"><div class="empty-icon">📑</div><p>لا توجد بيانات</p></div>`;
    $('stExportBtns').style.display='none'; return;
  }
  renderStatement();
  $('stExportBtns').style.display='block';
  toast(`تم توليد الكشف — ${stData.length} معاملة`);
}

function renderStatement() {
  let forMe=0, onMe=0;
  stData.forEach(t => {
    if (t.type==='incoming') forMe+=parseFloat(t.amount)||0;
    else onMe+=parseFloat(t.amount)||0;
  });
  const net=forMe-onMe;
  $('stSummary').style.display='grid';
  $('stSummary').innerHTML = [
    {label:'إجمالي لي',val:`${forMe.toFixed(2)} ر.س`,cls:'green',bg:'rgba(72,187,120,0.1)',bc:'rgba(72,187,120,0.3)'},
    {label:'إجمالي علي',val:`${onMe.toFixed(2)} ر.س`,cls:'red',bg:'rgba(252,129,129,0.1)',bc:'rgba(252,129,129,0.3)'},
    {label:'الصافي',val:`${net>=0?'+':''}${net.toFixed(2)} ر.س`,cls:net>=0?'green':'red',bg:'rgba(246,201,14,0.1)',bc:'rgba(246,201,14,0.3)'},
    {label:'المعاملات',val:stData.length,cls:'blue',bg:'rgba(99,179,237,0.1)',bc:'rgba(99,179,237,0.3)'},
  ].map(s=>`<div style="background:${s.bg};border:1px solid ${s.bc};border-radius:12px;padding:14px;">
    <div style="font-size:11px;color:#a0aec0;margin-bottom:6px;">${s.label}</div>
    <div style="font-size:18px;font-weight:800;" class="${s.cls}">${s.val}</div>
  </div>`).join('');

  if (stTab==='total') {
    $('stOutput').innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>التاريخ</th><th>الجهة</th><th>البيان</th><th>لي 📥</th><th>علي 📤</th><th>الحالة</th></tr></thead>
      <tbody>${stData.map(t=>{
        const isIn=t.type==='incoming';
        const sl={pending:'🕐 معلقة',partial:'🔄 جزئية',settled:'✅ مسوّاة'}[t.status]||'';
        return `<tr>
          <td>${t.date||'—'}</td>
          <td style="font-weight:600;">${t.contact_name||'—'}</td>
          <td style="color:#a0aec0;font-size:12px;">${t.notes||'—'}</td>
          <td class="green" style="font-weight:700;">${isIn?t.amount+' '+t.currency:'—'}</td>
          <td class="red" style="font-weight:700;">${!isIn?t.amount+' '+t.currency:'—'}</td>
          <td>${sl}</td>
        </tr>`;
      }).join('')}</tbody>
    </table></div>`;
  } else if (stTab==='analytic') {
    // Group by month
    const byMonth={};
    stData.forEach(t=>{
      const k=(t.date||'').substr(0,7)||'غير محدد';
      if(!byMonth[k]) byMonth[k]={forMe:0,onMe:0,count:0};
      if(t.type==='incoming') byMonth[k].forMe+=parseFloat(t.amount)||0;
      else byMonth[k].onMe+=parseFloat(t.amount)||0;
      byMonth[k].count++;
    });
    const monthNames=['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
    const mLabel=k=>{const[y,m]=k.split('-');return(monthNames[parseInt(m)-1]||m)+' '+y;};
    $('stOutput').innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>الشهر</th><th>العدد</th><th class="green">لي</th><th class="red">علي</th><th class="gold">الصافي</th></tr></thead>
      <tbody>${Object.entries(byMonth).sort().map(([k,v])=>{
        const n=v.forMe-v.onMe;
        return `<tr><td style="font-weight:600;">${mLabel(k)}</td><td>${v.count}</td>
          <td class="green">${v.forMe.toFixed(2)}</td><td class="red">${v.onMe.toFixed(2)}</td>
          <td class="${n>=0?'green':'red'}" style="font-weight:800;">${n>=0?'+':''}${n.toFixed(2)}</td></tr>`;
      }).join('')}</tbody>
    </table></div>`;
  } else {
    // By person
    const byPerson={};
    stData.forEach(t=>{
      if(!byPerson[t.contact_id]) byPerson[t.contact_id]={name:t.contact_name,forMe:0,onMe:0,txs:[]};
      if(t.type==='incoming') byPerson[t.contact_id].forMe+=parseFloat(t.amount)||0;
      else byPerson[t.contact_id].onMe+=parseFloat(t.amount)||0;
      byPerson[t.contact_id].txs.push(t);
    });
    $('stOutput').innerHTML = Object.entries(byPerson).map(([cid,v])=>{
      const n=v.forMe-v.onMe;
      return `<div class="card" style="margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <div style="font-size:16px;font-weight:800;">${v.name}</div>
          <div style="font-size:16px;font-weight:800;" class="${n>=0?'green':'red'}">${n>=0?'+':''}${n.toFixed(2)} ر.س</div>
        </div>
        <div class="table-wrap"><table>
          <thead><tr><th>التاريخ</th><th>البيان</th><th class="green">لي</th><th class="red">علي</th></tr></thead>
          <tbody>${v.txs.map(t=>{
            const isIn=t.type==='incoming';
            return `<tr><td>${t.date||'—'}</td><td>${t.notes||'—'}</td>
              <td class="green">${isIn?t.amount+' '+t.currency:''}</td>
              <td class="red">${!isIn?t.amount+' '+t.currency:''}</td></tr>`;
          }).join('')}</tbody>
        </table></div>
        <div style="display:flex;justify-content:space-between;padding:8px 0 0;font-size:13px;color:#a0aec0;">
          <span>لي: <strong class="green">${v.forMe.toFixed(2)}</strong></span>
          <span>علي: <strong class="red">${v.onMe.toFixed(2)}</strong></span>
        </div>
      </div>`;
    }).join('');
  }
}

async function exportPDF()   { window.open('/api/export/pdf?'+new URLSearchParams({from:$('stFrom').value,to:$('stTo').value,contact_id:$('stContact').value}),'_blank'); }
async function exportExcel() { window.open('/api/export/excel?'+new URLSearchParams({from:$('stFrom').value,to:$('stTo').value,contact_id:$('stContact').value}),'_blank'); }

// ===== REPORTS =====
function renderReports() {
  let forMe=0,onMe=0,settled=0;
  allTx.forEach(t=>{
    if(t.status==='settled') settled++;
    else if(t.type==='incoming') forMe+=parseFloat(t.amount)||0;
    else onMe+=parseFloat(t.amount)||0;
  });
  const net=forMe-onMe;
  $('reportSummary').innerHTML=[
    {l:'إجمالي لي',v:`${forMe.toFixed(0)} ر.س`,c:'green'},
    {l:'إجمالي علي',v:`${onMe.toFixed(0)} ر.س`,c:'red'},
    {l:'الصافي',v:`${net>=0?'+':''}${net.toFixed(0)} ر.س`,c:net>=0?'green':'red'},
    {l:'مسوّاة',v:settled,c:'blue'},
  ].map(s=>`<div class="stat-card"><div class="stat-val ${s.c}">${s.v}</div><div class="stat-label">${s.l}</div></div>`).join('');

  // Top balances
  const sorted=[...allContacts].map(c=>({...c,...getLocalBalance(c.id)})).sort((a,b)=>Math.abs(b.net)-Math.abs(a.net)).slice(0,8);
  $('topBalances').innerHTML=sorted.map(c=>`
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(99,179,237,0.07);">
      <div style="font-size:14px;font-weight:600;">${c.name}<span style="font-size:11px;color:#a0aec0;margin-right:6px;">${c.type}</span></div>
      <div style="font-size:14px;font-weight:800;" class="${c.net>=0?'green':'red'}">${Math.abs(c.net).toFixed(0)} ر.س</div>
    </div>`).join('')||`<div class="empty"><p>لا توجد بيانات</p></div>`;

  // Type breakdown
  const byType={};
  allContacts.forEach(c=>{
    if(!byType[c.type]) byType[c.type]={count:0,forMe:0,onMe:0};
    byType[c.type].count++;
    const b=getLocalBalance(c.id);
    byType[c.type].forMe+=b.forMe;
    byType[c.type].onMe+=b.onMe;
  });
  $('typeBreakdown').innerHTML=Object.entries(byType).map(([type,v])=>`
    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(99,179,237,0.07);">
      <div style="font-size:14px;font-weight:600;">${type} <span style="font-size:11px;color:#a0aec0;">(${v.count})</span></div>
      <div style="font-size:12px;text-align:left;">
        <span class="green">${v.forMe.toFixed(0)}</span> /
        <span class="red">${v.onMe.toFixed(0)}</span>
      </div>
    </div>`).join('')||`<div class="empty"><p>لا توجد بيانات</p></div>`;
}

// ===== NOTIFICATIONS =====
async function renderNotifs() {
  const r = await api('/api/notifications');
  const list = r.data||[];
  $('notifList').innerHTML = list.length ? list.map(n=>`
    <div class="card" style="margin-bottom:10px;${!n.is_read?'border-color:rgba(99,179,237,0.4);':''}">
      <div style="display:flex;gap:10px;">
        <div style="font-size:22px;">${n.icon}</div>
        <div>
          <div style="font-size:14px;font-weight:700;">${n.title}</div>
          <div style="font-size:13px;color:#a0aec0;margin-top:3px;">${n.body}</div>
          <div style="font-size:11px;color:#718096;margin-top:6px;">${n.created}</div>
        </div>
      </div>
    </div>`).join('') :
    `<div class="empty"><div class="empty-icon">🔔</div><p>لا توجد إشعارات</p></div>`;
}

async function markAllRead() {
  await api('/api/notifications/read-all');
  renderNotifs();
}

// ===== MODAL HELPERS =====
function openModal(id)  { $(id).classList.add('open'); }
function closeModal(id) { $(id).classList.remove('open'); }
document.querySelectorAll('.modal-bg').forEach(bg => {
  bg.addEventListener('click', e => { if(e.target===bg) bg.classList.remove('open'); });
});

// ===== INIT =====
window.onload = async () => {
  const r = await api('/api/me');
  if (r.user) { startApp(r.user); }
  else { $('loginPage').style.display='block'; }
};

// ===== GLOBAL SEARCH =====
function globalSearchFn() {
  const q = ($('globalSearch')?.value||'').trim().toLowerCase();
  const res = $('searchResults');
  if (!q || q.length < 2) { res.style.display='none'; return; }

  const contacts = allContacts.filter(c =>
    c.name.toLowerCase().includes(q) || (c.phone||'').includes(q)
  ).slice(0,4);

  const txs = allTx.filter(t =>
    (t.contact_name||'').toLowerCase().includes(q) || (t.notes||'').toLowerCase().includes(q)
  ).slice(0,4);

  if (!contacts.length && !txs.length) {
    res.style.display='block';
    res.innerHTML=`<div style="text-align:center;color:#718096;font-size:13px;">لا توجد نتائج لـ "${q}"</div>`;
    return;
  }

  let html = '';
  if (contacts.length) {
    html += `<div style="font-size:11px;color:#a0aec0;margin-bottom:8px;font-weight:700;">👥 جهات الاتصال</div>`;
    html += contacts.map(c => {
      const bal = getLocalBalance(c.id);
      return `<div onclick="openContactDetail(${c.id});$('globalSearch').value='';$('searchResults').style.display='none';"
        style="display:flex;align-items:center;gap:10px;padding:8px;border-radius:8px;cursor:pointer;transition:background 0.15s;"
        onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background=''">
        <div style="font-size:18px;">👤</div>
        <div style="flex:1;"><div style="font-size:13px;font-weight:600;">${c.name}</div><div style="font-size:11px;color:#a0aec0;">${c.type} · ${c.phone||''}</div></div>
        <div style="font-size:13px;font-weight:700;" class="${bal.net>=0?'green':'red'}">${Math.abs(bal.net).toFixed(0)} ر.س</div>
      </div>`;
    }).join('');
  }

  if (txs.length) {
    html += `<div style="font-size:11px;color:#a0aec0;margin:10px 0 8px;font-weight:700;">📋 المعاملات</div>`;
    html += txs.map(t => {
      const isIn = t.type==='incoming';
      return `<div onclick="editTx(${t.id});$('globalSearch').value='';$('searchResults').style.display='none';"
        style="display:flex;align-items:center;gap:10px;padding:8px;border-radius:8px;cursor:pointer;transition:background 0.15s;"
        onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background=''">
        <div style="font-size:18px;">${isIn?'📥':'📤'}</div>
        <div style="flex:1;"><div style="font-size:13px;font-weight:600;">${t.contact_name||'—'}</div><div style="font-size:11px;color:#a0aec0;">${t.notes||''} · ${t.date||''}</div></div>
        <div style="font-size:13px;font-weight:700;" class="${isIn?'green':'red'}">${isIn?'+':'-'}${t.amount} ${t.currency}</div>
      </div>`;
    }).join('');
  }

  res.innerHTML = html;
  res.style.display = 'block';
}

// Close search on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('#globalSearch') && !e.target.closest('#searchResults')) {
    const res = $('searchResults');
    if (res) res.style.display = 'none';
  }
});

// ===== OTP =====
let pendingOTPAction = null;
let pendingOTPCode = null;

function generateOTP() {
  return Math.floor(1000 + Math.random() * 9000).toString();
}

function showOTP(action, desc) {
  pendingOTPCode = generateOTP();
  pendingOTPAction = action;
  $('otpDesc').textContent = desc || `رمز التحقق: ${pendingOTPCode} (تجريبي)`;
  ['otp0','otp1','otp2','otp3'].forEach(id => { const el=$(id); if(el) el.value=''; });
  $('alertOTP').className='alert';
  openModal('modalOTP');
  setTimeout(() => { const el=$('otp0'); if(el) el.focus(); }, 200);
  // In real app: send SMS via Unifonic/Taqnyat
  console.log(`OTP Code: ${pendingOTPCode}`);
  toast(`رمز التحقق: ${pendingOTPCode}`, 'success');
}

function otpNext(i) {
  const el = $('otp' + i);
  if (el && el.value.length === 1 && i < 3) {
    const next = $('otp' + (i+1));
    if (next) next.focus();
  }
}

function verifyOTP() {
  const entered = ['otp0','otp1','otp2','otp3'].map(id => {
    const el = $(id); return el ? el.value : '';
  }).join('');

  if (entered === pendingOTPCode) {
    closeModal('modalOTP');
    toast('تم التحقق بنجاح ✅', 'success');
    if (pendingOTPAction) pendingOTPAction();
  } else {
    showAlert('alertOTP', 'رمز التحقق غير صحيح', 'error');
  }
}

// Hook into register to show OTP
const _origDoRegister = doRegister;
async function doRegister() {
  const name  = $('regName').value.trim();
  const phone = $('regPhone').value.trim();
  const pass  = $('regPass').value;
  if (!name || !phone || !pass) { showAlert('alertAuth','يرجى تعبئة الحقول','error'); return; }
  if (pass.length < 6) { showAlert('alertAuth','كلمة المرور قصيرة (6 أحرف على الأقل)','error'); return; }

  showOTP(async () => {
    const r = await api('/api/register', {name, phone, password: pass});
    if (r.success) { startApp(r.user); }
    else { showAlert('alertAuth', r.error || 'خطأ في التسجيل', 'error'); }
  }, `رمز تأكيد تسجيل الحساب (تجريبي)`);
}

// ===== SETTINGS =====
let currentUser = null;

async function renderSettings() {
  const r = await api('/api/me');
  currentUser = r.user;
  if (!currentUser) return;
  const av = $('settingsAvatar');
  const nm = $('settingsName');
  const ph = $('settingsPhone');
  if (av) av.textContent = (currentUser.name||'م').charAt(0);
  if (nm) nm.textContent = currentUser.name || '—';
  if (ph) ph.textContent = currentUser.phone || '—';

  // Load saved terms
  const s = await api('/api/settings');
  if (s.data) {
    const ti = $('termIncoming'); const to = $('termOutgoing');
    if (ti && s.data.termIncoming) ti.value = s.data.termIncoming;
    if (to && s.data.termOutgoing) to.value = s.data.termOutgoing;
  }
}

function openEditProfile() {
  if (!currentUser) return;
  $('epName').value = currentUser.name || '';
  $('epPhone').value = currentUser.phone || '';
  $('epBusiness').value = currentUser.business || '';
  $('alertEditProfile').className = 'alert';
  openModal('modalEditProfile');
}

async function saveProfile() {
  const name = $('epName').value.trim();
  const phone = $('epPhone').value.trim();
  const business = $('epBusiness').value.trim();
  if (!name) { showAlert('alertEditProfile','يرجى إدخال الاسم','error'); return; }
  const r = await api('/api/profile', {name, phone, business});
  if (r.success) {
    closeModal('modalEditProfile');
    await renderSettings();
    $('welcomeName').textContent = name;
    toast('تم الحفظ ✅', 'success');
  } else {
    showAlert('alertEditProfile', r.error||'خطأ', 'error');
  }
}

function openChangePwd() {
  $('pwdCurrent').value=''; $('pwdNew').value=''; $('pwdConfirm').value='';
  $('alertChangePwd').className='alert';
  openModal('modalChangePwd');
}

async function doChangePwd() {
  const current = $('pwdCurrent').value;
  const newPwd  = $('pwdNew').value;
  const confirm = $('pwdConfirm').value;
  if (!current || !newPwd) { showAlert('alertChangePwd','يرجى تعبئة الحقول','error'); return; }
  if (newPwd !== confirm) { showAlert('alertChangePwd','كلمتا المرور غير متطابقتين','error'); return; }
  if (newPwd.length < 6) { showAlert('alertChangePwd','كلمة المرور قصيرة جداً','error'); return; }
  const r = await api('/api/change-password', {current_password: current, new_password: newPwd});
  if (r.success) {
    closeModal('modalChangePwd');
    toast('تم تغيير كلمة المرور ✅', 'success');
  } else {
    showAlert('alertChangePwd', r.error||'خطأ', 'error');
  }
}

async function saveTerms() {
  const termIncoming = $('termIncoming').value.trim() || 'لي';
  const termOutgoing = $('termOutgoing').value.trim() || 'علي';
  await api('/api/settings', {termIncoming, termOutgoing});
  toast('تم حفظ المسميات ✅', 'success');
}

async function backupData() {
  const [contacts, txs] = await Promise.all([api('/api/contacts'), api('/api/transactions')]);
  const backup = { contacts: contacts.data, transactions: txs.data, date: new Date().toISOString() };
  const blob = new Blob([JSON.stringify(backup, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `hesabi_backup_${new Date().toISOString().split('T')[0]}.json`;
  a.click(); URL.revokeObjectURL(url);
  toast('تم تصدير النسخة الاحتياطية ✅', 'success');
}

// ===== MAP =====
let mapInstance = null;
let mapMarkers = [];
let mapTypeFilter = 'all';

const PIN_COLORS = {'عميل':'#63b3ed','مورد':'#f6ad55','مندوب':'#b794f4','دائن':'#fc8181','مدين':'#48bb78','شريك':'#f6c90e','أخرى':'#a0aec0'};
const PIN_EMOJI  = {'عميل':'👤','مورد':'🏭','مندوب':'🚗','دائن':'💸','مدين':'🤝','شريك':'🤝','أخرى':'📌'};

function makePin(type, name) {
  const color = PIN_COLORS[type] || '#a0aec0';
  const emoji = PIN_EMOJI[type] || '📌';
  return L.divIcon({
    html: `<div style="display:flex;flex-direction:column;align-items:center;">
      <div style="width:36px;height:36px;background:${color};border-radius:50% 50% 50% 0;transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(0,0,0,0.4);border:2px solid rgba(255,255,255,0.3);">
        <span style="transform:rotate(45deg);font-size:16px;">${emoji}</span>
      </div>
      <div style="margin-top:4px;background:rgba(15,22,40,0.88);color:#e2e8f0;font-size:10px;font-weight:700;padding:2px 7px;border-radius:8px;white-space:nowrap;max-width:90px;overflow:hidden;text-overflow:ellipsis;font-family:Cairo,sans-serif;">${name}</div>
    </div>`,
    className:'', iconSize:[36,52], iconAnchor:[18,52], popupAnchor:[0,-54]
  });
}

function initMap() {
  if (!window.L) { setTimeout(initMap, 500); return; }
  const container = $('mainMap');
  if (!container) return;

  if (mapInstance) { mapInstance.remove(); mapInstance = null; }

  mapInstance = L.map('mainMap', { zoomControl: true });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap', maxZoom: 19
  }).addTo(mapInstance);
  mapInstance.setView([24.7136, 46.6753], 11);

  setTimeout(() => { if (mapInstance) mapInstance.invalidateSize(); }, 200);
  renderMapMarkers();
}

function renderMapMarkers() {
  if (!mapInstance) return;
  mapMarkers.forEach(m => m.remove());
  mapMarkers = [];

  const contacts = allContacts.filter(c =>
    c.lat && c.lng && (mapTypeFilter === 'all' || c.type === mapTypeFilter)
  );

  let forCount=0, onCount=0;
  contacts.forEach(c => {
    const bal = getLocalBalance(c.id);
    if (bal.net > 0) forCount++; else if (bal.net < 0) onCount++;
    const marker = L.marker([c.lat, c.lng], {icon: makePin(c.type, c.name)}).addTo(mapInstance);
    const balColor = bal.net >= 0 ? '#48bb78' : '#fc8181';
    marker.bindPopup(`
      <div class="map-popup">
        <div class="map-popup-name">${c.name}</div>
        <div style="font-size:11px;color:${PIN_COLORS[c.type]||'#aaa'};margin-bottom:6px;font-weight:600;">${c.type}</div>
        <div class="map-popup-bal" style="color:${balColor};">${bal.net>=0?'لي منه':'علي له'}: ${Math.abs(bal.net).toFixed(2)} ر.س</div>
        ${c.phone?`<div style="font-size:12px;color:#a0aec0;margin-bottom:8px;">📞 ${c.phone}</div>`:''}
        <div style="display:flex;gap:6px;">
          <button onclick="window.open('https://wa.me/${(c.phone||'').replace(/^0/,'966')}','_blank')" style="padding:5px 10px;background:#1a3a2a;color:#48bb78;border:1px solid #48bb78;border-radius:6px;cursor:pointer;font-family:Cairo,sans-serif;font-size:12px;">💬</button>
          <button onclick="window.open('https://www.google.com/maps/dir/?api=1&destination=${c.lat},${c.lng}','_blank')" style="padding:5px 10px;background:#1a2a3a;color:#63b3ed;border:1px solid #63b3ed;border-radius:6px;cursor:pointer;font-family:Cairo,sans-serif;font-size:12px;">🧭</button>
        </div>
      </div>`, {maxWidth:200});
    mapMarkers.push(marker);
  });

  // Stats
  const ms = $('mapStats');
  if (ms) {
    ms.innerHTML = [
      {l:'جهة على الخريطة', v:contacts.length, c:'blue'},
      {l:'لي منهم', v:forCount, c:'green'},
      {l:'علي لهم', v:onCount, c:'red'},
    ].map(s=>`<div class="stat-card"><div class="stat-val ${s.c}">${s.v}</div><div class="stat-label">${s.l}</div></div>`).join('');
  }

  if (contacts.length > 0) {
    const bounds = L.latLngBounds(contacts.map(c=>[c.lat,c.lng]));
    mapInstance.fitBounds(bounds, {padding:[40,40], maxZoom:14});
  }
}

function filterMap(el, type) {
  document.querySelectorAll('#mapFilterChips .chip').forEach(c=>c.classList.remove('active'));
  el.classList.add('active');
  mapTypeFilter = type;
  renderMapMarkers();
}

// Hook loadAll to refresh map if open
const _origLoadAll = loadAll;
async function loadAll() {
  const [contacts, txs] = await Promise.all([
    api('/api/contacts'),
    api('/api/transactions')
  ]);
  allContacts = contacts.data || [];
  allTx       = txs.data || [];
  populateContactSelects();
  if (mapInstance) renderMapMarkers();
}

// Update startApp to save user ref
const _origStartApp = startApp;
async function startApp(user) {
  currentUser = user;
  $('loginPage').style.display = 'none';
  $('mainApp').style.display = 'block';
  $('welcomeName').textContent = user?.name || 'مستخدم';
  $('todayDate').textContent = new Date().toLocaleDateString('ar-SA', {weekday:'long',year:'numeric',month:'long',day:'numeric'});
  await loadAll();
  showPage('home');
}
</script>
</body>
</html>"""

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return HTML

# ============================================================
# 5) API Routes — نقاط الاتصال مع قاعدة البيانات
# ============================================================

# ----- AUTH -----
@app.route('/api/register', methods=['POST'])
def register():
    """تسجيل مستخدم جديد"""
    data     = request.get_json()
    name     = data.get('name', '').strip()
    phone    = data.get('phone', '').strip()
    password = data.get('password', '')

    if not name or not phone or not password:
        return jsonify({'error': 'يرجى تعبئة جميع الحقول'})

    db = get_db()
    # تحقق أن الجوال غير مسجّل
    existing = db.execute(
        "SELECT id FROM users WHERE phone=?", (phone,)
    ).fetchone()
    if existing:
        return jsonify({'error': 'رقم الجوال مسجّل مسبقاً'})

    hashed = hash_password(password)
    db.execute(
        "INSERT INTO users (name,phone,password) VALUES (?,?,?)",
        (name, phone, hashed)
    )
    db.commit()

    user = db.execute(
        "SELECT * FROM users WHERE phone=?", (phone,)
    ).fetchone()
    session['user_id'] = user['id']
    session['user_name'] = user['name']

    # إشعار ترحيب
    add_notification(user['id'], 'مرحباً بك! 👋',
                     f'أهلاً {name}، ابدأ بإضافة جهاتك ومعاملاتك')

    return jsonify({'success': True, 'user': {'id': user['id'], 'name': user['name']}})


@app.route('/api/login', methods=['POST'])
def login():
    """تسجيل الدخول"""
    data     = request.get_json()
    phone    = data.get('phone', '').strip()
    password = data.get('password', '')

    db     = get_db()
    hashed = hash_password(password)
    user   = db.execute(
        "SELECT * FROM users WHERE phone=? AND password=?",
        (phone, hashed)
    ).fetchone()

    if not user:
        return jsonify({'error': 'الجوال أو كلمة المرور غير صحيحة'})

    session['user_id']   = user['id']
    session['user_name'] = user['name']
    return jsonify({'success': True, 'user': {'id': user['id'], 'name': user['name']}})


@app.route('/api/logout', methods=['POST'])
def logout():
    """تسجيل الخروج"""
    session.clear()
    return jsonify({'success': True})


@app.route('/api/me')
def me():
    """جلب بيانات الجلسة الحالية"""
    if 'user_id' in session:
        return jsonify({'user': {'id': session['user_id'], 'name': session['user_name']}})
    return jsonify({'user': None})


# ----- CONTACTS -----
@app.route('/api/contacts', methods=['GET', 'POST'])
@login_required
def contacts():
    db      = get_db()
    user_id = session['user_id']

    if request.method == 'GET':
        rows = db.execute(
            "SELECT * FROM contacts WHERE user_id=? ORDER BY name",
            (user_id,)
        ).fetchall()
        return jsonify({'data': [dict(r) for r in rows]})

    # POST — إضافة جهة
    data  = request.get_json()
    name  = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'الاسم مطلوب'})

    db.execute("""
        INSERT INTO contacts (user_id,name,phone,email,type,notes,lat,lng,location_text)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (user_id, name, data.get('phone',''), data.get('email',''),
         data.get('type','عميل'), data.get('notes',''),
         data.get('lat'), data.get('lng'), data.get('location_text',''))
    )
    db.commit()
    add_notification(user_id, 'جهة جديدة 👤', f'تمت إضافة {name}')
    return jsonify({'success': True})


@app.route('/api/contacts/<int:cid>', methods=['POST'])
@login_required
def contact_detail(cid):
    db      = get_db()
    user_id = session['user_id']
    data    = request.get_json()

    # حذف
    if data.get('_method') == 'DELETE':
        db.execute(
            "DELETE FROM contacts WHERE id=? AND user_id=?", (cid, user_id)
        )
        db.execute(
            "DELETE FROM transactions WHERE contact_id=? AND user_id=?", (cid, user_id)
        )
        db.commit()
        return jsonify({'success': True})

    # تعديل
    db.execute("""
        UPDATE contacts
        SET name=?,phone=?,email=?,type=?,notes=?
        WHERE id=? AND user_id=?""",
        (data.get('name'), data.get('phone',''), data.get('email',''),
         data.get('type','عميل'), data.get('notes',''), cid, user_id)
    )
    db.commit()
    return jsonify({'success': True})


# ----- TRANSACTIONS -----
@app.route('/api/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    db      = get_db()
    user_id = session['user_id']

    if request.method == 'GET':
        rows = db.execute("""
            SELECT t.*, c.name as contact_name
            FROM transactions t
            LEFT JOIN contacts c ON c.id=t.contact_id
            WHERE t.user_id=?
            ORDER BY t.created DESC""",
            (user_id,)
        ).fetchall()
        return jsonify({'data': [dict(r) for r in rows]})

    # POST — إضافة معاملة
    data       = request.get_json()
    contact_id = data.get('contact_id')
    amount     = float(data.get('amount', 0))
    tx_type    = data.get('type', 'incoming')

    if not contact_id or amount <= 0:
        return jsonify({'error': 'بيانات غير مكتملة'})

    contact = db.execute(
        "SELECT name FROM contacts WHERE id=?", (contact_id,)
    ).fetchone()
    contact_name = contact['name'] if contact else '—'

    db.execute("""
        INSERT INTO transactions
        (user_id,contact_id,contact_name,amount,currency,type,date,due_date,notes,status,reminder)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, contact_id, contact_name, amount,
         data.get('currency','ر.س'), tx_type,
         data.get('date', str(date.today())),
         data.get('due_date',''), data.get('notes',''),
         data.get('status','pending'), data.get('reminder','none'))
    )
    db.commit()
    label = 'لي من' if tx_type == 'incoming' else 'علي من'
    add_notification(user_id, 'معاملة جديدة 📋',
                     f'{label} {contact_name}: {amount} {data.get("currency","ر.س")}')
    return jsonify({'success': True})


@app.route('/api/transactions/<int:tid>', methods=['POST'])
@login_required
def transaction_detail(tid):
    db      = get_db()
    user_id = session['user_id']
    data    = request.get_json()

    if data.get('_method') == 'DELETE':
        db.execute(
            "DELETE FROM transactions WHERE id=? AND user_id=?", (tid, user_id)
        )
        db.commit()
        return jsonify({'success': True})

    db.execute("""
        UPDATE transactions
        SET contact_id=?,amount=?,currency=?,type=?,
            date=?,due_date=?,notes=?,status=?
        WHERE id=? AND user_id=?""",
        (data.get('contact_id'), data.get('amount'),
         data.get('currency','ر.س'), data.get('type'),
         data.get('date'), data.get('due_date',''),
         data.get('notes',''), data.get('status'),
         tid, user_id)
    )
    db.commit()
    return jsonify({'success': True})


# ----- STATEMENTS -----
@app.route('/api/statements', methods=['POST'])
@login_required
def statements():
    """توليد كشف حسابات مع فلترة"""
    db      = get_db()
    user_id = session['user_id']
    data    = request.get_json()

    query  = """
        SELECT t.*, c.name as contact_name, c.type as contact_type
        FROM transactions t
        LEFT JOIN contacts c ON c.id=t.contact_id
        WHERE t.user_id=?"""
    params = [user_id]

    if data.get('from'):
        query += " AND t.date >= ?"
        params.append(data['from'])
    if data.get('to'):
        query += " AND t.date <= ?"
        params.append(data['to'])
    if data.get('contact_id'):
        query += " AND t.contact_id = ?"
        params.append(data['contact_id'])
    if data.get('type'):
        query += " AND t.type = ?"
        params.append(data['type'])
    if data.get('status'):
        query += " AND t.status = ?"
        params.append(data['status'])

    query += " ORDER BY t.date DESC, t.created DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify({'data': [dict(r) for r in rows]})


# ----- EXPORT PDF -----
@app.route('/api/export/pdf')
@login_required
def export_pdf():
    """تصدير كشف الحسابات كـ PDF"""
    db      = get_db()
    user_id = session['user_id']
    from_d  = request.args.get('from', '')
    to_d    = request.args.get('to', '')
    cid     = request.args.get('contact_id', '')

    query  = "SELECT t.*, c.name as contact_name FROM transactions t LEFT JOIN contacts c ON c.id=t.contact_id WHERE t.user_id=?"
    params = [user_id]
    if from_d: query += " AND t.date>=?"; params.append(from_d)
    if to_d:   query += " AND t.date<=?"; params.append(to_d)
    if cid:    query += " AND t.contact_id=?"; params.append(cid)
    query += " ORDER BY t.date DESC"
    rows = db.execute(query, params).fetchall()

    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    # بناء PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles  = getSampleStyleSheet()
    gold    = colors.HexColor('#f6c90e')
    dark    = colors.HexColor('#1a2340')
    green_c = colors.HexColor('#48bb78')
    red_c   = colors.HexColor('#fc8181')

    story = []

    # العنوان
    title_style = ParagraphStyle('title', fontName='Helvetica-Bold',
                                  fontSize=20, alignment=TA_CENTER,
                                  textColor=dark, spaceAfter=8)
    sub_style   = ParagraphStyle('sub', fontName='Helvetica',
                                  fontSize=11, alignment=TA_CENTER,
                                  textColor=colors.grey, spaceAfter=20)

    story.append(Paragraph('&#x62D;&#x633;&#x627;&#x628;&#x64A; - Account Statement', title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=gold, spaceAfter=16))

    # ملخص
    for_me = sum(float(r['amount']) for r in rows if r['type']=='incoming' and r['status']!='settled')
    on_me  = sum(float(r['amount']) for r in rows if r['type']=='outgoing' and r['status']!='settled')
    net    = for_me - on_me

    summary_data = [
        ['Total For Me (لي)', f'{for_me:,.2f}'],
        ['Total On Me (علي)', f'{on_me:,.2f}'],
        ['Net Balance (الصافي)', f'{net:+,.2f}'],
        ['Transactions', str(len(rows))],
    ]
    summary_table = Table(summary_data, colWidths=[10*cm, 6*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('FONTNAME',    (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE',    (0,0), (-1,-1), 11),
        ('FONTNAME',    (1,0), (1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR',   (1,0), (1,0), green_c),
        ('TEXTCOLOR',   (1,1), (1,1), red_c),
        ('TEXTCOLOR',   (1,2), (1,2), green_c if net >= 0 else red_c),
        ('ALIGN',       (1,0), (1,-1), 'RIGHT'),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
        ('ROUNDEDCORNERS', [6]),
        ('TOPPADDING',  (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # جدول المعاملات
    table_data = [['Date', 'Contact', 'Notes', 'For Me', 'On Me', 'Status']]
    for r in rows:
        is_in  = r['type'] == 'incoming'
        status = {'pending':'Pending','partial':'Partial','settled':'Settled'}.get(r['status'],'')
        table_data.append([
            r['date'] or '—',
            r['contact_name'] or '—',
            (r['notes'] or '—')[:30],
            f"{r['amount']} {r['currency']}" if is_in else '—',
            f"{r['amount']} {r['currency']}" if not is_in else '—',
            status
        ])

    col_w = [2.5*cm, 3.5*cm, 4*cm, 3*cm, 3*cm, 2*cm]
    main_table = Table(table_data, colWidths=col_w, repeatRows=1)
    main_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0), dark),
        ('TEXTCOLOR',   (0,0), (-1,0), gold),
        ('FONTNAME',    (0,0), (-1,-1), 'Helvetica'),
        ('FONTNAME',    (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,0),  10),
        ('FONTSIZE',    (0,1), (-1,-1), 9),
        ('ALIGN',       (3,0), (4,-1), 'CENTER'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f9f9f9')]),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor('#e0e0e0')),
        ('TOPPADDING',  (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
    ]))
    story.append(main_table)

    # Footer
    story.append(Spacer(1, 20))
    footer_style = ParagraphStyle('footer', fontName='Helvetica',
                                   fontSize=9, alignment=TA_CENTER,
                                   textColor=colors.grey)
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f'Hesabi App | {user["name"]} | {datetime.now().strftime("%Y-%m-%d")}', footer_style))

    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f'hesabi_statement_{date.today()}.pdf')


# ----- EXPORT EXCEL -----
@app.route('/api/export/excel')
@login_required
def export_excel():
    """تصدير كشف الحسابات كـ Excel"""
    db      = get_db()
    user_id = session['user_id']
    from_d  = request.args.get('from', '')
    to_d    = request.args.get('to', '')
    cid     = request.args.get('contact_id', '')

    query  = "SELECT t.*, c.name as contact_name, c.type as contact_type FROM transactions t LEFT JOIN contacts c ON c.id=t.contact_id WHERE t.user_id=?"
    params = [user_id]
    if from_d: query += " AND t.date>=?"; params.append(from_d)
    if to_d:   query += " AND t.date<=?"; params.append(to_d)
    if cid:    query += " AND t.contact_id=?"; params.append(cid)
    rows = db.execute(query, params).fetchall()

    user = db.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()

    wb = Workbook()
    ws = wb.active
    ws.title = "كشف الحسابات"
    ws.sheet_view.rightToLeft = True

    # ألوان
    gold_fill  = PatternFill("solid", fgColor="F6C90E")
    dark_fill  = PatternFill("solid", fgColor="1A2340")
    green_fill = PatternFill("solid", fgColor="E8F5E9")
    red_fill   = PatternFill("solid", fgColor="FFEBEE")
    header_font = Font(bold=True, size=11)
    gold_font   = Font(bold=True, size=11, color="F6C90E")
    white_font  = Font(bold=True, size=11, color="FFFFFF")
    center      = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    # ----- العنوان -----
    ws.merge_cells('A1:H1')
    ws['A1'] = f'حسابي – كشف الحسابات | {user["name"]}' if user else 'حسابي – كشف الحسابات'
    ws['A1'].font      = Font(bold=True, size=16, color="F6C90E")
    ws['A1'].fill      = dark_fill
    ws['A1'].alignment = center
    ws.row_dimensions[1].height = 40

    ws.merge_cells('A2:H2')
    ws['A2'] = f'تاريخ التصدير: {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    ws['A2'].font      = Font(size=10, color="AAAAAA")
    ws['A2'].fill      = PatternFill("solid", fgColor="0F1628")
    ws['A2'].alignment = center
    ws.row_dimensions[2].height = 25

    # ----- الملخص -----
    for_me = sum(float(r['amount']) for r in rows if r['type']=='incoming' and r['status']!='settled')
    on_me  = sum(float(r['amount']) for r in rows if r['type']=='outgoing' and r['status']!='settled')
    net    = for_me - on_me

    ws.row_dimensions[4].height = 28
    summary = [
        ('A4', 'إجمالي لي (مستحق)', f'{for_me:,.2f} ر.س', '48BB78'),
        ('C4', 'إجمالي علي (مديونية)', f'{on_me:,.2f} ر.س', 'FC8181'),
        ('E4', 'الصافي', f'{net:+,.2f} ر.س', '48BB78' if net >= 0 else 'FC8181'),
        ('G4', 'عدد المعاملات', str(len(rows)), 'F6C90E'),
    ]
    for cell_addr, label, value, color in summary:
        lbl = ws[cell_addr]
        val = ws[cell_addr[0] + str(int(cell_addr[1:])+0)]
        # Merge 2 cells for each
        col = cell_addr[0]
        row = int(cell_addr[1:])
        next_col = chr(ord(col) + 1)
        ws.merge_cells(f'{col}{row}:{next_col}{row}')
        ws[f'{col}{row}'] = f'{label}: {value}'
        ws[f'{col}{row}'].font = Font(bold=True, size=11, color=color)
        ws[f'{col}{row}'].fill = PatternFill("solid", fgColor="151D35")
        ws[f'{col}{row}'].alignment = center

    # ----- رأس الجدول -----
    headers = ['التاريخ','الجهة','النوع','المبلغ','العملة','البيان','الحالة','الاستحقاق']
    for col, hdr in enumerate(headers, 1):
        cell = ws.cell(row=6, column=col, value=hdr)
        cell.font      = Font(bold=True, size=10, color="000000")
        cell.fill      = gold_fill
        cell.alignment = center
        cell.border    = thin_border
    ws.row_dimensions[6].height = 28

    # ----- البيانات -----
    status_labels = {'pending':'معلقة','partial':'جزئية','settled':'مسوّاة'}
    type_labels   = {'incoming':'لي 📥','outgoing':'علي 📤'}

    for i, r in enumerate(rows, 7):
        is_in   = r['type'] == 'incoming'
        row_fill= green_fill if is_in else red_fill
        values  = [
            r['date'] or '',
            r['contact_name'] or '',
            type_labels.get(r['type'], r['type']),
            float(r['amount']),
            r['currency'],
            r['notes'] or '',
            status_labels.get(r['status'], r['status']),
            r['due_date'] or '',
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=i, column=col, value=val)
            cell.fill      = row_fill if col <= 4 else PatternFill()
            cell.alignment = right_align
            cell.border    = thin_border
            if col == 4:
                cell.font   = Font(bold=True, color="1B5E20" if is_in else "B71C1C")
                cell.number_format = '#,##0.00'
        ws.row_dimensions[i].height = 22

    # ----- عرض الأعمدة -----
    col_widths = [14, 20, 12, 14, 10, 28, 12, 14]
    for col, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    # ----- إجماليات -----
    total_row = len(rows) + 8
    ws.merge_cells(f'A{total_row}:C{total_row}')
    ws[f'A{total_row}'] = 'الإجماليات'
    ws[f'A{total_row}'].font = Font(bold=True, size=11)
    ws[f'A{total_row}'].fill = dark_fill
    ws[f'A{total_row}'].alignment = center
    ws.cell(row=total_row, column=4, value=for_me).font = Font(bold=True, color="48BB78", size=11)
    ws.cell(row=total_row, column=4).number_format = '#,##0.00'
    ws.row_dimensions[total_row].height = 28

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'hesabi_{date.today()}.xlsx')


# ----- NOTIFICATIONS -----
@app.route('/api/notifications')
@login_required
def notifications():
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 50",
        (session['user_id'],)
    ).fetchall()
    return jsonify({'data': [dict(r) for r in rows]})


@app.route('/api/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifs():
    db = get_db()
    db.execute(
        "UPDATE notifications SET is_read=1 WHERE user_id=?",
        (session['user_id'],)
    )
    db.commit()
    return jsonify({'success': True})


# ----- PROFILE -----
@app.route('/api/profile', methods=['POST'])
@login_required
def update_profile():
    """تعديل بيانات المستخدم"""
    data     = request.get_json()
    name     = data.get('name', '').strip()
    phone    = data.get('phone', '').strip()
    business = data.get('business', '').strip()
    user_id  = session['user_id']

    if not name:
        return jsonify({'error': 'الاسم مطلوب'})

    db = get_db()
    db.execute(
        "UPDATE users SET name=?, phone=?, business=? WHERE id=?",
        (name, phone, business, user_id)
    )
    db.commit()
    session['user_name'] = name
    return jsonify({'success': True})


# ----- CHANGE PASSWORD -----
@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    """تغيير كلمة المرور"""
    data         = request.get_json()
    current_pass = data.get('current_password', '')
    new_pass     = data.get('new_password', '')
    user_id      = session['user_id']

    if not current_pass or not new_pass:
        return jsonify({'error': 'يرجى تعبئة جميع الحقول'})

    if len(new_pass) < 6:
        return jsonify({'error': 'كلمة المرور الجديدة قصيرة جداً'})

    db   = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id=? AND password=?",
        (user_id, hash_password(current_pass))
    ).fetchone()

    if not user:
        return jsonify({'error': 'كلمة المرور الحالية غير صحيحة'})

    db.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_pass), user_id)
    )
    db.commit()
    return jsonify({'success': True})


# ----- SETTINGS -----
@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    """جلب وحفظ إعدادات المستخدم"""
    user_id = session['user_id']

    if request.method == 'GET':
        data = get_user_settings(user_id)
        return jsonify({'data': data})

    # POST — حفظ الإعدادات
    new_data = request.get_json()
    current  = get_user_settings(user_id)
    current.update(new_data)
    save_user_settings(user_id, current)
    return jsonify({'success': True})


# ----- SEARCH -----
@app.route('/api/search')
@login_required
def search():
    """بحث شامل في الجهات والمعاملات"""
    q       = request.args.get('q', '').strip()
    user_id = session['user_id']

    if not q or len(q) < 2:
        return jsonify({'contacts': [], 'transactions': []})

    db = get_db()

    contacts = db.execute("""
        SELECT * FROM contacts
        WHERE user_id=? AND (name LIKE ? OR phone LIKE ?)
        LIMIT 5""",
        (user_id, f'%{q}%', f'%{q}%')
    ).fetchall()

    txs = db.execute("""
        SELECT t.*, c.name as contact_name
        FROM transactions t
        LEFT JOIN contacts c ON c.id=t.contact_id
        WHERE t.user_id=? AND (c.name LIKE ? OR t.notes LIKE ?)
        ORDER BY t.created DESC LIMIT 5""",
        (user_id, f'%{q}%', f'%{q}%')
    ).fetchall()

    return jsonify({
        'contacts':     [dict(r) for r in contacts],
        'transactions': [dict(r) for r in txs]
    })


# ============================================================
# 6) تشغيل التطبيق
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("  💰 حسابي — تطبيق محاسبة بلغة Python")
    print("=" * 50)
    init_db()
    print("🌐 افتح المتصفح على: http://localhost:5000")
    print("📁 قاعدة البيانات:   hesabi.db")
    print("🛑 لإيقاف التطبيق:   Ctrl+C")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
