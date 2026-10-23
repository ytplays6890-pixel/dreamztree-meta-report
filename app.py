import re
import random
import hmac
import hashlib
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Dreamztree Meta Report", page_icon="🌴", layout="wide")

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
      content:""; position:fixed; z-index:-1; pointer-events:none; width:30rem; height:30rem;
      right:-12rem; bottom:3%; border-radius:50%; filter:blur(75px);
      background:radial-gradient(circle,rgba(236,72,153,.12),rgba(20,184,166,.05) 48%,transparent 72%);
      animation:dt-float 7.5s ease-in-out infinite reverse;
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
    """Create one Supabase client per Streamlit browser session."""
    if "supabase_client" in st.session_state:
        return st.session_state["supabase_client"]

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
        return client
    except Exception as exc:
        st.session_state["supabase_setup_error"] = str(exc)
        return None


def _show_login_header():
    st.markdown(
        """
        <style>
        @keyframes dt-login-entrance {from {opacity:0; transform:translateY(18px) scale(.99);} to {opacity:1; transform:translateY(0) scale(1);}}
        @keyframes dt-login-shift {0%,100% {background-position:0% 50%;} 50% {background-position:100% 50%;}}
        @keyframes dt-login-glow {0%,100% {box-shadow:0 22px 60px rgba(0,0,0,.3),0 0 10px rgba(124,58,237,.08),inset 0 1px rgba(255,255,255,.08)} 50% {box-shadow:0 22px 60px rgba(0,0,0,.3),0 0 34px rgba(96,165,250,.2),inset 0 1px rgba(255,255,255,.08)}}
        @keyframes dt-login-orbit {from {transform:rotate(0deg) translateX(15px) rotate(0deg)} to {transform:rotate(360deg) translateX(15px) rotate(-360deg)}}
        [data-testid="stAppViewContainer"] {
          background: radial-gradient(circle at 12% 5%, rgba(124,58,237,.36), transparent 32%),
            radial-gradient(circle at 90% 12%, rgba(236,72,153,.22), transparent 28%),
            linear-gradient(135deg, #0b1020, #11152b 55%, #101827);
        }
        [data-testid="stHeader"] {background: transparent;}
        .login-panel {max-width: 760px; margin: 4vh auto 1rem auto; padding: 2.2rem;
          border: 1px solid rgba(167,139,250,.55); border-radius: 24px;
          background: linear-gradient(125deg, rgba(124,58,237,.32), rgba(37,99,235,.2) 55%, rgba(13,148,136,.2));
          background-size: 180% 180%; position:relative; overflow:hidden;
          animation: dt-login-entrance .75s cubic-bezier(.2,.75,.25,1) both, dt-login-shift 14s ease-in-out infinite, dt-login-glow 7s ease-in-out infinite;
          box-shadow: 0 22px 60px rgba(0,0,0,.3), inset 0 1px rgba(255,255,255,.08);}
        .login-panel:after {content:""; position:absolute; width:145px; height:145px; right:9%; bottom:-112px; border-radius:50%;
          border:1px solid rgba(94,234,212,.3); box-shadow:0 0 28px rgba(96,165,250,.13); pointer-events:none; animation:dt-login-orbit 16s linear infinite;}
        [data-testid="stForm"] {animation:dt-login-entrance .9s cubic-bezier(.2,.75,.25,1) both;}
        [data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {box-shadow:0 0 0 1px rgba(94,234,212,.6),0 0 18px rgba(96,165,250,.14);}
        @media (prefers-reduced-motion: reduce) {.login-panel,[data-testid="stForm"] {animation:none !important;}}
        .login-kicker {letter-spacing: .18em; text-transform: uppercase; color: #77f3df;
          font-size: .75rem; font-weight: 900;}
        .login-panel h1 {color: #fff; text-shadow: 0 4px 25px rgba(96,165,250,.18);}
        .login-panel p {color: #d6def0;}
        </style>
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
            email_or_admin = st.text_input("Email address or admin username")
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
                    st.rerun()
                elif "@" in login_id:
                    try:
                        response = client.auth.sign_in_with_password(
                            {"email": login_id, "password": password}
                        )
                        if response and response.user:
                            st.session_state["authenticated"] = True
                            st.session_state["authenticated_user"] = (
                                response.user.email or login_id
                            )
                            st.session_state["auth_method"] = "supabase"
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
                    response = client.auth.sign_up(
                        {
                            "email": new_email,
                            "password": new_password,
                            "options": {"data": {"username": new_username}},
                        }
                    )
                    if response and response.session and response.user:
                        st.session_state["authenticated"] = True
                        st.session_state["authenticated_user"] = (
                            response.user.email or new_email
                        )
                        st.session_state["auth_method"] = "supabase"
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
                except Exception:
                    st.error(
                        "Account creation failed. The email may already be registered, "
                        "or Supabase may require email verification. Check the Supabase "
                        "Authentication settings and try again."
                    )

    st.stop()


def main():
    require_login()
    inject_premium_theme()
    st.markdown('<div class="hero"><div class="eyebrow">Dreamztree · Marketing intelligence</div><div class="hero-title">Meta Leads Command Center</div><p class="hero-copy">Branch-wise lead volume, campaign assignments and cost reporting in one workspace.</p></div>', unsafe_allow_html=True)
    header_left, header_right = st.columns([5, 1])
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
            st.rerun()
    st.caption("Upload a Meta Ads Excel export to generate a branch-wise, staff-wise leads report.")

    # Optional mini-game arcade for short breaks; game state stays in this browser session.
    if "show_break_games" not in st.session_state:
        st.session_state["show_break_games"] = False
    arcade_col, arcade_note = st.columns([1, 3], vertical_alignment="center")
    with arcade_col:
        if st.button(
            "🎮  Take a break · Mini Games" if not st.session_state["show_break_games"] else "✖  Close Mini Games",
            key="toggle_break_games",
            use_container_width=True,
            type="primary",
        ):
            st.session_state["show_break_games"] = not st.session_state["show_break_games"]
            st.rerun()
    with arcade_note:
        st.caption("Quick games for a short break — your report data stays untouched.")

    if st.session_state["show_break_games"]:
        st.markdown("""<div class="arcade-banner"><span class="arcade-kicker">DREAMZTREE BREAK ROOM</span><h2>🎮 Mini Game Arcade</h2><p>Take a quick break, then get back to the leads.</p></div>""", unsafe_allow_html=True)
        game_tabs = st.tabs([
            "🎯 Number Guess", "✊ RPS", "🧠 Brain Test", "🧩 Memory", "🔢 Mini Sudoku",
            "🔤 Word Ladder", "➕ Math Sprint", "♟️ Queens Logic", "🟦 Color Match"
        ])
        with game_tabs[0]:
            if "break_number_target" not in st.session_state:
                st.session_state["break_number_target"] = random.randint(1, 20)
            if "break_number_attempts" not in st.session_state:
                st.session_state["break_number_attempts"] = 0
            if "break_number_message" not in st.session_state:
                st.session_state["break_number_message"] = "I'm thinking of a number from 1 to 20. Can you guess it?"
            st.markdown("#### 🎯 Guess the Number")
            st.write("Pick a number from **1 to 20**. Try to find it in as few guesses as possible!")
            guess_col, guess_btn_col, reset_col = st.columns([2, 1, 1])
            with guess_col:
                guess_value = st.number_input("Your guess", min_value=1, max_value=20, value=10, step=1, key="break_number_guess")
            with guess_btn_col:
                st.write("")
                if st.button("Check guess", key="break_check_guess", use_container_width=True):
                    st.session_state["break_number_attempts"] += 1
                    target = st.session_state["break_number_target"]
                    if int(guess_value) == target:
                        st.session_state["break_number_message"] = f"🎉 Correct! You found {target} in {st.session_state['break_number_attempts']} guesses!"
                    elif int(guess_value) < target:
                        st.session_state["break_number_message"] = "⬆️ Too low — try a higher number!"
                    else:
                        st.session_state["break_number_message"] = "⬇️ Too high — try a lower number!"
            with reset_col:
                st.write("")
                if st.button("New game", key="break_reset_guess", use_container_width=True):
                    st.session_state["break_number_target"] = random.randint(1, 20)
                    st.session_state["break_number_attempts"] = 0
                    st.session_state["break_number_message"] = "New number picked! Make your guess."
                    st.rerun()
            st.info(st.session_state["break_number_message"])
            st.caption(f"Guesses: {st.session_state['break_number_attempts']}")

        with game_tabs[1]:
            st.markdown("#### ✊ Rock Paper Scissors")
            st.write("Choose your move and see if you can beat the computer.")
            rps_cols = st.columns(3)
            moves = [("✊ Rock", "Rock"), ("✋ Paper", "Paper"), ("✌️ Scissors", "Scissors")]
            for col, (label, move) in zip(rps_cols, moves):
                with col:
                    if st.button(label, key=f"break_rps_{move.lower()}", use_container_width=True):
                        computer_move = random.choice(["Rock", "Paper", "Scissors"])
                        if move == computer_move:
                            outcome = "It's a tie! 🤝"
                        elif (move, computer_move) in [("Rock", "Scissors"), ("Paper", "Rock"), ("Scissors", "Paper")]:
                            outcome = "You win! 🎉"
                        else:
                            outcome = "Computer wins this round! 🤖"
                        st.session_state["break_rps_result"] = f"You chose {move}. Computer chose {computer_move}. {outcome}"
            if st.session_state.get("break_rps_result"):
                st.success(st.session_state["break_rps_result"])
            else:
                st.caption("Your result will appear here after you choose a move.")

        with game_tabs[2]:
            st.markdown("#### 🧠 Brain Test")
            brain_questions = [
                ("What comes next? 2, 4, 8, 16, __", ["18", "24", "32", "30"], "32", "Each number doubles."),
                ("Which one doesn't belong?", ["Triangle", "Square", "Circle", "Blue"], "Blue", "The others are shapes."),
                ("A farmer has 12 sheep. All but 5 run away. How many remain?", ["5", "7", "12", "0"], "5", "‘All but 5’ means five remain."),
                ("What comes next? J, F, M, A, M, __", ["J", "A", "S", "D"], "J", "The first letters of the months: January, February, March..."),
                ("You overtake the person in second place. What place are you in?", ["First", "Second", "Third", "Last"], "Second", "You take their position."),
            ]
            if "brain_question_index" not in st.session_state: st.session_state.brain_question_index = 0
            if "brain_score" not in st.session_state: st.session_state.brain_score = 0
            if "brain_answered" not in st.session_state: st.session_state.brain_answered = False
            qi = st.session_state.brain_question_index
            if qi < len(brain_questions):
                question, options, answer, explanation = brain_questions[qi]
                st.progress(qi / len(brain_questions), text=f"Question {qi+1} of {len(brain_questions)} · Score {st.session_state.brain_score}")
                st.write(f"**{question}**")
                selected = st.radio("Choose your answer", options, key=f"brain_pick_{qi}", label_visibility="collapsed")
                if st.button("Submit answer", key=f"brain_submit_{qi}", type="primary") and not st.session_state.brain_answered:
                    st.session_state.brain_answered = True
                    st.session_state.brain_last_correct = selected == answer
                    if selected == answer: st.session_state.brain_score += 1
                    st.session_state.brain_explanation = explanation
                    st.rerun()
                if st.session_state.brain_answered:
                    if st.session_state.get("brain_last_correct"): st.success("Correct! 🧠✨")
                    else: st.warning(f"Not quite. Answer: {answer}")
                    st.caption(explanation)
                    if st.button("Next question ➜", key=f"brain_next_{qi}"):
                        st.session_state.brain_question_index += 1
                        st.session_state.brain_answered = False
                        st.rerun()
            else:
                st.success(f"Brain test complete! You scored {st.session_state.brain_score}/{len(brain_questions)}.")
                if st.button("Play brain test again", key="brain_restart"):
                    st.session_state.brain_question_index = 0; st.session_state.brain_score = 0; st.session_state.brain_answered = False; st.rerun()

        with game_tabs[3]:
            st.markdown("#### 🧩 Memory Sequence")
            st.write("Memorize this sequence, then type it back in the same order.")
            if "memory_sequence" not in st.session_state:
                st.session_state.memory_sequence = [random.randint(1, 9) for _ in range(4)]
                st.session_state.memory_length = 4
            st.markdown(f"### `{'  ·  '.join(map(str, st.session_state.memory_sequence))}`")
            memory_guess = st.text_input("Enter the digits without spaces", key="memory_guess")
            if st.button("Check memory", key="memory_check"):
                expected = "".join(map(str, st.session_state.memory_sequence))
                if memory_guess.strip().replace(" ", "") == expected:
                    st.success("Amazing memory! 🎉")
                    st.session_state.memory_sequence = [random.randint(1, 9) for _ in range(min(9, st.session_state.memory_length + 1))]
                    st.session_state.memory_length = min(9, st.session_state.memory_length + 1)
                    st.rerun()
                else: st.error(f"Not quite. The sequence was {expected}. Try a new round!")
            if st.button("Reset memory game", key="memory_reset"):
                st.session_state.memory_length = 4
                st.session_state.memory_sequence = [random.randint(1, 9) for _ in range(4)]
                st.rerun()

        with game_tabs[4]:
            st.markdown("#### 🔢 Mini Sudoku · 4×4")
            st.write("Fill each row and column with 1–4 without repeating a number. This is a mini practice puzzle.")
            sudoku_solution = [[1,2,3,4],[3,4,1,2],[2,1,4,3],[4,3,2,1]]
            sudoku_clues = [[1,0,0,4],[0,4,1,0],[2,0,4,0],[0,3,0,1]]
            if "sudoku_board" not in st.session_state: st.session_state.sudoku_board = [row[:] for row in sudoku_clues]
            sudoku_cols = st.columns(4)
            for ri in range(4):
                row_cols = st.columns(4)
                for ci in range(4):
                    with row_cols[ci]:
                        if sudoku_clues[ri][ci]: st.markdown(f"### {sudoku_clues[ri][ci]}")
                        else:
                            v = st.selectbox(f"R{ri+1}C{ci+1}", [0,1,2,3,4], index=st.session_state.sudoku_board[ri][ci], key=f"sudoku_{ri}_{ci}", format_func=lambda x: "·" if x == 0 else str(x), label_visibility="collapsed")
                            st.session_state.sudoku_board[ri][ci] = v
            if st.button("Check Sudoku", key="sudoku_check", type="primary"):
                if st.session_state.sudoku_board == sudoku_solution: st.success("Solved! 🏆")
                else: st.warning("Not solved yet. Check every row and column; each must contain 1, 2, 3 and 4 once.")
            if st.button("Reset Sudoku", key="sudoku_reset"):
                st.session_state.sudoku_board = [row[:] for row in sudoku_clues]; st.rerun()

        with game_tabs[5]:
            st.markdown("#### 🔤 Word Ladder")
            st.write("Change one letter at a time to turn **COLD** into **WARM**. Use a valid 4-letter word for each step.")
            if "ladder_words" not in st.session_state: st.session_state.ladder_words = ["COLD"]
            st.caption("Your path: " + " → ".join(st.session_state.ladder_words))
            ladder_word = st.text_input("Next four-letter word", max_chars=4, key="ladder_input").strip().upper()
            if st.button("Add word", key="ladder_add"):
                prev = st.session_state.ladder_words[-1]
                if len(ladder_word) != 4 or not ladder_word.isalpha(): st.error("Enter exactly four letters.")
                elif sum(a != b for a,b in zip(prev, ladder_word)) != 1: st.error("Change exactly one letter from the previous word.")
                elif ladder_word in st.session_state.ladder_words: st.error("You've already used that word.")
                else:
                    st.session_state.ladder_words.append(ladder_word)
                    if ladder_word == "WARM": st.success(f"You made it in {len(st.session_state.ladder_words)-1} moves! 🏆")
                    else: st.rerun()
            if st.button("Restart ladder", key="ladder_reset"): st.session_state.ladder_words = ["COLD"]; st.rerun()
            st.caption("Try: CORD → CARD → WARD → WARM")

        with game_tabs[6]:
            st.markdown("#### ➕ Math Sprint")
            if "math_problem" not in st.session_state: st.session_state.math_problem = (random.randint(2,12), random.randint(2,12), random.choice(["+", "−", "×"]))
            a,b,op = st.session_state.math_problem
            correct = a+b if op == "+" else (a-b if op == "−" else a*b)
            st.markdown(f"## {a} {op} {b} = ?")
            math_answer = st.number_input("Your answer", value=0, step=1, key="math_answer")
            if st.button("Check answer", key="math_check"):
                if int(math_answer) == correct: st.success("Correct! ⚡ Fast brain!")
                else: st.error(f"Not quite — the answer is {correct}.")
            if st.button("Next problem", key="math_next"):
                st.session_state.math_problem = (random.randint(2,12), random.randint(2,12), random.choice(["+", "−", "×"]))
                st.rerun()

        with game_tabs[7]:
            st.markdown("#### ♟️ Queens Logic · 4×4")
            st.write("Place four queens on a 4×4 board so no two queens share a row, column, or diagonal. Choose one column for each row.")
            queen_cols = [st.selectbox(f"Queen in row {r+1}", [1,2,3,4], key=f"queen_row_{r}") for r in range(4)]
            if st.button("Check queens", key="queens_check", type="primary"):
                safe = len(set(queen_cols)) == 4 and all(abs(queen_cols[i]-queen_cols[j]) != abs(i-j) for i in range(4) for j in range(i+1,4))
                if safe: st.success("Perfect placement! 👑")
                else: st.warning("Some queens can attack each other. Try another arrangement.")
            st.caption("Hint: try columns 2, 4, 1, 3.")

        with game_tabs[8]:
            st.markdown("#### 🟦 Color Match")
            st.write("Choose the colour named by the word, not the colour used to display it — a quick focus test.")
            colors = {"RED":"#ef4444", "BLUE":"#3b82f6", "GREEN":"#22c55e", "PURPLE":"#a855f7", "ORANGE":"#f97316"}
            if "color_match_word" not in st.session_state:
                st.session_state.color_match_word = random.choice(list(colors))
                st.session_state.color_match_ink = random.choice(list(colors))
            word = st.session_state.color_match_word
            st.markdown(f"<div style='font-size:2.6rem;font-weight:900;text-align:center;color:{colors[st.session_state.color_match_ink]};padding:1rem'>{word}</div>", unsafe_allow_html=True)
            color_choice = st.radio("Which colour is written?", list(colors), horizontal=True, key="color_match_choice")
            if st.button("Submit colour", key="color_match_submit"):
                if color_choice == word: st.success("Correct — great focus! 🎯")
                else: st.error(f"The word says {word}.")
            if st.button("Next colour", key="color_match_next"):
                st.session_state.color_match_word = random.choice(list(colors))
                st.session_state.color_match_ink = random.choice(list(colors))
                st.rerun()

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
