import pytest
from unittest.mock import patch, mock_open, MagicMock
import os
from datetime import datetime, timezone
import pandas as pd
import oci
import configparser
import oracledb

# Adjust the import path for main if necessary
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import initialize_client, get_pdf_files_from_bucket, upload_file_to_csv_folder, main_logic

# Mock OCI config and client initialization
@pytest.fixture
def mock_oci_config():
    with patch('oci.config.from_file') as mock_from_file, \
         patch('oci.object_storage.ObjectStorageClient') as mock_client:
        mock_from_file.return_value = {'some': 'config'}
        mock_client.return_value = "mock_object_storage_client"
        yield mock_from_file, mock_client

# Mock configparser
@pytest.fixture
def mock_configparser():
    with patch('configparser.ConfigParser') as MockConfigParser:
        mock_config = MockConfigParser.return_value
        mock_config.read.return_value = None
        mock_config.__getitem__.side_effect = lambda key: {
            'DEFAULT': {
                'user': 'test_user',
                'key_file': 'test_key',
                'fingerprint': 'test_fingerprint',
                'tenancy': 'test_tenancy',
                'region': 'test_region'
            },
            'ADW':{
                'config_dir': '/tmp',
                'wallet_loc': '/tmp',
                'wallet_pw': 'test_wallet_pw',
                'dsn': 'test_dsn',
                'USERNAME': 'adw_user',
                'PASSWORD': 'adw_password',
            }
        }[key]
        yield MockConfigParser

# Mock oracledb connection
@pytest.fixture
def mock_oracledb_connection():
    with patch('oracledb.connect') as mock_connect, \
         patch('oracledb.Connection') as MockConnection, \
         patch('oracledb.Cursor') as MockCursor:
        mock_connect.return_value = MockConnection.return_value
        MockConnection.return_value.cursor.return_value = MockCursor.return_value
        yield mock_connect, MockConnection, MockCursor


# Test initialize_client
def test_initialize_client(mock_configparser, mock_oci_config):
    client, bucket_info = initialize_client()
    assert client == "mock_object_storage_client"
    assert bucket_info['namespace'] == "bmb8tbvmgtsy"
    assert bucket_info['bucket_name'] == "BOAT-BUCKET"
    assert bucket_info['region'] == "test_region"


# Test get_pdf_files_from_bucket
@patch('main.initialize_client')
def test_get_pdf_files_from_bucket(mock_init_client):
    # Create mock objects
    mock_client = MagicMock()
    mock_bucket_info = {
        'namespace': 'bmb8tbvmgtsy',
        'bucket_name': 'BOAT-BUCKET',
        'region': 'test_region'
    }
    
    # Set up the return value for initialize_client
    mock_init_client.return_value = (mock_client, mock_bucket_info)
    
    # Create mock response object
    mock_response = MagicMock()
    mock_response.data.objects = [
        type('obj', (object,), {'name': 'pdf/file1.pdf'}),
        type('obj', (object,), {'name': 'pdf/file2.pdf'}),
        type('obj', (object,), {'name': 'pdf/'})
    ]
    mock_client.list_objects.return_value = mock_response

    file_names, file_urls = get_pdf_files_from_bucket()
    assert "file1" in file_names
    assert "file2" in file_names
    assert "https://objectstorage.test_region.oraclecloud.com/n/bmb8tbvmgtsy/b/BOAT-BUCKET/o/pdf/file1.pdf" in file_urls

# Test upload_file_to_csv_folder
@patch('main.initialize_client')
def test_upload_file_to_csv_folder(mock_init_client):
    # Create mock objects
    mock_client = MagicMock()
    mock_bucket_info = {
        'namespace': 'bmb8tbvmgtsy',
        'bucket_name': 'BOAT-BUCKET',
        'region': 'test_region'
    }
    
    # Set up the return value for initialize_client
    mock_init_client.return_value = (mock_client, mock_bucket_info)
    
    mock_client.put_object.return_value = "mock_response"

    with patch('builtins.open', mock_open(read_data=b"file content")) as mock_file_open, \
         patch('os.path.basename', return_value="test.csv"):
        object_name = upload_file_to_csv_folder("test.csv")
        mock_client.put_object.assert_called_once_with(
            namespace_name="bmb8tbvmgtsy",
            bucket_name="BOAT-BUCKET",
            object_name="csv-ps/test.csv",
            put_object_body=b"file content",
            content_type="text/csv"
        )
        assert object_name == "csv-ps/test.csv"

# Test main_logic
@patch('main.bucket')
@patch('main.upload_file_to_csv_folder')
@patch('os.path.exists')
@patch('os.remove')
def test_main_logic(mock_os_remove, mock_os_exists, mock_upload_file, mock_bucket):
    # Mock the return values for bucket
    mock_header_df = pd.DataFrame({
        'po_number': ['PO123'],
        'po_date': ['2023-01-01'],
        'due_date': ['2023-01-31'],
        'buyer_info': ['Buyer A'],
        'bill_to': ['Bill To A'],
        'vendor_id': ['V001'],
        'name': ['Vendor Name'],
        'address': ['Vendor Address'],
        'contact': ['Vendor Contact'],
        'ship_to': ['Ship To A'],
        'ship_from': ['Ship From A'],
        'ship_date': ['2023-01-05'],
        'ship_via': ['DHL'],
        'shipping_instruction': ['Fragile'],
        'total_amount': [100.00],
        'po_doc_name': ['test.pdf'],
        'response_time': ['0 00:00:01.000000']
    })
    mock_lines_df = pd.DataFrame({
        'po_number': ['PO123'],
        'po_doc_name': ['test.pdf'],
        'response_time': ['0 00:00:01.000000'],
        'item_description': ['Item 1'],
        'timeline': ['T1'],
        'rate_type': ['Fixed'],
        'total_price': ['100'],
        'Serial_no': ['S1'],
        'item_code': ['C1'],
        'quantity': ['1'],
        'UOM': ['EA'],
        'unit_price': ['100'],
        'page_no': [0]
    })
    mock_bucket.return_value = (mock_header_df, mock_lines_df)

    # Mock os.path.exists to always return True for file deletion checks
    mock_os_exists.return_value = True

    main_logic("test_file")

    # Assertions for main_logic
    mock_bucket.assert_called_once_with("test_file")
    assert mock_upload_file.call_count == 2
    mock_upload_file.assert_any_call("test_file_lines_.csv")
    mock_upload_file.assert_any_call("test_file_headers_.csv")
    assert mock_os_remove.call_count == 2
    mock_os_remove.assert_any_call("test_file_headers_.csv")
    mock_os_remove.assert_any_call("test_file_lines_.csv")
