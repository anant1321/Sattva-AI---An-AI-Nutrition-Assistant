"""
calorie_engine.py
────────────────────────────────────────────────────────
Sattva AI · Deterministic Layer
Priority-Inference Engine: IFCT → USDA → Not Found (never hallucinate)

Loads food_data.csv at startup. Supports:
  - Exact lookup
  - Fuzzy matching (rapidfuzz)
  - Source priority (IFCT beats USDA for Indian foods)
  - Per-serving calculations
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path
from typing import Optional
from rapidfuzz import process, fuzz

# ── CONFIG ──────────────────────────────────────────────────────────────────────
CSV_PATH = Path(__file__).parent / "food_data.csv"
FUZZY_THRESHOLD = 72          # min score to accept a fuzzy match (0-100)
SOURCE_PRIORITY = {"IFCT": 1, "USDA": 2, "Estimated": 3}

# ── LOAD DATASET ────────────────────────────────────────────────────────────────
_df: Optional[pd.DataFrame] = None


def _load() -> pd.DataFrame:
    global _df
    if _df is None:
        _df = pd.read_csv(CSV_PATH)
        # Normalize food names for matching
        _df["name_lower"] = _df["food_name"].str.lower().str.strip()
        # Sort by source priority so IFCT rows come first
        _df["_priority"] = _df["source"].map(SOURCE_PRIORITY).fillna(99)
        _df = _df.sort_values("_priority").reset_index(drop=True)
    return _df


def get_all_names() -> list[str]:
    """Return all food names (for autocomplete)."""
    return _load()["food_name"].tolist()


def search_foods(query: str, limit: int = 10) -> list[dict]:
    """
    Search food database by partial name match.
    Returns list of food dicts with macros.
    """
    df = _load()
    q = query.lower().strip()
    mask = df["name_lower"].str.contains(q, na=False)
    results = df[mask].head(limit)
    return _rows_to_dicts(results, qty_g=100)


def lookup_food(food_name: str, quantity_g: float) -> dict:
    """
    Priority-Inference Engine:
    1. Exact match (case-insensitive)
    2. Fuzzy match via rapidfuzz (threshold: FUZZY_THRESHOLD)
    3. Raises LookupError — never invents data

    All CSV values are stored per 100g. Scales to quantity_g.
    """
    df = _load()
    q = food_name.lower().strip()

    # ── Step 1: Exact match ──
    exact = df[df["name_lower"] == q]
    if not exact.empty:
        row = exact.iloc[0]
        return _scale_row(row, quantity_g, match_type="exact")

    # ── Step 2: Fuzzy match ──
    names = df["name_lower"].tolist()
    match, score, idx = process.extractOne(
        q, names, scorer=fuzz.token_sort_ratio
    )
    if score >= FUZZY_THRESHOLD:
        row = df.iloc[idx]
        return _scale_row(row, quantity_g, match_type=f"fuzzy ({score:.0f}%)")

    # ── Step 3: Not found ──
    raise LookupError(
        f"Food '{food_name}' not found in IFCT/USDA database (best fuzzy match: "
        f"'{match}' at {score:.0f}% — below {FUZZY_THRESHOLD}% threshold). "
        f"Use the AI estimation endpoint for unlisted foods."
    )


def get_food_by_id(food_id: int) -> Optional[dict]:
    df = _load()
    row = df[df["id"] == food_id]
    return _rows_to_dicts(row, qty_g=100)[0] if not row.empty else None


# ── HELPERS ──────────────────────────────────────────────────────────────────────

def _scale_row(row: pd.Series, quantity_g: float, match_type: str = "exact") -> dict:
    """Scale per-100g values to the requested quantity."""
    r = quantity_g / 100.0
    return {
        "food_name":   row["food_name"],
        "quantity_g":  quantity_g,
        "calories":    round(float(row["calories_per_100g"])   * r, 1),
        "protein_g":   round(float(row["protein_g_per_100g"])  * r, 1),
        "carbs_g":     round(float(row["carbs_g_per_100g"])    * r, 1),
        "fats_g":      round(float(row["fats_g_per_100g"])     * r, 1),
        "fiber_g":     round(float(row.get("fiber_g_per_100g", 0) or 0) * r, 1),
        "sugar_g":     round(float(row.get("sugar_g_per_100g", 0) or 0) * r, 1),
        "sodium_mg":   round(float(row.get("sodium_mg_per_100g", 0) or 0) * r, 1),
        "source":      str(row["source"]),
        "category":    str(row.get("category", "")),
        "match_type":  match_type,
        "verified":    str(row["source"]) in ("IFCT", "USDA"),
    }


def _rows_to_dicts(df_slice: pd.DataFrame, qty_g: float) -> list[dict]:
    return [_scale_row(row, qty_g) for _, row in df_slice.iterrows()]


# ── DATASET STATS ──────────────────────────────────────────────────────────────

def dataset_stats() -> dict:
    df = _load()
    return {
        "total_foods":   len(df),
        "ifct_count":    int((df["source"] == "IFCT").sum()),
        "usda_count":    int((df["source"] == "USDA").sum()),
        "categories":    df["category"].nunique() if "category" in df.columns else 0,
        "last_updated":  str(df.get("last_updated", pd.Series(["unknown"])).iloc[0]),
    }
