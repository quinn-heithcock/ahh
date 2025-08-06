import streamlit as st
import pdfplumber
import re

# ------------------ ARCHITECTURAL EXTRACTOR ------------------
def extract_store_info(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\b(?:[A-Z]-\d{3}[A-Z]?|[A-Z] \d\.\d)\b', '', text)

    start_pos = re.search(r'STORE\s*#\s*\d+', text, re.IGNORECASE)
    if start_pos:
        text = text[start_pos.start():]

    store_pattern = r'S(?i:TORE)\s*#\s*\d+'
    space_pattern = r'(?:S(?i:pace)|S(?i:uite)) #?\w+'
    mall_pattern = r'\b([A-Z][a-z]+(?: (?:[a-z]+|[A-Z][a-z]+)){0,4})\b'
    address_pattern = r'(\d{1,5}(?: [A-Z]\.)?(?: [A-Z][a-z]{1,15}){1,3})'
    city_state_pattern = r'([A-Z][a-z]+(?: [A-Z][a-z]+)*,?\s*[A-Z]{2},?\s*\d{5}(?:-\d{4})?)'

    store_match = re.search(store_pattern, text)
    mall_text = text[store_match.end():store_match.end() + 300] if store_match else text

    mall_match = re.search(mall_pattern, mall_text)
    space_match = re.search(space_pattern, text)

    address_text = text[space_match.end():space_match.end() + 300] if space_match else text
    address_match = re.search(address_pattern, address_text)
    city_state_match = re.search(city_state_pattern, address_text)

    parts = [
        "JOURNEYS " + store_match.group() if store_match else "ERROR_store_not_found",
        mall_match.group(1) if mall_match else "ERROR_mall_not_found",
        space_match.group() if space_match else "ERROR_space_not_found",
        address_match.group(1) if address_match else "ERROR_address_not_found",
        city_state_match.group(1) if city_state_match else "ERROR_city_state_not_found"
    ]

    return "\n".join(filter(None, parts))

# ------------------ QUOTE EXTRACTOR FOR ACCEL ------------------
def extract_quote_info(pdf_path):
    quote_number = None
    quote_amount = None
    quote_date = None 

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            quote_number_match = re.search(r'Order Acknowledgement #\s*([\w-]+)', text)
            if quote_number_match:
                quote_number = quote_number_match.group(1)

            quote_amount_match = re.search(
                r'Grand Total \(Payable in U\.S\. Dollars\):\s*\$?([\d,]+\.\d{2})',
                text
            )
            if quote_amount_match:
                quote_amount = quote_amount_match.group(1)

            quote_date_match = re.search(r'Date Ordered:\s*(\d{1,2}/\d{1,2}/\d{2})', text)
            if quote_date_match:
                quote_date = quote_date_match.group(1)

            if quote_number and quote_amount and quote_date:
                break

    return {
        "quote_number": quote_number,
        "quote_amount": quote_amount,
        "quote_date": quote_date  
    }

# ------------------ QUOTE EXTRACTOR FOR CEILDECK ------------------
def extract_quote_info_ceildeck(pdf_file):
    date = None
    distributor_info = []
    total_cost = None
    delivery_cost = None

    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    date_match = re.search(r"DATE:\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
    if date_match:
        date = date_match.group(1)

    total_match = re.search(r"TOTAL\s*\$\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if total_match:
        total_cost = total_match.group(1)

    delivery_match = re.search(r"DELIVERY\s*\$\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if delivery_match:
        delivery_cost = delivery_match.group(1)

    lines = text.splitlines()
    distributor_info = []
    capture = False

    for i, line in enumerate(lines):
        if not capture:
            match = re.search(r"Distrubitor:\s*(.*?)\s*TOTAL\s*\$\s*[\d,]+\.\d{2}", line, re.IGNORECASE)
            if match:
                distributor_info.append(match.group(1).strip())  
                capture = True
                continue
        elif capture:
            distributor_info.append(line.strip())

    distributor_block = "\n".join(distributor_info).strip()

    return {
        "date": date or "Not Found",
        "distributor": distributor_block or "Not Found",
        "total_cost": total_cost or "Not Found",
        "delivery_cost": delivery_cost or "Not Found"
    }

# ------------------ VENDOR MAPPING ------------------
VENDOR_SCRIPTS = {
    "Accel": extract_quote_info_accel,
    "Ceildeck": extract_quote_info_ceildeck
}

# ------------------ STREAMLIT APP ------------------

st.title("Q's PO Helper")

# === 1. ARCHITECTURE PDF ===
st.header("Architecturals - Extract Address")
arch_file = st.file_uploader("Upload Architectural PDF", type=["pdf"], key="arch")

if arch_file:
    try:
        result = extract_store_info(arch_file)
        st.text_area("Extracted Address", result, height=200)
    except Exception as e:
        st.error(f"Error extracting address: {e}")

# === 2. QUOTE PDF ===
st.header("Quote PDF - Extract Quote Info")

vendor = st.selectbox("Select Vendor", list(VENDOR_SCRIPTS.keys()))
quote_file = st.file_uploader("Upload Quote PDF", type=["pdf"], key="quote")

if quote_file and vendor:
    try:
        result = VENDOR_SCRIPTS[vendor](quote_file)

        if vendor == "Accel":
            quote_text = (
                f"Quote Number: {result['quote_number']}\n"
                f"Quote Amount: ${result['quote_amount']}"
            )
        elif vendor == "Ceildeck":
            quote_text = (
                f"Date: {result['date']}\n"
                f"Distributor Info:\n{result['distributor']}\n\n"
                f"Total Cost: ${result['total_cost']}\n"
                f"Delivery Cost: ${result['delivery_cost']}"
            )
        else:
            quote_text = "Unknown vendor."

        st.text_area("Extracted Quote Info", quote_text, height=200)
    except Exception as e:
        st.error(f"Error extracting quote info: {e}")
