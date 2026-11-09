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
from streamlit_cookies_controller import CookieController, RemoveEmptyElementContainer
from cryptography.fernet import Fernet, InvalidToken

st.set_page_config(page_title="Dreamztree Meta Report", page_icon="D", layout="wide")

# Encrypted browser cookie used only to restore authentication after a reload.
_AUTH_COOKIE_NAME = "dt_auth_session_v1"
_AUTH_COOKIE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days; Supabase refresh token rules still apply.
# Keep one cookie-controller instance per Streamlit browser session. A module-level
# controller can accidentally share component state between concurrent sessions.
if "_dt_auth_cookie_controller" not in st.session_state:
    st.session_state["_dt_auth_cookie_controller"] = CookieController(
        key="dreamztree_auth_cookie_controller"
    )
_auth_cookie_controller = st.session_state["_dt_auth_cookie_controller"]
RemoveEmptyElementContainer()


def _auth_cipher():
    """Load the server-side Fernet key from Streamlit Secrets or environment."""
    key = str(os.environ.get("AUTH_COOKIE_KEY", "")).strip()
    if not key:
        try:
            key = str(st.secrets["AUTH_COOKIE_KEY"]).strip()
        except Exception:
            key = ""
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except Exception:
        st.error("AUTH_COOKIE_KEY is invalid. Add a valid Fernet key in Streamlit Secrets.")
        return None


def _save_auth_cookie(payload):
    """Persist an encrypted, short-lived auth payload in the user's browser."""
    cipher = _auth_cipher()
    if cipher is None:
        st.error("Persistent login is not configured. Add AUTH_COOKIE_KEY to Streamlit Secrets.")
        return False
    try:
        token = cipher.encrypt(json.dumps(payload).encode("utf-8")).decode("ascii")
        # The installed streamlit-cookies-controller 0.0.4 API documents
        # set(name, value). Avoid unsupported keyword arguments.
        _auth_cookie_controller.set(_AUTH_COOKIE_NAME, token)
        # The component writes in the browser asynchronously. Give it time to
        # commit the cookie before the login flow triggers a Streamlit rerun.
        time.sleep(1.0)
        return True
    except Exception as exc:
        st.warning(f"Could not save the persistent login cookie: {exc}")
        return False


def _delete_auth_cookie():
    try:
        _auth_cookie_controller.remove(_AUTH_COOKIE_NAME)
    except Exception:
        pass


