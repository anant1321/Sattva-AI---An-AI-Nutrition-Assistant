"""
database.py
────────────────────────────────────────────────────────
Sattva AI · Supabase Data Layer

All database interactions go through this module.
Tables:
  - profiles        : user biometrics, goals, preferences
  - meal_logs       : individual food entries per day
  - daily_summaries : pre-aggregated daily macro totals (updated on each log)
  - chat_history    : AI conversation turns per user

SQL schema to run in Supabase SQL Editor:
────────────────────────────────────────────────────────
CREATE TABLE profiles (
  id           UUID PRIMARY KEY REFERENCES auth.users(id),
  name         TEXT,
  age          INT,
  gender       TEXT,
  weight_kg    FLOAT,
  height_cm    FLOAT,
  activity     TEXT DEFAULT 'moderate',
  goal         TEXT DEFAULT 'maintain',
  bmi          FLOAT,
  bmr          FLOAT,
  tdee         FLOAT,
  calorie_goal FLOAT,
  dietary_pref TEXT DEFAULT 'non-veg',  -- vegetarian | vegan | non-veg
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE meal_logs (
  id           BIGSERIAL PRIMARY KEY,
  user_id      UUID REFERENCES profiles(id) ON DELETE CASCADE,
  log_date     DATE NOT NULL DEFAULT CURRENT_DATE,
  meal_type    TEXT NOT NULL,
  food_name    TEXT NOT NULL,
  quantity_g   FLOAT NOT NULL,
  calories     FLOAT NOT NULL,
  protein_g    FLOAT NOT NULL,
  carbs_g      FLOAT NOT NULL,
  fats_g       FLOAT NOT NULL,
  fiber_g      FLOAT DEFAULT 0,
  source       TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_meal_logs_user_date ON meal_logs(user_id, log_date);

CREATE TABLE daily_summaries (
  id             BIGSERIAL PRIMARY KEY,
  user_id        UUID REFERENCES profiles(id) ON DELETE CASCADE,
  summary_date   DATE NOT NULL DEFAULT CURRENT_DATE,
  total_calories FLOAT DEFAULT 0,
  total_protein  FLOAT DEFAULT 0,
  total_carbs    FLOAT DEFAULT 0,
  total_fats     FLOAT DEFAULT 0,
  total_fiber    FLOAT DEFAULT 0,
  meal_count     INT DEFAULT 0,
  calorie_goal   FLOAT,
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, summary_date)
);

CREATE TABLE chat_history (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID REFERENCES profiles(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,
  content     TEXT NOT NULL,
  model       TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_chat_history_user ON chat_history(user_id, created_at DESC);
────────────────────────────────────────────────────────
"""

from __future__ import annotations
import os
from datetime import date
from typing import Optional
from supabase import create_client, Client

_client: Optional[Client] = None


def get_db() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        _client = create_client(url, key)
    return _client


# ── PROFILES ──────────────────────────────────────────────────────────────────

def upsert_profile(user_id: str, data: dict) -> dict:
    db = get_db()
    data["id"] = user_id
    res = db.table("profiles").upsert(data).execute()
    return res.data[0] if res.data else {}


def get_profile(user_id: str) -> Optional[dict]:
    db = get_db()
    res = db.table("profiles").select("*").eq("id", user_id).single().execute()
    return res.data


# ── MEAL LOGS ──────────────────────────────────────────────────────────────────

def insert_meal_log(user_id: str, meal: dict) -> dict:
    """Insert a single meal entry and update the daily summary."""
    db = get_db()
    meal["user_id"] = user_id
    meal.setdefault("log_date", str(date.today()))
    res = db.table("meal_logs").insert(meal).execute()
    entry = res.data[0] if res.data else {}
    # Update daily summary
    _update_daily_summary(user_id, meal["log_date"])
    return entry


def get_meals_for_day(user_id: str, log_date: str) -> list[dict]:
    db = get_db()
    res = (
        db.table("meal_logs")
        .select("*")
        .eq("user_id", user_id)
        .eq("log_date", log_date)
        .order("created_at")
        .execute()
    )
    return res.data or []


def delete_meal_log(meal_id: int, user_id: str) -> bool:
    db = get_db()
    res = db.table("meal_logs").delete().eq("id", meal_id).eq("user_id", user_id).execute()
    if res.data:
        _update_daily_summary(user_id, str(date.today()))
        return True
    return False


# ── DAILY SUMMARY ──────────────────────────────────────────────────────────────

def _update_daily_summary(user_id: str, log_date: str) -> None:
    """Recalculate and upsert the daily summary from raw meal_logs."""
    db = get_db()
    meals = get_meals_for_day(user_id, log_date)
    if not meals:
        return
    total_cal = sum(m["calories"] for m in meals)
    total_p   = sum(m["protein_g"] for m in meals)
    total_c   = sum(m["carbs_g"] for m in meals)
    total_f   = sum(m["fats_g"] for m in meals)
    total_fib = sum(m.get("fiber_g", 0) for m in meals)
    profile   = get_profile(user_id) or {}
    db.table("daily_summaries").upsert({
        "user_id":       user_id,
        "summary_date":  log_date,
        "total_calories": round(total_cal, 1),
        "total_protein":  round(total_p, 1),
        "total_carbs":    round(total_c, 1),
        "total_fats":     round(total_f, 1),
        "total_fiber":    round(total_fib, 1),
        "meal_count":     len(meals),
        "calorie_goal":   profile.get("calorie_goal"),
    }).execute()


def get_daily_summary(user_id: str, log_date: str) -> Optional[dict]:
    db = get_db()
    res = (
        db.table("daily_summaries")
        .select("*")
        .eq("user_id", user_id)
        .eq("summary_date", log_date)
        .single()
        .execute()
    )
    return res.data


def get_weekly_history(user_id: str, days: int = 7) -> list[dict]:
    """Fetch last N days of daily summaries for trend charts."""
    db = get_db()
    res = (
        db.table("daily_summaries")
        .select("*")
        .eq("user_id", user_id)
        .order("summary_date", desc=True)
        .limit(days)
        .execute()
    )
    return list(reversed(res.data or []))


# ── CHAT HISTORY ───────────────────────────────────────────────────────────────

def save_chat_turn(user_id: str, role: str, content: str, model: str = "") -> None:
    db = get_db()
    db.table("chat_history").insert({
        "user_id": user_id, "role": role,
        "content": content, "model": model,
    }).execute()


def get_chat_history(user_id: str, limit: int = 20) -> list[dict]:
    """Return last N messages for a user (for context injection)."""
    db = get_db()
    res = (
        db.table("chat_history")
        .select("role, content, model")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data or []))
