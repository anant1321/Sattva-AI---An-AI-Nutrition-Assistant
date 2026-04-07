-- ╔══════════════════════════════════════════════════════╗
-- ║        SATTVA AI — SUPABASE DATABASE SETUP          ║
-- ║     Run this entire block in SQL Editor → Run       ║
-- ╚══════════════════════════════════════════════════════╝

-- ── STEP 1: DROP everything cleanly ──────────────────────
DROP TABLE IF EXISTS chat_history     CASCADE;
DROP TABLE IF EXISTS daily_summaries  CASCADE;
DROP TABLE IF EXISTS meal_logs        CASCADE;
DROP TABLE IF EXISTS profiles         CASCADE;

-- ── STEP 2: CREATE tables ─────────────────────────────────

-- 1. profiles
CREATE TABLE profiles (
  id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
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
  dietary_pref TEXT DEFAULT 'non-veg',
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 2. meal_logs
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

-- 3. daily_summaries
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

-- 4. chat_history
CREATE TABLE chat_history (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID REFERENCES profiles(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,
  content     TEXT NOT NULL,
  model       TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── STEP 3: INDEXES ───────────────────────────────────────
CREATE INDEX idx_meal_logs_user_date
  ON meal_logs(user_id, log_date);

CREATE INDEX idx_chat_history_user
  ON chat_history(user_id, created_at DESC);

-- ── STEP 4: ENABLE ROW LEVEL SECURITY ────────────────────
ALTER TABLE profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_logs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history    ENABLE ROW LEVEL SECURITY;

-- ── STEP 5: RLS POLICIES ─────────────────────────────────
-- Drop old policies if they exist
DROP POLICY IF EXISTS "Users can manage own profile"   ON profiles;
DROP POLICY IF EXISTS "Users can manage own meals"     ON meal_logs;
DROP POLICY IF EXISTS "Users can manage own summaries" ON daily_summaries;
DROP POLICY IF EXISTS "Users can manage own chat"      ON chat_history;

-- Create fresh policies
CREATE POLICY "Users can manage own profile"
  ON profiles FOR ALL
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can manage own meals"
  ON meal_logs FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage own summaries"
  ON daily_summaries FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage own chat"
  ON chat_history FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ── DONE ─────────────────────────────────────────────────
-- You should see: "Success. No rows returned"
-- Check Table Editor — you'll see all 4 tables listed.
