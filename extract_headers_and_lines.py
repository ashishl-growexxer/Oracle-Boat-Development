import ast
import pandas as pd

def extract_values_only(data, prefix=""):
    flat = {}
    for key, val in data.items():
        new_key = f"{prefix}.{key}" if prefix else key

        # Typical structure: {"value": "...", "coordinates": [...]}
        if isinstance(val, dict) and "value" in val:
            flat[new_key] = val.get("value", "")
            continue

        # Nested objects → recursive flatten
        if isinstance(val, dict):
            flat.update(extract_values_only(val, new_key))
        else:
            # simple values (string, list, etc.)
            flat[new_key] = val

    return flat

def extract_header_df(llm_json):
    """
    Extracts PO header fields from the first available page.
    Works even if some fields are missing.
    """

    # Ensure we only look at real pages
    pages = {k: v for k, v in llm_json.items() if k.startswith("page_")}
    if not pages:
        return pd.DataFrame([{}])

    first_page_key = sorted(pages.keys())[0]
    first_page = pages.get(first_page_key, {})
    priority_fields = first_page.get("priority_fields") or {}

    # Flatten all nested value fields
    values = extract_values_only(priority_fields)

    header = {
        "po_number": values.get("po_number", ""),
        "po_date": values.get("po_date", ""),
        "due_date": values.get("due_date", ""),

        "buyer_info": values.get("customer_details.buyer_info", ""),
        "bill_to": values.get("customer_details.bill_to", ""),

        "vendor_id": values.get("vendor_details.vendor_id", ""),
        "name": values.get("vendor_details.name", ""),
        "address": values.get("vendor_details.address", ""),
        "contact": values.get("vendor_details.contact", ""),

        "ship_to": values.get("shipping_details.ship_to", ""),
        "ship_from": values.get("shipping_details.ship_from", ""),
        "ship_date": values.get("shipping_details.ship_date", ""),
        "ship_via": values.get("shipping_details.ship_via", ""),
        "shipping_instruction": values.get("shipping_details.shipping_instruction", ""),

        "total_amount": values.get("order_summary.total_amount", "")
    }

    return pd.DataFrame([header])

def extract_line_items_df(llm_json):
    """
    Safely extracts line items from ALL pages.
    Handles missing keys, missing value fields, wrong formats.
    """
    all_rows = []

    # Only iterate actual pages: page_1, page_2, ...
    pages = {k: v for k, v in llm_json.items() if k.startswith("page_")}

    for page_key, page in pages.items():
        page_no = page_key.replace("page_", "")

        priority_fields = page.get("priority_fields") or {}

        line_items = priority_fields.get("line_items") or []

        if not isinstance(line_items, list):
            print(f"⚠️ line_items on {page_key} is not a list → skipping")
            continue

        if not line_items:
            print(f"⚠️ No line_items found on {page_key}")
            continue

        for item in line_items:

            # Standard LLM output: {"value": "..."}
            def extract_val(obj):
                if isinstance(obj, dict):
                    return obj.get("value", "")
                return obj or ""

            row = {
                "item_description": extract_val(item.get("item_description")),
                "timeline": extract_val(item.get("timeline")),
                "rate_type": extract_val(item.get("rate_type")),
                "total_price": extract_val(item.get("total_price")),
                "Serial_no": item.get("Serial_no", ""),
                "item_code": item.get("item_code", ""),
                "quantity": item.get("quantity", ""),
                "UOM": item.get("UOM", ""),
                "unit_price": item.get("unit_price", ""),
                "page_no": page_no
            }

            all_rows.append(row)

    return pd.DataFrame(all_rows)

def extract_values_from_dict_file(file_path: str):
    """
    Reads a file containing a Python dict and extracts only the 'value' fields,
    ignoring all 'coordinates', nested dicts, pages, and line items.
    """
    
    # Step 1: Read file and evaluate into Python dict
    with open(file_path, "r") as f:
        file_content = f.read()

    try:
        data_dict = ast.literal_eval(file_content)
    except Exception as e:
        raise ValueError(f"Error parsing dict from file: {e}")

    # Step 2: Recursively collect only 'value' fields
    extracted_values = {}

    def recursive_extract(obj, parent_key=""):
        if isinstance(obj, dict):
            for key, val in obj.items():
                new_key = f"{parent_key}.{key}" if parent_key else key

                if key == "value":  
                    extracted_values[parent_key] = val  # Store using parent field name
                else:
                    recursive_extract(val, new_key)

        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                recursive_extract(item, f"{parent_key}[{idx}]")

    recursive_extract(data_dict)

    return extracted_values

def extract_po_from_file(file_path):
    with open(file_path, "r") as f:
        raw = f.read()

    llm_json = ast.literal_eval(raw)

    # 🔥 FIX: use only the nested actual data
    po_data = llm_json.get("data", {})

    # header df
    header_df = extract_header_df(po_data)
    print(header_df)

    # line items df
    line_items_df = extract_line_items_df(po_data)
    print(line_items_df)

    return header_df, line_items_df





