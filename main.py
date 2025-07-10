import streamlit as st
import json
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill
import io
import re

# Function to get nested value from dict based on navigation path
def get_nested_value(data, path):
    keys = path.split('.')
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return None
    return data

def strip_comments(text):
    # Remove JavaScript-style comments
    return re.sub(r'//.*', '', text)
    
st.title("JSON Reconciliation App")

json1_file = st.file_uploader("Upload System 1 JSON", type=["json"] )
json2_file = st.file_uploader("Upload System 2 JSON", type=["json"] )
nav_input = st.text_area("Enter navigation paths (comma-separated)", placeholder="key1.key2,key3.key4.key5")

if st.button("Reconcile") and json1_file and json2_file and nav_input:
    # Load JSONs with comment stripping
    raw1 = json1_file.read().decode('utf-8')
    raw2 = json2_file.read().decode('utf-8')
    system1 = json.loads(strip_comments(raw1))
    system2 = json.loads(strip_comments(raw2))
    # If top-level is a list of dicts, merge into a single dict
    if isinstance(system1, list):
        merged = {}
        for item in system1:
            if isinstance(item, dict):
                merged.update(item)
        system1 = merged
    if isinstance(system2, list):
        merged = {}
        for item in system2:
            if isinstance(item, dict):
                merged.update(item)
        system2 = merged
    # If top-level values are stringified JSON, parse them
    for d in (system1, system2):
        if isinstance(d, dict):  # ensure dict before iterating
            for k, v in d.items():
                if isinstance(v, str):
                    try:
                        d[k] = json.loads(strip_comments(v))
                    except Exception:
                        pass
    # Parse navigation paths
    nav_paths = [p.strip() for p in nav_input.split(',') if p.strip()]
    # Determine matching and orphan keys
    set1 = set(system1.keys())
    set2 = set(system2.keys())
    matches = sorted(set1 & set2)
    orphans1 = sorted(set1 - set2)
    orphans2 = sorted(set2 - set1)

    # Build rows for matches and orphans
    rows = []
    # Matches: two rows per key (system1, system2)
    for key in matches:
        id_, version = key.split('.', 1)
        for sys_name, sys_data in [("system1", system1), ("system2", system2)]:
            row = {"system": sys_name, "id": id_, "version": version}
            for path in nav_paths:
                row[path] = get_nested_value(sys_data.get(key, {}), path)
            rows.append(row)
    # Orphans in system1
    for key in orphans1:
        id_, version = key.split('.', 1)
        row = {"system": "system1", "id": id_, "version": version}
        for path in nav_paths:
            row[path] = get_nested_value(system1.get(key, {}), path)
        rows.append(row)
    # Orphans in system2
    for key in orphans2:
        id_, version = key.split('.', 1)
        row = {"system": "system2", "id": id_, "version": version}
        for path in nav_paths:
            row[path] = get_nested_value(system2.get(key, {}), path)
        rows.append(row)

    # Create DataFrame with separate columns per navigation path
    cols = ["system", "id", "version"] + nav_paths
    df = pd.DataFrame(rows, columns=cols)

    # Create Excel workbook with styling
    wb = Workbook()
    ws = wb.active
    # Write header
    ws.append(df.columns.tolist())
    # Define fills
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    # Write data rows
    for i, row in enumerate(rows, start=2):
        for j, col in enumerate(df.columns, start=1):
            ws.cell(row=i, column=j, value=row[col])
    # Apply color coding for matches
    for idx in range(len(matches)):
        base = 2 + idx * 2
        for path in nav_paths:
            col_idx = df.columns.get_loc(path) + 1
            cell1 = ws.cell(row=base, column=col_idx)
            cell2 = ws.cell(row=base + 1, column=col_idx)
            if cell1.value == cell2.value:
                cell1.fill = green_fill
                cell2.fill = green_fill
            else:
                cell1.fill = red_fill
                cell2.fill = red_fill
    # Apply yellow fill for orphans
    orphan_start = 2 + len(matches) * 2
    orphan_count = len(orphans1) + len(orphans2)
    for r in range(orphan_start, orphan_start + orphan_count):
        for path in nav_paths:
            col_idx = df.columns.get_loc(path) + 1
            ws.cell(row=r, column=col_idx).fill = yellow_fill
    # Prepare Excel for download
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)

    st.download_button(
        "Download Excel", data=excel_buffer,
        file_name="recon.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Create HTML with styling via pandas Styler
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    # Color matches/mismatches
    for idx in range(len(matches) * 2):
        if idx % 2 == 0:
            other = idx + 1
            for path in nav_paths:
                if df.at[idx, path] == df.at[other, path]:
                    styles.at[idx, path] = "background-color:lightgreen"
                    styles.at[other, path] = "background-color:lightgreen"
                else:
                    styles.at[idx, path] = "background-color:lightcoral"
                    styles.at[other, path] = "background-color:lightcoral"
    # Color orphans yellow
    for idx in range(len(matches) * 2, len(df)):
        for path in nav_paths:
            styles.at[idx, path] = "background-color:khaki"
    styled = df.style.apply(lambda _: styles, axis=None)
    html = styled.to_html()

    st.download_button(
        "Download HTML", data=html,
        file_name="recon.html", mime="text/html"
    )
