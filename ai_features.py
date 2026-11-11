"""AI and decision-support helpers for Dreamztree Meta Report."""
import os, statistics, requests, time
import pandas as pd
import streamlit as st


def _secret_value(name, default=""):
    value = str(os.environ.get(name, "")).strip()
    if not value:
        try: value = str(st.secrets.get(name, default)).strip()
        except Exception: value = str(default).strip()
    return value


def get_ai_config():
    """Prefer configured Groq free tier, then Gemini, then OpenAI."""
    groq_key = _secret_value("GROQ_API_KEY")
    if groq_key:
        return {"provider": "Groq (Free tier)", "api_key": groq_key,
                "model": _secret_value("GROQ_MODEL", "openai/gpt-oss-20b")}
    gemini_key = _secret_value("GEMINI_API_KEY")
    if gemini_key:
        return {"provider": "Gemini", "api_key": gemini_key,
                "model": _secret_value("GEMINI_MODEL", "gemini-3.8-flash")}
    openai_key = _secret_value("OPENAI_API_KEY")
    if openai_key:
        return {"provider": "OpenAI", "api_key": openai_key,
                "model": _secret_value("OPENAI_MODEL", "gpt-4o-mini")}
    return None


def _generate_openai_compatible(api_key, prompt, model, base_url, provider_label):
    is_gpt_oss = "gpt-oss" in str(model).lower()
    system_instruction = (
        "You are a precise marketing analytics assistant. Use only supplied data; never invent metrics. "
        "Answer the user's question directly and concisely."
    )
    if is_gpt_oss:
        # Groq's GPT-OSS models use max_completion_tokens and an explicit
        # reasoning format. A small legacy max_tokens budget can be consumed
        # by reasoning, leaving message.content empty.
        messages = [{"role": "user", "content": system_instruction + "\n\n" + prompt}]
        request_options = {
            "max_completion_tokens": 1800,
            "reasoning_effort": "low",
            "reasoning_format": "hidden",
        }
    else:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
        request_options = {"max_tokens": 1200}

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        **request_options,
    }
    try:
        response = requests.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=(5, 45))
    except requests.RequestException as exc:
        raise RuntimeError(f"{provider_label} request timed out or could not connect.") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"{provider_label} API error ({response.status_code}): {detail}")
    try:
        result = response.json()
        choice = result["choices"][0]
        message = choice["message"]
        content = message.get("content", "")
        if isinstance(content, list):
            answer = "\n".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            ).strip()
        else:
            answer = str(content or "").strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise RuntimeError(f"{provider_label} returned no readable text.")
    if not answer:
        finish_reason = choice.get("finish_reason", "unknown")
        raise RuntimeError(
            f"{provider_label} returned an empty answer (finish reason: {finish_reason}). "
            "Check the model's output-token limit or try another configured model."
        )
    return answer


def _generate_gemini(api_key, prompt, model):
    model = model or _secret_value("GEMINI_MODEL", "gemini-3.8-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "systemInstruction": {"parts": [{"text": "You are a precise marketing analytics assistant. Use only supplied data; never invent metrics."}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900}
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(5, 25))
    except requests.RequestException as exc:
        raise RuntimeError("Gemini request timed out or could not connect.") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"Gemini API error ({response.status_code}): {detail}")
    try:
        parts = response.json()["candidates"][0]["content"]["parts"]
        answer = "\\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned no readable text.")
    if not answer:
        raise RuntimeError("Gemini returned an empty answer.")
    return answer


def generate_ai_response(api_key, prompt, model=None, provider="Gemini"):
    """Use the selected provider and automatically fall back to Groq when configured."""
    provider_key = str(provider or "Gemini").lower()
    groq_key = _secret_value("GROQ_API_KEY")
    primary_error = None

    try:
        if "groq" in provider_key:
            return _generate_openai_compatible(
                api_key, prompt, model or _secret_value("GROQ_MODEL", "openai/gpt-oss-20b"),
                "https://api.groq.com/openai/v1", "Groq")
        if "openai" in provider_key:
            return _generate_openai_compatible(
                api_key, prompt, model or _secret_value("OPENAI_MODEL", "gpt-4o-mini"),
                "https://api.openai.com/v1", "OpenAI")
        return _generate_gemini(api_key, prompt, model)
    except Exception as exc:
        primary_error = exc

    # If GPT-OSS 20B returns no visible answer, retry once with Groq's
    # currently listed production GPT-OSS 120B model. This path is only used
    # after the primary request fails and can have different API pricing.
    if "groq" in provider_key and groq_key and "gpt-oss-20b" in str(model or _secret_value("GROQ_MODEL", "openai/gpt-oss-20b")).lower():
        fallback_model = _secret_value("GROQ_FALLBACK_MODEL", "openai/gpt-oss-120b")
        try:
            return _generate_openai_compatible(
                groq_key, prompt, fallback_model,
                "https://api.groq.com/openai/v1", "Groq fallback")
        except Exception as fallback_exc:
            raise RuntimeError(
                f"{primary_error} | Groq backup model ({fallback_model}) also failed: {fallback_exc}"
            ) from fallback_exc

    # Groq is also available as a fallback when another provider is selected.
    if groq_key and "groq" not in provider_key:
        try:
            return _generate_openai_compatible(
                groq_key, prompt, _secret_value("GROQ_MODEL", "openai/gpt-oss-20b"),
                "https://api.groq.com/openai/v1", "Groq fallback")
        except Exception as fallback_exc:
            raise RuntimeError(
                f"{primary_error} | Groq fallback also failed: {fallback_exc}"
            ) from fallback_exc
    raise primary_error

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


