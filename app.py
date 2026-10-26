import re
import random
import hmac
import hashlib
import os
import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

st.set_page_config(page_title="Dreamztree Meta Report", page_icon="D", layout="wide")

# Default mapping from the existing Dreamztree report. Edit or extend in the Mapping editor.
DEFAULT_MAPPINGS = [
    ("Jincy |01| healthacreleads campaign", "Jincy", "Healthcare", "Mangaf"),
    ("hishana/bahrain/computer/29/11", "Hishana", "Computer", "Bahrain"),
    ("healthcare | hishana | bahrain | 2/12/2025", "Hishana", "Healthcare", "Bahrain"),
    ("healthcare placement | arya | 15/12/2025 engagement", "Arya", "Healthcare", "Salmiya"),
    ("german | ligin | 20/1/26 engagement campaign", "Ligin", "German", "Salmiya"),
    ("healthcare | ligin | 22/1/26 engagement campaign", "Ligin", "Healthcare", "Salmiya"),
    ("healthcare | seetha | 19 /2/26 engagement campaign", "Seetha", "Healthcare", "Bahrain"),
    ("computer | hishana | 19/2/26", "Hishana", "Computer", "Bahrain"),
    ("computer | seetha | 19/2/26", "Seetha", "Computer", "Bahrain"),
    ("mangaf | german |27/2/26", "Aswathy", "German", "Salmiya"),
    ("ligin | ielts | 28/2/26", "Ligin", "IELTS", "Salmiya"),
    ("jincy | logistics | 2/3/26", "Jincy", "Logistics", "Mangaf"),
    ("arya | philipi | 14/3/26", "Arya", "Philipi", "Salmiya"),
    ("sethu | boost video | 15/3/26", "Sethu", "Boost Video", "Mangaf"),
    ("jincy | safety course | 26/3/26", "Jincy", "Safety Course", "Mangaf"),
    ("healthcare | seetha | 27/3/26", "Seetha", "Healthcare", "Bahrain"),
    ("practical video | arya | 28/3/26", "Arya", "Practical Video", "Salmiya"),
    ("teacher training | arya | 30/3/26", "Arya", "Teacher Training", "Salmiya"),
    ("computer | arya | 30/3/26", "Arya", "Computer", "Salmiya"),
    ("sethu | testimonial healthcare | 2/4/26", "Sethu", "Healthcare", "Mangaf"),
    ("jincy | professional career courses | 3/4/26", "Jincy", "Professional Courses", "Mangaf"),
    ("prometric | arya | 4/3/26", "Arya", "Prometric", "Salmiya"),
    ("jincy | teacher training | 13/4/26", "Jincy", "Teacher Training", "Mangaf"),
    ("jincy | german  | 13/4/26", "Jincy", "German", "Mangaf"),
    ("hishana | tuition | 13/4/26", "Hishana", "Tuition", "Bahrain"),
    ("ligin | prometric | 16/4/26", "Ligin", "Prometric", "Salmiya"),
    ("arya  | healthcare(intership) | 18/4/26", "Arya", "Healthcare", "Salmiya"),
    ("arya  | spa | 30/4/26", "Arya", "Spa", "Salmiya"),
    ("jincy | autocad | 30/4/26", "Jincy", "Autocad", "Mangaf"),
    ("jincy | hospital administration | 5/5/26", "Jincy", "Hospital Admin", "Mangaf"),
    ("jincy | language training | 6/5/26", "Jincy", "Language Training", "Mangaf"),
    ("caregiving anakha 09/05/2026", "Anakha", "Caregiving", "Bahrain"),
    ("hishana new | healthcare | 11/5/26", "Hishana", "Healthcare", "Bahrain"),
    ("hishana | phonics | 10/5/26", "Hishana", "Phonics", "Bahrain"),
    ("hishna new | tuition | 10/5/26", "Hishana", "Tuition", "Bahrain"),
    ("hishana | healthcare | 11/5/26", "Hishana", "Healthcare", "Bahrain"),
    ("ligin | healthcare  | 16/5/26", "Ligin", "Healthcare", "Salmiya"),
    ("jincy | ielts  | 16/5/26", "Jincy", "IELTS", "Mangaf"),
    ("arya  | spa video | 18/5/26", "Arya", "Spa", "Salmiya"),
    ("jincy   | influencer ad new | 18/5/26", "Jincy", "Influencer Ad", "Mangaf"),
    ("seetha  | tuition  | 18/5/26", "Seetha", "Tuition", "Bahrain"),
    ("vedhika | healthcare | 19/5/26", "Vedhika", "Healthcare", "Kerala"),
    ("arya  | spa ad new | 20/5/26", "Arya", "Spa", "Salmiya"),
    ("vedhika | healthcare | 20/5/26", "Vedhika", "Healthcare", "Kerala"),
    ("jincy | language training | 20/5/26", "Jincy", "Language Training", "Mangaf"),
    ("hishana  | healthcare | 21/5/26", "Hishana", "Healthcare", "Bahrain"),
    ("seetha | healthcare | 25/5/26", "Seetha", "Healthcare", "Bahrain"),
    ("seetha | tution | 29-05-2026", "Seetha", "Tuition", "Bahrain"),
    ("sethu | tuition | 27-05-2026", "Sethu", "Tuition", "Mangaf"),
    ("seetha  | healthcare | 1/6/26", "Seetha", "Healthcare", "Bahrain"),
    ("anakha | healthcare | 3/6/26", "Anakha", "Healthcare", "Bahrain"),
    ("montessori | ligin  | 5/6/26", "Ligin", "Montessori", "Salmiya"),
    ("ligin | hospital administration | 05 | 06 | 2026", "Ligin", "Hospital Admin", "Salmiya"),
    ("healthcare  | vedhika | 9/6/26", "Vedhika", "Healthcare", "Kerala"),
    ("anakha | summer camp | 9/6/26", "Anakha", "Summer Camp", "Bahrain"),
    ("anakha | healthcare | 10/6/26", "Anakha", "Healthcare", "Bahrain"),
    ("ligin  | josun video | 11/6/26", "Ligin", "Josun Video", "Salmiya"),
    ("tuition  | anakha | 12/6/26", "Anakha", "Tuition", "Bahrain"),
    ("jincy | computer  |  14/6/26", "Jincy", "Computer", "Mangaf"),
    ("jincy  | post bsc | 14/6/26", "Jincy", "Post BSC", "Mangaf"),
    ("nissi | nanny course  | 16/6/26", "Nissi", "Nanny Course", "Mangaf"),
    ("vipin  | healthcare  | 16/6/26", "Vipin", "Healthcare", "Kerala"),
    ("aswathy | healthcare  | 18/6/26", "Aswathy", "Healthcare", "Kerala"),
    ("anupama | healthcare | 18/6/26", "Anupama", "Healthcare", "Kerala"),
    ("anupama | healthcare | 20/6/26", "Anupama", "Healthcare", "Kerala"),
    ("seetha  | ielts | 24/6/26", "Seetha", "IELTS", "Bahrain"),
    ("seetha  | cg | 24/6/26", "Seetha", "CG", "Bahrain"),
    ("anupama | practical video | 24/6/26", "Anupama", "Practical Video", "Kerala"),
    ("nissi | computer | 25/6/26", "Nissi", "Computer", "Mangaf"),
    ("sushma | ielts | 25/6/26", "Sushma", "IELTS", "Mangaf"),
    ("shelbin hiring gda&gna 6/29/2026 campaign", "Shelbin", "Hiring", "Kerala"),
    ("sushma autocad  7/7/2026 campaign", "Sushma", "Autocad", "Mangaf"),
    ("nursing  tutor h shelbin 08/07/2026", "Shelbin", "Nursing Tutor", "Kerala"),
    ("roshni cg 08/07/2026", "Roshni", "CG", "Kerala"),
    ("hishana pte 10/07/2026", "Hishana", "PTE", "Bahrain"),
    ("nissi cg 16/07/2026", "Nissi", "CG", "Mangaf"),
    ("hiring | german | dani | 24/6/26", "Dani", "German", "Kerala"),
    ("dani  cg 20/07/2026", "Dani", "CG", "Kerala"),
    ("hospital am shelbin 31/07/2026", "Shelbin", "Hospital Admin", "Kerala"),
    ("ham sushma 31/07/2026", "Sushma", "HAM", "Mangaf"),
    ("sushma teacher 31/07/2026", "Sushma", "Teacher Training", "Mangaf"),
    ("shelbin hr 04/08/2026", "Shelbin", "HR", "Kerala"),
    ("dani | healthcare  | 7/8/26", "Dani", "Healthcare", "Kerala"),
    ("anupama j&v 11/08/2026", "Anupama", "J&V Video", "Kerala"),
    ("jincy j&v 12/08/2026", "Jincy", "J&V Video", "Mangaf"),
    ("jincy | logistics | 13/8/26", "Jincy", "Logistics", "Mangaf"),
    ("hishana | ielts | 13/8/26", "Hishana", "IELTS", "Bahrain"),
    ("sushma | language training | 14/8/26", "Sushma", "Language Training", "Mangaf"),
    ("hishana  | computer | 14/8/26", "Hishana", "Computer", "Bahrain"),
    ("seetha | language training | 14/8/26", "Seetha", "Language Training", "Bahrain"),
    ("sushma | safety course | 17/8/26", "Sushma", "Safety Course", "Mangaf"),
    ("arya gda 24/08/2026", "Arya", "GDA", "Salmiya"),
    ("hishana tuition 24/08/2026", "Hishana", "Tuition", "Bahrain"),
    ("arya cg phili 27/08/2026", "Arya", "CG", "Salmiya"),
    ("nissi tuition 27/08/2026", "Nissi", "Tuition", "Mangaf"),
    ("hishana tuition 27/08/2026", "Hishana", "Tuition", "Bahrain"),
    ("nissi house keeping 28/08/2026", "Nissi", "House Keeping", "Mangaf"),
    ("nissi | tuition video | 31/8/26", "Nissi", "Tuition Video", "Mangaf"),
    ("hishana tuition 31/08/2026", "Hishana", "Tuition", "Bahrain"),
    ("aswathy cg 29/08/2026", "Aswathy", "CG", "Kerala"),
    ("ligin | german | 3/9/26", "Ligin", "German", "Salmiya"),
    ("ligin teacher training 3/9/26", "Ligin", "Teacher Training", "Salmiya"),
    ("jincy | language training | 4/9/26", "Jincy", "Language Training", "Mangaf"),
    ("jincy safety 05/09/2026", "Jincy", "Safety Course", "Mangaf"),
    ("hishana | healthcare | 5/9/26", "Hishana", "Healthcare", "Bahrain"),
    ("hishana german 05/09/2026", "Hishana", "German", "Bahrain"),
    ("shabna commerce 05/09/2026", "Shabna", "Commerce", "Bahrain"),
    ("jincy | healthcare | call | 7/9/26", "Jincy", "Healthcare", "Mangaf"),
    ("arya call cg 07/09/2026", "Arya", "CG", "Salmiya"),
    ("renjith medical hiring 07/09/2026", "Renjith", "Medical Hiring", "Kerala"),
    ("renjith coordinator hiring 09/09/2026", "Renjith", "Coordinator Hiring", "Kerala"),
    ("anju hiring 11/09/2026", "Anju", "Hiring", "Kerala"),
    ("hishana phys tuition 12/09/2026", "Hishana", "Phys Tuition", "Bahrain"),
    ("roshni hiring gda 12/09/2026", "Roshni", "Hiring GDA", "Kerala"),
    ("roshni | healthcare | 14/9/26", "Roshni", "Healthcare", "Kerala"),
    ("roshni german 21/09/2026", "Roshni", "German", "Kerala"),
    ("jincy | digital marketing | 23/9/26", "Jincy", "Digital Marketing", "Mangaf"),
    ("vipin kerala | healthcare | 1/10/26", "Vipin", "Healthcare", "Kerala"),
    ("aswathy kuwait computer 02/10/2026", "Aswathy", "Computer", "Mangaf"),
    ("hishana tuition 03/10/2026", "Hishana", "Tuition", "Bahrain"),
    ("hishana tuition 05/10/2026", "Hishana", "Tuition", "Bahrain"),
    ("test - arya gda 24/08/2026", "Arya", "GDA", "Salmiya"),
    ("arya cg 08/10/2026", "Arya", "CG", "Salmiya"),
    ("roshni cg 10/10/2026", "Roshni", "CG", "Kerala"),
    ("arya | healthcare | 12/10/26", "Arya", "Healthcare", "Salmiya"),
    ("aswathy kuwait | healthcare | 12/10/26", "Aswathy", "Healthcare", "Mangaf"),
    ("shabna | healthcare | testimonials | 15/10/26", "Shabna", "Healthcare", "Bahrain"),
    ("nissi tuition 15/10/2026", "Nissi", "Tuition", "Mangaf"),
    ("aswathy tuition kuwait 15/10/2026", "Aswathy", "Tuition", "Mangaf"),
    ("awsathy cg 16/10/2026", "Aswathy", "CG", "Kerala"),
    ("awsathy cg kerala 16/10/2026", "Aswathy", "CG", "Kerala"),
    ("ajay dm 17/10/2026", "Ajay", "Digital Marketing", "Kerala"),
    ("vipin dca 20/10/2026", "Vipin", "DCA", "Kerala"),
    ("vipin cg 08/09/2026", "Vipin", "CG", "Kerala"),
    ("nissi hiring 09/09/2026", "Nissi", "Hiring", "Mangaf"),
    ("vipin cg", "Vipin", "CG", "Kerala"),
    ("shabna | healthcare 19 /2/26 engagement campaign", "Shabna", "Healthcare", "Bahrain"),
    ("shabna|computer | 19/2/26", "Shabna", "Computer", "Bahrain"),
    ("aswathy kuwait | boost video | 15/3/26", "Aswathy", "Boost Video", "Mangaf"),
    ("aswathy kuwait| testimonial healthcare | 2/4/26", "Aswathy", "Healthcare", "Mangaf"),
    ("shabna | healthcare | 1/6/26", "Shabna", "Healthcare", "Bahrain"),
    ("shabna | language training | 14/8/26", "Shabna", "Language Training", "Bahrain"),
    ("jincy healthcare 24/08/2026", "Jincy", "Healthcare", "Mangaf"),
    ("aswathy kerala | healthcare | 1/10/26", "Aswathy", "Healthcare", "Kerala"),
    ("aswathy cg kerala 16/10/2026", "Aswathy", "CG", "Kerala"),
    ("hishana cg call 17/10/2026", "Hishana", "CG", "Bahrain"),
    ("jincy cg 21/10/2026", "Jincy", "CG", "Mangaf"),
]

BRANCH_ORDER = ["Mangaf", "Salmiya", "Bahrain", "Kerala"]
STAFF_ORDER = {
    "Mangaf": ["Jincy", "Sethu", "Nissi", "Sushma", "Aswathy"],
    "Salmiya": ["Arya", "Ligin", "Aswathy"],
    "Bahrain": ["Hishana", "Anakha", "Seetha", "Shabna"],
    "Kerala": ["Anupama", "Vedhika", "Vipin", "Aswathy", "Roshni", "Shelbin", "Ajay", "Dani", "Renjith", "Anju", "Biju"],
}
MANUAL_FALLBACK_KWD_FACTOR = 0.308  # Previous organization setting; used only if API fails or manual mode is selected.

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_usd_kwd_rate():
    """Fetch the latest published USD->KWD reference rate; cache for 24 hours.

    Frankfurter's ECB-based feed does not cover every currency, including KWD,
    so use the free open.er-api.com latest-rates endpoint instead.
    """
    url = "https://open.er-api.com/v6/latest/USD"
    response = requests.get(url, timeout=8)
    response.raise_for_status()
    payload = response.json()
    if payload.get("result") != "success":
        raise ValueError("The exchange-rate provider did not return success.")
    rate = float(payload["rates"]["KWD"])
    rate_date = str(payload.get("time_last_update_utc", "")).strip()
    if rate <= 0 or not rate_date:
        raise ValueError("The API returned an invalid rate or missing update date.")
    return rate, rate_date

