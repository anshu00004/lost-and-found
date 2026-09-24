# 🔍 Lost & Found Portal — FastAPI Backend

A production-ready REST API for a Lost & Found management system built with **FastAPI**, **SQLAlchemy 2**, and **MySQL**.

---

## ✨ Features

| Feature | Details |
|---|---|
| **JWT Auth** | Access + Refresh tokens with rotation & revocation |
| **Lost Item Reports** | Create, read, update, delete, search & filter |
| **Found Item Reports** | Create, read, update, delete, search & filter |
| **Ownership Claims** | Submit → Admin review → Approve / Reject |
| **Auto-cascades** | Approved claim → both items auto-resolved; other claims auto-rejected |
| **Admin Panel** | User management, role promotion, platform statistics |
| **Pagination** | All list endpoints support `page` / `page_size` |
| **Search** | Full-text keyword search on title, description, location |
| **Alembic** | Database migrations included |

---

## 🗂️ Project Structure

```
lost-and-found/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routers, lifespan
│   ├── config.py        # Pydantic settings (reads .env)
│   ├── database.py      # SQLAlchemy engine + session
│   ├── models.py        # ORM models (User, LostItem, FoundItem, Claim, RefreshToken)
│   ├── schemas.py       # Pydantic v2 request/response schemas
│   ├── auth.py          # Password hashing, JWT helpers, dependencies
│   └── routers/
│       ├── auth.py          # /api/v1/auth/*
│       ├── lost_items.py    # /api/v1/lost-items/*
│       ├── found_items.py   # /api/v1/found-items/*
│       ├── claims.py        # /api/v1/claims/*
│       └── admin.py         # /api/v1/admin/*
├── alembic/
│   └── env.py
├── alembic.ini
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
# Also install pydantic-settings (not bundled with pydantic v2 by default)
pip install pydantic-settings
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your MySQL credentials and a strong SECRET_KEY
```

### 4. Create the MySQL database

```sql
CREATE DATABASE lost_and_found_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. Run database migrations (Alembic) **or** let the app auto-create tables

**Option A — Alembic (recommended for production):**
```bash
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

**Option B — Auto-create (dev only, handled by `lifespan` in `main.py`):**
Tables are created automatically on startup via `create_all_tables()`.

### 6. Start the dev server

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for interactive Swagger UI.

---

## 📡 API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | ❌ | Register new user |
| POST | `/auth/login` | ❌ | Login → access + refresh tokens |
| POST | `/auth/refresh` | ❌ | Rotate refresh token |
| POST | `/auth/logout` | ✅ | Revoke refresh token |
| GET | `/auth/me` | ✅ | Get own profile |
| PATCH | `/auth/me` | ✅ | Update own profile |
| POST | `/auth/change-password` | ✅ | Change password |

### Lost Items

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/lost-items/` | ✅ | Report a lost item |
| GET | `/lost-items/` | ✅ | List / search (paginated) |
| GET | `/lost-items/{id}` | ✅ | Get by ID |
| PATCH | `/lost-items/{id}` | ✅ Owner/Admin | Update |
| DELETE | `/lost-items/{id}` | ✅ Owner/Admin | Delete |
| GET | `/lost-items/my/reports` | ✅ | Own reports |

### Found Items

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/found-items/` | ✅ | Report a found item |
| GET | `/found-items/` | ✅ | List / search (paginated) |
| GET | `/found-items/{id}` | ✅ | Get by ID |
| PATCH | `/found-items/{id}` | ✅ Owner/Admin | Update |
| DELETE | `/found-items/{id}` | ✅ Owner/Admin | Delete |
| GET | `/found-items/my/reports` | ✅ | Own reports |

### Claims

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/claims/` | ✅ | Submit a claim |
| GET | `/claims/` | ✅ | List claims (admin = all, user = own) |
| GET | `/claims/{id}` | ✅ Owner/Admin | Full claim detail |
| GET | `/claims/{id}/status` | ✅ Owner/Admin | Lightweight status poll |
| PATCH | `/claims/{id}/review` | ✅ Admin | Approve / Reject |
| DELETE | `/claims/{id}` | ✅ Owner | Withdraw (pending only) |

### Admin

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/users` | ✅ Admin | List all users |
| GET | `/admin/users/{id}` | ✅ Admin | Get user |
| PATCH | `/admin/users/{id}/activate` | ✅ Admin | Re-activate account |
| PATCH | `/admin/users/{id}/deactivate` | ✅ Admin | Deactivate account |
| PATCH | `/admin/users/{id}/promote` | ✅ Admin | Grant admin role |
| GET | `/admin/stats` | ✅ Admin | Platform statistics |

---

## 🔐 Authentication Flow

```
POST /auth/register → User created
POST /auth/login    → { access_token, refresh_token }

  ↓ Include in subsequent requests:
  Authorization: Bearer <access_token>

POST /auth/refresh  → New { access_token, refresh_token } (old refresh revoked)
POST /auth/logout   → Refresh token revoked
```

---

## 🔄 Claim Lifecycle

```
User submits claim (POST /claims/)
        │
        ▼
  Status: PENDING
  LostItem & FoundItem → MATCHED
        │
        ▼
  Admin reviews (PATCH /claims/{id}/review)
        │
   ┌────┴────┐
APPROVED   REJECTED
   │           │
   ▼           ▼
Both items  If no other
→ RESOLVED  active claims:
            items → OPEN

All other PENDING claims
on same items → REJECTED
```

---

## 🛠️ Item Categories

`electronics` · `clothing` · `accessories` · `documents` · `bags` · `keys` · `wallet` · `jewelry` · `pet` · `other`

## 📊 Item Statuses

`open` · `matched` · `resolved` · `expired`

## 📋 Claim Statuses

`pending` · `approved` · `rejected`
