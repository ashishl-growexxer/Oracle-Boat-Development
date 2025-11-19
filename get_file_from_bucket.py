"""
This module handles the extraction, processing, and storage of purchase order (PO) data
from PDF files. It includes functionalities for connecting to Oracle Autonomous Data Warehouse (ADW),
performing inference with an OCI Generative AI model, extracting data from model responses,
and inserting processed data into database tables.
"""
import oci
import csv
from inference_code import OCIModel
from pdf2image import convert_from_path
from typing import Optional, List, Dict, Any
from io import BytesIO
from PIL import Image
import io, base64 , json, os
import oracledb
import pandas as pd
from extract_headers_and_lines import extract_po_from_file
from utils.queries import QueryManager
from datetime import datetime, timezone
import time
import numpy as np
from configparser import ConfigParser

# Create configparser instance
config = ConfigParser()
config.read('config.ini')
config_dir = config.get('ADW', 'config_dir')
wallet_loc =  config.get('ADW','wallet_loc')
wallet_pw = config.get('ADW','wallet_pw')
dsn = config.get('ADW','dsn')
adw_username = config.get('ADW','USERNAME')
adw_password = config.get('ADW','PASSWORD')

def get_connection():
    """Establishes and returns a connection to the Oracle Autonomous Data Warehouse (ADW).
    The connection parameters (config directory, wallet location, wallet password, DSN, username, and password)
    are read from the 'ADW' section of the `config.ini` file.
    Returns:
        oracledb.Connection: An active connection object to the ADW database.
    """
    connection = oracledb.connect(
    config_dir=config_dir,
    user=adw_username,
    password=adw_password,
    dsn=dsn,
    wallet_location=wallet_loc,
    wallet_password=wallet_pw)
    return connection


def stringify_dict_fields(df):
    """Converts dictionary-like fields in a DataFrame to JSON strings.
    Iterates through all columns of the input DataFrame and, if a cell contains a dictionary,
    it converts that dictionary into a JSON string. This is useful for preparing data
    for storage in a database where dictionary objects are not directly supported.
    Args:
        df (pd.DataFrame): The input Pandas DataFrame.
    Returns:
        pd.DataFrame: The DataFrame with dictionary fields converted to JSON strings.
    """
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: json.dumps(x) if isinstance(x, dict) else x
        )
    return df

def insert_dfs_to_sql(header_df , line_df):
    """Inserts header and line item DataFrames into SQL database tables.
    This function connects to the Oracle ADW, prepares the data from the provided
    `header_df` and `line_df` DataFrames, and executes bulk insertions into
    `PO_HEADER_DETAILS` and `PO_LINE_ITEMS` tables respectively.
    Args:
        header_df (pd.DataFrame): DataFrame containing purchase order header details.
        line_df (pd.DataFrame): DataFrame containing purchase order line item details.
    """
    print(f"header df {header_df}")
    query_manager = QueryManager()
    insert_queries = query_manager.get_insertion_queries()
    header_insertion_query = insert_queries['insert_po_header_sql']
    line_insertion_query = insert_queries['insert_po_line_items_sql']
    print(header_insertion_query)
    print(line_insertion_query)
    print(line_df.columns)
    print(header_df.columns)
    print(line_df.info())
    print(header_df.info())
    print(f"header df {header_df}")
    header_rows = [
        (
            row['po_number'],
            row['po_date'],
            row['due_date'],
            row['buyer_info'],
            row['bill_to'],
            row['vendor_id'],
            row['name'],
            row['address'],
            row['contact'],
            row['ship_to'],
            row['ship_from'],
            row['ship_date'],
            row['ship_via'],
            row['shipping_instruction'],
            row['total_amount'],
            row['po_doc_name'],
            row['response_time']
        )
        for _, row in header_df.iterrows()
    ]
    # Prepare rows for LINE ITEMS table
    line_rows = [
        tuple(row.values)
        for _, row in line_df.iterrows()
    ]
    # Insert into DB
    conn = get_connection()
    cur = conn.cursor()
    print("Inserting header rows:", len(header_rows))
    cur.executemany(header_insertion_query, header_rows)
    print("Inserting line rows:", len(line_rows))
    cur.executemany(line_insertion_query, line_rows)
    conn.commit()
    cur.close()
    conn.close()
    print("Data inserted successfully!")

