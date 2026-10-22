import re
from datetime import datetime
from pathlib import Path
import pandas as pd
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
KWD_FACTOR = 0.308

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
    """Infer staff, course and branch from campaign names using shared rules for all staff.

    Exact campaign mappings take priority. Otherwise, staff names and known course names
    are matched as whole words, explicit branch names take priority, and a staff member's
    single known/home branch is used when the mapping history is unambiguous.
    """
    raw_name = str(name)
    key = normalize(raw_name)

    exact = mappings[mappings["Campaign"].astype(str).map(normalize) == key]
    if not exact.empty:
        r = exact.iloc[0]
        return str(r["Staff"]), str(r["Course"]), str(r["Branch"]), "Exact mapping"

    tokens = set(key.split())
    # Detect all known staff, even if a staff member has no exact row in this upload.
    known_staff = {str(x).strip() for x in mappings["Staff"] if str(x).strip()}
    for names in STAFF_ORDER.values():
        known_staff.update(names)
    staff_values = sorted(known_staff, key=lambda s: len(normalize(s)), reverse=True)
    course_values = sorted(
        {str(x).strip() for x in mappings["Course"] if str(x).strip()},
        key=lambda c: len(normalize(c)), reverse=True
    )

    # Match staff names as whole words, avoiding accidental substring matches.
    staff_hits = []
    for staff_name in staff_values:
        staff_norm = normalize(staff_name)
        if staff_norm and re.search(r"(?<![a-z0-9])" + re.escape(staff_norm) + r"(?![a-z0-9])", key):
            staff_hits.append(staff_name)
    # Keep the longest match when one staff name is contained in another.
    if staff_hits:
        longest = max(len(normalize(s)) for s in staff_hits)
        staff_hits = [s for s in staff_hits if len(normalize(s)) == longest]

    # Match the most specific known course, using whole-token matching.
    course_hits = [
        c for c in course_values
        if normalize(c) and set(normalize(c).split()).issubset(tokens)
    ]
    course = sorted(course_hits, key=lambda c: len(normalize(c)), reverse=True)[0] if course_hits else ""

    # Recognize common course labels even when the exact phrase is new.
    if not course:
        course_aliases = [
            (r"\bcaregiv(?:er|ing)\b", "Caregiving"),
            (r"\bhealthcare\b|\bhealth care\b", "Healthcare"),
            (r"\bprometric\b", "Prometric"), (r"\bgerman\b", "German"),
            (r"\bielts\b", "IELTS"), (r"\boet\b", "OET"),
            (r"\bcomputer\b|\bms office\b", "Computer"),
            (r"\bautocad\b", "Autocad"), (r"\brevit\b", "Revit"),
            (r"\btuition\b", "Tuition"), (r"\bphonics\b", "Phonics"),
            (r"\bcg\b", "CG"), (r"\bgda\b", "GDA"), (r"\bgna\b", "GNA"),
            (r"\bnursing\b", "Nursing"), (r"\bhospital administration\b|\bhospital admin\b", "Hospital Admin"),
            (r"\bteacher training\b|\bttc\b", "Teacher Training"),
            (r"\bdigital marketing\b", "Digital Marketing"),
            (r"\blogistics\b", "Logistics"), (r"\bsafety\b", "Safety Course"),
            (r"\bspa\b", "Spa"), (r"\bphilip[iy]\b", "Philipi"),
        ]
        for pattern, label in course_aliases:
            if re.search(pattern, key):
                course = label
                break

    explicit_branch = next(
        (b for b in ["Mangaf", "Salmiya", "Bahrain", "Kerala"]
         if re.search(r"(?<![a-z0-9])" + re.escape(normalize(b)) + r"(?![a-z0-9])", key)),
        None
    )

    if len(staff_hits) == 1:
        staff = staff_hits[0]
        staff_rows = mappings[mappings["Staff"].astype(str).str.strip().str.casefold() == staff.casefold()]
        known_branches = [str(x).strip() for x in staff_rows["Branch"] if str(x).strip()]
        branches = sorted(set(known_branches))
        # Use the established staff-to-branch roster when there is exactly one home branch.
        # A campaign's explicit branch always overrides the roster. Staff listed in multiple
        # branches (for example Aswathy) still need a branch marker or exact mapping.
        roster_branches = [b for b, names in STAFF_ORDER.items() if staff.casefold() in {n.casefold() for n in names}]
        if explicit_branch:
            branch = explicit_branch
            branch_status = "explicit branch"
        elif len(roster_branches) == 1:
            branch = roster_branches[0]
            branch_status = "staff roster"
        elif len(branches) == 1:
            branch = branches[0]
            branch_status = "staff branch"
        else:
            # If this campaign omits the branch but the mapping history has the same
            # staff + course + date, reuse that known branch (e.g. Aswathy CG 16/10/2026
            # can match the saved Aswathy CG Kerala 16/10/2026 mapping).
            date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", raw_name)
            same_staff = mappings[mappings["Staff"].astype(str).str.strip().str.casefold() == staff.casefold()]
            if course:
                same_staff = same_staff[same_staff["Course"].astype(str).map(normalize) == normalize(course)]
            if date_match:
                date_bits = tuple(date_match.groups())
                def has_same_date(value):
                    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", str(value))
                    return bool(m and tuple(m.groups()) == date_bits)
                same_staff = same_staff[same_staff["Campaign"].map(has_same_date)]
            candidate_branches = sorted({str(x).strip() for x in same_staff["Branch"] if str(x).strip()})
            if len(candidate_branches) == 1:
                branch = candidate_branches[0]
                branch_status = "matched staff/course/date"
            else:
                branch = ""
                branch_status = "uncertain branch"

        # For names such as 'Anupama : Caregiving Course 3/3/26', recognize the staff
        # and caregiving course, then use Anupama's known Kerala branch from mappings.
        if staff and course and branch:
            status = "Inferred from name" if explicit_branch else "Inferred from staff/course"
            return staff, course, branch, status
        return staff, course, branch, "Needs review"

    return "", course, explicit_branch or "", "Needs review"

