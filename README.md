# Livestock Health MVP

AI-assisted livestock health risk assessment prototype.

## Features

- Animal health reporting
- Symptom-based risk assessment
- District-level historical Anthrax evidence
- Machine learning prediction
- Explainable risk breakdown
- Low / Medium / High risk classification
- Recommended actions

## Technology

- Python
- Flask
- Pandas
- Scikit-learn
- Random Forest Regressor
- HTML
- CSS
- Bootstrap
- JavaScript

## Project Structure

```text
livestock-health-mvp/
├── app.py
├── requirements.txt
├── .gitignore
├── ml/
│   ├── data/
│   │   └── anthrax_2020_2023.csv
│   ├── livestock_risk_model.pkl
│   ├── predict.py
│   └── train_model.py
├── static/
│   └── css/
│       └── style.css
└── templates/
    ├── analysis.html
    ├── dashboard.html
    ├── location.html
    └── report.html