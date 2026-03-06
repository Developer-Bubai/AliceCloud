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
