"""AI and decision-support helpers for Dreamztree Meta Report."""
import os, statistics, requests
import pandas as pd
import streamlit as st


def _secret_value(name, default=""):
    value = str(os.environ.get(name, "")).strip()
    if not value:
        try: value = str(st.secrets.get(name, default)).strip()
        except Exception: value = str(default).strip()
    return value


def get_ai_config():
    """Prefer Gemini when configured; retain OpenAI as a backward-compatible fallback."""
    gemini_key = _secret_value("GEMINI_API_KEY")
    if gemini_key:
        return {"provider": "Gemini", "api_key": gemini_key,
                "model": _secret_value("GEMINI_MODEL", "gemini-2.5-flash")}
    openai_key = _secret_value("OPENAI_API_KEY")
    if openai_key:
        return {"provider": "OpenAI", "api_key": openai_key,
                "model": _secret_value("OPENAI_MODEL", "gpt-4o-mini")}
    return None


def generate_ai_response(api_key, prompt, model=None, provider="Gemini"):
    if provider.lower() == "openai":
        model = model or _secret_value("OPENAI_MODEL", "gpt-4o-mini")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [
                {"role": "system", "content": "You are a precise marketing analytics assistant. Use only supplied data; never invent metrics."},
                {"role": "user", "content": prompt}], "temperature": 0.2},
            timeout=60)
        if response.status_code >= 400:
            try: detail = response.json().get("error", {}).get("message", response.text)
            except Exception: detail = response.text
            raise RuntimeError(f"OpenAI API error ({response.status_code}): {detail}")
        return response.json()["choices"][0]["message"]["content"].strip()

    model = model or _secret_value("GEMINI_MODEL", "gemini-2.5-flash")
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={"systemInstruction": {"parts": [{"text": "You are a precise marketing analytics assistant. Use only supplied data; never invent metrics."}]},
              "contents": [{"role": "user", "parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.2}},
        timeout=60)
    if response.status_code >= 400:
        try:
            err = response.json().get("error", {})
            detail = err.get("message", response.text)
        except Exception: detail = response.text
        raise RuntimeError(f"Gemini API error ({response.status_code}): {detail}")
    try:
        parts = response.json()["candidates"][0]["content"]["parts"]
        return "\\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned no text. The response may have been blocked by safety filters.")


def build_ai_metrics(campaigns, usd_to_kwd):
    rows = campaigns.copy()
    for col in ["Campaign", "Staff", "Course", "Branch"]:
        if col not in rows: rows[col] = ""
        rows[col] = rows[col].fillna("").astype(str).str.strip()
    rows["Results"] = pd.to_numeric(rows.get("Results", 0), errors="coerce").fillna(0)
    rows["Spent"] = pd.to_numeric(rows.get("Spent", 0), errors="coerce").fillna(0.0)
    rows["Cost_KWD"] = rows["Spent"] * float(usd_to_kwd)
    rows["CPL_KWD"] = rows.apply(lambda r: r["Cost_KWD"] / r["Results"] if r["Results"] > 0 else None, axis=1)
    assigned = rows[(rows["Staff"] != "") & (rows["Branch"] != "")]
    branches = []
    if not assigned.empty:
        grouped = assigned.groupby("Branch", as_index=False).agg(Leads=("Results", "sum"), Spend_KWD=("Cost_KWD", "sum"), Campaigns=("Campaign", "count"))
        grouped["CPL_KWD"] = grouped.apply(lambda r: r["Spend_KWD"] / r["Leads"] if r["Leads"] else None, axis=1)
        branches = grouped.round(3).to_dict("records")
    output = rows[["Campaign", "Results", "Spent", "Staff", "Course", "Branch", "Cost_KWD", "CPL_KWD"]].copy()
    output["Cost_KWD"] = output["Cost_KWD"].round(3)
    output["CPL_KWD"] = output["CPL_KWD"].round(3)
    unassigned = rows[(rows["Staff"] == "") | (rows["Branch"] == "")]
    cpl_rows = rows[(rows["Results"] > 0) & (rows["Staff"] != "") & (rows["Branch"] != "")]
    median_cpl = float(cpl_rows["CPL_KWD"].median()) if not cpl_rows.empty else None
    recommendations = []
    if median_cpl and median_cpl > 0:
        for _, r in cpl_rows.iterrows():
            if r["Results"] >= 2 and r["CPL_KWD"] <= median_cpl * .75:
                action = "Consider a cautious budget increase; validate lead quality first"
            elif r["CPL_KWD"] >= median_cpl * 1.5:
                action = "Review targeting, creative and lead quality before adding budget"
            else: continue
            recommendations.append({"Campaign":r["Campaign"],"Leads":int(r["Results"]),"Cost per lead (KD)":round(float(r["CPL_KWD"]),3),"Action":action})
    return {"totals":{"leads":int(rows["Results"].sum()),"spend_usd":round(float(rows["Spent"].sum()),2),
        "spend_kwd":round(float(rows["Cost_KWD"].sum()),3),"campaign_count":int(len(rows)),
        "assigned_campaigns":int(len(assigned)),"unassigned_campaigns":int(len(unassigned)),
        "unassigned_leads":int(unassigned["Results"].sum())},
        "branches":branches,"campaigns":output.to_dict("records"),
        "budget_recommendations":recommendations,
        "median_assigned_cpl_kwd":round(median_cpl,3) if median_cpl is not None else None}


def rule_based_insights(metrics):
    alerts=[]; totals=metrics.get("totals",{})
    if totals.get("unassigned_campaigns",0):
        alerts.append({"level":"medium","text":f"{totals['unassigned_campaigns']} campaign(s) are unassigned. Their {totals.get('unassigned_leads',0)} leads and spend remain in grand totals, but branch/staff attribution is incomplete."})
    rows=metrics.get("campaigns",[])
    cpls=[r.get("CPL_KWD") for r in rows if r.get("CPL_KWD") is not None]
    median_cpl=statistics.median(cpls) if cpls else None
    for r in rows:
        if r.get("Results",0)<=0 and r.get("Spent",0)>0:
            alerts.append({"level":"high","text":f"{r['Campaign']}: spend recorded but no results in this export. Check attribution and delivery."})
        elif median_cpl and r.get("CPL_KWD") is not None and r["CPL_KWD"]>median_cpl*1.75:
            alerts.append({"level":"medium","text":f"{r['Campaign']}: CPL ({r['CPL_KWD']:.3f} KD) is substantially above campaign median ({median_cpl:.3f} KD). Review before changing budget."})
    if not alerts: alerts.append({"level":"low","text":"No rule-based cost or attribution alerts were triggered for this upload."})
    return alerts[:12]


def forecast_from_daily_totals(yesterday_leads, yesterday_spend_kwd, today_leads, today_spend_kwd):
    if yesterday_leads is None:
        daily_leads=max(0,int(today_leads)); daily_spend=max(0.0,float(today_spend_kwd)); basis="1-day baseline"
    else:
        daily_leads=max(0,round((int(yesterday_leads)+int(today_leads))/2))
        daily_spend=max(0.0,(float(yesterday_spend_kwd)+float(today_spend_kwd))/2); basis="2-day average"
    return {"next_day_leads":int(daily_leads),"next_7_day_leads":int(daily_leads*7),
        "basis":basis,"estimated_daily_spend_kwd":round(daily_spend,3)}
