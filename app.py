import re
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

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
    st.markdown("""
    <style>
    .stApp{background:radial-gradient(ellipse at 12% 0%,#172635 0%,#0b0f14 45%);color:#edf2f8}
    [data-testid="stHeader"]{background:rgba(11,15,20,.9)}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#111a25,#0b1017);border-right:1px solid #29384a}
    [data-testid="stSidebar"] *{color:#edf2f8}
    .block-container{max-width:1480px;padding-top:1.6rem;padding-bottom:3rem}
    h1,h2,h3{letter-spacing:-.035em}
    [data-testid="stMetric"]{background:linear-gradient(145deg,#17212d,#111821);border:1px solid #2a394c;padding:18px 20px;border-radius:16px;box-shadow:0 8px 24px #0002}
    [data-testid="stMetricLabel"]{color:#9babc0}[data-testid="stMetricValue"]{color:#f3f7fc;font-weight:750}
    .hero{background:linear-gradient(115deg,#20394acc,#121923eb 70%);border:1px solid #304256;border-radius:20px;padding:24px 28px;margin-bottom:20px}
    .eyebrow{color:#69e2c8;font-size:.76rem;font-weight:800;text-transform:uppercase;letter-spacing:.15em}
    .hero-title{font-size:2rem;line-height:1.12;font-weight:800;margin:.35rem 0 .55rem}
    .hero-copy,.section-note{color:#aab9ca;font-size:.94rem}
    div[data-testid="stTabs"] button{border-radius:10px;padding:10px 15px}
    div[data-testid="stTabs"] button[aria-selected="true"]{background:#1d2c3c;color:#77e6d0}
    [data-testid="stDataFrame"]{border:1px solid #263244;border-radius:12px;overflow:hidden}
    .stButton button[kind="primary"]{background:linear-gradient(90deg,#24b89a,#48d6b4);color:#071411;border:0;font-weight:800;border-radius:10px}
    hr{border-color:#263244}
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



def require_login():
    """Require credentials configured privately in Streamlit Cloud Secrets."""
    try:
        users = dict(st.secrets["auth"]["users"])
    except Exception:
        st.title("Dreamztree Meta Report")
        st.error("Login is not configured yet.")
        st.markdown(
            "To protect your report, add credentials in **Streamlit Cloud → App settings → Secrets**. "
            "Use the setup instructions in README.txt supplied with this app."
        )
        st.stop()

    current_user = st.session_state.get("authenticated_user", "")
    expected_password = str(users.get(current_user, ""))
    current_fingerprint = hashlib.sha256(
        (current_user + "\\0" + expected_password).encode("utf-8")
    ).hexdigest()
    if (
        st.session_state.get("authenticated")
        and current_user in users
        and hmac.compare_digest(
            st.session_state.get("login_fingerprint", ""),
            current_fingerprint,
        )
    ):
        return
    st.session_state["authenticated"] = False
    st.session_state.pop("login_fingerprint", None)

    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {background: radial-gradient(circle at top left, #17283a, #090d13 58%);}
        [data-testid="stHeader"] {background: transparent;}
        .login-panel {max-width: 560px; margin: 5vh auto 0 auto; padding: 2rem;
          border: 1px solid #2b3b50; border-radius: 22px;
          background: linear-gradient(145deg, #151f2c, #0e141d);
          box-shadow: 0 20px 55px rgba(0,0,0,.25);}
        .login-kicker {letter-spacing: .18em; text-transform: uppercase; color: #65e5c6;
          font-size: .75rem; font-weight: 800;}
        </style>
        <div class="login-panel">
          <div class="login-kicker">Dreamztree · Marketing Intelligence</div>
          <h1>Meta Leads Command Center</h1>
          <p>Sign in to access campaign performance and lead reports.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        expected = users.get(username.strip())
        if expected is not None and hmac.compare_digest(password, str(expected)):
            st.session_state["authenticated"] = True
            st.session_state["authenticated_user"] = username.strip()
            st.session_state["login_fingerprint"] = hashlib.sha256(
                (username.strip() + "\\0" + str(expected)).encode("utf-8")
            ).hexdigest()
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    st.stop()


def main():
    require_login()
    inject_premium_theme()
    st.markdown('<div class="hero"><div class="eyebrow">Dreamztree · Marketing intelligence</div><div class="hero-title">Meta Leads Command Center</div><p class="hero-copy">Branch-wise lead volume, campaign assignments and cost reporting in one workspace.</p></div>', unsafe_allow_html=True)
    header_left, header_right = st.columns([5, 1])
    with header_right:
        if st.button("Sign out", use_container_width=True):
            st.session_state["authenticated"] = False
            st.session_state.pop("authenticated_user", None)
            st.session_state.pop("login_fingerprint", None)
            st.rerun()
    st.caption("Upload a Meta Ads Excel export to generate a branch-wise, staff-wise leads report.")
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
