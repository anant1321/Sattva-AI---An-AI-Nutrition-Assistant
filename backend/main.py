"""main.py — Sattva AI FastAPI Entry Point (Gemini only)"""
from __future__ import annotations
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import date
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")
print("GEMINI KEY loaded:", bool(os.getenv("GEMINI_API_KEY")))
print("SUPABASE URL loaded:", os.getenv("SUPABASE_URL"))

from bmi import full_biometric_analysis
from calorie_engine import lookup_food, search_foods, dataset_stats
from nutrition_engine import route_chat, estimate_food_with_ai, generate_meal_plan
from auth import verify_token, optional_token, require_authenticated, create_guest_token
import database as db

app = FastAPI(title="Sattva AI", version="2.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5500,http://127.0.0.1:5500").split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class BMIRequest(BaseModel):
    weight_kg: float = Field(..., gt=0, le=500)
    height_cm: float = Field(..., gt=0, le=300)
    age: int = Field(..., gt=0, le=120)
    gender: Literal["male","female","other"]
    activity: Literal["sedentary","light","moderate","active","very_active"]
    goal: Literal["lose","maintain","gain"] = "maintain"
    waist_cm: Optional[float]=None; neck_cm: Optional[float]=None; hip_cm: Optional[float]=None

class MealLogRequest(BaseModel):
    food_name: str; quantity_g: float = Field(...,gt=0)
    meal_type: Literal["breakfast","lunch","dinner","snack"]
    log_date: Optional[str]=None

class WaterLogRequest(BaseModel):
    ml: float = Field(..., gt=0, le=2000)
    note: Optional[str] = None

class ChatMessage(BaseModel):
    role: Literal["user","assistant"]; content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model_provider: str = "gemini"   # always Gemini
    user_context: Optional[dict]=None

class MealPlanRequest(BaseModel):
    goal: Literal["lose","maintain","gain"]="maintain"
    preference: Literal["vegetarian","vegan","non-veg"]="non-veg"

@app.get("/")
async def root(): return {"status":"ok","version":"2.0.0","ai":"gemini-2.5-flash"}

@app.get("/health")
async def health(): return {"status":"ok","ai_model":"gemini-2.5-flash","dataset":dataset_stats()}

@app.post("/auth/guest")
async def guest_session(): return create_guest_token()

@app.get("/auth/me")
async def get_me(user:dict=Depends(verify_token)):
    return {**user,"profile":db.get_profile(user["id"]) if user["type"]=="authenticated" else None}

@app.post("/bmi/calculate")
async def calculate_bmi(data:BMIRequest, user:Optional[dict]=Depends(optional_token)):
    r = full_biometric_analysis(data.weight_kg,data.height_cm,data.age,data.gender,
        data.activity,data.goal,data.waist_cm,data.neck_cm,data.hip_cm)
    if user and user["type"]=="authenticated":
        db.upsert_profile(user["id"],{"weight_kg":data.weight_kg,"height_cm":data.height_cm,
            "age":data.age,"gender":data.gender,"activity":data.activity,"goal":data.goal,
            "bmi":r.bmi,"bmr":r.bmr,"tdee":r.tdee,"calorie_goal":r.calorie_goal})
    return r.__dict__

@app.get("/foods/search")
async def food_search(q:str=Query(...,min_length=1),limit:int=10):
    return {"results":search_foods(q,limit),"query":q}

@app.get("/foods/lookup")
async def food_lookup(name:str, quantity_g:float=100):
    try: return lookup_food(name,quantity_g)
    except LookupError as e: raise HTTPException(404,str(e))

@app.post("/meals/log")
async def log_meal(data:MealLogRequest, user:dict=Depends(verify_token)):
    try: nutrition=lookup_food(data.food_name,data.quantity_g)
    except LookupError as e: raise HTTPException(404,str(e))
    entry={"food_name":nutrition["food_name"],"quantity_g":data.quantity_g,
        "meal_type":data.meal_type,"log_date":data.log_date or str(date.today()),
        "calories":nutrition["calories"],"protein_g":nutrition["protein_g"],
        "carbs_g":nutrition["carbs_g"],"fats_g":nutrition["fats_g"],
        "fiber_g":nutrition["fiber_g"],"source":nutrition["source"]}
    if user["type"]=="authenticated":
        saved=db.insert_meal_log(user["id"],entry)
        return {**entry,"id":saved.get("id"),"saved":True}
    return {**entry,"saved":False,"note":"Sign in to save meal history"}

@app.get("/meals/today")
async def get_today(user:dict=Depends(require_authenticated)):
    today=str(date.today())
    return {"date":today,"meals":db.get_meals_for_day(user["id"],today),
            "summary":db.get_daily_summary(user["id"],today)}

@app.get("/meals/history")
async def get_history(days:int=7,user:dict=Depends(require_authenticated)):
    return {"history":db.get_weekly_history(user["id"],days)}

@app.delete("/meals/{meal_id}")
async def delete_meal(meal_id:int,user:dict=Depends(require_authenticated)):
    if not db.delete_meal_log(meal_id,user["id"]): raise HTTPException(404,"Meal not found")
    return {"deleted":True}

@app.post("/ai/chat")
async def ai_chat(data:ChatRequest, user:Optional[dict]=Depends(optional_token)):
    messages=[{"role":m.role,"content":m.content} for m in data.messages]
    context=data.user_context or {}
    if user and user["type"]=="authenticated":
        profile=db.get_profile(user["id"]) or {}
        summary=db.get_daily_summary(user["id"],str(date.today())) or {}
        meals=db.get_meals_for_day(user["id"],str(date.today()))
        context={**context,"bmi":profile.get("bmi"),"tdee":profile.get("tdee"),
            "calorie_goal":profile.get("calorie_goal"),"health_goal":profile.get("goal"),
            "today_kcal":summary.get("total_calories",0),
            "today_protein_g":summary.get("total_protein",0),
            "meals_logged":[f"{m['food_name']} ({m['quantity_g']}g)" for m in meals]}
    try: reply,model_name,tokens=await route_chat(messages,"gemini",context)
    except Exception as e: raise HTTPException(502,f"Gemini error: {str(e)}")
    if user and user["type"]=="authenticated":
        db.save_chat_turn(user["id"],"user",messages[-1]["content"],"gemini")
        db.save_chat_turn(user["id"],"assistant",reply,"gemini-1.5-flash")
    return {"reply":reply,"model_used":model_name,"tokens_used":tokens}

@app.post("/ai/estimate-food")
async def estimate_food(food_name:str,quantity_g:float=100):
    try: return await estimate_food_with_ai(food_name,quantity_g,"gemini")
    except Exception as e: raise HTTPException(502,str(e))

@app.post("/ai/meal-plan")
async def get_meal_plan(data:MealPlanRequest,user:Optional[dict]=Depends(optional_token)):
    tdee=2000.0
    if user and user["type"]=="authenticated":
        tdee=(db.get_profile(user["id"]) or {}).get("tdee",2000.0)
    try: plan=await generate_meal_plan(tdee,data.goal,data.preference,"gemini")
    except Exception as e: raise HTTPException(502,str(e))
    return {"meal_plan":plan,"based_on_tdee":tdee}
