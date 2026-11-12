# Dataset source

**File:** `champagne_sales.csv`

**Download URL:**
https://raw.githubusercontent.com/jbrownlee/Datasets/master/monthly_champagne_sales.csv

**Hosted by:** Jason Brownlee (Machine Learning Mastery) — public GitHub mirror of classic time-series datasets.

**Original name:** Perrin Freres Monthly Champagne Sales

**Description:** Monthly sales of champagne (thousands of bottles) by the Perrin Frères company, January 1964 — September 1972 (105 observations).

**Original citation:**
Makridakis, S., Wheelwright, S. C., & Hyndman, R. J. (1998). *Forecasting: Methods and Applications* (3rd ed.). Wiley.

**Also available in:** Rob Hyndman's `fma` R package; widely used in forecasting courses, textbooks, and Kaggle notebooks.

**License / usage:** Public-domain / freely redistributable for pedagogy.

**Why chosen for Problems & Exercises 2:**
- Monthly frequency — matches the exercise scenario exactly
- A beverage — fits the "new flavored-water product" framing honestly
- Strong December seasonality — makes the Naive vs SARIMA vs tree-model comparison pedagogically clean
- ~8 years of history — enough for a 12-month hold-out plus multi-year training
- Zero licensing friction

**To swap for a different dataset:** replace `champagne_sales.csv` with any file that has two columns `Month,Sales` at monthly frequency — `pipeline.py` and the notebook are dataset-agnostic.

**Fetched on:** 2026-11-12 (Asia/Dubai)
