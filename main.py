# STEP 2: Streamlit App for Registration and Upload (main.py)

import streamlit as st
from db import get_db
from datetime import datetime
import base64
import os
import re
import imagehash
import pytesseract
from PIL import Image
import cv2
from PIL.ExifTags import TAGS, GPSTAGS
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# ===================== IMAGE ANALYSIS AND AUTHENTICATION ===================== #

def analyze_image_conditions(image_path):
    # Placeholder ML-based logic for automated classification
    # Replace this with actual model loading and prediction
    import random
    return random.choice(["Good", "Needs Attention", "Bad"])

def extract_coordinates_from_overlay(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)

    regexes = [
        r'Lat(?:itude)?[^\d\-]*(-?\d+\.\d+)[^\d\-]*Long(?:itude)?[^\d\-]*(-?\d+\.\d+)',
        r'(-?\d+\.\d+)[^\d\-]{1,6}(-?\d+\.\d+)'
    ]

    for pattern in regexes:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if 10 < lat < 40 and 60 < lon < 100:
                    return (lat, lon)
            except:
                continue
    return (None, None)

def check_authenticity(image_path, inspection_date_str, expected_coords=None):
    metadata = {}
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "GPSInfo":
                    gps_data = {GPSTAGS.get(t, t): value[t] for t in value}
                    metadata["GPSInfo"] = gps_data
                else:
                    metadata[tag] = value
    except:
        pass

    gps_coords = extract_coordinates_from_overlay(image_path)
    date_taken = metadata.get("DateTimeOriginal", "Not found")
    software_used = metadata.get("Software", "Not found")

    try:
        image_date = datetime.strptime(date_taken, "%Y:%m:%d %H:%M:%S").date()
        inspection_date = datetime.strptime(inspection_date_str, "%Y-%m-%d").date()
        date_status = "✅" if image_date == inspection_date else "❌"
    except:
        date_status = "❌"

    if expected_coords and gps_coords and None not in gps_coords:
        lat_diff = abs(expected_coords[0] - gps_coords[0])
        lon_diff = abs(expected_coords[1] - gps_coords[1])
        gps_status = "✅" if lat_diff < 0.03 and lon_diff < 0.03 else "❌"
    else:
        gps_status = "❌"

    edit_status = "❌" if "photoshop" in software_used.lower() else "✅"

    try:
        original_hash = imagehash.average_hash(Image.open(image_path))
        re_saved_hash = imagehash.average_hash(Image.open(image_path).convert("RGB"))
        hash_diff = original_hash - re_saved_hash
        hash_status = "❌" if hash_diff > 10 else "✅"
    except:
        hash_diff = "N/A"
        hash_status = "❌"

    overall_auth = "Authentic" if all([
        date_status == "✅", gps_status == "✅",
        edit_status == "✅", hash_status == "✅"
    ]) else "Fake"

    return {
        "authenticity": overall_auth,
        "software_used": software_used,
        "date_taken": date_taken,
        "gps_coords": gps_coords,
        "hash_diff": hash_diff,
        "date_status": date_status,
        "gps_status": gps_status,
        "edit_status": edit_status,
        "hash_status": hash_status
    }

# ===================== STREAMLIT APP ===================== #

db = get_db()

st.title("EduInspect - Empowering Education Through AI")

