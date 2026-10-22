
    if len(staff_hits) == 1:
        staff = staff_hits[0]
        staff_rows = mappings[mappings["Staff"].astype(str).str.strip().str.casefold() == staff.casefold()]
        known_branches = [str(x).strip() for x in staff_rows["Branch"] if str(x).strip()]
        # Use the configured staff/branch order as the default home branch only when
        # the staff member appears under exactly one branch in the mapping history.
        branches = sorted(set(known_branches))
        if explicit_branch:
            branch = explicit_branch
            branch_status = "explicit branch"
        elif len(branches) == 1:
            branch = branches[0]
            branch_status = "staff branch"
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
