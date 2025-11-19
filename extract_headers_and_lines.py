"""
This module provides functions for extracting purchase order (PO) header and line item data
from LLM-generated JSON structures. It handles nested dictionaries, extracts values from
structured formats, and converts the extracted data into pandas DataFrames.
"""
import ast
import pandas as pd
def extract_values_only(data, prefix=""):
    """Recursively extracts 'value' fields from a nested dictionary structure.
    This function flattens a potentially nested dictionary where values might be dictionaries
    containing a 'value' key (e.g., from an inference model response). It extracts these 'value'
    fields and constructs a flat dictionary with keys representing the path to the original value.
    If a value is not a dictionary with a 'value' key, it's included as is.
    Args:
        data (dict): The input nested dictionary.
        prefix (str, optional): A prefix to use for constructing flattened keys during recursion.
                                 Defaults to "".
    Returns:
        dict: A flattened dictionary containing only the extracted values.
    """
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
    """Extracts PO header fields from the first available page.
    This function processes LLM-generated JSON data and extracts purchase order header
    information from the first page found. It handles missing fields gracefully by
    returning empty strings for missing values.
    Args:
        llm_json (dict): A dictionary containing page data with keys starting with "page_".
    Returns:
        pd.DataFrame: A DataFrame containing a single row with PO header fields including
                     po_number, po_date, due_date, buyer_info, bill_to, vendor details,
                     shipping details, and total_amount.
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
    """Safely extracts line items from ALL pages.
    This function processes LLM-generated JSON data and extracts purchase order line items
    from all available pages. It handles missing keys, missing value fields, and wrong formats
    gracefully by skipping invalid entries and continuing processing.
    Args:
        llm_json (dict): A dictionary containing page data with keys starting with "page_".
    Returns:
        pd.DataFrame: A DataFrame containing line items with columns for item_description,
                     timeline, rate_type, total_price, Serial_no, item_code, quantity,
                     UOM, unit_price, and page_no.
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
                """Extracts the 'value' field from an object if it's a dictionary, otherwise returns the object.
                This helper function handles the standard LLM output format where values are wrapped
                in dictionaries with a 'value' key.
                Args:
                    obj: The object to extract value from. Can be a dict with 'value' key or any other type.
                Returns:
                    str: The extracted value if obj is a dict with 'value' key, otherwise returns obj or empty string.
                """
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
def _recursive_extract_values(obj, parent_key="", extracted_values=None):
    """Recursively extracts 'value' fields from nested dictionary or list structures.
    This helper function traverses nested dictionaries and lists to find all 'value' fields
    and stores them in the extracted_values dictionary with keys representing their path.
    Args:
        obj: The object to process (dict, list, or other).
        parent_key (str): The key path prefix for the current recursion level.
        extracted_values (dict): Dictionary to store extracted values (modified in place).
    Returns:
        None: Modifies extracted_values dictionary in place.
    """
    if extracted_values is None:
        extracted_values = {}
    if isinstance(obj, dict):
        _extract_from_dict(obj, parent_key, extracted_values)
    elif isinstance(obj, list):
        _extract_from_list(obj, parent_key, extracted_values)
def _extract_from_dict(obj_dict, parent_key, extracted_values):
    """Extracts values from a dictionary object.
    Args:
        obj_dict (dict): Dictionary to process.
        parent_key (str): Parent key path.
        extracted_values (dict): Dictionary to store extracted values.
    """
    for key, val in obj_dict.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if key == "value":
            extracted_values[parent_key] = val
        else:
            _recursive_extract_values(val, new_key, extracted_values)
def _extract_from_list(obj_list, parent_key, extracted_values):
    """Extracts values from a list object.
    Args:
        obj_list (list): List to process.
        parent_key (str): Parent key path.
        extracted_values (dict): Dictionary to store extracted values.
    """
    for idx, item in enumerate(obj_list):
        _recursive_extract_values(item, f"{parent_key}[{idx}]", extracted_values)
def extract_values_from_dict_file(file_path: str):
    """Reads a file containing a Python dict and extracts only the 'value' fields.
    This function reads a file containing a Python dictionary representation (using ast.literal_eval),
    then recursively extracts all 'value' fields from nested structures, ignoring 'coordinates',
    nested dicts, pages, and line items.
    Args:
        file_path (str): The path to the file containing the Python dictionary representation.
    Returns:
        dict: A flattened dictionary containing only the extracted 'value' fields with keys
              representing the path to each value.
    Raises:
        ValueError: If the file cannot be parsed as a valid Python dictionary.
    """
    with open(file_path, "r") as f:
        file_content = f.read()
    try:
        data_dict = ast.literal_eval(file_content)
    except Exception as e:
        raise ValueError(f"Error parsing dict from file: {e}")
    extracted_values = {}
    _recursive_extract_values(data_dict, "", extracted_values)
    return extracted_values
def extract_po_from_file(file_path):
    """Extracts purchase order header and line items from a file containing LLM JSON output.
    This function reads a file containing LLM-generated JSON data, parses it, and extracts
    both the purchase order header information and line items. It expects the data to be
    nested under a 'data' key in the JSON structure.
    Args:
        file_path (str): The path to the file containing the LLM JSON output.
    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: DataFrame with PO header details.
            - pd.DataFrame: DataFrame with PO line items.
    Raises:
        ValueError: If the file cannot be parsed as a valid Python dictionary.
    """
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
