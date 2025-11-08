 
# app.py
import streamlit as st
from datetime import date
import json
import pandas as pd
import networkx as nx
import webbrowser  # kept for potential use

# YOUR project logic functions (ensure logic.py is in same folder)
from logic import (
    init_db, save_profile, load_profile, save_daily_log,
    load_logs, evaluate_meals, load_grpm_index,
    register_user, get_user_credentials,
    delete_all_data
)

# ---------------------------------------------------------------------
# IMPORTANT: set_page_config must be the very first Streamlit call
# ---------------------------------------------------------------------
st.set_page_config(page_title="Personal Nutrition GRPM", layout="wide")

# --- Initialize DB and Session State ---
init_db()

# Initialize session state for authentication and page flow
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "page_mode" not in st.session_state:
    st.session_state["page_mode"] = 'register'

# --- Helper Functions (BMR/Macro Calculation) ---
def calculate_bmr(weight_kg, height_cm, age, sex):
    if sex and str(sex).lower().startswith("m"):
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

def calorie_target_for_maintain(tdee):
    return tdee

def macro_split_by_default(total_cal):
    cal_protein = 4
    cal_carb = 4
    cal_fat = 9
    pct_protein, pct_carb, pct_fat = 0.25, 0.50, 0.25
    grams_protein = round(total_cal * pct_protein / cal_protein)
    grams_carb = round(total_cal * pct_carb / cal_carb)
    grams_fat = round(total_cal * pct_fat / cal_fat)
    return {
        "protein_g": grams_protein,
        "carb_g": grams_carb,
        "fat_g": grams_fat,
        "pct": (pct_protein*100, pct_carb*100, pct_fat*100)
    }

# --- State Management Functions ---
def set_page_mode(mode):
    st.session_state["page_mode"] = mode

def logout():
    st.session_state["authenticated"] = False
    st.session_state["page_mode"] = 'login'
    if "username" in st.session_state:
        del st.session_state["username"]
    st.rerun()  # Final fixed rerun

