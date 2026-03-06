from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
import os, time, secrets, httpx
from datetime import datetime
from app.router import route_request
from app.auth import get_current_user, create_token, check_limit
from app.database import db

app = FastAPI(title="AliceAPI", version="2.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL          = os.getenv("BACKEND_URL",  "http://localhost:8000")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "alice-flash"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 500

class APIKeyRequest(BaseModel):
    name: str

@app.get("/health")
async def health():
    return {"status":"online","service":"AliceAPI","version":"2.0.0","timestamp":datetime.utcnow().isoformat()}

@app.get("/auth/google")
async def google_login():
    scope = "openid email profile"
    redirect_uri = f"{BACKEND_URL}/auth/google/callback"
    url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&access_type=offline"
    return RedirectResponse(url)

@app.get("/auth/google/callback")
async def google_callback(code: str):
    try:
        redirect_uri = f"{BACKEND_URL}/auth/google/callback"
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://oauth2.googleapis.com/token",
                data={"code":code,"client_id":GOOGLE_CLIENT_ID,"client_secret":GOOGLE_CLIENT_SECRET,"redirect_uri":redirect_uri,"grant_type":"authorization_code"})
            token_data = token_resp.json()
            user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization":f"Bearer {token_data.get('access_token')}"})
            user_info = user_resp.json()
        user = db.upsert_user(google_id=user_info["id"],email=user_info["email"],name=user_info.get("name","User"),picture=user_info.get("picture",""))
        jwt_token = create_token({"user_id":user["id"],"email":user["email"]})
        return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={jwt_token}")
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/auth/error?msg={str(e)[:100]}")

@app.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    return user

@app.post("/chat")
async def simple_chat(request: Request, user=Depends(get_current_user)):
    body = await request.json()
    message = body.get("message","")
    history = body.get("history",[])
    model   = body.get("model","alice-flash")
    if not message:
        raise HTTPException(400,"message required")
    allowed, msg, remaining = check_limit(user["id"], user.get("plan","free"))
    if not allowed:
        raise HTTPException(429, msg)
    messages = history[-10:] + [{"role":"user","content":message}]
    result = await route_request(messages=messages, model=model, temperature=0.7, max_tokens=500)
    msg_id = f"msg_{secrets.token_hex(8)}"
    db.log_chat(user["id"], msg_id, result["model_used"], result.get("tokens",0), 0)
    return {"reply":result["content"],"model":result["model_used"],"provider":result["provider"],"msg_id":msg_id,"remaining":remaining,"ok":True}

@app.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    stats = db.get_user_stats(user["id"])
    limit = 100 if user.get("plan","free")=="free" else 2000
    return {"user":user,"stats":stats,"plan":user.get("plan","free"),"daily_limit":limit,"used_today":stats.get("today_requests",0),"remaining":max(0,limit-stats.get("today_requests",0))}

@app.get("/stats")
async def public_stats():
    return db.get_public_stats()

@app.post("/keys/create")
async def create_key(req: APIKeyRequest, user=Depends(get_current_user)):
    key = db.create_api_key(user["id"], req.name)
    return {"api_key":key,"name":req.name,"message":"Save this — shown only once!"}

@app.get("/v1/models")
async def list_models(user=Depends(get_current_user)):
    return {"object":"list","data":[
        {"id":"alice-flash","provider":"groq","speed":"fastest"},
        {"id":"alice-smart","provider":"gemini","speed":"smart"},
        {"id":"alice-pro","provider":"gemini-pro","speed":"powerful"},
        {"id":"alice-balanced","provider":"cohere","speed":"balanced"},
        {"id":"gpt-3.5-turbo","provider":"groq","speed":"fastest"},
        {"id":"gpt-4","provider":"gemini-pro","speed":"powerful"},
    ]}