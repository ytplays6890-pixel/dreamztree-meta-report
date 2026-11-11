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
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from ai_features import get_ai_config, generate_ai_response, build_ai_metrics, rule_based_insights, forecast_from_daily_totals, answer_report_question, build_local_management_summary
from intelligence_dashboard import render_intelligence_dashboard
import streamlit.components.v1 as components
from supabase import create_client
from streamlit_cookies_controller import CookieController, RemoveEmptyElementContainer
from cryptography.fernet import Fernet, InvalidToken


def build_daily_report_files(report_date, leads, spend_kwd, market_rows, hiring, branch_rows):
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(.55); sec.bottom_margin = Inches(.55)
    sec.left_margin = Inches(.65); sec.right_margin = Inches(.65)
    doc.styles["Normal"].font.name = "Aptos"
    doc.styles["Normal"].font.size = Pt(9)
    def shade(cell, fill):
        tcPr=cell._tc.get_or_add_tcPr()
        shd=OxmlElement("w:shd"); shd.set(qn("w:fill"),fill); tcPr.append(shd)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    x=p.add_run("DREAMZTREE"); x.bold=True; x.font.size=Pt(12); x.font.color.rgb=RGBColor(15,116,110)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    x=p.add_run("DAILY LEAD GENERATION REPORT"); x.bold=True; x.font.size=Pt(19)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run(report_date.strftime("%d %b %Y")).italic=True
    total_hiring=sum(int(v) for v in hiring.values())
    def heading(txt):
        p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(10)
        x=p.add_run(txt); x.bold=True; x.font.size=Pt(12); x.font.color.rgb=RGBColor(15,116,110)
    def add_table(headers, rows):
        t=doc.add_table(rows=1,cols=len(headers)); t.style="Table Grid"; t.alignment=WD_TABLE_ALIGNMENT.CENTER
        for i,h in enumerate(headers):
            c=t.rows[0].cells[i]; c.text=str(h); shade(c,"17324D")
            for rr in c.paragraphs[0].runs: rr.bold=True; rr.font.color.rgb=RGBColor(255,255,255)
        for row in rows:
            cells=t.add_row().cells
            for i,val in enumerate(row): cells[i].text=str(val)
        return t
    heading("Overall Performance")
    add_table(["Total Leads","Hiring","Total Ad Spend"],[[f"{leads:,}",f"{total_hiring:,}",f"{spend_kwd:.3f} KD"]])
    heading("Market Performance")
    rows=[[n,f"{int(l):,}",f"{int(hiring.get(n,0)):,}",f"{float(sp):.3f} KD"] for n,l,sp in market_rows]
    rows.append(["Total",f"{leads:,}",f"{total_hiring:,}",f"{spend_kwd:.3f} KD"])
    add_table(["Market","Leads","Hiring","Ad Spend"],rows)
    heading("Kuwait Lead Breakdown")
    add_table(["Branch","Leads"],[[n,f"{int(v):,}"] for n,v in branch_rows])
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    x=p.add_run("Dreamztree Training Academy | Daily Marketing Performance"); x.italic=True; x.font.size=Pt(8)
    word=io.BytesIO(); doc.save(word)
    styles=getSampleStyleSheet()
    title=ParagraphStyle("DTTitle",parent=styles["Title"],fontSize=18,textColor=colors.HexColor("#1c2738"),alignment=1)
    section=ParagraphStyle("DTSection",parent=styles["Heading2"],fontSize=12,textColor=colors.HexColor("#0f746e"),spaceBefore=12,spaceAfter=6)
    story=[Paragraph("DREAMZTREE",ParagraphStyle("Brand",parent=title,fontSize=11,textColor=colors.HexColor("#0f746e"))),Paragraph("DAILY LEAD GENERATION REPORT",title),Paragraph(report_date.strftime("%d %b %Y"),ParagraphStyle("Date",parent=styles["Normal"],alignment=1))]
    def pdf_table(data):
        t=Table(data,repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#d8dee8")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f3f6f9")]),("PADDING",(0,0),(-1,-1),7)]))
        story.append(t)
    story.append(Paragraph("Overall Performance",section))
    pdf_table([["Total Leads","Hiring","Total Ad Spend"],[f"{leads:,}",f"{total_hiring:,}",f"{spend_kwd:.3f} KD"]])
    story.append(Paragraph("Market Performance",section))
    pdf_table([["Market","Leads","Hiring","Ad Spend"]]+[[n,f"{int(l):,}",f"{int(hiring.get(n,0)):,}",f"{float(sp):.3f} KD"] for n,l,sp in market_rows]+[["Total",f"{leads:,}",f"{total_hiring:,}",f"{spend_kwd:.3f} KD"]])
    story.append(Paragraph("Kuwait Lead Breakdown",section))
    pdf_table([["Branch","Leads"]]+[[n,f"{int(v):,}"] for n,v in branch_rows])
    pdfbuf=io.BytesIO(); SimpleDocTemplate(pdfbuf,pagesize=A4,rightMargin=17*mm,leftMargin=17*mm).build(story)
    return word.getvalue(),pdfbuf.getvalue()


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

# The lamp pull is a small Streamlit custom component so pointer dragging can
# redraw the real SVG cord in the browser (st.markdown scripts cannot do this).
_DT_LAMP_COMPONENT_DIR = Path(__file__).resolve().parent / ".dt_lamp_drag_component"
_DT_LAMP_COMPONENT_DIR.mkdir(parents=True, exist_ok=True)
_DT_LAMP_COMPONENT_HTML = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}*{box-sizing:border-box}
#stage{position:relative;width:72px;height:250px;background:transparent;touch-action:none;user-select:none;-webkit-user-select:none}
svg{position:absolute;inset:0;width:72px;height:250px;overflow:visible;touch-action:none}
#cord{fill:none;stroke:#17191d;stroke-width:2.2;stroke-linecap:round;filter:drop-shadow(0 1px 1px #000)}
#highlight{fill:none;stroke:rgba(210,215,225,.34);stroke-width:.65;stroke-linecap:round}
#bead{cursor:grab;touch-action:none;filter:drop-shadow(0 2px 2px rgba(0,0,0,.7))}
#bead:active{cursor:grabbing}
#beadCore{fill:url(#gold);stroke:#6f4b16;stroke-width:.8}
#shine{fill:none;stroke:rgba(255,245,190,.85);stroke-width:1.1;stroke-linecap:round}
</style></head><body><div id="stage" aria-label="Pull the lamp cord">
<svg viewBox="0 0 72 250" role="img" aria-label="Lamp pull cord">
<defs><linearGradient id="gold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9b6c24"/><stop offset=".32" stop-color="#f1ca69"/><stop offset=".58" stop-color="#fff0aa"/><stop offset="1" stop-color="#a87322"/></linearGradient></defs>
<path id="cord" d="M36 0 Q36 84 36 183"/><path id="highlight" d="M36.6 1 Q36.6 84 36.6 183"/>
<g id="bead" transform="translate(36 183)"><circle id="beadCore" r="6.1"/><path id="shine" d="M-2.5 -3.4 Q-4 -1.8 -3.3 .2"/></g>
</svg></div>
<script>
(function(){
 const stage=document.getElementById('stage'),cord=document.getElementById('cord'),hi=document.getElementById('highlight'),bead=document.getElementById('bead');
 const anchorX=36, restY=183; let drag=false,startY=0,offsetY=0,offsetX=0,raf=0,pulls=0,velocity=0,lastY=0,lastT=0;
 function draw(x,y){const bend=x*.24;const midY=(restY+y)*.5;const d=`M ${anchorX} 0 Q ${anchorX+bend} ${midY} ${anchorX+x} ${restY+y}`;cord.setAttribute('d',d);hi.setAttribute('d',`M ${anchorX+.7} 1 Q ${anchorX+bend+.7} ${midY} ${anchorX+x+.7} ${restY+y}`);bead.setAttribute('transform',`translate(${anchorX+x} ${restY+y})`)}
 function spring(){cancelAnimationFrame(raf);let y=offsetY,v=velocity,x=offsetX;let prev=performance.now(),start=prev;function tick(now){const dt=Math.min((now-prev)/1000,.032);prev=now;const a=-210*y-25*v;v+=a*dt;y+=v*dt;if(Math.abs(y)<.16&&Math.abs(v)<1.2){y=0;draw(0,0);return}draw(x*Math.exp(-(now-start)*.012),y);raf=requestAnimationFrame(tick)}raf=requestAnimationFrame(tick)}
 function down(e){if(e.button!==undefined&&e.button!==0)return;drag=true;stage.setPointerCapture?.(e.pointerId);bead.setPointerCapture?.(e.pointerId);startY=e.clientY;lastY=startY;lastT=performance.now();offsetY=0;velocity=0;cancelAnimationFrame(raf);e.preventDefault()}
 function move(e){if(!drag)return;const now=performance.now(),dt=Math.max(.008,(now-lastT)/1000);const dy=e.clientY-startY;offsetY=Math.max(0,Math.min(86,dy));offsetX=Math.max(-18,Math.min(18,(e.clientX-(stage.getBoundingClientRect().left+anchorX))*.3));velocity=(e.clientY-lastY)/dt;lastY=e.clientY;lastT=now;draw(offsetX,offsetY);e.preventDefault()}
 function up(e){if(!drag)return;drag=false;const pulled=offsetY>8;const releaseY=offsetY;velocity=Math.max(-500,Math.min(500,velocity*.45));if(!pulled){offsetY=0;offsetX=0;draw(0,0);return}pulls++;window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',value:{pulls:pulls,stamp:Date.now()}},'*');offsetY=releaseY;spring();e.preventDefault()}
 bead.addEventListener('pointerdown',down);stage.addEventListener('pointermove',move);stage.addEventListener('pointerup',up);stage.addEventListener('pointercancel',up);stage.addEventListener('lostpointercapture',()=>{if(drag){drag=false;spring()}});
 window.addEventListener('message',e=>{const d=e.data||{};if(d.type==='streamlit:render'){if(d.args&&typeof d.args.pulls==='number')pulls=Math.max(pulls,d.args.pulls);}});
 window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:componentReady',apiVersion:1},'*');window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setFrameHeight',height:250},'*');draw(0,0);
})();
</script></body></html>'''
_DT_LAMP_COMPONENT_FILE = _DT_LAMP_COMPONENT_DIR / "index.html"
if not _DT_LAMP_COMPONENT_FILE.exists() or _DT_LAMP_COMPONENT_FILE.read_text(encoding="utf-8") != _DT_LAMP_COMPONENT_HTML:
    _DT_LAMP_COMPONENT_FILE.write_text(_DT_LAMP_COMPONENT_HTML, encoding="utf-8")
_dt_lamp_drag = components.declare_component("dt_lamp_drag", path=str(_DT_LAMP_COMPONENT_DIR))

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
    ("Arun | Healthcare | 6/11/26", "Arun", "Healthcare", "Salmiya"),
    ("Arun | Digital Marketing | 6/11/26", "Arun", "Digital Marketing", "Salmiya"),
    ("Arun | SPA | 6/11/26", "Arun", "SPA", "Salmiya"),
]

BRANCH_ORDER = ["Mangaf", "Salmiya", "Bahrain", "Kerala"]
STAFF_ORDER = {
    "Mangaf": ["Jincy", "Sethu", "Nissi", "Sushma", "Aswathy"],
    "Salmiya": ["Arun", "Arya", "Ligin", "Aswathy"],
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
        "Arun": "Salmiya", "Arya": "Salmiya", "Ligin": "Salmiya",
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
        (r"\boffice\s+management\b", "Office Management"),
        (r"\bhigher\s+education\b", "Higher Education"),
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
    """Dreamztree charcoal premium theme with restrained, app-wide motion."""
    st.markdown(r"""
    <style>
    :root {
      --dt-bg:#17191c; --dt-sidebar:#141619; --dt-panel:#202328;
      --dt-panel-raised:#272b31; --dt-border:#30353c; --dt-text:#f5f6f7;
      --dt-muted:#9ba2ac; --dt-accent:#8b5cf6; --dt-accent-soft:rgba(139,92,246,.16);
      --dt-success:#35b879; --dt-warning:#e6a943; --dt-danger:#e26767;
      --dt-fast:150ms; --dt-motion:180ms; --dt-slow:250ms;
      color-scheme:dark;
    }
    @keyframes dt-enter { from{opacity:0;transform:translateY(7px)} to{opacity:1;transform:translateY(0)} }
    @keyframes dt-ambient {
      0%,100%{background-position:0% 0%,100% 100%}
      50%{background-position:5% 4%,95% 96%}
    }
    @keyframes dt-shimmer { 0%{background-position:-180% 0} 100%{background-position:180% 0} }

    .stApp {
      background:
        radial-gradient(ellipse at 12% 8%,rgba(139,92,246,.055),transparent 35%),
        radial-gradient(ellipse at 88% 82%,rgba(74,115,151,.045),transparent 38%),
        var(--dt-bg) !important;
      background-size:120% 120%,120% 120%,auto;
      animation:dt-ambient 36s ease-in-out infinite;
      color:var(--dt-text);
    }
    [data-testid="stAppViewContainer"],[data-testid="stMainBlockContainer"]{background:transparent}
    [data-testid="stHeader"]{background:rgba(20,22,25,.9);border-bottom:1px solid var(--dt-border);backdrop-filter:blur(12px)}
    [data-testid="stSidebar"]{background:var(--dt-sidebar);border-right:1px solid var(--dt-border);transition:width var(--dt-slow) ease}
    [data-testid="stSidebar"] *{color:var(--dt-text)}
    .block-container{max-width:1460px;padding-top:.55rem;padding-bottom:2.5rem}
    h1,h2,h3,h4{color:var(--dt-text);letter-spacing:-.025em;font-weight:650}
    p,label,[data-testid="stMarkdownContainer"]{color:var(--dt-text)}
    [data-testid="stCaptionContainer"],.section-note{color:var(--dt-muted)}

    .hero{
      background:linear-gradient(145deg,#24282e,#1d2025);
      border:1px solid var(--dt-border);border-left:3px solid var(--dt-accent);
      border-radius:14px;padding:22px 24px;margin-bottom:20px;
      box-shadow:0 8px 26px rgba(0,0,0,.12);
      animation:dt-enter 420ms ease-out both;
    }
    .eyebrow{color:#aaa6f4;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em}
    .hero-title{color:var(--dt-text);font-size:clamp(1.55rem,2.5vw,2.1rem);line-height:1.2;font-weight:700;margin:.4rem 0 .5rem}
    .hero-copy{color:var(--dt-muted);font-size:.94rem}

    [data-testid="stMetric"]{
      background:linear-gradient(145deg,#24282e,#1d2025);
      border:1px solid var(--dt-border);border-radius:14px;padding:16px 18px;
      box-shadow:0 5px 18px rgba(0,0,0,.10);
      animation:dt-enter 420ms ease-out both;
      transition:transform var(--dt-motion) ease,border-color var(--dt-motion) ease,box-shadow var(--dt-motion) ease;
    }
    [data-testid="stMetric"]:hover{border-color:rgba(133,128,232,.62);transform:translateY(-2px);box-shadow:0 10px 26px rgba(0,0,0,.2)}
    [data-testid="stMetricLabel"]{color:var(--dt-muted)!important;font-size:.82rem}
    [data-testid="stMetricValue"]{color:var(--dt-text)!important;font-weight:700}
    [data-testid="stMetricDelta"]{font-weight:600}

    .stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{
      border-radius:10px;border:1px solid #3a4049;
      transition:transform var(--dt-fast) ease,border-color var(--dt-motion) ease,background var(--dt-motion) ease,box-shadow var(--dt-motion) ease;
    }
    .stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover{
      transform:translateY(-1px);border-color:var(--dt-accent);
      box-shadow:0 5px 16px rgba(133,128,232,.12)
    }
    .stButton>button:active,.stDownloadButton>button:active{transform:scale(.985)}
    input,textarea,[data-baseweb="select"]>div{transition:border-color var(--dt-motion) ease,box-shadow var(--dt-motion) ease}
    input:focus,textarea:focus,[data-baseweb="select"]>div:focus-within{
      border-color:var(--dt-accent)!important;box-shadow:0 0 0 2px var(--dt-accent-soft)!important
    }

    div[data-testid="stTabs"]{border-bottom:1px solid var(--dt-border)}
    div[data-testid="stTabs"] button{color:var(--dt-muted);border-radius:8px 8px 0 0;transition:color var(--dt-motion) ease,background var(--dt-motion) ease}
    div[data-testid="stTabs"] button:hover{color:var(--dt-text);background:var(--dt-accent-soft)}
    div[data-testid="stTabs"] button[aria-selected="true"]{color:#d8d4ff;background:var(--dt-accent-soft);border-bottom:2px solid var(--dt-accent)}
    [data-testid="stDataFrame"],[data-testid="stTable"]{border:1px solid var(--dt-border);border-radius:12px;overflow:hidden}
    [data-testid="stExpander"]{
      background:rgba(32,35,40,.82);border:1px solid var(--dt-border);border-radius:12px;
      transition:border-color var(--dt-motion) ease,box-shadow var(--dt-motion) ease
    }
    [data-testid="stExpander"]:hover{border-color:#505765;box-shadow:0 7px 20px rgba(0,0,0,.12)}
    [data-testid="stExpander"] details>summary{background:rgba(139,92,246,.055);color:var(--dt-text);transition:background var(--dt-motion) ease}
    [data-testid="stExpander"] details>summary:hover{background:rgba(133,128,232,.11)}
    [data-testid="stAlert"]{border-radius:12px;animation:dt-enter 240ms ease-out both}
    [data-testid="stPlotlyChart"]{
      border:1px solid rgba(48,53,60,.72);border-radius:14px;overflow:hidden;
      animation:dt-enter 520ms ease-out both;transition:border-color var(--dt-motion) ease,box-shadow var(--dt-motion) ease
    }
    [data-testid="stPlotlyChart"]:hover{border-color:rgba(133,128,232,.45);box-shadow:0 8px 24px rgba(0,0,0,.13)}
    [data-testid="stFileUploader"] section{
      border:1px dashed #555d69;border-radius:14px;background:rgba(32,35,40,.62);
      transition:border-color var(--dt-motion) ease,background var(--dt-motion) ease
    }
    [data-testid="stFileUploader"] section:hover{border-color:var(--dt-accent);background:rgba(133,128,232,.07)}
    [data-testid="stProgressBar"]>div>div{
      background:linear-gradient(90deg,#7c3aed,#a78bfa,#7c3aed);
      background-size:200% 100%;animation:dt-shimmer 1.5s linear infinite
    }
    .dt-landing,.dt-report-intro{
      background:linear-gradient(135deg,#202329,#1a1d22)!important;
      border:1px solid var(--dt-border)!important;
      box-shadow:0 10px 32px rgba(0,0,0,.14)!important;
      animation:dt-enter 420ms ease-out both
    }
    .dt-landing-kicker,.dt-brand-tag{color:#aaa6f4!important}
    .dt-landing-copy,.dt-report-intro p{color:#b5bdc8!important}
    .dt-landing-actions a{transition:transform var(--dt-motion) ease,border-color var(--dt-motion) ease,background var(--dt-motion) ease!important}
    .dt-landing-actions a:hover{transform:translateY(-2px)}
    @media(max-width:768px){
      .block-container{padding-top:1rem;padding-left:1rem;padding-right:1rem}
      [data-testid="stMetric"]{padding:12px}
    }
    @media(prefers-reduced-motion:reduce){
      *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important}
    }
    </style>
    """, unsafe_allow_html=True)

    # Stronger, clearly visible motion layer. CSS-only so authentication,
    # calculations, session state and report data remain untouched.
    st.markdown(r"""
    <style>
    @keyframes dt-rise-in {
      0% { opacity:0; transform:translate3d(0,28px,0) scale(.975); filter:blur(3px); }
      65% { opacity:1; filter:blur(0); }
      100% { opacity:1; transform:translate3d(0,0,0) scale(1); filter:blur(0); }
    }
    @keyframes dt-chart-in {
      0% { opacity:0; transform:translateY(24px) scale(.965); }
      100% { opacity:1; transform:translateY(0) scale(1); }
    }
    @keyframes dt-glow-pulse {
      0%,100% { box-shadow:0 5px 18px rgba(0,0,0,.14),0 0 0 rgba(133,128,232,0); }
      50% { box-shadow:0 9px 28px rgba(0,0,0,.22),0 0 22px rgba(133,128,232,.13); }
    }
    @keyframes dt-accent-sweep {
      0% { background-position:-220% 0; }
      100% { background-position:220% 0; }
    }
    @keyframes dt-nav-in { from { transform:translateX(-9px); opacity:.45; } to { transform:translateX(0); opacity:1; } }

    /* Main dashboard sections enter with a visible stagger. */
    [data-testid="stMainBlockContainer"] > div > div > div[data-testid="stVerticalBlock"] > div {
      animation:dt-rise-in .78s cubic-bezier(.2,.75,.25,1) both;
    }
    [data-testid="stMainBlockContainer"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(1) { animation-delay:.04s; }
    [data-testid="stMainBlockContainer"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) { animation-delay:.12s; }
    [data-testid="stMainBlockContainer"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(3) { animation-delay:.20s; }
    [data-testid="stMainBlockContainer"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(4) { animation-delay:.28s; }

    /* KPI cards: stronger entrance, sequential timing, and a restrained idle glow. */
    [data-testid="stMetric"] {
      animation:dt-rise-in .82s cubic-bezier(.2,.75,.25,1) both, dt-glow-pulse 4.8s ease-in-out 1.2s 1;
      will-change:transform,opacity;
    }
    [data-testid="stMetric"]:nth-child(1) { animation-delay:.08s,1.1s; }
    [data-testid="stMetric"]:nth-child(2) { animation-delay:.20s,1.2s; }
    [data-testid="stMetric"]:nth-child(3) { animation-delay:.32s,1.3s; }
    [data-testid="stMetric"]:nth-child(4) { animation-delay:.44s,1.4s; }
    [data-testid="stMetric"]:hover { transform:translateY(-6px) scale(1.015); border-color:rgba(150,145,255,.85)!important; box-shadow:0 16px 34px rgba(0,0,0,.28),0 0 0 1px rgba(133,128,232,.18)!important; }

    /* Charts visibly rise and settle after the KPI row. */
    [data-testid="stPlotlyChart"] { animation:dt-chart-in 1.05s cubic-bezier(.2,.75,.25,1) .25s both!important; }
    [data-testid="stPlotlyChart"]:hover { transform:translateY(-3px); border-color:rgba(150,145,255,.7)!important; box-shadow:0 14px 32px rgba(0,0,0,.24)!important; }

    /* Stronger but still polished interaction feedback. */
    .stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button { position:relative; overflow:hidden; }
    .stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stFormSubmitButton"]>button:hover { transform:translateY(-3px) scale(1.015)!important; box-shadow:0 8px 24px rgba(133,128,232,.22)!important; }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a,[data-testid="stSidebar"] button { transition:transform .22s ease,background .22s ease,border-color .22s ease!important; }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,[data-testid="stSidebar"] button:hover { transform:translateX(5px); background:rgba(133,128,232,.12)!important; }
    [data-testid="stProgressBar"]>div>div { background-size:220% 100%!important; animation:dt-accent-sweep 1.15s linear infinite!important; }
    [data-testid="stExpander"] details[open] [data-testid="stExpanderDetails"] { animation:dt-rise-in .38s ease-out both; }
    [data-testid="stAlert"] { animation:dt-rise-in .55s ease-out both; }

    @media(prefers-reduced-motion:reduce) {
      [data-testid="stMainBlockContainer"] > div > div > div[data-testid="stVerticalBlock"] > div,
      [data-testid="stMetric"],[data-testid="stPlotlyChart"],[data-testid="stAlert"] { animation:none!important; }
      [data-testid="stMetric"],[data-testid="stPlotlyChart"],.stButton>button,.stDownloadButton>button { transition:none!important; }
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


def _show_login_header():
    """Render the new supplied animated lamp room behind the real Streamlit auth form."""
    pull_step = int(st.session_state.get("dt_lamp_pull_count", 0))
    room_class = ("room on pull-step-{}".format(pull_step) if st.session_state.get("dt_lamp_on", False) else "room pull-step-{}".format(pull_step))
    css = r"""/* ===================================================
   COZY ANIMATED LAMP LOGIN - MODERN INTERACTIVE STYLES
   =================================================== */

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  
  /* Dynamic Lamp Theme Colors (Default: Warm Gold) */
  --lamp-clr: #ffd54f;
  --lamp-glow-core: #fff9c4;
  --lamp-glow-strong: rgba(255, 213, 79, 0.65);
  --lamp-glow-soft: rgba(255, 193, 7, 0.25);
  --lamp-beam-start: rgba(255, 235, 150, 0.85);
  --lamp-beam-mid: rgba(255, 213, 79, 0.25);
  --lamp-desk-glow: radial-gradient(ellipse at center, rgba(255, 220, 100, 0.35) 0%, rgba(255, 180, 50, 0.08) 55%, transparent 75%);
  
  /* Dark Atmosphere Colors */
  --bg-dark-off: #08090c;
  --bg-dark-on: #0e1117;
  --glass-bg: rgba(22, 27, 34, 0.65);
  --glass-border: rgba(255, 255, 255, 0.12);
  --text-main: #f0f6fc;
  --text-muted: #8b949e;
  --card-shadow-off: 0 30px 60px rgba(0, 0, 0, 0.8);
  --card-shadow-on: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px -5px var(--lamp-glow-soft);
}

/* Mood Color Variations */
[data-theme="cyber"] {
  --lamp-clr: #00e5ff;
  --lamp-glow-core: #e0f7fa;
  --lamp-glow-strong: rgba(0, 229, 255, 0.65);
  --lamp-glow-soft: rgba(0, 188, 212, 0.25);
  --lamp-beam-start: rgba(128, 243, 255, 0.85);
  --lamp-beam-mid: rgba(0, 229, 255, 0.25);
  --lamp-desk-glow: radial-gradient(ellipse at center, rgba(0, 229, 255, 0.35) 0%, rgba(0, 188, 212, 0.08) 55%, transparent 75%);
}

[data-theme="sunset"] {
  --lamp-clr: #ff5252;
  --lamp-glow-core: #ffebee;
  --lamp-glow-strong: rgba(255, 82, 82, 0.65);
  --lamp-glow-soft: rgba(233, 30, 99, 0.25);
  --lamp-beam-start: rgba(255, 138, 128, 0.85);
  --lamp-beam-mid: rgba(255, 82, 82, 0.25);
  --lamp-desk-glow: radial-gradient(ellipse at center, rgba(255, 82, 82, 0.35) 0%, rgba(233, 30, 99, 0.08) 55%, transparent 75%);
}

[data-theme="aurora"] {
  --lamp-clr: #00e676;
  --lamp-glow-core: #e8f5e9;
  --lamp-glow-strong: rgba(0, 230, 118, 0.65);
  --lamp-glow-soft: rgba(76, 175, 80, 0.25);
  --lamp-beam-start: rgba(185, 246, 202, 0.85);
  --lamp-beam-mid: rgba(0, 230, 118, 0.25);
  --lamp-desk-glow: radial-gradient(ellipse at center, rgba(0, 230, 118, 0.35) 0%, rgba(76, 175, 80, 0.08) 55%, transparent 75%);
}

[data-theme="violet"] {
  --lamp-clr: #d500f9;
  --lamp-glow-core: #f3e5f5;
  --lamp-glow-strong: rgba(213, 0, 249, 0.65);
  --lamp-glow-soft: rgba(171, 71, 188, 0.25);
  --lamp-beam-start: rgba(234, 128, 252, 0.85);
  --lamp-beam-mid: rgba(213, 0, 249, 0.25);
  --lamp-desk-glow: radial-gradient(ellipse at center, rgba(213, 0, 249, 0.35) 0%, rgba(171, 71, 188, 0.08) 55%, transparent 75%);
}

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
  font-family: var(--font-family);
  background-color: var(--bg-dark-off);
  color: var(--text-main);
  user-select: none;
  -webkit-font-smoothing: antialiased;
}

button, input {
  font-family: inherit;
}

/* ===================================================
   ROOM & AMBIENCE
   =================================================== */

.room {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: radial-gradient(circle at 35% 45%, #131720 0%, var(--bg-dark-off) 85%);
  transition: background .8s cubic-bezier(0.16, 1, 0.3, 1);
}

.room.on {
  background: radial-gradient(circle at 35% 45%, #19202c 0%, var(--bg-dark-on) 85%);
}

/* Night Sky Backdrop with Subtle Window Frame */
.night-sky {
  position: absolute;
  top: 40px;
  left: 60px;
  width: 160px;
  height: 240px;
  border-radius: 12px;
  border: 4px solid rgba(255, 255, 255, 0.05);
  background: linear-gradient(180deg, #050811 0%, #0c1220 100%);
  overflow: hidden;
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.8), 0 10px 30px rgba(0, 0, 0, 0.4);
  pointer-events: none;
  opacity: 0.6;
  transition: opacity 0.8s ease;
  z-index: 1;
}

.room.on .night-sky {
  opacity: 0.25;
}

.ambient-window {
  width: 100%;
  height: 100%;
  position: relative;
}

.window-frame {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(255, 255, 255, 0.07);
}

.window-frame::after {
  content: '';
  position: absolute;
  left: 50%;
  top: -120px;
  bottom: -120px;
  width: 3px;
  background: rgba(255, 255, 255, 0.07);
}

.stars-cluster {
  position: absolute;
  inset: 0;
  background-image: 
    radial-gradient(1px 1px at 20px 30px, #fff, rgba(0,0,0,0)),
    radial-gradient(1px 1px at 40px 70px, #fff, rgba(0,0,0,0)),
    radial-gradient(1.5px 1.5px at 90px 40px, #aed581, rgba(0,0,0,0)),
    radial-gradient(1px 1px at 130px 80px, #fff, rgba(0,0,0,0)),
    radial-gradient(1.5px 1.5px at 110px 140px, #81d4fa, rgba(0,0,0,0)),
    radial-gradient(1px 1px at 50px 180px, #fff, rgba(0,0,0,0));
  animation: twinkle 4s ease-in-out infinite alternate;
}

@keyframes twinkle {
  0% { opacity: 0.3; }
  100% { opacity: 0.9; }
}

/* Room Light Radial Gradient */
.room-light {
  position: absolute;
  top: -20%;
  left: -10%;
  width: 1100px;
  height: 1100px;
  border-radius: 50%;
  pointer-events: none;
  z-index: 2;
  opacity: 0;
  transform: scale(0.6);
  background: radial-gradient(circle, var(--lamp-glow-soft) 0%, rgba(0,0,0,0) 70%);
  transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1), transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.room.on .room-light {
  opacity: 1;
  transform: scale(1.4);
}

/* Atmospheric Floating Fireflies / Dust Motes */
.fireflies {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 15;
  overflow: hidden;
}

.firefly {
  position: absolute;
  border-radius: 50%;
  background: var(--lamp-clr);
  box-shadow: 0 0 12px 3px var(--lamp-glow-strong), 0 0 24px var(--lamp-clr);
  animation: fireflyMove var(--duration) ease-in-out var(--delay) infinite alternate;
  pointer-events: none;
  transition: background-color 0.5s ease, box-shadow 0.5s ease;
}

@keyframes fireflyMove {
  0% { transform: translate(var(--x1), var(--y1)) scale(0.8); opacity: 0.2; }
  33% { transform: translate(var(--x2), var(--y2)) scale(1.2); opacity: 0.8; }
  66% { transform: translate(var(--x3), var(--y3)) scale(0.9); opacity: 0.4; }
  100% { transform: translate(var(--x4), var(--y4)) scale(1); opacity: 0.7; }
}

/* ===================================================
   LAMP ASSEMBLY & REALISTIC 3D LIGHTING
   =================================================== */

.lamp-side {
  flex: 1.1;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 10;
}

.lamp-container {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  transform: scale(1.15);
  transform-origin: center bottom;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.3s ease;
}

/* Interactive Prompt Tooltip */
.pull-hint {
  position: absolute;
  top: 15px;
  left: calc(50% + 80px);
  background: rgba(20, 24, 33, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #e6edf3;
  padding: 8px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  gap: 8px;
  pointer-events: none;
  opacity: 0.9;
  transform: translateY(0);
  animation: floatHint 2.5s ease-in-out infinite;
  transition: opacity 0.5s ease, transform 0.5s ease;
  z-index: 20;
}

.room.on .pull-hint {
  opacity: 0;
  transform: translateY(-15px);
}

@keyframes floatHint {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

/* Lamp Finial */
.lamp-top-finial {
  width: 18px;
  height: 8px;
  background: linear-gradient(180deg, #d4af37 0%, #856404 100%);
  border-radius: 6px 6px 0 0;
  box-shadow: 0 -2px 5px rgba(0, 0, 0, 0.5);
  z-index: 12;
}

/* Lamp Head Shade */
.lamp-head {
  width: 154px;
  height: 60px;
  background: linear-gradient(135deg, #24292e 0%, #161b22 60%, #0d1117 100%);
  border-radius: 154px 154px 8px 8px;
  box-shadow: inset 0 3px 6px rgba(255, 255, 255, 0.2), 
              inset 0 -2px 6px rgba(0, 0, 0, 0.8),
              0 15px 30px rgba(0, 0, 0, 0.95);
  position: relative;
  z-index: 11;
  border-bottom: 3px solid #111418;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.5s ease;
  display: flex;
  justify-content: center;
  align-items: flex-end;
}

.lamp-inner-bulb {
  width: 32px;
  height: 14px;
  background: #2a2e37;
  border-radius: 50% 50% 0 0;
  margin-bottom: 2px;
  transition: background 0.4s ease, box-shadow 0.4s ease;
}

.room.on .lamp-inner-bulb {
  background: var(--lamp-glow-core);
  box-shadow: 0 0 20px 8px var(--lamp-clr);
}

.room.on .lamp-head {
  box-shadow: inset 0 -4px 15px var(--lamp-glow-soft), 
              inset 0 3px 6px rgba(255, 255, 255, 0.25),
              0 15px 30px rgba(0, 0, 0, 0.9);
}

/* Filament Core Glow */
.lamp-glow {
  position: absolute;
  top: 52px;
  width: 110px;
  height: 28px;
  background: #ffffff;
  border-radius: 50%;
  box-shadow: 0 0 45px 25px var(--lamp-glow-strong), 0 0 90px 45px var(--lamp-glow-soft);
  opacity: 0;
  transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 10;
  pointer-events: none;
}

.room.on .lamp-glow {
  opacity: 1;
}

/* Volumetric Light Beam */
.light-beam {
  position: absolute;
  top: 55px;
  width: 620px;
  height: 400px;
  clip-path: polygon(42% 0, 58% 0, 100% 100%, 0 100%);
  background: linear-gradient(180deg, var(--lamp-beam-start) 0%, var(--lamp-beam-mid) 50%, rgba(0, 0, 0, 0) 100%);
  opacity: 0;
  transition: opacity 0.5s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 6;
  pointer-events: none;
  filter: blur(12px);
  transform-origin: 50% 0%;
}

.room.on .light-beam {
  opacity: 0.95;
}

/* Lamp Hardware Details */
.lamp-neck-joint {
  width: 14px;
  height: 10px;
  background: linear-gradient(90deg, #b8860b 0%, #ffd700 50%, #856404 100%);
  border-radius: 3px;
  z-index: 9;
}

.lamp-stem {
  width: 8px;
  height: 310px;
  background: linear-gradient(90deg, #111418 0%, #2f3640 45%, #111418 100%);
  position: relative;
  z-index: 8;
  box-shadow: 0 0 10px rgba(0,0,0,0.8);
  transition: box-shadow 0.4s ease;
}

.room.on .lamp-stem {
  box-shadow: 0 0 15px var(--lamp-glow-soft);
}

.lamp-joint {
  width: 18px;
  height: 12px;
  background: linear-gradient(90deg, #856404 0%, #ffd700 50%, #856404 100%);
  border-radius: 4px;
  margin-top: -6px;
  z-index: 9;
}

.lamp-base {
  width: 120px;
  height: 20px;
  background: linear-gradient(180deg, #24292e 0%, #161b22 100%);
  border-radius: 40px 40px 6px 6px;
  box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.15), 0 12px 24px rgba(0, 0, 0, 0.9);
  position: relative;
  z-index: 9;
  border-bottom: 3px solid #090c10;
  display: flex;
  justify-content: center;
  align-items: center;
}

.base-ridge {
  width: 80px;
  height: 3px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
}

/* Desk Light Reflection Pool */
.desk-surface {
  position: absolute;
  bottom: -45px;
  width: 650px;
  height: 120px;
  background: var(--lamp-desk-glow);
  border-radius: 50%;
  opacity: 0;
  transition: opacity 0.5s ease;
  z-index: 3;
  pointer-events: none;
}

.room.on .desk-surface {
  opacity: 1;
}

/* ===================================================
   INTERACTIVE PULL STRING WITH SPRING PHYSICS
   =================================================== */

.string-svg {
  position: absolute;
  top: 55px;
  left: calc(50% + 58px);
  width: 4px;
  height: 100px;
  overflow: visible;
  z-index: 10;
  pointer-events: none;
}

.string-svg path {
  stroke: #7d8590;
  stroke-width: 2.2;
  stroke-linecap: round;
  fill: none;
  filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.8));
}

.string-handle {
  position: absolute;
  top: 145px;
  left: calc(50% + 52px);
  width: 14px;
  height: 26px;
  background: linear-gradient(180deg, #f7d56e 0%, #c49826 60%, #7e5e0f 100%);
  border-radius: 7px;
  box-shadow: inset 0 2px 3px rgba(255, 255, 255, 0.6), 0 4px 10px rgba(0, 0, 0, 0.8);
  cursor: grab;
  z-index: 12;
  touch-action: none;
  user-select: none;
  display: flex;
  justify-content: center;
  align-items: center;
  outline: none;
  transition: box-shadow 0.2s ease, filter 0.2s ease;
}

.string-handle:hover {
  filter: brightness(1.15);
  box-shadow: inset 0 2px 3px rgba(255, 255, 255, 0.8), 0 6px 14px rgba(0, 0, 0, 0.9), 0 0 12px var(--lamp-glow-soft);
}

.string-handle.dragging {
  cursor: grabbing;
  filter: brightness(1.25);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.95);
}

.handle-bead {
  width: 4px;
  height: 12px;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 2px;
}

/* ===================================================
   GLASSMORPHIC LOGIN CARD 2.0
   =================================================== */

.login-side {
  flex: 1.2;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  padding-right: 8%;
}

.login-card {
  width: 100%;
  max-width: 450px;
  padding: 40px;
  border-radius: 28px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  position: relative;
  overflow: hidden;
  opacity: 0;
  transform: translateX(45px) scale(0.96);
  filter: blur(12px);
  pointer-events: none;
  box-shadow: var(--card-shadow-off);
  transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1),
              transform 0.6s cubic-bezier(0.16, 1, 0.3, 1),
              filter 0.6s ease,
              box-shadow 0.6s ease;
}

.room.on .login-card {
  opacity: 1;
  transform: translateX(0) scale(1);
  filter: blur(0);
  pointer-events: auto;
  box-shadow: var(--card-shadow-on);
  transition-delay: 0.15s;
}

.glass {
  background: var(--glass-bg);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid var(--glass-border);
}

.glass-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1.5px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), var(--lamp-clr), transparent);
}

/* Card Glow Spotlight Overlay */
.card-glow-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background: radial-gradient(circle at var(--mouse-x, 50%) var(--mouse-y, 50%), var(--lamp-glow-soft) 0%, transparent 65%);
  opacity: 0;
  transition: opacity 0.4s ease;
  z-index: 1;
}

.room.on .card-glow-overlay {
  opacity: 0.35;
}

/* Form Switcher Tabs */
.form-tabs {
  position: relative;
  display: flex;
  background: rgba(13, 17, 23, 0.6);
  padding: 4px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 2;
}

.tab-slider {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.form-tabs.signup-active .tab-slider {
  transform: translateX(100%);
}

.tab-btn {
  flex: 1;
  padding: 10px 0;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  z-index: 3;
  transition: color 0.3s ease;
}

.tab-btn.active {
  color: #fff;
}

/* Card Heading */
.login-heading {
  text-align: center;
  position: relative;
  z-index: 2;
}

.login-heading h2 {
  font-size: 30px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.5px;
  margin-bottom: 6px;
}

.login-heading p {
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 400;
}

/* ===================================================
   INPUTS & FORM FIELDS
   =================================================== */

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  position: relative;
  z-index: 2;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.signup-only-field {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  margin: 0;
  transform: translateY(-8px);
  transition: max-height 0.35s cubic-bezier(0.16, 1, 0.3, 1),
              opacity 0.35s ease,
              transform 0.35s ease,
              margin 0.35s ease;
}

.form-tabs.signup-active ~ .login-heading ~ .auth-form .signup-only-field,
.auth-form.mode-signup .signup-only-field {
  max-height: 70px;
  opacity: 1;
  transform: translateY(0);
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  color: var(--text-muted);
  pointer-events: none;
  transition: color 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-icon svg {
  width: 100%;
  height: 100%;
}

.input-wrap input {
  width: 100%;
  padding: 15px 16px 15px 48px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(13, 17, 23, 0.55);
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  outline: none;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4);
  transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
}

.input-wrap input:focus {
  border-color: var(--lamp-clr);
  background: rgba(13, 17, 23, 0.85);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4), 0 0 0 3px var(--lamp-glow-soft);
}

.input-wrap input:focus ~ .input-icon {
  color: var(--lamp-clr);
}

.input-wrap input::placeholder {
  color: #6e7681;
  font-weight: 400;
}

/* Password Visibility Toggle */
.password-wrap input {
  padding-right: 48px;
}

.toggle-password {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-muted);
  width: 24px;
  height: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.25s ease, transform 0.2s ease;
}

.toggle-password:hover {
  color: #fff;
  transform: translateY(-50%) scale(1.1);
}

.toggle-password svg {
  width: 20px;
  height: 20px;
}

/* Live Password Strength Meter */
.password-meter {
  display: none;
  flex-direction: column;
  gap: 4px;
  padding: 0 4px;
  transition: opacity 0.3s ease;
}

.password-meter.active {
  display: flex;
}

.meter-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.meter-fill {
  display: block;
  height: 100%;
  width: 0%;
  border-radius: 4px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.meter-text {
  font-size: 11px;
  color: var(--text-muted);
  text-align: right;
  font-weight: 500;
}

/* Options Row (Remember Me & Forgot Password) */
.options-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.remember-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text-muted);
  transition: color 0.2s ease;
}

.remember-label:hover {
  color: #fff;
}

.remember-label input {
  display: none;
}

.checkbox-custom {
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(13, 17, 23, 0.6);
  position: relative;
  transition: all 0.2s ease;
}

.remember-label input:checked ~ .checkbox-custom {
  background: var(--lamp-clr);
  border-color: var(--lamp-clr);
}

.remember-label input:checked ~ .checkbox-custom::after {
  content: '';
  position: absolute;
  left: 6px;
  top: 2px;
  width: 4px;
  height: 9px;
  border: solid #000;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.forgot-link {
  color: var(--lamp-clr);
  text-decoration: none;
  font-weight: 500;
  transition: opacity 0.2s ease, text-shadow 0.2s ease;
}

.forgot-link:hover {
  opacity: 0.85;
  text-shadow: 0 0 8px var(--lamp-glow-soft);
}

/* ===================================================
   BUTTONS & SOCIAL LOGIN
   =================================================== */

.sign-in-btn {
  position: relative;
  padding: 16px;
  border-radius: 16px;
  border: none;
  background: var(--lamp-clr);
  color: #0d1117;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 20px var(--lamp-glow-soft);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease, filter 0.2s ease;
  overflow: hidden;
}

.sign-in-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px var(--lamp-glow-strong);
  filter: brightness(1.08);
}

.sign-in-btn:active {
  transform: translateY(1px);
}

/* Button Loading Spinner */
.btn-loader {
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(0, 0, 0, 0.2);
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Social Divider */
.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 4px 0;
}

.divider span {
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
}

.divider b {
  color: #6e7681;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

/* Social Buttons */
.socials {
  display: flex;
  gap: 12px;
}

.social-btn {
  flex: 1;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: #f0f6fc;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: transform 0.2s ease, background 0.25s ease, border-color 0.25s ease;
}

.social-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.25);
  transform: translateY(-2px);
}

.social-btn:active {
  transform: translateY(0);
}

.social-svg {
  width: 18px;
  height: 18px;
}

/* Feedback Toast Notification */
.feedback-toast {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(30px);
  background: #1f6feb;
  color: #fff;
  padding: 10px 18px;
  border-radius: 30px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  opacity: 0;
  pointer-events: none;
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.35s ease;
  z-index: 30;
}

.feedback-toast.show {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.feedback-toast.success {
  background: #238636;
}

.feedback-toast.error {
  background: #da3633;
}

/* Error Shake Animation */
.shake {
  animation: shakeCard 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
}

@keyframes shakeCard {
  10%, 90% { transform: translate3d(-2px, 0, 0); }
  20%, 80% { transform: translate3d(3px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-5px, 0, 0); }
  40%, 60% { transform: translate3d(5px, 0, 0); }
}

/* ===================================================
   RESPONSIVE DESIGN
   =================================================== */

@media (max-width: 950px) {
  .room {
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .lamp-side {
    flex: 0 0 52vh;
    min-height: 400px;
    padding-top: 20px;
  }

  .login-side {
    padding: 20px 20px 60px;
    flex: 0 0 auto;
  }

  .night-sky {
    display: none;
  }

  .top-controls {
    top: 16px;
    right: 16px;
  }

  .lamp-container {
    transform: scale(0.95);
  }

  .login-card {
    max-width: 420px;
    padding: 30px 24px;
  }

  .pull-hint {
    left: 50%;
    transform: translateX(-50%);
    top: 0;
  }
}

@media (max-height: 680px) and (min-width: 951px) {
  .lamp-container {
    transform: scale(0.85);
  }

  .login-card {
    padding: 26px 30px;
    gap: 16px;
  }
}

/* Streamlit pull-cord elastic interaction */
@keyframes dt-cord-elastic {0% { transform:translateY(0) scaleY(1); }12% { transform:translateY(54px) scaleY(1.55); }27% { transform:translateY(-15px) scaleY(.82); }43% { transform:translateY(18px) scaleY(1.22); }59% { transform:translateY(-9px) scaleY(.91); }74% { transform:translateY(7px) scaleY(1.08); }88% { transform:translateY(-3px) scaleY(.97); }100% { transform:translateY(0) scaleY(1); }}
/* Streamlit integration overrides: keep the supplied lamp room, but use real Streamlit auth widgets. */
html, body { overflow-x:hidden !important; overflow-y:auto !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:#08090c !important; }
[data-testid="stMain"], [data-testid="stMainBlockContainer"], .main { background:transparent !important; }
.room { position:fixed !important; inset:0 !important; left:0 !important; right:0 !important; width:auto !important; max-width:100vw !important; height:100vh !important; z-index:0 !important; pointer-events:none !important; }
.room .lamp-side { position:fixed !important; left:0 !important; top:0 !important; width:44vw !important; height:100vh !important; pointer-events:none !important; }
.room .lamp-container { pointer-events:none !important; }
.room .string-svg, .room .string-handle { visibility:hidden !important; opacity:0 !important; pointer-events:none !important; }
/* Spring animation for the visible gold pull bead and its cord. */
@keyframes dt-bead-spring {0%{transform:translateY(0) scaleY(1)}9%{transform:translateY(48px) scaleY(1.30)}22%{transform:translateY(-12px) scaleY(.91)}38%{transform:translateY(15px) scaleY(1.13)}54%{transform:translateY(-7px) scaleY(.95)}70%{transform:translateY(5px) scaleY(1.05)}85%{transform:translateY(-2px) scaleY(.99)}100%{transform:translateY(0) scaleY(1)}}
@keyframes dt-cord-spring {0%{transform:scaleY(1)}9%{transform:scaleY(1.72)}22%{transform:scaleY(.94)}38%{transform:scaleY(1.28)}54%{transform:scaleY(.97)}70%{transform:scaleY(1.10)}85%{transform:scaleY(.995)}100%{transform:scaleY(1)}}
@keyframes dt-bead-spring {0%{transform:translateY(0)}9%{transform:translateY(58px)}22%{transform:translateY(-10px)}38%{transform:translateY(17px)}54%{transform:translateY(-7px)}70%{transform:translateY(5px)}85%{transform:translateY(-2px)}100%{transform:translateY(0)}}
/* Stretch the whole SVG cord from its top anchor, not just the invisible SVG path. */
.room[class*="pull-step-"] .string-svg { animation:dt-cord-spring .95s cubic-bezier(.22,.61,.36,1) both!important; transform-origin:top left!important; transform-box:border-box!important; overflow:visible!important; }
.room[class*="pull-step-"] .string-svg path { animation:none!important; }
.room[class*="pull-step-"] .string-handle { animation:dt-bead-spring .95s cubic-bezier(.22,.61,.36,1) both!important; transform-origin:top center!important; }
.room .night-sky { position:fixed !important; left:3vw !important; top:9vh !important; }
.block-container { position:relative !important; z-index:5 !important; }
/* Clearly visible frosted-glass surface across the complete login panel. */
.block-container:has([data-testid="stTabs"]) {
  background:
    radial-gradient(ellipse at 14% 0%, rgba(125,190,235,.24), transparent 48%),
    linear-gradient(135deg, rgba(35,61,88,.94) 0%, rgba(25,35,61,.96) 54%, rgba(30,29,57,.95) 100%) !important;
  border: 1px solid rgba(190,222,255,.34) !important;
  border-radius: 34px !important;
  padding: 34px 42px 30px !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.20),
    inset 0 0 42px rgba(139,190,235,.075),
    0 28px 80px rgba(0,0,0,.38),
    0 0 46px rgba(105,164,220,.13) !important;
  -webkit-backdrop-filter: blur(24px) saturate(150%) !important;
  backdrop-filter: blur(24px) saturate(150%) !important;
}
/* Realistic storm lightning strikes on the login screen. Decorative layers never intercept clicks. */
@keyframes dtStormStrikeA {
  0%, 64%, 67%, 100% { opacity:0; }
  65% { opacity:.95; }
  65.7% { opacity:.12; }
  66.2% { opacity:.82; }
  66.8% { opacity:0; }
}
@keyframes dtStormStrikeB {
  0%, 31%, 34%, 100% { opacity:0; }
  32% { opacity:.9; }
  32.6% { opacity:.08; }
  33.1% { opacity:.72; }
  33.7% { opacity:0; }
}
@keyframes dtStormSkyFlash {
  0%, 64%, 67%, 100% { background-color:rgba(125,205,255,0); }
  65% { background-color:rgba(165,220,255,.13); }
  65.7% { background-color:rgba(125,190,255,.015); }
  66.2% { background-color:rgba(165,220,255,.09); }
  66.8% { background-color:rgba(125,205,255,0); }
}
.block-container:has([data-testid="stTabs"]) {
  position:relative !important;
  isolation:isolate !important;
  animation:dtLightningGlow 8s linear infinite;
}
.stApp:has(.block-container [data-testid="stTabs"])::before,
.stApp:has(.block-container [data-testid="stTabs"])::after {
  content:"";
  position:fixed !important;
  inset:0 !important;
  width:100vw !important;
  height:100vh !important;
  z-index:99999 !important;
  pointer-events:none !important;
  background-repeat:no-repeat !important;
  background-size:min(31vw,390px) 94vh !important;
  mix-blend-mode:screen;
  will-change:opacity,filter;
}
.stApp:has(.block-container [data-testid="stTabs"])::before {
  background-position:82% 0 !important;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 260 900'%3E%3Cdefs%3E%3Cfilter id='g' x='-150%25' y='-50%25' width='400%25' height='200%25'%3E%3CfeGaussianBlur stdDeviation='9'/%3E%3C/filter%3E%3C/defs%3E%3Cg fill='none' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M178 -20 L145 95 L174 116 L112 236 L146 249 L75 390 L105 403 L24 590 L54 600 L-8 760' stroke='%2358bfff' stroke-width='30' opacity='.62' filter='url(%23g)'/%3E%3Cpath d='M178 -20 L145 95 L174 116 L112 236 L146 249 L75 390 L105 403 L24 590 L54 600 L-8 760' stroke='%239beaff' stroke-width='10' opacity='.95'/%3E%3Cpath d='M145 95 L75 150 L28 248 M112 236 L190 300 L216 390 M75 390 L20 440 L-8 520 M24 590 L105 650 L132 730' stroke='%23b9f2ff' stroke-width='5' opacity='.92'/%3E%3Cpath d='M145 95 L75 150 L28 248 M112 236 L190 300 L216 390 M75 390 L20 440 L-8 520 M24 590 L105 650 L132 730' stroke='%2358bfff' stroke-width='17' opacity='.42' filter='url(%23g)'/%3E%3C/g%3E%3C/svg%3E") !important;
  animation:dtStormStrikeA 8.4s steps(1,end) infinite, dtStormSkyFlash 8.4s steps(1,end) infinite;
}
.stApp:has(.block-container [data-testid="stTabs"])::after {
  background-position:8% 8% !important;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 260 900'%3E%3Cg fill='none' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M92 -30 L126 90 L96 120 L164 250 L128 265 L204 410 L172 424 L242 590' stroke='%2358bfff' stroke-width='27' opacity='.58'/%3E%3Cpath d='M92 -30 L126 90 L96 120 L164 250 L128 265 L204 410 L172 424 L242 590' stroke='%23ffffff' stroke-width='8' opacity='.96'/%3E%3Cpath d='M126 90 L195 150 L238 238 M164 250 L78 320 L48 402 M204 410 L252 468 M172 424 L102 505 L76 585' stroke='%23c5f4ff' stroke-width='5' opacity='.9'/%3E%3C/g%3E%3C/svg%3E") !important;
  animation:dtStormStrikeB 8.4s steps(1,end) infinite;
}
@media (prefers-reduced-motion: reduce) {
  .stApp:has(.block-container [data-testid="stTabs"])::before,
  .stApp:has(.block-container [data-testid="stTabs"])::after { animation:none !important; opacity:0 !important; }
}

@keyframes dtLightningFlash {
  0%, 30%, 72%, 100% { opacity:.24; filter:brightness(1.15); }
  8%, 12%, 48%, 53% { opacity:1; filter:brightness(2.4); }
  9.5%, 13.5%, 50%, 55% { opacity:.62; filter:brightness(1.7); }
}
@keyframes dtLightningGlow {
  0%, 30%, 72%, 100% { box-shadow:inset 0 1px 0 rgba(255,255,255,.20), inset 0 0 42px rgba(139,190,235,.075), 0 28px 80px rgba(0,0,0,.38), 0 0 30px rgba(105,164,220,.10); }
  8%, 12%, 48%, 53% { box-shadow:inset 0 1px 0 rgba(255,255,255,.42), inset 0 0 65px rgba(139,190,235,.20), 0 28px 80px rgba(0,0,0,.38), 0 0 70px rgba(65,205,255,.48), 0 0 110px rgba(150,120,255,.28); }
  9.5%, 13.5%, 50%, 55% { box-shadow:inset 0 1px 0 rgba(255,255,255,.28), inset 0 0 48px rgba(139,190,235,.12), 0 28px 80px rgba(0,0,0,.38), 0 0 48px rgba(65,205,255,.28); }
}
.block-container:has([data-testid="stTabs"]) {
  position:relative !important;
  isolation:isolate !important;
  animation:dtLightningGlow 3.6s linear infinite;
}
.block-container:has([data-testid="stTabs"])::before,
.block-container:has([data-testid="stTabs"])::after {
  content:"";
  position:absolute;
  z-index:100000 !important;
  width:54px;
  height:230px;
  pointer-events:none;
  opacity:.24;
  background:linear-gradient(180deg, #ffffff 0%, rgba(115,225,255,.98) 34%, rgba(155,135,255,.9) 68%, transparent 100%);
  filter:drop-shadow(0 0 7px rgba(95,215,255,1)) drop-shadow(0 0 18px rgba(125,145,255,.95)) drop-shadow(0 0 30px rgba(95,190,255,.55));
  clip-path:polygon(52% 0,100% 0,62% 35%,91% 35%,14% 100%,39% 54%,4% 54%);
  mix-blend-mode:screen;
  animation:dtLightningFlash 3.6s ease-in-out infinite;
  will-change:opacity,filter;
}
.block-container:has([data-testid="stTabs"])::before { left:-26px; top:10%; }
.block-container:has([data-testid="stTabs"])::after { right:-26px; bottom:8%; animation-delay:-1.8s; transform:scaleX(-1) rotate(8deg); }
.block-container:has([data-testid="stTabs"]) > div {
  position:relative;
  z-index:1;
}
@media (prefers-reduced-motion: reduce) {
  .block-container:has([data-testid="stTabs"]),
  .block-container:has([data-testid="stTabs"])::before,
  .block-container:has([data-testid="stTabs"])::after { animation:none !important; }
}
.block-container:has([data-testid="stTabs"]) { width:min(680px, 48vw) !important; max-width:680px !important; margin-left:auto !important; margin-right:5vw !important; padding-top:7vh !important; }
.block-container:has([data-testid="stTabs"]) [data-testid="stTabs"],
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] { max-width:100% !important; width:100% !important; }
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] {
  background:
    linear-gradient(135deg, rgba(218,238,255,.13) 0%, rgba(116,159,204,.075) 42%, rgba(24,31,55,.34) 100%),
    rgba(13,22,39,.72) !important;
  border:1px solid rgba(190,222,255,.27) !important;
  border-radius:26px !important;
  padding:22px !important;
  -webkit-backdrop-filter:blur(26px) saturate(145%) !important;
  backdrop-filter:blur(26px) saturate(145%) !important;
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,.19),
    inset 0 -1px 0 rgba(132,179,224,.09),
    0 22px 60px rgba(0,0,0,.24),
    0 0 34px rgba(106,165,218,.075) !important;
  position:relative !important;
  overflow:visible !important;
}
.block-container:has([data-testid="stTabs"]) [data-testid="stTabs"] button { color:#f0f6fc !important; }
.block-container:has([data-testid="stTabs"]) [data-testid="stTabs"] button[aria-selected="true"] { color:var(--lamp-clr) !important; }
/* Position the transparent custom component over the physical cord location. */
.st-key-dt_lamp_drag_component { position:fixed !important; left:calc(26.4vw - 36px) !important; top:calc(44.2vh - 145px) !important; width:72px !important; height:250px !important; min-width:72px !important; max-width:72px !important; padding:0 !important; margin:0 !important; z-index:100000 !important; background:transparent !important; overflow:visible !important; }
.st-key-dt_lamp_drag_component iframe { width:72px !important; height:250px !important; border:0 !important; background:transparent !important; display:block !important; }
/* Realistic dark room: layered vignette, wall falloff and subtle floor reflections. */
html, body, .stApp, [data-testid="stAppViewContainer"] { background:#07090d !important; }
[data-testid="stAppViewContainer"]::before {
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background:
    radial-gradient(ellipse at 22% 42%, var(--lamp-glow-soft) 0%, transparent 35%),
    radial-gradient(ellipse at 78% 82%, rgba(38,48,62,.16) 0%, transparent 44%),
    linear-gradient(90deg, rgba(0,0,0,.12), rgba(4,6,10,.12) 45%, rgba(0,0,0,.52)),
    linear-gradient(180deg, #090b10 0%, #0c1017 58%, #050609 100%);
  transition:background 1.1s ease, opacity 1.1s ease;
}
.room { isolation:isolate; }
.room::after { content:""; position:fixed; inset:0; z-index:3; pointer-events:none; background:radial-gradient(ellipse at center, transparent 28%, rgba(0,0,0,.24) 72%, rgba(0,0,0,.62) 100%); }
.night-sky { filter:brightness(.58) saturate(.72); transition:filter 1.2s ease, opacity 1.2s ease; }
.room.on .night-sky { filter:brightness(.36) saturate(.58); }
.lamp-glow { transition:opacity 1s ease, filter 1s ease; }
.light-beam { opacity:.12; filter:blur(1.4px); transition:opacity 1.15s cubic-bezier(.2,.7,.2,1), filter 1.15s ease; }
.room.on .light-beam { opacity:.92; filter:blur(.35px); }
.desk-surface { transition:opacity 1.2s ease, filter 1.2s ease; }
.room.on .desk-surface { filter:blur(2px) saturate(1.15); }
/* Gentle login entrance: smooth fade, small rise and blur-to-focus. */
@keyframes dt-auth-fade-rise {
  0% { opacity:0; transform:translate3d(0,24px,0) scale(.992); filter:blur(5px); }
  65% { opacity:1; filter:blur(.6px); }
  100% { opacity:1; transform:translate3d(0,0,0) scale(1); filter:blur(0); }
}
.block-container:has([data-testid="stTabs"]) [data-testid="stTabs"] { animation:dt-auth-fade-rise 1.05s cubic-bezier(.22,.75,.25,1) both !important; animation-delay:.12s !important; }
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] { animation:dt-auth-fade-rise 1.2s cubic-bezier(.22,.75,.25,1) both !important; animation-delay:.28s !important; will-change:opacity,transform,filter; }
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] input,
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] button { transition:background-color .35s ease, border-color .35s ease, box-shadow .35s ease, transform .35s cubic-bezier(.2,.7,.2,1) !important; }
@media (prefers-reduced-motion: reduce) {
  .block-container:has([data-testid="stTabs"]) [data-testid="stTabs"], .block-container:has([data-testid="stTabs"]) [data-testid="stForm"] { animation:none !important; }
  .light-beam, .lamp-glow, .desk-surface, .night-sky { transition:none !important; }
}
@media(max-width:850px) {
 .room .lamp-side { width:100vw !important; height:46vh !important; top:0 !important; }
 .room .lamp-container { transform:scale(.65) !important; transform-origin:top center !important; }
 .block-container:has([data-testid="stTabs"]) { width:auto !important; max-width:620px !important; margin:34vh 14px 0 !important; padding-top:0 !important; }
 .st-key-dt_lamp_drag_component { left:calc(50vw - 36px) !important; top:calc(18vh - 23px) !important; }
}
"""
    markup = '<main class="room {room_class}" id="room">\n  <div class="night-sky"><div class="stars-cluster"></div><div class="ambient-window"><div class="window-frame"></div><div class="window-pane"><div class="window-glow"></div></div></div></div>\n  <div class="room-light" id="roomLight"></div><div class="fireflies" id="fireflies"></div>\n  <section class="lamp-side"><div class="lamp-container" id="lampContainer">\n    <div class="lamp-glow"></div><div class="lamp-top-finial"></div>\n    <div class="lamp-head" id="lampHead"><div class="lamp-inner-bulb"></div></div>\n    <div class="light-beam" id="lightBeam"><div class="dust-motes"></div></div>\n    <div class="lamp-neck-joint"></div><div class="lamp-stem"></div><div class="lamp-joint"></div>\n    <div class="lamp-base"><div class="base-ridge"></div></div><div class="desk-surface" id="deskSurface"></div>\n    <svg class="string-svg" aria-hidden="true"><path id="stringPath" d="M 0 0 L 0 95"></path></svg>\n    <div class="string-handle" id="stringHandle" aria-label="Pull lamp switch string"><div class="handle-bead"></div></div>\n  </div></section>\n</main>'.format(room_class=room_class)
    st.markdown("<style>" + css + "</style>" + markup, unsafe_allow_html=True)




def inject_christmas_snow():
    """Render falling snow and the optional Christmas music player."""
    import random
    random.seed(24)
    flakes = []
    for i in range(58):
        left = random.randint(0, 100)
        size = random.randint(3, 8)
        duration = random.randint(11, 23)
        delay = random.randint(-22, 0)
        drift = random.randint(-65, 65)
        opacity = random.uniform(0.35, 0.85)
        flakes.append(
            f'<span class="dt-snowflake" style="left:{left}%;width:{size}px;height:{size}px;'
            f'--fall-duration:{duration}s;--fall-delay:{delay}s;--snow-drift:{drift}px;'
            f'--snow-opacity:{opacity:.2f};"></span>'
        )

    # Compact Christmas music player. Music starts only when the user presses Play.
    components.html(r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;background:transparent;overflow:hidden;font-family:Arial,sans-serif}
.player{position:fixed;top:0;right:0;display:flex;gap:6px;align-items:center;justify-content:flex-end;width:100%;}
select,button{height:36px;border:1px solid rgba(205,220,245,.30);border-radius:999px;
 background:rgba(28,35,48,.97);color:#edf4ff;font-size:11px;font-weight:650;padding:0 11px;
 box-shadow:0 5px 20px rgba(0,0,0,.24);outline:none}
select{width:145px;cursor:pointer}button{cursor:pointer;white-space:nowrap}
button:hover,select:hover{background:rgba(48,59,78,.99)}
</style></head><body>
<div class="player"><select id="song" aria-label="Choose Christmas song">
<option value="jingle">Jingle Bells</option><option value="wewish">We Wish You a Merry Christmas</option>
<option value="deck">Deck the Halls</option><option value="silent">Silent Night</option>
</select><button id="soundToggle" type="button">▶ Play</button></div>
<script>
(()=>{
 const frame=window.frameElement;
 if(frame){frame.style.position='fixed';frame.style.top='18px';frame.style.right='22px';frame.style.width='310px';frame.style.height='44px';frame.style.zIndex='1000000';frame.style.border='0';frame.style.background='transparent';frame.style.overflow='hidden';}
 const btn=document.getElementById('soundToggle'),picker=document.getElementById('song');
 let ctx=null,master=null,on=false,runId=0;
 const N={C4:261.63,D4:293.66,E4:329.63,F4:349.23,G4:392,A4:440,B4:493.88,C5:523.25,D5:587.33,E5:659.25,F5:698.46,G5:783.99,A5:880};
 const tunes={
  jingle:[[N.E5,1],[N.E5,1],[N.E5,2],[N.E5,1],[N.E5,1],[N.E5,2],[N.E5,1],[N.G5,1],[N.C5,1.5],[N.D5,.5],[N.E5,3],[N.F5,1],[N.F5,1],[N.F5,1],[N.F5,1],[N.F5,1],[N.E5,1],[N.E5,1],[N.E5,.5],[N.E5,.5],[N.D5,1],[N.D5,1],[N.E5,1],[N.D5,2],[N.G5,2]],
  wewish:[[N.C4,1],[N.F4,1],[N.F4,1],[N.G4,1],[N.F4,1],[N.E4,1],[N.D4,2],[N.D4,1],[N.G4,1],[N.G4,1],[N.A4,1],[N.G4,1],[N.F4,1],[N.E4,2],[N.E4,1],[N.A4,1],[N.A4,1],[N.B4,1],[N.A4,1],[N.G4,1],[N.F4,2]],
  deck:[[N.G4,1],[N.F4,1],[N.E4,1],[N.D4,1],[N.C4,1],[N.D4,1],[N.E4,1],[N.C4,1],[N.D4,1],[N.E4,1],[N.F4,1],[N.D4,1],[N.E4,1],[N.F4,1],[N.G4,1],[N.A4,1],[N.G4,1],[N.F4,1],[N.E4,1],[N.D4,1],[N.C4,2]],
  silent:[[N.G4,2],[N.A4,2],[N.G4,1],[N.E4,2],[N.G4,2],[N.A4,2],[N.G4,1],[N.E4,2],[N.D5,2],[N.D5,1],[N.B4,2],[N.C5,2],[N.C5,1],[N.G4,2]]
 };
 function note(freq,when,duration){
  const osc=ctx.createOscillator(),gain=ctx.createGain(),harm=ctx.createOscillator(),hg=ctx.createGain();
  osc.type='sine';osc.frequency.setValueAtTime(freq,when);harm.type='sine';harm.frequency.setValueAtTime(freq*2.01,when);
  gain.gain.setValueAtTime(.0001,when);gain.gain.exponentialRampToValueAtTime(.105,when+.02);gain.gain.exponentialRampToValueAtTime(.0001,when+duration*.88);
  hg.gain.setValueAtTime(.0001,when);hg.gain.exponentialRampToValueAtTime(.027,when+.015);hg.gain.exponentialRampToValueAtTime(.0001,when+Math.min(duration*.65,.4));
  osc.connect(gain);gain.connect(master);harm.connect(hg);hg.connect(master);osc.start(when);harm.start(when);osc.stop(when+duration);harm.stop(when+Math.min(duration,.45));
 }
 function phrase(){let t=ctx.currentTime+.06;const beat=.31;for(const [freq,b] of tunes[picker.value]){const d=b*beat;note(freq,t,d);t+=d+.025;}return t-ctx.currentTime;}
 async function start(){ctx=ctx||new(window.AudioContext||window.webkitAudioContext)();await ctx.resume();master=ctx.createGain();master.gain.value=.48;master.connect(ctx.destination);on=true;const id=++runId;
  const play=()=>{if(!on||id!==runId)return;const duration=phrase();setTimeout(play,(duration+.55)*1000);};play();btn.textContent='Ⅱ Stop';}
 function stop(){on=false;runId++;if(master&&ctx)master.gain.setTargetAtTime(0,ctx.currentTime,.035);btn.textContent='▶ Play';}
 btn.addEventListener('click',async()=>{if(on){stop();}else{try{await start();}catch(e){btn.textContent='Audio unavailable';}}});
 picker.addEventListener('change',()=>{if(on){stop();start();}});
})();
</script></body></html>''', height=1, scrolling=False)

    # Use a transparent full-viewport component iframe so HTML is rendered,
    # never displayed as literal text in the Streamlit page.
    snow_html = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden}
