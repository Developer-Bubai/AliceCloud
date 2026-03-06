# AliceCloud Setup Script
# Run this in PowerShell as: .\setup.ps1

Write-Host "Creating AliceCloud files..." -ForegroundColor Cyan

# Create folders
New-Item -ItemType Directory -Force -Path "C:\AliceCloud\backend\app"
New-Item -ItemType Directory -Force -Path "C:\AliceCloud\frontend"
New-Item -ItemType Directory -Force -Path "C:\AliceCloud\data"

# ── __init__.py
Set-Content "C:\AliceCloud\backend\app\__init__.py" "# AliceCloud"

# ── requirements.txt
Set-Content "C:\AliceCloud\backend\requirements.txt" @"
fastapi==0.115.0
uvicorn==0.30.6
httpx==0.27.2
python-dotenv==1.0.1
pydantic==2.8.2
PyJWT==2.9.0
"@

# ── render.yaml
Set-Content "C:\AliceCloud\render.yaml" @"
services:
  - type: web
    name: alicecloud-api
    env: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port `$PORT
"@

# ── vercel.json
Set-Content "C:\AliceCloud\frontend\vercel.json" @"
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
"@

# ── .gitignore
Set-Content "C:\AliceCloud\.gitignore" @"
.env
__pycache__/
*.pyc
data/
.DS_Store
venv/
node_modules/
"@

# ── auth.py
Set-Content "C:\AliceCloud\backend\app\auth.py" @"
import os, jwt, secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "alice-secret-bubai-2025")
JWT_EXPIRE = 30

security = HTTPBearer(auto_error=False)

def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token. Please login.")

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    if not credentials:
        raise HTTPException(401, "Not authenticated. Please login at /auth/google")
    payload = verify_token(credentials.credentials)
    from app.database import db
    user = db.get_user(payload["user_id"])
    if not user:
        raise HTTPException(401, "User not found.")
    return user

import time
from collections import defaultdict
_req_log = defaultdict(list)
PLAN_LIMITS = {"free": 100, "pro": 2000, "owner": 99999}

def check_limit(user_id: str, plan: str = "free"):
    now = time.time()
    day = 86400
    limit = PLAN_LIMITS.get(plan, 100)
    _req_log[user_id] = [t for t in _req_log[user_id] if now - t < day]
    used = len(_req_log[user_id])
    remaining = max(0, limit - used)
    if used >= limit:
        return False, f"Daily limit of {limit} messages reached. Resets in 24h.", 0
    _req_log[user_id].append(now)
    return True, "ok", remaining - 1
"@

# ── database.py
Set-Content "C:\AliceCloud\backend\app\database.py" @"
import json, os, secrets
from datetime import datetime, date

DB_FILE = "data/alice_db.json"

class Database:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(DB_FILE):
            self._save({"users":{},"keys":{},"chats":{},"feedback":{},"stats":{"total_requests":0,"total_users":0,"total_tokens":0}})

    def _load(self):
        try:
            with open(DB_FILE) as f: return json.load(f)
        except:
            return {"users":{},"keys":{},"chats":{},"feedback":{},"stats":{"total_requests":0,"total_users":0,"total_tokens":0}}

    def _save(self, data):
        with open(DB_FILE,"w") as f: json.dump(data, f, indent=2)

    def upsert_user(self, google_id, email, name, picture):
        data = self._load()
        for uid, u in data["users"].items():
            if u.get("google_id") == google_id:
                u.update({"name":name,"picture":picture,"last_login":datetime.utcnow().isoformat()})
                self._save(data)
                return {**u,"id":uid}
        uid = f"user_{secrets.token_hex(8)}"
        data["users"][uid] = {"id":uid,"google_id":google_id,"email":email,"name":name,"picture":picture,"plan":"free","created_at":datetime.utcnow().isoformat(),"last_login":datetime.utcnow().isoformat()}
        data["stats"]["total_users"] += 1
        self._save(data)
        return {**data["users"][uid],"id":uid}

    def get_user(self, user_id):
        data = self._load()
        u = data["users"].get(user_id)
        return {**u,"id":user_id} if u else None

    def create_api_key(self, user_id, name):
        data = self._load()
        key = f"ak-{secrets.token_urlsafe(32)}"
        kid = f"key_{secrets.token_hex(6)}"
        data["keys"][key] = {"id":kid,"user_id":user_id,"name":name,"created_at":datetime.utcnow().isoformat(),"active":True,"requests":0}
        self._save(data)
        return key

    def verify_api_key(self, key):
        data = self._load()
        k = data["keys"].get(key)
        if k and k.get("active"):
            return self.get_user(k["user_id"])
        return None

    def get_user_keys(self, user_id):
        data = self._load()
        return [{"id":v["id"],"name":v["name"],"created_at":v["created_at"],"requests":v.get("requests",0)} for k,v in data["keys"].items() if v["user_id"]==user_id and v.get("active")]

    def delete_api_key(self, user_id, key_id):
        data = self._load()
        for k,v in data["keys"].items():
            if v["id"]==key_id and v["user_id"]==user_id:
                v["active"] = False
        self._save(data)

    def log_chat(self, user_id, message_id, model, tokens, latency_ms):
        data = self._load()
        today = str(date.today())
        if user_id not in data["chats"]:
            data["chats"][user_id] = {"total":0,"today":0,"today_date":today,"models":{}}
        c = data["chats"][user_id]
        if c.get("today_date") != today:
            c["today"] = 0
            c["today_date"] = today
        c["total"] += 1
        c["today"] += 1
        c["models"][model] = c["models"].get(model,0) + 1
        data["stats"]["total_requests"] += 1
        data["stats"]["total_tokens"] += tokens
        self._save(data)

    def get_user_stats(self, user_id):
        data = self._load()
        c = data["chats"].get(user_id, {})
        today = str(date.today())
        today_count = c.get("today",0) if c.get("today_date")==today else 0
        return {"total_requests":c.get("total",0),"today_requests":today_count,"models_used":c.get("models",{})}

    def save_feedback(self, user_id, message_id, rating, comment):
        data = self._load()
        fid = f"fb_{secrets.token_hex(6)}"
        data["feedback"][fid] = {"user_id":user_id,"message_id":message_id,"rating":rating,"comment":comment,"created_at":datetime.utcnow().isoformat()}
        self._save(data)

    def get_public_stats(self):
        data = self._load()
        s = data["stats"]
        return {"total_requests":s.get("total_requests",0),"total_users":s.get("total_users",0),"total_tokens":s.get("total_tokens",0),"status":"operational","providers":4}

db = Database()
"@

# ── router.py
Set-Content "C:\AliceCloud\backend\app\router.py" @"
import os, httpx
from typing import List, Dict

GROQ_KEY   = os.getenv("GROQ_API_KEY",   "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
COHERE_KEY = os.getenv("COHERE_API_KEY", "")
HF_KEY     = os.getenv("HF_API_KEY",     "")

MODEL_MAP = {
    "alice-flash":    ("groq",        "llama-3.1-8b-instant"),
    "alice-smart":    ("gemini",      "gemini-1.5-flash"),
    "alice-pro":      ("gemini",      "gemini-1.5-pro"),
    "alice-balanced": ("cohere",      "command-r"),
    "alice-free":     ("huggingface", "mistralai/Mistral-7B-Instruct-v0.3"),
    "gpt-3.5-turbo":  ("groq",        "llama-3.1-8b-instant"),
    "gpt-4":          ("gemini",      "gemini-1.5-pro"),
    "gpt-4o":         ("gemini",      "gemini-1.5-flash"),
    "gpt-4o-mini":    ("groq",        "llama-3.1-8b-instant"),
}

async def _groq(messages, model, temperature, max_tokens):
    if not GROQ_KEY: return None
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {GROQ_KEY}"},json={"model":model,"messages":messages,"temperature":temperature,"max_tokens":max_tokens})
            d = r.json()
            return {"content":d["choices"][0]["message"]["content"],"provider":"groq","model_used":f"groq/{model}","tokens":d.get("usage",{}).get("total_tokens",0)}
    except Exception as e:
        print(f"[Groq] {e}"); return None

async def _gemini(messages, model, temperature, max_tokens):
    if not GEMINI_KEY: return None
    try:
        contents, system = [], ""
        for m in messages:
            if m["role"]=="system": system=m["content"]
            elif m["role"]=="user": contents.append({"parts":[{"text":m["content"]}],"role":"user"})
            elif m["role"]=="assistant": contents.append({"parts":[{"text":m["content"]}],"role":"model"})
        payload = {"contents":contents,"generationConfig":{"temperature":temperature,"maxOutputTokens":max_tokens}}
        if system: payload["systemInstruction"]={"parts":[{"text":system}]}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}",json=payload)
            d = r.json()
            text = d["candidates"][0]["content"]["parts"][0]["text"]
            return {"content":text,"provider":"gemini","model_used":f"gemini/{model}","tokens":len(text.split())*2}
    except Exception as e:
        print(f"[Gemini] {e}"); return None

async def _cohere(messages, model, temperature, max_tokens):
    if not COHERE_KEY: return None
    try:
        history, user_msg = [], ""
        for m in messages:
            if m["role"]=="user": user_msg=m["content"]
            elif m["role"]=="assistant": history.append({"role":"CHATBOT","message":m["content"]})
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post("https://api.cohere.ai/v1/chat",headers={"Authorization":f"Bearer {COHERE_KEY}"},json={"model":model,"message":user_msg,"chat_history":history,"temperature":temperature,"max_tokens":max_tokens})
            d = r.json()
            return {"content":d.get("text",""),"provider":"cohere","model_used":f"cohere/{model}","tokens":d.get("meta",{}).get("billed_units",{}).get("output_tokens",0)}
    except Exception as e:
        print(f"[Cohere] {e}"); return None

async def _huggingface(messages, model, temperature, max_tokens):
    if not HF_KEY: return None
    try:
        prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"https://api-inference.huggingface.co/models/{model}",headers={"Authorization":f"Bearer {HF_KEY}"},json={"inputs":prompt,"parameters":{"max_new_tokens":max_tokens,"temperature":temperature,"return_full_text":False}})
            d = r.json()
            text = d[0]["generated_text"].strip() if isinstance(d,list) else str(d)
            return {"content":text,"provider":"huggingface","model_used":f"hf/{model}","tokens":len(text.split())}
    except Exception as e:
        print(f"[HF] {e}"); return None

async def route_request(messages, model="alice-flash", temperature=0.7, max_tokens=500):
    provider, real_model = MODEL_MAP.get(model, ("groq","llama-3.1-8b-instant"))
    order = [provider] + [p for p in ["groq","gemini","cohere","huggingface"] if p != provider]
    for p in order:
        result = None
        if   p=="groq":        result = await _groq(messages, real_model if provider=="groq" else "llama-3.1-8b-instant", temperature, max_tokens)
        elif p=="gemini":      result = await _gemini(messages, real_model if provider=="gemini" else "gemini-1.5-flash", temperature, max_tokens)
        elif p=="cohere":      result = await _cohere(messages, real_model if provider=="cohere" else "command-r", temperature, max_tokens)
        elif p=="huggingface": result = await _huggingface(messages, real_model if provider=="huggingface" else "mistralai/Mistral-7B-Instruct-v0.3", temperature, max_tokens)
        if result:
            result["fallback"] = (p != provider)
            return result
    return {"content":"AliceAPI is temporarily unavailable. Please try again.","provider":"error","model_used":"none","tokens":0,"fallback":True}
"@

Write-Host ""
Write-Host "All files created!" -ForegroundColor Green
Write-Host "Now run: cd C:\AliceCloud && git add . && git commit -m 'Add all files' && git push origin main" -ForegroundColor Yellow