def _restore_auth_cookie(client):
    """Restore a signed-in user and retain a safe diagnostic if restoration fails."""
    if st.session_state.get("authenticated"):
        return True
    st.session_state.pop("_dt_auth_restore_error", None)

    try:
        cookies = _auth_cookie_controller.getAll()
        if not isinstance(cookies, dict) or _AUTH_COOKIE_NAME not in cookies:
            time.sleep(1.0)
            cookies = _auth_cookie_controller.getAll()
    except Exception as exc:
        st.session_state["_dt_auth_restore_error"] = (
            "The browser cookie component could not be read (" + type(exc).__name__ + ")."
        )
        return False

    if not isinstance(cookies, dict):
        st.session_state["_dt_auth_restore_error"] = "The browser cookie component has not finished loading."
        return False

    encrypted = cookies.get(_AUTH_COOKIE_NAME)
    if not encrypted:
        # A missing cookie is normal for a first-time visitor or a signed-out user.
        # Do not expose it as an authentication error on the public login screen.
        return False

    cipher = _auth_cipher()
    if cipher is None:
        st.session_state["_dt_auth_restore_error"] = "AUTH_COOKIE_KEY is missing or is not a valid Fernet key."
        return False
    try:
        payload = json.loads(cipher.decrypt(str(encrypted).encode("ascii"), ttl=_AUTH_COOKIE_TTL_SECONDS))
    except InvalidToken:
        # Do not delete the cookie yet: preserve evidence while diagnosing.
        st.session_state["_dt_auth_restore_error"] = (
            "The cookie could not be decrypted or has expired. Check that AUTH_COOKIE_KEY "
            "has not changed since the cookie was created."
        )
        return False
    except (ValueError, TypeError, json.JSONDecodeError):
        st.session_state["_dt_auth_restore_error"] = "The decrypted session data is not valid JSON."
        return False
    except Exception as exc:
        st.session_state["_dt_auth_restore_error"] = "Cookie decoding failed (" + type(exc).__name__ + ")."
        return False

    if not isinstance(payload, dict):
        st.session_state["_dt_auth_restore_error"] = "The session cookie does not contain a valid session record."
        return False

    method = payload.get("method")
    if method == "legacy":
        username = str(payload.get("username", "")).strip()
        if not username:
            st.session_state["_dt_auth_restore_error"] = "The legacy session cookie has no username."
            return False
        try:
            legacy_users = dict(st.secrets["auth"]["users"])
        except Exception:
            legacy_users = {}
        env_admin_user = os.environ.get("ADMIN_USERNAME", "").strip()
        env_admin_password = os.environ.get("ADMIN_PASSWORD", "")
        if env_admin_user and env_admin_password:
            legacy_users.setdefault(env_admin_user, env_admin_password)
        if username not in legacy_users:
            st.session_state["_dt_auth_restore_error"] = (
                "The cookie belongs to a legacy username that is not present in the current admin configuration."
            )
            return False
        st.session_state["authenticated"] = True
        st.session_state["authenticated_user"] = username
        st.session_state["auth_method"] = "legacy"
        return True

    if method == "supabase":
        refresh_token = str(payload.get("refresh_token", "")).strip()
        if not refresh_token or client is None:
            st.session_state["_dt_auth_restore_error"] = "The Supabase refresh token is missing or Supabase is not configured."
            return False
        try:
            refreshed = client.auth.refresh_session(refresh_token)
            session = getattr(refreshed, "session", None)
            user = getattr(refreshed, "user", None)
            if not session or not user:
                st.session_state["_dt_auth_restore_error"] = "Supabase did not return a valid refreshed session and user."
                return False
            st.session_state["supabase_access_token"] = session.access_token
            st.session_state["supabase_refresh_token"] = session.refresh_token
            st.session_state["authenticated"] = True
            st.session_state["authenticated_user"] = user.email or payload.get("email", "")
            st.session_state["auth_method"] = "supabase"
            try:
                client.auth.set_session(session.access_token, session.refresh_token)
            except Exception:
                pass
            _save_auth_cookie({
                "method": "supabase",
                "refresh_token": session.refresh_token,
                "email": user.email or payload.get("email", ""),
            })
            return True
        except Exception as exc:
            # Preserve the cookie during diagnosis; the next login can overwrite it.
            st.session_state["_dt_auth_restore_error"] = (
                "Supabase rejected or could not refresh the saved session (" + type(exc).__name__ + ")."
            )
            return False

    st.session_state["_dt_auth_restore_error"] = "The session cookie contains an unknown authentication method."
    return False

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
        (r"\ball\s+courses?\b", "All Course"),
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
        # Keep hiring campaigns separate from regular tuition campaigns.
        (r"\btuition\s+hiring\b|\btution\s+hiring\b", "Tuition Hiring"),
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

    # Treat "Hiring" as a campaign qualifier for EVERY course/staff member.
    # Examples: "Nissi | Tuition Hiring", "Arya | Caregiver Hiring",
    # or "New Staff | German | Hiring" are classified separately from
    # their non-hiring course campaigns without adding person-specific rules.
    has_hiring_qualifier = bool(re.search(r"\bhiring\b", key))
    if has_hiring_qualifier and course and not course.lower().endswith("hiring"):
        course = f"{course} Hiring"

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
    """Apply a restrained, minimal dark theme without changing app functionality."""
    st.markdown("""
    <style>
    :root {
      --dt-bg: #111318;
      --dt-panel: #191d24;
      --dt-panel-soft: #202630;
      --dt-border: #303743;
      --dt-text: #edf0f5;
      --dt-muted: #9aa4b2;
      --dt-accent: #a78bfa;
      --dt-accent-soft: rgba(167,139,250,.12);
    }

    .stApp {
      background: var(--dt-bg);
      color: var(--dt-text);
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"] {
      background: transparent;
    }

    [data-testid="stHeader"] {
      background: rgba(17,19,24,.94);
      border-bottom: 1px solid var(--dt-border);
    }

    [data-testid="stSidebar"] {
      background: #151920;
      border-right: 1px solid var(--dt-border);
    }
    [data-testid="stSidebar"] * {
      color: var(--dt-text);
    }

    .block-container {
      max-width: 1440px;
      padding-top: 1.5rem;
      padding-bottom: 2.5rem;
    }

    h1, h2, h3, h4 {
      color: #f5f6f8;
      letter-spacing: -.025em;
      font-weight: 650;
    }
    h1 { font-size: 2rem; }
    h2 { font-size: 1.45rem; }
    h3 { font-size: 1.12rem; }

    p, label, [data-testid="stMarkdownContainer"] {
      color: var(--dt-text);
    }
    [data-testid="stCaptionContainer"], .section-note {
      color: var(--dt-muted);
    }

    .hero {
      background: #191e27;
      border: 1px solid var(--dt-border);
      border-left: 3px solid var(--dt-accent);
      border-radius: 12px;
      padding: 22px 24px;
      margin-bottom: 20px;
      box-shadow: none;
      animation: none;
    }
    .eyebrow {
      color: #b9a5ff;
      font-size: .72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .12em;
    }
    .hero-title {
      color: #f5f6f8;
      font-size: clamp(1.55rem, 2.5vw, 2.1rem);
      line-height: 1.2;
      font-weight: 700;
      margin: .4rem 0 .5rem;
      background: none;
      -webkit-text-fill-color: currentColor;
      animation: none;
    }
    .hero-copy {
      color: var(--dt-muted);
      font-size: .94rem;
    }

    [data-testid="stMetric"] {
      background: var(--dt-panel);
      border: 1px solid var(--dt-border);
      border-radius: 12px;
      padding: 16px 18px;
      box-shadow: none;
      animation: none;
      transition: border-color .15s ease;
    }
    [data-testid="stMetric"]:hover {
      border-color: #596273;
      transform: none;
      box-shadow: none;
    }
    [data-testid="stMetricLabel"] {
      color: var(--dt-muted) !important;
      font-size: .82rem;
    }
    [data-testid="stMetricValue"] {
      color: #f5f6f8 !important;
      font-weight: 700;
    }
    [data-testid="stMetricDelta"] {
      font-weight: 600;
    }

    div[data-testid="stTabs"] {
      border-bottom: 1px solid var(--dt-border);
    }
    div[data-testid="stTabs"] button {
      color: var(--dt-muted);
      border-radius: 7px 7px 0 0;
      padding: 9px 13px;
      transition: color .15s ease, background .15s ease;
    }
    div[data-testid="stTabs"] button:hover {
      color: var(--dt-text);
      background: var(--dt-accent-soft);
      transform: none;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
      color: #d8ccff;
      background: var(--dt-accent-soft);
      border-bottom: 2px solid var(--dt-accent);
    }
    div[data-testid="stTabs"] button[aria-selected="true"] p {
      color: #d8ccff !important;
      font-weight: 650;
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
      border: 1px solid var(--dt-border);
      border-radius: 10px;
      overflow: hidden;
      animation: none;
      box-shadow: none;
    }

    [data-testid="stFileUploader"] {
      background: var(--dt-panel);
      border: 1px dashed #596273;
      border-radius: 10px;
      padding: 8px;
      animation: none;
    }
    [data-testid="stFileUploader"]:hover {
      border-color: var(--dt-accent);
      transform: none;
    }

    [data-testid="stExpander"] {
      background: var(--dt-panel);
      border: 1px solid var(--dt-border);
      border-radius: 10px;
      box-shadow: none;
    }
    [data-testid="stExpander"]:hover {
      border-color: #596273;
      box-shadow: none;
    }

    .stButton button,
    [data-testid="stDownloadButton"] button {
      background: #29243a;
      color: #eee9ff;
      border: 1px solid #51466f;
      border-radius: 8px;
      font-weight: 600;
      box-shadow: none;
      animation: none;
      transition: background .15s ease, border-color .15s ease;
    }
    .stButton button:hover,
    [data-testid="stDownloadButton"] button:hover {
      background: #352d4a;
      border-color: var(--dt-accent);
      color: #fff;
      transform: none;
      box-shadow: none;
    }
    .stButton button[kind="primary"],
    button[kind="primary"] {
      background: #7658c8;
      color: #fff;
      border: 1px solid #7658c8;
      box-shadow: none;
      font-weight: 650;
    }
    .stButton button[kind="primary"]:hover,
    button[kind="primary"]:hover {
      background: #866bd2;
      border-color: #866bd2;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"],
    [data-testid="stMultiSelect"] div[data-baseweb="select"] {
      border-radius: 8px;
    }

    [data-testid="stAlert"] {
      border-radius: 9px;
      border: 1px solid var(--dt-border);
    }

    hr {
      border-color: var(--dt-border);
    }
    a { color: #b9a5ff !important; }

    .arcade-banner {
      margin: 1rem 0;
      padding: 1.2rem 1.4rem;
      border-radius: 12px;
      border: 1px solid #51466f;
      background: #211d2d;
      box-shadow: none;
      animation: none;
    }
    .arcade-banner h2 {
      margin: .3rem 0;
      color: #f5f1ff;
    }
    .arcade-banner p { color: #c9c1d9; }
    .arcade-kicker {
      color: #c7b6ff;
      font-size: .72rem;
      font-weight: 700;
      letter-spacing: .12em;
    }

    @media (max-width: 700px) {
      .block-container { padding-top: 1rem; }
      .hero { padding: 18px; }
      [data-testid="stMetric"] { padding: 13px; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        scroll-behavior: auto !important;
      }
    }
    </style>
    """, unsafe_allow_html=True)


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