.snow{position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;overflow:hidden}
.flake{position:absolute;top:-48px;display:block;width:var(--size);height:var(--size);
 opacity:var(--o);animation:fall var(--d) linear var(--delay) infinite;will-change:transform}
.flake svg{display:block;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 3px rgba(220,238,255,.38));animation:crystal-spin var(--spin) linear infinite}
.flake path{fill:none;stroke:rgba(244,249,255,.88);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}
@keyframes fall{0%{transform:translate3d(0,-6vh,0) rotate(0deg)}50%{transform:translate3d(var(--drift),52vh,0) rotate(180deg)}100%{transform:translate3d(calc(var(--drift)*-.45),110vh,0) rotate(360deg)}}
@keyframes crystal-spin{to{transform:rotate(60deg)}}
@media(prefers-reduced-motion:reduce){.flake,.flake svg{animation:none!important;display:none!important}}
</style></head><body><div class="snow" aria-hidden="true">''' + ''.join(
        f'<i class="flake" style="left:{random.randint(0,100)}%;--size:{random.randint(15,30)}px;--d:{random.randint(14,26)}s;--spin:{random.randint(7,15)}s;--delay:{random.randint(-26,0)}s;--drift:{random.randint(-55,55)}px;--o:{random.uniform(.30,.62):.2f}"><svg viewBox="0 0 100 100" aria-hidden="true"><g transform="translate(50 50)">' + ''.join(
            f'<path d="M0 0 V-43 M0 -34 L-10 -24 M0 -34 L10 -24 M0 -22 L-9 -13 M0 -22 L9 -13 M0 -43 L-7 -34 M0 -43 L7 -34" transform="rotate({angle})"/>' for angle in range(0, 360, 60)
        ) + '</g></svg></i>'
        for _ in range(24)
    ) + r'''</div></body></html>'''
    snow_html = snow_html.replace('</body>', "<script>const f=window.frameElement;if(f){f.style.position='fixed';f.style.inset='0';f.style.width='100vw';f.style.height='100vh';f.style.zIndex='0';f.style.border='0';f.style.background='transparent';f.style.pointerEvents='none';}</script></body>")
    components.html(snow_html, height=1, scrolling=False)




def require_login():
    """Use Supabase Auth for colleague registration and sign-in.

    Optional legacy admin credentials in [auth.users] remain supported so the
    existing administrator can still sign in during the transition.
    """
    if st.session_state.get("authenticated"):
        return

    inject_christmas_snow()
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

    # Apple-inspired, single-column login screen with restrained motion.
    st.markdown("""
    <style>
      [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse at 50% 12%, rgba(83,101,133,.16), transparent 42%),
          radial-gradient(ellipse at 8% 78%, rgba(91,83,133,.10), transparent 36%),
          #080b11 !important;
      }
      [data-testid="stHeader"] { background: transparent !important; }

      /* One unified glass login card, matching the supplied reference. */
      /* Streamlit current and legacy main content wrappers */
      .main .block-container,
      [data-testid="stMainBlockContainer"],
      .stMainBlockContainer {
        box-sizing: border-box !important;
        width: min(100% - 32px, 760px) !important;
        max-width: 760px !important;
        min-width: 0 !important;
        margin: 5vh auto 2rem !important;
        position: relative !important;
        padding: 42px 48px 36px !important;
        border: 1px solid rgba(177,190,211,.34) !important;
        border-radius: 38px !important;
        background:
          radial-gradient(ellipse at 12% 5%, rgba(147,166,194,.12), transparent 42%),
          linear-gradient(145deg, rgba(34,40,51,.90), rgba(17,21,29,.94) 58%, rgba(24,28,38,.91)) !important;
        box-shadow:
          0 28px 90px rgba(0,0,0,.48),
          inset 0 1px 0 rgba(255,255,255,.10),
          inset 0 -1px 0 rgba(255,255,255,.025) !important;
        backdrop-filter: blur(28px) saturate(135%);
        -webkit-backdrop-filter: blur(28px) saturate(135%);
        animation: dtLoginEnter .9s cubic-bezier(.2,.7,.2,1) both;
      }
      @keyframes dtLoginEnter {
        from { opacity: 0; transform: translateY(18px) scale(.985); filter: blur(5px); }
        to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
      }
      @keyframes dtAmbient {
        0%, 100% { opacity: .28; transform: translate3d(-1.5%,0,0); }
        50%      { opacity: .52; transform: translate3d(1.5%,0,0); }
      }
      [data-testid="stAppViewContainer"]::before {
        content: ""; position: fixed; inset: -18%; pointer-events: none; z-index: 0;
        background: radial-gradient(ellipse at 50% 48%, rgba(116,132,164,.10), transparent 48%);
        animation: dtAmbient 12s ease-in-out infinite;
      }

      /* Subtle CSS-only aurora ribbons behind the login card. */
      /* Keep the app surface transparent so the aurora layer is visible. */
      [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
        background: transparent !important;
      }
      [data-testid="stAppViewContainer"]::after {
        content: ""; position: fixed; inset: -24% -18%;
        z-index: 1; pointer-events: none; opacity: .92;
        background:
          radial-gradient(ellipse 58% 28% at 16% 42%, rgba(35,220,190,.30), transparent 72%),
          radial-gradient(ellipse 54% 26% at 52% 34%, rgba(65,135,255,.30), transparent 74%),
          radial-gradient(ellipse 58% 30% at 84% 48%, rgba(166,91,255,.27), transparent 72%),
          linear-gradient(112deg, transparent 16%, rgba(51,218,194,.12) 36%, rgba(103,126,255,.16) 52%, rgba(181,105,250,.12) 68%, transparent 86%);
        background-size: 145% 145%, 150% 150%, 140% 140%, 180% 180%;
        background-position: 0% 50%, 100% 40%, 40% 60%, 50% 50%;
        transform: translate3d(0,0,0) rotate(-7deg) scale(1.08);
        transform-origin: center;
        animation: dtAuroraDrift 26s ease-in-out infinite alternate;
        will-change: transform, background-position, opacity;
      }
      /* Place login content above the aurora without blocking its visibility. */
      .main .block-container, .main .block-container > div {
        position: relative; z-index: 2;
      }
      @keyframes dtAuroraDrift {
        0% {
          transform: translate3d(-1.2%,1%,0) rotate(-8deg) scale(1.08);
          background-position: 0% 48%, 100% 42%, 35% 58%, 45% 50%;
          opacity: .38;
        }
        50% {
          transform: translate3d(1%, -1.2%,0) rotate(-5deg) scale(1.12);
          background-position: 55% 52%, 38% 48%, 80% 44%, 65% 48%;
          opacity: .62;
        }
        100% {
          transform: translate3d(-.6%,.8%,0) rotate(-9deg) scale(1.10);
          background-position: 100% 46%, 0% 54%, 20% 52%, 35% 52%;
          opacity: .46;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        [data-testid="stAppViewContainer"]::after { animation: none !important; }
      }
      .main .block-container > div { position: relative; z-index: 10; }
      /* Keep native login controls interactive above decorative overlays. */
      [data-testid="stForm"], [data-testid="stTextInput"],
      [data-testid="stTextInput"] > div, [data-testid="stTextInput"] input {
        position: relative !important;
        z-index: 20 !important;
        pointer-events: auto !important;
      }
      [data-testid="stTextInput"] input {
        user-select: text !important;
        -webkit-user-select: text !important;
        cursor: text !important;
      }

      .dt-auth-shell {
        box-sizing: border-box; width: 100%; max-width: none;
        margin: 0 auto 28px; padding: 4px 0 0;
        background: transparent !important; border: 0 !important;
        box-shadow: none !important; text-align: center;
        animation: dtLoginEnter .85s cubic-bezier(.2,.7,.2,1) both;
      }
      .dt-auth-title {
        color: #f7f8fb; font-size: clamp(36px, 4vw, 48px); line-height: 1.12;
        font-weight: 700; letter-spacing: -.045em; margin: 0 0 12px;
      }
      .dt-auth-subtitle {
        color: #b1b8c5; font-size: 18px; line-height: 1.5; margin: 0;
      }

      [data-testid="stTabs"] {
        width: 100%; margin: 0 auto !important;
        animation: dtLoginEnter .9s .08s both;
      }
      [data-testid="stTabs"] [data-baseweb="tab-list"] {
        display: flex !important; width: 100%;
        padding: 4px !important; gap: 4px !important;
        border: 1px solid rgba(255,255,255,.075) !important;
        border-radius: 22px !important;
        background: rgba(8,11,17,.26) !important;
      }
      [data-testid="stTabs"] [data-baseweb="tab"] {
        flex: 1 1 50%; justify-content: center;
        min-height: 54px; border-radius: 18px !important;
        color: #e4e7ed !important;
        transition: background .25s ease, box-shadow .25s ease, color .25s ease;
      }
      [data-testid="stTabs"] [data-baseweb="tab"] p {
        font-size: 16px !important; font-weight: 600 !important;
      }
      [data-testid="stTabs"] button[aria-selected="true"] {
        color: #fff !important;
        background: linear-gradient(180deg, rgba(133,145,164,.48), rgba(92,103,122,.42)) !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.17), 0 3px 12px rgba(0,0,0,.14) !important;
      }
      [data-testid="stTabs"] [data-baseweb="tab-highlight"],
      [data-testid="stTabs"] [data-baseweb="tab-border"] {
        display: none !important;
      }

      [data-testid="stForm"] {
        box-sizing: border-box; width: 100%;
        margin: 18px auto 0 !important; padding: 0 !important;
        background: transparent !important; border: 0 !important;
        box-shadow: none !important;
        animation: dtLoginEnter 1s .15s both;
      }
      [data-testid="stTextInput"] { margin-bottom: 14px; }
      [data-testid="stTextInput"] label {
        color: #f0f2f6 !important; font-size: 16px !important;
        font-weight: 500 !important; margin-bottom: 8px !important;
      }
      [data-testid="stTextInput"] input {
        box-sizing: border-box;
        background: rgba(29,34,44,.78) !important;
        border: 1px solid rgba(157,171,194,.27) !important;
        border-radius: 17px !important; color: #f7f8fb !important;
        min-height: 58px !important; padding: 0 18px !important;
        font-size: 16px !important;
        transition: border-color .22s ease, box-shadow .22s ease, background .22s ease;
      }
      [data-testid="stTextInput"] input::placeholder { color: #929baa !important; }
      [data-testid="stTextInput"] input:focus {
        border-color: rgba(206,218,237,.72) !important;
        box-shadow: 0 0 0 3px rgba(174,190,216,.12), 0 8px 24px rgba(0,0,0,.12) !important;
        background: rgba(37,43,55,.94) !important;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
      [data-testid="stForm"] button[kind="primary"] {
        background: linear-gradient(180deg, #ffffff, #e9edf3) !important;
        color: #11151c !important; border: 1px solid rgba(255,255,255,.8) !important;
        border-radius: 17px !important; min-height: 60px !important;
        font-size: 18px !important; font-weight: 700 !important;
        box-shadow: 0 8px 22px rgba(0,0,0,.18), inset 0 1px 0 #fff !important;
        transition: transform .22s ease, box-shadow .22s ease, filter .22s ease;
      }
      [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover,
      [data-testid="stForm"] button[kind="primary"]:hover {
        filter: brightness(1.04); transform: translateY(-2px);
        box-shadow: 0 13px 28px rgba(0,0,0,.25), inset 0 1px 0 #fff !important;
      }
      [data-testid="stAlert"] { border-radius: 14px; }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
      }
      @media (max-width: 640px) {
         .main .block-container,
        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer {
          width: calc(100% - 24px) !important; max-width: 760px !important; margin: 3vh auto 2rem !important;
          padding: 32px 22px 28px !important; border-radius: 26px !important;
        }
        .dt-auth-shell { margin-bottom: 28px; }
        .dt-auth-subtitle { font-size: 15px; }
        [data-testid="stTabs"] [data-baseweb="tab"] { min-height: 48px; }
        [data-testid="stTextInput"] input { min-height: 56px !important; }
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] button { min-height: 58px !important; }
      }

      /* Real storm lightning for the active require_login screen. */
      @keyframes dtRealStrikeOne {
        0%, 18%, 21%, 100% { opacity: 0; }
        18.25% { opacity: .98; }
        18.8% { opacity: .08; }
        19.15% { opacity: .82; }
        19.55% { opacity: 0; }
      }
      @keyframes dtRealStrikeTwo {
        0%, 61%, 64%, 100% { opacity: 0; }
        61.2% { opacity: .95; }
        61.65% { opacity: .05; }
        62.05% { opacity: .72; }
        62.45% { opacity: 0; }
      }
      /* Background-only storm layer: behind the login card and village artwork. */
      .dt-storm-lightning {
        position: fixed !important; inset: 0 !important;
        width: 100vw !important; height: 100vh !important;
        z-index: 1 !important; pointer-events: none !important;
        overflow: hidden !important; mix-blend-mode: screen;
        isolation: isolate;
      }
      .main .block-container { position: relative !important; z-index: 10 !important; }
      .dt-winter-village { z-index: 20 !important; }
      .dt-storm-lightning svg {
        position: absolute; inset: 0; width: 100%; height: 100%;
        overflow: visible;
      }
      .dt-storm-bolt-left {
        opacity: 0; animation: dtRealStrikeOne 7s steps(1,end) infinite;
      }
      .dt-storm-bolt-right {
        opacity: 0; animation: dtRealStrikeTwo 8.5s steps(1,end) infinite;
      }
      .dt-storm-lightning .bolt-glow {
        fill: none; stroke: #65cfff; stroke-width: 22;
        stroke-linecap: round; stroke-linejoin: round; opacity: .65;
        filter: blur(12px);
      }
      .dt-storm-lightning .bolt-core {
        fill: none; stroke: #f4fcff; stroke-width: 4.2;
        stroke-linecap: round; stroke-linejoin: round;
        filter: drop-shadow(0 0 5px #fff) drop-shadow(0 0 14px #75d8ff);
      }
      .dt-storm-lightning .bolt-branch {
        fill: none; stroke: #d9f6ff; stroke-width: 2.1;
        stroke-linecap: round; opacity: .95;
        filter: drop-shadow(0 0 7px #79dfff);
      }
      @media (max-width: 640px) {
        .dt-storm-lightning { opacity: .72; }
      }
      /* Lightweight winter village foreground: static SVG with tiny window glow only. */
      .dt-winter-village {
        position: fixed; left: 0; right: 0; bottom: 40px;
        height: clamp(112px, 15vh, 158px);
        z-index: 20; pointer-events: none; overflow: hidden;
        opacity: .62; line-height: 0;
        /* Feather the upper skyline and both horizontal ends into the page background. */
        -webkit-mask-image:
          linear-gradient(to bottom, transparent 0%, rgba(0,0,0,.10) 28%, #000 68%),
          linear-gradient(to right, transparent 0%, #000 9%, #000 91%, transparent 100%);
        -webkit-mask-composite: source-in;
        mask-image:
          linear-gradient(to bottom, transparent 0%, rgba(0,0,0,.10) 28%, #000 68%),
          linear-gradient(to right, transparent 0%, #000 9%, #000 91%, transparent 100%);
        mask-composite: intersect;
      }
      /* Keep village artwork in front of the login card; pointer-events remain disabled so controls still work. */
      .main .block-container {
        position: relative !important;
        z-index: 10 !important;
      }
      .dt-winter-village svg { width: 100%; height: 100%; display: block; }
      .dt-village-window { fill: #ffd58a; opacity: .62; animation: dtWindowGlow 5s ease-in-out infinite alternate; }
      .dt-village-window:nth-of-type(2n) { animation-delay: 1.8s; }
      @keyframes dtWindowGlow { from { opacity:.28; } to { opacity:.82; } }
      @media (max-width: 640px) {
        .dt-winter-village { bottom: 28px; height: 104px; opacity: .56; }
      }
      @media (prefers-reduced-motion: reduce) {
        .dt-village-window { animation: none !important; }
      }

      /* Login-only layout safeguards: prevent viewport overflow without changing app behavior. */
      html, body, .stApp, [data-testid="stAppViewContainer"],
      [data-testid="stMain"], [data-testid="stMainBlockContainer"], .main {
        max-width: 100% !important;
        overflow-x: clip !important;
      }
      .block-container:has([data-testid="stTabs"]) {
        box-sizing: border-box !important;
        width: min(760px, calc(100vw - 32px)) !important;
        max-width: 760px !important;
        margin: 4vh auto 2rem !important;
      }
      @media (max-width: 850px) {
        .block-container:has([data-testid="stTabs"]) {
          width: calc(100vw - 28px) !important;
          max-width: 620px !important;
          margin: 34vh auto 2rem !important;
          padding: 30px 22px 28px !important;
        }
      }
      @media (max-width: 640px) {
        .block-container:has([data-testid="stTabs"]) {
          width: calc(100vw - 24px) !important;
          margin: 34vh auto 2rem !important;
          padding: 28px 18px 24px !important;
          border-radius: 26px !important;
        }
        .dt-auth-title { font-size: clamp(30px, 8vw, 40px) !important; }
        .dt-auth-subtitle { font-size: 15px !important; }
      }
    </style>
    <div class="dt-storm-lightning" aria-hidden="true">
      <svg viewBox="0 0 1600 900" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <g class="dt-storm-bolt-right">
          <path class="bolt-glow" d="M1320 -30 L1278 96 L1310 119 L1238 236 L1271 253 L1188 391 L1220 407 L1137 560 L1172 574 L1088 760"/>
          <path class="bolt-core" d="M1320 -30 L1278 96 L1310 119 L1238 236 L1271 253 L1188 391 L1220 407 L1137 560 L1172 574 L1088 760"/>
          <path class="bolt-branch" d="M1278 96 L1194 154 L1152 249 M1238 236 L1338 292 L1374 384 M1188 391 L1107 451 L1072 536 M1137 560 L1230 626 L1260 720"/>
        </g>
        <g class="dt-storm-bolt-left">
          <path class="bolt-glow" d="M238 -20 L280 91 L250 118 L322 245 L287 261 L368 397 L336 416 L420 575 L383 590 L464 748"/>
          <path class="bolt-core" d="M238 -20 L280 91 L250 118 L322 245 L287 261 L368 397 L336 416 L420 575 L383 590 L464 748"/>
          <path class="bolt-branch" d="M280 91 L190 151 L151 242 M322 245 L414 308 L452 400 M368 397 L286 458 L249 541 M420 575 L326 641 L292 728"/>
        </g>
      </svg>
    </div>
    <div class="dt-winter-village" aria-hidden="true">
      <svg viewBox="0 0 1600 240" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="dtVillageSky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#14263a" stop-opacity="0"/>
            <stop offset="1" stop-color="#07101c" stop-opacity=".96"/>
          </linearGradient>
          <linearGradient id="dtVillageSnow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#7894ad" stop-opacity=".12"/>
            <stop offset=".48" stop-color="#526d87" stop-opacity=".34"/>
            <stop offset="1" stop-color="#101e2d" stop-opacity=".82"/>
          </linearGradient>
        </defs>
        <path d="M0 155 Q170 95 340 150 T680 145 T1020 135 T1360 145 T1600 125 V240 H0Z" fill="#102338" opacity=".48"/>
        <path d="M0 190 Q180 140 360 184 T720 176 T1080 180 T1440 165 T1600 180 V240 H0Z" fill="url(#dtVillageSky)"/>
        <g fill="#091522" opacity=".96">
          <path d="M70 205V128L112 91L154 128V205Z"/><path d="M95 130V108H130V130Z"/>
          <path d="M225 213V150L270 112L315 150V213Z"/>
          <path d="M1280 212V145L1332 99L1384 145V212Z"/><path d="M1430 210V130L1472 94L1514 130V210Z"/>
        </g>
        <g fill="#0b1c2c">
          <path d="M0 225L48 115L96 225Z"/><path d="M34 225L84 91L134 225Z"/>
          <path d="M154 232L205 112L256 232Z"/><path d="M1190 230L1245 100L1300 230Z"/>
          <path d="M1360 232L1415 105L1470 232Z"/><path d="M1490 232L1545 88L1600 232Z"/>
        </g>
        <g fill="#d8e9f7" opacity=".44">
          <path d="M48 115L36 143L48 136L60 143Z"/><path d="M84 91L71 124L84 116L97 124Z"/>
          <path d="M205 112L192 143L205 135L218 143Z"/><path d="M1245 100L1231 133L1245 125L1259 133Z"/>
          <path d="M1415 105L1401 138L1415 130L1429 138Z"/><path d="M1545 88L1530 123L1545 114L1560 123Z"/>
        </g>
        <g fill="#101d2b">
          <path d="M390 215V155L430 121L470 155V215Z"/><path d="M475 220V165L515 132L555 165V220Z"/>
          <path d="M1010 218V153L1055 115L1100 153V218Z"/>
        </g>
        <g class="dt-village-window">
          <rect x="405" y="169" width="13" height="20" rx="2"/><rect x="442" y="169" width="13" height="20" rx="2"/>
          <rect x="490" y="179" width="13" height="19" rx="2"/><rect x="527" y="179" width="13" height="19" rx="2"/>
          <rect x="1028" y="166" width="14" height="20" rx="2"/><rect x="1068" y="166" width="14" height="20" rx="2"/>
          <rect x="91" y="151" width="13" height="19" rx="2"/><rect x="1270" y="165" width="13" height="19" rx="2"/>
          <rect x="1450" y="148" width="13" height="19" rx="2"/>
        </g>
        <!-- Dark, soft snowbank silhouette: avoids a bright horizontal stripe across the sign-in button. -->
        <path d="M0 226 Q200 206 400 228 T800 221 T1200 228 T1600 215 V240 H0Z" fill="#0b1928" opacity=".78"/>
        <path d="M0 226 Q200 206 400 228 T800 221 T1200 228 T1600 215" fill="none" stroke="#7894ad" stroke-opacity=".16" stroke-width="3"/>
      </svg>
    </div>
    <div class="dt-auth-shell">
      <div class="dt-auth-title">Welcome back.</div>
      <div class="dt-auth-subtitle">Sign in to access your campaign reports.</div>
    </div>
    """, unsafe_allow_html=True)

    sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("supabase_signin_form", clear_on_submit=False):
            email_or_admin = st.text_input("Email address or username", placeholder="Enter your email or username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
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
    </style><div class="games-hero"><h1>🎮 Dreamztree Game Zone</h1><p>Play quick arcade games, challenge your skills and beat your best scores.</p></div>
    """, unsafe_allow_html=True)
    game = st.radio("Choose a game", ["🎮 Arcade Challenges", "🧠 Brain Test", "🔢 Mini Sudoku", "🦖 Dino Runner"], horizontal=True, label_visibility="collapsed", key="games_page_choice")
    if game == "🎮 Arcade Challenges":
        st.markdown("### ⚡ New Arcade Challenges")
        st.caption("Six new games plus Quiz Battle and 2048. Built for touchscreens, phones and desktops.")
        components.html(r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1020;color:#f8fafc;font-family:system-ui,-apple-system,Segoe UI,sans-serif}
.shell{padding:13px;border-radius:18px;background:linear-gradient(145deg,#111b36,#24134b);border:1px solid #ffffff20}
.tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-bottom:13px}
.tabs button,.action{border:0;border-radius:10px;padding:10px 8px;font-weight:800;cursor:pointer;background:#263554;color:#e2e8f0}
.tabs button.active,.action{background:linear-gradient(120deg,#8b5cf6,#ec4899);color:white}
.panel{background:#ffffff0b;border:1px solid #ffffff1a;border-radius:15px;padding:15px;min-height:370px}
h2{margin:0 0 5px;font-size:22px}.muted{color:#b8c5dc;font-size:13px}.score{font-weight:900;color:#fde68a}
canvas{display:block;width:100%;max-width:620px;height:auto;margin:12px auto;border-radius:12px;background:#101a33;touch-action:none;border:1px solid #ffffff20}
.controls{display:flex;justify-content:center;gap:9px;flex-wrap:wrap;margin:10px 0}.controls button{min-width:64px;min-height:42px}
.action{padding:10px 15px}.quizopt{display:block;width:100%;text-align:left;margin:8px 0;padding:12px;border:1px solid #ffffff22;border-radius:10px;background:#253451;color:white;cursor:pointer}
.board{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;max-width:360px;margin:16px auto}.cell{aspect-ratio:1;display:grid;place-items:center;border-radius:8px;background:#26334d;font-size:clamp(18px,4vw,27px);font-weight:900;color:white}
@media(max-width:520px){.shell{padding:9px}.panel{padding:10px}.tabs{grid-template-columns:repeat(2,minmax(0,1fr))}.tabs button{font-size:12px;padding:10px 5px}}
</style></head><body><div class="shell"><div class="tabs" id="tabs">
<button class="active" data-tab="race">🏎️ Cyber Racing</button><button data-tab="tower">🧱 Tower Builder</button><button data-tab="fruit">🍉 Fruit Slice</button><button data-tab="runner">🏃 Neon Runner</button><button data-tab="bubble">🫧 Bubble Shooter</button><button data-tab="golf">⛳ Mini Golf</button><button data-tab="quiz">🏆 Quiz Battle</button><button data-tab="2048">🔢 2048</button>
</div><div class="panel" id="panel"></div></div>
<script>
const panel=document.getElementById('panel'),tabs=[...document.querySelectorAll('[data-tab]')];let raf=0,keys={},tab='race';
function stop(){if(raf)cancelAnimationFrame(raf);raf=0;keys={}}
function btn(t,fn){const b=document.createElement('button');b.className='action';b.textContent=t;b.onclick=fn;return b}
function canvas(title,desc){panel.innerHTML='<h2>'+title+'</h2><p class="muted">'+desc+'</p><div class="score" id="score">Score: 0</div><canvas id="c" width="600" height="330"></canvas><div class="controls" id="controls"></div><p class="muted" id="hint">Use the on-screen controls or keyboard.</p>';return {c:document.getElementById('c'),x:document.getElementById('c').getContext('2d'),score:document.getElementById('score'),controls:document.getElementById('controls'),hint:document.getElementById('hint')}}
function control(box,label,down,up){let b=btn(label,()=>{});box.appendChild(b);b.addEventListener('pointerdown',e=>{e.preventDefault();down()});if(up){['pointerup','pointercancel','pointerleave'].forEach(v=>b.addEventListener(v,e=>{e.preventDefault();up()}))}}
function start(){stop();tabs.forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));({race,tower,fruit,runner,bubble,golf,quiz, '2048':game2048}[tab])()}
tabs.forEach(b=>b.onclick=()=>{tab=b.dataset.tab;start()});
function race(){let g=canvas('🏎️ Cyber Racing','Dodge traffic, survive as long as possible and beat your high score.');let {c,x,score,controls}=g,car=270,obs=[],points=0,over=false,frame=0;control(controls,'◀ LEFT',()=>keys.left=true,()=>keys.left=false);control(controls,'RIGHT ▶',()=>keys.right=true,()=>keys.right=false);control(controls,'↻ RESTART',()=>{stop();race()});function loop(){frame++;x.fillStyle='#101a33';x.fillRect(0,0,600,330);x.fillStyle='#273449';x.fillRect(125,0,350,330);x.strokeStyle='#f8fafc';x.setLineDash([24,20]);x.lineWidth=5;x.lineDashOffset=-frame*5;x.beginPath();x.moveTo(300,0);x.lineTo(300,330);x.stroke();x.setLineDash([]);if(!over){if(keys.left)car-=5;if(keys.right)car+=5;car=Math.max(145,Math.min(415,car));if(frame%48===0)obs.push({x:150+Math.random()*260,y:-45});obs.forEach(o=>o.y+=4+points/180);obs=obs.filter(o=>o.y<360);points+=1;obs.forEach(o=>{if(Math.abs(o.x-car)<38&&o.y>245&&o.y<315)over=true})}x.fillStyle='#38bdf8';x.fillRect(car,267,42,52);x.fillStyle='#bae6fd';x.fillRect(car+7,274,28,13);obs.forEach(o=>{x.fillStyle='#fb7185';x.fillRect(o.x, o.y,42,54);x.fillStyle='#fecdd3';x.fillRect(o.x+7,o.y+7,28,12)});score.textContent='Score: '+Math.floor(points);if(over){x.fillStyle='#0009';x.fillRect(0,0,600,330);x.fillStyle='white';x.font='bold 32px system-ui';x.textAlign='center';x.fillText('CRASH! Score '+Math.floor(points),300,160);x.font='16px system-ui';x.fillText('Press RESTART to race again',300,195)}else raf=requestAnimationFrame(loop)}window.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='a')keys.left=true;if(e.key==='ArrowRight'||e.key==='d')keys.right=true};window.onkeyup=e=>{keys.left=false;keys.right=false};loop()}
function tower(){let g=canvas('🧱 Tower Builder','Tap DROP when the moving block lines up. Build the tallest tower.');let {c,x,score,controls}=g,blocks=[{x:205,w:190,y:290}],moving={x:0,w:190,dir:1},level=1,over=false;function draw(){x.fillStyle='#111827';x.fillRect(0,0,600,330);x.fillStyle='#a78bfa';blocks.forEach((b,i)=>{x.fillRect(b.x,b.y, b.w,24);x.fillStyle='#ddd6fe';x.fillRect(b.x,b.y,b.w,4);x.fillStyle='#a78bfa'});if(!over){x.fillStyle='#f472b6';x.fillRect(moving.x,blocks[blocks.length-1].y-27,moving.w,24);moving.x+=moving.dir*3.2;if(moving.x<0||moving.x+moving.w>600)moving.dir*=-1}score.textContent='Floor: '+(blocks.length-1);if(over){x.fillStyle='white';x.font='bold 30px system-ui';x.textAlign='center';x.fillText('Tower complete! '+(blocks.length-1)+' floors',300,165)}else raf=requestAnimationFrame(draw)}function drop(){if(over)return;let prev=blocks[blocks.length-1],left=Math.max(prev.x,moving.x),right=Math.min(prev.x+prev.w,moving.x+moving.w),w=right-left;if(w<12){over=true;return}blocks.push({x:left,w,y:prev.y-27});moving={x:0,w,dir:1};if(blocks.length>10){blocks.forEach(b=>b.y+=24);blocks[0].y=290} }control(controls,'DROP BLOCK',drop);control(controls,'↻ RESTART',()=>{stop();tower()});draw()}
function fruit(){let g=canvas('🍉 Fruit Slice','Tap or swipe across the fruits. Avoid bombs. 30-second round.');let {c,x,score,controls}=g,items=[],points=0,frame=0,left=30,over=false;control(controls,'START / RESTART',()=>{stop();items=[];points=0;frame=0;left=30;over=false;loop()});function hit(e){if(over)return;let r=c.getBoundingClientRect(),px=(e.clientX-r.left)*600/r.width,py=(e.clientY-r.top)*330/r.height;items.forEach(o=>{if(!o.hit&&Math.hypot(o.x-px,o.y-py)<o.r+15){o.hit=true;if(o.bomb)over=true;else points++}})}c.addEventListener('pointerdown',hit);function loop(){frame++;if(frame%60===0)left--;if(frame%34===0)items.push({x:40+Math.random()*520,y:340,vx:(Math.random()-.5)*3,vy:-8-Math.random()*3,r:18+Math.random()*8,bomb:Math.random()<.18,hit:false});x.fillStyle='#111827';x.fillRect(0,0,600,330);items.forEach(o=>{o.x+=o.vx;o.y+=o.vy;o.vy+=.18;x.beginPath();x.fillStyle=o.bomb?'#475569':['#f43f5e','#22c55e','#facc15','#a78bfa'][Math.floor(o.x)%4];x.arc(o.x,o.y,o.r,0,Math.PI*2);x.fill();x.fillStyle='white';x.font='18px system-ui';x.textAlign='center';x.fillText(o.bomb?'✹':'✦',o.x,o.y+6)});items=items.filter(o=>o.y<370&&!o.hit);score.textContent='Score: '+points+' · Time: '+left+'s';if(left<=0)over=true;if(over){x.fillStyle='white';x.font='bold 28px system-ui';x.textAlign='center';x.fillText('Round over · '+points+' points',300,165)}else raf=requestAnimationFrame(loop)}loop()}
function runner(){let g=canvas('🏃 Neon Runner','Jump over glowing barriers. Tap JUMP or press Space.');let {c,x,score,controls}=g,py=255,vy=0,obs=[],points=0,frame=0,over=false;control(controls,'⬆ JUMP',()=>{if(py>=254)vy=-12});control(controls,'↻ RESTART',()=>{stop();runner()});window.onkeydown=e=>{if(e.code==='Space'||e.key==='ArrowUp'){e.preventDefault();if(py>=254)vy=-12}};function loop(){frame++;x.fillStyle='#080d22';x.fillRect(0,0,600,330);x.strokeStyle='#22d3ee';x.lineWidth=3;x.beginPath();x.moveTo(0,285);x.lineTo(600,285);x.stroke();if(!over){py+=vy;vy+=.55;if(py>255){py=255;vy=0}if(frame%65===0)obs.push({x:610});obs.forEach(o=>o.x-=5);obs=obs.filter(o=>o.x>-40);points++;obs.forEach(o=>{if(o.x<115&&o.x>65&&py>220)over=true})}x.fillStyle='#a78bfa';x.fillRect(85,py,35,30);x.fillStyle='#22d3ee';obs.forEach(o=>x.fillRect(o.x,245,24,40));score.textContent='Distance: '+Math.floor(points/5);if(over){x.fillStyle='white';x.font='bold 30px system-ui';x.textAlign='center';x.fillText('RUN OVER! '+Math.floor(points/5),300,160)}else raf=requestAnimationFrame(loop)}loop()}
function bubble(){let g=canvas('🫧 Bubble Shooter','Aim and tap to shoot. Match three or more bubbles of the same colour.');let {c,x,score,controls}=g,colors=['#fb7185','#60a5fa','#facc15','#4ade80'],grid=[],shots=0;for(let r=0;r<5;r++)for(let q=0;q<8;q++)grid.push({x:50+q*70,y:35+r*38,col:colors[Math.floor(Math.random()*4)],alive:true});let selected=0;colors.forEach((co,i)=>{let b=btn(['Pink','Blue','Yellow','Green'][i]);b.style.background=co;b.onclick=()=>selected=i;controls.appendChild(b)});function draw(){x.fillStyle='#101a33';x.fillRect(0,0,600,330);grid.filter(b=>b.alive).forEach(b=>{x.beginPath();x.fillStyle=b.col;x.arc(b.x,b.y,16,0,Math.PI*2);x.fill()});x.beginPath();x.fillStyle=colors[selected];x.arc(300,300,15,0,Math.PI*2);x.fill();score.textContent='Bubbles popped: '+shots;c.onclick=e=>{let r=c.getBoundingClientRect(),px=(e.clientX-r.left)*600/r.width,py=(e.clientY-r.top)*330/r.height;let target=grid.filter(b=>b.alive).sort((a,b)=>Math.hypot(a.x-px,a.y-py)-Math.hypot(b.x-px,b.y-py))[0];if(target&&Math.hypot(target.x-px,target.y-py)<65){let same=grid.filter(b=>b.alive&&b.col===target.col&&Math.hypot(b.x-target.x,b.y-target.y)<48);if(target.col===colors[selected]||same.length>=2){same.forEach(b=>b.alive=false);target.alive=false;shots+=same.length+1}else{target.col=colors[selected]}draw()}};};control(controls,'NEW BOARD',()=>{grid.forEach(b=>{b.alive=true;b.col=colors[Math.floor(Math.random()*4)]});shots=0;draw()});draw()}
function golf(){let g=canvas('⛳ Mini Golf','Drag from the ball backwards to aim and set power, then release to putt.');let {c,x,score,controls}=g,ball={x:95,y:260,vx:0,vy:0},hole={x:510,y:90},strokes=0,drag=null,done=false;function draw(){x.fillStyle='#14532d';x.fillRect(0,0,600,330);x.fillStyle='#166534';x.fillRect(15,15,570,300);x.beginPath();x.fillStyle='#020617';x.arc(hole.x,hole.y,17,0,Math.PI*2);x.fill();x.strokeStyle='#fff';x.lineWidth=3;x.beginPath();x.moveTo(hole.x,hole.y-5);x.lineTo(hole.x,hole.y-65);x.stroke();if(!done){ball.x+=ball.vx;ball.y+=ball.vy;ball.vx*=.985;ball.vy*=.985;if(Math.abs(ball.vx)+Math.abs(ball.vy)<.12){ball.vx=0;ball.vy=0}if(Math.hypot(ball.x-hole.x,ball.y-hole.y)<18&&ball.vx===0&&ball.vy===0)done=true}x.beginPath();x.fillStyle='#f8fafc';x.arc(ball.x,ball.y,9,0,Math.PI*2);x.fill();if(drag){x.strokeStyle='#facc15';x.lineWidth=3;x.beginPath();x.moveTo(ball.x,ball.y);x.lineTo(drag.x,drag.y);x.stroke()}score.textContent='Strokes: '+strokes+(done?' · HOLE IN!');if(!done)raf=requestAnimationFrame(draw)}c.onpointerdown=e=>{let r=c.getBoundingClientRect(),px=(e.clientX-r.left)*600/r.width,py=(e.clientY-r.top)*330/r.height;if(Math.hypot(px-ball.x,py-ball.y)<35&&!ball.vx&&!ball.vy)drag={x:px,y:py}};c.onpointermove=e=>{if(drag){let r=c.getBoundingClientRect();drag.x=(e.clientX-r.left)*600/r.width;drag.y=(e.clientY-r.top)*330/r.height}};c.onpointerup=()=>{if(drag){ball.vx=Math.max(-9,Math.min(9,(ball.x-drag.x)*.08));ball.vy=Math.max(-9,Math.min(9,(ball.y-drag.y)*.08));if(Math.abs(ball.vx)+Math.abs(ball.vy)>.4)strokes++;drag=null}};control(controls,'↻ NEW HOLE',()=>{stop();golf()});draw()}
function quiz(){let qs=[['Which planet is known as the Red Planet?',['Venus','Mars','Jupiter'],1],['How many sides does a hexagon have?',['5','6','8'],1],['What is 12 × 8?',['86','96','108'],1],['Which gas do plants absorb?',['Oxygen','Carbon dioxide','Nitrogen'],1],['What is the largest ocean?',['Atlantic','Indian','Pacific'],2],['How many minutes are in 2 hours?',['100','120','140'],1],['Which is a primary color?',['Green','Red','Pink'],1],['What is the square root of 81?',['8','9','10'],1]];let q=0,s=0;function draw(){panel.innerHTML='<h2>🏆 Quiz Battle</h2><p class="muted">Answer eight quick questions and beat your score.</p><div class="score">Score: '+s+' / 8</div><h3>'+qs[q][0]+'</h3><div id="opts"></div><p id="msg" class="muted"></p>';qs[q][1].forEach((v,i)=>{let b=document.createElement('button');b.className='quizopt';b.textContent=v;b.onclick=()=>{if(b.disabled)return;[...document.querySelectorAll('.quizopt')].forEach(z=>z.disabled=true);if(i===qs[q][2])s++;document.getElementById('msg').textContent=i===qs[q][2]?'Correct!':'Correct answer: '+qs[q][1][qs[q][2]];panel.appendChild(btn(q===7?'FINISH':'NEXT QUESTION',()=>{if(q===7){panel.innerHTML='<h2>Challenge complete!</h2><div class="score">Final score: '+s+'/8</div>';panel.appendChild(btn('PLAY AGAIN',()=>{q=0;s=0;draw()}))}else{q++;draw()}}))};document.getElementById('opts').appendChild(b)})}draw()}
function game2048(){let board=Array(16).fill(0),scoreN=0;function add(){let z=board.map((v,i)=>v?null:i).filter(v=>v!==null);if(z.length)board[z[Math.floor(Math.random()*z.length)]]=Math.random()<.9?2:4}function draw(){panel.innerHTML='<h2>🔢 2048 Challenge</h2><p class="muted">Use arrow keys or swipe. Combine matching numbers to reach 2048.</p><p class="score">Score: '+scoreN+'</p><div class="board">'+board.map(v=>'<div class="cell" style="background:'+(v?'hsl('+(35+Math.log2(v)*18)+',65%,42%)':'#26334d')+'">'+(v||'')+'</div>').join('')+'</div>';panel.appendChild(btn('NEW GAME',()=>{board=Array(16).fill(0);scoreN=0;add();add();draw()}))}function move(d){let old=board.slice();for(let l=0;l<4;l++){let ids=[];for(let j=0;j<4;j++){let r=d==='up'?j:d==='down'?3-j:l,c=d==='left'?j:d==='right'?3-j:l;ids.push(r*4+c)}let vals=ids.map(i=>board[i]).filter(Boolean);for(let j=0;j<vals.length-1;j++)if(vals[j]===vals[j+1]){vals[j]*=2;scoreN+=vals[j];vals.splice(j+1,1)}while(vals.length<4)vals.push(0);ids.forEach((id,j)=>board[id]=vals[j])}if(old.some((v,i)=>v!==board[i]))add();draw()}window.onkeydown=e=>{let m={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'};if(m[e.key]){e.preventDefault();move(m[e.key])}};let sx=0,sy=0;panel.ontouchstart=e=>{sx=e.touches[0].clientX;sy=e.touches[0].clientY};panel.ontouchend=e=>{let dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.max(Math.abs(dx),Math.abs(dy))>25)move(Math.abs(dx)>Math.abs(dy)?(dx>0?'right':'left'):(dy>0?'down':'up'))};board=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];add();add();draw()}
start();
</script></body></html>""", height=650, scrolling=False)
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
      <span>Try Reaction Rush, Whack-a-Mole, or Dino Runner!</span>
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


def render_post_login_transition():
    """Show a brief, one-time welcome transition after a successful login."""
    st.markdown(r"""
    <style>
      @keyframes dt-welcome-overlay {
        0% { opacity: 0; visibility: visible; }
        12% { opacity: 1; }
        82% { opacity: 1; }
        100% { opacity: 0; visibility: hidden; }
      }
      /* Animate only opacity and transform; avoid blur/filter changes that can stutter. */
      @keyframes dt-welcome-logo {
        0% { opacity: 0; transform: translate3d(0, 14px, 0) scale(.94); }
        24% { opacity: .35; }
        62% { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
        100% { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
      }
      @keyframes dt-welcome-line {
        0%,34% { opacity: 0; transform: translate3d(0, 8px, 0); }
        68%,88% { opacity: 1; transform: translate3d(0, 0, 0); }
        100% { opacity: 0; transform: translate3d(0, -2px, 0); }
      }
      .dt-welcome-overlay {
        position: fixed; inset: 0; z-index: 999999; pointer-events: none;
        display: flex; align-items: center; justify-content: center;
        background: radial-gradient(ellipse at center, rgba(24,42,67,.97), rgba(7,10,16,.985) 72%);
        animation: dt-welcome-overlay 3.2s linear forwards;
        will-change: opacity; contain: layout paint;
      }
      .dt-welcome-content { text-align: center; padding: 24px; color: #f3f6fb; }
      .dt-welcome-mark {
        width: 170px; height: 170px; margin: 0 auto 18px;
        display: flex; align-items: center; justify-content: center;
        background: transparent; border: 0; box-shadow: none; border-radius: 0;
        animation: dt-welcome-logo 2.7s cubic-bezier(.16, 1, .3, 1) both;
        will-change: transform, opacity; transform: translateZ(0); backface-visibility: hidden;
      }
      .dt-welcome-mark img {
        display: block; width: 100%; height: 100%; object-fit: contain;
        filter: none; transform: translateZ(0); backface-visibility: hidden;
      }
      .dt-welcome-title { margin: 0; font-size: clamp(24px,3.5vw,38px); font-weight: 720; letter-spacing: -.045em; }
      .dt-welcome-subtitle { margin: 9px 0 0; color: #9eafc5; font-size: 13px; letter-spacing: .14em; text-transform: uppercase; animation: dt-welcome-line 2.7s cubic-bezier(.16, 1, .3, 1) both; }
      @media (prefers-reduced-motion: reduce) {
        .dt-welcome-overlay, .dt-welcome-mark, .dt-welcome-subtitle { animation-duration: .01ms !important; }
      }
    </style>
    <div class="dt-welcome-overlay" aria-hidden="true">
      <div class="dt-welcome-content">
        <div class="dt-welcome-mark"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABT4AAAW3CAYAAABpEW6xAAAgAElEQVR4nOzdyXLbRhiFUSnl939lZuHIkWgOGBrd/3BOlXfJIgSiUF9uAx8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALQHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC0BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0MntdvsXjqmbVHamOtwAAAAASUVORK5CYII=" alt="Dreamztree logo"></div>
        <h1 class="dt-welcome-title">Welcome to Dreamztree</h1>
        <p class="dt-welcome-subtitle">Marketing Intelligence</p>
      </div>
    </div>
    """, unsafe_allow_html=True)



def inject_performance_patch():
    """Keep effects lightweight without globally disabling dashboard animations."""
    st.markdown(r"""
    <style>
      /* Prevent expensive full-screen filters while retaining small UI transitions. */
      .fireflies,.stars-cluster,.night-sky,.lamp-glow,.light-beam,.desk-surface {
        filter:none;
      }
      .dt-welcome-overlay { will-change:opacity; }
      @media(prefers-reduced-motion:reduce) {
        *,*::before,*::after { animation:none!important; transition:none!important; }
      }
    </style>
    """, unsafe_allow_html=True)

def inject_dashboard_snow():
    """Lightweight dendritic snowfall for the dashboard only."""
    import random
    random.seed(42)
    flakes = []
    for _ in range(12):
        arms = ''.join(
            f'<path d="M0 0 V-42 M0 -31 L-8 -23 M0 -31 L8 -23 M0 -18 L-6 -12 M0 -18 L6 -12" transform="rotate({angle})"/>'
            for angle in range(0, 360, 60)
        )
        flakes.append(
            f'<i class="flake" style="left:{random.randint(2,98)}%;--size:{random.randint(14,22)}px;'
            f'--duration:{random.randint(24,38)}s;--delay:{random.randint(-35,0)}s;'
            f'--drift:{random.randint(-28,28)}px;--opacity:{random.uniform(.22,.38):.2f}">'
            f'<svg viewBox="0 0 100 100" aria-hidden="true"><g transform="translate(50 50)">{arms}</g></svg></i>'
        )
    snow_html = r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden}
.snow{position:fixed;inset:0;width:100vw;height:100vh;overflow:hidden;pointer-events:none}
.flake{position:absolute;top:-32px;width:var(--size);height:var(--size);opacity:var(--opacity);
 animation:dashboard-fall var(--duration) linear var(--delay) infinite;will-change:transform}
.flake svg{display:block;width:100%;height:100%;overflow:visible}
.flake path{fill:none;stroke:rgba(238,246,255,.76);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
@keyframes dashboard-fall{
 0%{transform:translate3d(0,-5vh,0) rotate(0deg)}
 50%{transform:translate3d(var(--drift),52vh,0) rotate(180deg)}
 100%{transform:translate3d(calc(var(--drift)*-.35),108vh,0) rotate(360deg)}
}
@media(prefers-reduced-motion:reduce){.flake{animation:none!important;display:none!important}}
</style></head><body><div class="snow" aria-hidden="true">''' + ''.join(flakes) + r'''</div>
<script>
const frame=window.frameElement;
if(frame){
 frame.style.position='fixed';frame.style.left='0';frame.style.top='0';
 frame.style.width='100vw';frame.style.height='100vh';frame.style.zIndex='999999';
 frame.style.border='0';frame.style.background='transparent';frame.style.pointerEvents='none';
}
</script></body></html>'''
    components.html(snow_html, height=1, scrolling=False)


