from flask import Flask, render_template, request, session, redirect, jsonify
import joblib
import pandas as pd


app = Flask(__name__)

app.secret_key = "livestock-health-mvp-secret"


# ============================================================
# LOAD ML MODEL
# ============================================================

model = joblib.load("ml/livestock_risk_model.pkl")


# ============================================================
# LOAD HISTORICAL ANTHRAX DATASET
# ============================================================

df = pd.read_csv(
    "ml/data/anthrax_2020_2023.csv"
)

# Remove duplicate records
df = df.drop_duplicates()


# Clean State and District values
df["State"] = df["State"].astype(str).str.strip()
df["District"] = df["District"].astype(str).str.strip()


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def dashboard():

    return render_template(
        "dashboard.html"
    )


# ============================================================
# HEALTH REPORT
# ============================================================

@app.route("/report", methods=["GET", "POST"])
def report():

    if request.method == "POST":

        animal_type = request.form.get(
            "animal_type"
        )

        age = request.form.get(
            "age"
        )

        affected = request.form.get(
            "affected"
        )

        symptoms = request.form.getlist(
            "symptoms"
        )

        duration = request.form.get(
            "duration"
        )


        # Print report in terminal

        print(
            "\n========== NEW HEALTH REPORT =========="
        )

        print(
            "Animal:",
            animal_type
        )

        print(
            "Age:",
            age
        )

        print(
            "Affected animals:",
            affected
        )

        print(
            "Symptoms:",
            symptoms
        )

        print(
            "Duration:",
            duration
        )

        print(
            "=======================================\n"
        )


        # Save report in session

        session["report"] = {

            "animal_type": animal_type,

            "age": age,

            "affected": affected,

            "symptoms": symptoms,

            "duration": duration

        }


        # Get unique states from dataset

        states = sorted(
            df["State"].unique()
        )


        # Open location page

        return render_template(
            "location.html",

            states=states,

            districts=[]

        )


    return render_template(
        "report.html"
    )


# ============================================================
# GET DISTRICTS FOR SELECTED STATE
# ============================================================

@app.route("/districts/<state>")
def get_districts(state):

    # Filter dataset by state

    state_data = df[
        df["State"].str.upper()
        == state.upper()
    ]


    # Get districts

    districts = sorted(
        state_data["District"].unique()
    )


    return jsonify(
        districts
    )


# ============================================================
# LOCATION
# ============================================================

@app.route("/location", methods=["GET", "POST"])
def location():

    if request.method == "POST":

        state = request.form.get(
            "state"
        )

        district = request.form.get(
            "district"
        )

        village = request.form.get(
            "village"
        )


        # ----------------------------------------------------
        # VALIDATE STATE
        # ----------------------------------------------------

        valid_states = [
            s.upper()
            for s in df["State"].unique()
        ]


        if not state or state.upper() not in valid_states:

            return "Invalid state selected."


        # ----------------------------------------------------
        # VALIDATE DISTRICT AGAINST STATE
        # ----------------------------------------------------

        valid_districts = df[
            df["State"].str.upper()
            == state.upper()
        ]["District"].str.lower().unique()


        if (
            not district
            or district.lower()
            not in valid_districts
        ):

            return "Invalid district selected for this state."


        # ----------------------------------------------------
        # SAVE LOCATION
        # ----------------------------------------------------

        session["location"] = {

            "state": state,

            "district": district,

            "village": village

        }


        print(
            "\n========== LOCATION =========="
        )

        print(
            "State:",
            state
        )

        print(
            "District:",
            district
        )

        print(
            "Village:",
            village
        )

        print(
            "==============================\n"
        )


        return redirect(
            "/analysis"
        )


    # --------------------------------------------------------
    # GET REQUEST
    # --------------------------------------------------------

    states = sorted(
        df["State"].unique()
    )


    return render_template(
        "location.html",

        states=states,

        districts=[]

    )


# ============================================================
# ANALYSIS
# ============================================================