def require_login():
    """Use Supabase Auth for colleague registration and sign-in.

    Optional legacy admin credentials in [auth.users] remain supported so the
    existing administrator can still sign in during the transition.
    """
    if st.session_state.get("authenticated"):
        return

    client = get_supabase_client()
    if _restore_auth_cookie(client):
        return
    # Cookie restoration diagnostics stay in session state for server-side
    # troubleshooting; never display implementation details to end users.
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

    # Minimal, accessible authentication screen. No decorative animation,
    # dim overlay, theme cycling, or interaction gate before the form appears.
    st.markdown("""
    <style>
      [data-testid="stAppViewContainer"] { background: #101214 !important; }
      [data-testid="stHeader"] { background: transparent !important; }
      .block-container { max-width: 1120px; padding-top: 3rem; }
      .dt-auth-shell { max-width: 440px; margin: 3vh auto 0; padding: 30px;
        background: #191c20; border: 1px solid #30353b; border-radius: 16px; }
      .dt-auth-kicker { color: #a3aab4; font-size: 12px; letter-spacing: .12em;
        text-transform: uppercase; margin-bottom: 8px; }
      .dt-auth-title { color: #f5f6f7; font-size: 28px; font-weight: 650;
        letter-spacing: -.04em; margin: 0 0 6px; }
      .dt-auth-subtitle { color: #a3aab4; font-size: 14px; margin: 0 0 22px; }
      [data-testid="stTabs"] button { color: #b8bec7; }
      [data-testid="stTabs"] button[aria-selected="true"] { color: #f5f6f7; }
      [data-testid="stTextInput"] label { color: #d7dbe0; }
      [data-testid="stTextInput"] input { background: #111417; border: 1px solid #39414a;
        border-radius: 9px; color: #f5f6f7; min-height: 44px; }
      [data-testid="stTextInput"] input:focus { border-color: #8b95a3;
        box-shadow: 0 0 0 1px #8b95a3; }
      [data-testid="stForm"] button[kind="primary"],
      [data-testid="stForm"] button[data-testid="stFormSubmitButton"] {
        background: #f1f3f5 !important; color: #17191c !important;
        border: 1px solid #f1f3f5 !important; border-radius: 9px;
        min-height: 44px; font-weight: 600; box-shadow: none !important; }
      [data-testid="stForm"] button[kind="primary"]:hover { background: #dfe3e7 !important; }
      [data-testid="stAlert"] { border-radius: 10px; }
      @media (max-width: 640px) { .block-container { padding: 1.2rem 1rem; }
        .dt-auth-shell { margin-top: 1rem; padding: 22px; } }
    </style>
    <div class="dt-auth-shell">
      <div class="dt-auth-kicker">Dreamztree · Marketing Analytics</div>
      <div class="dt-auth-title">Welcome back</div>
      <div class="dt-auth-subtitle">Sign in to access your campaign reports.</div>
    </div>
    """, unsafe_allow_html=True)

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
                    _save_auth_cookie({"method": "legacy", "username": login_id})
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
                                _save_auth_cookie({"method": "supabase", "refresh_token": response.session.refresh_token, "email": response.user.email or login_id})
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
                        _save_auth_cookie({"method": "supabase", "refresh_token": response.session.refresh_token, "email": response.user.email or new_email})
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