def main():
    st.title("🌴 Dreamztree Meta Leads Report")
    st.caption("Upload a Meta Ads Excel export to generate a branch-wise, staff-wise leads report.")
    with st.sidebar:
        st.header("Settings")
        date_value = st.date_input("Report date", value=datetime.today().date())
        factor = st.number_input("USD to KD conversion factor", min_value=0.0, value=KWD_FACTOR, step=0.001, format="%.3f")
        st.caption("Verify the conversion factor used by your organization before relying on cost totals.")
        mapping_upload = st.file_uploader("Optional campaign mapping file", type=["xlsx", "xls", "csv"])
        st.caption("Mapping columns: Campaign, Staff, Course, Branch.")
    mappings = read_mapping_file(mapping_upload)
    st.subheader("1. Upload Meta Ads report")
    uploaded = st.file_uploader("Choose Excel file", type=["xlsx", "xls"], key="meta_excel")
    if uploaded is None:
        st.info("Upload your Meta Ads Excel export to begin.")
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
        df = df[(df["Results"] > 0) & (df["Results"] < 10000)].reset_index(drop=True)
        st.success(f"Loaded {len(df)} campaigns with {int(df['Results'].sum())} total results.")
        st.subheader("2. Review campaign assignments")
        assignments = []
        for _, r in df.iterrows():
            staff, course, branch, status = infer_campaign(r["Campaign"], mappings)
            assignments.append({"Campaign": r["Campaign"], "Results": int(r["Results"]), "Spent": float(r["Spent"]), "Staff": staff, "Course": course, "Branch": branch, "Status": status})
        assigned = pd.DataFrame(assignments)
        unresolved_preview = assigned[(assigned["Staff"].astype(str).str.strip() == "") | (assigned["Course"].astype(str).str.strip() == "") | (assigned["Branch"].astype(str).str.strip() == "")]
        if not unresolved_preview.empty:
            st.error(f"⚠️ {len(unresolved_preview)} campaign(s) need review. The rows below are highlighted; complete their Staff, Course and Branch fields before generating the report.")
            def highlight_review_rows(row):
                return ["background-color: #5b1f24; color: #ffffff; font-weight: 600;"] * len(row)
            st.dataframe(unresolved_preview.style.apply(highlight_review_rows, axis=1), use_container_width=True, hide_index=True)
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
            st.warning(f"{len(unresolved)} campaign(s) need staff/course/branch review. They will not be included in the grouped report until you fill the missing fields.")
        if st.button("Generate report", type="primary"):
            valid = edited[(edited["Staff"].astype(str).str.strip() != "") & (edited["Course"].astype(str).str.strip() != "") & (edited["Branch"].astype(str).str.strip() != "")]
            if valid.empty:
                st.error("No campaigns have complete assignments. Review the assignment table first.")
                return
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
            st.metric("Total leads included", f"{grand_leads:,}")
            st.metric("Total cost", f"{round(grand_spent * factor, 2):.2f} KD")
            st.caption(f"{len(unresolved)} campaign(s) require review if left incomplete.")
    except Exception as e:
        st.error(f"Could not process this Excel file: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
