"""
bmi.py
────────────────────────────────────────────────────────
Sattva AI · Biometric Calculation Engine

Implements:
  - BMI calculation & WHO/Asian classification
  - BMR via Mifflin-St Jeor (most accurate for general population)
  - TDEE via activity multiplier
  - Ideal Body Weight (Devine formula)
  - Body Fat % estimation (US Navy method)
  - Personalised macro targets derived from TDEE + goal
  - Weekly weight change projection
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional
import math


ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
Gender = Literal["male", "female", "other"]
Goal = Literal["lose", "maintain", "gain"]


ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary":   1.200,   # desk job, no exercise
    "light":       1.375,   # 1–3x/week light exercise
    "moderate":    1.550,   # 3–5x/week moderate
    "active":      1.725,   # 6–7x/week hard training
    "very_active": 1.900,   # athlete / physical labour
}

CALORIE_ADJUSTMENTS: dict[str, int] = {
    "lose":      -400,   # safe deficit
    "maintain":     0,
    "gain":      +300,   # lean bulk
}

# Asian BMI thresholds (more relevant for Indian population)
ASIAN_BMI_CATEGORIES = [
    (0,    18.5, "Underweight",   "#3B82F6"),
    (18.5, 23.0, "Normal weight", "#22C55E"),
    (23.0, 27.5, "Overweight",   "#F59E0B"),
    (27.5, 999,  "Obese",        "#EF4444"),
]


@dataclass
class BiometricResult:
    # Core
    bmi:              float
    bmi_category:     str
    bmi_color:        str

    # Energy
    bmr:              float
    tdee:             float
    calorie_goal:     float

    # Weight
    ideal_weight_min: float   # kg
    ideal_weight_max: float   # kg
    weight_to_goal:   float   # kg (negative = need to lose)

    # Macro targets (grams)
    protein_goal_g:   float
    carbs_goal_g:     float
    fats_goal_g:      float

    # Body fat (estimated, Navy method — needs waist/neck/hip)
    body_fat_pct:     Optional[float]

    # Projection
    weeks_to_goal:    Optional[int]   # at current deficit/surplus
    recommendation:   str


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    h = height_cm / 100
    return round(weight_kg / (h * h), 1)


def classify_bmi(bmi: float, use_asian: bool = True) -> tuple[str, str]:
    """Returns (category, hex_color). Uses Asian thresholds by default."""
    thresholds = ASIAN_BMI_CATEGORIES if use_asian else [
        (0, 18.5, "Underweight", "#3B82F6"),
        (18.5, 25, "Normal weight", "#22C55E"),
        (25, 30, "Overweight", "#F59E0B"),
        (30, 999, "Obese", "#EF4444"),
    ]
    for low, high, cat, color in thresholds:
        if low <= bmi < high:
            return cat, color
    return "Obese", "#EF4444"


def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: Gender,
) -> float:
    """Mifflin-St Jeor equation — most validated formula."""
    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    return round(base + 5 if gender == "male" else base - 161, 1)


def calculate_tdee(bmr: float, activity: ActivityLevel) -> float:
    return round(bmr * ACTIVITY_MULTIPLIERS[activity], 0)


def ideal_body_weight(height_cm: float, gender: Gender) -> tuple[float, float]:
    """Devine formula. Returns (min_kg, max_kg) for BMI 18.5–22.9 range (Asian)."""
    h = height_cm / 100
    return (round(18.5 * h * h, 1), round(22.9 * h * h, 1))


def estimate_body_fat_navy(
    gender: Gender,
    waist_cm: float,
    neck_cm: float,
    height_cm: float,
    hip_cm: Optional[float] = None,   # required for female
) -> Optional[float]:
    """
    US Navy Body Fat Formula.
    Female requires hip measurement. Returns None if inputs invalid.
    """
    try:
        if gender == "male":
            bf = 495 / (
                1.0324 - 0.19077 * math.log10(waist_cm - neck_cm)
                + 0.15456 * math.log10(height_cm)
            ) - 450
        else:
            if not hip_cm:
                return None
            bf = 495 / (
                1.29579 - 0.35004 * math.log10(waist_cm + hip_cm - neck_cm)
                + 0.22100 * math.log10(height_cm)
            ) - 450
        return round(max(3.0, min(bf, 60.0)), 1)
    except (ValueError, ZeroDivisionError):
        return None


def calculate_macro_targets(
    calorie_goal: float,
    goal: Goal,
    weight_kg: float,
) -> tuple[float, float, float]:
    """
    Returns (protein_g, carbs_g, fats_g) based on goal.
    - Lose: high protein (35%), moderate carbs, moderate fat
    - Maintain: balanced (30/40/30)
    - Gain: higher carbs for energy, moderate protein
    """
    splits: dict[str, tuple[float, float, float]] = {
        "lose":     (0.35, 0.35, 0.30),
        "maintain": (0.30, 0.40, 0.30),
        "gain":     (0.28, 0.45, 0.27),
    }
    p_pct, c_pct, f_pct = splits[goal]
    protein_g = round((calorie_goal * p_pct) / 4, 0)
    carbs_g   = round((calorie_goal * c_pct) / 4, 0)
    fats_g    = round((calorie_goal * f_pct) / 9, 0)
    return protein_g, carbs_g, fats_g


def weeks_to_goal_weight(
    current_kg: float,
    ideal_max_kg: float,
    calorie_delta: int,
) -> Optional[int]:
    """Estimate weeks to reach ideal weight at given daily calorie deficit/surplus."""
    kg_diff = abs(current_kg - ideal_max_kg)
    if kg_diff < 0.5 or calorie_delta == 0:
        return None
    # 7700 kcal ≈ 1 kg of body fat
    weeks = (kg_diff * 7700) / (abs(calorie_delta) * 7)
    return max(1, round(weeks))


RECOMMENDATIONS = {
    "Underweight": (
        "Your weight is below the healthy range. Focus on a caloric surplus with "
        "nutrient-dense Indian foods: full-fat dairy, ghee, dal, nuts, and whole grains. "
        "Aim to gain 0.25–0.5 kg/week with strength training."
    ),
    "Normal weight": (
        "You're in a healthy weight range — excellent! Prioritize protein and fibre-rich meals "
        "to maintain muscle mass and energy. Stay consistent with your current habits."
    ),
    "Overweight": (
        "A modest 300–400 kcal daily deficit will help you return to a healthy range. "
        "Reduce refined carbs (maida, white rice in excess) and increase protein (dal, paneer, eggs). "
        "Aim for 30 mins of walking daily."
    ),
    "Obese": (
        "Consult your doctor before making major dietary changes. "
        "Start with a 400–500 kcal deficit and gentle daily movement. "
        "Replacing one refined-carb meal with a protein-rich option (dal, sabzi + roti) is a great first step."
    ),
}


def full_biometric_analysis(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: Gender,
    activity: ActivityLevel,
    goal: Goal = "maintain",
    waist_cm: Optional[float] = None,
    neck_cm: Optional[float] = None,
    hip_cm: Optional[float] = None,
) -> BiometricResult:
    """
    Single entry point for all biometric calculations.
    Used by the /bmi/calculate FastAPI route.
    """
    bmi = calculate_bmi(weight_kg, height_cm)
    category, color = classify_bmi(bmi, use_asian=True)
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    tdee = calculate_tdee(bmr, activity)
    calorie_goal = tdee + CALORIE_ADJUSTMENTS[goal]

    ideal_min, ideal_max = ideal_body_weight(height_cm, gender)
    weight_delta = round(weight_kg - ideal_max, 1)

    protein_g, carbs_g, fats_g = calculate_macro_targets(calorie_goal, goal, weight_kg)

    body_fat = None
    if waist_cm and neck_cm:
        body_fat = estimate_body_fat_navy(gender, waist_cm, neck_cm, height_cm, hip_cm)

    daily_delta = CALORIE_ADJUSTMENTS[goal]
    weeks = weeks_to_goal_weight(weight_kg, ideal_max, daily_delta) if goal != "maintain" else None

    return BiometricResult(
        bmi=bmi,
        bmi_category=category,
        bmi_color=color,
        bmr=bmr,
        tdee=tdee,
        calorie_goal=calorie_goal,
        ideal_weight_min=ideal_min,
        ideal_weight_max=ideal_max,
        weight_to_goal=weight_delta,
        protein_goal_g=protein_g,
        carbs_goal_g=carbs_g,
        fats_goal_g=fats_g,
        body_fat_pct=body_fat,
        weeks_to_goal=weeks,
        recommendation=RECOMMENDATIONS.get(category, ""),
    )
