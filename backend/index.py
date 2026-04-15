from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import json
import os
import requests
from dotenv import load_dotenv
from database import db
from tasks import celery_app
from email import send_cold_email, send_invoice_email
from datetime import datetime, timedelta
import jwt
import bcrypt
from config_llm import get_ollama_llm

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://frontend-mu-tan-45.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

class AgentRequest(BaseModel):
    target_url: str
    industry: str

class LeadRequest(BaseModel):
    website_url: str
    industry: str
    company_name: str = None
    monthly_ad_spend: int = None

@app.on_event("startup")
async def startup_event():
    db.connect()

@app.on_event("shutdown")
async def shutdown_event():
    db.close()

@app.post("/api/run-swarm")
async def execute_swarm(request: AgentRequest):
    try:
        llm = get_ollama_llm()
        def event_stream():
            for thought in run_acquisition_engine_stream(request.target_url, request.industry, llm):
                yield f"data: {json.dumps({'text': thought})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/add-lead")
async def add_lead(request: LeadRequest):
    try:
        lead_data = {
            'website_url': request.website_url,
            'industry': request.industry,
            'company_name': request.company_name,
            'monthly_ad_spend': request.monthly_ad_spend,
            'email': None,
            'phone': None,
            'contact_person': None,
            'lead_score': 0,
            'status': 'new'
        }
        lead_id = db.insert_lead(lead_data)
        return {"lead_id": lead_id, "message": "Lead added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leads")
async def get_leads(status: str = None):
    try:
        if status:
            db._execute("""
                SELECT * FROM leads
                WHERE status = %s
                ORDER BY created_at DESC
            """, (status,))
        else:
            db._execute("""
                SELECT * FROM leads
                ORDER BY created_at DESC
            """)
        leads = db.cursor.fetchall()
        return {"leads": rows_to_dicts(leads)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-lead-generation")
async def schedule_lead_generation(lead_ids: list):
    try:
        for lead_id in lead_ids:
            celery_app.send_task('lead_generation_task', args=[lead_id])
        return {"message": f"Scheduled lead generation for {len(lead_ids)} leads"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns")
async def get_campaigns():
    try:
        db._execute("""
            SELECT * FROM campaigns
            ORDER BY created_at DESC
        """)
        return {"campaigns": db.fetch_all_dicts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/invoices")
async def get_invoices():
    try:
        db._execute("""
            SELECT * FROM invoices
            ORDER BY created_at DESC
        """)
        return {"invoices": db.fetch_all_dicts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "agency-automation-engine",
        "database": "connected" if db.connection else "disconnected",
        "database_type": "sqlite" if db.is_sqlite else "postgres"
    }

@app.post("/api/auth/register")
async def register(request: OAuth2PasswordRequestForm = Depends()):
    try:
        user = db.authenticate_user(request.username, request.password)
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )

        user_id = db.create_user(
            email=request.username,
            password=request.password,
            name=request.username.split('@')[0]
        )

        if user_id:
            access_token_expires = timedelta(minutes=30)
            access_token = jwt.encode(
                {"sub": request.username, "exp": datetime.utcnow() + access_token_expires},
                os.getenv("SECRET_KEY", "your-secret-key")
            )
            return {"access_token": access_token, "token_type": "bearer"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/auth/token")
async def login(request: OAuth2PasswordRequestForm = Depends()):
    try:
        user = db.authenticate_user(request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=30)
        access_token = jwt.encode(
            {"sub": request.username, "exp": datetime.utcnow() + access_token_expires},
            os.getenv("SECRET_KEY", "your-secret-key")
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def rows_to_dicts(rows):
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    if hasattr(rows[0], 'keys'):
        return [dict(row) for row in rows]
    columns = [col.name if hasattr(col, 'name') else col[0] for col in db.cursor.description]
    return [dict(zip(columns, row)) for row in rows]