# --- Authentication Pages ---
def register_page():
    st.title("🧬 Personal Nutrition Advisor — Register")
    st.markdown("Create an account to access your personalized nutrition plan.")

    with st.form("register_form"):
        new_username = st.text_input("Choose Username", key="reg_username")
        new_password = st.text_input("Choose Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")

        submitted = st.form_submit_button("✅ Create Account")

        if submitted:
            if not new_username or not new_password:
                st.error("Username and password cannot be empty.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                if register_user(new_username, new_password):
                    st.success("Registration successful! Please log in.")
                    st.session_state["page_mode"] = 'login'
                    st.rerun()
                else:
                    st.error("Registration failed. That username may already be taken.")

    st.markdown("---")
    st.button("Already have an account? Log in here.", on_click=set_page_mode, args=('login',))


def login_page():
    st.title("🔐 Personal Nutrition Advisor — Login")

    def attempt_login():
        username = st.session_state["login_username"]
        password = st.session_state["login_password"]

        stored_password = get_user_credentials(username)

        if stored_password and stored_password == password:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["page_mode"] = 'app'
            st.rerun()
        else:
            st.session_state["authenticated"] = False
            st.error("Login failed: Invalid username or password.")

    with st.form("login_form"):
        st.text_input("Username", key="login_username")
        st.text_input("Password", type="password", key="login_password")
        st.form_submit_button("🔑 Login", on_click=attempt_login)

    st.markdown("---")
    st.button("Need an account? Register here.", on_click=set_page_mode, args=('register',))


# ---------- New: ChatGPT link placed inside sidebar (red) ----------
def sidebar_chatgpt_link():
    """
    Places a visible red ChatGPT link inside the sidebar.
    This avoids fixed positioning and keeps link stable on scroll.
    """
    st.sidebar.markdown("---")
    # Use HTML to style the link strongly red and button-like.
    st.sidebar.markdown(
        """
        <div style="text-align: center; margin-top: 6px;">
            <a href="https://chatgpt.com/" target="_blank" rel="noreferrer noopener" style="
                display: inline-block;
                color: white;
                background-color: #d32f2f; /* strong red */
                padding: 8px 12px;
                border-radius: 6px;
                text-decoration: none;
                font-weight: 600;
            ">
                🔗 Open ChatGPT
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )


# --- Main Application Logic Function ---
def run_app():
    st.title("Personal Nutrition Advisor — GRPM 🧬")

    # ---------- Sidebar: Profile form and Admin Wipe Button ----------
    st.sidebar.header("User Profile 👤")
    profile = load_profile() or {}
    with st.sidebar.form("profile_form"):
        name = st.text_input("Name", value=profile.get("name",""))
        age = st.number_input("Age", min_value=0, max_value=120, value=int(profile.get("age") or 25))
        sex_options = ["Male", "Female", "Other"]
        current_sex = profile.get("sex")
        sex_index = sex_options.index(current_sex) if current_sex in sex_options else 0
        sex = st.selectbox("Sex", options=sex_options, index=sex_index)
        height = st.number_input("Height (cm)", min_value=50.0, max_value=250.0, value=float(profile.get("height_cm") or 170.0))
        weight = st.number_input("Weight (kg)", min_value=20.0, max_value=500.0, value=float(profile.get("weight_kg") or 70.0))
        notes = st.text_area("Notes / Genotype Info (optional)", value=profile.get("notes",""))

        submitted = st.form_submit_button("💾 Save Profile")
        if submitted:
            p = {
                "name": name, "age": age, "sex": sex,
                "height_cm": height, "weight_kg": weight,
                "notes": notes
            }
            save_profile(p)
            st.success("Profile saved!")

        st.sidebar.button("Logout", on_click=logout)

    # Place the ChatGPT link in the sidebar (below Logout)
    sidebar_chatgpt_link()

    # --- ADMIN WIPE BUTTON (FIXED LOGIC) ---
    st.sidebar.markdown("---")
    st.sidebar.header("Admin Actions ⚠️")

    def wipe_and_logout():
        """Deletes the database file, resets state, and re-initializes DB."""
        data_deleted = delete_all_data()

        st.session_state["authenticated"] = False
        st.session_state["page_mode"] = 'register'
        if "username" in st.session_state:
            del st.session_state["username"]

        if data_deleted:
            st.warning("Database file deleted. Starting fresh on the Register page.")
        else:
            st.error("Failed to delete database file. Check console/permissions.")

        st.rerun()

    st.sidebar.button(
        "🔥 DELETE ALL DATA & Log Out",
        on_click=wipe_and_logout,
        help="WARNING: This deletes ALL user accounts, profiles, and logs by removing the database file."
    )
    st.sidebar.markdown("---")

    # ---------- Main area: daily log ----------
    st.header("🍎 Daily Food Log & Evaluation ")
    col1, col2 = st.columns([2,1])

    with col1:
        st.subheader("Add Today's Meals")
        log_date = st.date_input("Date", value=date.today())
        st.write("Enter meals (simple format): meal name, items comma-separated, total calories for the meal.")

        if 'n_meals' not in st.session_state:
            st.session_state['n_meals'] = 3

        n_meals = st.number_input("Number of meals to add", min_value=1, max_value=10, value=st.session_state['n_meals'], key="n_meals_input")
        st.session_state['n_meals'] = int(n_meals)

        meal_entries = []
        for i in range(st.session_state['n_meals']):
            with st.expander(f"Meal {i+1}", expanded=(i==0)):
                mname = st.text_input(f"Meal Name {i+1}", key=f"mname_{i}")
                items = st.text_input(f"Items (comma separated) {i+1}", key=f"items_{i}", placeholder="e.g., oats, milk, banana")
                cal = st.number_input(f"Calories {i+1}", min_value=0.0, value=0.0, key=f"cal_{i}")
                meal_entries.append({"name": mname or f"Meal {i+1}", "items":[it.strip() for it in items.split(",") if it.strip()], "calories": cal})

        if st.button("✨ Evaluate & Save Log"):
            total_cal, score, assessment = evaluate_meals(meal_entries, profile)
            save_daily_log(log_date.isoformat(), json.dumps(meal_entries), total_cal, score, assessment)
            st.balloons()
            st.success(f"Log saved for **{log_date}**! **Score:** **{score}** ({assessment}) | **Total Calories:** **{total_cal}** kcal")

    with col2:
        st.subheader("Latest Assessment")
        logs = load_logs(limit=7)
        if not logs.empty:
            latest = logs.iloc[0]
            try:
                latest_date = pd.to_datetime(latest["date"])
                latest_date_str = latest_date.strftime("%Y-%m-%d")
            except Exception:
                latest_date_str = str(latest.get("date", "unknown"))

            latest_score = latest.get("score")
            assessment = str(latest.get("assessment", "N/A"))
            total_cal = latest.get("calories", "N/A")

            st.write(f"**Date:** **{latest_date_str}**")
            if latest_score is not None:
                st.metric("GRPM Score (0-100)", float(latest_score), delta_color="off")
            else:
                st.info(f"Score: N/A")

            st.metric("Total Calories", f"{total_cal} kcal", delta_color="off")
            st.write("**Assessment:**", f"*{assessment}*")

            with st.expander("View Meals JSON"):
                try:
                    st.json(json.loads(latest["meals"]))
                except Exception:
                    st.write(latest.get("meals", "No meal data"))
        else:
            st.info("No logs yet. Add today's meals on the left.")

    # ---------- History & Chart ----------
    st.header("History 📈")
    logs_full = load_logs(limit=365)
    if logs_full.empty:
        st.info("No history yet.")
    else:
        df = logs_full.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        st.markdown("**GRPM Score Trend Over Time**")
        st.line_chart(df.set_index('date')['score'])

        st.markdown("**Latest 50 Log Entries**")
        st.dataframe(df[['date','calories','score','assessment']].tail(50).sort_values('date', ascending=False))

    # ---------- Personalized Nutrition Plan (calories & macros) ----------
    st.header("Personalized Nutrition Plan 📋")
    profile = load_profile()
    if not profile:
        st.info("Save your profile to see personalized calorie & macro recommendations.")
    else:
        bmr = calculate_bmr(profile["weight_kg"], profile["height_cm"], int(profile["age"]), profile["sex"])
        mult = 1.55
        tdee = round(bmr * mult)
        target_cal = round(calorie_target_for_maintain(tdee))
        macros = macro_split_by_default(target_cal)
        p_pct, c_pct, f_pct = macros["pct"]

        st.subheader(f"Goal: Maintain Weight (Defaulted)")
        st.write(f"**Estimated BMR:** **{round(bmr)}** kcal/day")
        st.write(f"**Estimated TDEE:** **{tdee}** kcal/day")
        st.success(f"**Target Calories for your goal:** **{target_cal}** kcal/day")

        st.markdown("### Recommended Macronutrients (Balanced Split):")

        macro_data = {
            "Macronutrient": ["Protein", "Carbohydrates", "Fat"],
            "Grams/Day": [macros['protein_g'], macros['carb_g'], macros['fat_g']],
            "Percentage of Calories": [f"{p_pct:.0f}%", f"{c_pct:.0f}%", f"{f_pct:.0f}%"]
        }
        st.dataframe(pd.DataFrame(macro_data).set_index("Macronutrient"))

        st.info(f"This is a **Balanced** macro split (Protein:{p_pct:.0f}%, Carb:{c_pct:.0f}%, Fat:{f_pct:.0f}%) based on your profile.")


# --- Application Entry Point: Controls the flow ---
if st.session_state["page_mode"] == 'app' and st.session_state["authenticated"]:
    run_app()
elif st.session_state["page_mode"] == 'login':
    login_page()
else:
    register_page()
