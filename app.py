import streamlit as st
import fitz
import re
import os
from datetime import datetime

# ============ 讀取 HTML 模板 ============
def load_template():
    with open(os.path.join(os.path.dirname(__file__), "debit_note.html"), "r", encoding="utf-8") as f:
        return f.read()

HTML_TEMPLATE = load_template()

# ============ 欄位提取邏輯 ============
def extract_from_text(text):
    result = {}
    lines = text.split('\n')

    def find(pattern, flags=re.IGNORECASE):
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else ""

    # --- Zurich format ---
    result['insured_name']          = find(r'CONSTRUCTION\s+ENGINEERING\s+LIMITED|The\s+Insured[:\s]*(.+?)(?:\n|$)', re.IGNORECASE)
    if not result['insured_name'] or 'CONSTRUCTION' not in result['insured_name'].upper():
        result['insured_name']      = find(r'Insured[:\s]*([^\n]+)')

    result['policy_number']         = find(r'Policy\s*(?:No|Number)[:\s.]*([A-Z0-9/]+)')
    result['insurance_class']       = find(r'Policy\s+Class[:\s]*([^\n]+)')

    # Premium
    prem_m = re.search(r'Premium\s*:\s*HKD[*\s]*([\d,]+\.\d{2})', text)
    result['premium'] = prem_m.group(1) if prem_m else find(r'Total\s+Gross\s+Premium[:\s]*([\d,]+\.\d{2})')

    # Levy
    levy_m = re.search(r'IA\s+LEVY\s+HKD[*\s]*([\d,]+\.\d{2})', text)
    result['levy'] = levy_m.group(1) if levy_m else find(r'Premium\s+Levy.*?:\s*([\d,]+\.\d{2})')

    # Total
    total_m = re.search(r'Total\s+payable\s*:\s*HKD[*\s]*([\d,]+\.\d{2})', text)
    result['total_amount'] = total_m.group(1) if total_m else ""

    # Period
    period_m = re.search(r'FROM\s+(\d{2}/\d{2}/\d{4})\s+TO\s+(\d{2}/\d{2}/\d{4})', text)
    if period_m:
        result['policy_effective_date'] = period_m.group(1)
        result['policy_expiry_date'] = period_m.group(2)
    else:
        result['policy_effective_date'] = find(r'Period\s+of\s+Insurance[:\s]*([^\n]+)')
        result['policy_expiry_date'] = ""

    result['insurer_name'] = "Zurich Insurance Company Ltd" if 'ZURICH' in text.upper() else (
        "Chubb Insurance Hong Kong Limited" if 'CHUBB' in text.upper() else ""
    )

    # Chubb specifics
    if 'CHUBB' in text.upper():
        chubb_policy = find(r'Policy\s*No[:\s]*([A-Z]{4}\d+)')
        if chubb_policy:
            result['policy_number'] = chubb_policy
        # Chubb total amount due
        chubb_total = find(r'Total\s+Amount\s+Due[:\s]*([\d,]+\.\d{2})')
        if chubb_total:
            result['total_amount'] = chubb_total
        # Chubb insured
        chubb_insured = find(r'Insured[:\s]*([^\n]+)')
        if chubb_insured and len(chubb_insured) > 3:
            result['insured_name'] = chubb_insured
        # Period
        chubb_period = find(r'Period\s+of\s+Insurance[:\s]*([\d]{2}-[A-Z]{3}-\d{4}\s+to\s+\d{2}-[A-Z]{3}-\d{4})')
        if chubb_period:
            result['policy_effective_date'] = chubb_period
            result['policy_expiry_date'] = ""

    # Defaults
    result['debit_note_date'] = datetime.now().strftime('%d/%m/%Y')
    result['commission'] = ""
    result['billing_date'] = datetime.now().strftime('%d/%m/%Y')
    result['receipt_date'] = ""
    result['receipt_method'] = ""

    return result


# ============ 生成 HTML ============
def generate_html(data):
    html = HTML_TEMPLATE
    for key, val in data.items():
        html = html.replace(f"{{{{ {key} }}}}", str(val) if val else "")
    return html


# ============ Streamlit UI ============
st.set_page_config(page_title="Debit Note / Receipt Generator", layout="wide")
st.title("📄 Debit Note / Receipt Generator")

# --- Upload ---
uploaded_file = st.file_uploader("📤 Upload Policy / Quotation PDF", type=["pdf"])

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = "\n".join([page.get_text() for page in doc])

    st.info(f"📑 偵測到保險公司：{'🟦 Zurich' if 'ZURICH' in full_text.upper() else ('🟥 Chubb' if 'CHUBB' in full_text.upper() else '❓ 未識別')}")

    if st.button("🚀 提取資料", type="primary"):
        extracted = extract_from_text(full_text)
        st.session_state['data'] = extracted
        st.success("✅ 提取完成！")

# --- 編輯 + 生成 ---
if 'data' in st.session_state:
    d = st.session_state['data']

    st.subheader("✏️ 確認 / 修改欄位")

    doc_type = st.radio("📄 選擇生成文件類型", ["Debit Note", "Receipt"], horizontal=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        d['debit_note_date'] = st.text_input("Debit Note Date", d.get('debit_note_date',''))
        d['policy_number'] = st.text_input("Policy No.", d.get('policy_number',''))
    with col2:
        d['insured_name'] = st.text_input("Insured Name", d.get('insured_name',''))
        d['insurer_name'] = st.text_input("Insurer", d.get('insurer_name',''))
    with col3:
        d['insurance_class'] = st.text_input("Insurance Class", d.get('insurance_class',''))
        d['billing_date'] = st.text_input("Billing Date", d.get('billing_date',''))

    col4, col5, col6 = st.columns(3)
    with col4:
        d['policy_effective_date'] = st.text_input("Effective Date", d.get('policy_effective_date',''))
        d['premium'] = st.text_input("Premium (HKD)", d.get('premium',''))
    with col5:
        d['policy_expiry_date'] = st.text_input("Expiry Date", d.get('policy_expiry_date',''))
        d['levy'] = st.text_input("Levy (HKD)", d.get('levy',''))
    with col6:
        d['total_amount'] = st.text_input("Total Amount (HKD)", d.get('total_amount',''))
        d['commission'] = st.text_input("Commission (HKD)", d.get('commission',''))

    # Receipt 專用欄位
    if doc_type == "Receipt":
        st.markdown("#### 💰 收款資料")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            d['receipt_date'] = st.text_input("收款日期", d.get('receipt_date',''))
        with col_r2:
            d['receipt_method'] = st.text_input("收款方法 (例: CHEQUE / FPS / BANK TRANSFER)", d.get('receipt_method',''))

    d['doc_type'] = doc_type

    if st.button(f"📄 生成 {doc_type}", type="primary"):
        html_out = generate_html(d)
        st.session_state['html_out'] = html_out
        st.success(f"✅ {doc_type} 生成成功！")

if 'html_out' in st.session_state:
    st.components.v1.html(st.session_state['html_out'], height=900, scrolling=True)
    st.markdown("---")
    st.info("🖨️ 撳下面 Print 可以 Save as PDF（建議揀 **Landscape / 橫向**）")
    print_btn = f"""
    <button onclick="window.print()" style="padding:10px 20px;font-size:16px;cursor:pointer;
    background:#4CAF50;color:white;border:none;border-radius:5px;">
    🖨️ Print / Save as PDF</button>
    """
    st.components.v1.html(print_btn, height=60)
