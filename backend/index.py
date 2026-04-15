from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import os
import sqlite3
from datetime import datetime, timedelta
import jwt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

DB_PATH = "agency_db.sqlite"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            website_url TEXT,
            industry TEXT,
            monthly_ad_spend INTEGER,
            email TEXT,
            phone TEXT,
            contact_person TEXT,
            lead_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            status TEXT DEFAULT 'active',
            budget INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class LeadRequest(BaseModel):
    website_url: str
    industry: str
    company_name: str = None
    monthly_ad_spend: int = None

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "agency-automation-engine"}

@app.post("/api/auth/register")
async def register(request: OAuth2PasswordRequestForm = Depends()):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (request.username,))
        if c.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="User already exists")
        
        c.execute("INSERT INTO users (email, password, name) VALUES (?, ?, ?)",
                  (request.username, request.password, request.username.split('@')[0]))
        conn.commit()
        conn.close()
        
        access_token = jwt.encode(
            {"sub": request.username, "exp": datetime.utcnow() + timedelta(minutes=30)},
            os.getenv("SECRET_KEY", "secret-key")
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/token")
async def login(request: OAuth2PasswordRequestForm = Depends()):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (request.username,))
    user = c.fetchone()
    conn.close()
    
    if not user or user['password'] != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = jwt.encode(
        {"sub": request.username, "exp": datetime.utcnow() + timedelta(minutes=30)},
        os.getenv("SECRET_KEY", "secret-key")
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/add-lead")
async def add_lead(request: LeadRequest):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO leads (website_url, industry, company_name, monthly_ad_spend, status)
        VALUES (?, ?, ?, ?, 'new')
    """, (request.website_url, request.industry, request.company_name, request.monthly_ad_spend))
    conn.commit()
    lead_id = c.lastrowid
    conn.close()
    return {"lead_id": lead_id, "message": "Lead added successfully"}

@app.get("/api/leads")
async def get_leads(status: str = None):
    conn = get_db()
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        c.execute("SELECT * FROM leads ORDER BY created_at DESC")
    leads = c.fetchall()
    conn.close()
    return {"leads": [dict(row) for row in leads]}

@app.get("/api/campaigns")
async def get_campaigns():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
    campaigns = c.fetchall()
    conn.close()
    return {"campaigns": [dict(row) for row in campaigns]}

@app.get("/api/invoices")
async def get_invoices():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM invoices ORDER BY created_at DESC")
    invoices = c.fetchall()
    conn.close()
    return {"invoices": [dict(row) for row in invoices]}
