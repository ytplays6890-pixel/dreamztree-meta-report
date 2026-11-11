"""Executive marketing intelligence views for Dreamztree.

This module is intentionally read-only: it analyses the reviewed campaign
assignments and never edits uploaded rows, mappings, or campaign settings.
"""
import pandas as pd
import plotly.express as px
import streamlit as st


def _safe_frame(frame):
    required = ["Campaign", "Results", "Spent", "Staff", "Course", "Branch"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError("Campaign data is missing required columns: " + ", ".join(missing))
    data = frame[required].copy()
    data["Campaign"] = data["Campaign"].fillna("").astype(str)
    for column in ["Staff", "Course", "Branch"]:
        data[column] = data[column].fillna("").astype(str).str.strip()
    data["Results"] = pd.to_numeric(data["Results"], errors="coerce").fillna(0)
    data["Spent"] = pd.to_numeric(data["Spent"], errors="coerce").fillna(0.0)
    data["Cost per lead (KD)"] = 0.0
    valid = data["Results"] > 0
    data.loc[valid, "Cost per lead (KD)"] = (
        data.loc[valid, "Spent"] / data.loc[valid, "Results"]
    )
    data["Attribution"] = (
        data["Staff"].ne("") & data["Branch"].ne("")
    ).map({True: "Assigned", False: "Needs review"})
    data["Course display"] = data["Course"].replace("", "Unclassified course")
    data["Staff display"] = data["Staff"].replace("", "Unassigned")
    data["Branch display"] = data["Branch"].replace("", "Unassigned")
    return data


def _aggregate(data, dimension, exchange_rate):
    result = (
        data.groupby(dimension, dropna=False, as_index=False)
        .agg(
            Campaigns=("Campaign", "count"),
            Leads=("Results", "sum"),
            Spend_USD=("Spent", "sum"),
        )
    )
    result["Spend_KD"] = result["Spend_USD"] * float(exchange_rate or 1.0)
    result["CPL_KD"] = result.apply(
        lambda row: row["Spend_KD"] / row["Leads"] if row["Leads"] else 0.0,
        axis=1,
    )
    return result.sort_values(["Leads", "Spend_KD"], ascending=[False, False])


def render_intelligence_dashboard(frame, exchange_rate, report_date=None):
    """Render a read-only executive overview from the reviewed campaign table."""
    data = _safe_frame(frame)
    total_leads = int(data["Results"].sum())
    total_spend_usd = float(data["Spent"].sum())
    total_spend_kd = total_spend_usd * float(exchange_rate or 1.0)
    campaign_count = int(len(data))
    assigned_mask = data["Attribution"].eq("Assigned")
    assigned_leads = int(data.loc[assigned_mask, "Results"].sum())
    assigned_spend = float(data.loc[assigned_mask, "Spent"].sum()) * float(exchange_rate or 1.0)
    cpl = total_spend_kd / total_leads if total_leads else 0.0
    coverage = (int(assigned_mask.sum()) / campaign_count * 100) if campaign_count else 0.0

    st.markdown("## Executive overview")
    subtitle = "Reviewed campaign data · Read-only analytics"
    if report_date:
        subtitle += " · " + str(report_date)
    st.caption(subtitle)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total leads", f"{total_leads:,}")
    k2.metric("Ad spend", f"{total_spend_kd:,.3f} KD")
    k3.metric("Blended CPL", f"{cpl:,.3f} KD")
    k4.metric("Campaigns", f"{campaign_count:,}")
    k5.metric("Mapping coverage", f"{coverage:.1f}%")

    unassigned = data.loc[~assigned_mask]
    if not unassigned.empty:
        st.warning(
            f"{len(unassigned):,} campaign(s) need staff/branch review. "
            "Their leads and spend are included in the overall totals, but excluded "
            "from attributed branch and staff comparisons."
        )

    assigned = data.loc[assigned_mask].copy()
    if assigned.empty:
        st.info("Branch and staff analytics will appear after campaigns have both a staff and branch assignment.")
        st.dataframe(data, use_container_width=True, hide_index=True)
        return

    branch = _aggregate(assigned, "Branch", exchange_rate)
    staff = _aggregate(assigned, "Staff", exchange_rate)
    course = _aggregate(assigned.assign(Course=assigned["Course display"]), "Course", exchange_rate)
    campaign = assigned.copy()
    campaign["Spend_KD"] = campaign["Spent"] * float(exchange_rate or 1.0)
    campaign["CPL_KD"] = campaign.apply(
        lambda row: row["Spend_KD"] / row["Results"] if row["Results"] else 0.0,
        axis=1,
    )

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown("### Leads by branch")
        fig = px.bar(
            branch.sort_values("Leads", ascending=True),
            x="Leads", y="Branch", orientation="h", text="Leads",
            color_discrete_sequence=["#9B8AFB"],
        )
        fig.update_layout(
            template="plotly_dark", height=330, margin=dict(l=8, r=8, t=15, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Leads", yaxis_title="", showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right:
        st.markdown("### Spend by branch")
        spend_chart = branch.sort_values("Spend_KD", ascending=True)
        fig = px.bar(
            spend_chart, x="Spend_KD", y="Branch", orientation="h", text="Spend_KD",
            color_discrete_sequence=["#5CC8B0"],
        )
        fig.update_traces(texttemplate="%{text:.3f} KD", textposition="outside")
        fig.update_layout(
            template="plotly_dark", height=330, margin=dict(l=8, r=20, t=15, b=8),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Spend (KD)", yaxis_title="", showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    tab_branch, tab_staff, tab_course, tab_campaigns = st.tabs(
        ["Branch performance", "Staff performance", "Course performance", "Campaign detail"]
    )
    display_columns = {
        "Campaigns": st.column_config.NumberColumn(format="%d"),
        "Leads": st.column_config.NumberColumn(format="%d"),
        "Spend_KD": st.column_config.NumberColumn("Spend (KD)", format="%.3f"),
        "CPL_KD": st.column_config.NumberColumn("CPL (KD)", format="%.3f"),
    }
    with tab_branch:
        st.dataframe(branch, use_container_width=True, hide_index=True, column_config=display_columns)
    with tab_staff:
        st.dataframe(staff, use_container_width=True, hide_index=True, column_config=display_columns)
    with tab_course:
        st.dataframe(course, use_container_width=True, hide_index=True, column_config=display_columns)
    with tab_campaigns:
        show = campaign[[
            "Campaign", "Staff", "Course display", "Branch", "Results", "Spend_KD", "CPL_KD"
        ]].rename(columns={"Course display": "Course"})
        st.dataframe(show.sort_values(["Results", "Spend_KD"], ascending=[False, False]),
                     use_container_width=True, hide_index=True)
        st.download_button(
            "Download attributed campaign analytics (CSV)",
            show.to_csv(index=False).encode("utf-8-sig"),
            "dreamztree_campaign_intelligence.csv",
            "text/csv",
            key="dt_download_intelligence_csv",
        )

    st.caption(
        f"Attributed totals: {assigned_leads:,} leads · {assigned_spend:,.3f} KD spend. "
        "Overall KPIs include every positive-result campaign in the reviewed upload. "
        "Branch/staff/course tables include campaigns with both staff and branch assigned. "
        "CPL is spend divided by results; no conversion or lead-quality data is inferred."
    )
