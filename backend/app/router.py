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
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model":model,"messages":messages,"temperature":temperature,"max_tokens":max_tokens}
            )
            d = r.json()
            return {
                "content":    d["choices"][0]["message"]["content"],
                "provider":   "groq",
                "model_used": f"groq/{model}",
                "tokens":     d.get("usage",{}).get("total_tokens",0)
            }
    except Exception as e:
        print(f"[Groq] {e}")
        return None

async def _gemini(messages, model, temperature, max_tokens):
    if not GEMINI_KEY: return None
    try:
        contents, system = [], ""
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "user":
                contents.append({"parts":[{"text":m["content"]}],"role":"user"})
            elif m["role"] == "assistant":
                contents.append({"parts":[{"text":m["content"]}],"role":"model"})
        payload = {
            "contents": contents,
            "generationConfig": {"temperature":temperature,"maxOutputTokens":max_tokens}
        }
        if system:
            payload["systemInstruction"] = {"parts":[{"text":system}]}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}",
                json=payload
            )
            d = r.json()
            text = d["candidates"][0]["content"]["parts"][0]["text"]
            return {
                "content":    text,
                "provider":   "gemini",
                "model_used": f"gemini/{model}",
                "tokens":     len(text.split()) * 2
            }
    except Exception as e:
        print(f"[Gemini] {e}")
        return None

async def _cohere(messages, model, temperature, max_tokens):
    if not COHERE_KEY: return None
    try:
        history, user_msg = [], ""
        for m in messages:
            if m["role"] == "user":
                user_msg = m["content"]
            elif m["role"] == "assistant":
                history.append({"role":"CHATBOT","message":m["content"]})
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                "https://api.cohere.ai/v1/chat",
                headers={"Authorization": f"Bearer {COHERE_KEY}"},
                json={"model":model,"message":user_msg,"chat_history":history,"temperature":temperature,"max_tokens":max_tokens}
            )
            d = r.json()
            return {
                "content":    d.get("text",""),
                "provider":   "cohere",
                "model_used": f"cohere/{model}",
                "tokens":     d.get("meta",{}).get("billed_units",{}).get("output_tokens",0)
            }
    except Exception as e:
        print(f"[Cohere] {e}")
        return None

async def _huggingface(messages, model, temperature, max_tokens):
    if not HF_KEY: return None
    try:
        prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {HF_KEY}"},
                json={"inputs":prompt,"parameters":{"max_new_tokens":max_tokens,"temperature":temperature,"return_full_text":False}}
            )
            d = r.json()
            text = d[0]["generated_text"].strip() if isinstance(d,list) else str(d)
            return {
                "content":    text,
                "provider":   "huggingface",
                "model_used": f"hf/{model}",
                "tokens":     len(text.split())
            }
    except Exception as e:
        print(f"[HF] {e}")
        return None

async def route_request(messages, model="alice-flash", temperature=0.7, max_tokens=500):
    provider, real_model = MODEL_MAP.get(model, ("groq","llama-3.1-8b-instant"))
    order = [provider] + [p for p in ["groq","gemini","cohere","huggingface"] if p != provider]

    for p in order:
        result = None
        if p == "groq":
            result = await _groq(messages, real_model if provider=="groq" else "llama-3.1-8b-instant", temperature, max_tokens)
        elif p == "gemini":
            result = await _gemini(messages, real_model if provider=="gemini" else "gemini-1.5-flash", temperature, max_tokens)
        elif p == "cohere":
            result = await _cohere(messages, real_model if provider=="cohere" else "command-r", temperature, max_tokens)
        elif p == "huggingface":
            result = await _huggingface(messages, real_model if provider=="huggingface" else "mistralai/Mistral-7B-Instruct-v0.3", temperature, max_tokens)
        if result:
            result["fallback"] = (p != provider)
            return result

    return {
        "content":    "AliceAPI is temporarily unavailable. Please try again.",
        "provider":   "error",
        "model_used": "none",
        "tokens":     0,
        "fallback":   True
    }