def inject_dashboard_music():
    """Add a compact, user-controlled Christmas music player to the dashboard."""
    components.html(r'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;background:transparent;overflow:hidden;font-family:Arial,sans-serif}
.player{position:fixed;top:0;right:0;display:flex;gap:6px;align-items:center;justify-content:flex-end;width:100%}
select,button{height:36px;border:1px solid rgba(205,220,245,.30);border-radius:999px;
 background:rgba(28,35,48,.97);color:#edf4ff;font-size:11px;font-weight:650;padding:0 11px;
 box-shadow:0 5px 20px rgba(0,0,0,.24);outline:none}
select{width:145px;cursor:pointer}button{cursor:pointer;white-space:nowrap}
button:hover,select:hover{background:rgba(48,59,78,.99)}
@media(max-width:600px){select{width:122px}.player{gap:5px}}
</style></head><body>
<div class="player"><select id="dashboardSong" aria-label="Choose Christmas song">
<option value="jingle">Jingle Bells</option><option value="wewish">We Wish You a Merry Christmas</option>
<option value="deck">Deck the Halls</option><option value="silent">Silent Night</option>
</select><button id="dashboardSoundToggle" type="button">▶ Play</button></div>
<script>
(()=>{
 const frame=window.frameElement;
 if(frame){frame.style.position='fixed';frame.style.top='166px';frame.style.right='24px';frame.style.width='310px';frame.style.height='44px';frame.style.zIndex='1000001';frame.style.border='0';frame.style.background='transparent';frame.style.overflow='hidden';}
 const btn=document.getElementById('dashboardSoundToggle'),picker=document.getElementById('dashboardSong');
 let ctx=null,master=null,on=false,runId=0;
 const N={C4:261.63,D4:293.66,E4:329.63,F4:349.23,G4:392,A4:440,B4:493.88,C5:523.25,D5:587.33,E5:659.25,F5:698.46,G5:783.99,A5:880};
 const tunes={
  jingle:[[N.E5,1],[N.E5,1],[N.E5,2],[N.E5,1],[N.E5,1],[N.E5,2],[N.E5,1],[N.G5,1],[N.C5,1.5],[N.D5,.5],[N.E5,3],[N.F5,1],[N.F5,1],[N.F5,1],[N.F5,1],[N.F5,1],[N.E5,1],[N.E5,1],[N.E5,.5],[N.E5,.5],[N.D5,1],[N.D5,1],[N.E5,1],[N.D5,2],[N.G5,2]],
  wewish:[[N.C4,1],[N.F4,1],[N.F4,1],[N.G4,1],[N.F4,1],[N.E4,1],[N.D4,2],[N.D4,1],[N.G4,1],[N.G4,1],[N.A4,1],[N.G4,1],[N.F4,1],[N.E4,2],[N.E4,1],[N.A4,1],[N.A4,1],[N.B4,1],[N.A4,1],[N.G4,1],[N.F4,2]],
  deck:[[N.G4,1],[N.F4,1],[N.E4,1],[N.D4,1],[N.C4,1],[N.D4,1],[N.E4,1],[N.C4,1],[N.D4,1],[N.E4,1],[N.F4,1],[N.D4,1],[N.E4,1],[N.F4,1],[N.G4,1],[N.A4,1],[N.G4,1],[N.F4,1],[N.E4,1],[N.D4,1],[N.C4,2]],
  silent:[[N.G4,2],[N.A4,2],[N.G4,1],[N.E4,2],[N.G4,2],[N.A4,2],[N.G4,1],[N.E4,2],[N.D5,2],[N.D5,1],[N.B4,2],[N.C5,2],[N.C5,1],[N.G4,2]]
 };
 function note(freq,when,duration){
  const osc=ctx.createOscillator(),gain=ctx.createGain(),harm=ctx.createOscillator(),hg=ctx.createGain();
  osc.type='sine';osc.frequency.setValueAtTime(freq,when);harm.type='sine';harm.frequency.setValueAtTime(freq*2.01,when);
  gain.gain.setValueAtTime(.0001,when);gain.gain.exponentialRampToValueAtTime(.105,when+.02);gain.gain.exponentialRampToValueAtTime(.0001,when+duration*.88);
  hg.gain.setValueAtTime(.0001,when);hg.gain.exponentialRampToValueAtTime(.027,when+.015);hg.gain.exponentialRampToValueAtTime(.0001,when+Math.min(duration*.65,.4));
  osc.connect(gain);gain.connect(master);harm.connect(hg);hg.connect(master);osc.start(when);harm.start(when);osc.stop(when+duration);harm.stop(when+Math.min(duration,.45));
 }
 function phrase(){let t=ctx.currentTime+.06;const beat=.31;for(const [freq,b] of tunes[picker.value]){const d=b*beat;note(freq,t,d);t+=d+.025;}return t-ctx.currentTime;}
 async function start(){ctx=ctx||new(window.AudioContext||window.webkitAudioContext)();await ctx.resume();master=ctx.createGain();master.gain.value=.48;master.connect(ctx.destination);on=true;const id=++runId;
  const play=()=>{if(!on||id!==runId)return;const duration=phrase();setTimeout(play,(duration+.55)*1000);};play();btn.textContent='Ⅱ Stop';}
 function stop(){on=false;runId++;if(master&&ctx)master.gain.setTargetAtTime(0,ctx.currentTime,.035);btn.textContent='▶ Play';}
 btn.addEventListener('click',async()=>{if(on){stop();}else{try{await start();}catch(e){btn.textContent='Audio unavailable';}}});
 picker.addEventListener('change',()=>{if(on){stop();start();}});
})();
</script></body></html>''', height=1, scrolling=False)


def main():
    require_login()
    st.session_state.pop("login_just_succeeded", False)
    inject_premium_theme()
    inject_performance_patch()
    inject_dashboard_snow()
    inject_dashboard_music()
    st.markdown(r"""
    <style>
      [data-testid="stExpander"] { border:0!important; border-radius:16px!important; overflow:visible!important; background:transparent!important; box-shadow:none!important; margin:10px 0!important; }
      @keyframes workspaceButtonGlow { 0%,100% { box-shadow:0 7px 18px rgba(0,0,0,.24),0 0 0 1px rgba(190,158,239,.10),0 0 12px rgba(157,112,220,.10),inset 0 1px 0 rgba(255,255,255,.14); } 50% { box-shadow:0 9px 22px rgba(0,0,0,.28),0 0 0 2px rgba(205,176,255,.20),0 0 25px rgba(157,112,220,.28),inset 0 1px 0 rgba(255,255,255,.18); } }
      [data-testid="stExpander"] details > summary { min-height:72px!important; box-sizing:border-box!important; padding:19px 24px 19px 27px!important; border:1px solid rgba(205,176,255,.58)!important; border-radius:14px!important; background:linear-gradient(105deg,rgba(112,77,170,.99),rgba(65,72,119,.99) 58%,rgba(38,52,78,.99))!important; color:#fff!important; font-weight:780!important; letter-spacing:.018em!important; box-shadow:0 7px 18px rgba(0,0,0,.24),0 0 0 1px rgba(190,158,239,.10),0 0 12px rgba(157,112,220,.10),inset 0 1px 0 rgba(255,255,255,.14)!important; animation:workspaceButtonGlow 2.8s ease-in-out infinite!important; transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease,filter .2s ease!important; cursor:pointer!important; }
      [data-testid="stExpander"] details > summary:hover { border-color:rgba(235,220,255,.95)!important; background:linear-gradient(105deg,rgba(139,96,205,1),rgba(79,89,143,1) 58%,rgba(48,67,99,1))!important; box-shadow:0 13px 30px rgba(0,0,0,.34),0 0 0 4px rgba(190,158,239,.18),0 0 32px rgba(157,112,220,.38)!important; transform:translateY(-3px) scale(1.004)!important; filter:brightness(1.13)!important; }
      @keyframes workspaceSpotlightGlowFirst { 0%,18%,82%,100% { box-shadow:0 12px 28px rgba(0,0,0,.30),0 0 0 2px rgba(225,203,255,.34),0 0 32px rgba(180,132,245,.48),inset 0 1px 0 rgba(255,255,255,.22); } 20%,80% { box-shadow:0 7px 18px rgba(0,0,0,.24),0 0 0 1px rgba(190,158,239,.10),inset 0 1px 0 rgba(255,255,255,.14); } }
      @keyframes workspaceSpotlightGlowSecond { 0%,18%,42%,58%,82%,100% { box-shadow:0 7px 18px rgba(0,0,0,.24),0 0 0 1px rgba(190,158,239,.10),inset 0 1px 0 rgba(255,255,255,.14); } 20%,40%,60%,80% { box-shadow:0 12px 28px rgba(0,0,0,.30),0 0 0 2px rgba(225,203,255,.34),0 0 32px rgba(180,132,245,.48),inset 0 1px 0 rgba(255,255,255,.22); } }
      @keyframes workspaceSpotlightGlowThird { 0%,38%,62%,100% { box-shadow:0 7px 18px rgba(0,0,0,.24),0 0 0 1px rgba(190,158,239,.10),inset 0 1px 0 rgba(255,255,255,.14); } 40%,60% { box-shadow:0 12px 28px rgba(0,0,0,.30),0 0 0 2px rgba(225,203,255,.34),0 0 32px rgba(180,132,245,.48),inset 0 1px 0 rgba(255,255,255,.22); } }
      @keyframes workspaceSpotlightSweepFirst { 0% { left:-42%;opacity:0; } 3% { opacity:.95; } 15% { opacity:.85; } 19% { left:112%;opacity:0; } 20%,80% { left:-42%;opacity:0; } 83% { opacity:.95; } 95% { opacity:.85; } 99%,100% { left:112%;opacity:0; } }
      @keyframes workspaceSpotlightSweepSecond { 0%,18% { left:-42%;opacity:0; } 21% { opacity:.95; } 35% { opacity:.85; } 39% { left:112%;opacity:0; } 40%,58% { left:-42%;opacity:0; } 61% { opacity:.95; } 75% { opacity:.85; } 79%,100% { left:112%;opacity:0; } }
      @keyframes workspaceSpotlightSweepThird { 0%,38% { left:-42%;opacity:0; } 41% { opacity:.95; } 55% { opacity:.85; } 59%,100% { left:112%;opacity:0; } }
      [data-testid="stExpander"] details > summary { position:relative!important; isolation:isolate!important; overflow:hidden!important; }
      [data-testid="stExpander"] details > summary:after { content:""; position:absolute; z-index:0; pointer-events:none; top:-55%; bottom:-55%; left:-42%; width:34%; transform:skewX(-22deg); background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,.04) 20%,rgba(239,222,255,.62) 48%,rgba(255,255,255,.12) 72%,transparent 100%); filter:blur(2px); }
      [data-testid="stExpander"] details > summary > * { position:relative!important; z-index:1!important; }
      [data-testid="stExpander"]:nth-of-type(1) details > summary { animation:workspaceSpotlightGlowFirst 10s ease-in-out infinite!important; }
      [data-testid="stExpander"]:nth-of-type(2) details > summary { animation:workspaceSpotlightGlowSecond 10s ease-in-out infinite!important; }
      [data-testid="stExpander"]:nth-of-type(3) details > summary { animation:workspaceSpotlightGlowThird 10s ease-in-out infinite!important; }
      [data-testid="stExpander"]:nth-of-type(1) details > summary:after { animation:workspaceSpotlightSweepFirst 10s linear infinite!important; }
      [data-testid="stExpander"]:nth-of-type(2) details > summary:after { animation:workspaceSpotlightSweepSecond 10s linear infinite!important; }
      [data-testid="stExpander"]:nth-of-type(3) details > summary:after { animation:workspaceSpotlightSweepThird 10s linear infinite!important; }

      [data-testid="stExpander"] details > summary p,[data-testid="stExpander"] details > summary span { color:#fff!important; font-weight:760!important; }
      [data-testid="stExpander"] details > summary svg { color:#eadbff!important; }
      [data-testid="stExpander"] details[open] > summary { border-color:rgba(218,195,255,.58)!important; border-radius:13px 13px 9px 9px!important; background:linear-gradient(105deg,rgba(82,62,119,.98),rgba(43,53,79,.98))!important; box-shadow:0 5px 15px rgba(0,0,0,.20),inset 0 1px 0 rgba(255,255,255,.12)!important; }
      [data-testid="stExpander"] [data-testid="stExpanderDetails"] { margin-top:8px!important; border:1px solid rgba(158,139,194,.18)!important; border-radius:12px!important; background:rgba(13,17,27,.58)!important; padding:20px!important; }
      @keyframes dtButtonSheen { 0% { left:-130%; opacity:0; } 18% { opacity:.8; } 100% { left:140%; opacity:0; } }
      @keyframes dtUploadBorder { 0%,100% { border-color:rgba(151,133,190,.35); box-shadow:0 0 0 0 rgba(167,130,224,0); } 50% { border-color:rgba(190,155,244,.85); box-shadow:0 0 0 3px rgba(167,130,224,.10); } }
      .stButton button,[data-testid="stDownloadButton"] button { position:relative!important; overflow:hidden!important; isolation:isolate!important; border-radius:10px!important; border:1px solid rgba(145,164,190,.26)!important; background:linear-gradient(110deg,rgba(255,255,255,.055),rgba(255,255,255,.025))!important; color:#e7edf6!important; box-shadow:0 3px 10px rgba(0,0,0,.12)!important; transition:transform .22s cubic-bezier(.2,.8,.2,1),border-color .22s ease,background .22s ease,box-shadow .22s ease!important; }
      .stButton button:after,[data-testid="stDownloadButton"] button:after { content:""; position:absolute; z-index:-1; pointer-events:none; top:-40%; bottom:-40%; left:-130%; width:48%; transform:skewX(-22deg); background:linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent); opacity:0; }
      .stButton button:hover { transform:translateY(-2px)!important; border-color:rgba(177,142,232,.72)!important; background:linear-gradient(110deg,rgba(111,78,158,.30),rgba(70,83,120,.22))!important; box-shadow:0 8px 20px rgba(0,0,0,.22),0 0 0 2px rgba(167,130,224,.08)!important; }
      .stButton button:hover:after { animation:dtButtonSheen .8s ease-out 1!important; }
      [data-testid="stDownloadButton"] button:hover { transform:translateY(-2px)!important; border-color:rgba(102,211,164,.7)!important; background:linear-gradient(110deg,rgba(35,128,91,.22),rgba(55,105,100,.16))!important; box-shadow:0 8px 20px rgba(0,0,0,.22),0 0 0 2px rgba(102,211,164,.08)!important; }
      [data-testid="stDownloadButton"] button:hover:after { animation:dtButtonSheen .8s ease-out 1!important; }
      [data-testid="stFileUploader"] button { border-radius:10px!important; transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease!important; }
      [data-testid="stFileUploader"] button:hover { transform:translateY(-2px)!important; border-color:rgba(190,158,239,.85)!important; box-shadow:0 0 0 3px rgba(167,130,224,.12),0 7px 18px rgba(0,0,0,.2)!important; }
      [data-testid="stFileUploader"] section { transition:border-color .2s ease,box-shadow .2s ease!important; }
      [data-testid="stFileUploader"] section:hover { border-color:rgba(190,158,239,.65)!important; box-shadow:0 0 0 2px rgba(167,130,224,.07)!important; }
      @media(prefers-reduced-motion:reduce) { [data-testid="stExpander"],[data-testid="stExpander"] details > summary,.stButton button,[data-testid="stDownloadButton"] button,[data-testid="stFileUploader"] button { transition:none!important; animation:none!important; } }
    </style>
    """, unsafe_allow_html=True)
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
    # Premium sidebar navigation — visual layer only; existing page routes remain intact.
    st.markdown(r"""
    <style>
      [data-testid="stSidebar"]{background:linear-gradient(180deg,#11111b 0%,#171522 55%,#11121a 100%)!important;border-right:1px solid #30283e!important}
      [data-testid="stSidebar"] > div:first-child{padding-top:1.1rem}
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#e9e4f2}
      .dt-side-brand{display:flex;align-items:center;gap:11px;padding:8px 4px 20px;border-bottom:1px solid #30283e;margin-bottom:18px}
      .dt-side-logo{width:43px;height:43px;border-radius:14px;background:linear-gradient(140deg,#d0a8ff,#7739c6);display:grid;place-items:center;color:#fff;font-size:23px;font-weight:850;box-shadow:0 7px 25px #9c58ee44}
      .dt-side-name{font-size:15px;font-weight:800;color:#fff;letter-spacing:-.4px}.dt-side-sub{font-size:10px;color:#aaa2b8;margin-top:3px}
      .dt-side-label{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:#897b9d;font-weight:800;margin:18px 0 7px}
      [data-testid="stSidebar"] .stButton>button{width:100%;text-align:left;justify-content:flex-start;border:1px solid transparent!important;background:transparent!important;color:#d8d2e2!important;border-radius:11px!important;padding:10px 12px!important;min-height:42px!important;transition:all .2s ease!important}
      [data-testid="stSidebar"] .stButton>button:hover{background:#30243f!important;border-color:#624586!important;color:#fff!important;transform:translateX(3px)!important;box-shadow:0 5px 18px #9b5de522!important}
      [data-testid="stSidebar"] .dt-side-foot{margin-top:28px;padding:12px;border:1px solid #3b3348;border-radius:13px;background:#211d2b;color:#e9e3f2;font-size:12px}
      .dt-date-shell{border-color:#59416f!important;background:linear-gradient(145deg,#292333,#1d1b26)!important}
      [data-testid="stFileUploader"]{background:linear-gradient(145deg,#24202e,#1d1d27)!important;border-color:#66517e!important}
      [data-testid="stFileUploader"]:hover{border-color:#c49aff!important;box-shadow:0 0 0 1px #b995f533,0 12px 30px #0004!important}
      .dt-upload-note{background:linear-gradient(100deg,#292238,#201e2a)!important;border-color:#49375e!important}
      @media(max-width:800px){[data-testid="stSidebar"]{min-width:0}}
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="dt-side-brand"><div class="dt-side-logo">D</div><div><div class="dt-side-name">Dreamztree</div><div class="dt-side-sub">Marketing Intelligence</div></div></div><div class="dt-side-label">Workspace</div>', unsafe_allow_html=True)
        if st.button("⌂  Dashboard", key="side_dashboard", use_container_width=True):
            st.query_params["page"] = "dashboard"; st.rerun()
        st.markdown('<a href="#executive-overview" style="display:block;padding:10px 12px;color:#d8d2e2;text-decoration:none;border-radius:10px">▦ &nbsp; Executive Overview</a><a href="#report-form" style="display:block;padding:10px 12px;color:#d8d2e2;text-decoration:none;border-radius:10px">▤ &nbsp; Reports</a><a href="#campaign-insights" style="display:block;padding:10px 12px;color:#d8d2e2;text-decoration:none;border-radius:10px">◇ &nbsp; Campaign Mapping</a>', unsafe_allow_html=True)
        if st.button("♧  Team Chat", key="side_chat", use_container_width=True):
            st.query_params["page"] = "chat"; st.rerun()
        if st.button("♧  Game Zone", key="side_game", use_container_width=True):
            st.query_params["page"] = "game"; st.rerun()
        st.markdown('<div class="dt-side-label">Account</div><div class="dt-side-foot">● &nbsp; Secure session<br><span style="color:#a69bb6">Dreamztree reporting workspace</span></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        if st.button("↪  Sign Out", key="side_sign_out", use_container_width=True):
            _delete_auth_cookie()
            if st.session_state.get("auth_method") == "supabase":
                try:
                    client = get_supabase_client()
                    if client is not None: client.auth.sign_out()
                except Exception: pass
            st.session_state["authenticated"] = False
            st.session_state.pop("authenticated_user", None); st.session_state.pop("auth_method", None)
            st.session_state.pop("supabase_access_token", None); st.session_state.pop("supabase_refresh_token", None)
            st.rerun()

    # Compact utility row: navigation shortcuts and reporting date share one line.
    game_col, chat_col, date_col = st.columns([1.0, 1.0, 1.35], vertical_alignment="center")
    with game_col:
        if st.button("🎮 Game Zone", key="open_game_zone_main", use_container_width=True):
            st.query_params["page"] = "game"; st.rerun()
    with chat_col:
        if st.button("💬 Team Chat", key="open_team_chat_main", use_container_width=True):
            st.query_params["page"] = "chat"; st.rerun()
    with date_col:
        st.markdown('<div class="dt-date-shell"><div class="dt-date-caption">Report Date</div>', unsafe_allow_html=True)
        date_value = st.date_input("Reporting date", value=datetime.today().date(), key="reporting_date_selector", label_visibility="collapsed", help="Choose the date used in report headings and downloaded files.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div id="report-form"></div><div id="campaign-insights"></div>', unsafe_allow_html=True)
    with st.expander("01  WORKSPACE SETTINGS     ·     Currency & campaign mapping", expanded=False):
        settings_left, settings_right = st.columns(2, gap="large")
        with settings_left:
            st.subheader("Currency conversion · USD to KWD")
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
    st.markdown('<div class="dt-step"><span class="dt-step-num">02</span> Import campaign exports</div>', unsafe_allow_html=True)
    st.markdown("<div style='color:#a5a3b0;font-size:.82rem;margin:-3px 0 13px 35px'>Add today's file to build the report. Yesterday's file is optional for comparison.</div>", unsafe_allow_html=True)
    upload_today_col, upload_yesterday_col = st.columns(2, gap="large")
    with upload_today_col:
        with st.container(border=True):
            st.markdown('<div style="display:flex;align-items:center;gap:9px;margin-bottom:7px"><span style="color:#c6a4fa;font-size:1.2rem">▤</span><span style="font-weight:720;color:#f4effb">Today’s export</span><span style="font-size:.65rem;color:#d7baff;background:#382d47;padding:3px 7px;border-radius:20px">REQUIRED</span></div><div style="font-size:.75rem;color:#a6a1b1;margin-bottom:8px">Meta Ads · Excel workbook</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("Today's Meta Ads Excel report", type=["xlsx", "xls"], key="meta_excel", label_visibility="collapsed")
    with upload_yesterday_col:
        with st.container(border=True):
            st.markdown('<div style="display:flex;align-items:center;gap:9px;margin-bottom:7px"><span style="color:#a99abf;font-size:1.2rem">◷</span><span style="font-weight:720;color:#f4effb">Previous day</span><span style="font-size:.65rem;color:#b8b1c3;background:#34313b;padding:3px 7px;border-radius:20px">OPTIONAL</span></div><div style="font-size:.75rem;color:#a6a1b1;margin-bottom:8px">Compare leads, spend and campaign changes</div>', unsafe_allow_html=True)
            yesterday_uploaded = st.file_uploader("Yesterday's Meta Ads Excel report (optional)", type=["xlsx", "xls"], key="yesterday_meta_excel", help="Upload yesterday's export to compare leads, spend, and top-performing campaigns.", label_visibility="collapsed")
    with st.expander("02  WEEKLY INTELLIGENCE     ·     Campaign performance", expanded=False):
        st.caption("Upload a weekly Meta Ads Excel export to identify zero-result, low-lead, high-cost and best-performing campaigns. Campaign names are shown in every result table.")
        weekly_file = st.file_uploader("Weekly Meta Ads Excel report", type=["xlsx", "xls"], key="weekly_meta_excel", help="Upload an export covering the full week. If a campaign appears on multiple rows, its results and spend will be combined.")
        low_lead_limit = st.number_input("Flag campaigns with leads at or below", min_value=0, max_value=10000, value=5, step=1, key="weekly_low_lead_limit", help="Adjust this threshold to match your weekly expectations.")
        high_cpl_limit = st.number_input("Flag campaigns with CPL above (KWD)", min_value=0.0, value=3.0, step=0.25, format="%.3f", key="weekly_high_cpl_limit", help="A campaign is high-cost when its cost per result exceeds this threshold.")
        if weekly_file is not None:
            try:
                weekly_raw = pd.read_excel(weekly_file)
                weekly_cols = list(weekly_raw.columns)
                if len(weekly_cols) < 3:
                    st.error("The weekly Excel file must contain campaign, results and spend columns.")
                else:
                    weekly_norm = [normalize(x) for x in weekly_cols]
                    def weekly_find_col(predicate, fallback):
                        return next((weekly_cols[i] for i, value in enumerate(weekly_norm) if predicate(value)), weekly_cols[min(fallback, len(weekly_cols)-1)])
                    weekly_campaign_col = weekly_find_col(lambda x: "campaign" in x, 0)
                    weekly_result_col = weekly_find_col(lambda x: "result" in x and "initial" not in x, 1)
                    weekly_spend_col = weekly_find_col(lambda x: "spent" in x or "amount" in x, 2)
                    weekly_df = weekly_raw[[weekly_campaign_col, weekly_result_col, weekly_spend_col]].copy()
                    weekly_df.columns = ["Campaign", "Results", "Spent"]
                    weekly_df["Campaign"] = weekly_df["Campaign"].fillna("").astype(str).str.strip()
                    weekly_df["Results"] = pd.to_numeric(weekly_df["Results"], errors="coerce").fillna(0)
                    weekly_df["Spent"] = pd.to_numeric(weekly_df["Spent"], errors="coerce").fillna(0.0)
                    weekly_df = weekly_df[weekly_df["Campaign"] != ""]
                    weekly_df = weekly_df.groupby("Campaign", as_index=False).agg(Results=("Results", "sum"), Spent=("Spent", "sum"))
                    weekly_df["Results"] = weekly_df["Results"].round().astype(int)
                    weekly_df["Spend (KWD)"] = weekly_df["Spent"] * factor
                    weekly_df["CPL (KWD)"] = weekly_df.apply(lambda row: row["Spend (KWD)"] / row["Results"] if row["Results"] > 0 else None, axis=1)
                    weekly_assignments = weekly_df["Campaign"].apply(lambda name: infer_campaign(name, mappings))
                    weekly_df["Staff"] = weekly_assignments.apply(lambda item: item[0])
                    weekly_df["Branch"] = weekly_assignments.apply(lambda item: item[2])
                    zero_week = weekly_df[weekly_df["Results"] <= 0].copy()
                    low_week = weekly_df[(weekly_df["Results"] > 0) & (weekly_df["Results"] <= int(low_lead_limit))].copy()
                    high_week = weekly_df[(weekly_df["Results"] > 0) & (weekly_df["CPL (KWD)"] > float(high_cpl_limit))].copy()
                    best_week = weekly_df[weekly_df["Results"] > 0].sort_values(["CPL (KWD)", "Results"], ascending=[True, False]).head(10).copy()
                    wk1, wk2, wk3, wk4 = st.columns(4)
                    wk1.metric("Zero-result campaigns", f"{len(zero_week):,}")
                    wk2.metric("Low-lead campaigns", f"{len(low_week):,}")
                    wk3.metric("High-CPL campaigns", f"{len(high_week):,}")
                    wk4.metric("Campaigns analysed", f"{len(weekly_df):,}")
                    st.metric("Spend on zero-result campaigns", f"{zero_week['Spend (KWD)'].sum():,.3f} KD")
                    weekly_display_cols = ["Campaign", "Staff", "Branch", "Results", "Spent", "Spend (KWD)", "CPL (KWD)"]
                    def show_weekly_group(title, frame, empty_message):
                        st.markdown("#### " + title)
                        if frame.empty:
                            st.success(empty_message)
                        else:
                            display = frame[weekly_display_cols].copy().rename(columns={"Campaign": "Campaign name", "Results": "Leads", "Spent": "Spend (USD)"})
                            st.dataframe(display, use_container_width=True, hide_index=True)
                            safe_title = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
                            st.download_button("Download " + title.lower() + " (CSV)", frame[weekly_display_cols].to_csv(index=False).encode("utf-8-sig"), "dreamztree_" + safe_title + ".csv", "text/csv", key="weekly_download_" + safe_title)
                    show_weekly_group("Zero-result campaigns", zero_week, "No zero-result campaigns found.")
                    show_weekly_group("Low-lead campaigns", low_week, "No campaigns fall at or below this lead threshold.")
                    show_weekly_group("High-cost campaigns (CPL)", high_week, "No campaigns exceed this CPL threshold.")
                    show_weekly_group("Best-performing campaigns", best_week, "No campaigns with positive results were found.")
                    st.caption("Low-lead and high-CPL flags use your selected thresholds. Spend is converted using the app's current USD-to-KWD rate. The file is treated as a weekly total; duplicate campaign rows are combined.")
            except Exception as weekly_exc:
                st.error(f"Could not analyse the weekly Excel file: {weekly_exc}")
                st.caption("Check that the workbook contains campaign, results and amount spent columns.")
    if uploaded is None:
        st.markdown('<div class="dt-upload-note">✦ &nbsp; Your workspace is ready. Add today’s Excel export to generate the report; include the previous day for a performance comparison.</div>', unsafe_allow_html=True)
        with st.expander("03  CAMPAIGN LIBRARY     ·     Team & course mappings", expanded=False):
            st.dataframe(mappings, use_container_width=True, hide_index=True)
        st.download_button("↓  Download mapping template", mappings.to_csv(index=False).encode("utf-8-sig"), "dreamztree_campaign_mapping.csv", "text/csv")
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
        st.markdown('<div id="executive-overview"></div>', unsafe_allow_html=True)
        st.divider()
        with st.expander("Executive marketing intelligence", expanded=True):
            render_intelligence_dashboard(edited, factor, date_value)
        unresolved = edited[(edited["Staff"].astype(str).str.strip() == "") | (edited["Course"].astype(str).str.strip() == "") | (edited["Branch"].astype(str).str.strip() == "")]
        if not unresolved.empty:
            can_include = unresolved[(unresolved["Staff"].astype(str).str.strip() != "") & (unresolved["Branch"].astype(str).str.strip() != "")]
            needs_staff_branch = len(unresolved) - len(can_include)
            st.warning(f"{len(can_include)} campaign(s) with Staff and Branch identified can be included despite a missing course. {needs_staff_branch} campaign(s) still need Staff or Branch review.")
        if st.button("Generate report", type="primary"):
            # Include every positive-result campaign, including brand-new campaigns
            # whose staff/branch cannot yet be inferred. Unknown campaigns are listed
            # separately instead of being silently dropped from the report totals.
            all_campaigns = edited.copy()
            all_campaigns["Staff"] = all_campaigns["Staff"].fillna("").astype(str).str.strip()
            all_campaigns["Branch"] = all_campaigns["Branch"].fillna("").astype(str).str.strip()
            all_campaigns["Course"] = all_campaigns["Course"].fillna("").astype(str).str.strip()
            all_campaigns["Course"] = all_campaigns["Course"].replace("", "Unclassified course")
            # Any course label containing "Hiring" is a hiring outcome
            # (for example Hiring, Medical Hiring, Coordinator Hiring, or Hiring GDA).
            # Keep these results separate from Meta lead totals, but report them by staff.
            _is_hiring_campaign = all_campaigns["Course"].str.contains(r"\bhiring\b", case=False, na=False)
            hiring_campaigns = all_campaigns[_is_hiring_campaign].copy()
            lead_campaigns = all_campaigns[~_is_hiring_campaign].copy()

            assigned = lead_campaigns[
                (lead_campaigns["Staff"] != "") & (lead_campaigns["Branch"] != "")
            ].copy()
            unassigned = lead_campaigns[
                (lead_campaigns["Staff"] == "") | (lead_campaigns["Branch"] == "")
            ].copy()
            grouped = assigned.groupby(["Branch", "Staff", "Course"], sort=False).agg(
                Results=("Results", "sum"), Spent=("Spent", "sum")
            ).reset_index()
            lines = [f"*📋 Leads Count  ·  {date_value.strftime('%d/%m/%Y')}*", ""]
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
            if not unassigned.empty:
                unassigned_spend = float(unassigned["Spent"].sum())
                lines.extend(["*New / Unassigned Campaigns*  —  Cost: "
                              f"{round(unassigned_spend * factor, 2)} KD", "——————————"])
                for _, rr in unassigned.sort_values("Results", ascending=False).iterrows():
                    lines.append(
                        f"{rr['Campaign']}  -  {int(rr['Results'])} Leads  -  "
                        f"{round(float(rr['Spent']) * factor, 3)} KD"
                    )
                lines.append("")
            # Grand totals cover all campaigns, not just those with inferred assignments.
            grand_leads = int(pd.to_numeric(lead_campaigns["Results"], errors="coerce").fillna(0).sum())
            grand_spent = float(pd.to_numeric(all_campaigns["Spent"], errors="coerce").fillna(0).sum())
            # Use the same branch-to-market mapping for hiring as for leads.
            # This supports multiple Kuwait branches (including Abu Halifa) and
            # avoids assuming that every branch name is itself a market name.
            _branch_market_alias = {
                "mangaf": "Kuwait", "salmiya": "Kuwait", "abu halifa": "Kuwait",
                "abu khalifa": "Kuwait", "kuwait": "Kuwait",
                "bahrain": "Bahrain", "gufool": "Bahrain", "manama": "Bahrain",
                "al gufool": "Bahrain",
                "kerala": "Kerala", "konni": "Kerala", "kochi": "Kerala",
                "malappuram": "Kerala", "trivandrum": "Kerala",
            }
            _hiring_market_defaults = {"Kuwait": 0, "Bahrain": 0, "Kerala": 0}
            for _, _hire_row in hiring_campaigns.iterrows():
                _hire_branch = str(_hire_row.get("Branch", "")).strip().lower()
                _hire_market = _branch_market_alias.get(_hire_branch)
                if _hire_market is None:
                    continue
                _hiring_market_defaults[_hire_market] += int(
                    pd.to_numeric(pd.Series([_hire_row.get("Results", 0)]), errors="coerce").fillna(0).iloc[0]
                )
            # Show hiring outcomes separately, including the responsible staff member.
            hiring_assigned = hiring_campaigns[
                (hiring_campaigns["Staff"] != "") & (hiring_campaigns["Branch"] != "")
            ].copy()
            hiring_unassigned = hiring_campaigns[
                (hiring_campaigns["Staff"] == "") | (hiring_campaigns["Branch"] == "")
            ].copy()
            hiring_grouped = hiring_assigned.groupby(
                ["Branch", "Staff", "Course"], sort=False
            ).agg(Results=("Results", "sum")).reset_index()
            lines.extend(["", "*👥 Hiring Results by Staff*", ""])
            for branch in BRANCH_ORDER + [b for b in hiring_grouped["Branch"].unique() if b not in BRANCH_ORDER]:
                branch_hiring = hiring_grouped[hiring_grouped["Branch"] == branch]
                if branch_hiring.empty:
                    continue
                lines.extend([f"*{branch} — Hiring*", "——————————"])
                for _, hire_row in branch_hiring.sort_values("Results", ascending=False).iterrows():
                    lines.append(
                        f"{hire_row['Staff']}  -  {hire_row['Course']}  -  {int(hire_row['Results'])} Hiring"
                    )
                lines.append("")
            if not hiring_unassigned.empty:
                lines.extend(["*Unassigned Hiring Campaigns*", "——————————"])
                for _, hire_row in hiring_unassigned.iterrows():
                    lines.append(
                        f"{hire_row['Campaign']}  -  {int(hire_row['Results'])} Hiring"
                    )
                lines.append("")
            lines.extend(["——————————", f"*🏆 Grand Total  —  {grand_leads} Leads  |  Total Hiring: {int(pd.to_numeric(hiring_campaigns['Results'], errors='coerce').fillna(0).sum())}  |  Total Cost: {round(grand_spent * factor, 2)} KD*"])
            report = "\n".join(lines)
            # Persist this upload in session state so AI tools remain available after reruns.
            st.session_state["_dt_ai_report_context"] = {
                "date": date_value.strftime("%d/%m/%Y"),
                "upload_fingerprint": hashlib.sha256(uploaded.getvalue()).hexdigest(),
                "campaigns": lead_campaigns[["Campaign", "Results", "Spent", "Staff", "Course", "Branch"]].to_dict("records"),
                "hiring_campaigns": hiring_campaigns[["Campaign", "Results", "Staff", "Course", "Branch"]].to_dict("records"),
                "factor": float(factor),
                "yesterday": None,
            }
            if yesterday_uploaded is not None:
                try:
                    _hist_frame = load_campaign_report(yesterday_uploaded, mappings)
                    st.session_state["_dt_ai_report_context"]["yesterday"] = {
                        "leads": int(_hist_frame["Results"].sum()) if not _hist_frame.empty else 0,
                        "spend_kwd": float(_hist_frame["Spent"].sum()) * float(factor) if not _hist_frame.empty else 0.0,
                    }
                except Exception:
                    pass
            st.subheader("3. Generated report")
            st.code(report, language=None)
            st.markdown("### Daily Lead Generation Report")
            st.caption("Lead and spend figures are calculated from the Meta export. Enter hiring outcomes separately because they are not supplied by Meta Ads.")
            _market_alias = {
                "mangaf":"Kuwait","salmiya":"Kuwait","abu halifa":"Kuwait","abu khalifa":"Kuwait","kuwait":"Kuwait",
                "bahrain":"Bahrain","gufool":"Bahrain","manama":"Bahrain","al gufool":"Bahrain",
                "kerala":"Kerala","konni":"Kerala","kochi":"Kerala","malappuram":"Kerala","trivandrum":"Kerala"
            }
            _market_data = {"Kuwait":{"leads":0,"spend":0.0},"Bahrain":{"leads":0,"spend":0.0},"Kerala":{"leads":0,"spend":0.0}}
            for _,_rpt_row in all_campaigns.iterrows():
                _m = _market_alias.get(str(_rpt_row.get("Branch","")).strip().lower(),"Unassigned")
                if _m not in _market_data: _market_data[_m]={"leads":0,"spend":0.0}
                if not re.search(r"\bhiring\b", str(_rpt_row.get("Course", "")), flags=re.IGNORECASE):
                    _market_data[_m]["leads"] += int(float(_rpt_row.get("Results",0) or 0))
                # Hiring campaign spend remains part of the market's ad spend.
                _market_data[_m]["spend"] += float(_rpt_row.get("Spent",0) or 0)*float(factor)
            _market_names=["Kuwait","Bahrain","Kerala"]+(["Unassigned"] if "Unassigned" in _market_data else [])
            _market_rows=[(n,_market_data[n]["leads"],_market_data[n]["spend"]) for n in _market_names]

            # Hiring is a separate operational metric entered by market. It is
            # deliberately never added to Meta Ads lead results or ad spend.
            st.markdown("#### Enter hiring figures (separate from leads)")
            _hc=st.columns(3); _hiring={}
            for _i,_name in enumerate(["Kuwait","Bahrain","Kerala"]):
                with _hc[_i]:
                    _default_hiring = int(_hiring_market_defaults.get(_name, 0))
                    _hiring[_name]=st.number_input(
                        f"{_name} hiring count", min_value=0, step=1, value=_default_hiring,
                        key=f"dt_daily_hiring_v2_{_name.lower()}",
                        help="Pre-filled from campaigns whose course name contains 'Hiring'. Staff-level results are shown separately in the generated report. Hiring is never added to Meta Ads leads."
                    )

            _branch_rows=[]
            for _name in ["Mangaf","Salmiya"]:
                _num=int(pd.to_numeric(
                    lead_campaigns.loc[
                        lead_campaigns["Branch"].astype(str).str.strip().str.lower()==_name.lower(),
                        "Results"
                    ], errors="coerce"
                ).fillna(0).sum())
                _branch_rows.append((_name,_num))

            # Reconcile the report's market rows against the all-campaign grand
            # totals before creating downloadable files. Unassigned campaigns
            # remain visible as their own row instead of disappearing.
            _market_leads_total=sum(int(row[1]) for row in _market_rows)
            _market_spend_total=sum(float(row[2]) for row in _market_rows)
            if _market_leads_total != grand_leads or abs(_market_spend_total-grand_spent*factor) > 0.01:
                st.error("The market breakdown does not reconcile with the overall totals. Check campaign branch assignments before downloading.")
                st.stop()

            _report_preview_rows=[
                {"Market":name,"Leads":int(leads),"Hiring":int(_hiring.get(name,0)),"Ad Spend":f"{float(spend):.3f} KD"}
                for name,leads,spend in _market_rows
            ]
            _report_preview_rows.append({
                "Market":"Total",
                "Leads":grand_leads,
                "Hiring":sum(int(v) for v in _hiring.values()),
                "Ad Spend":f"{grand_spent*factor:.3f} KD"
            })
            st.markdown("#### Report preview")
            st.dataframe(pd.DataFrame(_report_preview_rows), use_container_width=True, hide_index=True)
            st.caption("Total Leads and Hiring are separate totals. Hiring is not included in the lead count.")
            _word_bytes,_pdf_bytes=build_daily_report_files(
                date_value, grand_leads, grand_spent*factor, _market_rows, _hiring, _branch_rows
            )
            _dl1,_dl2=st.columns(2)
            with _dl1:
                st.download_button("Download Daily Report (.docx)",_word_bytes,f"dreamztree_daily_leads_{date_value.strftime('%Y%m%d')}.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
            with _dl2:
                st.download_button("Download Daily Report (.pdf)",_pdf_bytes,f"dreamztree_daily_leads_{date_value.strftime('%Y%m%d')}.pdf","application/pdf",use_container_width=True)
            st.download_button("Download report (.txt)", report.encode("utf-8"), f"dreamztree_leads_{date_value.strftime('%Y%m%d')}.txt", "text/plain")
            st.download_button("Download reviewed mappings (.csv)", edited[["Campaign", "Staff", "Course", "Branch"]].to_csv(index=False).encode("utf-8-sig"), "dreamztree_campaign_mapping_updated.csv", "text/csv")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total leads included", f"{grand_leads:,}")
            m2.metric("Total cost", f"{round(grand_spent * factor, 2):.2f} KD")
            m3.metric("Campaigns included", f"{len(all_campaigns):,}")
            st.subheader("Performance analytics")
            # Build charts from the same complete campaign set used by the report.
            # The former "valid" variable belonged to a separate helper and was
            # undefined in this scope, causing a NameError after report generation.
            analytics_data = all_campaigns.copy()
            analytics_data["Branch"] = analytics_data["Branch"].fillna("").astype(str).str.strip().replace("", "Unassigned")
            analytics_data["Course"] = analytics_data["Course"].fillna("").astype(str).str.strip().replace("", "Unclassified course")
            analytics_data["Results"] = pd.to_numeric(analytics_data["Results"], errors="coerce").fillna(0)
            analytics_data["Spent"] = pd.to_numeric(analytics_data["Spent"], errors="coerce").fillna(0.0)
            branch_chart = analytics_data.groupby("Branch", as_index=False).agg(Leads=("Results", "sum"), Spend_USD=("Spent", "sum"))
            branch_chart["Spend_KWD"] = branch_chart["Spend_USD"] * factor
            course_chart = analytics_data.groupby("Course", as_index=False)["Results"].sum().sort_values("Results", ascending=False).head(12)
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
        # Persistent AI workspace: rendered outside the Generate report button branch.
        ai_context = st.session_state.get("_dt_ai_report_context")
        if ai_context and ai_context.get("upload_fingerprint") == hashlib.sha256(uploaded.getvalue()).hexdigest():
            st.divider()
            st.subheader("✦ AI Marketing Intelligence")
            st.caption("Python calculates all figures. AI interprets the verified report data; no budgets are changed automatically.")
            ai_campaigns = pd.DataFrame(ai_context.get("campaigns", []))
            if not ai_campaigns.empty:
                ai_metrics = build_ai_metrics(ai_campaigns, float(ai_context.get("factor", 1.0)))
                ai_metrics["hiring"] = ai_context.get("hiring_campaigns", [])
                with st.container(border=True):
                    st.markdown("#### Smart alerts")
                    for alert in rule_based_insights(ai_metrics):
                        if alert["level"] == "high": st.error(alert["text"])
                        elif alert["level"] == "medium": st.warning(alert["text"])
                        else: st.info(alert["text"])
                with st.container(border=True):
                    st.markdown("#### Branch performance intelligence")
                    if ai_metrics["branches"]:
                        st.dataframe(pd.DataFrame(ai_metrics["branches"]), use_container_width=True, hide_index=True)
                    else:
                        st.info("Branch comparisons will appear when campaigns have recognised branch assignments.")
                with st.container(border=True):
                    st.markdown("#### Budget recommendations")
                    if ai_metrics["budget_recommendations"]:
                        st.dataframe(pd.DataFrame(ai_metrics["budget_recommendations"]), use_container_width=True, hide_index=True)
                    else:
                        st.info("No clear budget recommendation from this upload. More campaign history and lead-quality data would improve decisions.")
                    st.caption("Suggestions use relative cost-per-lead comparisons. Validate lead quality before changing budgets.")
                with st.container(border=True):
                    st.markdown("#### Lead forecasting & historical trend")
                    historical_files = st.file_uploader(
                        "Optional: upload previous daily Meta exports for trend analysis",
                        type=["xlsx", "xls"], accept_multiple_files=True, key="dt_ai_historical_exports",
                        help="Upload one Excel export per day. These files are used only for this session's trend calculations."
                    )
                    historical_daily = []
                    for hist_file in historical_files or []:
                        try:
                            hist_raw = pd.read_excel(hist_file)
                            hist_cols = list(hist_raw.columns)
                            hist_norm = [normalize(x) for x in hist_cols]
                            def _hist_col(pred, fallback):
                                return next((hist_cols[i] for i, value in enumerate(hist_norm) if pred(value)), hist_cols[min(fallback, len(hist_cols)-1)])
                            hc = _hist_col(lambda x: "campaign" in x, 0)
                            hr = _hist_col(lambda x: "result" in x and "initial" not in x, 1)
                            hs = _hist_col(lambda x: "spent" in x or "amount" in x, 2)
                            historical_daily.append({
                                "file": hist_file.name,
                                "leads": int(pd.to_numeric(hist_raw[hr], errors="coerce").fillna(0).sum()),
                                "spend_kwd": float(pd.to_numeric(hist_raw[hs], errors="coerce").fillna(0).sum()) * float(ai_context.get("factor", 1.0)),
                            })
                        except Exception as hist_exc:
                            st.warning(f"Could not read historical file {hist_file.name}: {hist_exc}")
                    yesterday_data = ai_context.get("yesterday")
                    daily_series = list(historical_daily)
                    if yesterday_data:
                        daily_series.append({"file": "Yesterday's upload", **yesterday_data})
                    daily_series.append({"file": "Today's upload", "leads": ai_metrics["totals"]["leads"], "spend_kwd": ai_metrics["totals"]["spend_kwd"]})
                    average_leads = round(sum(x["leads"] for x in daily_series) / len(daily_series))
                    average_spend = sum(x["spend_kwd"] for x in daily_series) / len(daily_series)
                    forecast = {
                        "next_day_leads": int(average_leads),
                        "next_7_day_leads": int(average_leads * 7),
                        "basis": f"{len(daily_series)} uploaded day(s)",
                    }
                    fc1, fc2, fc3 = st.columns(3)
                    fc1.metric("Indicative next-day leads", f"{forecast['next_day_leads']:,}")
                    fc2.metric("Indicative 7-day leads", f"{forecast['next_7_day_leads']:,}")
                    fc3.metric("Forecast basis", forecast["basis"])
                    st.caption("This is a simple average run-rate projection, not a trained predictive model. Upload at least 7 daily exports to support a more representative weekly review.")
                    if len(daily_series) >= 7:
                        st.dataframe(pd.DataFrame(daily_series), use_container_width=True, hide_index=True)
                    ai_metrics["historical_daily_average"] = {
                        "days_uploaded": len(daily_series),
                        "average_daily_leads": average_leads,
                        "average_daily_spend_kwd": round(average_spend, 3),
                        "indicative_next_7_day_leads": forecast["next_7_day_leads"],
                    }
                ai_config = get_ai_config()
                with st.container(border=True):
                    st.markdown("#### AI analyst & management summary")
                    if ai_config:
                        st.caption(f"AI provider connected: {ai_config['provider']} · Model: {ai_config['model']}")
                    else:
                        st.caption("Local analytics active · Add a Gemini or Groq API key for AI narrative analysis")
                    if st.button("Generate AI analysis", key="dt_ai_analyse"):
                        if ai_config:
                            prompt = (
                                "You are a careful performance marketing analyst for a multi-branch training academy. "
                                "Analyse only these verified figures. Provide an executive summary, strongest and weakest signals, "
                                "branch observations, campaign risks, practical budget recommendations, and a concise management summary "
                                "for the uploaded reporting period. If historical daily averages are supplied, include a weekly management summary; otherwise label it as a single-period summary. Do not invent causes, audiences, conversions, or missing data. "
                                "Label hypotheses clearly and do not call a single-day report a weekly report.\\n\\n"
                                + json.dumps(ai_metrics, ensure_ascii=False, default=str)
                            )
                            with st.spinner("Analysing campaign performance…"):
                                try:
                                    st.session_state["_dt_ai_analysis_result"] = generate_ai_response(ai_config['api_key'], prompt, model=ai_config['model'], provider=ai_config['provider'])
                                    st.session_state["_dt_ai_analysis_is_local"] = False
                                except Exception as exc:
                                    st.session_state["_dt_ai_analysis_result"] = build_local_management_summary(ai_metrics)
                                    st.session_state["_dt_ai_analysis_is_local"] = True
                                    st.session_state["_dt_ai_analysis_error"] = str(exc)
                        else:
                            st.session_state["_dt_ai_analysis_result"] = build_local_management_summary(ai_metrics)
                            st.session_state["_dt_ai_analysis_is_local"] = True
                    if st.session_state.get("_dt_ai_analysis_error") and st.session_state.get("_dt_ai_analysis_is_local"):
                        st.warning("AI providers were unavailable, so this summary was generated locally from verified report figures.")
                        st.caption(st.session_state.pop("_dt_ai_analysis_error"))
                    if st.session_state.get("_dt_ai_analysis_result"):
                        st.markdown(st.session_state["_dt_ai_analysis_result"])
                    st.markdown("#### Chat with your reports")
                    question = st.text_input("Ask a question about this report", key="dt_ai_question", placeholder="Which branch has the lowest cost per lead?")
                    if st.button("Ask AI", key="dt_ai_ask") and question.strip():
                        local_answer = answer_report_question(ai_metrics, question)
                        if local_answer:
                            st.session_state["_dt_ai_chat_answer"] = local_answer
                            st.session_state["_dt_ai_chat_is_local"] = True
                            st.session_state.pop("_dt_ai_chat_error", None)
                        elif ai_config:
                            prompt = (
                                "Answer using only the supplied report data. Show calculations when useful. "
                                "If the data cannot answer the question, say so. Do not invent metrics. "
                                "Separate attributed figures from unassigned campaign totals.\\n\\nDATA:\\n"
                                + json.dumps(ai_metrics, ensure_ascii=False, default=str)
                                + "\\n\\nQUESTION:\\n" + question.strip()
                            )
                            with st.spinner("Checking report data…"):
                                try:
                                    st.session_state["_dt_ai_chat_answer"] = generate_ai_response(ai_config['api_key'], prompt, model=ai_config['model'], provider=ai_config['provider'])
                                    st.session_state["_dt_ai_chat_is_local"] = False
                                    st.session_state.pop("_dt_ai_chat_error", None)
                                except Exception as exc:
                                    st.session_state["_dt_ai_chat_answer"] = build_local_management_summary(ai_metrics)
                                    st.session_state["_dt_ai_chat_is_local"] = True
                                    st.session_state["_dt_ai_chat_error"] = str(exc)
                        else:
                            st.session_state["_dt_ai_chat_answer"] = (
                                "I can answer common metric questions locally. Try asking about lowest cost per lead, "
                                "most leads, total spend, total leads, campaign count, or unassigned campaigns."
                            )
                            st.session_state["_dt_ai_chat_is_local"] = True
                    if st.session_state.get("_dt_ai_chat_error") and st.session_state.get("_dt_ai_chat_is_local"):
                        st.warning("AI providers were unavailable. Showing a local report summary instead.")
                        st.caption(st.session_state.pop("_dt_ai_chat_error"))
                    if st.session_state.get("_dt_ai_chat_answer"):
                        st.markdown(st.session_state["_dt_ai_chat_answer"])
                        st.caption("Local calculation" if st.session_state.get("_dt_ai_chat_is_local") else "AI-generated answer")
                    if st.button("Clear AI answers", key="dt_ai_clear"):
                        for key in ["_dt_ai_analysis_result", "_dt_ai_chat_answer", "_dt_ai_analysis_error", "_dt_ai_chat_error"]:
                            st.session_state.pop(key, None)
                        st.rerun()


    except Exception as e:
        st.error(f"Could not process this Excel file: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
