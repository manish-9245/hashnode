import streamlit as st
import json
import openpyxl
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from io import BytesIO

def split_key(key):
    if '.' not in key:
        return key, ""
    return key.rsplit('.', 1)

def parse_nested_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return value
    return value

def extract_value(data, path):
    keys = path.split('.')
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

st.title("JSON Reconciliation Tool")

system1_file = st.file_uploader("Upload System 1 JSON", type=['json'])
system2_file = st.file_uploader("Upload System 2 JSON", type=['json'])
attr_paths_input = st.text_area("Enter attribute paths (one per line):")
attr_paths = [p.strip() for p in attr_paths_input.split('\n') if p.strip()]

if st.button("Generate Reconciliation Report") and system1_file and system2_file and attr_paths:
    system1_data = json.load(system1_file)
    system2_data = json.load(system2_file)
    
    # Process System 1: Split keys and parse nested JSON
    sys1_processed = {}
    for key, value in system1_data.items():
        id_part, version_part = split_key(key)
        sys1_processed[key] = {
            'id': id_part,
            'version': version_part,
            'data': parse_nested_json(value)
        }
    
    # Process System 2
    sys2_processed = {}
    for key, value in system2_data.items():
        id_part, version_part = split_key(key)
        sys2_processed[key] = {
            'id': id_part,
            'version': version_part,
            'data': parse_nested_json(value)
        }
    
    # Identify matched and orphan keys
    all_keys = set(sys1_processed.keys()) | set(sys2_processed.keys())
    matched_keys = []
    orphans_sys1 = []
    orphans_sys2 = []
    
    for key in all_keys:
        if key in sys1_processed and key in sys2_processed:
            matched_keys.append(key)
        elif key in sys1_processed:
            orphans_sys1.append(key)
        else:
            orphans_sys2.append(key)
    
    # Generate report rows
    report_rows = []
    
    # Process matched keys
    for key in matched_keys:
        id1 = sys1_processed[key]['id']
        ver1 = sys1_processed[key]['version']
        data1 = sys1_processed[key]['data']
        data2 = sys2_processed[key]['data']
        
        for path in attr_paths:
            val1 = extract_value(data1, path)
            val2 = extract_value(data2, path)
            
            if val1 == val2:
                color = 'green'
            else:
                color = 'red'
            
            report_rows.append({
                'system': 'Both',
                'id': id1,
                'version': ver1,
                'attribute': path,
                'value_sys1': val1,
                'value_sys2': val2,
                'color': color
            })
    
    # Process orphans
    for key in orphans_sys1:
        id1 = sys1_processed[key]['id']
        ver1 = sys1_processed[key]['version']
        data1 = sys1_processed[key]['data']
        
        for path in attr_paths:
            val1 = extract_value(data1, path)
            report_rows.append({
                'system': 'System1',
                'id': id1,
                'version': ver1,
                'attribute': path,
                'value_sys1': val1,
                'value_sys2': None,
                'color': 'yellow'
            })
    
    for key in orphans_sys2:
        id2 = sys2_processed[key]['id']
        ver2 = sys2_processed[key]['version']
        data2 = sys2_processed[key]['data']
        
        for path in attr_paths:
            val2 = extract_value(data2, path)
            report_rows.append({
                'system': 'System2',
                'id': id2,
                'version': ver2,
                'attribute': path,
                'value_sys1': None,
                'value_sys2': val2,
                'color': 'yellow'
            })
    
    # Generate Excel Report
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ['System', 'ID', 'Version', 'Attribute', 'Value (System1)', 'Value (System2)']
    ws.append(headers)
    
    color_fills = {
        'green': PatternFill(start_color='00FF00', end_color='00FF00', fill_type='solid'),
        'red': PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid'),
        'yellow': PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    }
    
    for row in report_rows:
        data_row = [
            row['system'],
            row['id'],
            row['version'],
            row['attribute'],
            str(row['value_sys1']) if row['value_sys1'] is not None else '',
            str(row['value_sys2']) if row['value_sys2'] is not None else ''
        ]
        ws.append(data_row)
        
        # Apply color to entire row
        row_idx = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row_idx, column=col_idx).fill = color_fills[row['color']]
    
    # Auto-adjust column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width
    
    excel_buffer = BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    
    # Generate HTML Report
    html_content = """
    <html>
    <head>
        <title>Reconciliation Report</title>
        <style>
            table {
                border-collapse: collapse;
                width: 100%;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        </style>
    </head>
    <body>
        <h1>Reconciliation Report</h1>
        <table>
            <tr>
                <th>System</th>
                <th>ID</th>
                <th>Version</th>
                <th>Attribute</th>
                <th>Value (System1)</th>
                <th>Value (System2)</th>
            </tr>
    """
    
    for row in report_rows:
        color_style = f"background-color: {row['color']};"
        html_content += f"""
            <tr style="{color_style}">
                <td>{row['system']}</td>
                <td>{row['id']}</td>
                <td>{row['version']}</td>
                <td>{row['attribute']}</td>
                <td>{str(row['value_sys1']) if row['value_sys1'] is not None else ''}</td>
                <td>{str(row['value_sys2']) if row['value_sys2'] is not None else ''}</td>
            </tr>
        """
    
    html_content += """
        </table>
    </body>
    </html>
    """
    
    html_buffer = BytesIO()
    html_buffer.write(html_content.encode('utf-8'))
    html_buffer.seek(0)
    
    # Provide download links
    st.success("Report generated successfully!")
    st.download_button(
        label="Download Excel Report",
        data=excel_buffer,
        file_name="reconciliation_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.download_button(
        label="Download HTML Report",
        data=html_buffer,
        file_name="reconciliation_report.html",
        mime="text/html"
    )