def normalize(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

def read_mapping_file(upload):
    if upload is None:
        return pd.DataFrame(DEFAULT_MAPPINGS, columns=["Campaign", "Staff", "Course", "Branch"])
    try:
        df = pd.read_excel(upload) if upload.name.lower().endswith((".xlsx", ".xls")) else pd.read_csv(upload)
        cols = {normalize(c): c for c in df.columns}
        needed = ["campaign", "staff", "course", "branch"]
        if not all(x in cols for x in needed):
            st.error("Mapping file must have columns: Campaign, Staff, Course, Branch.")
            return pd.DataFrame(DEFAULT_MAPPINGS, columns=["Campaign", "Staff", "Course", "Branch"])
        return df[[cols[x] for x in needed]].rename(columns={cols[x]: x.title() for x in needed}).fillna("")
    except Exception as e:
        st.error(f"Could not read mapping file: {e}")
        return pd.DataFrame(DEFAULT_MAPPINGS, columns=["Campaign", "Staff", "Course", "Branch"])

def infer_campaign(name, mappings):
    """Resolve campaign using exact/partial mappings, staff aliases, course clues and branch rules."""
    original_name = str(name or "")
    key = normalize(original_name)
    tokens = set(key.split())

    # Canonical staff-to-branch rules. Aswathy's branch depends on the course.
    staff_branch_rules = {
        "Jincy": "Mangaf", "Sethu": "Mangaf", "Nissi": "Mangaf", "Sushma": "Mangaf",
        "Arya": "Salmiya", "Ligin": "Salmiya",
        "Hishana": "Bahrain", "Anakha": "Bahrain", "Seetha": "Bahrain", "Shabna": "Bahrain",
        "Anupama": "Kerala", "Vedhika": "Kerala", "Vipin": "Kerala", "Roshni": "Kerala",
        "Shelbin": "Kerala", "Ajay": "Kerala", "Dani": "Kerala", "Renjith": "Kerala",
        "Anju": "Kerala", "Biju": "Kerala", "Aswathy": "",
    }
    staff_aliases = {
        "Aswathy": ["aswathy", "awsathy", "aswathi"],
        "Hishana": ["hishana", "hishna"],
        "Shabna": ["shabna", "shabana"],
        "Vipin": ["vipin", "vipin"],
        "Anupama": ["anupama"],
    }

    # Start with any exact mapping, but keep filling missing fields rather than returning early.
    staff = course = branch = ""
    exact = mappings[mappings["Campaign"].astype(str).map(normalize) == key]
    if not exact.empty:
        row = exact.iloc[0]
        staff = str(row.get("Staff", "") or "").strip()
        course = str(row.get("Course", "") or "").strip()
        branch = str(row.get("Branch", "") or "").strip()

    # Staff can appear anywhere in the campaign, including known spelling variants.
    hits = []
    for canonical in staff_branch_rules:
        aliases = staff_aliases.get(canonical, [canonical.lower()])
        if any(re.search(r"\b" + re.escape(normalize(alias)) + r"\b", key) for alias in aliases):
            hits.append(canonical)
    hits = list(dict.fromkeys(hits))
    if not staff and len(hits) == 1:
        staff = hits[0]

    # Identify a course from the whole campaign string. Longer/more-specific terms first.
    course_aliases = [
        (r"\bcaregiving\b|\bcaregiver\b", "Caregiving"),
        (r"\bpractical\s+video\b", "Practical Video"),
        (r"\bj\s*&\s*v\b|\bj\s+and\s+v\s+video\b|\bj\s+v\s+video\b", "J&V Video"),
        (r"\btestimonial\s+healthcare\b", "Healthcare"),
        (r"\bnursing\s+tutor\b", "Nursing Tutor"),
        (r"\bhospital\s+administration\b|\bhospital\s+admin\b", "Hospital Admin"),
        (r"\bteacher\s+training\b", "Teacher Training"),
        (r"\blanguage\s+training\b", "Language Training"),
        (r"\bdigital\s+marketing\b|\bdm\b", "Digital Marketing"),
        (r"\bsafety\s+course\b|\bsafety\b", "Safety Course"),
        (r"\bhealthcare\b|\bhealth\s+care\b", "Healthcare"),
        (r"\bcomputer\b", "Computer"), (r"\bgerman\b", "German"),
        (r"\btuition\b|\btution\b", "Tuition"), (r"\bielts\b", "IELTS"),
        (r"\bprometric\b", "Prometric"), (r"\bmontessori\b", "Montessori"),
        (r"\bphonics\b", "Phonics"), (r"\bautocad\b", "Autocad"),
        (r"\blogistics\b", "Logistics"), (r"\bnanny\s+course\b", "Nanny Course"),
        (r"\bhouse\s+keeping\b", "House Keeping"), (r"\bsummer\s+camp\b", "Summer Camp"),
        (r"\bmedical\s+hiring\b", "Medical Hiring"), (r"\bcoordinator\s+hiring\b", "Coordinator Hiring"),
        (r"\bhiring\b", "Hiring"), (r"\bcommerce\b", "Commerce"),
        (r"\bspa\b", "Spa"), (r"\bgda\b", "GDA"), (r"\bgna\b", "GNA"),
        (r"\bcg\b", "CG"), (r"\bdca\b", "DCA"), (r"\bpte\b", "PTE"),
        (r"\bham\b", "HAM"), (r"\bhr\b", "HR"), (r"\bphili(?:pi)?\b", "Philipi"),
        (r"\bboost\s+video\b", "Boost Video"), (r"\bcomputer\s+course\b", "Computer"),
    ]
    if not course:
        for pattern, label in course_aliases:
            if re.search(pattern, key):
                course = label
                break

    # Recognize an explicit branch in the campaign.
    explicit_branch = next((b for b in BRANCH_ORDER if re.search(r"\b" + re.escape(normalize(b)) + r"\b", key)), "")
    if not branch and explicit_branch:
        branch = explicit_branch

    # Use mapping evidence to infer missing fields from any two known fields when unique.
    m = mappings.copy().fillna("")
    for col in ["Staff", "Course", "Branch"]:
        m[col] = m[col].astype(str).str.strip()
    if staff and course and not branch:
        rows = m[(m.Staff.map(normalize) == normalize(staff)) & (m.Course.map(normalize) == normalize(course))]
        options = set(rows.Branch[rows.Branch != ""])
        if len(options) == 1:
            branch = next(iter(options))
    if staff and branch and not course:
        rows = m[(m.Staff.map(normalize) == normalize(staff)) & (m.Branch.map(normalize) == normalize(branch))]
        # Only infer a course if the campaign wording or historical match identifies one uniquely.
        campaign_rows = rows[rows.Campaign.astype(str).map(normalize).map(lambda x: any(t in key.split() for t in x.split() if len(t) > 3))]
        options = set(campaign_rows.Course[campaign_rows.Course != ""])
        if len(options) == 1:
            course = next(iter(options))
    if course and branch and not staff:
        rows = m[(m.Course.map(normalize) == normalize(course)) & (m.Branch.map(normalize) == normalize(branch))]
        options = set(rows.Staff[rows.Staff != ""])
        if len(options) == 1:
            staff = next(iter(options))

    # Staff-to-branch rules fill the branch after staff/course detection.
    if staff == "Aswathy":
        c = normalize(course)
        if "computer" in c or "tuition" in c or "boost video" in c:
            branch = branch or "Mangaf"
        elif "german" in c:
            branch = branch or "Salmiya"
        elif any(word in c.split() for word in ["healthcare", "cg"]):
            branch = branch or "Kerala"
        elif explicit_branch:
            branch = explicit_branch
    elif staff and not branch:
        branch = staff_branch_rules.get(staff, "")

    # Staff branch rules are authoritative for staff with one fixed branch.
    if staff in staff_branch_rules and staff != "Aswathy":
        branch = staff_branch_rules[staff]

    # Last chance: exact historical mapping by campaign similarity/known course+staff.
    if staff and course and not branch:
        rows = m[(m.Staff.map(normalize) == normalize(staff)) & (m.Course.map(normalize) == normalize(course))]
        options = set(rows.Branch[rows.Branch != ""])
        if len(options) == 1:
            branch = next(iter(options))

    if staff and course and branch:
        return staff, course, branch, ("Exact mapping" if not exact.empty else "Auto-inferred")
    return staff, course, branch, "Needs review"

def inject_premium_theme():
    """Apply Dreamztree's brighter, colorful premium dashboard theme."""
    st.markdown("""
    <style>
    @keyframes dt-fade-up {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes dt-gradient-drift {
      0%, 100% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
    }
    @keyframes dt-soft-glow {
      0%, 100% { box-shadow: 0 18px 50px rgba(0,0,0,.20), 0 0 0 rgba(139,92,246,0); }
      50% { box-shadow: 0 18px 50px rgba(0,0,0,.20), 0 0 28px rgba(139,92,246,.16); }
    }
    @keyframes dt-float {0%,100% {transform:translate3d(0,0,0) scale(1)} 50% {transform:translate3d(0,-28px,0) scale(1.08)}}
    @keyframes dt-border-flow {0% {background-position:0% 50%} 50% {background-position:100% 50%} 100% {background-position:0% 50%}}
    @keyframes dt-shimmer {0% {background-position:-200% center} 100% {background-position:200% center}}
    @keyframes dt-orbit {from {transform:rotate(0deg) translateX(18px) rotate(0deg)} to {transform:rotate(360deg) translateX(18px) rotate(-360deg)}}
    @keyframes dt-pulse {0%,100% {opacity:.28; transform:scale(.88)} 50% {opacity:1; transform:scale(1.22)}}
    @keyframes dt-particle-drift {
      0% { background-position: 0 0, 35px 70px, 90px 20px; transform: translate3d(0,0,0); }
      50% { background-position: 70px -55px, -25px 25px, 40px 95px; transform: translate3d(0,-8px,0); }
      100% { background-position: 140px -110px, -85px -20px, -10px 170px; transform: translate3d(0,0,0); }
    }
    @keyframes dt-chart-rise {from {opacity:0; transform:translateY(22px) scale(.985)} to {opacity:1; transform:translateY(0) scale(1)}}
    :root {
      --dt-ink: #f8faff; --dt-muted: #c0cce0; --dt-pink: #ff6ba8;
      --dt-purple: #a78bfa; --dt-blue: #60a5fa; --dt-cyan: #5eead4;
      --dt-orange: #ffbd69; --dt-green: #6ee7a8;
    }
    .stApp {
      background:
        radial-gradient(ellipse at 8% 2%, rgba(99,102,241,.28), transparent 32%),
        radial-gradient(ellipse at 92% 8%, rgba(236,72,153,.19), transparent 29%),
        radial-gradient(ellipse at 70% 88%, rgba(20,184,166,.13), transparent 32%),
        linear-gradient(135deg, #0b1020 0%, #11152b 48%, #101827 100%);
      color: var(--dt-ink);
      background-size: 180% 180%; animation: dt-border-flow 9s ease-in-out infinite;
    }
    /* Soft moving ambient light, kept behind all app controls. */
    [data-testid="stAppViewContainer"] {position:relative; isolation:isolate;}
    [data-testid="stAppViewContainer"]:before {
      content:""; position:fixed; z-index:-1; pointer-events:none; width:34rem; height:34rem;
      top:8%; left:-13rem; border-radius:50%; filter:blur(72px);
      background:radial-gradient(circle,rgba(124,58,237,.13),rgba(59,130,246,.06) 48%,transparent 72%);
      animation:dt-float 6s ease-in-out infinite;
    }
    [data-testid="stAppViewContainer"]:after {
      content:""; position:fixed; z-index:-1; pointer-events:none; inset:0;
      opacity:.34;
      background-image:
        radial-gradient(circle, rgba(167,139,250,.72) 0 1px, transparent 1.8px),
        radial-gradient(circle, rgba(96,165,250,.62) 0 1px, transparent 1.8px),
        radial-gradient(circle, rgba(94,234,212,.52) 0 1px, transparent 1.8px);
      background-size: 180px 180px, 230px 230px, 290px 290px;
      animation:dt-particle-drift 32s linear infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      [data-testid="stAppViewContainer"]:after { animation:none; }
    }
    [data-testid="stHeader"] {background: rgba(11,16,32,.72); backdrop-filter: blur(14px);}
    [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #171632 0%, #121a30 48%, #0d1c2c 100%);
      border-right: 1px solid rgba(167,139,250,.3);
    }
    [data-testid="stSidebar"] * {color: var(--dt-ink);}
    .block-container {max-width: 1480px; padding-top: 1.6rem; padding-bottom: 3rem; animation: dt-fade-up .65s ease both;}
    h1,h2,h3 {letter-spacing: -.035em; color: #fff;}
    h2 {text-shadow: 0 2px 24px rgba(96,165,250,.14);}
    p, label, [data-testid="stMarkdownContainer"] {color: var(--dt-ink);}
    [data-testid="stMetric"] {
      background: linear-gradient(135deg, rgba(99,102,241,.23), rgba(30,41,72,.84) 55%, rgba(14,165,233,.13));
      border: 1px solid rgba(129,140,248,.42); padding: 18px 20px; border-radius: 18px;
      box-shadow: 0 12px 30px rgba(0,0,0,.22), inset 0 1px rgba(255,255,255,.06);
      transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
      animation: dt-chart-rise .85s cubic-bezier(.2,.75,.25,1) both, dt-soft-glow 3.2s ease-in-out 1s infinite;
    }
    [data-testid="stMetric"]:nth-of-type(2) {animation-delay:.08s,.8s}
    [data-testid="stMetric"]:nth-of-type(3) {animation-delay:.16s,1.2s}
    [data-testid="stMetric"]:nth-of-type(4) {animation-delay:.24s,1.6s}
    [data-testid="stMetric"]:hover {transform: translateY(-4px) scale(1.01); border-color: rgba(94,234,212,.85); box-shadow: 0 16px 34px rgba(0,0,0,.28), 0 0 20px rgba(94,234,212,.12);}
    [data-testid="stMetricLabel"] {color: #c6d2ea !important;}
    [data-testid="stMetricValue"] {color: #fff !important; font-weight: 800;}
    [data-testid="stMetricDelta"] {font-weight: 700;}
    .hero {
      position: relative; overflow: hidden;
      background: linear-gradient(112deg, rgba(124,58,237,.38), rgba(37,99,235,.24) 48%, rgba(13,148,136,.25));
      border: 1px solid rgba(167,139,250,.48); border-radius: 24px; padding: 28px 30px; margin-bottom: 22px;
      background-size: 180% 180%; animation: dt-gradient-drift 5s ease-in-out infinite, dt-fade-up .9s ease both;
      box-shadow: 0 18px 50px rgba(0,0,0,.2), inset 0 1px rgba(255,255,255,.08);
    }
    @keyframes dt-sparkle-drift {
      0%,100% { transform:translate3d(0,0,0) rotate(0deg); opacity:.35; }
      50% { transform:translate3d(-18px,-24px,0) rotate(18deg); opacity:.95; }
    }
    @keyframes dt-hero-border-pulse {
      0%,100% { box-shadow:0 18px 50px rgba(0,0,0,.2), 0 0 0 rgba(96,165,250,0), inset 0 1px rgba(255,255,255,.08); }
      50% { box-shadow:0 18px 50px rgba(0,0,0,.2), 0 0 32px rgba(96,165,250,.3), 0 0 54px rgba(236,72,153,.14), inset 0 1px rgba(255,255,255,.12); }
    }
    .hero { animation:dt-gradient-drift 5s ease-in-out infinite, dt-fade-up .9s ease both, dt-hero-border-pulse 3.4s ease-in-out 1s infinite; }
    .hero:after { animation:dt-pulse 3.2s ease-in-out infinite; }
    [data-testid="stMetric"] { position:relative; overflow:hidden; }
    [data-testid="stMetric"]:after {
      content:""; position:absolute; top:-60%; left:-80%; width:55%; height:220%; pointer-events:none;
      background:linear-gradient(100deg,transparent,rgba(255,255,255,.16),transparent);
      transform:skewX(-18deg); animation:dt-shimmer 4.2s linear infinite;
    }
    [data-testid="stMetric"]:nth-of-type(2):after {animation-delay:.6s;}
    [data-testid="stMetric"]:nth-of-type(3):after {animation-delay:1.2s;}
    [data-testid="stMetric"]:nth-of-type(4):after {animation-delay:1.8s;}
    .hero:after {content: ""; position: absolute; width: 220px; height: 220px; right: -70px; top: -105px;
      border-radius: 50%; background: radial-gradient(circle, rgba(255,107,168,.35), transparent 70%); pointer-events: none;
      animation:dt-pulse 6s ease-in-out infinite;}
    .hero:before {content:""; position:absolute; width:170px; height:170px; right:18%; bottom:-125px; border-radius:50%;
      border:1px solid rgba(94,234,212,.2); box-shadow:0 0 42px rgba(96,165,250,.1); pointer-events:none;
      animation:dt-orbit 18s linear infinite;}
    .eyebrow {color: #77f3df; font-size: .76rem; font-weight: 900; text-transform: uppercase; letter-spacing: .16em;}
    .hero-title {font-size: clamp(1.7rem, 3vw, 2.45rem); line-height: 1.12; font-weight: 850; margin: .45rem 0 .6rem; color: #fff;
      background:linear-gradient(90deg,#fff 0%,#c4b5fd 24%,#7dd3fc 48%,#99f6e4 68%,#fff 100%);
      background-size:220% auto; -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
      animation:dt-shimmer 3.2s linear infinite;}
    .hero-copy,.section-note {color: #d2def2; font-size: .96rem;}
    div[data-testid="stTabs"] {border-radius: 14px; animation:dt-fade-up .65s ease both;}
    div[data-testid="stTabs"] button {border-radius: 11px; padding: 10px 15px; color: #d6def0; transition:background .25s ease, transform .25s ease, color .25s ease;}
    div[data-testid="stTabs"] button:hover {transform:translateY(-2px); background:rgba(96,165,250,.13);}
    div[data-testid="stTabs"] button[aria-selected="true"] {background: linear-gradient(90deg, rgba(124,58,237,.34), rgba(37,99,235,.27)); color: #8cf5e4;}
    div[data-testid="stTabs"] button[aria-selected="true"] p {color: #8cf5e4 !important; font-weight: 800;}
    [data-testid="stDataFrame"], [data-testid="stTable"] {border: 1px solid rgba(129,140,248,.3); border-radius: 14px; overflow: hidden;
      animation:dt-chart-rise .8s cubic-bezier(.2,.75,.25,1) both; transition:border-color .25s ease, box-shadow .25s ease;}
    [data-testid="stDataFrame"]:hover, [data-testid="stTable"]:hover {border-color:rgba(94,234,212,.55); box-shadow:0 10px 32px rgba(96,165,250,.08);}
    [data-testid="stFileUploader"] {background: linear-gradient(135deg, rgba(99,102,241,.13), rgba(20,184,166,.08)); background-size:180% 180%;
      border: 1px dashed rgba(129,140,248,.6); border-radius: 16px; padding: 8px; animation:dt-border-flow 4.5s ease infinite; transition:transform .25s ease, border-color .25s ease;}
    [data-testid="stFileUploader"]:hover {transform:translateY(-2px); border-color:rgba(94,234,212,.85);}
    [data-testid="stExpander"] {transition:border-color .25s ease, box-shadow .25s ease;}
    [data-testid="stExpander"]:hover {border-color:rgba(167,139,250,.6); box-shadow:0 8px 26px rgba(124,58,237,.08);}
    [data-testid="stExpander"] {background: rgba(26,34,61,.62); border: 1px solid rgba(129,140,248,.28); border-radius: 14px;}
    .stButton button, [data-testid="stDownloadButton"] button {
      border: 1px solid rgba(167,139,250,.48); border-radius: 11px; font-weight: 750;
      transition: transform .2s ease, filter .2s ease, box-shadow .2s ease; color: #fff;
      background: linear-gradient(100deg, #7c3aed, #2563eb 55%, #0891b2); background-size:180% 180%; animation:dt-border-flow 4s ease infinite;
    }
    .stButton button:hover, [data-testid="stDownloadButton"] button:hover {transform: translateY(-2px) scale(1.01); filter: brightness(1.14); border-color: #5eead4; color: #fff; box-shadow: 0 8px 24px rgba(96,165,250,.18);}
    .stButton button[kind="primary"], button[kind="primary"] {
      background: linear-gradient(100deg, #ec4899, #8b5cf6 52%, #3b82f6); color: #fff; border: 0;
      box-shadow: 0 8px 22px rgba(139,92,246,.24); font-weight: 850;
    }
    [data-testid="stAlert"] {border-radius: 13px; border: 1px solid rgba(255,255,255,.13);}
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stDateInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"], [data-testid="stMultiSelect"] div[data-baseweb="select"] {
      border-radius: 10px;
    }
    hr {border-color: rgba(167,139,250,.25);}
    a {color: #7dd3fc !important;}
    ::selection {background: rgba(236,72,153,.45); color: #fff;}
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important;}
    }
    @media (max-width: 700px) {
      .block-container {padding-top: 1rem;}
      .hero {padding: 22px 20px; border-radius: 18px;}
      [data-testid="stMetric"] {padding: 14px;}
    }
/* Global binary animation: CSS background is attached to the app root, not a single page card. */
    .stApp { position: relative; isolation: isolate; }
    .stApp::before {
      content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
      opacity: .035; background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMjAwIiBoZWlnaHQ9IjE1MCIgdmlld0JveD0iMCAwIDEyMDAgMTUwIj48ZyBmb250LWZhbWlseT0ibW9ub3NwYWNlIiBmb250LXNpemU9IjExIiBmb250LXdlaWdodD0iNjAwIiBsZXR0ZXItc3BhY2luZz0iMi40IiBmaWxsPSIjOWFhOWQ4IiBvcGFjaXR5PSIwLjcyIj48dGV4dCB4PSIwIiB5PSIyMiI+MDEwMDEwMTAgMTAxMTAxMDAgMDExMDEwMDEgMTEwMDEwMTAgMDAxMTAxMDEgMTAxMDAxMTAgMDEwMTExMDAgMTAxMDEwMDEgMDExMDAxMTAgMTEwMDEwMTAgMDAxMTAxMDEgMTAxMDAxMTAgMDEwMTExMDAgMTAxMDEwMDEgMDExMDAxMTA8L3RleHQ+PHRleHQgeD0iLTQwIiB5PSI1NyIgZmlsbD0iI2I3YTZmNSI+MTAxMTAxMDAgMDEwMDEwMTAgMTEwMDEwMTAgMDExMDEwMDEgMTAxMDAxMDEgMDEwMTEwMTAgMTEwMTAwMTAgMDExMDEwMTAgMDAxMTAxMDEgMTAxMDAxMTAgMDEwMTExMDAgMTAxMTAxMDAgMDEwMDEwMTAgMTEwMDEwMTAgMDExMDEwMDE8L3RleHQ+PHRleHQgeD0iMTAiIHk9IjkyIiBmaWxsPSIjNzdkOWQwIj4wMTEwMTAwMSAxMTAxMDAxMCAwMTAxMTAxMCAxMDExMDEwMCAwMTAwMTAxMCAxMTAwMTAxMCAxMDEwMDEwMSAwMTEwMTAxMCAxMTAwMTAxMCAwMDExMDEwMSAwMTEwMTAwMSAxMTAxMDAxMCAwMTAxMTAxMCAxMDExMDEwMDwvdGV4dD48dGV4dCB4PSItMjAiIHk9IjEyNyIgZmlsbD0iI2Q2OGViNyI+MTEwMDEwMTAgMDExMDEwMTAgMTAxMTAxMDAgMDEwMDEwMTAgMDExMDEwMDEgMTAxMDAxMDEgMTEwMTAwMTAgMDEwMTEwMTAgMTAxMTAxMDAgMDExMDEwMDEgMTEwMDEwMTAgMDExMDEwMTAgMTAxMTAxMDA8L3RleHQ+PC9nPjwvc3ZnPg==");
      background-repeat: repeat; background-size: 1200px 150px;
      animation: dt-global-binary-drift 70s linear infinite;
      will-change: background-position;
    }
    [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"],
    [data-testid="stMainBlockContainer"], .main { position: relative; z-index: 1; }
    [data-testid="stAppViewContainer"] { background: transparent; }
    [data-testid="stStatusWidget"], [data-testid="stToast"], [data-testid="stNotification"],
    [data-testid="stAlert"], .dt-game-toast { position: relative; z-index: 10000; }
    @keyframes dt-global-binary-drift {
      0% { background-position: 0 0; }
      50% { background-position: 90px 75px; }
      100% { background-position: 180px 150px; }
    }
    @media (prefers-reduced-motion: reduce) { .stApp::before { animation: none !important; } }

    .arcade-banner { margin: 1rem 0; padding: 1.4rem 1.6rem; border-radius: 22px; border: 1px solid rgba(232,121,249,.65); background: linear-gradient(120deg, rgba(91,33,182,.82), rgba(14,165,233,.68), rgba(236,72,153,.72)); background-size: 220% 220%; animation: arcade-gradient 5s ease infinite, arcade-pop .55s ease both; box-shadow: 0 0 28px rgba(168,85,247,.28); }
        .arcade-banner h2 { margin: .35rem 0; color: white; }
        .arcade-banner p { margin-bottom: 0; color: #f5f3ff; }
        .arcade-kicker { letter-spacing: .18em; font-size: .72rem; font-weight: 900; color: #fef08a; }
        @keyframes arcade-gradient { 0%,100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        @keyframes arcade-pop { from { opacity: 0; transform: translateY(16px) scale(.985); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @media (prefers-reduced-motion: reduce) { .arcade-banner { animation: none; } }
</style>""", unsafe_allow_html=True)


def load_campaign_report(upload, mappings):
    """Load and classify a Meta export using the same rules as the main report."""
    raw = pd.read_excel(upload)
    if raw.empty or len(raw.columns) < 3:
        raise ValueError("The Excel report is empty or does not contain the expected columns.")

    original_cols = list(raw.columns)
    normalized_cols = [normalize(c) for c in original_cols]

    def find_col(predicate, fallback):
        for i, c in enumerate(normalized_cols):
            if predicate(c):
                return original_cols[i]
        if fallback >= len(original_cols):
            raise ValueError("Could not identify Campaign, Results and Amount Spent columns.")
        return original_cols[fallback]

    campaign_col = find_col(lambda c: "campaign" in c, 0)
    result_col = find_col(lambda c: "result" in c and "initial" not in c, 1)
    spent_col = find_col(lambda c: "spent" in c or "amount" in c, 2)
    df = raw[[campaign_col, result_col, spent_col]].copy()
    df.columns = ["Campaign", "Results", "Spent"]
    df["Campaign"] = df["Campaign"].fillna("").astype(str)
    df["Results"] = pd.to_numeric(df["Results"], errors="coerce").fillna(0).astype(int)
    df["Spent"] = pd.to_numeric(df["Spent"], errors="coerce").fillna(0.0)
    # Match the main report's inclusion rule: exclude zero and awareness/reach-scale results.
    df = df[(df["Results"] > 0) & (df["Results"] <= 10000)].reset_index(drop=True)

    assignments = []
    for _, row in df.iterrows():
        staff, course, branch, status = infer_campaign(row["Campaign"], mappings)
        assignments.append({
            "Campaign": row["Campaign"],
            "Results": int(row["Results"]),
            "Spent": float(row["Spent"]),
            "Staff": staff,
            "Course": course,
            "Branch": branch,
            "Status": status,
        })
    return pd.DataFrame(assignments)


def summarize_campaign_performance(frame, exchange_rate):
    """Summaries include only campaigns with identifiable staff and branch."""
    if frame.empty:
        empty = pd.DataFrame(columns=["Campaign", "Results", "Spent", "Staff", "Course", "Branch", "Cost_KWD"])
        return empty, 0, 0.0, None

    valid = frame[
        frame["Staff"].astype(str).str.strip().ne("")
        & frame["Branch"].astype(str).str.strip().ne("")
    ].copy()
    valid["Course"] = valid["Course"].astype(str).str.strip().replace("", "Unclassified course")
    valid["Cost_KWD"] = valid["Spent"].astype(float) * exchange_rate
    if valid.empty:
        return valid, 0, 0.0, None
    top = valid.sort_values(["Results", "Spent"], ascending=[False, True]).iloc[0]
    return valid, int(valid["Results"].sum()), float(valid["Spent"].sum() * exchange_rate), top



def get_supabase_client():
    """Create or restore the Supabase client for this Streamlit session."""
    if "supabase_client" in st.session_state:
        client = st.session_state["supabase_client"]
        access_token = st.session_state.get("supabase_access_token")
        refresh_token = st.session_state.get("supabase_refresh_token")
        if access_token and refresh_token:
            try:
                client.auth.set_session(access_token, refresh_token)
            except Exception:
                # Keep the existing client; the login screen can request a fresh sign-in.
                pass
        return client

    # Render uses environment variables; Streamlit Cloud can still use secrets.toml.
    supabase_url = str(os.environ.get("SUPABASE_URL", "")).strip()
    publishable_key = str(os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")).strip()
    if not supabase_url or not publishable_key:
        try:
            config = st.secrets["supabase"]
            supabase_url = supabase_url or str(config["url"]).strip()
            publishable_key = publishable_key or str(config["publishable_key"]).strip()
        except Exception:
            pass

    if not supabase_url or not publishable_key:
        return None

    try:
        client = create_client(supabase_url, publishable_key)
        st.session_state["supabase_client"] = client
        access_token = st.session_state.get("supabase_access_token")
        refresh_token = st.session_state.get("supabase_refresh_token")
        if access_token and refresh_token:
            try:
                client.auth.set_session(access_token, refresh_token)
            except Exception:
                pass
        return client
    except Exception as exc:
        st.session_state["supabase_setup_error"] = str(exc)
        return None


def _show_login_header():
    st.markdown(
        """
        <style>
        @keyframes dt-logo-rise-away {
          0% { opacity: 1; transform: translateY(0) scale(1); }
          68% { opacity: 1; transform: translateY(-42px) scale(.98); }
          100% { opacity: 0; transform: translateY(-115px) scale(.94); }
        }
        @keyframes dt-login-panel-rise {
          0% { opacity: 0; transform: translateY(54px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes dt-login-shift {0%,100% {background-position:0% 50%;} 50% {background-position:100% 50%;}}
        @keyframes dt-login-glow {0%,100% {box-shadow:0 22px 60px rgba(0,0,0,.3),0 0 10px rgba(124,58,237,.08),inset 0 1px rgba(255,255,255,.08)} 50% {box-shadow:0 22px 60px rgba(0,0,0,.3),0 0 34px rgba(96,165,250,.2),inset 0 1px rgba(255,255,255,.08)}}
        @keyframes dt-login-orbit {from {transform:rotate(0deg) translateX(15px) rotate(0deg)} to {transform:rotate(360deg) translateX(15px) rotate(-360deg)}}
        @keyframes dt-ambient-drift {0%,100% {background-position:0% 0%,100% 0%,0% 50%;} 50% {background-position:18% 22%,82% 18%,100% 50%;}}
        @keyframes dt-card-shimmer {0% {transform:translateX(-130%) rotate(12deg); opacity:0;} 18% {opacity:.45;} 48% {opacity:0;} 100% {transform:translateX(240%) rotate(12deg); opacity:0;}}
        @keyframes dt-orb-float {0%,100% {transform:translate3d(0,0,0) scale(1);} 50% {transform:translate3d(0,-16px,0) scale(1.06);}}
        @keyframes dt-button-breathe {0%,100% {box-shadow:0 7px 20px rgba(124,58,237,.2);} 50% {box-shadow:0 9px 28px rgba(59,130,246,.34),0 0 16px rgba(94,234,212,.13);}}
        @keyframes dt-tab-enter {from {opacity:0; transform:translateY(12px);} to {opacity:1; transform:translateY(0);}}
        [data-testid="stAppViewContainer"] {
          background: radial-gradient(circle at 12% 5%, rgba(124,58,237,.36), transparent 32%),
            radial-gradient(circle at 90% 12%, rgba(236,72,153,.22), transparent 28%),
            linear-gradient(135deg, #0b1020, #11152b 55%, #101827);
          background-size: 140% 140%, 140% 140%, 220% 220%;
          animation: dt-ambient-drift 24s ease-in-out infinite;
        }
        [data-testid="stAppViewContainer"]::after {
          content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
          background: radial-gradient(circle at 17% 72%, rgba(94,234,212,.075), transparent 18%),
                      radial-gradient(circle at 82% 66%, rgba(168,85,247,.09), transparent 21%);
          animation: dt-orb-float 12s ease-in-out infinite;
        }
        [data-testid="stHeader"] {background: transparent;}
        /* Limit the login page width without changing the dashboard after login. */
        .block-container:has(.login-panel) {
          max-width: 760px !important;
          padding-top: 1rem !important;
          padding-bottom: 1.5rem !important;
        }
        .dt-login-logo {
          display:flex; flex-direction:column; align-items:center; justify-content:center;
          gap:.25rem; margin: 48px auto 1rem; min-height:112px; text-align:center;
          animation: dt-logo-rise-away 2.8s cubic-bezier(.4,0,.2,1) .15s both;
        }
        .dt-login-logo-image {
          display:block; width:116px; height:100px; object-fit:contain;
          filter: drop-shadow(0 0 18px rgba(96,165,250,.18));
        }
        .login-panel {
          max-width: 620px; width:100%; box-sizing:border-box;
          margin: -12px auto .8rem auto; padding: 1.6rem 1.8rem;
          border: 1px solid rgba(167,139,250,.55); border-radius: 22px;
          background: linear-gradient(125deg, rgba(124,58,237,.32), rgba(37,99,235,.2) 55%, rgba(13,148,136,.2));
          background-size: 180% 180%; position:relative; overflow:hidden;
          opacity:0; animation: dt-login-panel-rise 1.05s cubic-bezier(.2,.75,.25,1) 1.05s forwards,
          dt-login-shift 14s ease-in-out 2.4s infinite, dt-login-glow 7s ease-in-out 2.4s infinite;
          box-shadow: 0 22px 60px rgba(0,0,0,.3), inset 0 1px rgba(255,255,255,.08);
        }
        .login-panel:after {content:""; position:absolute; width:145px; height:145px; right:9%; bottom:-112px; border-radius:50%;
          border:1px solid rgba(94,234,212,.3); box-shadow:0 0 28px rgba(96,165,250,.13); pointer-events:none; animation:dt-login-orbit 16s linear infinite;}
        .login-panel:before {content:""; position:absolute; top:-45%; left:0; width:34%; height:190%;
          background:linear-gradient(90deg,transparent,rgba(255,255,255,.085),rgba(94,234,212,.09),transparent);
          transform:translateX(-130%) rotate(12deg); pointer-events:none; animation:dt-card-shimmer 9s ease-in-out 2s infinite;}
        .login-panel > * {position:relative; z-index:1;}
        /* Gentle hover feedback keeps the page lively without interfering with authentication. */
        [data-testid="stFormSubmitButton"] button, [data-testid="stForm"] button[kind="primary"] {
          border:1px solid rgba(167,139,250,.28) !important; border-radius:11px !important;
          background:linear-gradient(105deg,#7c3aed,#3b82f6 58%,#0d9488) !important;
          background-size:180% 180% !important; color:#fff !important; font-weight:750 !important;
          transition:transform .22s ease, filter .22s ease, box-shadow .22s ease !important;
          animation:dt-button-breathe 5s ease-in-out 2s infinite;
        }
        [data-testid="stFormSubmitButton"] button:hover, [data-testid="stForm"] button[kind="primary"]:hover {
          transform:translateY(-2px); filter:brightness(1.12); box-shadow:0 12px 28px rgba(124,58,237,.28) !important;
        }
        [data-testid="stFormSubmitButton"] button:active {transform:translateY(0) scale(.99);}
        [data-testid="stTabs"] [data-baseweb="tab"] {transition:color .2s ease, background .2s ease;}
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {color:#5eead4;}
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {transition:border-color .2s ease, box-shadow .2s ease, background .2s ease;}
        [data-testid="stTextInput"] input:focus {background:rgba(30,41,59,.92);}
        /* Keep tabs and forms centered and compact, and bring them into view after the logo. */
        div[data-testid="stTabs"] {
          max-width:620px; width:100%; margin:0 auto !important;
          opacity:0; animation:dt-login-panel-rise 1.0s cubic-bezier(.2,.75,.25,1) 1.25s forwards;
        }
        [data-testid="stForm"] {
          max-width:620px; margin-left:auto; margin-right:auto;
          opacity:0; animation:dt-login-panel-rise 1.0s cubic-bezier(.2,.75,.25,1) 1.4s forwards;
        }
        [data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
          box-shadow:0 0 0 1px rgba(94,234,212,.72),0 0 20px rgba(96,165,250,.2);
          border-color:rgba(94,234,212,.8) !important;
        }
        @keyframes dt-field-arrive {from {transform:translateY(5px);opacity:.72;} to {transform:translateY(0);opacity:1;}}
        @keyframes dt-login-error-shake {0%,100% {transform:translateX(0)} 25% {transform:translateX(-4px)} 50% {transform:translateX(4px)} 75% {transform:translateX(-2px)}}
        @keyframes dt-auth-pulse {0%,100% {filter:brightness(1);box-shadow:0 7px 20px rgba(124,58,237,.22)} 50% {filter:brightness(1.12);box-shadow:0 0 30px rgba(94,234,212,.24),0 9px 28px rgba(59,130,246,.34)}}
        [data-testid="stTextInput"] input:focus {animation:dt-field-arrive .22s ease-out;}
        [data-testid="stTextInput"]:focus-within label {color:#5eead4 !important;transition:color .2s ease;}
        [data-testid="stFormSubmitButton"] button:focus-visible {outline:2px solid #5eead4 !important;outline-offset:3px;}
        [data-testid="stFormSubmitButton"] button:disabled {opacity:.8;cursor:wait;}
        [data-testid="stAlert"] {animation:dt-login-panel-rise .28s ease-out both;}
        .login-kicker {letter-spacing: .18em; text-transform: uppercase; color: #77f3df; font-size: .75rem; font-weight: 900;}
        .login-panel h1 {color: #fff; text-shadow: 0 4px 25px rgba(96,165,250,.18); font-size:clamp(1.7rem,3vw,2.25rem); line-height:1.12;}
        .login-panel p {color: #d6def0;}
        @media (max-width:700px) {
          .block-container:has(.login-panel) {padding-left:1rem !important;padding-right:1rem !important;}
          .login-panel {padding:1.3rem 1.2rem; margin-top:-8px;}
        }
        @media (prefers-reduced-motion: reduce) {
          .dt-login-logo,.login-panel,div[data-testid="stTabs"],[data-testid="stForm"],[data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"]::after,
          [data-testid="stFormSubmitButton"] button,.login-panel:before,.login-panel:after,
          [data-testid="stTextInput"] input:focus,[data-testid="stAlert"] {animation:none !important; opacity:1 !important; transform:none !important;}
        }
        /* Safety fallback: never leave login content invisible if animation timing is interrupted. */
        @media (max-width:700px) {
          .dt-login-logo {min-height:90px; margin-bottom:.35rem;}
          .dt-login-logo-image {width:96px; height:82px;}
          .login-panel {max-width:100%;}
          div[data-testid="stTabs"],[data-testid="stForm"] {max-width:100%;}
        }
        /* Stronger, browser-side interactions: these work even inside st.form. */
        [data-testid="stTextInput"] { transition: transform .22s ease, filter .22s ease; }
        [data-testid="stTextInput"]:focus-within { transform: translateY(-2px); filter: drop-shadow(0 0 10px rgba(94,234,212,.13)); }
        [data-testid="stTextInput"] input {
          border: 1px solid rgba(148,163,184,.38) !important;
          border-radius: 12px !important;
          background: rgba(10,16,32,.68) !important;
          transition: border-color .25s ease, box-shadow .25s ease, background .25s ease, transform .25s ease !important;
        }
        [data-testid="stTextInput"] input:hover { border-color: rgba(167,139,250,.8) !important; }
        [data-testid="stTextInput"] input:focus {
          border-color: #5eead4 !important;
          background: rgba(18,29,48,.96) !important;
          box-shadow: 0 0 0 1px rgba(94,234,212,.45), 0 0 0 5px rgba(59,130,246,.10), 0 0 24px rgba(94,234,212,.18) !important;
          transform: translateY(-1px);
        }
        [data-testid="stForm"] {
          border: 1px solid rgba(167,139,250,.28) !important;
          border-radius: 18px !important;
          padding: 1.25rem !important;
          background: rgba(12,18,35,.56) !important;
          backdrop-filter: blur(14px);
          box-shadow: 0 18px 48px rgba(0,0,0,.18);
        }
        [data-testid="stFormSubmitButton"] button {
          min-height: 48px !important;
          background: linear-gradient(110deg,#7c3aed,#3b82f6,#0d9488,#7c3aed) !important;
          background-size: 260% 260% !important;
          animation: dt-login-shift 5s ease-in-out infinite, dt-button-breathe 3.5s ease-in-out infinite !important;
          box-shadow: 0 8px 24px rgba(124,58,237,.24) !important;
        }
        [data-testid="stFormSubmitButton"] button:hover {
          transform: translateY(-2px) scale(1.01) !important;
          filter: brightness(1.13) saturate(1.12) !important;
          box-shadow: 0 12px 32px rgba(59,130,246,.32), 0 0 18px rgba(94,234,212,.18) !important;
        }
        [data-testid="stFormSubmitButton"] button:active { transform: scale(.985) !important; }
        [data-testid="stTabs"] button[role="tab"] { transition: color .2s ease, background .2s ease, box-shadow .2s ease; }
        [data-testid="stTabs"] button[role="tab"]:hover { color:#5eead4 !important; }
        @media (prefers-reduced-motion: reduce) {
          [data-testid="stTextInput"], [data-testid="stTextInput"] input,
          [data-testid="stFormSubmitButton"] button { animation:none !important; transition:none !important; }
        }
        </style>
        <div class="dt-login-logo">
          <img class="dt-login-logo-image" alt="Dreamztree logo" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABT4AAAW3CAYAAABpEW6xAAAgAElEQVR4nOzdyXLbRhiFUSnl939lZuHIkWgOGBrd/3BOlXfJIgSiUF9uAx8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0MntdvsXjqmbVHamOtwAAAAASUVORK5CYII=" />
        </div>
        <div class="login-panel">
          <div class="login-kicker">Dreamztree · Marketing Intelligence</div>
          <h1>Meta Leads Command Center</h1>
          <p>Sign in or create an account to access campaign performance and lead reports.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def require_login():
    """Use Supabase Auth for colleague registration and sign-in.

    Optional legacy admin credentials in [auth.users] remain supported so the
    existing administrator can still sign in during the transition.
    """
    if st.session_state.get("authenticated"):
        return

    client = get_supabase_client()
    if client is None:
        st.title("Dreamztree Meta Report")
        st.error("Supabase authentication is not configured yet.")
        st.markdown(
            "Set the `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` environment variables "
            "in your hosting provider's settings, or configure `[supabase]` in Streamlit Secrets."
        )
        if st.session_state.get("supabase_setup_error"):
            st.caption("Connection detail: " + st.session_state["supabase_setup_error"])
        st.stop()

    _show_login_header()
    sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("supabase_signin_form", clear_on_submit=False):
            email_or_admin = st.text_input("Email address Or Username")
            password = st.text_input("Password", type="password")
            signin_clicked = st.form_submit_button(
                "Sign in", type="primary", use_container_width=True
            )

        if signin_clicked:
            login_id = email_or_admin.strip()
            if not login_id or not password:
                st.error("Enter your email/username and password.")
            else:
                # Keep the existing private admin login working during migration.
                try:
                    legacy_users = dict(st.secrets["auth"]["users"])
                except Exception:
                    legacy_users = {}
                # Optional single admin login for hosts that use environment variables.
                env_admin_user = os.environ.get("ADMIN_USERNAME", "").strip()
                env_admin_password = os.environ.get("ADMIN_PASSWORD", "")
                if env_admin_user and env_admin_password:
                    legacy_users.setdefault(env_admin_user, env_admin_password)

                legacy_password = legacy_users.get(login_id)
                if legacy_password is not None and hmac.compare_digest(
                    password, str(legacy_password)
                ):
                    st.session_state["authenticated"] = True
                    st.session_state["authenticated_user"] = login_id
                    st.session_state["auth_method"] = "legacy"
                    st.session_state["login_just_succeeded"] = True
                    st.rerun()
                elif "@" in login_id:
                    try:
                        with st.spinner("Authenticating securely…"):
                            response = client.auth.sign_in_with_password(
                                {"email": login_id, "password": password}
                            )
                        if response and response.user:
                            if getattr(response, "session", None):
                                st.session_state["supabase_access_token"] = response.session.access_token
                                st.session_state["supabase_refresh_token"] = response.session.refresh_token
                            st.session_state["authenticated"] = True
                            st.session_state["authenticated_user"] = (
                                response.user.email or login_id
                            )
                            st.session_state["auth_method"] = "supabase"
                            st.session_state["login_just_succeeded"] = True
                            st.rerun()
                        else:
                            st.error("Sign-in failed. Check your email and password.")
                    except Exception:
                        st.error(
                            "Could not sign in. Check your email and password, and "
                            "confirm your email address if verification is enabled."
                        )
                else:
                    st.error("Incorrect username or password.")

    with create_tab:
        st.caption("Create a personal account using your work email address.")
        with st.form("supabase_signup_form", clear_on_submit=True):
            new_email = st.text_input("Work email address", key="signup_email")
            new_username = st.text_input("Your name", key="signup_name")
            new_password = st.text_input(
                "Create password", type="password", key="signup_password"
            )
            confirm_password = st.text_input(
                "Confirm password", type="password", key="signup_confirm_password"
            )
            signup_clicked = st.form_submit_button(
                "Create account", type="primary", use_container_width=True
            )

        if signup_clicked:
            new_email = new_email.strip().lower()
            new_username = new_username.strip()
            if not new_email or "@" not in new_email:
                st.error("Enter a valid email address.")
            elif not new_username:
                st.error("Enter your name.")
            elif len(new_password) < 8:
                st.error("Use a password with at least 8 characters.")
            elif new_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    with st.spinner("Creating your secure account…"):
                        response = client.auth.sign_up(
                            {
                                "email": new_email,
                                "password": new_password,
                                "options": {"data": {"username": new_username}},
                            }
                        )
                    if response and response.session and response.user:
                        st.session_state["supabase_access_token"] = response.session.access_token
                        st.session_state["supabase_refresh_token"] = response.session.refresh_token
                        st.session_state["authenticated"] = True
                        st.session_state["authenticated_user"] = (
                            response.user.email or new_email
                        )
                        st.session_state["auth_method"] = "supabase"
                        st.session_state["login_just_succeeded"] = True
                        # Profile details are optional; Auth remains the source of truth.
                        try:
                            client.table("profiles").upsert(
                                {
                                    "id": response.user.id,
                                    "username": new_username,
                                }
                            ).execute()
                        except Exception:
                            pass
                        st.success("Account created. Signing you in…")
                        st.rerun()
                    else:
                        st.success(
                            "Registration received. Check your email for a verification "
                            "link, then return here and sign in."
                        )
                
                except Exception as e:
                    st.error(f"Account creation failed: {e}")


    st.stop()


def _ludo_default_state():
    return {
        "players": [], "tokens": {}, "turn": 0, "dice": None,
        "rolled": False, "winner": None, "updated_at": datetime.utcnow().isoformat()
    }


def render_ludo_online():
    'Classic-style four-token online Ludo using the existing Supabase room table.'
    st.markdown("### 🎲 Ludo Online · Classic gameplay")
    st.caption("Play online with colleagues, or choose Play Ludo with 3 bots when nobody is available. Four tokens each, roll a 6 to leave base, capture opponents, and reach home.")
    client = get_supabase_client()
    if client is None:
        st.error("Supabase is not configured. Check the URL and publishable key in Streamlit Secrets.")
        return
    try:
        user = client.auth.get_user().user
        if not user:
            raise ValueError("No authenticated user")
    except Exception:
        st.warning("Please sign in with your Supabase email and password to play online.")
        return
    uid = str(user.id)
    email = str(user.email or "")
    meta = getattr(user, "user_metadata", None) or {}
    name = str(meta.get("username") or meta.get("name") or email.split("@")[0] or "Player")[:30]
    token = st.session_state.get("supabase_access_token", "")
    try:
        cfg = st.secrets["supabase"]
        url, key = str(cfg["url"]).rstrip("/"), str(cfg["publishable_key"])
    except Exception:
        st.error("Missing Supabase URL or publishable key in Streamlit Secrets.")
        return
    if not token:
        st.warning("No active Supabase session token. Sign out and sign in with your Supabase email/password.")
        return
    left, right = st.columns(2)
    with left:
        if st.button("🎲 Create classic Ludo room", type="primary", use_container_width=True):
            code = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            state = _ludo_default_state()
            state["players"] = [{"id": uid, "name": name, "color": "red"}]
            state["tokens"] = {uid: [-1, -1, -1, -1]}
            try:
                client.table("ludo_rooms").insert({"room_code": code, "created_by": uid, "state": state}).execute()
                st.session_state["ludo_room_code"] = code
                st.success(f"Room created: {code}. Share this code with colleagues.")
                st.rerun()
            except Exception as exc:
                st.error("Could not create room. Run the Ludo SQL setup first.")
                st.caption(str(exc))
    with left:
        if st.button("🤖 Play Ludo with 3 bots", use_container_width=True, key="ludo_vs_bots"):
            code = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            state = _ludo_default_state()
            state["players"] = [
                {"id": uid, "name": name, "color": "red"},
                {"id": "bot-blue", "name": "Blue Bot", "color": "blue", "is_bot": True},
                {"id": "bot-yellow", "name": "Yellow Bot", "color": "yellow", "is_bot": True},
                {"id": "bot-green", "name": "Green Bot", "color": "green", "is_bot": True},
            ]
            state["tokens"] = {uid: [-1, -1, -1, -1], "bot-blue": [-1, -1, -1, -1], "bot-yellow": [-1, -1, -1, -1], "bot-green": [-1, -1, -1, -1]}
            try:
                client.table("ludo_rooms").insert({"room_code": code, "created_by": uid, "state": state}).execute()
                st.session_state["ludo_room_code"] = code
                st.success(f"Bot game created: {code}. You are Red; play against three bots.")
                st.rerun()
            except Exception as exc:
                st.error("Could not create bot game. Check the Ludo SQL setup.")
                st.caption(str(exc))
    with right:
        code_in = st.text_input("Colleague's room code", max_chars=6, key="ludo_join_code").strip().upper()
        if st.button("Join Ludo room", use_container_width=True):
            try:
                rows = client.table("ludo_rooms").select("room_code,state").eq("room_code", code_in).limit(1).execute().data or []
                if not rows:
                    st.error("Room not found. Check the code.")
                else:
                    state = rows[0].get("state") or _ludo_default_state()
                    players = state.setdefault("players", [])
                    if not any(str(pl.get("id")) == uid for pl in players):
                        if len(players) >= 4:
                            st.error("This room already has four players.")
                            return
                        colors = ["red", "blue", "green", "yellow"]
                        used = {pl.get("color") for pl in players}
                        color = next(c for c in colors if c not in used)
                        players.append({"id": uid, "name": name, "color": color})
                        state.setdefault("tokens", {})[uid] = [-1, -1, -1, -1]
                        state["turn"] = 0
                        state["dice"] = None
                        state["rolled"] = False
                        client.table("ludo_rooms").update({"state": state}).eq("room_code", code_in).execute()
                    st.session_state["ludo_room_code"] = code_in
                    st.rerun()
            except Exception as exc:
                st.error("Could not join room. Check the SQL setup and table policies.")
                st.caption(str(exc))
    room = st.session_state.get("ludo_room_code", "")
    if not room:
        st.info("Create a room or enter a colleague's room code to start.")
        return
    try:
        rows = client.table("ludo_rooms").select("state").eq("room_code", room).limit(1).execute().data or []
        if not rows:
            st.warning("Room not found. Create or join another room.")
            return
        state = rows[0].get("state") or _ludo_default_state()
        players = state.get("players", [])
        st.markdown(f"### Current room: `{room}`")
        st.write("Players: " + (" · ".join(f"{pl.get('name', 'Player')} ({pl.get('color', '')})" for pl in players) if players else "Waiting for players"))
        payload = json.dumps({"url": url, "key": key, "token": token, "room": room, "uid": uid}).replace("</", "<\\/")
        html = r'''<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(ellipse at 50% 0%,#253b68 0%,#10182e 62%);color:#f8fafc}.panel{padding:clamp(12px,2.2vw,22px);border:1px solid #ffffff20;border-radius:22px;background:linear-gradient(145deg,#17233d,#0c1428);box-shadow:0 22px 60px #02061780,inset 0 1px #ffffff12}#status{text-align:center;color:#a7f3d0;font-weight:800;margin:8px 0 14px;font-size:clamp(14px,2vw,17px);letter-spacing:.01em;min-height:24px}.boardwrap{max-width:680px;margin:16px auto 10px;padding:10px;border-radius:22px;background:linear-gradient(145deg,#f8fafc,#cbd5e1 52%,#94a3b8);box-shadow:0 14px 32px #02061770,inset 0 2px 2px #fff}.boardwrap canvas{width:100%;height:auto;display:block;border-radius:14px;touch-action:manipulation;filter:drop-shadow(0 4px 6px #0f172a30)}.row{display:flex;gap:10px;justify-content:center;margin:14px;flex-wrap:wrap}.row button{padding:12px 20px;border:1px solid #ffffff28;border-radius:13px;font-weight:800;background:linear-gradient(135deg,#f472b6,#8b5cf6 55%,#3b82f6);color:white;cursor:pointer;box-shadow:0 7px 18px #6366f155;transition:transform .16s ease,filter .16s ease,box-shadow .16s ease}.row button:hover:not(:disabled){transform:translateY(-2px);filter:brightness(1.08);box-shadow:0 10px 24px #6366f177}.row button:active:not(:disabled){transform:translateY(1px) scale(.99)}.row button:disabled{opacity:.42;filter:grayscale(.35);box-shadow:none}.hint{text-align:center;color:#cbd5e1;font-size:13px;line-height:1.6;max-width:680px;margin:12px auto 2px}.chips{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:8px 0 12px}.chip{padding:7px 11px;border-radius:999px;background:#ffffff0c;border:1px solid #ffffff18;font-size:12px;font-weight:700;box-shadow:inset 0 1px #ffffff0c}
</style></head><body><div class="panel"><div id="status">Connecting…</div><div class="chips" id="players"></div><div class="boardwrap"><canvas id="board" width="600" height="600"></canvas></div><div class="row"><button id="roll">🎲 Roll dice</button><button id="refresh">↻ Refresh</button></div><div class="hint">Classic rules: roll a 6 to enter a token, click one of your glowing tokens to move, capture opponents, and reach home exactly. A 6 or capture earns another turn.</div></div><script>
const C=PAYLOAD,api=C.url+'/rest/v1/',H={'apikey':C.key,'Authorization':'Bearer '+C.token,'Content-Type':'application/json'};const cv=document.getElementById('board'),ctx=cv.getContext('2d'),status=document.getElementById('status'),playerBox=document.getElementById('players');let state=null,busy=false,localDice=null,canMove=[];const W=600,S=40,colors={red:'#e53935',blue:'#2585e8',green:'#22a65a',yellow:'#f3c623'},light={red:'#ffcdd2',blue:'#bbdefb',green:'#c8e6c9',yellow:'#fff3b0'};
// 52-cell classic perimeter path, with separate six-cell home lanes.
const ring=[[6,0],[6,1],[6,2],[6,3],[6,4],[6,5],[5,6],[4,6],[3,6],[2,6],[1,6],[0,6],[0,7],[0,8],[1,8],[2,8],[3,8],[4,8],[5,8],[6,9],[6,10],[6,11],[6,12],[6,13],[6,14],[7,14],[8,14],[8,13],[8,12],[8,11],[8,10],[8,9],[9,8],[10,8],[11,8],[12,8],[13,8],[14,8],[14,7],[14,6],[13,6],[12,6],[11,6],[10,6],[9,6],[8,5],[8,4],[8,3],[8,2],[8,1],[8,0],[7,0]];
const order=['red','blue','yellow','green'],start={red:1,blue:14,yellow:27,green:40};
const home={red:[[7,1],[7,2],[7,3],[7,4],[7,5],[7,6]],blue:[[13,7],[12,7],[11,7],[10,7],[9,7],[8,7]],yellow:[[7,13],[7,12],[7,11],[7,10],[7,9],[7,8]],green:[[1,7],[2,7],[3,7],[4,7],[5,7],[6,7]]};
const base={red:[[1.7,1.7],[3.1,1.7],[1.7,3.1],[3.1,3.1]],blue:[[10.9,1.7],[12.3,1.7],[10.9,3.1],[12.3,3.1]],green:[[1.7,10.9],[3.1,10.9],[1.7,12.3],[3.1,12.3]],yellow:[[10.9,10.9],[12.3,10.9],[10.9,12.3],[12.3,12.3]]};
const safe=[1,9,14,22,27,35,40,48];function xy(c){return [(c[0]+.5)*S,(c[1]+.5)*S]};function cur(){return (state?.players||[])[state?.turn||0]};function tokenPos(pl,i){let pos=(state.tokens?.[pl.id]||[-1,-1,-1,-1])[i];if(pos<0)return base[pl.color][i];if(pos<51){let ix=(start[pl.color]+pos)%52;return ring[ix]}if(pos<57)return home[pl.color][pos-51];return [7,7]}
function rounded(x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1.2;ctx.stroke()}}
function cell(x,y,col){let px=x*S,py=y*S;ctx.fillStyle=col;ctx.fillRect(px,py,S,S);ctx.strokeStyle='#94a3b8';ctx.lineWidth=1.1;ctx.strokeRect(px+.5,py+.5,S-1,S-1);ctx.strokeStyle='#ffffffaa';ctx.beginPath();ctx.moveTo(px+2,py+2);ctx.lineTo(px+S-2,py+2);ctx.stroke()}
function draw(){ctx.clearRect(0,0,W,W);let bg=ctx.createLinearGradient(0,0,W,W);bg.addColorStop(0,'#ffffff');bg.addColorStop(1,'#e2e8f0');ctx.fillStyle=bg;ctx.fillRect(0,0,W,W);ctx.save();ctx.shadowColor='#0f172a28';ctx.shadowBlur=8;ctx.shadowOffsetY=3;[['red',0,0],['blue',9,0],['green',0,9],['yellow',9,9]].forEach(([c,x,y])=>{let baseGrad=ctx.createLinearGradient(x*S,y*S,(x+6)*S,(y+6)*S);baseGrad.addColorStop(0,light[c]);baseGrad.addColorStop(1,colors[c]+'22');rounded(x*S+1,y*S+1,6*S-2,6*S-2,10,baseGrad,'#ffffff');let g=ctx.createLinearGradient((x+1)*S,(y+1)*S,(x+5)*S,(y+5)*S);g.addColorStop(0,colors[c]);g.addColorStop(1,light[c]);rounded((x+1)*S+1,(y+1)*S+1,4*S-2,4*S-2,8,g,'#ffffffaa');rounded((x+1.5)*S,(y+1.5)*S,3*S,3*S,24,'#ffffff','#e2e8f0');});ctx.restore();
ring.forEach((p,i)=>{let c='#fff';if(i===start.red)c=light.red;if(i===start.blue)c=light.blue;if(i===start.green)c=light.green;if(i===start.yellow)c=light.yellow;if(safe.includes(i))c='#fef3c7';cell(p[0],p[1],c)});
Object.entries(home).forEach(([col,arr])=>arr.forEach(p=>cell(p[0],p[1],light[col])));for(let x=6;x<=8;x++)for(let y=6;y<=8;y++){ctx.fillStyle='#f8fafc';ctx.fillRect(x*S,y*S,S,S)}
// Center four-colour finish triangle.
ctx.beginPath();ctx.moveTo(6*S,6*S);ctx.lineTo(9*S,6*S);ctx.lineTo(7.5*S,7.5*S);ctx.closePath();ctx.fillStyle=colors.red;ctx.fill();ctx.beginPath();ctx.moveTo(9*S,6*S);ctx.lineTo(9*S,9*S);ctx.lineTo(7.5*S,7.5*S);ctx.fillStyle=colors.blue;ctx.fill();ctx.beginPath();ctx.moveTo(9*S,9*S);ctx.lineTo(6*S,9*S);ctx.lineTo(7.5*S,7.5*S);ctx.fillStyle=colors.yellow;ctx.fill();ctx.beginPath();ctx.moveTo(6*S,9*S);ctx.lineTo(6*S,6*S);ctx.lineTo(7.5*S,7.5*S);ctx.fillStyle=colors.green;ctx.fill();
const ps=state?.players||[];ps.forEach(pl=>{for(let i=0;i<4;i++){let p=tokenPos(pl,i),[x,y]=xy(p),active=pl.id===C.uid&&canMove.includes(i),r=13;ctx.save();ctx.shadowColor='#0f172a55';ctx.shadowBlur=active?17:7;ctx.shadowOffsetY=active?3:4;let grad=ctx.createRadialGradient(x-r*.38,y-r*.45,2,x,y,r*1.25);let baseColor=colors[pl.color];grad.addColorStop(0,'#ffffff');grad.addColorStop(.18,light[pl.color]);grad.addColorStop(.52,baseColor);grad.addColorStop(1,'#172033');ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=grad;ctx.fill();ctx.restore();ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.lineWidth=active?3.5:1.8;ctx.strokeStyle=active?'#fef08a':'#ffffff';ctx.stroke();ctx.beginPath();ctx.arc(x-r*.32,y-r*.34,3.4,0,Math.PI*2);ctx.fillStyle='#ffffffcc';ctx.fill();ctx.fillStyle='#fff';ctx.font='900 10px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowColor='#00000055';ctx.shadowBlur=2;ctx.fillText(String(i+1),x,y+1);ctx.shadowBlur=0;if(active){let pulse=3+Math.sin(Date.now()/180)*2;ctx.beginPath();ctx.arc(x,y,r+pulse,0,Math.PI*2);ctx.strokeStyle='#fef08a';ctx.lineWidth=2;ctx.stroke()}}});ctx.textBaseline='alphabetic';ctx.textAlign='left';ctx.save();ctx.shadowColor='#ffffff';ctx.shadowBlur=5;ctx.fillStyle='#0f172a';ctx.font='900 17px system-ui';ctx.fillText('DICE',S*6.05,S*7.55);ctx.restore();let dice=localDice||state?.dice||'—';rounded(S*7.05,S*7.08,S*.95,S*.95,8,'#ffffff','#94a3b8');ctx.fillStyle='#111827';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='900 24px system-ui';ctx.fillText(String(dice),S*7.525,S*7.55);ctx.textAlign='left';ctx.textBaseline='alphabetic';}
async function req(path,opt={}){let r=await fetch(api+path,{...opt,headers:{...H,...(opt.headers||{})}});if(!r.ok)throw Error('Supabase '+r.status+' '+(await r.text()).slice(0,150));return r}
async function load(){try{let r=await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room)+'&select=state'),a=await r.json();if(!a.length){status.textContent='Room not found';return}state=a[0].state||{};if(!state.tokens){state.tokens={};(state.players||[]).forEach(p=>state.tokens[p.id]=[-1,-1,-1,-1]);state.dice=null;state.rolled=false}let ps=state.players||[],cp=cur();playerBox.innerHTML=ps.map(p=>'<span class="chip" style="border:1px solid '+colors[p.color]+'">● '+esc(p.name)+' · '+p.color+'</span>').join('');canMove=[];if(cp?.id===C.uid&&state.rolled&&state.dice)canMove=legalMoves(C.uid,state.dice);document.getElementById('roll').disabled=busy||!cp||cp.id!==C.uid||!!state.rolled||!!state.winner;status.textContent=state.winner?'🏆 Winner: '+state.winner.name:('Room '+C.room+' · '+(cp?cp.name+' to play':'Waiting for players')+(cp?.id===C.uid?' — your turn':''));draw();if(cp?.is_bot&&!state.winner&&!busy)setTimeout(runBotTurn,700)}catch(e){status.textContent='Connection error: '+e.message}}
async function runBotTurn(){if(!state||busy||state.winner)return;let cp=cur();if(!cp?.is_bot||cp.id===C.uid)return;busy=true;try{let d=1+Math.floor(Math.random()*6),arr=state.tokens[cp.id]||[-1,-1,-1,-1],moves=[];arr.forEach((p,i)=>{if((p===-1&&d===6)||(p>=0&&p<57&&p+d<=57))moves.push(i)});if(!moves.length){state.turn=(state.turn+1)%state.players.length;state.dice=null;state.rolled=false;await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room),{method:'PATCH',headers:{'Prefer':'return=minimal'},body:JSON.stringify({state})});}else{let choices=moves.map(i=>({i,p:arr[i],next:arr[i]<0?0:arr[i]+d}));choices.sort((a,b)=>{let av=(a.p<0?10:0)+(a.next===57?100:0)+(a.next>0&&a.next<51?3:0);let bv=(b.p<0?10:0)+(b.next===57?100:0)+(b.next>0&&b.next<51?3:0);return bv-av});let pick=choices[0],old=arr[pick.i],next=pick.next;arr[pick.i]=next;state.tokens[cp.id]=arr;let captured=false;if(next<51){let abs=(start[cp.color]+next)%52;if(!safe.includes(abs)){state.players.filter(p=>p.id!==cp.id).forEach(p=>{let pa=state.tokens[p.id]||[-1,-1,-1,-1];pa.forEach((pos,j)=>{if(pos>=0&&pos<51&&(start[p.color]+pos)%52===abs){pa[j]=-1;captured=true}});state.tokens[p.id]=pa})}}if(arr.every(v=>v===57))state.winner=cp;let bonus=d===6||captured||next===57;state.dice=null;state.rolled=false;if(!state.winner&&!bonus)state.turn=(state.turn+1)%state.players.length;await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room),{method:'PATCH',headers:{'Prefer':'return=minimal'},body:JSON.stringify({state})})}}catch(e){status.textContent='Bot move failed: '+e.message}finally{busy=false;await load()}}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function legalMoves(id,d){let a=state.tokens?.[id]||[-1,-1,-1,-1],out=[];a.forEach((p,i)=>{if(p===-1&&d===6)out.push(i);else if(p>=0&&p<57&&p+d<=57)out.push(i)});return out}
async function save(){if(busy)return;busy=true;try{state.updated_at=new Date().toISOString();await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room),{method:'PATCH',headers:{'Prefer':'return=minimal'},body:JSON.stringify({state})})}catch(e){status.textContent='Save failed: '+e.message}finally{busy=false}}
document.getElementById('roll').onclick=async()=>{if(!state||state.winner||busy)return;let cp=cur();if(!cp||cp.id!==C.uid){status.textContent='Wait for your turn';return}if(state.rolled){status.textContent='Select a highlighted token first';return}localDice=1+Math.floor(Math.random()*6);state.dice=localDice;state.rolled=true;canMove=legalMoves(C.uid,localDice);if(!canMove.length){state.rolled=false;state.dice=null;state.turn=(state.turn+1)%state.players.length;status.textContent='No legal move. Turn passes.'}else status.textContent='You rolled '+localDice+'. Click a highlighted token.';draw();await save();await load()};
cv.addEventListener('click',async ev=>{if(!state||busy||state.winner)return;let cp=cur();if(!cp||cp.id!==C.uid||!state.rolled)return;const r=cv.getBoundingClientRect(),x=(ev.clientX-r.left)*600/r.width,y=(ev.clientY-r.top)*600/r.height;let picked=-1,bestD=1e9;for(let i of canMove){let [tx,ty]=xy(tokenPos(cp,i)),d=Math.hypot(x-tx,y-ty);if(d<25&&d<bestD){picked=i;bestD=d}}if(picked<0){status.textContent='Click one of your highlighted tokens.';return}let d=state.dice,arr=state.tokens[C.uid]||[-1,-1,-1,-1],old=arr[picked],next=old<0?0:old+d;if(old<0&&d!==6)return;if(next>57){status.textContent='Need an exact roll to reach home';return}arr[picked]=next;state.tokens[C.uid]=arr;let captured=false;if(next<51){let abs=(start[cp.color]+next)%52;if(!safe.includes(abs)){(state.players||[]).filter(p=>p.id!==C.uid).forEach(p=>{let pa=state.tokens[p.id]||[-1,-1,-1,-1];pa.forEach((pos,j)=>{if(pos>=0&&pos<51&&(start[p.color]+pos)%52===abs){pa[j]=-1;captured=true}});state.tokens[p.id]=pa})}}if(arr.every(v=>v===57)){state.winner=cp;status.textContent='🏆 You won!'}let bonus=d===6||captured||next===57;state.rolled=false;state.dice=null;localDice=null;if(!state.winner&&!bonus)state.turn=(state.turn+1)%state.players.length;canMove=[];draw();await save();await load()});
document.getElementById('refresh').onclick=load;function refresh(){load()}function animateTokens(){if(state)draw();requestAnimationFrame(animateTokens)}load();requestAnimationFrame(animateTokens);setInterval(refresh,1600);
</script></body></html>'''.replace('PAYLOAD', payload)
        components.html(html, height=930, scrolling=False)
        st.caption("Classic-style online Ludo: four tokens per player, dice-based moves, captures, safe squares, home lanes, and turn sharing. Keep the room open on each player's device.")
    except Exception as exc:
        st.error(f"Could not load Ludo room: {exc}")

def render_snake_apple():
    st.markdown("### 🐍 Snake & Apple")
    st.caption("Use arrow keys or WASD to collect apples. Avoid the walls and your own tail.")
    html = r'''<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#10182e;color:white;font-family:system-ui}.wrap{padding:12px;background:linear-gradient(135deg,#172554,#14532d);border-radius:16px}.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-weight:800}.game{display:block;width:100%;max-width:600px;margin:12px auto;border-radius:12px;background:#0b1220;touch-action:none}.buttons{display:flex;justify-content:center;gap:8px;flex-wrap:wrap}.buttons button{padding:10px 16px;border:0;border-radius:10px;background:#86efac;color:#052e16;font-weight:900}.hint{text-align:center;color:#d1fae5;font-size:13px}</style></head><body><div class="wrap"><div class="top"><span>🐍 SNAKE & APPLE</span><span>Score: <b id="score">0</b></span><span>Best: <b id="best">0</b></span></div><canvas id="c" class="game" width="600" height="420"></canvas><div class="buttons"><button id="up">⬆</button><button id="left">⬅</button><button id="down">⬇</button><button id="right">➡</button><button id="restart">Restart</button></div><p class="hint">Arrow keys / WASD or buttons to move. Eat apples to grow. Avoid walls and your tail.</p></div><script>
const c=document.getElementById('c'),x=c.getContext('2d'),N=30,cols=20,rows=14;let snake,dir,next,apple,score,over,best=+(localStorage.getItem('dtSnakeBest')||0);document.getElementById('best').textContent=best;function place(){do{apple={x:Math.floor(Math.random()*cols),y:Math.floor(Math.random()*rows)}}while(snake.some(p=>p.x===apple.x&&p.y===apple.y))}function reset(){snake=[{x:7,y:7},{x:6,y:7},{x:5,y:7}];dir={x:1,y:0};next={x:1,y:0};score=0;over=false;place();document.getElementById('score').textContent=score}function turn(a,b){if(a!==-dir.x||b!==-dir.y)next={x:a,y:b}}window.addEventListener('keydown',e=>{let k=e.key.toLowerCase(),m={'arrowup':[0,-1],w:[0,-1],'arrowdown':[0,1],s:[0,1],'arrowleft':[-1,0],a:[-1,0],'arrowright':[1,0],d:[1,0]}[k];if(m){e.preventDefault();turn(...m)}});[['up',0,-1],['down',0,1],['left',-1,0],['right',1,0]].forEach(([id,a,b])=>document.getElementById(id).onclick=()=>turn(a,b));document.getElementById('restart').onclick=reset;function draw(){x.clearRect(0,0,c.width,c.height);x.fillStyle='#0b1220';x.fillRect(0,0,c.width,c.height);for(let y=0;y<rows;y++)for(let xx=0;xx<cols;xx++){x.fillStyle=(xx+y)%2?'#142b2b':'#183737';x.fillRect(xx*N,y*N,N,N)}x.fillStyle='#ef4444';x.beginPath();x.arc(apple.x*N+N/2,apple.y*N+N/2,N*.36,0,Math.PI*2);x.fill();x.fillStyle='#86efac';x.fillRect(apple.x*N+N*.48,apple.y*N+2,4,8);snake.forEach((p,i)=>{x.fillStyle=i?'#22c55e':'#a3e635';x.beginPath();x.roundRect(p.x*N+2,p.y*N+2,N-4,N-4,6);x.fill()});if(over){x.fillStyle='#000a';x.fillRect(0,0,c.width,c.height);x.fillStyle='white';x.textAlign='center';x.font='bold 34px system-ui';x.fillText('GAME OVER',c.width/2,c.height/2);x.font='18px system-ui';x.fillText('Press Restart to play again',c.width/2,c.height/2+32)}}function step(){if(!over){dir=next;let h={x:snake[0].x+dir.x,y:snake[0].y+dir.y};if(h.x<0||h.x>=cols||h.y<0||h.y>=rows||snake.some(p=>p.x===h.x&&p.y===h.y)){over=true}else{snake.unshift(h);if(h.x===apple.x&&h.y===apple.y){score+=10;document.getElementById('score').textContent=score;if(score>best){best=score;localStorage.setItem('dtSnakeBest',best);document.getElementById('best').textContent=best}place()}else snake.pop()}}draw()}reset();const SNAKE_STEP_MS=180;setInterval(step,SNAKE_STEP_MS);
</script></body></html>'''
    components.html(html, height=610, scrolling=False)


def render_games_page():
    st.markdown("""
    <style>
    .games-hero{padding:24px 28px;border-radius:22px;background:linear-gradient(120deg,#6425d0,#e83e8c 52%,#ff9f43);color:white;margin:8px 0 20px;box-shadow:0 12px 35px #8b5cf633}
    .games-hero h1{margin:0;font-size:2.2rem}.games-hero p{margin:6px 0 0;color:#fffde8}
    </style><div class="games-hero"><h1>🎮 Dreamztree Game Zone</h1><p>Think fast, solve the puzzle, and beat your best score.</p></div>
    """, unsafe_allow_html=True)
    game = st.radio("Choose a game", ["🧠 Brain Test", "🔢 Mini Sudoku", "🧠 Memory Match", "🎯 Number Hunt", "🦖 Dino Runner", "🎲 Ludo Online", "🐍 Snake & Apple"], horizontal=True, label_visibility="collapsed", key="games_page_choice")
    if game == "🎲 Ludo Online":
        render_ludo_online()
        return
    if game == "🐍 Snake & Apple":
        render_snake_apple()
        return
    if game == "🧠 Brain Test":
        st.markdown("### 🧠 Brain Test · Quick Challenge")
        questions = [
            ("What has keys but cannot open locks?", ["A door", "A piano", "A map", "A clock"], 1, "A piano has keys, but no locks."),
            ("What comes next: 2, 4, 8, 16, __?", ["18", "24", "30", "32"], 3, "Each number doubles, so the answer is 32."),
            ("You overtake the person in second place. What place are you in?", ["First", "Second", "Third", "Last"], 1, "You take their place: second."),
            ("Which month has 28 days?", ["February only", "April", "All months", "June"], 2, "Every month has at least 28 days."),
        ]
        if "brain_test_q" not in st.session_state: st.session_state.brain_test_q = 0
        if "brain_test_score" not in st.session_state: st.session_state.brain_test_score = 0
        if "brain_test_answered" not in st.session_state: st.session_state.brain_test_answered = False
        qn=st.session_state.brain_test_q
        if qn < len(questions):
            q,opts,correct,explain=questions[qn]
            st.progress(qn/len(questions), text=f"Question {qn+1} of {len(questions)} · Score {st.session_state.brain_test_score}")
            st.markdown(f"#### {q}")
            ans=st.radio("Choose your answer",opts,key=f"brain_answer_{qn}",label_visibility="collapsed")
            if st.button("Check answer",type="primary",key=f"brain_check_{qn}"):
                if not st.session_state.brain_test_answered:
                    if opts.index(ans)==correct: st.session_state.brain_test_score+=1; st.success("Correct! ✨")
                    else: st.error(f"Not quite. {explain}")
                    st.session_state.brain_test_answered=True
            if st.session_state.brain_test_answered and st.button("Next question ➜",key=f"brain_next_{qn}"):
                st.session_state.brain_test_q+=1; st.session_state.brain_test_answered=False; st.rerun()
        else:
            st.balloons(); st.success(f"Challenge complete! You scored {st.session_state.brain_test_score}/{len(questions)}.")
            if st.button("Play again",key="brain_restart"):
                for k in ["brain_test_q","brain_test_score","brain_test_answered"]: st.session_state.pop(k,None)
                st.rerun()
    elif game == "🔢 Mini Sudoku":
        st.markdown("### 🔢 Mini Sudoku · Classic 9×9")
        st.caption("Fill each row, column, and 3×3 box with digits 1–9. Fixed clues cannot be changed.")
        solution = [
            [5,3,4,6,7,8,9,1,2], [6,7,2,1,9,5,3,4,8], [1,9,8,3,4,2,5,6,7],
            [8,5,9,7,6,1,4,2,3], [4,2,6,8,5,3,7,9,1], [7,1,3,9,2,4,8,5,6],
            [9,6,1,5,3,7,2,8,4], [2,8,7,4,1,9,6,3,5], [3,4,5,2,8,6,1,7,9]
        ]
        puzzle = [
            [5,3,0,0,7,0,0,0,0], [6,0,0,1,9,5,0,0,0], [0,9,8,0,0,0,0,6,0],
            [8,0,0,0,6,0,0,0,3], [4,0,0,8,0,3,0,0,1], [7,0,0,0,2,0,0,0,6],
            [0,6,0,0,0,0,2,8,0], [0,0,0,4,1,9,0,0,5], [0,0,0,0,8,0,0,7,9]
        ]
        if "sudoku9_board" not in st.session_state: st.session_state.sudoku9_board=[r[:] for r in puzzle]
        board=st.session_state.sudoku9_board
        for r in range(9):
            cols=st.columns(9, gap="small")
            for c in range(9):
                with cols[c]:
                    if puzzle[r][c]: st.markdown(f"<div style='text-align:center;padding:8px 0;font-weight:800;background:#dbeafe;color:#1d4ed8;border-radius:5px;border:1px solid #93c5fd'>{puzzle[r][c]}</div>",unsafe_allow_html=True)
                    else:
                        val=st.selectbox(f"r{r+1}c{c+1}",[0,1,2,3,4,5,6,7,8,9],index=board[r][c],key=f"sudoku9_{r}_{c}",format_func=lambda x:"·" if x==0 else str(x),label_visibility="collapsed")
                        board[r][c]=val
        a,b=st.columns(2)
        with a:
            if st.button("Check Sudoku",type="primary",use_container_width=True,key="sudoku9_check"):
                if board==solution: st.success("Perfect! Every row, column, and 3×3 box is correct. 🏆")
                else:
                    errors=[]
                    for r in range(9):
                        for c in range(9):
                            if board[r][c] and board[r][c]!=solution[r][c]: errors.append((r+1,c+1))
                    if errors: st.warning(f"There are {len(errors)} incorrect filled cell(s). Check the highlighted-by-position cells: "+", ".join(f"R{r}C{c}" for r,c in errors[:12]))
                    else: st.info("No incorrect filled digits so far. Keep filling the empty cells!")
        with b:
            if st.button("Reset puzzle",use_container_width=True,key="sudoku9_reset"):
                st.session_state.sudoku9_board=[r[:] for r in puzzle]
                for r in range(9):
                    for c in range(9): st.session_state.pop(f"sudoku9_{r}_{c}",None)
                st.rerun()
    elif game == "🧠 Memory Match":
        st.markdown("### 🧠 Memory Match · Find the pairs")
        st.caption("Choose two cards at a time and find all matching emoji pairs.")
        if "memory_match_cards" not in st.session_state:
            cards = ["🚀", "🌴", "🎮", "⭐", "🚀", "🌴", "🎮", "⭐"]
            random.shuffle(cards)
            st.session_state.memory_match_cards = cards
            st.session_state.memory_match_found = []
            st.session_state.memory_match_tries = 0
            st.session_state.memory_match_pick = []
        cards = st.session_state.memory_match_cards
        found = st.session_state.memory_match_found
        picks = st.session_state.memory_match_pick
        st.write(f"**Pairs found:** {len(found)//2}/4 · **Attempts:** {st.session_state.memory_match_tries}")
        grid = st.columns(4)
        for idx, card in enumerate(cards):
            with grid[idx % 4]:
                if idx in found:
                    st.button(card, key=f"memory_card_{idx}", disabled=True, use_container_width=True)
                elif idx in picks:
                    st.button(card, key=f"memory_card_{idx}", disabled=True, use_container_width=True)
                else:
                    if st.button("❔", key=f"memory_card_{idx}", use_container_width=True):
                        picks.append(idx)
                        if len(picks) == 2:
                            st.session_state.memory_match_tries += 1
                            a, b = picks
                            if cards[a] == cards[b]:
                                found.extend([a, b])
                            else:
                                st.session_state.memory_match_last_miss = [a, b]
                            st.session_state.memory_match_pick = []
                            st.rerun()
        if len(found) == len(cards):
            st.balloons()
            st.success(f"Brilliant! You found all pairs in {st.session_state.memory_match_tries} attempts.")
        elif st.session_state.get("memory_match_last_miss"):
            st.info("Those cards didn't match. Pick another pair to continue.")
            if st.button("Continue", key="memory_continue"):
                st.session_state.memory_match_last_miss = []
                st.rerun()
        if st.button("🔄 New memory game", key="memory_restart"):
            for k in ["memory_match_cards", "memory_match_found", "memory_match_tries", "memory_match_pick", "memory_match_last_miss"]:
                st.session_state.pop(k, None)
            st.rerun()

    elif game == "🎯 Number Hunt":
        st.markdown("### 🎯 Number Hunt · Guess the secret number")
        st.caption("A secret number from 1 to 50 is waiting. You have 7 attempts.")
        if "number_hunt_secret" not in st.session_state:
            st.session_state.number_hunt_secret = random.randint(1, 50)
            st.session_state.number_hunt_tries = 0
            st.session_state.number_hunt_over = False
            st.session_state.number_hunt_message = "Make your first guess!"
        guess = st.number_input("Your guess", min_value=1, max_value=50, value=25, step=1, key="number_hunt_guess")
        if st.button("🎯 Check guess", type="primary", key="number_hunt_check", disabled=st.session_state.number_hunt_over):
            st.session_state.number_hunt_tries += 1
            secret = st.session_state.number_hunt_secret
            if guess == secret:
                st.session_state.number_hunt_message = f"Correct! You found it in {st.session_state.number_hunt_tries} attempt(s). 🏆"
                st.session_state.number_hunt_over = True
                st.balloons()
            elif st.session_state.number_hunt_tries >= 7:
                st.session_state.number_hunt_message = f"Out of attempts! The number was {secret}."
                st.session_state.number_hunt_over = True
            elif guess < secret:
                st.session_state.number_hunt_message = "Too low! Try a higher number. ⬆️"
            else:
                st.session_state.number_hunt_message = "Too high! Try a lower number. ⬇️"
        st.info(st.session_state.number_hunt_message)
        st.progress(min(st.session_state.number_hunt_tries / 7, 1.0), text=f"Attempts used: {st.session_state.number_hunt_tries}/7")
        if st.button("🔄 New number", key="number_hunt_restart"):
            for k in ["number_hunt_secret", "number_hunt_tries", "number_hunt_over", "number_hunt_message", "number_hunt_guess"]:
                st.session_state.pop(k, None)
            st.rerun()

    else:
        st.markdown("### 🦖 Dino Runner · Dreamztree Edition")
        st.info("🎮 **How to play:** Press **SPACE** or **↑ UP ARROW** to JUMP. Hold **↓ DOWN ARROW** to DUCK under flying birds. On-screen **JUMP**, **DUCK**, and **RESTART** buttons also work. Click inside the game first to activate laptop keyboard controls.")
        components.html(r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
        *{box-sizing:border-box}body{margin:0;font-family:system-ui;background:#10172a;color:white}.wrap{padding:12px;border-radius:18px;background:linear-gradient(135deg,#141e46,#4b1c80 60%,#c02f86);border:1px solid #ffffff30;overflow:hidden}.top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.pill{background:#ffffff20;border:1px solid #ffffff30;padding:7px 12px;border-radius:999px;font-weight:800}.stage{position:relative;margin-top:10px;border-radius:12px;overflow:hidden;background:#7dd3fc}.stage canvas{display:block;width:100%;height:auto;touch-action:manipulation}.actions{display:flex;gap:12px;margin-top:12px;position:relative;z-index:5}.actions button{flex:1;min-height:58px;border:0;border-radius:14px;padding:14px 10px;font-size:17px;font-weight:900;cursor:pointer;touch-action:manipulation;color:#25113f;background:linear-gradient(135deg,#fde047,#fb923c);box-shadow:0 4px 0 #b45309}.actions button:last-child{background:linear-gradient(135deg,#67e8f9,#818cf8);box-shadow:0 4px 0 #4338ca}.hint{text-align:center;font-size:12px;opacity:.9;margin-top:10px}
        </style></head><body><div class="wrap"><div class="top"><strong>🌈 DREAMZTREE RUNNER</strong><span class="pill">⭐ Stars: <span id="stars">0</span></span><span class="pill">🏁 Score: <span id="score">0</span></span><span class="pill">🏆 Best: <span id="best">0</span></span></div><div class="actions"><button id="jump" type="button">⬆ JUMP</button><button id="duck" type="button">⬇ DUCK</button><button id="restart" type="button">↻ RESTART</button></div><div class="stage"><canvas id="game" width="900" height="300" aria-label="Dino runner game"></canvas></div><div class="hint"><b>HOW TO PLAY:</b> Tap JUMP to leap over cacti. Press and hold DUCK to avoid flying birds. Tap RESTART after game over. Keyboard: Space/↑ = jump, ↓ = duck.</div></div>
        <script>
        const cv=document.getElementById('game'),ctx=cv.getContext('2d');let W=cv.width,H=cv.height,ground=244,player,obs,stars,score,starCount,speed,frame,over,shield,night,best=+(localStorage.getItem('dtDinoBest')||0),keys={};document.getElementById('best').textContent=best;
        function reset(){player={x:90,y:ground-48,w:42,h:48,vy:0,duck:false};obs=[];stars=[];score=0;starCount=0;speed=3.6;frame=0;over=false;shield=0;night=false;}
        function rect(x,y,w,h,c){ctx.fillStyle=c;ctx.fillRect(x,y,w,h)}function circle(x,y,r,c){ctx.fillStyle=c;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill()}
        function drawDino(){let p=player;let h=p.duck?27:48,y=p.duck?ground-h:p.y; // colorful pixel-inspired dinosaur
          rect(p.x+5,y+13,27,h-13,'#16a34a');rect(p.x+22,y+2,24,22,'#22c55e');rect(p.x+35,y+9,15,9,'#4ade80');rect(p.x+35,y+10,5,5,'#fff');rect(p.x+37,y+11,2,3,'#172554');rect(p.x+20,y+22,17,8,'#15803d');rect(p.x+8,y+h-8,10,8,'#14532d');rect(p.x+27,y+h-8,10,8,'#14532d');rect(p.x+2,y+18,9,7,'#86efac');if(shield>0){ctx.strokeStyle='#fef08a';ctx.lineWidth=4;ctx.beginPath();ctx.ellipse(p.x+25,y+h/2,35,h/2+14,0,0,Math.PI*2);ctx.stroke();circle(p.x+45,y-5,4,'#fff7ae')}}
        function spawn(){if(frame>110&&frame%Math.max(78,Math.floor(155-speed*3))===0){let bird=Math.random()<.16&&score>140;obs.push({x:W+10,w:bird?42:24,h:bird?22:35,y:bird?ground-65:ground-35,bird,passed:false})}if(frame>70&&frame%170===0)stars.push({x:W+5,y:ground-70-Math.random()*55,r:11})}
        function drawBackground(){let isNight=Math.floor(score/180)%2===1;let g=ctx.createLinearGradient(0,0,0,H);if(isNight){g.addColorStop(0,'#172554');g.addColorStop(1,'#7c3aed')}else{g.addColorStop(0,'#38bdf8');g.addColorStop(1,'#d9f99d')}ctx.fillStyle=g;ctx.fillRect(0,0,W,H);if(isNight){for(let i=0;i<35;i++)circle((i*83+frame*.15)%W,(i*37)%150,1.5,'#fff7ad');circle(760,52,21,'#fef3c7')}else{circle(760,50,25,'#fde047');circle(140,55,18,'#fff');circle(160,55,23,'#fff');circle(181,58,15,'#fff');circle(420,80,15,'#fff');circle(440,77,20,'#fff');circle(461,82,13,'#fff')}ctx.fillStyle=isNight?'#312e81':'#86efac';ctx.beginPath();ctx.moveTo(0,ground);for(let x=0;x<=W;x+=80)ctx.lineTo(x,ground-35-Math.sin((x+frame*1.2)/90)*17);ctx.lineTo(W,ground);ctx.fill();rect(0,ground,W,H-ground,isNight?'#166534':'#22c55e');rect(0,ground,W,4,'#facc15');for(let x=-(frame*speed%50);x<W;x+=50)rect(x,ground+24,20,3,'#bbf7d0')}
        function drawObstacle(o){if(o.bird){let flap=Math.sin(frame*.3)*5;rect(o.x+9,o.y+6,26,12,'#7c3aed');rect(o.x+18,o.y+3,18,10,'#a78bfa');rect(o.x+2,o.y+8,12,5,'#f0abfc');rect(o.x+30,o.y+5,4,4,'#fff');rect(o.x+33,o.y+6,2,2,'#111827');rect(o.x+7,o.y+5+flap,14,5,'#c4b5fd')}else{rect(o.x+6,o.y+8,14,o.h-8,'#f97316');rect(o.x,o.y+19,9,10,'#fb923c');rect(o.x+14,o.y+2,10,o.h-2,'#ea580c');rect(o.x+4,o.y+15,3,3,'#ffedd5')}}
        function drawStar(s){ctx.save();ctx.translate(s.x,s.y);ctx.rotate(frame*.04);ctx.fillStyle='#fde047';ctx.strokeStyle='#fff7ae';ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<10;i++){let a=i*Math.PI/5-Math.PI/2,r=i%2?5:12;ctx.lineTo(Math.cos(a)*r,Math.sin(a)*r)}ctx.closePath();ctx.fill();ctx.stroke();ctx.restore()}
        function loop(){drawBackground();if(!over){frame++;score+=.12;speed=Math.min(11,5+score/110);if(shield>0)shield--;spawn();player.duck=!!keys.ArrowDown||!!keys.KeyS;player.y+=player.vy;player.vy+=.72;if(player.y>ground-player.h){player.y=ground-player.h;player.vy=0}obs.forEach(o=>o.x-=speed);stars.forEach(s=>s.x-=speed);obs=obs.filter(o=>o.x>-60);stars=stars.filter(s=>s.x>-30);for(let o of obs){let ph=player.duck?27:48,py=player.duck?ground-ph:player.y;if(player.x+player.w-13>o.x+5&&player.x+11<o.x+o.w-4&&py+ph-9>o.y+5&&py+8<o.y+o.h-3){if(shield>0){o.x=-100;shield=0}else{over=true;best=Math.max(best,Math.floor(score));localStorage.setItem('dtDinoBest',best);document.getElementById('best').textContent=best}}}for(let s of stars){if(!s.got&&Math.abs((player.x+25)-s.x)<32&&Math.abs((player.y+20)-s.y)<35){s.got=true;starCount++;shield=420;score+=25}}stars=stars.filter(s=>!s.got);}
        obs.forEach(drawObstacle);stars.forEach(drawStar);drawDino();document.getElementById('score').textContent=Math.floor(score);document.getElementById('stars').textContent=starCount;if(shield>0){ctx.fillStyle='#fef08a';ctx.font='bold 15px system-ui';ctx.fillText('STAR SHIELD ✨',20,25)}if(over){ctx.fillStyle='#111827bb';ctx.fillRect(0,0,W,H);ctx.textAlign='center';ctx.fillStyle='#fff';ctx.font='bold 34px system-ui';ctx.fillText('GAME OVER!',W/2,H/2-8);ctx.font='bold 17px system-ui';ctx.fillText('Tap RESTART to run again',W/2,H/2+25);ctx.textAlign='left'}requestAnimationFrame(loop)}
        function jump(){if(over){reset();return}if(player.y>=ground-player.h-1)player.vy=-13}
const jumpBtn=document.getElementById('jump'),duckBtn=document.getElementById('duck'),restartBtn=document.getElementById('restart');
jumpBtn.addEventListener('click',e=>{e.preventDefault();jump()});
jumpBtn.addEventListener('pointerdown',e=>{e.preventDefault();jump()});
duckBtn.addEventListener('pointerdown',e=>{e.preventDefault();keys.ArrowDown=true});
['pointerup','pointercancel','pointerleave'].forEach(ev=>duckBtn.addEventListener(ev,e=>{e.preventDefault();keys.ArrowDown=false}));
duckBtn.addEventListener('lostpointercapture',()=>keys.ArrowDown=false);
restartBtn.addEventListener('click',e=>{e.preventDefault();reset()});window.addEventListener('keydown',e=>{keys[e.code]=true;if(['Space','ArrowUp','KeyW'].includes(e.code)){e.preventDefault();jump()}});document.addEventListener('keydown',e=>{if(['Space','ArrowUp','KeyW'].includes(e.code)){e.preventDefault();jump()}if(['ArrowDown','KeyS'].includes(e.code)){e.preventDefault();keys.ArrowDown=true}});document.addEventListener('keyup',e=>{if(['ArrowDown','KeyS'].includes(e.code))keys.ArrowDown=false});window.addEventListener('keyup',e=>{keys[e.code]=false});cv.setAttribute('tabindex','0');document.body.tabIndex=0;document.body.addEventListener('pointerdown',()=>window.focus());cv.addEventListener('pointerdown',e=>{cv.focus();if(e.target===cv)jump()});reset();loop();
        </script></body></html>""", height=560, scrolling=False)


@st.fragment(run_every="30s")
def _game_zone_popup():
    """Show a compact bottom-right Game Zone invitation every 30 seconds."""
    import time

    now = time.time()

    # Never show the Game Zone invitation while the Game Zone is open.
    if st.query_params.get("page", "dashboard") == "game":
        return

    if "game_popup_last_shown" not in st.session_state:
        st.session_state.game_popup_last_shown = now
        return
    if now - float(st.session_state.game_popup_last_shown) < 29:
        return

    st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"]:has(.dt-game-toast-anchor) {
      position: relative;
    }
    .dt-game-toast {
      position: fixed;
      right: 22px;
      bottom: 24px;
      z-index: 99999;
      width: min(330px, calc(100vw - 32px));
      padding: 16px;
      border-radius: 18px;
      color: #fff;
      background: linear-gradient(135deg, #29205f, #92278f 60%, #f05a6b);
      border: 1px solid rgba(255,255,255,.25);
      box-shadow: 0 14px 40px rgba(0,0,0,.38);
      animation: dt-toast-in .45s ease-out both;
    }
    .dt-game-toast strong {display:block;font-size:16px;margin-bottom:5px}
    .dt-game-toast span {display:block;font-size:13px;opacity:.92}
    @keyframes dt-toast-in {
      from {opacity:0;transform:translateY(18px)}
      to {opacity:1;transform:translateY(0)}
    }
    @media(max-width:600px) {
      .dt-game-toast {right:12px;bottom:16px;width:calc(100vw - 24px)}
    }
    </style>
    <div class="dt-game-toast-anchor"></div>
    <div class="dt-game-toast">
      <strong>🎮 Need a quick break?</strong>
      <span>Try Brain Test, Sudoku, or Dino Runner!</span>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([5, 2])
    with right:
        if st.button("🎮 Play now", key="game_popup_play", type="primary", use_container_width=True):
            st.session_state.game_popup_last_shown = time.time()
            st.query_params["page"] = "game"
            st.rerun()
        if st.button("✕ Not now", key="game_popup_later", use_container_width=True):
            st.session_state.game_popup_last_shown = time.time()
            st.rerun()


def render_team_chat():
    """Render authenticated group chat and one-to-one private messages."""
    st.title("💬 Dreamztree Team Chat")
    st.caption("Group messages and private messages for signed-in team members.")

    client = get_supabase_client()
    if client is None:
        st.error("Supabase is not configured. Check the app's Supabase settings.")
        return

    # Chat requires a real Supabase Auth session. Legacy-only admin logins do not
    # have a database user identity and therefore cannot safely use private chat.
    try:
        auth_response = client.auth.get_user()
        user = auth_response.user
        if not user:
            st.warning("Team Chat requires a Supabase account session. Please sign out and sign in with your work email account.")
            return
    except Exception:
        st.warning("Team Chat requires a Supabase account session. Please sign out and sign in with your work email account.")
        return

    user_id = str(user.id)
    email = user.email or ""
    metadata = getattr(user, "user_metadata", None) or {}
    display_name = str(metadata.get("username") or metadata.get("name") or email or "Team member").strip()

    try:
        client.table("team_chat_profiles").upsert({
            "id": user_id,
            "username": display_name,
            "email": email,
            "updated_at": datetime.now().isoformat(),
        }).execute()
        people_response = (
            client.table("team_chat_profiles")
            .select("id, username, email")
            .neq("id", user_id)
            .order("username")
            .execute()
        )
        people = people_response.data or []
    except Exception as exc:
        st.error("Could not load chat members. Confirm that the Team Chat SQL setup completed successfully.")
        st.caption(f"Technical detail: {exc}")
        return

    mode = st.radio("Chat type", ["Group Chat", "Private Message"], horizontal=True, key="team_chat_mode")
    recipient_id = None
    if mode == "Private Message":
        if not people:
            st.info("No other team members have opened Team Chat yet. Ask each colleague to sign in and open Team Chat once.")
            return
        options = {}
        for person in people:
            label = f"{person.get('username') or person.get('email') or 'Team member'} ({person.get('email') or 'No email'})"
            options[label] = person["id"]
        selected_person = st.selectbox("Send a private message to", list(options.keys()), key="team_chat_recipient")
        recipient_id = options[selected_person]

    try:
        query = (
            client.table("team_chat_messages")
            .select("id, sender_id, recipient_id, message, created_at")
            .order("created_at")
            .limit(100)
        )
        if mode == "Group Chat":
            query = query.is_("recipient_id", "null")
        else:
            query = query.or_(
                f"and(sender_id.eq.{user_id},recipient_id.eq.{recipient_id}),"
                f"and(sender_id.eq.{recipient_id},recipient_id.eq.{user_id})"
            )
        messages = query.execute().data or []
    except Exception as exc:
        st.error("Could not load messages. Confirm the database tables and access policies are set up.")
        st.caption(f"Technical detail: {exc}")
        return

    st.markdown("---")
    st.subheader("Messages")
    if not messages:
        st.info("No messages yet. Start the conversation!")
    for item in messages:
        is_me = str(item.get("sender_id")) == user_id
        sender_label = "You" if is_me else "Team member"
        created_at = str(item.get("created_at") or "")
        st.markdown(f"**{sender_label}** · {created_at}\n\n{item.get('message', '')}")
        st.divider()

    with st.form("team_chat_send_form", clear_on_submit=True):
        message = st.text_area("Your message", max_chars=2000, placeholder="Write a message...")
        send = st.form_submit_button("Send message", type="primary")
    if send:
        message = message.strip()
        if not message:
            st.warning("Please type a message first.")
        else:
            try:
                client.table("team_chat_messages").insert({
                    "sender_id": user_id,
                    "recipient_id": recipient_id,
                    "message": message,
                }).execute()
                st.rerun()
            except Exception as exc:
                st.error("Message could not be sent. Confirm that you are signed in with a Supabase account.")
                st.caption(f"Technical detail: {exc}")


def main():
    require_login()
    if st.session_state.pop("login_just_succeeded", False):
        st.toast("Welcome to Dreamztree Marketing Intelligence", icon="✨")
    inject_premium_theme()
    page = st.query_params.get("page", "dashboard")
    # Keep the Game Zone invitation/notification active on every non-game page.
    # The fragment itself suppresses the popup while the Game Zone is open.
    _game_zone_popup()
    if page == "game":
        if st.button("← Back to Meta Leads Dashboard", key="back_to_dashboard"):
            st.query_params["page"] = "dashboard"
            st.rerun()
        render_games_page()
        return
    if page == "chat":
        if st.button("← Back to Meta Leads Dashboard", key="back_from_team_chat"):
            st.query_params["page"] = "dashboard"
            st.rerun()
        render_team_chat()
        return
    # Dreamztree landing page with a clean hero; global particle animation is applied in inject_premium_theme().
    st.markdown("""
    <style>
      .dt-landing { position:relative; overflow:hidden; margin:10px 0 22px; padding:30px clamp(20px,4vw,46px) 34px;
        border-radius:28px; background:linear-gradient(125deg,rgba(124,58,237,.25),rgba(37,99,235,.18) 48%,rgba(13,148,136,.20));
        border:1px solid rgba(167,139,250,.38); box-shadow:0 22px 70px rgba(0,0,0,.22); }
      .dt-landing:before {content:"";position:absolute;inset:0;pointer-events:none;z-index:0;
        background:radial-gradient(ellipse at 12% 10%,rgba(236,72,153,.16),transparent 42%),radial-gradient(ellipse at 88% 85%,rgba(94,234,212,.12),transparent 42%);}
      .dt-brand-row {display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:54px;position:relative;}
      .dt-brand {display:flex;align-items:center;gap:14px;color:#fff;font-size:clamp(1.25rem,2.4vw,2rem);font-weight:800;letter-spacing:-.04em;}
      .dt-brand-tag {font-size:clamp(.75rem,1.6vw,1.25rem);color:#5eead4;letter-spacing:.035em;text-align:right;}
      .dt-landing-kicker {text-align:center;color:#77f3df;font-size:clamp(.8rem,1.4vw,1.1rem);font-weight:800;margin-bottom:24px;position:relative;}
      .dt-landing-title {text-align:center;color:#f8f9fc;font-size:clamp(1.6rem,3.2vw,2.8rem);line-height:1.16;font-weight:850;letter-spacing:-.035em;margin:0 auto 20px;max-width:1100px;position:relative;}
      .dt-landing-copy {text-align:center;color:#d2def2;font-size:clamp(1rem,1.8vw,1.5rem);line-height:1.5;margin:0 auto 26px;position:relative;}
      .dt-landing-actions {display:flex;justify-content:center;gap:14px;flex-wrap:wrap;position:relative;}
      .dt-landing-actions a {display:inline-flex;align-items:center;justify-content:center;padding:15px 24px;border-radius:16px;text-decoration:none!important;font-size:clamp(1rem,1.7vw,1.35rem);transition:transform .22s ease,box-shadow .22s ease;}
      .dt-landing-actions a:hover {transform:translateY(-3px);box-shadow:0 12px 32px rgba(96,165,250,.18);}
      .dt-landing-actions .primary {background:linear-gradient(100deg,#ec4899,#8b5cf6 55%,#2563eb);color:#fff!important;border:1px solid rgba(255,255,255,.18);font-weight:750;}
      .dt-landing-actions .secondary {background:rgba(15,23,42,.25);color:#f8f9fc!important;border:1px solid rgba(167,139,250,.55);}
      .dt-report-intro {margin:0 0 22px;padding:26px 24px;border:1px solid rgba(167,139,250,.32);border-radius:24px;background:linear-gradient(120deg,rgba(99,102,241,.14),rgba(20,184,166,.08));}
      .dt-report-intro h2 {margin:0 0 10px;color:#f8f9fc;font-size:clamp(1.3rem,2.2vw,2rem);}
      .dt-report-intro p {margin:0;color:#d2def2;font-size:1rem;}
      .dt-landing + div {scroll-margin-top:24px;}
      @media(max-width:650px){.dt-landing{padding:22px 16px}.dt-brand-row{margin-bottom:38px;align-items:flex-start}.dt-brand{gap:10px}.dt-landing-actions a{width:100%;box-sizing:border-box}}
      @media(prefers-reduced-motion:reduce){.dt-landing-actions a{animation:none;transition:none}}
    </style>
    <section class="dt-landing">
      <div class="dt-landing-kicker">DIGITAL MARKETING ANALYTICS</div>
      <h1 class="dt-landing-title">TURN YOUR CAMPAIGN DATA INTO GROWTH</h1>
      <p class="dt-landing-copy">Track leads. Analyze ad spend. Discover winning campaigns.</p>
      <div class="dt-landing-actions">
        <a class="primary" href="#report-form">Explore Reports ↓</a>
        <a class="secondary" href="#campaign-insights">Campaign Insights</a>
      </div>
    </section>
    <section class="dt-report-intro" id="report-form">
      <h2>↓ Scroll down to create a report</h2>
      <p>The existing report-making form and dashboard features remain below the landing page.</p>
    </section>
    """, unsafe_allow_html=True)
    header_left, game_col, chat_col, header_right = st.columns([3, 1.25, 1.1, 1])
    with game_col:
        if st.button("🎮 Game Zone", key="open_game_zone_main", use_container_width=True):
            st.query_params["page"] = "game"
            st.rerun()
    with chat_col:
        if st.button("💬 Team Chat", key="open_team_chat_main", use_container_width=True):
            st.query_params["page"] = "chat"
            st.rerun()
    with header_right:
        if st.button("Sign out", use_container_width=True):
            if st.session_state.get("auth_method") == "supabase":
                try:
                    client = get_supabase_client()
                    if client is not None:
                        client.auth.sign_out()
                except Exception:
                    pass
            st.session_state["authenticated"] = False
            st.session_state.pop("authenticated_user", None)
            st.session_state.pop("auth_method", None)
            st.session_state.pop("supabase_access_token", None)
            st.session_state.pop("supabase_refresh_token", None)
            st.rerun()
    st.caption("Upload a Meta Ads Excel export to generate a branch-wise, staff-wise leads report.")

    st.markdown('<div id="campaign-insights"></div>', unsafe_allow_html=True)
    with st.expander("⚙️ Report settings · date, exchange rate and campaign mapping", expanded=False):
        date_value = st.date_input("Report date", value=datetime.today().date())

        settings_left, settings_right = st.columns(2, gap="large")
        with settings_left:
            st.subheader("USD → KWD exchange rate")
            use_manual_rate = st.checkbox(
                "Use manual fallback rate instead",
                value=False,
                help="Enable this only if you need to use your company's rate or the automatic reference rate is unavailable.",
            )
            manual_factor = st.number_input(
                "Manual fallback rate (1 USD = KWD)",
                min_value=0.000001,
                value=MANUAL_FALLBACK_KWD_FACTOR,
                step=0.001,
                format="%.6f",
                disabled=not use_manual_rate,
            )
            if use_manual_rate:
                factor = float(manual_factor)
                st.warning(f"Manual fallback rate in use: 1 USD = {factor:.6f} KWD. This is not a live rate.")
                rate_source_label = "Manual fallback"
                rate_date_label = "Manually entered"
            else:
                try:
                    with st.spinner("Fetching latest published USD → KWD reference rate…"):
                        factor, rate_date_label = fetch_usd_kwd_rate()
                    rate_source_label = "Open ER API reference rate"
                    st.success(f"1 USD = {factor:.6f} KWD")
                    st.caption(f"Rate date: {rate_date_label} · Source: open.er-api.com · Cached for up to 24 hours.")
                except Exception as exc:
                    factor = float(manual_factor)
                    rate_source_label = "Manual fallback (API unavailable)"
                    rate_date_label = "Manually entered"
                    st.error("Could not fetch the exchange rate. The app is using the clearly labelled manual fallback below.")
                    st.warning(f"Fallback in use: 1 USD = {factor:.6f} KWD. Check your connection and verify this rate before using cost totals.")
                    st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
        with settings_right:
            st.subheader("Campaign mapping")
            mapping_upload = st.file_uploader(
                "Optional campaign mapping file", type=["xlsx", "xls", "csv"], key="mapping_upload_settings"
            )
            st.caption("Mapping columns: Campaign, Staff, Course, Branch.")
    mappings = read_mapping_file(mapping_upload)
    st.subheader("1. Upload Meta Ads reports")
    upload_today_col, upload_yesterday_col = st.columns(2)
    with upload_today_col:
        uploaded = st.file_uploader("Today's Meta Ads Excel report", type=["xlsx", "xls"], key="meta_excel")
    with upload_yesterday_col:
        yesterday_uploaded = st.file_uploader(
            "Yesterday's Meta Ads Excel report (optional)",
            type=["xlsx", "xls"],
            key="yesterday_meta_excel",
            help="Upload yesterday's export to compare leads, spend, and top-performing campaigns.",
        )
    if uploaded is None:
        st.info("Upload today's Meta Ads Excel export to begin. Add yesterday's report for a day-over-day comparison.")
        st.subheader("Campaign mapping preview")
        st.dataframe(mappings, use_container_width=True, hide_index=True)
        st.download_button("Download campaign mapping template (CSV)", mappings.to_csv(index=False).encode("utf-8-sig"), "dreamztree_campaign_mapping.csv", "text/csv")
        return
    try:
        raw = pd.read_excel(uploaded)
        original_cols = list(raw.columns)
        normalized_cols = [normalize(c) for c in original_cols]
        def find_col(predicate, fallback):
            for i, c in enumerate(normalized_cols):
                if predicate(c):
                    return original_cols[i]
            return original_cols[min(fallback, len(original_cols)-1)]
        campaign_col = find_col(lambda c: "campaign" in c, 0)
        result_col = find_col(lambda c: "result" in c and "initial" not in c, 1)
        spent_col = find_col(lambda c: "spent" in c or "amount" in c, 2)
        df = raw[[campaign_col, result_col, spent_col]].copy()
        df.columns = ["Campaign", "Results", "Spent"]
        df["Campaign"] = df["Campaign"].fillna("").astype(str)
        df["Results"] = pd.to_numeric(df["Results"], errors="coerce").fillna(0).astype(int)
        df["Spent"] = pd.to_numeric(df["Spent"], errors="coerce").fillna(0.0)

        # Preserve zero-result campaigns for spend visibility, while keeping them out of the lead report.
        no_result_df = df[df["Results"] <= 0].copy().reset_index(drop=True)
        no_result_count = len(no_result_df)
        no_result_spend_usd = float(no_result_df["Spent"].sum())
        df = df[(df["Results"] > 0) & (df["Results"] <= 10000)].reset_index(drop=True)

        st.success(f"Loaded {len(df)} campaigns with {int(df['Results'].sum())} total results.")
        with st.container(border=True):
            st.markdown("### ⚠️ Campaigns with no results")
            if no_result_count:
                st.warning(
                    f"Attention: {no_result_count} campaign(s) generated zero results "
                    f"and spent ${no_result_spend_usd:,.2f} USD "
                    f"({no_result_spend_usd * factor:,.3f} KD). "
                    "These costs are excluded from the leads report but shown here for review."
                )
                nr1, nr2, nr3 = st.columns(3)
                nr1.metric("Zero-result campaigns", f"{no_result_count:,}")
                nr2.metric("Total spend · USD", f"${no_result_spend_usd:,.2f}")
                nr3.metric("Total spend · KWD", f"{no_result_spend_usd * factor:,.3f} KD")

                no_result_display = no_result_df[["Campaign", "Results", "Spent"]].copy()
                no_result_display["Cost (KWD)"] = no_result_display["Spent"] * factor
                no_result_display = no_result_display.rename(
                    columns={"Campaign": "Campaign name", "Results": "Results", "Spent": "Spend (USD)"}
                )
                no_result_display["Spend (USD)"] = no_result_display["Spend (USD)"].map(lambda v: f"${v:,.2f}")
                no_result_display["Cost (KWD)"] = no_result_display["Cost (KWD)"].map(lambda v: f"{v:,.3f} KD")
                st.dataframe(no_result_display, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download no-result campaign list (CSV)",
                    no_result_df.assign(**{"Cost_KWD": no_result_df["Spent"] * factor})[
                        ["Campaign", "Results", "Spent", "Cost_KWD"]
                    ].to_csv(index=False).encode("utf-8-sig"),
                    f"dreamztree_no_result_campaigns_{date_value.strftime('%Y%m%d')}.csv",
                    "text/csv",
                )
            else:
                st.success("No campaigns with zero results were found in this export.")
        st.subheader("2. Review campaign assignments")
        assignments = []
        for _, r in df.iterrows():
            staff, course, branch, status = infer_campaign(r["Campaign"], mappings)
            assignments.append({"Campaign": r["Campaign"], "Results": int(r["Results"]), "Spent": float(r["Spent"]), "Staff": staff, "Course": course, "Branch": branch, "Status": status})
        assigned = pd.DataFrame(assignments)
        # A campaign can be included in branch/staff totals when Staff and Branch are known.
        # A missing Course is labelled "Unclassified course" in the report instead of excluding leads.
        initial_unresolved = assigned[(assigned["Staff"].astype(str).str.strip() == "") | (assigned["Branch"].astype(str).str.strip() == "") | (assigned["Course"].astype(str).str.strip() == "")]
        if not initial_unresolved.empty:
            st.warning(f"{len(initial_unresolved)} campaign(s) need review. Campaigns with Staff and Branch identified can still be included; missing courses will appear as 'Unclassified course'.")
            st.dataframe(initial_unresolved, use_container_width=True, hide_index=True)
        edited = st.data_editor(
            assigned,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Mapping status", disabled=True),
                "Results": st.column_config.NumberColumn("Results", disabled=True),
                "Spent": st.column_config.NumberColumn("Amount spent", disabled=True, format="%.2f"),
            },
            num_rows="fixed",
            key="assignments_editor",
        )
        unresolved = edited[(edited["Staff"].astype(str).str.strip() == "") | (edited["Course"].astype(str).str.strip() == "") | (edited["Branch"].astype(str).str.strip() == "")]
        if not unresolved.empty:
            can_include = unresolved[(unresolved["Staff"].astype(str).str.strip() != "") & (unresolved["Branch"].astype(str).str.strip() != "")]
            needs_staff_branch = len(unresolved) - len(can_include)
            st.warning(f"{len(can_include)} campaign(s) with Staff and Branch identified can be included despite a missing course. {needs_staff_branch} campaign(s) still need Staff or Branch review.")
        if st.button("Generate report", type="primary"):
            # Only Staff and Branch are required for inclusion. Missing courses are not allowed
            # to remove otherwise valid leads from the branch/staff report.
            valid = edited[(edited["Staff"].astype(str).str.strip() != "") & (edited["Branch"].astype(str).str.strip() != "")].copy()
            if valid.empty:
                st.error("No campaigns have both Staff and Branch identified. Review the assignment table first.")
                return
            valid["Course"] = valid["Course"].astype(str).str.strip().replace("", "Unclassified course")
            grouped = valid.groupby(["Branch", "Staff", "Course"], sort=False).agg(Results=("Results", "sum"), Spent=("Spent", "sum")).reset_index()
            lines = [f"*📋 Leads Count  ·  {date_value.strftime('%d/%m/%Y')}*", ""]
            grand_leads, grand_spent = 0, 0.0
            for branch in BRANCH_ORDER + [b for b in grouped["Branch"].unique() if b not in BRANCH_ORDER]:
                bd = grouped[grouped["Branch"] == branch]
                if bd.empty:
                    continue
                branch_spent = bd["Spent"].sum()
                lines.extend([f"*{branch}*  —  Cost: {round(branch_spent * factor, 2)} KD", "——————————"])
                staff_order = STAFF_ORDER.get(branch, [])
                extras = [s for s in bd["Staff"].unique() if s not in staff_order]
                for staff in staff_order + extras:
                    for _, rr in bd[bd["Staff"] == staff].sort_values("Results", ascending=False).iterrows():
                        lines.append(f"{rr['Staff']}  -  {rr['Course']}  -  {int(rr['Results'])}")
                lines.append("")
                grand_leads += int(bd["Results"].sum())
                grand_spent += float(branch_spent)
            lines.extend(["——————————", f"*🏆 Grand Total  —  {grand_leads} Leads  |  Total Cost: {round(grand_spent * factor, 2)} KD*"])
            report = "\n".join(lines)
            st.subheader("3. Generated report")
            st.code(report, language=None)
            st.download_button("Download report (.txt)", report.encode("utf-8"), f"dreamztree_leads_{date_value.strftime('%Y%m%d')}.txt", "text/plain")
            st.download_button("Download reviewed mappings (.csv)", edited[["Campaign", "Staff", "Course", "Branch"]].to_csv(index=False).encode("utf-8-sig"), "dreamztree_campaign_mapping_updated.csv", "text/csv")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total leads included", f"{grand_leads:,}")
            m2.metric("Total cost", f"{round(grand_spent * factor, 2):.2f} KD")
            m3.metric("Campaigns included", f"{len(valid):,}")
            st.subheader("Performance analytics")
            branch_chart = valid.groupby("Branch", as_index=False).agg(Leads=("Results", "sum"), Spend_USD=("Spent", "sum"))
            branch_chart["Spend_KWD"] = branch_chart["Spend_USD"] * factor
            course_chart = valid.assign(Course=valid["Course"].astype(str).str.strip().replace("", "Unclassified course")).groupby("Course", as_index=False)["Results"].sum().sort_values("Results", ascending=False).head(12)
            chart_left, chart_right = st.columns(2, gap="large")
            with chart_left:
                st.markdown("#### Leads by branch")
                branch_leads_plot = branch_chart.sort_values("Leads", ascending=True)
                fig_leads = px.bar(
                    branch_leads_plot, x="Leads", y="Branch", orientation="h",
                    text="Leads", color_discrete_sequence=["#3dd6b3"],
                    template="plotly_dark",
                )
                fig_leads.update_layout(
                    height=300, margin=dict(l=12, r=20, t=12, b=12),
                    showlegend=False, xaxis_title="Leads", yaxis_title="",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E8EEF7", size=12),
                )
                fig_leads.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(fig_leads, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            with chart_right:
                st.markdown("#### Cost by branch · KWD")
                branch_cost_plot = branch_chart.sort_values("Spend_KWD", ascending=True)
                fig_cost = px.bar(
                    branch_cost_plot, x="Spend_KWD", y="Branch", orientation="h",
                    text=branch_cost_plot["Spend_KWD"].map(lambda x: f"{x:.3f}"),
                    color_discrete_sequence=["#6ea8fe"], template="plotly_dark",
                )
                fig_cost.update_layout(
                    height=300, margin=dict(l=12, r=28, t=12, b=12),
                    showlegend=False, xaxis_title="Cost (KWD)", yaxis_title="",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E8EEF7", size=12),
                )
                fig_cost.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(fig_cost, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            st.markdown("#### Top courses by leads")
            course_plot = course_chart.sort_values("Results", ascending=True)
            fig_courses = px.bar(
                course_plot, x="Results", y="Course", orientation="h",
                text="Results", color_discrete_sequence=["#f7bd60"],
                template="plotly_dark",
            )
            fig_courses.update_layout(
                height=max(360, 36 * len(course_plot) + 70),
                margin=dict(l=18, r=28, t=12, b=24),
                showlegend=False, xaxis_title="Leads", yaxis_title="",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E8EEF7", size=12),
                yaxis=dict(automargin=True, tickfont=dict(size=12)),
            )
            fig_courses.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_courses, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            st.caption(f"{len(unresolved)} campaign(s) require review if left incomplete.")
            st.caption(f"Exchange rate used: 1 USD = {factor:.6f} KWD · {rate_source_label} · Rate date: {rate_date_label}.")

            # Optional day-over-day comparison. Yesterday is processed with the same campaign
            # filters and mapping rules; today's figures use the reviewed assignments above.
            st.divider()
            st.subheader("Yesterday vs today")
            if yesterday_uploaded is None:
                st.info("Upload yesterday's Meta Ads Excel report above to compare lead volume, cost, and the highest-lead campaign.")
            else:
                try:
                    yesterday_assigned = load_campaign_report(yesterday_uploaded, mappings)
                    yesterday_valid, yesterday_leads, yesterday_cost, yesterday_top = summarize_campaign_performance(
                        yesterday_assigned, factor
                    )
                    today_valid, today_leads, today_cost, today_top = summarize_campaign_performance(
                        edited, factor
                    )

                    if yesterday_valid.empty:
                        st.warning("Yesterday's file did not contain campaigns with both Staff and Branch identified. Review its mapping before comparing.")
                    else:
                        lead_delta = today_leads - yesterday_leads
                        cost_delta = today_cost - yesterday_cost
                        lead_pct = (lead_delta / yesterday_leads * 100) if yesterday_leads else None
                        cost_pct = (cost_delta / yesterday_cost * 100) if yesterday_cost else None

                        st.markdown(
                            "### Exact daily totals",
                        )
                        st.caption("These are the actual totals for each uploaded day, not just the difference.")
                        day1, day2, day3, day4 = st.columns(4, gap="medium")
                        day1.metric("Yesterday · Leads", f"{yesterday_leads:,}")
                        day2.metric("Today · Leads", f"{today_leads:,}", f"{lead_delta:+,} leads")
                        day3.metric("Yesterday · Cost", f"{yesterday_cost:,.3f} KD")
                        day4.metric("Today · Cost", f"{today_cost:,.3f} KD", f"{cost_delta:+.3f} KD")

                        change1, change2 = st.columns(2, gap="medium")
                        change1.metric(
                            "Lead change",
                            f"{lead_delta:+,} leads",
                            f"{lead_pct:+.1f}% vs yesterday" if lead_pct is not None else "Yesterday total is zero",
                            delta_color="normal",
                        )
                        change2.metric(
                            "Cost change",
                            f"{cost_delta:+.3f} KD",
                            f"{cost_pct:+.1f}% vs yesterday" if cost_pct is not None else "Yesterday cost is zero",
                            delta_color="inverse",
                        )

                        if lead_delta > 0 and cost_delta < 0:
                            st.success("Good result: you generated more leads while spending less.")
                        elif lead_delta > 0 and cost_delta > 0:
                            st.info("Lead volume increased, but ad spend also increased. Check whether the extra leads justify the extra cost.")
                        elif lead_delta < 0 and cost_delta < 0:
                            st.warning("Both leads and spend decreased. Check whether the lower spend explains the lead drop.")
                        elif lead_delta < 0 and cost_delta > 0:
                            st.error("Attention: leads decreased while spend increased. Review campaign targeting, creative, and budgets.")
                        else:
                            st.info("Lead volume and spend are broadly unchanged. Review the campaign-level table below.")

                        top_left, top_right = st.columns(2, gap="large")
                        with top_left:
                            st.markdown("#### 🏆 Best campaign yesterday")
                            st.write(f"**{yesterday_top['Campaign']}**")
                            st.caption(
                                f"{int(yesterday_top['Results']):,} leads · "
                                f"{float(yesterday_top['Cost_KWD']):.3f} KD spend · "
                                f"{yesterday_top['Branch']} · {yesterday_top['Staff']}"
                            )
                        with top_right:
                            st.markdown("#### 🏆 Best campaign today")
                            if today_top is not None:
                                st.write(f"**{today_top['Campaign']}**")
                                st.caption(
                                    f"{int(today_top['Results']):,} leads · "
                                    f"{float(today_top['Cost_KWD']):.3f} KD spend · "
                                    f"{today_top['Branch']} · {today_top['Staff']}"
                                )
                            else:
                                st.write("No campaigns today have both Staff and Branch assigned.")

                        # Side-by-side campaign comparison makes day-over-day movement explicit.
                        def campaign_rollup(summary, prefix):
                            if summary.empty:
                                return pd.DataFrame(columns=["Campaign", f"{prefix} leads", f"{prefix} cost (KD)"])
                            return summary.groupby("Campaign", as_index=False).agg(
                                **{
                                    f"{prefix} leads": ("Results", "sum"),
                                    f"{prefix} cost (KD)": ("Cost_KWD", "sum"),
                                }
                            )

                        yesterday_rollup = campaign_rollup(yesterday_valid, "Yesterday")
                        today_rollup = campaign_rollup(today_valid, "Today")
                        campaign_compare = yesterday_rollup.merge(today_rollup, on="Campaign", how="outer").fillna(0)
                        if not campaign_compare.empty:
                            campaign_compare["Lead change"] = (
                                campaign_compare["Today leads"] - campaign_compare["Yesterday leads"]
                            ).astype(int)
                            campaign_compare["Cost change (KD)"] = (
                                campaign_compare["Today cost (KD)"] - campaign_compare["Yesterday cost (KD)"]
                            ).round(3)
                            campaign_compare = campaign_compare.sort_values(
                                ["Today leads", "Yesterday leads"], ascending=False
                            )
                            st.markdown("#### Exact leads and cost by campaign — yesterday vs today")
                            st.caption("Positive lead change means more leads today. Negative cost change means less money spent today.")
                            st.dataframe(
                                campaign_compare,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Yesterday leads": st.column_config.NumberColumn(format="%d"),
                                    "Today leads": st.column_config.NumberColumn(format="%d"),
                                    "Lead change": st.column_config.NumberColumn(format="%+d"),
                                    "Yesterday cost (KD)": st.column_config.NumberColumn(format="%.3f KD"),
                                    "Today cost (KD)": st.column_config.NumberColumn(format="%.3f KD"),
                                    "Cost change (KD)": st.column_config.NumberColumn(format="%+.3f KD"),
                                },
                            )
                            st.download_button(
                                "Download comparison CSV",
                                campaign_compare.to_csv(index=False).encode("utf-8-sig"),
                                f"dreamztree_campaign_comparison_{date_value.strftime('%Y%m%d')}.csv",
                                "text/csv",
                            )
                        st.caption(
                            "For a fair comparison, both uploads should cover one full day each. "
                            "Campaigns are included only when Staff and Branch are identified. "
                            "Zero-result campaigns are shown in the separate no-result section."
                        )
                except Exception as compare_exc:
                    st.error(f"Could not compare yesterday's report: {compare_exc}")
                    st.caption("Check that both files use the same Meta Ads export format and that the mapping is reviewed.")
    except Exception as e:
        st.error(f"Could not process this Excel file: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()import re
import random
import hmac
import hashlib
import os
import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

st.set_page_config(page_title="Dreamztree Meta Report", page_icon="D", layout="wide")

# Default mapping from the existing Dreamztree report. Edit or extend in the Mapping editor.
DEFAULT_MAPPINGS = [
    ("Jincy |01| healthacreleads campaign", "Jincy", "Healthcare", "Mangaf"),
    ("hishana/bahrain/computer/29/11", "Hishana", "Computer", "Bahrain"),
    ("healthcare | hishana | bahrain | 2/12/2025", "Hishana", "Healthcare", "Bahrain"),
    ("healthcare placement | arya | 15/12/2025 engagement", "Arya", "Healthcare", "Salmiya"),
    ("german | ligin | 20/1/26 engagement campaign", "Ligin", "German", "Salmiya"),
    ("healthcare | ligin | 22/1/26 engagement campaign", "Ligin", "Healthcare", "Salmiya"),
    ("healthcare | seetha | 19 /2/26 engagement campaign", "Seetha", "Healthcare", "Bahrain"),
    ("computer | hishana | 19/2/26", "Hishana", "Computer", "Bahrain"),
    ("computer | seetha | 19/2/26", "Seetha", "Computer", "Bahrain"),
    ("mangaf | german |27/2/26", "Aswathy", "German", "Salmiya"),
    ("ligin | ielts | 28/2/26", "Ligin", "IELTS", "Salmiya"),
    ("jincy | logistics | 2/3/26", "Jincy", "Logistics", "Mangaf"),
    ("arya | philipi | 14/3/26", "Arya", "Philipi", "Salmiya"),
    ("sethu | boost video | 15/3/26", "Sethu", "Boost Video", "Mangaf"),
    ("jincy | safety course | 26/3/26", "Jincy", "Safety Course", "Mangaf"),
    ("healthcare | seetha | 27/3/26", "Seetha", "Healthcare", "Bahrain"),
    ("practical video | arya | 28/3/26", "Arya", "Practical Video", "Salmiya"),
    ("teacher training | arya | 30/3/26", "Arya", "Teacher Training", "Salmiya"),
    ("computer | arya | 30/3/26", "Arya", "Computer", "Salmiya"),
    ("sethu | testimonial healthcare | 2/4/26", "Sethu", "Healthcare", "Mangaf"),
    ("jincy | professional career courses | 3/4/26", "Jincy", "Professional Courses", "Mangaf"),
    ("prometric | arya | 4/3/26", "Arya", "Prometric", "Salmiya"),
    ("jincy | teacher training | 13/4/26", "Jincy", "Teacher Training", "Mangaf"),
    ("jincy | german  | 13/4/26", "Jincy", "German", "Mangaf"),
    ("hishana | tuition | 13/4/26", "Hishana", "Tuition", "Bahrain"),
    ("ligin | prometric | 16/4/26", "Ligin", "Prometric", "Salmiya"),
    ("arya  | healthcare(intership) | 18/4/26", "Arya", "Healthcare", "Salmiya"),
    ("arya  | spa | 30/4/26", "Arya", "Spa", "Salmiya"),
    ("jincy | autocad | 30/4/26", "Jincy", "Autocad", "Mangaf"),
    ("jincy | hospital administration | 5/5/26", "Jincy", "Hospital Admin", "Mangaf"),
    ("jincy | language training | 6/5/26", "Jincy", "Language Training", "Mangaf"),
    ("caregiving anakha 09/05/2026", "Anakha", "Caregiving", "Bahrain"),
    ("hishana new | healthcare | 11/5/26", "Hishana", "Healthcare", "Bahrain"),
    ("hishana | phonics | 10/5/26", "Hishana", "Phonics", "Bahrain"),
    ("hishna new | tuition | 10/5/26", "Hishana", "Tuition", "Bahrain"),
    ("hishana | healthcare | 11/5/26", "Hishana", "Healthcare", "Bahrain"),
    ("ligin | healthcare  | 16/5/26", "Ligin", "Healthcare", "Salmiya"),
    ("jincy | ielts  | 16/5/26", "Jincy", "IELTS", "Mangaf"),
    ("arya  | spa video | 18/5/26", "Arya", "Spa", "Salmiya"),
    ("jincy   | influencer ad new | 18/5/26", "Jincy", "Influencer Ad", "Mangaf"),
    ("seetha  | tuition  | 18/5/26", "Seetha", "Tuition", "Bahrain"),
    ("vedhika | healthcare | 19/5/26", "Vedhika", "Healthcare", "Kerala"),
    ("arya  | spa ad new | 20/5/26", "Arya", "Spa", "Salmiya"),
    ("vedhika | healthcare | 20/5/26", "Vedhika", "Healthcare", "Kerala"),
    ("jincy | language training | 20/5/26", "Jincy", "Language Training", "Mangaf"),
    ("hishana  | healthcare | 21/5/26", "Hishana", "Healthcare", "Bahrain"),
    ("seetha | healthcare | 25/5/26", "Seetha", "Healthcare", "Bahrain"),
    ("seetha | tution | 29-05-2026", "Seetha", "Tuition", "Bahrain"),
    ("sethu | tuition | 27-05-2026", "Sethu", "Tuition", "Mangaf"),
    ("seetha  | healthcare | 1/6/26", "Seetha", "Healthcare", "Bahrain"),
    ("anakha | healthcare | 3/6/26", "Anakha", "Healthcare", "Bahrain"),
    ("montessori | ligin  | 5/6/26", "Ligin", "Montessori", "Salmiya"),
    ("ligin | hospital administration | 05 | 06 | 2026", "Ligin", "Hospital Admin", "Salmiya"),
    ("healthcare  | vedhika | 9/6/26", "Vedhika", "Healthcare", "Kerala"),
    ("anakha | summer camp | 9/6/26", "Anakha", "Summer Camp", "Bahrain"),
    ("anakha | healthcare | 10/6/26", "Anakha", "Healthcare", "Bahrain"),
    ("ligin  | josun video | 11/6/26", "Ligin", "Josun Video", "Salmiya"),
    ("tuition  | anakha | 12/6/26", "Anakha", "Tuition", "Bahrain"),
    ("jincy | computer  |  14/6/26", "Jincy", "Computer", "Mangaf"),
    ("jincy  | post bsc | 14/6/26", "Jincy", "Post BSC", "Mangaf"),
    ("nissi | nanny course  | 16/6/26", "Nissi", "Nanny Course", "Mangaf"),
    ("vipin  | healthcare  | 16/6/26", "Vipin", "Healthcare", "Kerala"),
    ("aswathy | healthcare  | 18/6/26", "Aswathy", "Healthcare", "Kerala"),
    ("anupama | healthcare | 18/6/26", "Anupama", "Healthcare", "Kerala"),
    ("anupama | healthcare | 20/6/26", "Anupama", "Healthcare", "Kerala"),
    ("seetha  | ielts | 24/6/26", "Seetha", "IELTS", "Bahrain"),
    ("seetha  | cg | 24/6/26", "Seetha", "CG", "Bahrain"),
    ("anupama | practical video | 24/6/26", "Anupama", "Practical Video", "Kerala"),
    ("nissi | computer | 25/6/26", "Nissi", "Computer", "Mangaf"),
    ("sushma | ielts | 25/6/26", "Sushma", "IELTS", "Mangaf"),
    ("shelbin hiring gda&gna 6/29/2026 campaign", "Shelbin", "Hiring", "Kerala"),
    ("sushma autocad  7/7/2026 campaign", "Sushma", "Autocad", "Mangaf"),
    ("nursing  tutor h shelbin 08/07/2026", "Shelbin", "Nursing Tutor", "Kerala"),
    ("roshni cg 08/07/2026", "Roshni", "CG", "Kerala"),
    ("hishana pte 10/07/2026", "Hishana", "PTE", "Bahrain"),
    ("nissi cg 16/07/2026", "Nissi", "CG", "Mangaf"),
    ("hiring | german | dani | 24/6/26", "Dani", "German", "Kerala"),
    ("dani  cg 20/07/2026", "Dani", "CG", "Kerala"),
    ("hospital am shelbin 31/07/2026", "Shelbin", "Hospital Admin", "Kerala"),
    ("ham sushma 31/07/2026", "Sushma", "HAM", "Mangaf"),
    ("sushma teacher 31/07/2026", "Sushma", "Teacher Training", "Mangaf"),
    ("shelbin hr 04/08/2026", "Shelbin", "HR", "Kerala"),
    ("dani | healthcare  | 7/8/26", "Dani", "Healthcare", "Kerala"),
    ("anupama j&v 11/08/2026", "Anupama", "J&V Video", "Kerala"),
    ("jincy j&v 12/08/2026", "Jincy", "J&V Video", "Mangaf"),
    ("jincy | logistics | 13/8/26", "Jincy", "Logistics", "Mangaf"),
    ("hishana | ielts | 13/8/26", "Hishana", "IELTS", "Bahrain"),
    ("sushma | language training | 14/8/26", "Sushma", "Language Training", "Mangaf"),
    ("hishana  | computer | 14/8/26", "Hishana", "Computer", "Bahrain"),
    ("seetha | language training | 14/8/26", "Seetha", "Language Training", "Bahrain"),
    ("sushma | safety course | 17/8/26", "Sushma", "Safety Course", "Mangaf"),
    ("arya gda 24/08/2026", "Arya", "GDA", "Salmiya"),
    ("hishana tuition 24/08/2026", "Hishana", "Tuition", "Bahrain"),
    ("arya cg phili 27/08/2026", "Arya", "CG", "Salmiya"),
    ("nissi tuition 27/08/2026", "Nissi", "Tuition", "Mangaf"),
    ("hishana tuition 27/08/2026", "Hishana", "Tuition", "Bahrain"),
    ("nissi house keeping 28/08/2026", "Nissi", "House Keeping", "Mangaf"),
    ("nissi | tuition video | 31/8/26", "Nissi", "Tuition Video", "Mangaf"),
    ("hishana tuition 31/08/2026", "Hishana", "Tuition", "Bahrain"),
    ("aswathy cg 29/08/2026", "Aswathy", "CG", "Kerala"),
    ("ligin | german | 3/9/26", "Ligin", "German", "Salmiya"),
    ("ligin teacher training 3/9/26", "Ligin", "Teacher Training", "Salmiya"),
    ("jincy | language training | 4/9/26", "Jincy", "Language Training", "Mangaf"),
    ("jincy safety 05/09/2026", "Jincy", "Safety Course", "Mangaf"),
    ("hishana | healthcare | 5/9/26", "Hishana", "Healthcare", "Bahrain"),
    ("hishana german 05/09/2026", "Hishana", "German", "Bahrain"),
    ("shabna commerce 05/09/2026", "Shabna", "Commerce", "Bahrain"),
    ("jincy | healthcare | call | 7/9/26", "Jincy", "Healthcare", "Mangaf"),
    ("arya call cg 07/09/2026", "Arya", "CG", "Salmiya"),
    ("renjith medical hiring 07/09/2026", "Renjith", "Medical Hiring", "Kerala"),
    ("renjith coordinator hiring 09/09/2026", "Renjith", "Coordinator Hiring", "Kerala"),
    ("anju hiring 11/09/2026", "Anju", "Hiring", "Kerala"),
    ("hishana phys tuition 12/09/2026", "Hishana", "Phys Tuition", "Bahrain"),
    ("roshni hiring gda 12/09/2026", "Roshni", "Hiring GDA", "Kerala"),
    ("roshni | healthcare | 14/9/26", "Roshni", "Healthcare", "Kerala"),
    ("roshni german 21/09/2026", "Roshni", "German", "Kerala"),
    ("jincy | digital marketing | 23/9/26", "Jincy", "Digital Marketing", "Mangaf"),
    ("vipin kerala | healthcare | 1/10/26", "Vipin", "Healthcare", "Kerala"),
    ("aswathy kuwait computer 02/10/2026", "Aswathy", "Computer", "Mangaf"),
    ("hishana tuition 03/10/2026", "Hishana", "Tuition", "Bahrain"),
    ("hishana tuition 05/10/2026", "Hishana", "Tuition", "Bahrain"),
    ("test - arya gda 24/08/2026", "Arya", "GDA", "Salmiya"),
    ("arya cg 08/10/2026", "Arya", "CG", "Salmiya"),
    ("roshni cg 10/10/2026", "Roshni", "CG", "Kerala"),
    ("arya | healthcare | 12/10/26", "Arya", "Healthcare", "Salmiya"),
    ("aswathy kuwait | healthcare | 12/10/26", "Aswathy", "Healthcare", "Mangaf"),
    ("shabna | healthcare | testimonials | 15/10/26", "Shabna", "Healthcare", "Bahrain"),
    ("nissi tuition 15/10/2026", "Nissi", "Tuition", "Mangaf"),
    ("aswathy tuition kuwait 15/10/2026", "Aswathy", "Tuition", "Mangaf"),
    ("awsathy cg 16/10/2026", "Aswathy", "CG", "Kerala"),
    ("awsathy cg kerala 16/10/2026", "Aswathy", "CG", "Kerala"),
    ("ajay dm 17/10/2026", "Ajay", "Digital Marketing", "Kerala"),
    ("vipin dca 20/10/2026", "Vipin", "DCA", "Kerala"),
    ("vipin cg 08/09/2026", "Vipin", "CG", "Kerala"),
    ("nissi hiring 09/09/2026", "Nissi", "Hiring", "Mangaf"),
    ("vipin cg", "Vipin", "CG", "Kerala"),
    ("shabna | healthcare 19 /2/26 engagement campaign", "Shabna", "Healthcare", "Bahrain"),
    ("shabna|computer | 19/2/26", "Shabna", "Computer", "Bahrain"),
    ("aswathy kuwait | boost video | 15/3/26", "Aswathy", "Boost Video", "Mangaf"),
    ("aswathy kuwait| testimonial healthcare | 2/4/26", "Aswathy", "Healthcare", "Mangaf"),
    ("shabna | healthcare | 1/6/26", "Shabna", "Healthcare", "Bahrain"),
    ("shabna | language training | 14/8/26", "Shabna", "Language Training", "Bahrain"),
    ("jincy healthcare 24/08/2026", "Jincy", "Healthcare", "Mangaf"),
    ("aswathy kerala | healthcare | 1/10/26", "Aswathy", "Healthcare", "Kerala"),
    ("aswathy cg kerala 16/10/2026", "Aswathy", "CG", "Kerala"),
    ("hishana cg call 17/10/2026", "Hishana", "CG", "Bahrain"),
    ("jincy cg 21/10/2026", "Jincy", "CG", "Mangaf"),
]

BRANCH_ORDER = ["Mangaf", "Salmiya", "Bahrain", "Kerala"]
STAFF_ORDER = {
    "Mangaf": ["Jincy", "Sethu", "Nissi", "Sushma", "Aswathy"],
    "Salmiya": ["Arya", "Ligin", "Aswathy"],
    "Bahrain": ["Hishana", "Anakha", "Seetha", "Shabna"],
    "Kerala": ["Anupama", "Vedhika", "Vipin", "Aswathy", "Roshni", "Shelbin", "Ajay", "Dani", "Renjith", "Anju", "Biju"],
}
MANUAL_FALLBACK_KWD_FACTOR = 0.308  # Previous organization setting; used only if API fails or manual mode is selected.

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_usd_kwd_rate():
    """Fetch the latest published USD->KWD reference rate; cache for 24 hours.

    Frankfurter's ECB-based feed does not cover every currency, including KWD,
    so use the free open.er-api.com latest-rates endpoint instead.
    """
    url = "https://open.er-api.com/v6/latest/USD"
    response = requests.get(url, timeout=8)
    response.raise_for_status()
    payload = response.json()
    if payload.get("result") != "success":
        raise ValueError("The exchange-rate provider did not return success.")
    rate = float(payload["rates"]["KWD"])
    rate_date = str(payload.get("time_last_update_utc", "")).strip()
    if rate <= 0 or not rate_date:
        raise ValueError("The API returned an invalid rate or missing update date.")
    return rate, rate_date

def normalize(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

def read_mapping_file(upload):
    if upload is None:
        return pd.DataFrame(DEFAULT_MAPPINGS, columns=["Campaign", "Staff", "Course", "Branch"])
    try:
        df = pd.read_excel(upload) if upload.name.lower().endswith((".xlsx", ".xls")) else pd.read_csv(upload)
        cols = {normalize(c): c for c in df.columns}
        needed = ["campaign", "staff", "course", "branch"]
        if not all(x in cols for x in needed):
            st.error("Mapping file must have columns: Campaign, Staff, Course, Branch.")
            return pd.DataFrame(DEFAULT_MAPPINGS, columns=["Campaign", "Staff", "Course", "Branch"])
        return df[[cols[x] for x in needed]].rename(columns={cols[x]: x.title() for x in needed}).fillna("")
    except Exception as e:
        st.error(f"Could not read mapping file: {e}")
        return pd.DataFrame(DEFAULT_MAPPINGS, columns=["Campaign", "Staff", "Course", "Branch"])

def infer_campaign(name, mappings):
    """Resolve campaign using exact/partial mappings, staff aliases, course clues and branch rules."""
    original_name = str(name or "")
    key = normalize(original_name)
    tokens = set(key.split())

    # Canonical staff-to-branch rules. Aswathy's branch depends on the course.
    staff_branch_rules = {
        "Jincy": "Mangaf", "Sethu": "Mangaf", "Nissi": "Mangaf", "Sushma": "Mangaf",
        "Arya": "Salmiya", "Ligin": "Salmiya",
        "Hishana": "Bahrain", "Anakha": "Bahrain", "Seetha": "Bahrain", "Shabna": "Bahrain",
        "Anupama": "Kerala", "Vedhika": "Kerala", "Vipin": "Kerala", "Roshni": "Kerala",
        "Shelbin": "Kerala", "Ajay": "Kerala", "Dani": "Kerala", "Renjith": "Kerala",
        "Anju": "Kerala", "Biju": "Kerala", "Aswathy": "",
    }
    staff_aliases = {
        "Aswathy": ["aswathy", "awsathy", "aswathi"],
        "Hishana": ["hishana", "hishna"],
        "Shabna": ["shabna", "shabana"],
        "Vipin": ["vipin", "vipin"],
        "Anupama": ["anupama"],
    }

    # Start with any exact mapping, but keep filling missing fields rather than returning early.
    staff = course = branch = ""
    exact = mappings[mappings["Campaign"].astype(str).map(normalize) == key]
    if not exact.empty:
        row = exact.iloc[0]
        staff = str(row.get("Staff", "") or "").strip()
        course = str(row.get("Course", "") or "").strip()
        branch = str(row.get("Branch", "") or "").strip()

    # Staff can appear anywhere in the campaign, including known spelling variants.
    hits = []
    for canonical in staff_branch_rules:
        aliases = staff_aliases.get(canonical, [canonical.lower()])
        if any(re.search(r"\b" + re.escape(normalize(alias)) + r"\b", key) for alias in aliases):
            hits.append(canonical)
    hits = list(dict.fromkeys(hits))
    if not staff and len(hits) == 1:
        staff = hits[0]

    # Identify a course from the whole campaign string. Longer/more-specific terms first.
    course_aliases = [
        (r"\bcaregiving\b|\bcaregiver\b", "Caregiving"),
        (r"\bpractical\s+video\b", "Practical Video"),
        (r"\bj\s*&\s*v\b|\bj\s+and\s+v\s+video\b|\bj\s+v\s+video\b", "J&V Video"),
        (r"\btestimonial\s+healthcare\b", "Healthcare"),
        (r"\bnursing\s+tutor\b", "Nursing Tutor"),
        (r"\bhospital\s+administration\b|\bhospital\s+admin\b", "Hospital Admin"),
        (r"\bteacher\s+training\b", "Teacher Training"),
        (r"\blanguage\s+training\b", "Language Training"),
        (r"\bdigital\s+marketing\b|\bdm\b", "Digital Marketing"),
        (r"\bsafety\s+course\b|\bsafety\b", "Safety Course"),
        (r"\bhealthcare\b|\bhealth\s+care\b", "Healthcare"),
        (r"\bcomputer\b", "Computer"), (r"\bgerman\b", "German"),
        (r"\btuition\b|\btution\b", "Tuition"), (r"\bielts\b", "IELTS"),
        (r"\bprometric\b", "Prometric"), (r"\bmontessori\b", "Montessori"),
        (r"\bphonics\b", "Phonics"), (r"\bautocad\b", "Autocad"),
        (r"\blogistics\b", "Logistics"), (r"\bnanny\s+course\b", "Nanny Course"),
        (r"\bhouse\s+keeping\b", "House Keeping"), (r"\bsummer\s+camp\b", "Summer Camp"),
        (r"\bmedical\s+hiring\b", "Medical Hiring"), (r"\bcoordinator\s+hiring\b", "Coordinator Hiring"),
        (r"\bhiring\b", "Hiring"), (r"\bcommerce\b", "Commerce"),
        (r"\bspa\b", "Spa"), (r"\bgda\b", "GDA"), (r"\bgna\b", "GNA"),
        (r"\bcg\b", "CG"), (r"\bdca\b", "DCA"), (r"\bpte\b", "PTE"),
        (r"\bham\b", "HAM"), (r"\bhr\b", "HR"), (r"\bphili(?:pi)?\b", "Philipi"),
        (r"\bboost\s+video\b", "Boost Video"), (r"\bcomputer\s+course\b", "Computer"),
    ]
    if not course:
        for pattern, label in course_aliases:
            if re.search(pattern, key):
                course = label
                break

    # Recognize an explicit branch in the campaign.
    explicit_branch = next((b for b in BRANCH_ORDER if re.search(r"\b" + re.escape(normalize(b)) + r"\b", key)), "")
    if not branch and explicit_branch:
        branch = explicit_branch

    # Use mapping evidence to infer missing fields from any two known fields when unique.
    m = mappings.copy().fillna("")
    for col in ["Staff", "Course", "Branch"]:
        m[col] = m[col].astype(str).str.strip()
    if staff and course and not branch:
        rows = m[(m.Staff.map(normalize) == normalize(staff)) & (m.Course.map(normalize) == normalize(course))]
        options = set(rows.Branch[rows.Branch != ""])
        if len(options) == 1:
            branch = next(iter(options))
    if staff and branch and not course:
        rows = m[(m.Staff.map(normalize) == normalize(staff)) & (m.Branch.map(normalize) == normalize(branch))]
        # Only infer a course if the campaign wording or historical match identifies one uniquely.
        campaign_rows = rows[rows.Campaign.astype(str).map(normalize).map(lambda x: any(t in key.split() for t in x.split() if len(t) > 3))]
        options = set(campaign_rows.Course[campaign_rows.Course != ""])
        if len(options) == 1:
            course = next(iter(options))
    if course and branch and not staff:
        rows = m[(m.Course.map(normalize) == normalize(course)) & (m.Branch.map(normalize) == normalize(branch))]
        options = set(rows.Staff[rows.Staff != ""])
        if len(options) == 1:
            staff = next(iter(options))

    # Staff-to-branch rules fill the branch after staff/course detection.
    if staff == "Aswathy":
        c = normalize(course)
        if "computer" in c or "tuition" in c or "boost video" in c:
            branch = branch or "Mangaf"
        elif "german" in c:
            branch = branch or "Salmiya"
        elif any(word in c.split() for word in ["healthcare", "cg"]):
            branch = branch or "Kerala"
        elif explicit_branch:
            branch = explicit_branch
    elif staff and not branch:
        branch = staff_branch_rules.get(staff, "")

    # Staff branch rules are authoritative for staff with one fixed branch.
    if staff in staff_branch_rules and staff != "Aswathy":
        branch = staff_branch_rules[staff]

    # Last chance: exact historical mapping by campaign similarity/known course+staff.
    if staff and course and not branch:
        rows = m[(m.Staff.map(normalize) == normalize(staff)) & (m.Course.map(normalize) == normalize(course))]
        options = set(rows.Branch[rows.Branch != ""])
        if len(options) == 1:
            branch = next(iter(options))

    if staff and course and branch:
        return staff, course, branch, ("Exact mapping" if not exact.empty else "Auto-inferred")
    return staff, course, branch, "Needs review"

def inject_premium_theme():
    """Apply Dreamztree's brighter, colorful premium dashboard theme."""
    st.markdown("""
    <style>
    @keyframes dt-fade-up {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes dt-gradient-drift {
      0%, 100% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
    }
    @keyframes dt-soft-glow {
      0%, 100% { box-shadow: 0 18px 50px rgba(0,0,0,.20), 0 0 0 rgba(139,92,246,0); }
      50% { box-shadow: 0 18px 50px rgba(0,0,0,.20), 0 0 28px rgba(139,92,246,.16); }
    }
    @keyframes dt-float {0%,100% {transform:translate3d(0,0,0) scale(1)} 50% {transform:translate3d(0,-28px,0) scale(1.08)}}
    @keyframes dt-border-flow {0% {background-position:0% 50%} 50% {background-position:100% 50%} 100% {background-position:0% 50%}}
    @keyframes dt-shimmer {0% {background-position:-200% center} 100% {background-position:200% center}}
    @keyframes dt-orbit {from {transform:rotate(0deg) translateX(18px) rotate(0deg)} to {transform:rotate(360deg) translateX(18px) rotate(-360deg)}}
    @keyframes dt-pulse {0%,100% {opacity:.28; transform:scale(.88)} 50% {opacity:1; transform:scale(1.22)}}
    @keyframes dt-particle-drift {
      0% { background-position: 0 0, 35px 70px, 90px 20px; transform: translate3d(0,0,0); }
      50% { background-position: 70px -55px, -25px 25px, 40px 95px; transform: translate3d(0,-8px,0); }
      100% { background-position: 140px -110px, -85px -20px, -10px 170px; transform: translate3d(0,0,0); }
    }
    @keyframes dt-chart-rise {from {opacity:0; transform:translateY(22px) scale(.985)} to {opacity:1; transform:translateY(0) scale(1)}}
    :root {
      --dt-ink: #f8faff; --dt-muted: #c0cce0; --dt-pink: #ff6ba8;
      --dt-purple: #a78bfa; --dt-blue: #60a5fa; --dt-cyan: #5eead4;
      --dt-orange: #ffbd69; --dt-green: #6ee7a8;
    }
    .stApp {
      background:
        radial-gradient(ellipse at 8% 2%, rgba(99,102,241,.28), transparent 32%),
        radial-gradient(ellipse at 92% 8%, rgba(236,72,153,.19), transparent 29%),
        radial-gradient(ellipse at 70% 88%, rgba(20,184,166,.13), transparent 32%),
        linear-gradient(135deg, #0b1020 0%, #11152b 48%, #101827 100%);
      color: var(--dt-ink);
      background-size: 180% 180%; animation: dt-border-flow 9s ease-in-out infinite;
    }
    /* Soft moving ambient light, kept behind all app controls. */
    [data-testid="stAppViewContainer"] {position:relative; isolation:isolate;}
    [data-testid="stAppViewContainer"]:before {
      content:""; position:fixed; z-index:-1; pointer-events:none; width:34rem; height:34rem;
      top:8%; left:-13rem; border-radius:50%; filter:blur(72px);
      background:radial-gradient(circle,rgba(124,58,237,.13),rgba(59,130,246,.06) 48%,transparent 72%);
      animation:dt-float 6s ease-in-out infinite;
    }
    [data-testid="stAppViewContainer"]:after {
      content:""; position:fixed; z-index:-1; pointer-events:none; inset:0;
      opacity:.34;
      background-image:
        radial-gradient(circle, rgba(167,139,250,.72) 0 1px, transparent 1.8px),
        radial-gradient(circle, rgba(96,165,250,.62) 0 1px, transparent 1.8px),
        radial-gradient(circle, rgba(94,234,212,.52) 0 1px, transparent 1.8px);
      background-size: 180px 180px, 230px 230px, 290px 290px;
      animation:dt-particle-drift 32s linear infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      [data-testid="stAppViewContainer"]:after { animation:none; }
    }
    [data-testid="stHeader"] {background: rgba(11,16,32,.72); backdrop-filter: blur(14px);}
    [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #171632 0%, #121a30 48%, #0d1c2c 100%);
      border-right: 1px solid rgba(167,139,250,.3);
    }
    [data-testid="stSidebar"] * {color: var(--dt-ink);}
    .block-container {max-width: 1480px; padding-top: 1.6rem; padding-bottom: 3rem; animation: dt-fade-up .65s ease both;}
    h1,h2,h3 {letter-spacing: -.035em; color: #fff;}
    h2 {text-shadow: 0 2px 24px rgba(96,165,250,.14);}
    p, label, [data-testid="stMarkdownContainer"] {color: var(--dt-ink);}
    [data-testid="stMetric"] {
      background: linear-gradient(135deg, rgba(99,102,241,.23), rgba(30,41,72,.84) 55%, rgba(14,165,233,.13));
      border: 1px solid rgba(129,140,248,.42); padding: 18px 20px; border-radius: 18px;
      box-shadow: 0 12px 30px rgba(0,0,0,.22), inset 0 1px rgba(255,255,255,.06);
      transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
      animation: dt-chart-rise .85s cubic-bezier(.2,.75,.25,1) both, dt-soft-glow 3.2s ease-in-out 1s infinite;
    }
    [data-testid="stMetric"]:nth-of-type(2) {animation-delay:.08s,.8s}
    [data-testid="stMetric"]:nth-of-type(3) {animation-delay:.16s,1.2s}
    [data-testid="stMetric"]:nth-of-type(4) {animation-delay:.24s,1.6s}
    [data-testid="stMetric"]:hover {transform: translateY(-4px) scale(1.01); border-color: rgba(94,234,212,.85); box-shadow: 0 16px 34px rgba(0,0,0,.28), 0 0 20px rgba(94,234,212,.12);}
    [data-testid="stMetricLabel"] {color: #c6d2ea !important;}
    [data-testid="stMetricValue"] {color: #fff !important; font-weight: 800;}
    [data-testid="stMetricDelta"] {font-weight: 700;}
    .hero {
      position: relative; overflow: hidden;
      background: linear-gradient(112deg, rgba(124,58,237,.38), rgba(37,99,235,.24) 48%, rgba(13,148,136,.25));
      border: 1px solid rgba(167,139,250,.48); border-radius: 24px; padding: 28px 30px; margin-bottom: 22px;
      background-size: 180% 180%; animation: dt-gradient-drift 5s ease-in-out infinite, dt-fade-up .9s ease both;
      box-shadow: 0 18px 50px rgba(0,0,0,.2), inset 0 1px rgba(255,255,255,.08);
    }
    @keyframes dt-sparkle-drift {
      0%,100% { transform:translate3d(0,0,0) rotate(0deg); opacity:.35; }
      50% { transform:translate3d(-18px,-24px,0) rotate(18deg); opacity:.95; }
    }
    @keyframes dt-hero-border-pulse {
      0%,100% { box-shadow:0 18px 50px rgba(0,0,0,.2), 0 0 0 rgba(96,165,250,0), inset 0 1px rgba(255,255,255,.08); }
      50% { box-shadow:0 18px 50px rgba(0,0,0,.2), 0 0 32px rgba(96,165,250,.3), 0 0 54px rgba(236,72,153,.14), inset 0 1px rgba(255,255,255,.12); }
    }
    .hero { animation:dt-gradient-drift 5s ease-in-out infinite, dt-fade-up .9s ease both, dt-hero-border-pulse 3.4s ease-in-out 1s infinite; }
    .hero:after { animation:dt-pulse 3.2s ease-in-out infinite; }
    [data-testid="stMetric"] { position:relative; overflow:hidden; }
    [data-testid="stMetric"]:after {
      content:""; position:absolute; top:-60%; left:-80%; width:55%; height:220%; pointer-events:none;
      background:linear-gradient(100deg,transparent,rgba(255,255,255,.16),transparent);
      transform:skewX(-18deg); animation:dt-shimmer 4.2s linear infinite;
    }
    [data-testid="stMetric"]:nth-of-type(2):after {animation-delay:.6s;}
    [data-testid="stMetric"]:nth-of-type(3):after {animation-delay:1.2s;}
    [data-testid="stMetric"]:nth-of-type(4):after {animation-delay:1.8s;}
    .hero:after {content: ""; position: absolute; width: 220px; height: 220px; right: -70px; top: -105px;
      border-radius: 50%; background: radial-gradient(circle, rgba(255,107,168,.35), transparent 70%); pointer-events: none;
      animation:dt-pulse 6s ease-in-out infinite;}
    .hero:before {content:""; position:absolute; width:170px; height:170px; right:18%; bottom:-125px; border-radius:50%;
      border:1px solid rgba(94,234,212,.2); box-shadow:0 0 42px rgba(96,165,250,.1); pointer-events:none;
      animation:dt-orbit 18s linear infinite;}
    .eyebrow {color: #77f3df; font-size: .76rem; font-weight: 900; text-transform: uppercase; letter-spacing: .16em;}
    .hero-title {font-size: clamp(1.7rem, 3vw, 2.45rem); line-height: 1.12; font-weight: 850; margin: .45rem 0 .6rem; color: #fff;
      background:linear-gradient(90deg,#fff 0%,#c4b5fd 24%,#7dd3fc 48%,#99f6e4 68%,#fff 100%);
      background-size:220% auto; -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
      animation:dt-shimmer 3.2s linear infinite;}
    .hero-copy,.section-note {color: #d2def2; font-size: .96rem;}
    div[data-testid="stTabs"] {border-radius: 14px; animation:dt-fade-up .65s ease both;}
    div[data-testid="stTabs"] button {border-radius: 11px; padding: 10px 15px; color: #d6def0; transition:background .25s ease, transform .25s ease, color .25s ease;}
    div[data-testid="stTabs"] button:hover {transform:translateY(-2px); background:rgba(96,165,250,.13);}
    div[data-testid="stTabs"] button[aria-selected="true"] {background: linear-gradient(90deg, rgba(124,58,237,.34), rgba(37,99,235,.27)); color: #8cf5e4;}
    div[data-testid="stTabs"] button[aria-selected="true"] p {color: #8cf5e4 !important; font-weight: 800;}
    [data-testid="stDataFrame"], [data-testid="stTable"] {border: 1px solid rgba(129,140,248,.3); border-radius: 14px; overflow: hidden;
      animation:dt-chart-rise .8s cubic-bezier(.2,.75,.25,1) both; transition:border-color .25s ease, box-shadow .25s ease;}
    [data-testid="stDataFrame"]:hover, [data-testid="stTable"]:hover {border-color:rgba(94,234,212,.55); box-shadow:0 10px 32px rgba(96,165,250,.08);}
    [data-testid="stFileUploader"] {background: linear-gradient(135deg, rgba(99,102,241,.13), rgba(20,184,166,.08)); background-size:180% 180%;
      border: 1px dashed rgba(129,140,248,.6); border-radius: 16px; padding: 8px; animation:dt-border-flow 4.5s ease infinite; transition:transform .25s ease, border-color .25s ease;}
    [data-testid="stFileUploader"]:hover {transform:translateY(-2px); border-color:rgba(94,234,212,.85);}
    [data-testid="stExpander"] {transition:border-color .25s ease, box-shadow .25s ease;}
    [data-testid="stExpander"]:hover {border-color:rgba(167,139,250,.6); box-shadow:0 8px 26px rgba(124,58,237,.08);}
    [data-testid="stExpander"] {background: rgba(26,34,61,.62); border: 1px solid rgba(129,140,248,.28); border-radius: 14px;}
    .stButton button, [data-testid="stDownloadButton"] button {
      border: 1px solid rgba(167,139,250,.48); border-radius: 11px; font-weight: 750;
      transition: transform .2s ease, filter .2s ease, box-shadow .2s ease; color: #fff;
      background: linear-gradient(100deg, #7c3aed, #2563eb 55%, #0891b2); background-size:180% 180%; animation:dt-border-flow 4s ease infinite;
    }
    .stButton button:hover, [data-testid="stDownloadButton"] button:hover {transform: translateY(-2px) scale(1.01); filter: brightness(1.14); border-color: #5eead4; color: #fff; box-shadow: 0 8px 24px rgba(96,165,250,.18);}
    .stButton button[kind="primary"], button[kind="primary"] {
      background: linear-gradient(100deg, #ec4899, #8b5cf6 52%, #3b82f6); color: #fff; border: 0;
      box-shadow: 0 8px 22px rgba(139,92,246,.24); font-weight: 850;
    }
    [data-testid="stAlert"] {border-radius: 13px; border: 1px solid rgba(255,255,255,.13);}
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stDateInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"], [data-testid="stMultiSelect"] div[data-baseweb="select"] {
      border-radius: 10px;
    }
    hr {border-color: rgba(167,139,250,.25);}
    a {color: #7dd3fc !important;}
    ::selection {background: rgba(236,72,153,.45); color: #fff;}
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important;}
    }
    @media (max-width: 700px) {
      .block-container {padding-top: 1rem;}
      .hero {padding: 22px 20px; border-radius: 18px;}
      [data-testid="stMetric"] {padding: 14px;}
    }
/* Global binary animation: CSS background is attached to the app root, not a single page card. */
    .stApp { position: relative; isolation: isolate; }
    .stApp::before {
      content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
      opacity: .035; background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMjAwIiBoZWlnaHQ9IjE1MCIgdmlld0JveD0iMCAwIDEyMDAgMTUwIj48ZyBmb250LWZhbWlseT0ibW9ub3NwYWNlIiBmb250LXNpemU9IjExIiBmb250LXdlaWdodD0iNjAwIiBsZXR0ZXItc3BhY2luZz0iMi40IiBmaWxsPSIjOWFhOWQ4IiBvcGFjaXR5PSIwLjcyIj48dGV4dCB4PSIwIiB5PSIyMiI+MDEwMDEwMTAgMTAxMTAxMDAgMDExMDEwMDEgMTEwMDEwMTAgMDAxMTAxMDEgMTAxMDAxMTAgMDEwMTExMDAgMTAxMDEwMDEgMDExMDAxMTAgMTEwMDEwMTAgMDAxMTAxMDEgMTAxMDAxMTAgMDEwMTExMDAgMTAxMDEwMDEgMDExMDAxMTA8L3RleHQ+PHRleHQgeD0iLTQwIiB5PSI1NyIgZmlsbD0iI2I3YTZmNSI+MTAxMTAxMDAgMDEwMDEwMTAgMTEwMDEwMTAgMDExMDEwMDEgMTAxMDAxMDEgMDEwMTEwMTAgMTEwMTAwMTAgMDExMDEwMTAgMDAxMTAxMDEgMTAxMDAxMTAgMDEwMTExMDAgMTAxMTAxMDAgMDEwMDEwMTAgMTEwMDEwMTAgMDExMDEwMDE8L3RleHQ+PHRleHQgeD0iMTAiIHk9IjkyIiBmaWxsPSIjNzdkOWQwIj4wMTEwMTAwMSAxMTAxMDAxMCAwMTAxMTAxMCAxMDExMDEwMCAwMTAwMTAxMCAxMTAwMTAxMCAxMDEwMDEwMSAwMTEwMTAxMCAxMTAwMTAxMCAwMDExMDEwMSAwMTEwMTAwMSAxMTAxMDAxMCAwMTAxMTAxMCAxMDExMDEwMDwvdGV4dD48dGV4dCB4PSItMjAiIHk9IjEyNyIgZmlsbD0iI2Q2OGViNyI+MTEwMDEwMTAgMDExMDEwMTAgMTAxMTAxMDAgMDEwMDEwMTAgMDExMDEwMDEgMTAxMDAxMDEgMTEwMTAwMTAgMDEwMTEwMTAgMTAxMTAxMDAgMDExMDEwMDEgMTEwMDEwMTAgMDExMDEwMTAgMTAxMTAxMDA8L3RleHQ+PC9nPjwvc3ZnPg==");
      background-repeat: repeat; background-size: 1200px 150px;
      animation: dt-global-binary-drift 70s linear infinite;
      will-change: background-position;
    }
    [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"],
    [data-testid="stMainBlockContainer"], .main { position: relative; z-index: 1; }
    [data-testid="stAppViewContainer"] { background: transparent; }
    [data-testid="stStatusWidget"], [data-testid="stToast"], [data-testid="stNotification"],
    [data-testid="stAlert"], .dt-game-toast { position: relative; z-index: 10000; }
    @keyframes dt-global-binary-drift {
      0% { background-position: 0 0; }
      50% { background-position: 90px 75px; }
      100% { background-position: 180px 150px; }
    }
    @media (prefers-reduced-motion: reduce) { .stApp::before { animation: none !important; } }

    .arcade-banner { margin: 1rem 0; padding: 1.4rem 1.6rem; border-radius: 22px; border: 1px solid rgba(232,121,249,.65); background: linear-gradient(120deg, rgba(91,33,182,.82), rgba(14,165,233,.68), rgba(236,72,153,.72)); background-size: 220% 220%; animation: arcade-gradient 5s ease infinite, arcade-pop .55s ease both; box-shadow: 0 0 28px rgba(168,85,247,.28); }
        .arcade-banner h2 { margin: .35rem 0; color: white; }
        .arcade-banner p { margin-bottom: 0; color: #f5f3ff; }
        .arcade-kicker { letter-spacing: .18em; font-size: .72rem; font-weight: 900; color: #fef08a; }
        @keyframes arcade-gradient { 0%,100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        @keyframes arcade-pop { from { opacity: 0; transform: translateY(16px) scale(.985); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @media (prefers-reduced-motion: reduce) { .arcade-banner { animation: none; } }
</style>""", unsafe_allow_html=True)


def load_campaign_report(upload, mappings):
    """Load and classify a Meta export using the same rules as the main report."""
    raw = pd.read_excel(upload)
    if raw.empty or len(raw.columns) < 3:
        raise ValueError("The Excel report is empty or does not contain the expected columns.")

    original_cols = list(raw.columns)
    normalized_cols = [normalize(c) for c in original_cols]

    def find_col(predicate, fallback):
        for i, c in enumerate(normalized_cols):
            if predicate(c):
                return original_cols[i]
        if fallback >= len(original_cols):
            raise ValueError("Could not identify Campaign, Results and Amount Spent columns.")
        return original_cols[fallback]

    campaign_col = find_col(lambda c: "campaign" in c, 0)
    result_col = find_col(lambda c: "result" in c and "initial" not in c, 1)
    spent_col = find_col(lambda c: "spent" in c or "amount" in c, 2)
    df = raw[[campaign_col, result_col, spent_col]].copy()
    df.columns = ["Campaign", "Results", "Spent"]
    df["Campaign"] = df["Campaign"].fillna("").astype(str)
    df["Results"] = pd.to_numeric(df["Results"], errors="coerce").fillna(0).astype(int)
    df["Spent"] = pd.to_numeric(df["Spent"], errors="coerce").fillna(0.0)
    # Match the main report's inclusion rule: exclude zero and awareness/reach-scale results.
    df = df[(df["Results"] > 0) & (df["Results"] <= 10000)].reset_index(drop=True)

    assignments = []
    for _, row in df.iterrows():
        staff, course, branch, status = infer_campaign(row["Campaign"], mappings)
        assignments.append({
            "Campaign": row["Campaign"],
            "Results": int(row["Results"]),
            "Spent": float(row["Spent"]),
            "Staff": staff,
            "Course": course,
            "Branch": branch,
            "Status": status,
        })
    return pd.DataFrame(assignments)


def summarize_campaign_performance(frame, exchange_rate):
    """Summaries include only campaigns with identifiable staff and branch."""
    if frame.empty:
        empty = pd.DataFrame(columns=["Campaign", "Results", "Spent", "Staff", "Course", "Branch", "Cost_KWD"])
        return empty, 0, 0.0, None

    valid = frame[
        frame["Staff"].astype(str).str.strip().ne("")
        & frame["Branch"].astype(str).str.strip().ne("")
    ].copy()
    valid["Course"] = valid["Course"].astype(str).str.strip().replace("", "Unclassified course")
    valid["Cost_KWD"] = valid["Spent"].astype(float) * exchange_rate
    if valid.empty:
        return valid, 0, 0.0, None
    top = valid.sort_values(["Results", "Spent"], ascending=[False, True]).iloc[0]
    return valid, int(valid["Results"].sum()), float(valid["Spent"].sum() * exchange_rate), top



def get_supabase_client():
    """Create or restore the Supabase client for this Streamlit session."""
    if "supabase_client" in st.session_state:
        client = st.session_state["supabase_client"]
        access_token = st.session_state.get("supabase_access_token")
        refresh_token = st.session_state.get("supabase_refresh_token")
        if access_token and refresh_token:
            try:
                client.auth.set_session(access_token, refresh_token)
            except Exception:
                # Keep the existing client; the login screen can request a fresh sign-in.
                pass
        return client

    # Render uses environment variables; Streamlit Cloud can still use secrets.toml.
    supabase_url = str(os.environ.get("SUPABASE_URL", "")).strip()
    publishable_key = str(os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")).strip()
    if not supabase_url or not publishable_key:
        try:
            config = st.secrets["supabase"]
            supabase_url = supabase_url or str(config["url"]).strip()
            publishable_key = publishable_key or str(config["publishable_key"]).strip()
        except Exception:
            pass

    if not supabase_url or not publishable_key:
        return None

    try:
        client = create_client(supabase_url, publishable_key)
        st.session_state["supabase_client"] = client
        access_token = st.session_state.get("supabase_access_token")
        refresh_token = st.session_state.get("supabase_refresh_token")
        if access_token and refresh_token:
            try:
                client.auth.set_session(access_token, refresh_token)
            except Exception:
                pass
        return client
    except Exception as exc:
        st.session_state["supabase_setup_error"] = str(exc)
        return None


def _show_login_header():
    st.markdown(
        """
        <style>
        @keyframes dt-logo-rise-away {
          0% { opacity: 1; transform: translateY(0) scale(1); }
          68% { opacity: 1; transform: translateY(-42px) scale(.98); }
          100% { opacity: 0; transform: translateY(-115px) scale(.94); }
        }
        @keyframes dt-login-panel-rise {
          0% { opacity: 0; transform: translateY(54px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes dt-login-shift {0%,100% {background-position:0% 50%;} 50% {background-position:100% 50%;}}
        @keyframes dt-login-glow {0%,100% {box-shadow:0 22px 60px rgba(0,0,0,.3),0 0 10px rgba(124,58,237,.08),inset 0 1px rgba(255,255,255,.08)} 50% {box-shadow:0 22px 60px rgba(0,0,0,.3),0 0 34px rgba(96,165,250,.2),inset 0 1px rgba(255,255,255,.08)}}
        @keyframes dt-login-orbit {from {transform:rotate(0deg) translateX(15px) rotate(0deg)} to {transform:rotate(360deg) translateX(15px) rotate(-360deg)}}
        @keyframes dt-ambient-drift {0%,100% {background-position:0% 0%,100% 0%,0% 50%;} 50% {background-position:18% 22%,82% 18%,100% 50%;}}
        @keyframes dt-card-shimmer {0% {transform:translateX(-130%) rotate(12deg); opacity:0;} 18% {opacity:.45;} 48% {opacity:0;} 100% {transform:translateX(240%) rotate(12deg); opacity:0;}}
        @keyframes dt-orb-float {0%,100% {transform:translate3d(0,0,0) scale(1);} 50% {transform:translate3d(0,-16px,0) scale(1.06);}}
        @keyframes dt-button-breathe {0%,100% {box-shadow:0 7px 20px rgba(124,58,237,.2);} 50% {box-shadow:0 9px 28px rgba(59,130,246,.34),0 0 16px rgba(94,234,212,.13);}}
        @keyframes dt-tab-enter {from {opacity:0; transform:translateY(12px);} to {opacity:1; transform:translateY(0);}}
        [data-testid="stAppViewContainer"] {
          background: radial-gradient(circle at 12% 5%, rgba(124,58,237,.36), transparent 32%),
            radial-gradient(circle at 90% 12%, rgba(236,72,153,.22), transparent 28%),
            linear-gradient(135deg, #0b1020, #11152b 55%, #101827);
          background-size: 140% 140%, 140% 140%, 220% 220%;
          animation: dt-ambient-drift 24s ease-in-out infinite;
        }
        [data-testid="stAppViewContainer"]::after {
          content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
          background: radial-gradient(circle at 17% 72%, rgba(94,234,212,.075), transparent 18%),
                      radial-gradient(circle at 82% 66%, rgba(168,85,247,.09), transparent 21%);
          animation: dt-orb-float 12s ease-in-out infinite;
        }
        [data-testid="stHeader"] {background: transparent;}
        /* Limit the login page width without changing the dashboard after login. */
        .block-container:has(.login-panel) {
          max-width: 760px !important;
          padding-top: 1rem !important;
          padding-bottom: 1.5rem !important;
        }
        .dt-login-logo {
          display:flex; flex-direction:column; align-items:center; justify-content:center;
          gap:.25rem; margin: 48px auto 1rem; min-height:112px; text-align:center;
          animation: dt-logo-rise-away 2.8s cubic-bezier(.4,0,.2,1) .15s both;
        }
        .dt-login-logo-image {
          display:block; width:116px; height:100px; object-fit:contain;
          filter: drop-shadow(0 0 18px rgba(96,165,250,.18));
        }
        .login-panel {
          max-width: 620px; width:100%; box-sizing:border-box;
          margin: -12px auto .8rem auto; padding: 1.6rem 1.8rem;
          border: 1px solid rgba(167,139,250,.55); border-radius: 22px;
          background: linear-gradient(125deg, rgba(124,58,237,.32), rgba(37,99,235,.2) 55%, rgba(13,148,136,.2));
          background-size: 180% 180%; position:relative; overflow:hidden;
          opacity:0; animation: dt-login-panel-rise 1.05s cubic-bezier(.2,.75,.25,1) 1.05s forwards,
          dt-login-shift 14s ease-in-out 2.4s infinite, dt-login-glow 7s ease-in-out 2.4s infinite;
          box-shadow: 0 22px 60px rgba(0,0,0,.3), inset 0 1px rgba(255,255,255,.08);
        }
        .login-panel:after {content:""; position:absolute; width:145px; height:145px; right:9%; bottom:-112px; border-radius:50%;
          border:1px solid rgba(94,234,212,.3); box-shadow:0 0 28px rgba(96,165,250,.13); pointer-events:none; animation:dt-login-orbit 16s linear infinite;}
        .login-panel:before {content:""; position:absolute; top:-45%; left:0; width:34%; height:190%;
          background:linear-gradient(90deg,transparent,rgba(255,255,255,.085),rgba(94,234,212,.09),transparent);
          transform:translateX(-130%) rotate(12deg); pointer-events:none; animation:dt-card-shimmer 9s ease-in-out 2s infinite;}
        .login-panel > * {position:relative; z-index:1;}
        /* Gentle hover feedback keeps the page lively without interfering with authentication. */
        [data-testid="stFormSubmitButton"] button, [data-testid="stForm"] button[kind="primary"] {
          border:1px solid rgba(167,139,250,.28) !important; border-radius:11px !important;
          background:linear-gradient(105deg,#7c3aed,#3b82f6 58%,#0d9488) !important;
          background-size:180% 180% !important; color:#fff !important; font-weight:750 !important;
          transition:transform .22s ease, filter .22s ease, box-shadow .22s ease !important;
          animation:dt-button-breathe 5s ease-in-out 2s infinite;
        }
        [data-testid="stFormSubmitButton"] button:hover, [data-testid="stForm"] button[kind="primary"]:hover {
          transform:translateY(-2px); filter:brightness(1.12); box-shadow:0 12px 28px rgba(124,58,237,.28) !important;
        }
        [data-testid="stFormSubmitButton"] button:active {transform:translateY(0) scale(.99);}
        [data-testid="stTabs"] [data-baseweb="tab"] {transition:color .2s ease, background .2s ease;}
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {color:#5eead4;}
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {transition:border-color .2s ease, box-shadow .2s ease, background .2s ease;}
        [data-testid="stTextInput"] input:focus {background:rgba(30,41,59,.92);}
        /* Keep tabs and forms centered and compact, and bring them into view after the logo. */
        div[data-testid="stTabs"] {
          max-width:620px; width:100%; margin:0 auto !important;
          opacity:0; animation:dt-login-panel-rise 1.0s cubic-bezier(.2,.75,.25,1) 1.25s forwards;
        }
        [data-testid="stForm"] {
          max-width:620px; margin-left:auto; margin-right:auto;
          opacity:0; animation:dt-login-panel-rise 1.0s cubic-bezier(.2,.75,.25,1) 1.4s forwards;
        }
        [data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
          box-shadow:0 0 0 1px rgba(94,234,212,.72),0 0 20px rgba(96,165,250,.2);
          border-color:rgba(94,234,212,.8) !important;
        }
        @keyframes dt-field-arrive {from {transform:translateY(5px);opacity:.72;} to {transform:translateY(0);opacity:1;}}
        @keyframes dt-login-error-shake {0%,100% {transform:translateX(0)} 25% {transform:translateX(-4px)} 50% {transform:translateX(4px)} 75% {transform:translateX(-2px)}}
        @keyframes dt-auth-pulse {0%,100% {filter:brightness(1);box-shadow:0 7px 20px rgba(124,58,237,.22)} 50% {filter:brightness(1.12);box-shadow:0 0 30px rgba(94,234,212,.24),0 9px 28px rgba(59,130,246,.34)}}
        [data-testid="stTextInput"] input:focus {animation:dt-field-arrive .22s ease-out;}
        [data-testid="stTextInput"]:focus-within label {color:#5eead4 !important;transition:color .2s ease;}
        [data-testid="stFormSubmitButton"] button:focus-visible {outline:2px solid #5eead4 !important;outline-offset:3px;}
        [data-testid="stFormSubmitButton"] button:disabled {opacity:.8;cursor:wait;}
        [data-testid="stAlert"] {animation:dt-login-panel-rise .28s ease-out both;}
        .login-kicker {letter-spacing: .18em; text-transform: uppercase; color: #77f3df; font-size: .75rem; font-weight: 900;}
        .login-panel h1 {color: #fff; text-shadow: 0 4px 25px rgba(96,165,250,.18); font-size:clamp(1.7rem,3vw,2.25rem); line-height:1.12;}
        .login-panel p {color: #d6def0;}
        @media (max-width:700px) {
          .block-container:has(.login-panel) {padding-left:1rem !important;padding-right:1rem !important;}
          .login-panel {padding:1.3rem 1.2rem; margin-top:-8px;}
        }
        @media (prefers-reduced-motion: reduce) {
          .dt-login-logo,.login-panel,div[data-testid="stTabs"],[data-testid="stForm"],[data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"]::after,
          [data-testid="stFormSubmitButton"] button,.login-panel:before,.login-panel:after,
          [data-testid="stTextInput"] input:focus,[data-testid="stAlert"] {animation:none !important; opacity:1 !important; transform:none !important;}
        }
        /* Safety fallback: never leave login content invisible if animation timing is interrupted. */
        @media (max-width:700px) {
          .dt-login-logo {min-height:90px; margin-bottom:.35rem;}
          .dt-login-logo-image {width:96px; height:82px;}
          .login-panel {max-width:100%;}
          div[data-testid="stTabs"],[data-testid="stForm"] {max-width:100%;}
        }
        /* Stronger, browser-side interactions: these work even inside st.form. */
        [data-testid="stTextInput"] { transition: transform .22s ease, filter .22s ease; }
        [data-testid="stTextInput"]:focus-within { transform: translateY(-2px); filter: drop-shadow(0 0 10px rgba(94,234,212,.13)); }
        [data-testid="stTextInput"] input {
          border: 1px solid rgba(148,163,184,.38) !important;
          border-radius: 12px !important;
          background: rgba(10,16,32,.68) !important;
          transition: border-color .25s ease, box-shadow .25s ease, background .25s ease, transform .25s ease !important;
        }
        [data-testid="stTextInput"] input:hover { border-color: rgba(167,139,250,.8) !important; }
        [data-testid="stTextInput"] input:focus {
          border-color: #5eead4 !important;
          background: rgba(18,29,48,.96) !important;
          box-shadow: 0 0 0 1px rgba(94,234,212,.45), 0 0 0 5px rgba(59,130,246,.10), 0 0 24px rgba(94,234,212,.18) !important;
          transform: translateY(-1px);
        }
        [data-testid="stForm"] {
          border: 1px solid rgba(167,139,250,.28) !important;
          border-radius: 18px !important;
          padding: 1.25rem !important;
          background: rgba(12,18,35,.56) !important;
          backdrop-filter: blur(14px);
          box-shadow: 0 18px 48px rgba(0,0,0,.18);
        }
        [data-testid="stFormSubmitButton"] button {
          min-height: 48px !important;
          background: linear-gradient(110deg,#7c3aed,#3b82f6,#0d9488,#7c3aed) !important;
          background-size: 260% 260% !important;
          animation: dt-login-shift 5s ease-in-out infinite, dt-button-breathe 3.5s ease-in-out infinite !important;
          box-shadow: 0 8px 24px rgba(124,58,237,.24) !important;
        }
        [data-testid="stFormSubmitButton"] button:hover {
          transform: translateY(-2px) scale(1.01) !important;
          filter: brightness(1.13) saturate(1.12) !important;
          box-shadow: 0 12px 32px rgba(59,130,246,.32), 0 0 18px rgba(94,234,212,.18) !important;
        }
        [data-testid="stFormSubmitButton"] button:active { transform: scale(.985) !important; }
        [data-testid="stTabs"] button[role="tab"] { transition: color .2s ease, background .2s ease, box-shadow .2s ease; }
        [data-testid="stTabs"] button[role="tab"]:hover { color:#5eead4 !important; }
        @media (prefers-reduced-motion: reduce) {
          [data-testid="stTextInput"], [data-testid="stTextInput"] input,
          [data-testid="stFormSubmitButton"] button { animation:none !important; transition:none !important; }
        }

        /* Full-screen animated space + mountains, shown only while the login header is rendered. */
        #dt-login-universe {
          position:fixed; inset:0; overflow:hidden; pointer-events:none;
          z-index:0; isolation:isolate;
          background:linear-gradient(180deg,rgba(13,10,39,.18) 0%,rgba(20,14,57,.08) 48%,rgba(8,16,34,.42) 100%);
        }
        #dt-login-universe .dt-stars {
          position:absolute; inset:-15%;
          background-image:
            radial-gradient(circle,rgba(255,255,255,.95) 0 1px,transparent 1.7px),
            radial-gradient(circle,rgba(167,139,250,.9) 0 1.2px,transparent 2px),
            radial-gradient(circle,rgba(125,211,252,.75) 0 .8px,transparent 1.7px);
          background-size:113px 127px,179px 193px,241px 227px;
          background-position:0 0,47px 31px,83px 109px;
          animation:dt-space-stars 48s linear infinite,dt-star-twinkle 4.8s ease-in-out infinite alternate;
          opacity:.72;
        }
        @keyframes dt-space-stars {
          from {background-position:0 0,47px 31px,83px 109px;transform:translate3d(0,0,0)}
          to {background-position:90px 170px,-110px 120px,150px -130px;transform:translate3d(-1.5%,1%,0)}
        }
        @keyframes dt-star-twinkle {0%{opacity:.42}45%{opacity:.9}100%{opacity:.58}}
        #dt-login-universe .dt-mountain {
          position:absolute; left:-8%; width:116%; bottom:-2px;
          transform-origin:50% 100%; will-change:transform;
        }
        #dt-login-universe .dt-mountain-back {
          height:48%; opacity:.38;
          background:linear-gradient(155deg,#6d3db2,#34226f 68%,#251957);
          clip-path:polygon(0 78%,12% 42%,23% 72%,37% 28%,49% 65%,62% 18%,74% 62%,87% 34%,100% 73%,100% 100%,0 100%);
          animation:none !important;
        }
        #dt-login-universe .dt-mountain-mid {
          height:36%; opacity:.53;
          background:linear-gradient(160deg,#503092,#251b61 70%);
          clip-path:polygon(0 74%,14% 28%,26% 67%,40% 18%,54% 72%,68% 31%,82% 68%,93% 38%,100% 62%,100% 100%,0 100%);
          animation:none !important;
        }
        #dt-login-universe .dt-mountain-front {
          height:25%; opacity:.72;
          background:linear-gradient(180deg,#2e225f,#151a39);
          clip-path:polygon(0 55%,12% 32%,24% 64%,38% 24%,53% 66%,68% 18%,82% 56%,93% 31%,100% 50%,100% 100%,0 100%);
          animation:none !important;
        }
        @keyframes dt-mountain-drift-back {from{transform:translateX(-1.4%)}to{transform:translateX(1.4%)}}
        @keyframes dt-mountain-drift-mid {from{transform:translateX(1.8%)}to{transform:translateX(-1.8%)}}
        @keyframes dt-mountain-drift-front {from{transform:translateX(-.9%)}to{transform:translateX(.9%)}}
        /* Small animated spacecraft gliding through the star field. */
        #dt-login-universe .dt-spaceship {
          position:absolute; top:18%; left:-90px; width:64px; height:30px;
          opacity:0; transform:translate3d(0,0,0) rotate(-8deg);
          filter:drop-shadow(0 0 9px rgba(125,211,252,.65));
          animation:dt-spaceship-flight 90s ease-in-out 3s infinite;
          will-change:transform,opacity;
        }
        #dt-login-universe .dt-spaceship::before {
          content:""; position:absolute; left:12px; top:6px; width:36px; height:17px;
          border-radius:55% 45% 48% 52%;
          background:linear-gradient(180deg,#f8fafc 0%,#cbd5e1 48%,#64748b 100%);
          border:1px solid rgba(191,219,254,.9);
          box-shadow:inset 0 -3px 0 rgba(51,65,85,.45),0 0 12px rgba(125,211,252,.28);
          clip-path:polygon(0 50%,18% 12%,76% 0,100% 50%,76% 100%,18% 88%);
        }
        #dt-login-universe .dt-spaceship::after {
          content:""; position:absolute; left:25px; top:9px; width:13px; height:8px;
          border-radius:50%; background:linear-gradient(120deg,#67e8f9,#2563eb);
          border:1px solid rgba(224,242,254,.85);
          box-shadow:-17px 4px 0 -2px #64748b,17px 4px 0 -2px #64748b;
        }
        /* Detached ship panels and sparks appear only during the rare crash window. */
        #dt-login-universe .dt-ship-debris,
        #dt-login-universe .dt-sat-debris {
          position:absolute; width:7px; height:4px; opacity:0; pointer-events:none;
          background:linear-gradient(135deg,#f8fafc,#64748b); border:1px solid #cbd5e1;
          box-shadow:0 0 7px rgba(251,146,60,.9); border-radius:1px;
        }
        #dt-login-universe .dt-ship-debris {top:18%; left:74%; animation:dt-ship-debris-flight 90s ease-in-out 3s infinite;}
        #dt-login-universe .dt-ship-debris.d2 {width:5px;height:5px;animation-delay:3s;}
        #dt-login-universe .dt-ship-debris.d3 {width:3px;height:3px;background:#fb923c;box-shadow:0 0 9px #fb923c;animation:dt-ship-sparks 90s ease-in-out 3s infinite;}
        #dt-login-universe .dt-ship-debris.d4 {width:10px;height:3px;animation:dt-ship-debris-flight 90s ease-in-out 3s infinite;}
        @keyframes dt-ship-debris-flight {
          0%,74% {opacity:0;transform:translate(0,0) rotate(0)}
          76% {opacity:1;transform:translate(2vw,2vh) rotate(70deg)}
          82% {opacity:.95;transform:translate(5vw,11vh) rotate(230deg)}
          89% {opacity:0;transform:translate(9vw,24vh) rotate(520deg)}
          100% {opacity:0;transform:translate(9vw,24vh) rotate(520deg)}
        }
        @keyframes dt-ship-sparks {
          0%,74% {opacity:0;transform:translate(0,0) scale(.3)}
          76% {opacity:1;transform:translate(1vw,1vh) scale(1.8)}
          79% {opacity:.9;transform:translate(4vw,5vh) scale(.8)}
          83%,100% {opacity:0;transform:translate(7vw,12vh) scale(.1)}
        }
        #dt-login-universe .dt-sat-debris {top:24%; left:77%; width:8px;height:5px;animation:dt-sat-debris-flight 120s linear 2s infinite;}
        #dt-login-universe .dt-sat-debris.panel {width:12px;height:5px;background:repeating-linear-gradient(90deg,#2563eb 0 2px,#93c5fd 2px 3px);}
        #dt-login-universe .dt-sat-debris.spark {width:3px;height:3px;border:0;background:#fb923c;box-shadow:0 0 8px #fb923c;animation-name:dt-sat-sparks;}
        @keyframes dt-sat-debris-flight {
          0%,77% {opacity:0;transform:translate(0,0) rotate(0)}
          80% {opacity:1;transform:translate(2vw,2vh) rotate(80deg)}
          86% {opacity:.85;transform:translate(6vw,10vh) rotate(300deg)}
          93% {opacity:0;transform:translate(11vw,21vh) rotate(600deg)}
          100% {opacity:0;transform:translate(11vw,21vh) rotate(600deg)}
        }
        @keyframes dt-sat-sparks {
          0%,77% {opacity:0;transform:translate(0,0) scale(.2)}
          80% {opacity:1;transform:translate(2vw,2vh) scale(1.7)}
          84% {opacity:.7;transform:translate(5vw,6vh) scale(.7)}
          88%,100% {opacity:0;transform:translate(8vw,11vh) scale(.1)}
        }

        /* When the user starts entering login details, trigger a one-time 10-second space fly-by. */
        body:has(input:focus) #dt-login-universe .dt-spaceship {
          animation:dt-login-focus-flight 10s ease-in-out 1 both !important;
        }
        body:has(input:focus) #dt-login-universe .dt-satellite {
          animation:dt-login-focus-satellite 10s ease-in-out 1 both !important;
        }
        body:has(input:focus) #dt-login-universe .dt-stars {
          animation:dt-login-focus-stars 10s ease-in-out 1 both !important;
        }
        @keyframes dt-login-focus-flight {
          0% {opacity:0; transform:translate3d(-8vw,0,0) rotate(-12deg) scale(.72)}
          12% {opacity:1; transform:translate3d(8vw,-2vh,0) rotate(0) scale(.95)}
          38% {opacity:1; transform:translate3d(42vw,2vh,0) rotate(5deg) scale(1.08)}
          62% {opacity:1; transform:translate3d(68vw,-1vh,0) rotate(-5deg) scale(1)}
          82% {opacity:1; transform:translate3d(88vw,3vh,0) rotate(12deg) scale(.9)}
          100% {opacity:0; transform:translate3d(108vw,8vh,0) rotate(22deg) scale(.7)}
        }
        @keyframes dt-login-focus-satellite {
          0% {opacity:0; transform:translate3d(-5vw,0,0) rotate(0)}
          15% {opacity:.95}
          50% {opacity:.95; transform:translate3d(45vw,5vh,0) rotate(140deg)}
          82% {opacity:.9; transform:translate3d(85vw,-2vh,0) rotate(260deg)}
          100% {opacity:0; transform:translate3d(110vw,4vh,0) rotate(360deg)}
        }
        @keyframes dt-login-focus-stars {
          0% {opacity:.72; background-position:0 0,47px 31px,83px 109px}
          50% {opacity:1; background-position:45px 85px,-55px 60px,75px -65px}
          100% {opacity:.72; background-position:90px 170px,-110px 120px,150px -130px}
        }

        @keyframes dt-spaceship-flight {
          /* Cruise calmly, then occasionally malfunction and tumble out of the sky. */
          0%,3% {opacity:0; transform:translate3d(-4vw,3vh,0) rotate(-8deg) scale(.72); filter:drop-shadow(0 0 7px rgba(125,211,252,.35))}
          5% {opacity:.95}
          18% {opacity:1; transform:translate3d(22vw,-1vh,0) rotate(-3deg) scale(.9)}
          34% {opacity:1; transform:translate3d(43vw,2vh,0) rotate(2deg) scale(1)}
          52% {opacity:1; transform:translate3d(66vw,-1vh,0) rotate(-4deg) scale(1.02); filter:drop-shadow(0 0 12px rgba(125,211,252,.75))}
          68% {opacity:1; transform:translate3d(87vw,2vh,0) rotate(2deg) scale(.96)}
          74% {opacity:1; transform:translate3d(91vw,3vh,0) rotate(12deg) scale(1); filter:drop-shadow(0 0 12px rgba(125,211,252,.75))}
          76% {opacity:1; transform:translate3d(92vw,5vh,0) rotate(-18deg) scale(1.02); filter:drop-shadow(0 0 18px rgba(251,146,60,.95))}
          80% {opacity:.95; transform:translate3d(94vw,18vh,0) rotate(58deg) scale(.96); filter:drop-shadow(0 0 20px rgba(249,115,22,.9))}
          85% {opacity:.72; transform:translate3d(97vw,48vh,0) rotate(155deg) scale(.78); filter:drop-shadow(0 0 14px rgba(249,115,22,.6))}
          89% {opacity:0; transform:translate3d(101vw,82vh,0) rotate(250deg) scale(.55); filter:drop-shadow(0 0 0 transparent)}
          90%,100% {opacity:0; transform:translate3d(112vw,2vh,0) rotate(5deg) scale(.82)}
        }
        #dt-login-universe .dt-satellite {
          position:absolute; top:24%; left:-70px; width:31px; height:13px;
          animation:dt-satellite-orbit 120s linear 2s infinite;
          filter:drop-shadow(0 0 7px rgba(125,211,252,.5)); opacity:.9;
        }
        #dt-login-universe .dt-satellite::before {
          content:""; position:absolute; left:11px; top:2px; width:10px; height:9px;
          background:linear-gradient(135deg,#f8fafc,#94a3b8); border:1px solid #c4b5fd; border-radius:2px;
        }
        #dt-login-universe .dt-satellite::after {
          content:""; position:absolute; left:0; top:1px; width:8px; height:11px;
          background:repeating-linear-gradient(90deg,#2563eb 0 2px,#93c5fd 2px 3px);
          box-shadow:23px 0 0 #2563eb,23px 0 0 1px #93c5fd;
        }
        @keyframes dt-satellite-orbit {
          /* Slow orbital pass, a brief wobble, then a separate tumbling re-entry. */
          0%,4% {opacity:0; transform:translate3d(-5vw,0,0) rotate(12deg)}
          7% {opacity:.9; transform:translate3d(3vw,1vh,0) rotate(12deg)}
          24% {opacity:.9; transform:translate3d(28vw,5vh,0) rotate(4deg)}
          42% {opacity:.9; transform:translate3d(48vw,-2vh,0) rotate(-8deg)}
          60% {opacity:.9; transform:translate3d(70vw,1vh,0) rotate(4deg)}
          74% {opacity:.9; transform:translate3d(86vw,-1vh,0) rotate(-8deg)}
          78% {opacity:1; transform:translate3d(90vw,0,0) rotate(18deg)}
          80% {opacity:1; transform:translate3d(92vw,3vh,0) rotate(-28deg); filter:drop-shadow(0 0 12px rgba(251,146,60,.95))}
          84% {opacity:.9; transform:translate3d(95vw,16vh,0) rotate(55deg)}
          89% {opacity:.68; transform:translate3d(99vw,44vh,0) rotate(150deg); filter:drop-shadow(0 0 9px rgba(249,115,22,.7))}
          93% {opacity:0; transform:translate3d(103vw,82vh,0) rotate(270deg); filter:drop-shadow(0 0 0 transparent)}
          94%,100% {opacity:0; transform:translate3d(115vw,0,0) rotate(360deg)}
        }
        /* Keep every Streamlit control above the decorative background. */
        [data-testid="stAppViewContainer"] {position:relative;isolation:isolate;}
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stHeader"],
        [data-testid="stAppViewContainer"] .block-container {
          position:relative; z-index:2;
        }
        #dt-login-universe {z-index:0;}
        @media (prefers-reduced-motion: reduce) {
          #dt-login-universe *,#dt-login-universe *::before,#dt-login-universe *::after {animation:none !important;}
        }
        /* Safe escape effect: animate the login content container as one unit.
           The fixed universe and mountain layers are never transformed. */
        @keyframes dt-login-escape-20 {
          0% {transform:translate3d(0,0,0) rotate(0deg)}
          8% {transform:translate3d(5vw,-3vh,0) rotate(.7deg)}
          17% {transform:translate3d(-6vw,4vh,0) rotate(-.8deg)}
          27% {transform:translate3d(7vw,2vh,0) rotate(.8deg)}
          38% {transform:translate3d(-5vw,-4vh,0) rotate(-.7deg)}
          50% {transform:translate3d(6vw,5vh,0) rotate(.8deg)}
          62% {transform:translate3d(-7vw,-2vh,0) rotate(-.8deg)}
          74% {transform:translate3d(5vw,3vh,0) rotate(.6deg)}
          87% {transform:translate3d(-4vw,-3vh,0) rotate(-.5deg)}
          100% {transform:translate3d(0,0,0) rotate(0deg)}
        }
        @keyframes dt-ship-escape-20 {
          0% {transform:translate3d(0,0,0) rotate(0deg)}
          18% {transform:translate3d(-18vw,9vh,0) rotate(-35deg)}
          38% {transform:translate3d(26vw,-10vh,0) rotate(65deg)}
          58% {transform:translate3d(-30vw,14vh,0) rotate(-100deg)}
          78% {transform:translate3d(34vw,6vh,0) rotate(180deg)}
          100% {transform:translate3d(0,0,0) rotate(360deg)}
        }
        @keyframes dt-satellite-escape-20 {
          0% {transform:translate3d(0,0,0) rotate(0deg)}
          20% {transform:translate3d(20vw,-10vh,0) rotate(55deg)}
          40% {transform:translate3d(-26vw,12vh,0) rotate(-90deg)}
          62% {transform:translate3d(32vw,8vh,0) rotate(150deg)}
          82% {transform:translate3d(-18vw,-12vh,0) rotate(260deg)}
          100% {transform:translate3d(0,0,0) rotate(360deg)}
        }
        /* Keep content in normal flow and visible by default. */
        .dt-login-logo, .login-panel, div[data-testid="stTabs"], [data-testid="stForm"] {
          visibility:visible !important; opacity:1;
        }
        /* Trigger when the pointer reaches the login area or the user focuses a field.
           Move the page's login content as a single unit; never move the mountain layers. */
        body:has(.login-panel:hover, div[data-testid="stTabs"]:hover, [data-testid="stForm"]:hover, input:hover, input:focus, [data-testid="stFormSubmitButton"] button:hover) [data-testid="stAppViewContainer"] .block-container {
          animation:dt-login-escape-20 20s ease-in-out 1 both !important;
          will-change:transform;
        }
        body:has(.login-panel:hover, div[data-testid="stTabs"]:hover, [data-testid="stForm"]:hover, input:hover, input:focus, [data-testid="stFormSubmitButton"] button:hover) #dt-login-universe .dt-spaceship {
          animation:dt-ship-escape-20 20s ease-in-out 1 both !important;
        }
        body:has(.login-panel:hover, div[data-testid="stTabs"]:hover, [data-testid="stForm"]:hover, input:hover, input:focus, [data-testid="stFormSubmitButton"] button:hover) #dt-login-universe .dt-satellite {
          animation:dt-satellite-escape-20 20s ease-in-out 1 both !important;
        }
        @media (prefers-reduced-motion: reduce) {
          body:has(.login-panel:hover, div[data-testid="stTabs"]:hover, [data-testid="stForm"]:hover, input:hover, input:focus) [data-testid="stAppViewContainer"] .block-container,
          body:has(.login-panel:hover, div[data-testid="stTabs"]:hover, [data-testid="stForm"]:hover, input:hover, input:focus) #dt-login-universe .dt-spaceship,
          body:has(.login-panel:hover, div[data-testid="stTabs"]:hover, [data-testid="stForm"]:hover, input:hover, input:focus) #dt-login-universe .dt-satellite {animation:none !important;}
        }
        </style>
        <div id="dt-login-universe" aria-hidden="true">
          <div class="dt-stars"></div>
          <div class="dt-satellite"></div>
          <div class="dt-sat-debris panel"></div><div class="dt-sat-debris"></div><div class="dt-sat-debris spark"></div>
          <div class="dt-spaceship"></div>
          <div class="dt-ship-debris d1"></div><div class="dt-ship-debris d2"></div><div class="dt-ship-debris d3"></div><div class="dt-ship-debris d4"></div>
          <div class="dt-mountain dt-mountain-back"></div>
          <div class="dt-mountain dt-mountain-mid"></div>
          <div class="dt-mountain dt-mountain-front"></div>
        </div>
        <div class="dt-login-logo">
          <img class="dt-login-logo-image" alt="Dreamztree logo" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABT4AAAW3CAYAAABpEW6xAAAgAElEQVR4nOzdyXLbRhiFUSnl939lZuHIkWgOGBrd/3BOlXfJIgSiUF9uAx8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0MntdvsXjqmbVHamOtwAAAAASUVORK5CYII=" />
        </div>
        <div class="login-panel">
          <div class="login-kicker">Dreamztree · Marketing Intelligence</div>
          <h1>Meta Leads Command Center</h1>
          <p>Sign in or create an account to access campaign performance and lead reports.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def require_login():
    """Use Supabase Auth for colleague registration and sign-in.

    Optional legacy admin credentials in [auth.users] remain supported so the
    existing administrator can still sign in during the transition.
    """
    if st.session_state.get("authenticated"):
        return

    client = get_supabase_client()
    if client is None:
        st.title("Dreamztree Meta Report")
        st.error("Supabase authentication is not configured yet.")
        st.markdown(
            "Set the `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` environment variables "
            "in your hosting provider's settings, or configure `[supabase]` in Streamlit Secrets."
        )
        if st.session_state.get("supabase_setup_error"):
            st.caption("Connection detail: " + st.session_state["supabase_setup_error"])
        st.stop()

    _show_login_header()
    sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("supabase_signin_form", clear_on_submit=False):
            email_or_admin = st.text_input("Email address Or Username")
            password = st.text_input("Password", type="password")
            signin_clicked = st.form_submit_button(
                "Sign in", type="primary", use_container_width=True
            )

        if signin_clicked:
            login_id = email_or_admin.strip()
            if not login_id or not password:
                st.error("Enter your email/username and password.")
            else:
                # Keep the existing private admin login working during migration.
                try:
                    legacy_users = dict(st.secrets["auth"]["users"])
                except Exception:
                    legacy_users = {}
                # Optional single admin login for hosts that use environment variables.
                env_admin_user = os.environ.get("ADMIN_USERNAME", "").strip()
                env_admin_password = os.environ.get("ADMIN_PASSWORD", "")
                if env_admin_user and env_admin_password:
                    legacy_users.setdefault(env_admin_user, env_admin_password)

                legacy_password = legacy_users.get(login_id)
                if legacy_password is not None and hmac.compare_digest(
                    password, str(legacy_password)
                ):
                    st.session_state["authenticated"] = True
                    st.session_state["authenticated_user"] = login_id
                    st.session_state["auth_method"] = "legacy"
                    st.session_state["login_just_succeeded"] = True
                    st.rerun()
                elif "@" in login_id:
                    try:
                        with st.spinner("Authenticating securely…"):
                            response = client.auth.sign_in_with_password(
                                {"email": login_id, "password": password}
                            )
                        if response and response.user:
                            if getattr(response, "session", None):
                                st.session_state["supabase_access_token"] = response.session.access_token
                                st.session_state["supabase_refresh_token"] = response.session.refresh_token
                            st.session_state["authenticated"] = True
                            st.session_state["authenticated_user"] = (
                                response.user.email or login_id
                            )
                            st.session_state["auth_method"] = "supabase"
                            st.session_state["login_just_succeeded"] = True
                            st.rerun()
                        else:
                            st.error("Sign-in failed. Check your email and password.")
                    except Exception:
                        st.error(
                            "Could not sign in. Check your email and password, and "
                            "confirm your email address if verification is enabled."
                        )
                else:
                    st.error("Incorrect username or password.")

    with create_tab:
        st.caption("Create a personal account using your work email address.")
        with st.form("supabase_signup_form", clear_on_submit=True):
            new_email = st.text_input("Work email address", key="signup_email")
            new_username = st.text_input("Your name", key="signup_name")
            new_password = st.text_input(
                "Create password", type="password", key="signup_password"
            )
            confirm_password = st.text_input(
                "Confirm password", type="password", key="signup_confirm_password"
            )
            signup_clicked = st.form_submit_button(
                "Create account", type="primary", use_container_width=True
            )

        if signup_clicked:
            new_email = new_email.strip().lower()
            new_username = new_username.strip()
            if not new_email or "@" not in new_email:
                st.error("Enter a valid email address.")
            elif not new_username:
                st.error("Enter your name.")
            elif len(new_password) < 8:
                st.error("Use a password with at least 8 characters.")
            elif new_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    with st.spinner("Creating your secure account…"):
                        response = client.auth.sign_up(
                            {
                                "email": new_email,
                                "password": new_password,
                                "options": {"data": {"username": new_username}},
                            }
                        )
                    if response and response.session and response.user:
                        st.session_state["supabase_access_token"] = response.session.access_token
                        st.session_state["supabase_refresh_token"] = response.session.refresh_token
                        st.session_state["authenticated"] = True
                        st.session_state["authenticated_user"] = (
                            response.user.email or new_email
                        )
                        st.session_state["auth_method"] = "supabase"
                        st.session_state["login_just_succeeded"] = True
                        # Profile details are optional; Auth remains the source of truth.
                        try:
                            client.table("profiles").upsert(
                                {
                                    "id": response.user.id,
                                    "username": new_username,
                                }
                            ).execute()
                        except Exception:
                            pass
                        st.success("Account created. Signing you in…")
                        st.rerun()
                    else:
                        st.success(
                            "Registration received. Check your email for a verification "
                            "link, then return here and sign in."
                        )
                
                except Exception as e:
                    st.error(f"Account creation failed: {e}")


    st.stop()


def _ludo_default_state():
    return {
        "players": [], "tokens": {}, "turn": 0, "dice": None,
        "rolled": False, "winner": None, "updated_at": datetime.utcnow().isoformat()
    }


def render_ludo_online():
    'Classic-style four-token online Ludo using the existing Supabase room table.'
    st.markdown("### 🎲 Ludo Online · Classic gameplay")
    st.caption("Play online with colleagues, or choose Play Ludo with 3 bots when nobody is available. Four tokens each, roll a 6 to leave base, capture opponents, and reach home.")
    client = get_supabase_client()
    if client is None:
        st.error("Supabase is not configured. Check the URL and publishable key in Streamlit Secrets.")
        return
    try:
        user = client.auth.get_user().user
        if not user:
            raise ValueError("No authenticated user")
    except Exception:
        st.warning("Please sign in with your Supabase email and password to play online.")
        return
    uid = str(user.id)
    email = str(user.email or "")
    meta = getattr(user, "user_metadata", None) or {}
    name = str(meta.get("username") or meta.get("name") or email.split("@")[0] or "Player")[:30]
    token = st.session_state.get("supabase_access_token", "")
    try:
        cfg = st.secrets["supabase"]
        url, key = str(cfg["url"]).rstrip("/"), str(cfg["publishable_key"])
    except Exception:
        st.error("Missing Supabase URL or publishable key in Streamlit Secrets.")
        return
    if not token:
        st.warning("No active Supabase session token. Sign out and sign in with your Supabase email/password.")
        return
    left, right = st.columns(2)
    with left:
        if st.button("🎲 Create classic Ludo room", type="primary", use_container_width=True):
            code = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            state = _ludo_default_state()
            state["players"] = [{"id": uid, "name": name, "color": "red"}]
            state["tokens"] = {uid: [-1, -1, -1, -1]}
            try:
                client.table("ludo_rooms").insert({"room_code": code, "created_by": uid, "state": state}).execute()
                st.session_state["ludo_room_code"] = code
                st.success(f"Room created: {code}. Share this code with colleagues.")
                st.rerun()
            except Exception as exc:
                st.error("Could not create room. Run the Ludo SQL setup first.")
                st.caption(str(exc))
    with left:
        if st.button("🤖 Play Ludo with 3 bots", use_container_width=True, key="ludo_vs_bots"):
            code = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            state = _ludo_default_state()
            state["players"] = [
                {"id": uid, "name": name, "color": "red"},
                {"id": "bot-blue", "name": "Blue Bot", "color": "blue", "is_bot": True},
                {"id": "bot-yellow", "name": "Yellow Bot", "color": "yellow", "is_bot": True},
                {"id": "bot-green", "name": "Green Bot", "color": "green", "is_bot": True},
            ]
            state["tokens"] = {uid: [-1, -1, -1, -1], "bot-blue": [-1, -1, -1, -1], "bot-yellow": [-1, -1, -1, -1], "bot-green": [-1, -1, -1, -1]}
            try:
                client.table("ludo_rooms").insert({"room_code": code, "created_by": uid, "state": state}).execute()
                st.session_state["ludo_room_code"] = code
                st.success(f"Bot game created: {code}. You are Red; play against three bots.")
                st.rerun()
            except Exception as exc:
                st.error("Could not create bot game. Check the Ludo SQL setup.")
                st.caption(str(exc))
    with right:
        code_in = st.text_input("Colleague's room code", max_chars=6, key="ludo_join_code").strip().upper()
        if st.button("Join Ludo room", use_container_width=True):
            try:
                rows = client.table("ludo_rooms").select("room_code,state").eq("room_code", code_in).limit(1).execute().data or []
                if not rows:
                    st.error("Room not found. Check the code.")
                else:
                    state = rows[0].get("state") or _ludo_default_state()
                    players = state.setdefault("players", [])
                    if not any(str(pl.get("id")) == uid for pl in players):
                        if len(players) >= 4:
                            st.error("This room already has four players.")
                            return
                        colors = ["red", "blue", "green", "yellow"]
                        used = {pl.get("color") for pl in players}
                        color = next(c for c in colors if c not in used)
                        players.append({"id": uid, "name": name, "color": color})
                        state.setdefault("tokens", {})[uid] = [-1, -1, -1, -1]
                        state["turn"] = 0
                        state["dice"] = None
                        state["rolled"] = False
                        client.table("ludo_rooms").update({"state": state}).eq("room_code", code_in).execute()
                    st.session_state["ludo_room_code"] = code_in
                    st.rerun()
            except Exception as exc:
                st.error("Could not join room. Check the SQL setup and table policies.")
                st.caption(str(exc))
    room = st.session_state.get("ludo_room_code", "")
    if not room:
        st.info("Create a room or enter a colleague's room code to start.")
        return
    try:
        rows = client.table("ludo_rooms").select("state").eq("room_code", room).limit(1).execute().data or []
        if not rows:
            st.warning("Room not found. Create or join another room.")
            return
        state = rows[0].get("state") or _ludo_default_state()
        players = state.get("players", [])
        st.markdown(f"### Current room: `{room}`")
        st.write("Players: " + (" · ".join(f"{pl.get('name', 'Player')} ({pl.get('color', '')})" for pl in players) if players else "Waiting for players"))
        payload = json.dumps({"url": url, "key": key, "token": token, "room": room, "uid": uid}).replace("</", "<\\/")
        html = r'''<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(ellipse at 50% 0%,#253b68 0%,#10182e 62%);color:#f8fafc}.panel{padding:clamp(12px,2.2vw,22px);border:1px solid #ffffff20;border-radius:22px;background:linear-gradient(145deg,#17233d,#0c1428);box-shadow:0 22px 60px #02061780,inset 0 1px #ffffff12}#status{text-align:center;color:#a7f3d0;font-weight:800;margin:8px 0 14px;font-size:clamp(14px,2vw,17px);letter-spacing:.01em;min-height:24px}.boardwrap{max-width:680px;margin:16px auto 10px;padding:10px;border-radius:22px;background:linear-gradient(145deg,#f8fafc,#cbd5e1 52%,#94a3b8);box-shadow:0 14px 32px #02061770,inset 0 2px 2px #fff}.boardwrap canvas{width:100%;height:auto;display:block;border-radius:14px;touch-action:manipulation;filter:drop-shadow(0 4px 6px #0f172a30)}.row{display:flex;gap:10px;justify-content:center;margin:14px;flex-wrap:wrap}.row button{padding:12px 20px;border:1px solid #ffffff28;border-radius:13px;font-weight:800;background:linear-gradient(135deg,#f472b6,#8b5cf6 55%,#3b82f6);color:white;cursor:pointer;box-shadow:0 7px 18px #6366f155;transition:transform .16s ease,filter .16s ease,box-shadow .16s ease}.row button:hover:not(:disabled){transform:translateY(-2px);filter:brightness(1.08);box-shadow:0 10px 24px #6366f177}.row button:active:not(:disabled){transform:translateY(1px) scale(.99)}.row button:disabled{opacity:.42;filter:grayscale(.35);box-shadow:none}.hint{text-align:center;color:#cbd5e1;font-size:13px;line-height:1.6;max-width:680px;margin:12px auto 2px}.chips{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:8px 0 12px}.chip{padding:7px 11px;border-radius:999px;background:#ffffff0c;border:1px solid #ffffff18;font-size:12px;font-weight:700;box-shadow:inset 0 1px #ffffff0c}
</style></head><body><div class="panel"><div id="status">Connecting…</div><div class="chips" id="players"></div><div class="boardwrap"><canvas id="board" width="600" height="600"></canvas></div><div class="row"><button id="roll">🎲 Roll dice</button><button id="refresh">↻ Refresh</button></div><div class="hint">Classic rules: roll a 6 to enter a token, click one of your glowing tokens to move, capture opponents, and reach home exactly. A 6 or capture earns another turn.</div></div><script>
const C=PAYLOAD,api=C.url+'/rest/v1/',H={'apikey':C.key,'Authorization':'Bearer '+C.token,'Content-Type':'application/json'};const cv=document.getElementById('board'),ctx=cv.getContext('2d'),status=document.getElementById('status'),playerBox=document.getElementById('players');let state=null,busy=false,localDice=null,canMove=[];const W=600,S=40,colors={red:'#e53935',blue:'#2585e8',green:'#22a65a',yellow:'#f3c623'},light={red:'#ffcdd2',blue:'#bbdefb',green:'#c8e6c9',yellow:'#fff3b0'};
// 52-cell classic perimeter path, with separate six-cell home lanes.
const ring=[[6,0],[6,1],[6,2],[6,3],[6,4],[6,5],[5,6],[4,6],[3,6],[2,6],[1,6],[0,6],[0,7],[0,8],[1,8],[2,8],[3,8],[4,8],[5,8],[6,9],[6,10],[6,11],[6,12],[6,13],[6,14],[7,14],[8,14],[8,13],[8,12],[8,11],[8,10],[8,9],[9,8],[10,8],[11,8],[12,8],[13,8],[14,8],[14,7],[14,6],[13,6],[12,6],[11,6],[10,6],[9,6],[8,5],[8,4],[8,3],[8,2],[8,1],[8,0],[7,0]];
const order=['red','blue','yellow','green'],start={red:1,blue:14,yellow:27,green:40};
const home={red:[[7,1],[7,2],[7,3],[7,4],[7,5],[7,6]],blue:[[13,7],[12,7],[11,7],[10,7],[9,7],[8,7]],yellow:[[7,13],[7,12],[7,11],[7,10],[7,9],[7,8]],green:[[1,7],[2,7],[3,7],[4,7],[5,7],[6,7]]};
const base={red:[[1.7,1.7],[3.1,1.7],[1.7,3.1],[3.1,3.1]],blue:[[10.9,1.7],[12.3,1.7],[10.9,3.1],[12.3,3.1]],green:[[1.7,10.9],[3.1,10.9],[1.7,12.3],[3.1,12.3]],yellow:[[10.9,10.9],[12.3,10.9],[10.9,12.3],[12.3,12.3]]};
const safe=[1,9,14,22,27,35,40,48];function xy(c){return [(c[0]+.5)*S,(c[1]+.5)*S]};function cur(){return (state?.players||[])[state?.turn||0]};function tokenPos(pl,i){let pos=(state.tokens?.[pl.id]||[-1,-1,-1,-1])[i];if(pos<0)return base[pl.color][i];if(pos<51){let ix=(start[pl.color]+pos)%52;return ring[ix]}if(pos<57)return home[pl.color][pos-51];return [7,7]}
function rounded(x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=1.2;ctx.stroke()}}
function cell(x,y,col){let px=x*S,py=y*S;ctx.fillStyle=col;ctx.fillRect(px,py,S,S);ctx.strokeStyle='#94a3b8';ctx.lineWidth=1.1;ctx.strokeRect(px+.5,py+.5,S-1,S-1);ctx.strokeStyle='#ffffffaa';ctx.beginPath();ctx.moveTo(px+2,py+2);ctx.lineTo(px+S-2,py+2);ctx.stroke()}
function draw(){ctx.clearRect(0,0,W,W);let bg=ctx.createLinearGradient(0,0,W,W);bg.addColorStop(0,'#ffffff');bg.addColorStop(1,'#e2e8f0');ctx.fillStyle=bg;ctx.fillRect(0,0,W,W);ctx.save();ctx.shadowColor='#0f172a28';ctx.shadowBlur=8;ctx.shadowOffsetY=3;[['red',0,0],['blue',9,0],['green',0,9],['yellow',9,9]].forEach(([c,x,y])=>{let baseGrad=ctx.createLinearGradient(x*S,y*S,(x+6)*S,(y+6)*S);baseGrad.addColorStop(0,light[c]);baseGrad.addColorStop(1,colors[c]+'22');rounded(x*S+1,y*S+1,6*S-2,6*S-2,10,baseGrad,'#ffffff');let g=ctx.createLinearGradient((x+1)*S,(y+1)*S,(x+5)*S,(y+5)*S);g.addColorStop(0,colors[c]);g.addColorStop(1,light[c]);rounded((x+1)*S+1,(y+1)*S+1,4*S-2,4*S-2,8,g,'#ffffffaa');rounded((x+1.5)*S,(y+1.5)*S,3*S,3*S,24,'#ffffff','#e2e8f0');});ctx.restore();
ring.forEach((p,i)=>{let c='#fff';if(i===start.red)c=light.red;if(i===start.blue)c=light.blue;if(i===start.green)c=light.green;if(i===start.yellow)c=light.yellow;if(safe.includes(i))c='#fef3c7';cell(p[0],p[1],c)});
Object.entries(home).forEach(([col,arr])=>arr.forEach(p=>cell(p[0],p[1],light[col])));for(let x=6;x<=8;x++)for(let y=6;y<=8;y++){ctx.fillStyle='#f8fafc';ctx.fillRect(x*S,y*S,S,S)}
// Center four-colour finish triangle.
ctx.beginPath();ctx.moveTo(6*S,6*S);ctx.lineTo(9*S,6*S);ctx.lineTo(7.5*S,7.5*S);ctx.closePath();ctx.fillStyle=colors.red;ctx.fill();ctx.beginPath();ctx.moveTo(9*S,6*S);ctx.lineTo(9*S,9*S);ctx.lineTo(7.5*S,7.5*S);ctx.fillStyle=colors.blue;ctx.fill();ctx.beginPath();ctx.moveTo(9*S,9*S);ctx.lineTo(6*S,9*S);ctx.lineTo(7.5*S,7.5*S);ctx.fillStyle=colors.yellow;ctx.fill();ctx.beginPath();ctx.moveTo(6*S,9*S);ctx.lineTo(6*S,6*S);ctx.lineTo(7.5*S,7.5*S);ctx.fillStyle=colors.green;ctx.fill();
const ps=state?.players||[];ps.forEach(pl=>{for(let i=0;i<4;i++){let p=tokenPos(pl,i),[x,y]=xy(p),active=pl.id===C.uid&&canMove.includes(i),r=13;ctx.save();ctx.shadowColor='#0f172a55';ctx.shadowBlur=active?17:7;ctx.shadowOffsetY=active?3:4;let grad=ctx.createRadialGradient(x-r*.38,y-r*.45,2,x,y,r*1.25);let baseColor=colors[pl.color];grad.addColorStop(0,'#ffffff');grad.addColorStop(.18,light[pl.color]);grad.addColorStop(.52,baseColor);grad.addColorStop(1,'#172033');ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=grad;ctx.fill();ctx.restore();ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.lineWidth=active?3.5:1.8;ctx.strokeStyle=active?'#fef08a':'#ffffff';ctx.stroke();ctx.beginPath();ctx.arc(x-r*.32,y-r*.34,3.4,0,Math.PI*2);ctx.fillStyle='#ffffffcc';ctx.fill();ctx.fillStyle='#fff';ctx.font='900 10px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowColor='#00000055';ctx.shadowBlur=2;ctx.fillText(String(i+1),x,y+1);ctx.shadowBlur=0;if(active){let pulse=3+Math.sin(Date.now()/180)*2;ctx.beginPath();ctx.arc(x,y,r+pulse,0,Math.PI*2);ctx.strokeStyle='#fef08a';ctx.lineWidth=2;ctx.stroke()}}});ctx.textBaseline='alphabetic';ctx.textAlign='left';ctx.save();ctx.shadowColor='#ffffff';ctx.shadowBlur=5;ctx.fillStyle='#0f172a';ctx.font='900 17px system-ui';ctx.fillText('DICE',S*6.05,S*7.55);ctx.restore();let dice=localDice||state?.dice||'—';rounded(S*7.05,S*7.08,S*.95,S*.95,8,'#ffffff','#94a3b8');ctx.fillStyle='#111827';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font='900 24px system-ui';ctx.fillText(String(dice),S*7.525,S*7.55);ctx.textAlign='left';ctx.textBaseline='alphabetic';}
async function req(path,opt={}){let r=await fetch(api+path,{...opt,headers:{...H,...(opt.headers||{})}});if(!r.ok)throw Error('Supabase '+r.status+' '+(await r.text()).slice(0,150));return r}
async function load(){try{let r=await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room)+'&select=state'),a=await r.json();if(!a.length){status.textContent='Room not found';return}state=a[0].state||{};if(!state.tokens){state.tokens={};(state.players||[]).forEach(p=>state.tokens[p.id]=[-1,-1,-1,-1]);state.dice=null;state.rolled=false}let ps=state.players||[],cp=cur();playerBox.innerHTML=ps.map(p=>'<span class="chip" style="border:1px solid '+colors[p.color]+'">● '+esc(p.name)+' · '+p.color+'</span>').join('');canMove=[];if(cp?.id===C.uid&&state.rolled&&state.dice)canMove=legalMoves(C.uid,state.dice);document.getElementById('roll').disabled=busy||!cp||cp.id!==C.uid||!!state.rolled||!!state.winner;status.textContent=state.winner?'🏆 Winner: '+state.winner.name:('Room '+C.room+' · '+(cp?cp.name+' to play':'Waiting for players')+(cp?.id===C.uid?' — your turn':''));draw();if(cp?.is_bot&&!state.winner&&!busy)setTimeout(runBotTurn,700)}catch(e){status.textContent='Connection error: '+e.message}}
async function runBotTurn(){if(!state||busy||state.winner)return;let cp=cur();if(!cp?.is_bot||cp.id===C.uid)return;busy=true;try{let d=1+Math.floor(Math.random()*6),arr=state.tokens[cp.id]||[-1,-1,-1,-1],moves=[];arr.forEach((p,i)=>{if((p===-1&&d===6)||(p>=0&&p<57&&p+d<=57))moves.push(i)});if(!moves.length){state.turn=(state.turn+1)%state.players.length;state.dice=null;state.rolled=false;await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room),{method:'PATCH',headers:{'Prefer':'return=minimal'},body:JSON.stringify({state})});}else{let choices=moves.map(i=>({i,p:arr[i],next:arr[i]<0?0:arr[i]+d}));choices.sort((a,b)=>{let av=(a.p<0?10:0)+(a.next===57?100:0)+(a.next>0&&a.next<51?3:0);let bv=(b.p<0?10:0)+(b.next===57?100:0)+(b.next>0&&b.next<51?3:0);return bv-av});let pick=choices[0],old=arr[pick.i],next=pick.next;arr[pick.i]=next;state.tokens[cp.id]=arr;let captured=false;if(next<51){let abs=(start[cp.color]+next)%52;if(!safe.includes(abs)){state.players.filter(p=>p.id!==cp.id).forEach(p=>{let pa=state.tokens[p.id]||[-1,-1,-1,-1];pa.forEach((pos,j)=>{if(pos>=0&&pos<51&&(start[p.color]+pos)%52===abs){pa[j]=-1;captured=true}});state.tokens[p.id]=pa})}}if(arr.every(v=>v===57))state.winner=cp;let bonus=d===6||captured||next===57;state.dice=null;state.rolled=false;if(!state.winner&&!bonus)state.turn=(state.turn+1)%state.players.length;await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room),{method:'PATCH',headers:{'Prefer':'return=minimal'},body:JSON.stringify({state})})}}catch(e){status.textContent='Bot move failed: '+e.message}finally{busy=false;await load()}}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function legalMoves(id,d){let a=state.tokens?.[id]||[-1,-1,-1,-1],out=[];a.forEach((p,i)=>{if(p===-1&&d===6)out.push(i);else if(p>=0&&p<57&&p+d<=57)out.push(i)});return out}
async function save(){if(busy)return;busy=true;try{state.updated_at=new Date().toISOString();await req('ludo_rooms?room_code=eq.'+encodeURIComponent(C.room),{method:'PATCH',headers:{'Prefer':'return=minimal'},body:JSON.stringify({state})})}catch(e){status.textContent='Save failed: '+e.message}finally{busy=false}}
document.getElementById('roll').onclick=async()=>{if(!state||state.winner||busy)return;let cp=cur();if(!cp||cp.id!==C.uid){status.textContent='Wait for your turn';return}if(state.rolled){status.textContent='Select a highlighted token first';return}localDice=1+Math.floor(Math.random()*6);state.dice=localDice;state.rolled=true;canMove=legalMoves(C.uid,localDice);if(!canMove.length){state.rolled=false;state.dice=null;state.turn=(state.turn+1)%state.players.length;status.textContent='No legal move. Turn passes.'}else status.textContent='You rolled '+localDice+'. Click a highlighted token.';draw();await save();await load()};
cv.addEventListener('click',async ev=>{if(!state||busy||state.winner)return;let cp=cur();if(!cp||cp.id!==C.uid||!state.rolled)return;const r=cv.getBoundingClientRect(),x=(ev.clientX-r.left)*600/r.width,y=(ev.clientY-r.top)*600/r.height;let picked=-1,bestD=1e9;for(let i of canMove){let [tx,ty]=xy(tokenPos(cp,i)),d=Math.hypot(x-tx,y-ty);if(d<25&&d<bestD){picked=i;bestD=d}}if(picked<0){status.textContent='Click one of your highlighted tokens.';return}let d=state.dice,arr=state.tokens[C.uid]||[-1,-1,-1,-1],old=arr[picked],next=old<0?0:old+d;if(old<0&&d!==6)return;if(next>57){status.textContent='Need an exact roll to reach home';return}arr[picked]=next;state.tokens[C.uid]=arr;let captured=false;if(next<51){let abs=(start[cp.color]+next)%52;if(!safe.includes(abs)){(state.players||[]).filter(p=>p.id!==C.uid).forEach(p=>{let pa=state.tokens[p.id]||[-1,-1,-1,-1];pa.forEach((pos,j)=>{if(pos>=0&&pos<51&&(start[p.color]+pos)%52===abs){pa[j]=-1;captured=true}});state.tokens[p.id]=pa})}}if(arr.every(v=>v===57)){state.winner=cp;status.textContent='🏆 You won!'}let bonus=d===6||captured||next===57;state.rolled=false;state.dice=null;localDice=null;if(!state.winner&&!bonus)state.turn=(state.turn+1)%state.players.length;canMove=[];draw();await save();await load()});
document.getElementById('refresh').onclick=load;function refresh(){load()}function animateTokens(){if(state)draw();requestAnimationFrame(animateTokens)}load();requestAnimationFrame(animateTokens);setInterval(refresh,1600);
</script></body></html>'''.replace('PAYLOAD', payload)
        components.html(html, height=930, scrolling=False)
        st.caption("Classic-style online Ludo: four tokens per player, dice-based moves, captures, safe squares, home lanes, and turn sharing. Keep the room open on each player's device.")
    except Exception as exc:
        st.error(f"Could not load Ludo room: {exc}")

def render_snake_apple():
    st.markdown("### 🐍 Snake & Apple")
    st.caption("Use arrow keys or WASD to collect apples. Avoid the walls and your own tail.")
    html = r'''<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#10182e;color:white;font-family:system-ui}.wrap{padding:12px;background:linear-gradient(135deg,#172554,#14532d);border-radius:16px}.top{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-weight:800}.game{display:block;width:100%;max-width:600px;margin:12px auto;border-radius:12px;background:#0b1220;touch-action:none}.buttons{display:flex;justify-content:center;gap:8px;flex-wrap:wrap}.buttons button{padding:10px 16px;border:0;border-radius:10px;background:#86efac;color:#052e16;font-weight:900}.hint{text-align:center;color:#d1fae5;font-size:13px}</style></head><body><div class="wrap"><div class="top"><span>🐍 SNAKE & APPLE</span><span>Score: <b id="score">0</b></span><span>Best: <b id="best">0</b></span></div><canvas id="c" class="game" width="600" height="420"></canvas><div class="buttons"><button id="up">⬆</button><button id="left">⬅</button><button id="down">⬇</button><button id="right">➡</button><button id="restart">Restart</button></div><p class="hint">Arrow keys / WASD or buttons to move. Eat apples to grow. Avoid walls and your tail.</p></div><script>
const c=document.getElementById('c'),x=c.getContext('2d'),N=30,cols=20,rows=14;let snake,dir,next,apple,score,over,best=+(localStorage.getItem('dtSnakeBest')||0);document.getElementById('best').textContent=best;function place(){do{apple={x:Math.floor(Math.random()*cols),y:Math.floor(Math.random()*rows)}}while(snake.some(p=>p.x===apple.x&&p.y===apple.y))}function reset(){snake=[{x:7,y:7},{x:6,y:7},{x:5,y:7}];dir={x:1,y:0};next={x:1,y:0};score=0;over=false;place();document.getElementById('score').textContent=score}function turn(a,b){if(a!==-dir.x||b!==-dir.y)next={x:a,y:b}}window.addEventListener('keydown',e=>{let k=e.key.toLowerCase(),m={'arrowup':[0,-1],w:[0,-1],'arrowdown':[0,1],s:[0,1],'arrowleft':[-1,0],a:[-1,0],'arrowright':[1,0],d:[1,0]}[k];if(m){e.preventDefault();turn(...m)}});[['up',0,-1],['down',0,1],['left',-1,0],['right',1,0]].forEach(([id,a,b])=>document.getElementById(id).onclick=()=>turn(a,b));document.getElementById('restart').onclick=reset;function draw(){x.clearRect(0,0,c.width,c.height);x.fillStyle='#0b1220';x.fillRect(0,0,c.width,c.height);for(let y=0;y<rows;y++)for(let xx=0;xx<cols;xx++){x.fillStyle=(xx+y)%2?'#142b2b':'#183737';x.fillRect(xx*N,y*N,N,N)}x.fillStyle='#ef4444';x.beginPath();x.arc(apple.x*N+N/2,apple.y*N+N/2,N*.36,0,Math.PI*2);x.fill();x.fillStyle='#86efac';x.fillRect(apple.x*N+N*.48,apple.y*N+2,4,8);snake.forEach((p,i)=>{x.fillStyle=i?'#22c55e':'#a3e635';x.beginPath();x.roundRect(p.x*N+2,p.y*N+2,N-4,N-4,6);x.fill()});if(over){x.fillStyle='#000a';x.fillRect(0,0,c.width,c.height);x.fillStyle='white';x.textAlign='center';x.font='bold 34px system-ui';x.fillText('GAME OVER',c.width/2,c.height/2);x.font='18px system-ui';x.fillText('Press Restart to play again',c.width/2,c.height/2+32)}}function step(){if(!over){dir=next;let h={x:snake[0].x+dir.x,y:snake[0].y+dir.y};if(h.x<0||h.x>=cols||h.y<0||h.y>=rows||snake.some(p=>p.x===h.x&&p.y===h.y)){over=true}else{snake.unshift(h);if(h.x===apple.x&&h.y===apple.y){score+=10;document.getElementById('score').textContent=score;if(score>best){best=score;localStorage.setItem('dtSnakeBest',best);document.getElementById('best').textContent=best}place()}else snake.pop()}}draw()}reset();const SNAKE_STEP_MS=180;setInterval(step,SNAKE_STEP_MS);
</script></body></html>'''
    components.html(html, height=610, scrolling=False)


def render_games_page():
    st.markdown("""
    <style>
    .games-hero{padding:24px 28px;border-radius:22px;background:linear-gradient(120deg,#6425d0,#e83e8c 52%,#ff9f43);color:white;margin:8px 0 20px;box-shadow:0 12px 35px #8b5cf633}
    .games-hero h1{margin:0;font-size:2.2rem}.games-hero p{margin:6px 0 0;color:#fffde8}
    </style><div class="games-hero"><h1>🎮 Dreamztree Game Zone</h1><p>Think fast, solve the puzzle, and beat your best score.</p></div>
    """, unsafe_allow_html=True)
    game = st.radio("Choose a game", ["🧠 Brain Test", "🔢 Mini Sudoku", "🧠 Memory Match", "🎯 Number Hunt", "🦖 Dino Runner", "🎲 Ludo Online", "🐍 Snake & Apple"], horizontal=True, label_visibility="collapsed", key="games_page_choice")
    if game == "🎲 Ludo Online":
        render_ludo_online()
        return
    if game == "🐍 Snake & Apple":
        render_snake_apple()
        return
    if game == "🧠 Brain Test":
        st.markdown("### 🧠 Brain Test · Quick Challenge")
        questions = [
            ("What has keys but cannot open locks?", ["A door", "A piano", "A map", "A clock"], 1, "A piano has keys, but no locks."),
            ("What comes next: 2, 4, 8, 16, __?", ["18", "24", "30", "32"], 3, "Each number doubles, so the answer is 32."),
            ("You overtake the person in second place. What place are you in?", ["First", "Second", "Third", "Last"], 1, "You take their place: second."),
            ("Which month has 28 days?", ["February only", "April", "All months", "June"], 2, "Every month has at least 28 days."),
        ]
        if "brain_test_q" not in st.session_state: st.session_state.brain_test_q = 0
        if "brain_test_score" not in st.session_state: st.session_state.brain_test_score = 0
        if "brain_test_answered" not in st.session_state: st.session_state.brain_test_answered = False
        qn=st.session_state.brain_test_q
        if qn < len(questions):
            q,opts,correct,explain=questions[qn]
            st.progress(qn/len(questions), text=f"Question {qn+1} of {len(questions)} · Score {st.session_state.brain_test_score}")
            st.markdown(f"#### {q}")
            ans=st.radio("Choose your answer",opts,key=f"brain_answer_{qn}",label_visibility="collapsed")
            if st.button("Check answer",type="primary",key=f"brain_check_{qn}"):
                if not st.session_state.brain_test_answered:
                    if opts.index(ans)==correct: st.session_state.brain_test_score+=1; st.success("Correct! ✨")
                    else: st.error(f"Not quite. {explain}")
                    st.session_state.brain_test_answered=True
            if st.session_state.brain_test_answered and st.button("Next question ➜",key=f"brain_next_{qn}"):
                st.session_state.brain_test_q+=1; st.session_state.brain_test_answered=False; st.rerun()
        else:
            st.balloons(); st.success(f"Challenge complete! You scored {st.session_state.brain_test_score}/{len(questions)}.")
            if st.button("Play again",key="brain_restart"):
                for k in ["brain_test_q","brain_test_score","brain_test_answered"]: st.session_state.pop(k,None)
                st.rerun()
    elif game == "🔢 Mini Sudoku":
        st.markdown("### 🔢 Mini Sudoku · Classic 9×9")
        st.caption("Fill each row, column, and 3×3 box with digits 1–9. Fixed clues cannot be changed.")
        solution = [
            [5,3,4,6,7,8,9,1,2], [6,7,2,1,9,5,3,4,8], [1,9,8,3,4,2,5,6,7],
            [8,5,9,7,6,1,4,2,3], [4,2,6,8,5,3,7,9,1], [7,1,3,9,2,4,8,5,6],
            [9,6,1,5,3,7,2,8,4], [2,8,7,4,1,9,6,3,5], [3,4,5,2,8,6,1,7,9]
        ]
        puzzle = [
            [5,3,0,0,7,0,0,0,0], [6,0,0,1,9,5,0,0,0], [0,9,8,0,0,0,0,6,0],
            [8,0,0,0,6,0,0,0,3], [4,0,0,8,0,3,0,0,1], [7,0,0,0,2,0,0,0,6],
            [0,6,0,0,0,0,2,8,0], [0,0,0,4,1,9,0,0,5], [0,0,0,0,8,0,0,7,9]
        ]
        if "sudoku9_board" not in st.session_state: st.session_state.sudoku9_board=[r[:] for r in puzzle]
        board=st.session_state.sudoku9_board
        for r in range(9):
            cols=st.columns(9, gap="small")
            for c in range(9):
                with cols[c]:
                    if puzzle[r][c]: st.markdown(f"<div style='text-align:center;padding:8px 0;font-weight:800;background:#dbeafe;color:#1d4ed8;border-radius:5px;border:1px solid #93c5fd'>{puzzle[r][c]}</div>",unsafe_allow_html=True)
                    else:
                        val=st.selectbox(f"r{r+1}c{c+1}",[0,1,2,3,4,5,6,7,8,9],index=board[r][c],key=f"sudoku9_{r}_{c}",format_func=lambda x:"·" if x==0 else str(x),label_visibility="collapsed")
                        board[r][c]=val
        a,b=st.columns(2)
        with a:
            if st.button("Check Sudoku",type="primary",use_container_width=True,key="sudoku9_check"):
                if board==solution: st.success("Perfect! Every row, column, and 3×3 box is correct. 🏆")
                else:
                    errors=[]
                    for r in range(9):
                        for c in range(9):
                            if board[r][c] and board[r][c]!=solution[r][c]: errors.append((r+1,c+1))
                    if errors: st.warning(f"There are {len(errors)} incorrect filled cell(s). Check the highlighted-by-position cells: "+", ".join(f"R{r}C{c}" for r,c in errors[:12]))
                    else: st.info("No incorrect filled digits so far. Keep filling the empty cells!")
        with b:
            if st.button("Reset puzzle",use_container_width=True,key="sudoku9_reset"):
                st.session_state.sudoku9_board=[r[:] for r in puzzle]
                for r in range(9):
                    for c in range(9): st.session_state.pop(f"sudoku9_{r}_{c}",None)
                st.rerun()
    elif game == "🧠 Memory Match":
        st.markdown("### 🧠 Memory Match · Find the pairs")
        st.caption("Choose two cards at a time and find all matching emoji pairs.")
        if "memory_match_cards" not in st.session_state:
            cards = ["🚀", "🌴", "🎮", "⭐", "🚀", "🌴", "🎮", "⭐"]
            random.shuffle(cards)
            st.session_state.memory_match_cards = cards
            st.session_state.memory_match_found = []
            st.session_state.memory_match_tries = 0
            st.session_state.memory_match_pick = []
        cards = st.session_state.memory_match_cards
        found = st.session_state.memory_match_found
        picks = st.session_state.memory_match_pick
        st.write(f"**Pairs found:** {len(found)//2}/4 · **Attempts:** {st.session_state.memory_match_tries}")
        grid = st.columns(4)
        for idx, card in enumerate(cards):
            with grid[idx % 4]:
                if idx in found:
                    st.button(card, key=f"memory_card_{idx}", disabled=True, use_container_width=True)
                elif idx in picks:
                    st.button(card, key=f"memory_card_{idx}", disabled=True, use_container_width=True)
                else:
                    if st.button("❔", key=f"memory_card_{idx}", use_container_width=True):
                        picks.append(idx)
                        if len(picks) == 2:
                            st.session_state.memory_match_tries += 1
                            a, b = picks
                            if cards[a] == cards[b]:
                                found.extend([a, b])
                            else:
                                st.session_state.memory_match_last_miss = [a, b]
                            st.session_state.memory_match_pick = []
                            st.rerun()
        if len(found) == len(cards):
            st.balloons()
            st.success(f"Brilliant! You found all pairs in {st.session_state.memory_match_tries} attempts.")
        elif st.session_state.get("memory_match_last_miss"):
            st.info("Those cards didn't match. Pick another pair to continue.")
            if st.button("Continue", key="memory_continue"):
                st.session_state.memory_match_last_miss = []
                st.rerun()
        if st.button("🔄 New memory game", key="memory_restart"):
            for k in ["memory_match_cards", "memory_match_found", "memory_match_tries", "memory_match_pick", "memory_match_last_miss"]:
                st.session_state.pop(k, None)
            st.rerun()

    elif game == "🎯 Number Hunt":
        st.markdown("### 🎯 Number Hunt · Guess the secret number")
        st.caption("A secret number from 1 to 50 is waiting. You have 7 attempts.")
        if "number_hunt_secret" not in st.session_state:
            st.session_state.number_hunt_secret = random.randint(1, 50)
            st.session_state.number_hunt_tries = 0
            st.session_state.number_hunt_over = False
            st.session_state.number_hunt_message = "Make your first guess!"
        guess = st.number_input("Your guess", min_value=1, max_value=50, value=25, step=1, key="number_hunt_guess")
        if st.button("🎯 Check guess", type="primary", key="number_hunt_check", disabled=st.session_state.number_hunt_over):
            st.session_state.number_hunt_tries += 1
            secret = st.session_state.number_hunt_secret
            if guess == secret:
                st.session_state.number_hunt_message = f"Correct! You found it in {st.session_state.number_hunt_tries} attempt(s). 🏆"
                st.session_state.number_hunt_over = True
                st.balloons()
            elif st.session_state.number_hunt_tries >= 7:
                st.session_state.number_hunt_message = f"Out of attempts! The number was {secret}."
                st.session_state.number_hunt_over = True
            elif guess < secret:
                st.session_state.number_hunt_message = "Too low! Try a higher number. ⬆️"
            else:
                st.session_state.number_hunt_message = "Too high! Try a lower number. ⬇️"
        st.info(st.session_state.number_hunt_message)
        st.progress(min(st.session_state.number_hunt_tries / 7, 1.0), text=f"Attempts used: {st.session_state.number_hunt_tries}/7")
        if st.button("🔄 New number", key="number_hunt_restart"):
            for k in ["number_hunt_secret", "number_hunt_tries", "number_hunt_over", "number_hunt_message", "number_hunt_guess"]:
                st.session_state.pop(k, None)
            st.rerun()

    else:
        st.markdown("### 🦖 Dino Runner · Dreamztree Edition")
        st.info("🎮 **How to play:** Press **SPACE** or **↑ UP ARROW** to JUMP. Hold **↓ DOWN ARROW** to DUCK under flying birds. On-screen **JUMP**, **DUCK**, and **RESTART** buttons also work. Click inside the game first to activate laptop keyboard controls.")
        components.html(r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
        *{box-sizing:border-box}body{margin:0;font-family:system-ui;background:#10172a;color:white}.wrap{padding:12px;border-radius:18px;background:linear-gradient(135deg,#141e46,#4b1c80 60%,#c02f86);border:1px solid #ffffff30;overflow:hidden}.top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}.pill{background:#ffffff20;border:1px solid #ffffff30;padding:7px 12px;border-radius:999px;font-weight:800}.stage{position:relative;margin-top:10px;border-radius:12px;overflow:hidden;background:#7dd3fc}.stage canvas{display:block;width:100%;height:auto;touch-action:manipulation}.actions{display:flex;gap:12px;margin-top:12px;position:relative;z-index:5}.actions button{flex:1;min-height:58px;border:0;border-radius:14px;padding:14px 10px;font-size:17px;font-weight:900;cursor:pointer;touch-action:manipulation;color:#25113f;background:linear-gradient(135deg,#fde047,#fb923c);box-shadow:0 4px 0 #b45309}.actions button:last-child{background:linear-gradient(135deg,#67e8f9,#818cf8);box-shadow:0 4px 0 #4338ca}.hint{text-align:center;font-size:12px;opacity:.9;margin-top:10px}
        </style></head><body><div class="wrap"><div class="top"><strong>🌈 DREAMZTREE RUNNER</strong><span class="pill">⭐ Stars: <span id="stars">0</span></span><span class="pill">🏁 Score: <span id="score">0</span></span><span class="pill">🏆 Best: <span id="best">0</span></span></div><div class="actions"><button id="jump" type="button">⬆ JUMP</button><button id="duck" type="button">⬇ DUCK</button><button id="restart" type="button">↻ RESTART</button></div><div class="stage"><canvas id="game" width="900" height="300" aria-label="Dino runner game"></canvas></div><div class="hint"><b>HOW TO PLAY:</b> Tap JUMP to leap over cacti. Press and hold DUCK to avoid flying birds. Tap RESTART after game over. Keyboard: Space/↑ = jump, ↓ = duck.</div></div>
        <script>
        const cv=document.getElementById('game'),ctx=cv.getContext('2d');let W=cv.width,H=cv.height,ground=244,player,obs,stars,score,starCount,speed,frame,over,shield,night,best=+(localStorage.getItem('dtDinoBest')||0),keys={};document.getElementById('best').textContent=best;
        function reset(){player={x:90,y:ground-48,w:42,h:48,vy:0,duck:false};obs=[];stars=[];score=0;starCount=0;speed=3.6;frame=0;over=false;shield=0;night=false;}
        function rect(x,y,w,h,c){ctx.fillStyle=c;ctx.fillRect(x,y,w,h)}function circle(x,y,r,c){ctx.fillStyle=c;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill()}
        function drawDino(){let p=player;let h=p.duck?27:48,y=p.duck?ground-h:p.y; // colorful pixel-inspired dinosaur
          rect(p.x+5,y+13,27,h-13,'#16a34a');rect(p.x+22,y+2,24,22,'#22c55e');rect(p.x+35,y+9,15,9,'#4ade80');rect(p.x+35,y+10,5,5,'#fff');rect(p.x+37,y+11,2,3,'#172554');rect(p.x+20,y+22,17,8,'#15803d');rect(p.x+8,y+h-8,10,8,'#14532d');rect(p.x+27,y+h-8,10,8,'#14532d');rect(p.x+2,y+18,9,7,'#86efac');if(shield>0){ctx.strokeStyle='#fef08a';ctx.lineWidth=4;ctx.beginPath();ctx.ellipse(p.x+25,y+h/2,35,h/2+14,0,0,Math.PI*2);ctx.stroke();circle(p.x+45,y-5,4,'#fff7ae')}}
        function spawn(){if(frame>110&&frame%Math.max(78,Math.floor(155-speed*3))===0){let bird=Math.random()<.16&&score>140;obs.push({x:W+10,w:bird?42:24,h:bird?22:35,y:bird?ground-65:ground-35,bird,passed:false})}if(frame>70&&frame%170===0)stars.push({x:W+5,y:ground-70-Math.random()*55,r:11})}
        function drawBackground(){let isNight=Math.floor(score/180)%2===1;let g=ctx.createLinearGradient(0,0,0,H);if(isNight){g.addColorStop(0,'#172554');g.addColorStop(1,'#7c3aed')}else{g.addColorStop(0,'#38bdf8');g.addColorStop(1,'#d9f99d')}ctx.fillStyle=g;ctx.fillRect(0,0,W,H);if(isNight){for(let i=0;i<35;i++)circle((i*83+frame*.15)%W,(i*37)%150,1.5,'#fff7ad');circle(760,52,21,'#fef3c7')}else{circle(760,50,25,'#fde047');circle(140,55,18,'#fff');circle(160,55,23,'#fff');circle(181,58,15,'#fff');circle(420,80,15,'#fff');circle(440,77,20,'#fff');circle(461,82,13,'#fff')}ctx.fillStyle=isNight?'#312e81':'#86efac';ctx.beginPath();ctx.moveTo(0,ground);for(let x=0;x<=W;x+=80)ctx.lineTo(x,ground-35-Math.sin((x+frame*1.2)/90)*17);ctx.lineTo(W,ground);ctx.fill();rect(0,ground,W,H-ground,isNight?'#166534':'#22c55e');rect(0,ground,W,4,'#facc15');for(let x=-(frame*speed%50);x<W;x+=50)rect(x,ground+24,20,3,'#bbf7d0')}
        function drawObstacle(o){if(o.bird){let flap=Math.sin(frame*.3)*5;rect(o.x+9,o.y+6,26,12,'#7c3aed');rect(o.x+18,o.y+3,18,10,'#a78bfa');rect(o.x+2,o.y+8,12,5,'#f0abfc');rect(o.x+30,o.y+5,4,4,'#fff');rect(o.x+33,o.y+6,2,2,'#111827');rect(o.x+7,o.y+5+flap,14,5,'#c4b5fd')}else{rect(o.x+6,o.y+8,14,o.h-8,'#f97316');rect(o.x,o.y+19,9,10,'#fb923c');rect(o.x+14,o.y+2,10,o.h-2,'#ea580c');rect(o.x+4,o.y+15,3,3,'#ffedd5')}}
        function drawStar(s){ctx.save();ctx.translate(s.x,s.y);ctx.rotate(frame*.04);ctx.fillStyle='#fde047';ctx.strokeStyle='#fff7ae';ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<10;i++){let a=i*Math.PI/5-Math.PI/2,r=i%2?5:12;ctx.lineTo(Math.cos(a)*r,Math.sin(a)*r)}ctx.closePath();ctx.fill();ctx.stroke();ctx.restore()}
        function loop(){drawBackground();if(!over){frame++;score+=.12;speed=Math.min(11,5+score/110);if(shield>0)shield--;spawn();player.duck=!!keys.ArrowDown||!!keys.KeyS;player.y+=player.vy;player.vy+=.72;if(player.y>ground-player.h){player.y=ground-player.h;player.vy=0}obs.forEach(o=>o.x-=speed);stars.forEach(s=>s.x-=speed);obs=obs.filter(o=>o.x>-60);stars=stars.filter(s=>s.x>-30);for(let o of obs){let ph=player.duck?27:48,py=player.duck?ground-ph:player.y;if(player.x+player.w-13>o.x+5&&player.x+11<o.x+o.w-4&&py+ph-9>o.y+5&&py+8<o.y+o.h-3){if(shield>0){o.x=-100;shield=0}else{over=true;best=Math.max(best,Math.floor(score));localStorage.setItem('dtDinoBest',best);document.getElementById('best').textContent=best}}}for(let s of stars){if(!s.got&&Math.abs((player.x+25)-s.x)<32&&Math.abs((player.y+20)-s.y)<35){s.got=true;starCount++;shield=420;score+=25}}stars=stars.filter(s=>!s.got);}
        obs.forEach(drawObstacle);stars.forEach(drawStar);drawDino();document.getElementById('score').textContent=Math.floor(score);document.getElementById('stars').textContent=starCount;if(shield>0){ctx.fillStyle='#fef08a';ctx.font='bold 15px system-ui';ctx.fillText('STAR SHIELD ✨',20,25)}if(over){ctx.fillStyle='#111827bb';ctx.fillRect(0,0,W,H);ctx.textAlign='center';ctx.fillStyle='#fff';ctx.font='bold 34px system-ui';ctx.fillText('GAME OVER!',W/2,H/2-8);ctx.font='bold 17px system-ui';ctx.fillText('Tap RESTART to run again',W/2,H/2+25);ctx.textAlign='left'}requestAnimationFrame(loop)}
        function jump(){if(over){reset();return}if(player.y>=ground-player.h-1)player.vy=-13}
const jumpBtn=document.getElementById('jump'),duckBtn=document.getElementById('duck'),restartBtn=document.getElementById('restart');
jumpBtn.addEventListener('click',e=>{e.preventDefault();jump()});
jumpBtn.addEventListener('pointerdown',e=>{e.preventDefault();jump()});
duckBtn.addEventListener('pointerdown',e=>{e.preventDefault();keys.ArrowDown=true});
['pointerup','pointercancel','pointerleave'].forEach(ev=>duckBtn.addEventListener(ev,e=>{e.preventDefault();keys.ArrowDown=false}));
duckBtn.addEventListener('lostpointercapture',()=>keys.ArrowDown=false);
restartBtn.addEventListener('click',e=>{e.preventDefault();reset()});window.addEventListener('keydown',e=>{keys[e.code]=true;if(['Space','ArrowUp','KeyW'].includes(e.code)){e.preventDefault();jump()}});document.addEventListener('keydown',e=>{if(['Space','ArrowUp','KeyW'].includes(e.code)){e.preventDefault();jump()}if(['ArrowDown','KeyS'].includes(e.code)){e.preventDefault();keys.ArrowDown=true}});document.addEventListener('keyup',e=>{if(['ArrowDown','KeyS'].includes(e.code))keys.ArrowDown=false});window.addEventListener('keyup',e=>{keys[e.code]=false});cv.setAttribute('tabindex','0');document.body.tabIndex=0;document.body.addEventListener('pointerdown',()=>window.focus());cv.addEventListener('pointerdown',e=>{cv.focus();if(e.target===cv)jump()});reset();loop();
        </script></body></html>""", height=560, scrolling=False)


@st.fragment(run_every="20s")
def _game_zone_popup():
    """Show a compact bottom-right Game Zone invitation every 30 seconds."""
    import time

    now = time.time()

    # Never show the Game Zone invitation while the Game Zone is open.
    if st.query_params.get("page", "dashboard") == "game":
        return

    if "game_popup_last_shown" not in st.session_state:
        st.session_state.game_popup_last_shown = now
        return
    if now - float(st.session_state.game_popup_last_shown) < 29:
        return

    st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"]:has(.dt-game-toast-anchor) {
      position: relative;
    }
    .dt-game-toast {
      position: fixed;
      right: 22px;
      bottom: 24px;
      z-index: 99999;
      width: min(330px, calc(100vw - 32px));
      padding: 16px;
      border-radius: 18px;
      color: #fff;
      background: linear-gradient(135deg, #29205f, #92278f 60%, #f05a6b);
      border: 1px solid rgba(255,255,255,.25);
      box-shadow: 0 14px 40px rgba(0,0,0,.38);
      animation: dt-toast-in .45s ease-out both;
    }
    .dt-game-toast strong {display:block;font-size:16px;margin-bottom:5px}
    .dt-game-toast span {display:block;font-size:13px;opacity:.92}
    @keyframes dt-toast-in {
      from {opacity:0;transform:translateY(18px)}
      to {opacity:1;transform:translateY(0)}
    }
    @media(max-width:600px) {
      .dt-game-toast {right:12px;bottom:16px;width:calc(100vw - 24px)}
    }
    </style>
    <div class="dt-game-toast-anchor"></div>
    <div class="dt-game-toast">
      <strong>🎮 Need a quick break?</strong>
      <span>Try Brain Test, Sudoku, or Dino Runner!</span>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns([5, 2])
    with right:
        if st.button("🎮 Play now", key="game_popup_play", type="primary", use_container_width=True):
            st.session_state.game_popup_last_shown = time.time()
            st.query_params["page"] = "game"
            st.rerun()
        if st.button("✕ Not now", key="game_popup_later", use_container_width=True):
            st.session_state.game_popup_last_shown = time.time()
            st.rerun()


def render_team_chat():
    """Render authenticated group chat and one-to-one private messages."""
    st.title("💬 Dreamztree Team Chat")
    st.caption("Group messages and private messages for signed-in team members.")

    client = get_supabase_client()
    if client is None:
        st.error("Supabase is not configured. Check the app's Supabase settings.")
        return

    # Chat requires a real Supabase Auth session. Legacy-only admin logins do not
    # have a database user identity and therefore cannot safely use private chat.
    try:
        auth_response = client.auth.get_user()
        user = auth_response.user
        if not user:
            st.warning("Team Chat requires a Supabase account session. Please sign out and sign in with your work email account.")
            return
    except Exception:
        st.warning("Team Chat requires a Supabase account session. Please sign out and sign in with your work email account.")
        return

    user_id = str(user.id)
    email = user.email or ""
    metadata = getattr(user, "user_metadata", None) or {}
    display_name = str(metadata.get("username") or metadata.get("name") or email or "Team member").strip()

    try:
        client.table("team_chat_profiles").upsert({
            "id": user_id,
            "username": display_name,
            "email": email,
            "updated_at": datetime.now().isoformat(),
        }).execute()
        people_response = (
            client.table("team_chat_profiles")
            .select("id, username, email")
            .neq("id", user_id)
            .order("username")
            .execute()
        )
        people = people_response.data or []
    except Exception as exc:
        st.error("Could not load chat members. Confirm that the Team Chat SQL setup completed successfully.")
        st.caption(f"Technical detail: {exc}")
        return

    mode = st.radio("Chat type", ["Group Chat", "Private Message"], horizontal=True, key="team_chat_mode")
    recipient_id = None
    if mode == "Private Message":
        if not people:
            st.info("No other team members have opened Team Chat yet. Ask each colleague to sign in and open Team Chat once.")
            return
        options = {}
        for person in people:
            label = f"{person.get('username') or person.get('email') or 'Team member'} ({person.get('email') or 'No email'})"
            options[label] = person["id"]
        selected_person = st.selectbox("Send a private message to", list(options.keys()), key="team_chat_recipient")
        recipient_id = options[selected_person]

    try:
        query = (
            client.table("team_chat_messages")
            .select("id, sender_id, recipient_id, message, created_at")
            .order("created_at")
            .limit(100)
        )
        if mode == "Group Chat":
            query = query.is_("recipient_id", "null")
        else:
            query = query.or_(
                f"and(sender_id.eq.{user_id},recipient_id.eq.{recipient_id}),"
                f"and(sender_id.eq.{recipient_id},recipient_id.eq.{user_id})"
            )
        messages = query.execute().data or []
    except Exception as exc:
        st.error("Could not load messages. Confirm the database tables and access policies are set up.")
        st.caption(f"Technical detail: {exc}")
        return

    st.markdown("---")
    st.subheader("Messages")
    if not messages:
        st.info("No messages yet. Start the conversation!")
    for item in messages:
        is_me = str(item.get("sender_id")) == user_id
        sender_label = "You" if is_me else "Team member"
        created_at = str(item.get("created_at") or "")
        st.markdown(f"**{sender_label}** · {created_at}\n\n{item.get('message', '')}")
        st.divider()

    with st.form("team_chat_send_form", clear_on_submit=True):
        message = st.text_area("Your message", max_chars=2000, placeholder="Write a message...")
        send = st.form_submit_button("Send message", type="primary")
    if send:
        message = message.strip()
        if not message:
            st.warning("Please type a message first.")
        else:
            try:
                client.table("team_chat_messages").insert({
                    "sender_id": user_id,
                    "recipient_id": recipient_id,
                    "message": message,
                }).execute()
                st.rerun()
            except Exception as exc:
                st.error("Message could not be sent. Confirm that you are signed in with a Supabase account.")
                st.caption(f"Technical detail: {exc}")


def main():
    require_login()
    if st.session_state.pop("login_just_succeeded", False):
        st.toast("Welcome to Dreamztree Marketing Intelligence", icon="✨")
    inject_premium_theme()
    page = st.query_params.get("page", "dashboard")
    # Keep the Game Zone invitation/notification active on every non-game page.
    # The fragment itself suppresses the popup while the Game Zone is open.
    _game_zone_popup()
    if page == "game":
        if st.button("← Back to Meta Leads Dashboard", key="back_to_dashboard"):
            st.query_params["page"] = "dashboard"
            st.rerun()
        render_games_page()
        return
    if page == "chat":
        if st.button("← Back to Meta Leads Dashboard", key="back_from_team_chat"):
            st.query_params["page"] = "dashboard"
            st.rerun()
        render_team_chat()
        return
    # Dreamztree landing page with a clean hero; global particle animation is applied in inject_premium_theme().
    st.markdown("""
    <style>
      .dt-landing { position:relative; overflow:hidden; margin:10px 0 22px; padding:30px clamp(20px,4vw,46px) 34px;
        border-radius:28px; background:linear-gradient(125deg,rgba(124,58,237,.25),rgba(37,99,235,.18) 48%,rgba(13,148,136,.20));
        border:1px solid rgba(167,139,250,.38); box-shadow:0 22px 70px rgba(0,0,0,.22); }
      .dt-landing:before {content:"";position:absolute;inset:0;pointer-events:none;z-index:0;
        background:radial-gradient(ellipse at 12% 10%,rgba(236,72,153,.16),transparent 42%),radial-gradient(ellipse at 88% 85%,rgba(94,234,212,.12),transparent 42%);}
      .dt-brand-row {display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:54px;position:relative;}
      .dt-brand {display:flex;align-items:center;gap:14px;color:#fff;font-size:clamp(1.25rem,2.4vw,2rem);font-weight:800;letter-spacing:-.04em;}
      .dt-brand-tag {font-size:clamp(.75rem,1.6vw,1.25rem);color:#5eead4;letter-spacing:.035em;text-align:right;}
      .dt-landing-kicker {text-align:center;color:#77f3df;font-size:clamp(.8rem,1.4vw,1.1rem);font-weight:800;margin-bottom:24px;position:relative;}
      .dt-landing-title {text-align:center;color:#f8f9fc;font-size:clamp(1.6rem,3.2vw,2.8rem);line-height:1.16;font-weight:850;letter-spacing:-.035em;margin:0 auto 20px;max-width:1100px;position:relative;}
      .dt-landing-copy {text-align:center;color:#d2def2;font-size:clamp(1rem,1.8vw,1.5rem);line-height:1.5;margin:0 auto 26px;position:relative;}
      .dt-landing-actions {display:flex;justify-content:center;gap:14px;flex-wrap:wrap;position:relative;}
      .dt-landing-actions a {display:inline-flex;align-items:center;justify-content:center;padding:15px 24px;border-radius:16px;text-decoration:none!important;font-size:clamp(1rem,1.7vw,1.35rem);transition:transform .22s ease,box-shadow .22s ease;}
      .dt-landing-actions a:hover {transform:translateY(-3px);box-shadow:0 12px 32px rgba(96,165,250,.18);}
      .dt-landing-actions .primary {background:linear-gradient(100deg,#ec4899,#8b5cf6 55%,#2563eb);color:#fff!important;border:1px solid rgba(255,255,255,.18);font-weight:750;}
      .dt-landing-actions .secondary {background:rgba(15,23,42,.25);color:#f8f9fc!important;border:1px solid rgba(167,139,250,.55);}
      .dt-report-intro {margin:0 0 22px;padding:26px 24px;border:1px solid rgba(167,139,250,.32);border-radius:24px;background:linear-gradient(120deg,rgba(99,102,241,.14),rgba(20,184,166,.08));}
      .dt-report-intro h2 {margin:0 0 10px;color:#f8f9fc;font-size:clamp(1.3rem,2.2vw,2rem);}
      .dt-report-intro p {margin:0;color:#d2def2;font-size:1rem;}
      .dt-landing + div {scroll-margin-top:24px;}
      @media(max-width:650px){.dt-landing{padding:22px 16px}.dt-brand-row{margin-bottom:38px;align-items:flex-start}.dt-brand{gap:10px}.dt-landing-actions a{width:100%;box-sizing:border-box}}
      @media(prefers-reduced-motion:reduce){.dt-landing-actions a{animation:none;transition:none}}
    </style>
    <section class="dt-landing">
      <div class="dt-landing-kicker">DIGITAL MARKETING ANALYTICS</div>
      <h1 class="dt-landing-title">TURN YOUR CAMPAIGN DATA INTO GROWTH</h1>
      <p class="dt-landing-copy">Track leads. Analyze ad spend. Discover winning campaigns.</p>
      <div class="dt-landing-actions">
        <a class="primary" href="#report-form">Explore Reports ↓</a>
        <a class="secondary" href="#campaign-insights">Campaign Insights</a>
      </div>
    </section>
    <section class="dt-report-intro" id="report-form">
      <h2>↓ Scroll down to create a report</h2>
      <p>The existing report-making form and dashboard features remain below the landing page.</p>
    </section>
    """, unsafe_allow_html=True)
    header_left, game_col, chat_col, header_right = st.columns([3, 1.25, 1.1, 1])
    with game_col:
        if st.button("🎮 Game Zone", key="open_game_zone_main", use_container_width=True):
            st.query_params["page"] = "game"
            st.rerun()
    with chat_col:
        if st.button("💬 Team Chat", key="open_team_chat_main", use_container_width=True):
            st.query_params["page"] = "chat"
            st.rerun()
    with header_right:
        if st.button("Sign out", use_container_width=True):
            if st.session_state.get("auth_method") == "supabase":
                try:
                    client = get_supabase_client()
                    if client is not None:
                        client.auth.sign_out()
                except Exception:
                    pass
            st.session_state["authenticated"] = False
            st.session_state.pop("authenticated_user", None)
            st.session_state.pop("auth_method", None)
            st.session_state.pop("supabase_access_token", None)
            st.session_state.pop("supabase_refresh_token", None)
            st.rerun()
    st.caption("Upload a Meta Ads Excel export to generate a branch-wise, staff-wise leads report.")

    st.markdown('<div id="campaign-insights"></div>', unsafe_allow_html=True)
    with st.expander("⚙️ Report settings · date, exchange rate and campaign mapping", expanded=False):
        date_value = st.date_input("Report date", value=datetime.today().date())

        settings_left, settings_right = st.columns(2, gap="large")
        with settings_left:
            st.subheader("USD → KWD exchange rate")
            use_manual_rate = st.checkbox(
                "Use manual fallback rate instead",
                value=False,
                help="Enable this only if you need to use your company's rate or the automatic reference rate is unavailable.",
            )
            manual_factor = st.number_input(
                "Manual fallback rate (1 USD = KWD)",
                min_value=0.000001,
                value=MANUAL_FALLBACK_KWD_FACTOR,
                step=0.001,
                format="%.6f",
                disabled=not use_manual_rate,
            )
            if use_manual_rate:
                factor = float(manual_factor)
                st.warning(f"Manual fallback rate in use: 1 USD = {factor:.6f} KWD. This is not a live rate.")
                rate_source_label = "Manual fallback"
                rate_date_label = "Manually entered"
            else:
                try:
                    with st.spinner("Fetching latest published USD → KWD reference rate…"):
                        factor, rate_date_label = fetch_usd_kwd_rate()
                    rate_source_label = "Open ER API reference rate"
                    st.success(f"1 USD = {factor:.6f} KWD")
                    st.caption(f"Rate date: {rate_date_label} · Source: open.er-api.com · Cached for up to 24 hours.")
                except Exception as exc:
                    factor = float(manual_factor)
                    rate_source_label = "Manual fallback (API unavailable)"
                    rate_date_label = "Manually entered"
                    st.error("Could not fetch the exchange rate. The app is using the clearly labelled manual fallback below.")
                    st.warning(f"Fallback in use: 1 USD = {factor:.6f} KWD. Check your connection and verify this rate before using cost totals.")
                    st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
        with settings_right:
            st.subheader("Campaign mapping")
            mapping_upload = st.file_uploader(
                "Optional campaign mapping file", type=["xlsx", "xls", "csv"], key="mapping_upload_settings"
            )
            st.caption("Mapping columns: Campaign, Staff, Course, Branch.")
    mappings = read_mapping_file(mapping_upload)
    st.subheader("1. Upload Meta Ads reports")
    upload_today_col, upload_yesterday_col = st.columns(2)
    with upload_today_col:
        uploaded = st.file_uploader("Today's Meta Ads Excel report", type=["xlsx", "xls"], key="meta_excel")
    with upload_yesterday_col:
        yesterday_uploaded = st.file_uploader(
            "Yesterday's Meta Ads Excel report (optional)",
            type=["xlsx", "xls"],
            key="yesterday_meta_excel",
            help="Upload yesterday's export to compare leads, spend, and top-performing campaigns.",
        )
    if uploaded is None:
        st.info("Upload today's Meta Ads Excel export to begin. Add yesterday's report for a day-over-day comparison.")
        st.subheader("Campaign mapping preview")
        st.dataframe(mappings, use_container_width=True, hide_index=True)
        st.download_button("Download campaign mapping template (CSV)", mappings.to_csv(index=False).encode("utf-8-sig"), "dreamztree_campaign_mapping.csv", "text/csv")
        return
    try:
        raw = pd.read_excel(uploaded)
        original_cols = list(raw.columns)
        normalized_cols = [normalize(c) for c in original_cols]
        def find_col(predicate, fallback):
            for i, c in enumerate(normalized_cols):
                if predicate(c):
                    return original_cols[i]
            return original_cols[min(fallback, len(original_cols)-1)]
        campaign_col = find_col(lambda c: "campaign" in c, 0)
        result_col = find_col(lambda c: "result" in c and "initial" not in c, 1)
        spent_col = find_col(lambda c: "spent" in c or "amount" in c, 2)
        df = raw[[campaign_col, result_col, spent_col]].copy()
        df.columns = ["Campaign", "Results", "Spent"]
        df["Campaign"] = df["Campaign"].fillna("").astype(str)
        df["Results"] = pd.to_numeric(df["Results"], errors="coerce").fillna(0).astype(int)
        df["Spent"] = pd.to_numeric(df["Spent"], errors="coerce").fillna(0.0)

        # Preserve zero-result campaigns for spend visibility, while keeping them out of the lead report.
        no_result_df = df[df["Results"] <= 0].copy().reset_index(drop=True)
        no_result_count = len(no_result_df)
        no_result_spend_usd = float(no_result_df["Spent"].sum())
        df = df[(df["Results"] > 0) & (df["Results"] <= 10000)].reset_index(drop=True)

        st.success(f"Loaded {len(df)} campaigns with {int(df['Results'].sum())} total results.")
        with st.container(border=True):
            st.markdown("### ⚠️ Campaigns with no results")
            if no_result_count:
                st.warning(
                    f"Attention: {no_result_count} campaign(s) generated zero results "
                    f"and spent ${no_result_spend_usd:,.2f} USD "
                    f"({no_result_spend_usd * factor:,.3f} KD). "
                    "These costs are excluded from the leads report but shown here for review."
                )
                nr1, nr2, nr3 = st.columns(3)
                nr1.metric("Zero-result campaigns", f"{no_result_count:,}")
                nr2.metric("Total spend · USD", f"${no_result_spend_usd:,.2f}")
                nr3.metric("Total spend · KWD", f"{no_result_spend_usd * factor:,.3f} KD")

                no_result_display = no_result_df[["Campaign", "Results", "Spent"]].copy()
                no_result_display["Cost (KWD)"] = no_result_display["Spent"] * factor
                no_result_display = no_result_display.rename(
                    columns={"Campaign": "Campaign name", "Results": "Results", "Spent": "Spend (USD)"}
                )
                no_result_display["Spend (USD)"] = no_result_display["Spend (USD)"].map(lambda v: f"${v:,.2f}")
                no_result_display["Cost (KWD)"] = no_result_display["Cost (KWD)"].map(lambda v: f"{v:,.3f} KD")
                st.dataframe(no_result_display, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download no-result campaign list (CSV)",
                    no_result_df.assign(**{"Cost_KWD": no_result_df["Spent"] * factor})[
                        ["Campaign", "Results", "Spent", "Cost_KWD"]
                    ].to_csv(index=False).encode("utf-8-sig"),
                    f"dreamztree_no_result_campaigns_{date_value.strftime('%Y%m%d')}.csv",
                    "text/csv",
                )
            else:
                st.success("No campaigns with zero results were found in this export.")
        st.subheader("2. Review campaign assignments")
        assignments = []
        for _, r in df.iterrows():
            staff, course, branch, status = infer_campaign(r["Campaign"], mappings)
            assignments.append({"Campaign": r["Campaign"], "Results": int(r["Results"]), "Spent": float(r["Spent"]), "Staff": staff, "Course": course, "Branch": branch, "Status": status})
        assigned = pd.DataFrame(assignments)
        # A campaign can be included in branch/staff totals when Staff and Branch are known.
        # A missing Course is labelled "Unclassified course" in the report instead of excluding leads.
        initial_unresolved = assigned[(assigned["Staff"].astype(str).str.strip() == "") | (assigned["Branch"].astype(str).str.strip() == "") | (assigned["Course"].astype(str).str.strip() == "")]
        if not initial_unresolved.empty:
            st.warning(f"{len(initial_unresolved)} campaign(s) need review. Campaigns with Staff and Branch identified can still be included; missing courses will appear as 'Unclassified course'.")
            st.dataframe(initial_unresolved, use_container_width=True, hide_index=True)
        edited = st.data_editor(
            assigned,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Mapping status", disabled=True),
                "Results": st.column_config.NumberColumn("Results", disabled=True),
                "Spent": st.column_config.NumberColumn("Amount spent", disabled=True, format="%.2f"),
            },
            num_rows="fixed",
            key="assignments_editor",
        )
        unresolved = edited[(edited["Staff"].astype(str).str.strip() == "") | (edited["Course"].astype(str).str.strip() == "") | (edited["Branch"].astype(str).str.strip() == "")]
        if not unresolved.empty:
            can_include = unresolved[(unresolved["Staff"].astype(str).str.strip() != "") & (unresolved["Branch"].astype(str).str.strip() != "")]
            needs_staff_branch = len(unresolved) - len(can_include)
            st.warning(f"{len(can_include)} campaign(s) with Staff and Branch identified can be included despite a missing course. {needs_staff_branch} campaign(s) still need Staff or Branch review.")
        if st.button("Generate report", type="primary"):
            # Only Staff and Branch are required for inclusion. Missing courses are not allowed
            # to remove otherwise valid leads from the branch/staff report.
            valid = edited[(edited["Staff"].astype(str).str.strip() != "") & (edited["Branch"].astype(str).str.strip() != "")].copy()
            if valid.empty:
                st.error("No campaigns have both Staff and Branch identified. Review the assignment table first.")
                return
            valid["Course"] = valid["Course"].astype(str).str.strip().replace("", "Unclassified course")
            grouped = valid.groupby(["Branch", "Staff", "Course"], sort=False).agg(Results=("Results", "sum"), Spent=("Spent", "sum")).reset_index()
            lines = [f"*📋 Leads Count  ·  {date_value.strftime('%d/%m/%Y')}*", ""]
            grand_leads, grand_spent = 0, 0.0
            for branch in BRANCH_ORDER + [b for b in grouped["Branch"].unique() if b not in BRANCH_ORDER]:
                bd = grouped[grouped["Branch"] == branch]
                if bd.empty:
                    continue
                branch_spent = bd["Spent"].sum()
                lines.extend([f"*{branch}*  —  Cost: {round(branch_spent * factor, 2)} KD", "——————————"])
                staff_order = STAFF_ORDER.get(branch, [])
                extras = [s for s in bd["Staff"].unique() if s not in staff_order]
                for staff in staff_order + extras:
                    for _, rr in bd[bd["Staff"] == staff].sort_values("Results", ascending=False).iterrows():
                        lines.append(f"{rr['Staff']}  -  {rr['Course']}  -  {int(rr['Results'])}")
                lines.append("")
                grand_leads += int(bd["Results"].sum())
                grand_spent += float(branch_spent)
            lines.extend(["——————————", f"*🏆 Grand Total  —  {grand_leads} Leads  |  Total Cost: {round(grand_spent * factor, 2)} KD*"])
            report = "\n".join(lines)
            st.subheader("3. Generated report")
            st.code(report, language=None)
            st.download_button("Download report (.txt)", report.encode("utf-8"), f"dreamztree_leads_{date_value.strftime('%Y%m%d')}.txt", "text/plain")
            st.download_button("Download reviewed mappings (.csv)", edited[["Campaign", "Staff", "Course", "Branch"]].to_csv(index=False).encode("utf-8-sig"), "dreamztree_campaign_mapping_updated.csv", "text/csv")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total leads included", f"{grand_leads:,}")
            m2.metric("Total cost", f"{round(grand_spent * factor, 2):.2f} KD")
            m3.metric("Campaigns included", f"{len(valid):,}")
            st.subheader("Performance analytics")
            branch_chart = valid.groupby("Branch", as_index=False).agg(Leads=("Results", "sum"), Spend_USD=("Spent", "sum"))
            branch_chart["Spend_KWD"] = branch_chart["Spend_USD"] * factor
            course_chart = valid.assign(Course=valid["Course"].astype(str).str.strip().replace("", "Unclassified course")).groupby("Course", as_index=False)["Results"].sum().sort_values("Results", ascending=False).head(12)
            chart_left, chart_right = st.columns(2, gap="large")
            with chart_left:
                st.markdown("#### Leads by branch")
                branch_leads_plot = branch_chart.sort_values("Leads", ascending=True)
                fig_leads = px.bar(
                    branch_leads_plot, x="Leads", y="Branch", orientation="h",
                    text="Leads", color_discrete_sequence=["#3dd6b3"],
                    template="plotly_dark",
                )
                fig_leads.update_layout(
                    height=300, margin=dict(l=12, r=20, t=12, b=12),
                    showlegend=False, xaxis_title="Leads", yaxis_title="",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E8EEF7", size=12),
                )
                fig_leads.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(fig_leads, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            with chart_right:
                st.markdown("#### Cost by branch · KWD")
                branch_cost_plot = branch_chart.sort_values("Spend_KWD", ascending=True)
                fig_cost = px.bar(
                    branch_cost_plot, x="Spend_KWD", y="Branch", orientation="h",
                    text=branch_cost_plot["Spend_KWD"].map(lambda x: f"{x:.3f}"),
                    color_discrete_sequence=["#6ea8fe"], template="plotly_dark",
                )
                fig_cost.update_layout(
                    height=300, margin=dict(l=12, r=28, t=12, b=12),
                    showlegend=False, xaxis_title="Cost (KWD)", yaxis_title="",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E8EEF7", size=12),
                )
                fig_cost.update_traces(textposition="outside", cliponaxis=False)
                st.plotly_chart(fig_cost, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            st.markdown("#### Top courses by leads")
            course_plot = course_chart.sort_values("Results", ascending=True)
            fig_courses = px.bar(
                course_plot, x="Results", y="Course", orientation="h",
                text="Results", color_discrete_sequence=["#f7bd60"],
                template="plotly_dark",
            )
            fig_courses.update_layout(
                height=max(360, 36 * len(course_plot) + 70),
                margin=dict(l=18, r=28, t=12, b=24),
                showlegend=False, xaxis_title="Leads", yaxis_title="",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E8EEF7", size=12),
                yaxis=dict(automargin=True, tickfont=dict(size=12)),
            )
            fig_courses.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_courses, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            st.caption(f"{len(unresolved)} campaign(s) require review if left incomplete.")
            st.caption(f"Exchange rate used: 1 USD = {factor:.6f} KWD · {rate_source_label} · Rate date: {rate_date_label}.")

            # Optional day-over-day comparison. Yesterday is processed with the same campaign
            # filters and mapping rules; today's figures use the reviewed assignments above.
            st.divider()
            st.subheader("Yesterday vs today")
            if yesterday_uploaded is None:
                st.info("Upload yesterday's Meta Ads Excel report above to compare lead volume, cost, and the highest-lead campaign.")
            else:
                try:
                    yesterday_assigned = load_campaign_report(yesterday_uploaded, mappings)
                    yesterday_valid, yesterday_leads, yesterday_cost, yesterday_top = summarize_campaign_performance(
                        yesterday_assigned, factor
                    )
                    today_valid, today_leads, today_cost, today_top = summarize_campaign_performance(
                        edited, factor
                    )

                    if yesterday_valid.empty:
                        st.warning("Yesterday's file did not contain campaigns with both Staff and Branch identified. Review its mapping before comparing.")
                    else:
                        lead_delta = today_leads - yesterday_leads
                        cost_delta = today_cost - yesterday_cost
                        lead_pct = (lead_delta / yesterday_leads * 100) if yesterday_leads else None
                        cost_pct = (cost_delta / yesterday_cost * 100) if yesterday_cost else None

                        st.markdown(
                            "### Exact daily totals",
                        )
                        st.caption("These are the actual totals for each uploaded day, not just the difference.")
                        day1, day2, day3, day4 = st.columns(4, gap="medium")
                        day1.metric("Yesterday · Leads", f"{yesterday_leads:,}")
                        day2.metric("Today · Leads", f"{today_leads:,}", f"{lead_delta:+,} leads")
                        day3.metric("Yesterday · Cost", f"{yesterday_cost:,.3f} KD")
                        day4.metric("Today · Cost", f"{today_cost:,.3f} KD", f"{cost_delta:+.3f} KD")

                        change1, change2 = st.columns(2, gap="medium")
                        change1.metric(
                            "Lead change",
                            f"{lead_delta:+,} leads",
                            f"{lead_pct:+.1f}% vs yesterday" if lead_pct is not None else "Yesterday total is zero",
                            delta_color="normal",
                        )
                        change2.metric(
                            "Cost change",
                            f"{cost_delta:+.3f} KD",
                            f"{cost_pct:+.1f}% vs yesterday" if cost_pct is not None else "Yesterday cost is zero",
                            delta_color="inverse",
                        )

                        if lead_delta > 0 and cost_delta < 0:
                            st.success("Good result: you generated more leads while spending less.")
                        elif lead_delta > 0 and cost_delta > 0:
                            st.info("Lead volume increased, but ad spend also increased. Check whether the extra leads justify the extra cost.")
                        elif lead_delta < 0 and cost_delta < 0:
                            st.warning("Both leads and spend decreased. Check whether the lower spend explains the lead drop.")
                        elif lead_delta < 0 and cost_delta > 0:
                            st.error("Attention: leads decreased while spend increased. Review campaign targeting, creative, and budgets.")
                        else:
                            st.info("Lead volume and spend are broadly unchanged. Review the campaign-level table below.")

                        top_left, top_right = st.columns(2, gap="large")
                        with top_left:
                            st.markdown("#### 🏆 Best campaign yesterday")
                            st.write(f"**{yesterday_top['Campaign']}**")
                            st.caption(
                                f"{int(yesterday_top['Results']):,} leads · "
                                f"{float(yesterday_top['Cost_KWD']):.3f} KD spend · "
                                f"{yesterday_top['Branch']} · {yesterday_top['Staff']}"
                            )
                        with top_right:
                            st.markdown("#### 🏆 Best campaign today")
                            if today_top is not None:
                                st.write(f"**{today_top['Campaign']}**")
                                st.caption(
                                    f"{int(today_top['Results']):,} leads · "
                                    f"{float(today_top['Cost_KWD']):.3f} KD spend · "
                                    f"{today_top['Branch']} · {today_top['Staff']}"
                                )
                            else:
                                st.write("No campaigns today have both Staff and Branch assigned.")

                        # Side-by-side campaign comparison makes day-over-day movement explicit.
                        def campaign_rollup(summary, prefix):
                            if summary.empty:
                                return pd.DataFrame(columns=["Campaign", f"{prefix} leads", f"{prefix} cost (KD)"])
                            return summary.groupby("Campaign", as_index=False).agg(
                                **{
                                    f"{prefix} leads": ("Results", "sum"),
                                    f"{prefix} cost (KD)": ("Cost_KWD", "sum"),
                                }
                            )

                        yesterday_rollup = campaign_rollup(yesterday_valid, "Yesterday")
                        today_rollup = campaign_rollup(today_valid, "Today")
                        campaign_compare = yesterday_rollup.merge(today_rollup, on="Campaign", how="outer").fillna(0)
                        if not campaign_compare.empty:
                            campaign_compare["Lead change"] = (
                                campaign_compare["Today leads"] - campaign_compare["Yesterday leads"]
                            ).astype(int)
                            campaign_compare["Cost change (KD)"] = (
                                campaign_compare["Today cost (KD)"] - campaign_compare["Yesterday cost (KD)"]
                            ).round(3)
                            campaign_compare = campaign_compare.sort_values(
                                ["Today leads", "Yesterday leads"], ascending=False
                            )
                            st.markdown("#### Exact leads and cost by campaign — yesterday vs today")
                            st.caption("Positive lead change means more leads today. Negative cost change means less money spent today.")
                            st.dataframe(
                                campaign_compare,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Yesterday leads": st.column_config.NumberColumn(format="%d"),
                                    "Today leads": st.column_config.NumberColumn(format="%d"),
                                    "Lead change": st.column_config.NumberColumn(format="%+d"),
                                    "Yesterday cost (KD)": st.column_config.NumberColumn(format="%.3f KD"),
                                    "Today cost (KD)": st.column_config.NumberColumn(format="%.3f KD"),
                                    "Cost change (KD)": st.column_config.NumberColumn(format="%+.3f KD"),
                                },
                            )
                            st.download_button(
                                "Download comparison CSV",
                                campaign_compare.to_csv(index=False).encode("utf-8-sig"),
                                f"dreamztree_campaign_comparison_{date_value.strftime('%Y%m%d')}.csv",
                                "text/csv",
                            )
                        st.caption(
                            "For a fair comparison, both uploads should cover one full day each. "
                            "Campaigns are included only when Staff and Branch are identified. "
                            "Zero-result campaigns are shown in the separate no-result section."
                        )
                except Exception as compare_exc:
                    st.error(f"Could not compare yesterday's report: {compare_exc}")
                    st.caption("Check that both files use the same Meta Ads export format and that the mapping is reviewed.")
    except Exception as e:
        st.error(f"Could not process this Excel file: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