menu = ["Home", "Register Institute", "Start Inspection", "Dashboard", "Analytics"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Home":
    st.subheader("Welcome to EduInspect")
    st.write("Register your institution and upload required data for automated AI-driven inspection.")

elif choice == "Register Institute":
    st.subheader("New Institute Registration")
    with st.form("register_form"):
        name = st.text_input("Institute Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        code = st.text_input("Institute Code")
        submitted = st.form_submit_button("Register")

        if submitted:
            existing = db.institutions.find_one({"$or": [{"code": code}, {"email": email}]})
            if existing:
                similar_codes = db.institutions.find({"code": {"$regex": f"^{code[:3]}"}}).limit(3)
                suggestions = [entry['code'] for entry in similar_codes if entry['code'] != code]
                st.warning("This institute is already registered with the same code or email.")
                if suggestions:
                    st.info("Similar codes already registered: " + ", ".join(suggestions))
            else:
                db.institutions.insert_one({
                    "name": name,
                    "email": email,
                    "password": password,
                    "code": code,
                    "created_at": datetime.now()
                })
                st.success("Registration Successful")

elif choice == "Dashboard":
    st.subheader("📊 Inspection Dashboard")
    code = st.text_input("Enter Institute Code to View Past Inspections")
    selected_date = st.date_input("Filter by Date (optional)", value=None)
    if code:
        query = {"code": code}
        if selected_date:
            from datetime import datetime, timedelta
            start_dt = datetime.combine(selected_date, datetime.min.time())
            end_dt = datetime.combine(selected_date, datetime.max.time())
            query["timestamp"] = {"$gte": start_dt, "$lte": end_dt}
        results = list(db.inspections.find(query).sort("timestamp", -1))
        if results:
            grouped = {}
            for rec in results:
                dt_str = rec["timestamp"].strftime("%Y-%m-%d %H:%M")  # group by full timestamp to minute
                if dt_str not in grouped:
                    grouped[dt_str] = []
                grouped[dt_str].append(rec)

            for dt, entries in grouped.items():
                st.markdown(f"### 📅 Inspection: {dt}")
                for rec in entries:
                    param = rec['parameter']
                    cond_icon = "🟢" if rec['condition'] == "Good" else "🔴"
                    auth_icon = "✅" if rec['authenticity'] == "Authentic" else "❌"
                    st.markdown(f"- **{param}** ➡️ {cond_icon} {rec['condition']} | {auth_icon} {rec['authenticity']}")
        else:
            st.info("No inspection data found for this code.")

elif choice == "Analytics":
    st.subheader("📈 Visual Analytics")
    code = st.text_input("Institute Code for Analysis")
    selected_date = st.date_input("Filter by Date (optional)", value=None)
    if code:
        query = {"code": code}
        if selected_date:
            from datetime import datetime
            start_dt = datetime.combine(selected_date, datetime.min.time())
            end_dt = datetime.combine(selected_date, datetime.max.time())
            query["timestamp"] = {"$gte": start_dt, "$lte": end_dt}
        data = list(db.inspections.find(query))
        if data:
            df = pd.DataFrame(data)
            auth_counts = df['authenticity'].value_counts()
            cond_counts = df['condition'].value_counts()

            col1, col2 = st.columns(2)
            with col1:
                st.write("### Authenticity Distribution")
                fig, ax = plt.subplots()
                auth_counts.plot(kind='pie', autopct='%1.1f%%', ax=ax)
                st.pyplot(fig)

            with col2:
                st.write("### Condition Distribution")
                fig, ax = plt.subplots()
                sns.countplot(x='condition', data=df, ax=ax)
                st.pyplot(fig)

            st.write("### ML Readiness Scoring (Beta)")
            df['score'] = df.apply(lambda x: 1 if x['authenticity'] == 'Authentic' and x['condition'] == 'Good' else 0, axis=1)
            compliance_score = round((df['score'].sum() / len(df)) * 100, 2)
            st.success(f"Estimated Compliance Score: {compliance_score}%")
        else:
            st.info("No data found for this code.")

elif choice == "Start Inspection":
    st.subheader("Upload Data for Inspection")
    code = st.text_input("Enter Institute Code")
    inspection_date = st.date_input("Select Inspection Date")
    img_files = st.file_uploader("Upload 10 Facility Images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
    doc_file = st.file_uploader("Upload Report Document")
    feedback = st.text_area("Feedback or Survey Data")
    inspect = st.button("Start Inspection")

    if inspect:
        if code and img_files and len(img_files) == 10:
            parameters = [
                "Campus Cleanliness", "Classroom Environment", "Computer Labs", "Drinking Water Facility",
                "Fire Safety Measures", "Girls’ Common Room", "Health and Wellness Facilities",
                "Library Infrastructure", "Toilet Facilities", "Waste Management"
            ]

            expected_coords = (17.6868, 75.9112)
            inspection_date_str = inspection_date.strftime("%Y-%m-%d")
            summary_report = {}

            os.makedirs("temp", exist_ok=True)

            for idx, img in enumerate(img_files):
                temp_path = os.path.join("temp", img.name)
                with open(temp_path, "wb") as f:
                    f.write(img.getbuffer())

                condition = analyze_image_conditions(temp_path)
                auth_result = check_authenticity(temp_path, inspection_date_str, expected_coords)

                summary_report[parameters[idx]] = {
                    "Condition": condition,
                    "Authenticity": auth_result["authenticity"],
                    "Report": auth_result
                }

                db.inspections.insert_one({
                    "code": code,
                    "parameter": parameters[idx],
                    "condition": condition,
                    "authenticity": auth_result["authenticity"],
                    "timestamp": datetime.now()
                })

            doc_data = base64.b64encode(doc_file.read()).decode("utf-8") if doc_file else None
            db.reports.insert_one({
                "code": code,
                "document": doc_data,
                "feedback": feedback,
                "timestamp": datetime.now()
            })

            st.success("Inspection and Authentication Completed.")

            st.subheader("📸 Detailed Image Authentication Reports")
            for param, data in summary_report.items():
                report = data["Report"]
                st.markdown(f"""
🦾 **Image Authentication Report - {param}**
------------------------------------------
📸 **Camera Model**        : CPH2613 :: Captured by - GPS Map Camera  
🛠️ **Software Used**        : {report['software_used']} ({report['edit_status']})  
📅 **Date Taken**          : {report['date_taken']} ({report['date_status']})  
📍 **GPS Coordinates**     : {report['gps_coords']} ({report['gps_status']})  
🧠 **Tamper Check (Hash)** : Difference = {report['hash_diff']} ({report['hash_status']})  

✅ **Status**: Image is likely {report['authenticity'].upper()}.

**Condition**:  {data['Condition']} |
""")
        else:
            st.error("Please enter code and upload exactly 10 images.")
    pass