@app.route("/analysis")
def analysis():

    report = session.get("report")
    location = session.get("location")

    # ========================================================
    # CHECK REPORT
    # ========================================================

    if not report:
        return "No health report found."

    # ========================================================
    # CHECK LOCATION
    # ========================================================

    if not location:
        return "No location found."

    state = location.get("state", "")
    district = location.get("district", "")

    # ========================================================
    # HISTORICAL LOCATION DATA
    # ========================================================

    location_data = df[
        (
            df["State"]
            .astype(str)
            .str.upper()
            == state.upper()
        )
        &
        (
            df["District"]
            .astype(str)
            .str.lower()
            == district.lower()
        )
    ]

    # ========================================================
    # HISTORICAL STATISTICS
    # ========================================================

    if len(location_data) > 0:

        historical_outbreaks = int(
            location_data["Outbreaks"].sum()
        )

        historical_attacks = int(
            location_data["Attacks"].sum()
        )

        historical_deaths = int(
            location_data["Deaths"].sum()
        )

        historical_cases = True

    else:

        historical_outbreaks = 0
        historical_attacks = 0
        historical_deaths = 0

        historical_cases = False

    # ========================================================
    # USER INPUT
    # ========================================================

    try:
        affected = int(
            report.get("affected", 1)
        )

    except (ValueError, TypeError):
        affected = 1

    # Prevent invalid negative values
    affected = max(affected, 1)

    symptoms = report.get("symptoms", [])

    if not isinstance(symptoms, list):
        symptoms = []

    # ========================================================
    # MACHINE LEARNING PREDICTION
    # ========================================================

    year = 2023

    # Current MVP assumption:
    # one outbreak and attacks proportional to
    # the number of affected animals.

    outbreaks = 1
    susceptible = affected
    attacks = affected

    input_data = pd.DataFrame(
        [
            {
                "Year": year,
                "Outbreaks": outbreaks,
                "Susceptible": susceptible,
                "Attacks": attacks
            }
        ]
    )

    try:

        predicted_deaths = model.predict(
            input_data
        )[0]

        ml_prediction = round(
            max(float(predicted_deaths), 0),
            2
        )

    except Exception:

        ml_prediction = 0.0

    # ========================================================
    # RISK BREAKDOWN
    # ========================================================

    # --------------------------------------------------------
    # 1. ML CONTRIBUTION
    # --------------------------------------------------------

    # Convert predicted deaths into a bounded risk
    # contribution so that one model output cannot
    # completely dominate the final score.

    if ml_prediction >= 10:

        ml_risk = 5

    elif ml_prediction >= 5:

        ml_risk = 4

    elif ml_prediction >= 2:

        ml_risk = 3

    elif ml_prediction > 0:

        ml_risk = 2

    else:

        ml_risk = 0

    # --------------------------------------------------------
    # 2. HISTORICAL CONTRIBUTION
    # --------------------------------------------------------

    historical_risk = 0

    if historical_cases:

        if historical_deaths >= 10:

            historical_risk = 3

        elif historical_deaths > 0:

            historical_risk = 2

        elif historical_attacks > 0:

            historical_risk = 1

        elif historical_outbreaks > 0:

            historical_risk = 1

    # --------------------------------------------------------
    # 3. SYMPTOM CONTRIBUTION
    # --------------------------------------------------------

    symptom_risk = 0

    # Every reported symptom contributes 1 point.

    symptom_risk += len(symptoms)

    # Severe symptoms receive additional weight.

    severe_symptoms = [
        "Difficulty breathing",
        "Weakness",
        "Loss of appetite"
    ]

    for symptom in symptoms:

        if symptom in severe_symptoms:

            symptom_risk += 2

    # Cap symptom contribution so that
    # many symptoms do not overwhelm the score.

    symptom_risk = min(
        symptom_risk,
        6
    )

    # --------------------------------------------------------
    # 4. AFFECTED ANIMAL CONTRIBUTION
    # --------------------------------------------------------

    if affected >= 10:

        affected_risk = 3

    elif affected >= 5:

        affected_risk = 2

    elif affected >= 2:

        affected_risk = 1

    else:

        affected_risk = 0

    # ========================================================
    # FINAL RISK SCORE
    # ========================================================

    risk_score = (

        ml_risk
        + historical_risk
        + symptom_risk
        + affected_risk

    )

    risk_score = round(
        float(risk_score),
        2
    )

    # ========================================================
    # DETERMINE RISK LEVEL
    # ========================================================

    if risk_score >= 10:

        risk_level = "HIGH"

    elif risk_score >= 5:

        risk_level = "MEDIUM"

    else:

        risk_level = "LOW"

    # ========================================================
    # SEND DATA TO ANALYSIS PAGE
    # ========================================================

    return render_template(

        "analysis.html",

        report=report,

        location=location,

        risk_level=risk_level,

        risk_score=risk_score,

        ml_prediction=ml_prediction,

        historical_cases=historical_cases,

        historical_outbreaks=historical_outbreaks,

        historical_attacks=historical_attacks,

        historical_deaths=historical_deaths,

        # New risk-breakdown values
        ml_risk=ml_risk,

        historical_risk=historical_risk,

        symptom_risk=symptom_risk,

        affected_risk=affected_risk

    )


# ============================================================
# START FLASK
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
