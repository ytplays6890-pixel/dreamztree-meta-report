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
.block-container:has([data-testid="stTabs"]) { width:min(680px, 48vw) !important; max-width:680px !important; margin-left:auto !important; margin-right:5vw !important; padding-top:7vh !important; }
.block-container:has([data-testid="stTabs"]) [data-testid="stTabs"],
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] { max-width:100% !important; width:100% !important; }
.block-container:has([data-testid="stTabs"]) [data-testid="stForm"] { background:rgba(15,20,34,.76) !important; border:1px solid rgba(255,255,255,.15) !important; border-radius:22px !important; padding:22px !important; backdrop-filter:blur(18px) !important; }
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
    """Render falling snow and the Santa peek animation with optional Christmas music and a silent Santa animation."""
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

    # Santa uses the supplied transparent 3D reference image and peeks from a random
    # vertical edge position every 30 seconds, silently, without voice or sound effects.
    components.html(r'''<!doctype html><html><head><style>
      html,body{margin:0;background:transparent;overflow:hidden}
      #santa{position:fixed;left:0;top:0;width:min(5vw,76px);height:auto;
        pointer-events:none;z-index:2147483647;opacity:0;will-change:transform,opacity;
        filter:drop-shadow(0 6px 10px rgba(0,0,0,.35))}
      #santa.show{opacity:1;animation:peekIn 4.6s ease-in-out both}
      @keyframes peekIn{0%{transform:translate(var(--from-x),var(--from-y)) var(--flip,scaleX(1)) scale(.94);opacity:0}
        18%,72%{transform:translate(var(--to-x),var(--to-y)) var(--flip,scaleX(1)) scale(1);opacity:1}
        100%{transform:translate(var(--from-x),var(--from-y)) var(--flip,scaleX(1)) scale(.94);opacity:0}}
      @media(max-width:700px){#santa{width:min(18vw,68px)}}
      @media(prefers-reduced-motion:reduce){#santa.show{animation:none;opacity:0}}
    </style></head><body><img id="santa" alt="Santa peeking" src="data:image/png;base64,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">
    <script>
      (()=>{
        const santa=document.getElementById('santa');
        let portal=null, hostWin=null;
        function mountSanta(){
          try{
            const hostDoc=window.parent.document;
            hostWin=window.parent;
            const previous=hostDoc.getElementById('dt-santa-viewport-overlay');
            if(previous)previous.remove();
            portal=hostDoc.createElement('div');
            portal.id='dt-santa-viewport-overlay';
            portal.style.cssText='position:fixed;left:0;bottom:18px;width:100vw;height:0;z-index:2147483647;pointer-events:none;overflow:visible;';
            const img=hostDoc.createElement('img');
            img.alt='Santa peeking';
            img.src=santa.src;
            img.style.cssText='position:absolute;left:0;bottom:0;width:76px;height:auto;max-width:none;pointer-events:none;filter:drop-shadow(0 6px 10px rgba(0,0,0,.35));';
            portal.appendChild(img);
            hostDoc.body.appendChild(portal);
            return img;
          }catch(e){return null;}
        }
        const portalSanta=mountSanta();
        function peek(){
          if(!portalSanta||!hostWin)return;
          const sw=Math.min(76,hostWin.innerWidth*.05);
          portalSanta.style.width=sw+'px';
          if(portalSanta._peekAnimation)portalSanta._peekAnimation.cancel();
          portalSanta._peekAnimation=portalSanta.animate([
            {transform:'translateX('+(-sw+18)+'px) scale(.94)',opacity:0},
            {transform:'translateX(18px) scale(1)',opacity:1,offset:.18},
            {transform:'translateX(18px) scale(1)',opacity:1,offset:.72},
            {transform:'translateX('+(-sw+18)+'px) scale(.94)',opacity:0}
          ],{duration:4600,easing:'ease-in-out',fill:'both'});
        }
        if(portalSanta){setTimeout(peek,2500);setInterval(peek,30000);}
        window.addEventListener('resize',peek);
      })();
    </script></body></html>''', height=1, scrolling=False)


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

      /* Lightweight winter village foreground: static SVG with tiny window glow only. */
      .dt-winter-village {
        position: fixed; left: 0; right: 0; bottom: 58px;
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
        .dt-winter-village { bottom: 42px; height: 104px; opacity: .56; }
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
        <path d="M0 226 Q200 206 400 228 T800 221 T1200 228 T1600 215 V240 H0Z" fill="url(#dtVillageSnow)"/>
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


def main():
    require_login()
    st.session_state.pop("login_just_succeeded", False)
    inject_premium_theme()
    inject_performance_patch()
    inject_dashboard_snow()
    st.markdown(r"""
    <style>
      [data-testid="stExpander"] { border:1px solid rgba(145,164,190,.20)!important; border-radius:12px!important; overflow:hidden; background:rgba(18,24,34,.78)!important; box-shadow:0 8px 24px rgba(0,0,0,.16),inset 0 1px 0 rgba(255,255,255,.035)!important; transition:border-color .18s ease,box-shadow .18s ease!important; }
      [data-testid="stExpander"]:hover { border-color:rgba(103,216,208,.38)!important; box-shadow:0 10px 28px rgba(0,0,0,.22),0 0 0 1px rgba(103,216,208,.045)!important; }
      [data-testid="stExpander"] details > summary { min-height:54px!important; padding:13px 17px!important; background:linear-gradient(90deg,rgba(103,216,208,.075),rgba(255,255,255,.018))!important; color:#e8eef7!important; font-weight:680!important; letter-spacing:.015em!important; }
      [data-testid="stExpander"] details > summary:hover { background:linear-gradient(90deg,rgba(103,216,208,.12),rgba(255,255,255,.035))!important; }
      [data-testid="stExpander"] details > summary p,[data-testid="stExpander"] details > summary span { color:#e8eef7!important; font-weight:680!important; }
      [data-testid="stExpander"] details > summary svg { color:#86dcd4!important; }
      [data-testid="stExpander"] details[open] > summary { border-bottom:1px solid rgba(145,164,190,.16)!important; }
      [data-testid="stExpander"] [data-testid="stExpanderDetails"] { background:rgba(9,13,20,.30)!important; padding:18px!important; }
      .stButton button,[data-testid="stDownloadButton"] button { border-radius:9px!important; border:1px solid rgba(145,164,190,.23)!important; background:rgba(255,255,255,.045)!important; color:#e7edf6!important; box-shadow:none!important; transition:transform .16s ease,border-color .16s ease,background .16s ease!important; }
      .stButton button:hover,[data-testid="stDownloadButton"] button:hover { transform:translateY(-1px)!important; border-color:rgba(103,216,208,.42)!important; background:rgba(103,216,208,.075)!important; }
      @media(prefers-reduced-motion:reduce) { [data-testid="stExpander"],.stButton button,[data-testid="stDownloadButton"] button { transition:none!important; } }
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
        st.markdown('<a href="#report-form" style="display:block;padding:10px 12px;color:#d8d2e2;text-decoration:none;border-radius:10px">▤ &nbsp; Reports</a><a href="#campaign-insights" style="display:block;padding:10px 12px;color:#d8d2e2;text-decoration:none;border-radius:10px">◇ &nbsp; Campaign Mapping</a>', unsafe_allow_html=True)
        if st.button("♧  Team Chat", key="side_chat", use_container_width=True):
            st.query_params["page"] = "chat"; st.rerun()
        if st.button("♧  Game Zone", key="side_game", use_container_width=True):
            st.query_params["page"] = "game"; st.rerun()
        st.markdown('<div class="dt-side-label">Account</div><div class="dt-side-foot">● &nbsp; Secure session<br><span style="color:#a69bb6">Dreamztree reporting workspace</span></div>', unsafe_allow_html=True)

    # Compact utility row: actions and editable reporting date share one line,
    # eliminating the large empty area left by the removed hero/header.
    game_col, chat_col, signout_col, date_col = st.columns([1.0,  1.0, .82, 1.35], vertical_alignment="center")
    with game_col:
        if st.button("🎮 Game Zone", key="open_game_zone_main", use_container_width=True):
            st.query_params["page"] = "game"; st.rerun()
    with chat_col:
        if st.button("💬 Team Chat", key="open_team_chat_main", use_container_width=True):
            st.query_params["page"] = "chat"; st.rerun()
    with signout_col:
        if st.button("Sign out", key="sign_out_main", use_container_width=True):
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
    with date_col:
        st.markdown('<div class="dt-date-shell"><div class="dt-date-caption">Reporting date · Editable</div>', unsafe_allow_html=True)
        date_value = st.date_input("Reporting date", value=datetime.today().date(), key="reporting_date_selector", label_visibility="collapsed", help="Choose the date used in report headings and downloaded files.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div id="report-form"></div><div id="campaign-insights"></div>', unsafe_allow_html=True)
    with st.expander("Report settings     ·     Currency and campaign mapping", expanded=False):
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
    if uploaded is None:
        st.markdown('<div class="dt-upload-note">✦ &nbsp; Your workspace is ready. Add today’s Excel export to generate the report; include the previous day for a performance comparison.</div>', unsafe_allow_html=True)
        with st.expander("Campaign intelligence     ·     Review assigned teams and courses", expanded=False):
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
