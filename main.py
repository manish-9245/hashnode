import streamlit as st
import json
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill
import io
import re
import numpy as np

def get_nested_value(data, path):
    keys = path.split('.')
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return None
    return data

def strip_comments(text):
    return re.sub(r'//.*', '', text)

def values_equal(v1, v2):
    """Compare two values recursively, handling nested structures"""
    if v1 is None and v2 is None:
        return True
    if v1 is None or v2 is None:
        return False

    # Handle dictionaries
    if isinstance(v1, dict) and isinstance(v2, dict):
        if set(v1.keys()) != set(v2.keys()):
            return False
        for key in v1:
            if not values_equal(v1[key], v2[key]):
                return False
        return True

    # Check if both are non-string sequences
    v1_is_seq = isinstance(v1, (list, tuple, np.ndarray)) and not isinstance(v1, (str, bytes))
    v2_is_seq = isinstance(v2, (list, tuple, np.ndarray)) and not isinstance(v2, (str, bytes))
    
    if v1_is_seq and v2_is_seq:
        try:
            v1_list = list(v1)
            v2_list = list(v2)
        except TypeError:
            return False
            
        if len(v1_list) != len(v2_list):
            return False
            
        for i in range(len(v1_list)):
            if not values_equal(v1_list[i], v2_list[i]):
                return False
        return True
        
    elif v1_is_seq or v2_is_seq:
        return False
        
    # Handle all other types
    try:
        return v1 == v2
    except (ValueError, TypeError):
        return False

st.title("JSON Reconciliation App")

# File upload inputs
json1_file = st.file_uploader("Upload System 1 JSON", type=["json"])
json2_file = st.file_uploader("Upload System 2 JSON", type=["json"])
nav_input = st.text_area("Enter navigation paths (comma-separated)", placeholder="key1.key2,key3.key4.key5")

if st.button("Reconcile") and json1_file and json2_file and nav_input:
    # Load and clean JSON inputs
    raw1 = json1_file.read().decode('utf-8')
    raw2 = json2_file.read().decode('utf-8')
    system1 = json.loads(strip_comments(raw1))
    system2 = json.loads(strip_comments(raw2))

    # If top-level is list of dicts, merge them
    for d in (system1, system2):
        if isinstance(d, list):
            merged = {}
            for item in d:
                if isinstance(item, dict):
                    merged.update(item)
            if d is system1:
                system1 = merged
            else:
                system2 = merged

    # Parse stringified JSON values
    for d in (system1, system2):
        for k, v in list(d.items()):
            if isinstance(v, str):
                try:
                    d[k] = json.loads(strip_comments(v))
                except Exception:
                    pass

    # Parse navigation paths
    nav_paths = [p.strip() for p in nav_input.split(',') if p.strip()]

    # Determine keys
    set1, set2 = set(system1.keys()), set(system2.keys())
    matches = sorted(set1 & set2)
    orphans1 = sorted(set1 - set2)
    orphans2 = sorted(set2 - set1)

    # Build DataFrame rows
    rows = []
    # Matches: two rows per key
    for key in matches:
        id_, version = key.rsplit('.', 1)
        for sys_name, sys_data in [("system1", system1), ("system2", system2)]:
            row = {"system": sys_name, "id": id_, "version": version}
            for path in nav_paths:
                row[path] = get_nested_value(sys_data.get(key, {}), path)
            rows.append(row)
    # Orphans
    for key in orphans1:
        id_, version = key.rsplit('.', 1)
        row = {"system": "system1", "id": id_, "version": version}
        for path in nav_paths:
            row[path] = get_nested_value(system1.get(key, {}), path)
        rows.append(row)
    for key in orphans2:
        id_, version = key.rsplit('.', 1)
        row = {"system": "system2", "id": id_, "version": version}
        for path in nav_paths:
            row[path] = get_nested_value(system2.get(key, {}), path)
        rows.append(row)

    cols = ["system", "id", "version"] + nav_paths
    df = pd.DataFrame(rows, columns=cols)

    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.append(df.columns.tolist())
    # Define fills
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

    # Write data rows
    for i, row in enumerate(rows, start=2):
        for j, col in enumerate(df.columns, start=1):
            ws.cell(row=i, column=j, value=row[col])

    # Color Excel cells
    for pair_start in range(0, len(matches)*2, 2):
        df_row1 = pair_start
        df_row2 = pair_start + 1
        excel_row1 = 2 + pair_start
        excel_row2 = 2 + pair_start + 1
        
        for path in nav_paths:
            col_idx = df.columns.get_loc(path) + 1
            v1 = df.at[df_row1, path]
            v2 = df.at[df_row2, path]
            
            equal = values_equal(v1, v2)
            fill = green_fill if equal else red_fill
            ws.cell(row=excel_row1, column=col_idx).fill = fill
            ws.cell(row=excel_row2, column=col_idx).fill = fill

    # Orphans colored yellow
    orphan_start = 2 + len(matches)*2
    for r in range(orphan_start, orphan_start + len(orphans1) + len(orphans2)):
        for path in nav_paths:
            col_idx = df.columns.get_loc(path) + 1
            ws.cell(row=r, column=col_idx).fill = yellow_fill

    # Prepare Excel download
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    st.download_button(
        "Download Excel",
        data=excel_buffer,
        file_name="recon.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Generate styled HTML
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    # Matches/mismatches
    for pair_start in range(0, len(matches)*2, 2):
        i, j = pair_start, pair_start + 1
        for path in nav_paths:
            v1 = df.at[i, path]
            v2 = df.at[j, path]
            equal = values_equal(v1, v2)
            color = "lightgreen" if equal else "lightcoral"
            styles.at[i, path] = f"background-color:{color}"
            styles.at[j, path] = f"background-color:{color}"
    # Orphans
    for idx in range(len(matches)*2, len(df)):
        for path in nav_paths:
            styles.at[idx, path] = "background-color:khaki"

    styled = df.style.apply(lambda _: styles, axis=None)
    html = styled.to_html()
    st.download_button(
        "Download HTML",
        data=html,
        file_name="recon.html",
        mime="text/html"
    )