def convert_date_columns_in_header_df(df):
    """Converts specified date columns in the header DataFrame to datetime.date objects.
    This function takes a Pandas DataFrame, identifies columns related to dates (`po_date`, `due_date`, `ship_date`),
    and attempts to convert them to `datetime.date` objects. Errors during conversion will result in `NaT` (Not a Time).
    Args:
        df (pd.DataFrame): The input DataFrame containing header information.
    Returns:
        pd.DataFrame: The DataFrame with date columns converted.
    """
    date_cols = ['po_date', 'due_date', 'ship_date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
    return df

def extract_values_only(data, prefix=""):
    """Recursively extracts 'value' fields from a nested dictionary structure.
    This function flattens a potentially nested dictionary where values might be dictionaries
    containing a 'value' key (e.g., from an inference model response). It extracts these 'value'
    fields and constructs a flat dictionary with keys representing the path to the original value.
    If a value is not a dictionary with a 'value' key, it's included as is.
    Args:
        data (dict): The input nested dictionary.
        prefix (str, optional): A prefix to use for constructing flattened keys during recursion. defaults to "".
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

def bucket(filename):
    """Processes a PDF file by downloading it from OCI Object Storage, performing AI inference,
extracting data, and storing it in a database.
    This is the main processing function that orchestrates the following steps:
    1. Downloads a PDF file from a specified OCI Object Storage bucket.
    2. Initializes an OCI Generative AI model.
    3. Converts the PDF into images and performs inference using a predefined prompt.
    4. Saves the model's response to a temporary file.
    5. Deletes the local PDF file.
    6. Extracts header and line item data from the model's response.
    7. Cleans and transforms the extracted data (e.g., converts total_amount to numeric, handles dates).
    8. Enriches the data with response time, document name, and PO number.
    9. Inserts the processed header and line item data into the database.
    Args:
        filename (str): The name of the PDF file (without extension) to process.
    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: The processed header DataFrame.
            - pd.DataFrame: The processed line items DataFrame.
    """
    start_time = datetime.now(timezone.utc)
    filename = filename + '.pdf'
    config = oci.config.from_file("config.ini")
    object_storage_client = oci.object_storage.ObjectStorageClient(config)
    get_object_response = object_storage_client.get_object(
        bucket_name="BOAT-BUCKET",
        namespace_name="bmb8tbvmgtsy",
        object_name = f"pdf/{filename}"
        )
    # Get the data from response
    with open(filename, "wb") as f:
        for chunk in get_object_response.data.raw.stream(1024 * 1024, decode_content=False):
            f.write(chunk)
    model = OCIModel(
        model_id="ocid1.generativeaimodel.oc1.us-chicago-1." \
        "amaaaaaask7dceyayjawvuonfkw2ua4bob4rlnnlhs522pafbglivtwlfzta",
        compartment_id="ocid1.compartment.oc1..aaaaaaaa7wyo7euk2wfekpv36obtfbqgupxeb5yylivifscxseudvwwp2ixa",
        config_profile="DEFAULT"
    )
    # Example 2: Inference with PIL Images (like BedrockModel.infer_with_images())
    print("=" * 60)
    print("Bucket object downloaded and model initiated, Now we infer")
    print("=" * 60)
    images = convert_from_path(filename, dpi=200)
    with open("prompts/new_prompt.txt", "r", encoding="utf-8") as file:
        file_contents = file.read()
    response = model.infer_with_images(
        images=images,
        prompt=file_contents
    )
    print('*'*100)
    print(type(response))
    output_file = "response_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(response))
    if os.path.exists(filename):
        os.remove(filename)
        print(f"{filename} deleted successfully.")
    else:
        print("File not found.")
    header_df  ,lineitems_df = extract_po_from_file(file_path='response_output.txt')
    print(f"header df {header_df['total_amount']}")
    header_df['total_amount'] = pd.to_numeric(header_df['total_amount'], errors='coerce')
    header_df['total_amount'] = header_df['total_amount'].apply(lambda x: None if pd.isna(x) else x)
    print(f"header df {header_df['total_amount']}")
    end_time = datetime.now(timezone.utc)
    print(f"header df {header_df}")
    diff = end_time - start_time
    header_df['response_time'] = diff
    header_df['po_doc_name'] = filename
    po_num = header_df['po_number'][0]
    print(f"header df {header_df}")
    lineitems_df['po_number'] = po_num
    lineitems_df['po_doc_name'] = filename
    lineitems_df['response_time'] = diff
    lineitems_df['page_no'] = 0
    convert_date_columns_in_header_df(header_df)
    print(header_df[header_df['ship_via'].isna()])
    header_df = header_df[['po_number', 'po_date', 'due_date', 'buyer_info', 'bill_to','vendor_id', 'name',
                           'address', 'contact', 'ship_to', 'ship_from', 'ship_date', 'ship_via',
                           'shipping_instruction', 'total_amount','po_doc_name','response_time']]
    lineitems_df = lineitems_df[['po_number','po_doc_name','response_time','item_description', 'timeline',
                                 'rate_type', 'total_price', 'Serial_no', 'item_code', 'quantity', 'UOM',
                                 'unit_price', 'page_no']]
    lineitems_df = stringify_dict_fields(lineitems_df)
    insert_dfs_to_sql(header_df , lineitems_df )
    return header_df, lineitems_df
