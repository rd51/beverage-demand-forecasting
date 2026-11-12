# Beverage Demand Forecasting — AIO Session II, Problems & Exercises 2
# Rakshanda Dhote | SP Jain MAIB
#
# Pinned base image + pinned deps = reproducible across machines.
# Exposes two services:
#   8888  Jupyter Notebook  (for the .ipynb)
#   8000  Static HTTP       (for the dashboard)

FROM python:3.11-slim

LABEL org.opencontainers.image.title="Beverage Demand Forecasting"
LABEL org.opencontainers.image.authors="Rakshanda Dhote"
LABEL org.opencontainers.image.source="AI in Operations — SP Jain MAIB"

WORKDIR /app

# System deps that statsmodels / xgboost sometimes need at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project files
COPY champagne_sales.csv .
COPY pipeline.py .
COPY beverage_forecasting.ipynb .
COPY dashboard.html .
COPY results.json .
COPY README.md .

EXPOSE 8888 8000

# Default: launch both the Jupyter server and the static dashboard server.
# Jupyter on 8888 (no token for local use — DO NOT expose this to the internet),
# dashboard on 8000 (open http://localhost:8000/dashboard.html).
CMD ["bash","-lc","(python -m http.server 8000 &) && jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root --NotebookApp.token='' --NotebookApp.password=''"]