def inject_performance_patch():
    """Keep dashboard rendering lightweight by disabling decorative transitions."""
    st.markdown("""
    <style>
      .stApp, .stApp::before, .stApp::after,
      [data-testid="stMetric"], [data-testid="stFileUploader"],
      .stButton button, [data-testid="stDownloadButton"] button {
        animation: none !important;
        background-attachment: scroll !important;
      }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
      }
    </style>
    """, unsafe_allow_html=True)


def main():
    require_login()
    inject_premium_theme()
    inject_performance_patch()
    page = st.query_params.get("page", "dashboard")
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
    # Compact dashboard header; remove the duplicate welcome panel and oversized hero.
    st.markdown("""
    <div style="padding:8px 0 16px;border-bottom:1px solid #30353b;margin-bottom:18px">
      <div style="font-size:12px;letter-spacing:.12em;color:#8e9aa8;font-weight:700">DREAMZTREE</div>
      <div style="font-size:24px;font-weight:700;color:#f3f4f6;margin-top:4px">Marketing Intelligence</div>
      <div style="font-size:13px;color:#9ca3af;margin-top:4px">Meta Ads performance and lead reporting</div>
    </div>
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
            _delete_auth_cookie()
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
        with st.expander("Campaign mapping preview", expanded=False):
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
