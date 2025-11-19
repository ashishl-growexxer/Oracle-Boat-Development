import pytest
from unittest.mock import MagicMock, patch, mock_open
import pandas as pd
from io import BytesIO
from datetime import datetime
import get_file_from_bucket as gfb
import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# ----------------- PURE FUNCTION TESTS ----------------- #

def test_stringify_dict_fields():
    df = pd.DataFrame({
        "col1": [{"a": 1}, {"b": 2}],
        "col2": [10, 20]
    })
    out = gfb.stringify_dict_fields(df.copy())
    assert out["col1"][0] == '{"a": 1}'
    assert out["col2"][0] == 10


def test_convert_date_columns_in_header_df():
    df = pd.DataFrame({
        "po_date": ["2020-01-01", "2020/05/03"],
        "due_date": ["2020/05/03", "2020/05/03"],
        "ship_date": ["2020/05/03", "2024-12-12"]
    })

    out = gfb.convert_date_columns_in_header_df(df.copy())

    assert isinstance(out["po_date"][0], datetime.date)
    assert isinstance(out["po_date"][1], datetime.date)


def test_extract_values_only_nested_structures():
    data = {
        "a": {"value": 1},
        "b": {"nested": {"value": 10}},
        "c": 99
    }

    out = gfb.extract_values_only(data)

    assert out == {"a": 1, "b.nested": 10, "c": 99}



# ---------------- MOCK get_connection ---------------- #

def test_get_connection():
    with patch("get_file_from_bucket.oracledb.connect") as mock_conn:
        gfb.get_connection()
        mock_conn.assert_called_once()



# ---------------- DB INSERTION ---------------- #

@patch("get_file_from_bucket.get_connection")
@patch("get_file_from_bucket.QueryManager")
def test_insert_dfs_to_sql(mock_qm, mock_conn):
    # Mock QueryManager
    mock_qm.return_value.get_insertion_queries.return_value = {
        "insert_po_header_sql": "INSERT HEADER",
        "insert_po_line_items_sql": "INSERT LINE"
    }

    # Mock connection + cursor
    mock_cursor = MagicMock()
    mock_conn.return_value.cursor.return_value = mock_cursor

    header_df = pd.DataFrame([{
        "po_number": "1", "po_date": None, "due_date": None,
        "buyer_info": "x", "bill_to": "y", "vendor_id": "v",
        "name": "n", "address": "a", "contact": "c",
        "ship_to": "s", "ship_from": "f",
        "ship_date": None, "ship_via": None,
        "shipping_instruction": "", "total_amount": 100,
        "po_doc_name": "doc", "response_time": "t"
    }])

    line_df = pd.DataFrame([{
        "item": "AAA", "qty": 10
    }])

    gfb.insert_dfs_to_sql(header_df, line_df)

    # Ensure SQL executed
    assert mock_cursor.executemany.call_count == 2
    mock_conn.return_value.commit.assert_called_once()



# ---------------- FULL BUCKET FLOW ---------------- #

from unittest.mock import mock_open, patch
import builtins

real_open = builtins.open

def selective_open(file, mode="r", *args, **kwargs):
    if file == "sample_file":
        return mock_open(read_data=b"PDFDATA")()
    return real_open(file, mode, *args, **kwargs)


@patch("get_file_from_bucket.insert_dfs_to_sql")
@patch("get_file_from_bucket.stringify_dict_fields")
@patch("get_file_from_bucket.convert_date_columns_in_header_df")
@patch("get_file_from_bucket.extract_po_from_file")
@patch("get_file_from_bucket.OCIModel")
@patch("get_file_from_bucket.convert_from_path")
@patch("get_file_from_bucket.oci.object_storage.ObjectStorageClient")
@patch("builtins.open", side_effect=selective_open)
@patch("os.remove")
def test_bucket_full_flow(
    mock_remove,
    mock_file,
    mock_oci_client,
    mock_convert_from_path,
    mock_oci_model,
    mock_extract_po,
    mock_convert_dates,
    mock_stringify,
    mock_insert
):

    # --- Mock object storage get_object streaming ---
    mock_stream = MagicMock()
    mock_stream.raw.stream.return_value = [b"PDFDATA"]

    mock_obj = MagicMock()
    mock_obj.data = mock_stream
    mock_oci_client.return_value.get_object.return_value = mock_obj

    # --- Mock PDF to images ---
    mock_convert_from_path.return_value = ["IMG1", "IMG2"]

    # --- Mock model inference ---
    mock_model_instance = MagicMock()
    mock_model_instance.infer_with_images.return_value = {"result": "ok"}
    mock_oci_model.return_value = mock_model_instance

    # --- Mock extracted PO data ---
    header_df = pd.DataFrame([{
        "po_number": "123",
        "total_amount": "9999",
        "ship_via": None,

        # required fields by your bucket() function:
        "po_date": "2024-01-01",
        "due_date": "2024-01-05",
        "buyer_info": {},
        "bill_to": {},
        "vendor_id": "V1",
        "name": "Vendor ABC",
        "address": "Somewhere",
        "contact": "123",
        "ship_to": {},
        "ship_from": {},
        "ship_date": "2024-01-02",
        "shipping_instruction": "none"
    }])

    line_df = pd.DataFrame([{
        "item_description": "X",
        "timeline": "",
        "rate_type": "",
        "total_price": "10",
        "Serial_no": 1,
        "item_code": "IT",
        "quantity": 1,
        "UOM": "EA",
        "unit_price": "10"
    }])

    mock_extract_po.return_value = (header_df, line_df)
    mock_convert_dates.side_effect = lambda df: df
    mock_stringify.side_effect = lambda df: df

    # Execute bucket
    out_header, out_line = gfb.bucket("sample_file")

    # Validate output
    assert isinstance(out_header, pd.DataFrame)
    assert isinstance(out_line, pd.DataFrame)

    # Ensure major steps executed
    mock_oci_client.return_value.get_object.assert_called_once()
    mock_convert_from_path.assert_called_once()
    mock_oci_model.return_value.infer_with_images.assert_called_once()
    mock_extract_po.assert_called_once()
    mock_insert.assert_called_once()
    mock_remove.assert_called_once()




@patch("get_file_from_bucket.oracledb.connect")
def test_get_connection(mock_connect):
    # Arrange: create a fake connection object
    fake_conn = MagicMock()
    mock_connect.return_value = fake_conn

    # Act: call the function
    conn = gfb.get_connection()

    # Assert: the returned value is the mocked connection
    assert conn is fake_conn

    # Ensure connect() was called exactly once with required params
    mock_connect.assert_called_once_with(
        config_dir=gfb.config_dir,
        user=gfb.adw_username,
        password=gfb.adw_password,
        dsn=gfb.dsn,
        wallet_location=gfb.wallet_loc,
        wallet_password=gfb.wallet_pw
    )