def answer_report_question(metrics, question):
    """Answer common report questions deterministically without an external AI API."""
    q = str(question or "").lower()
    totals = metrics.get("totals", {})
    branches = metrics.get("branches", [])
    campaigns = metrics.get("campaigns", [])
    hiring = metrics.get("hiring", [])
    money = lambda x: f"{float(x):.3f} KD"
    if "hir" in q or "recruit" in q or "staff currently" in q:
        if hiring:
            assigned_hiring = [
                row for row in hiring
                if str(row.get("Staff", "")).strip()
                and str(row.get("Branch", "")).strip()
                and ("kerala" not in q or str(row.get("Branch", "")).strip().lower() in {
                    "kerala", "konni", "kochi", "malappuram", "trivandrum"
                })
            ]
            if assigned_hiring:
                grouped = {}
                for row in assigned_hiring:
                    key = (str(row.get("Staff", "")).strip(), str(row.get("Branch", "")).strip())
                    grouped[key] = grouped.get(key, 0) + int(float(row.get("Results") or 0))
                lines = ["**Staff with hiring results in this report:**"]
                for (staff_name, branch_name), count in sorted(grouped.items(), key=lambda item: item[1], reverse=True):
                    lines.append(f"- **{staff_name}** — {branch_name}: {count} hiring")
                return "\\n".join(lines)
            return "No hiring campaigns with both staff and branch assigned were found in this report."
        return "No hiring campaign data is available in this report. Check that the campaign course is mapped to a name containing 'Hiring'."
    if any(k in q for k in ["lowest cost per lead", "lowest cpl", "cheapest lead", "lowest cost", "low cost branch", "cheapest branch", "best cpl"]):
        valid = [b for b in branches if b.get("CPL_KWD") is not None and float(b.get("Leads", 0)) > 0]
        if valid:
            best = min(valid, key=lambda x: float(x["CPL_KWD"]))
            return (f"**Lowest cost per lead: {best['Branch']}**\n\n"
                    f"- Leads: {int(best['Leads']):,}\n- Spend: {money(best['Spend_KWD'])}\n"
                    f"- Cost per lead: **{money(best['CPL_KWD'])}**\n\n"
                    "Comparison includes campaigns assigned to a recognised staff member and branch.")
        return "There are no recognised branch assignments with leads, so a branch-level cost-per-lead comparison is not available."
    if any(k in q for k in ["highest lead", "most leads", "best campaign", "top campaign"]):
        valid = [c for c in campaigns if float(c.get("Results") or 0) > 0]
        if valid:
            best = max(valid, key=lambda x: float(x.get("Results") or 0))
            return (f"**Campaign with the most leads: {best.get('Campaign','Unassigned')}**\n\n"
                    f"- Leads: {int(float(best.get('Results') or 0)):,}\n"
                    f"- Spend: {money(best.get('Cost_KWD') or 0)}\n"
                    f"- Branch: {best.get('Branch') or 'Unassigned'}")
        return "No campaign in this report has recorded leads."
    if any(k in q for k in ["highest spend", "spent most", "most expensive campaign"]):
        if campaigns:
            best = max(campaigns, key=lambda x: float(x.get("Cost_KWD") or 0))
            return f"**Highest-spend campaign: {best.get('Campaign','Unassigned')}**\n\n- Spend: {money(best.get('Cost_KWD') or 0)}\n- Leads: {int(float(best.get('Results') or 0)):,}"
    if "total lead" in q or "how many lead" in q or "lead count" in q:
        return f"**Total leads: {int(totals.get('leads',0)):,}** across {int(totals.get('campaign_count',0))} campaigns."
    if "total cost" in q or "total spend" in q or "how much" in q:
        return f"**Total spend: {money(totals.get('spend_kwd',0))}** ({float(totals.get('spend_usd',0)):.2f} USD)."
    if "unassigned" in q or "new campaign" in q:
        return (f"**Unassigned campaigns: {int(totals.get('unassigned_campaigns',0))}**\n\n"
                f"- Leads from unassigned campaigns: {int(totals.get('unassigned_leads',0)):,}\n"
                "These campaigns remain included in overall totals; no staff or branch is guessed.")
    if "campaign" in q and ("count" in q or "how many" in q or "number" in q):
        return f"**Campaigns included: {int(totals.get('campaign_count',0)):,}**."
    return None


def build_local_management_summary(metrics):
    """Create a concise, verified management summary without calling an AI service."""
    totals = metrics.get("totals", {})
    branches = metrics.get("branches", [])
    campaigns = metrics.get("campaigns", [])
    lines = [
        "### Local report summary",
        f"- **Leads:** {int(totals.get('leads',0)):,}",
        f"- **Spend:** {float(totals.get('spend_kwd',0)):.3f} KD",
        f"- **Campaigns included:** {int(totals.get('campaign_count',0)):,}",
        f"- **Unassigned campaigns:** {int(totals.get('unassigned_campaigns',0)):,}",
    ]
    valid_branches = [b for b in branches if b.get("CPL_KWD") is not None and float(b.get("Leads",0)) > 0]
    if valid_branches:
        low = min(valid_branches, key=lambda x: float(x["CPL_KWD"]))
        high = max(valid_branches, key=lambda x: float(x["CPL_KWD"]))
        lines.append(f"- **Lowest branch CPL:** {low['Branch']} ({float(low['CPL_KWD']):.3f} KD)")
        lines.append(f"- **Highest branch CPL:** {high['Branch']} ({float(high['CPL_KWD']):.3f} KD)")
    if campaigns:
        top = max(campaigns, key=lambda x: float(x.get("Results") or 0))
        lines.append(f"- **Most leads from one campaign:** {top.get('Campaign','Unassigned')} ({int(float(top.get('Results') or 0)):,} leads)")
    lines.append("\n*Calculated locally from this upload. No Gemini API call is required for these figures.*")
    return "\n".join(lines)
