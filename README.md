# 🌿 Sattva AI — AI Nutrition Assistant

> Hybrid deterministic accuracy (IFCT & USDA data) + Gemini 1.5 Flash generative coaching — built for Indian dietary patterns.

---

## Project Structure

```
sattva-ai/
├── backend/
│   ├── main.py              ← FastAPI entry point, all routes wired
│   ├── nutrition_engine.py  ← Gemini 1.5 Flash system prompt & router
│   ├── calorie_engine.py    ← Priority-Inference Engine (IFCT → USDA → 404)
│   ├── bmi.py               ← BMI, BMR, TDEE, ideal weight, macro targets
│   ├── database.py          ← All Supabase operations + SQL schema
│   ├── auth.py              ← JWT verify, guest tokens, Google OAuth helpers
│   ├── food_data.csv        ← 50-item hybrid IFCT + USDA verified dataset
│   ├── .env.example         ← Copy to .env and add your keys
│   └── sattva_supabase.sql  ← Run this in Supabase SQL Editor
├── frontend/
│   └── index.html           ← Full dashboard (self-contained, logo embedded)
├── requirements.txt
└── README.md
```

---

## Features

| Feature | Description |
|---------|-------------|
| 💬 **Sattva AI Chat** | Gemini-powered nutrition coach with Indian cuisine expertise |
| ⚖️ **Body Metrics** | BMI (Asian thresholds), BMR, TDEE, ideal weight, macro targets |
| 🍱 **Meal Logger** | IFCT & USDA verified data — never hallucinates calories |
| 📊 **Macro Tracker** | Live donut chart + progress bars, updates as you log |
| 💧 **Hydration Tracker** | Glass-by-glass water tracker with personalized goal |
| 🔐 **Auth** | Supabase + Google OAuth, guest mode works without login |

---

## Quickstart (5 minutes)

### Step 1 — Get your FREE Gemini API key
1. Go to **aistudio.google.com**
2. Sign in with Google → Click **"Get API Key"** → **"Create API key"**
3. Copy the key (starts with `AIzaSy...`)

### Step 2 — Set up Supabase (FREE)
1. Go to **supabase.com** → Create project (Mumbai region)
2. Go to **Project Settings → API** → copy URL + anon key + service role key
3. Go to **SQL Editor** → paste contents of `backend/sattva_supabase.sql` → Run

### Step 3 — Configure environment
```bash
cd backend
cp .env.example .env
```
Edit `.env`:
```env
GEMINI_API_KEY=AIzaSy...              ← your Gemini key (FREE)
SUPABASE_URL=https://xyz.supabase.co  ← from Supabase settings
SUPABASE_ANON_KEY=eyJ...              ← from Supabase settings
SUPABASE_SERVICE_ROLE_KEY=eyJ...      ← from Supabase settings
```

### Step 4 — Install & run
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
Backend runs at: **http://127.0.0.1:8000**
API docs at: **http://127.0.0.1:8000/docs**

### Step 5 — Open frontend
Open `frontend/index.html` in your browser — or use **Live Server** in VS Code.

> ✅ The frontend works in **demo mode** without the backend. Connect FastAPI for live Gemini responses.

---

## Cost Breakdown

| Service | Cost |
|---------|------|
| **Gemini 1.5 Flash** | ✅ FREE (15 req/min, 1M tokens/day) |
| **Supabase** | ✅ FREE (500MB DB, 50,000 users) |
| **Total** | **₹0** |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bmi/calculate` | BMI, BMR, TDEE, macro targets |
| GET | `/foods/search?q=roti` | Search IFCT/USDA database |
| GET | `/foods/lookup?name=dal` | Exact food lookup with macros |
| POST | `/meals/log` | Log a verified meal |
| GET | `/meals/today` | Today's meals + summary |
| GET | `/meals/history?days=7` | Weekly macro history |
| POST | `/ai/chat` | Gemini nutrition coaching |
| POST | `/ai/estimate-food` | AI food estimation (unlisted foods) |
| POST | `/ai/meal-plan` | Generate 1-day Indian meal plan |
| POST | `/auth/guest` | Create guest session token |
| GET | `/health` | System health check |

---

## Supabase Tables

Run `sattva_supabase.sql` in your Supabase SQL Editor to create:

| Table | Purpose |
|-------|---------|
| `profiles` | User BMI, weight, goals, TDEE |
| `meal_logs` | Every food entry with macros |
| `daily_summaries` | Aggregated daily macro totals |
| `chat_history` | AI conversation turns |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTML · CSS · Vanilla JS (zero dependencies) |
| **Backend** | FastAPI · Python 3.11+ |
| **AI** | Google Gemini 1.5 Flash (free tier) |
| **Database** | Supabase (PostgreSQL) |
| **Auth** | Supabase Auth · Google OAuth |
| **Nutrition Data** | IFCT 2017 · USDA FoodData Central |

---

## Key Architecture — Hybrid AI Design

```
User asks "how many calories in Gulab Jamun?"
        ↓
Deterministic Engine (calorie_engine.py)
  → Looks up IFCT dataset first
  → Falls back to USDA
  → If not found → returns 404 (never invents data)
        ↓
Gemini AI (nutrition_engine.py)
  → Gets verified number from database
  → Provides coaching, context, personalization
  → Never invents calorie numbers
```

This is the "Hallucination Guard" — the key innovation of Sattva AI.

---

## AIES Mini Project — Review Notes

**Gap 1 — Hallucination Problem:** Solved by Priority-Inference Engine (IFCT → USDA → 404)

**Gap 2 — Cultural Specificity:** IFCT dataset covers Indian staples (Roti, Dal, Biryani, Idli etc.) with region-accurate macros

**Gap 3 — Data Collision:** IFCT takes priority over USDA for Indian foods; USDA used for global ingredients

**Gap 4 — Accessibility:** Guest mode provides instant value without login; Supabase Auth for persistent tracking

---

Built for AIES Mini Project · Symbiosis Institute · 2025
