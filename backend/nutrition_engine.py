"""
nutrition_engine.py — Sattva AI · Generative Layer
AI Model: Google Gemini 1.5 Flash (free tier)
"""
from __future__ import annotations
import json, os, httpx
from typing import Optional

SATTVA_SYSTEM_PROMPT = """You are Sattva AI — a compassionate AI Nutrition Assistant specializing in Indian dietary patterns and Ayurvedic wellness.

## Rules
1. NEVER invent calorie/macro numbers — always say "based on IFCT data"
2. Personalize every response to the user's BMI, TDEE, goals, and today's food log
3. Be specific and actionable. Mention hydration when relevant.
4. Use **bold** for key numbers. Keep responses under 200 words."""

def build_context(user_context):
    if not user_context: return ""
    lines = ["\n## User Data"]
    for k,v in [("bmi","BMI"),("tdee","TDEE kcal/day"),("calorie_goal","Calorie Goal"),
                ("today_kcal","Intake today"),("today_protein_g","Protein today"),
                ("water_ml","Water today"),("health_goal","Goal")]:
        if user_context.get(k): lines.append(f"- {v}: {user_context[k]}")
    if user_context.get("water_ml") is not None:
        lines.append(f"- Water: {user_context['water_ml']}ml of {user_context.get('water_goal',2000)}ml")
    if user_context.get("meals_logged"):
        lines.append(f"- Meals: {', '.join(user_context['meals_logged'])}")
    return "\n".join(lines)

async def call_gemini(messages, user_context=None):
    system = SATTVA_SYSTEM_PROMPT + build_context(user_context)
    contents = [{"role":"user" if m["role"]=="user" else "model","parts":[{"text":m["content"]}]} for m in messages]
    api_key = os.getenv("GEMINI_API_KEY","")
    
    print("=== GEMINI DEBUG ===")
    print("Key loaded:", bool(api_key))
    print("Key preview:", api_key[:10] if api_key else "NONE")
    
    if not api_key: raise ValueError("GEMINI_API_KEY not set in .env")
    
    async with httpx.AsyncClient(timeout=40) as client:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        print("Calling URL:", url[:80])
        
        resp = await client.post(
            url,
            json={"system_instruction":{"parts":[{"text":system}]},"contents":contents,
                  "generationConfig":{"maxOutputTokens":1024,"temperature":0.7}})
        
        print("Status:", resp.status_code)
        print("Response:", resp.text[:300])
        
        if resp.status_code == 429:
            raise ValueError("Rate limit hit. Wait a minute and retry.")
        
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"], data.get("usageMetadata",{}).get("candidatesTokenCount",0)
    
async def route_chat(messages, provider="gemini", user_context=None):
    text, tokens = await call_gemini(messages, user_context)
    return text, "gemini-2.5-flash", tokens

async def estimate_food_with_ai(food_name, quantity_g, provider="gemini"):
    prompt = f'Estimate nutrition for "{food_name}" ({quantity_g}g). JSON only...'
    raw, _ = await call_gemini([{"role":"user","content":prompt}])
    
    # ADD THIS LINE: Clean the string before parsing
    clean_raw = raw.replace("```json", "").replace("```", "").strip()
    
    result = json.loads(clean_raw)
    result.update({"source":"AI Estimated (not verified)","food_name":food_name,"quantity_g":quantity_g})
    return result

async def generate_meal_plan(tdee, goal, preference, provider="gemini"):
    target = {"lose":tdee-400,"maintain":tdee,"gain":tdee+300}.get(goal,tdee)
    prompt = f"1-day Indian meal plan: {target:.0f} kcal, goal={goal}, diet={preference}. Include Breakfast, Snack, Lunch, Snack, Dinner with grams, kcal, protein, carbs, fats per meal. Daily totals at end."
    text, _ = await call_gemini([{"role":"user","content":prompt}])
    return text
