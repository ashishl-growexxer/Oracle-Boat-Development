import pytest
import pandas as pd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from extract_headers_and_lines import extract_values_only, extract_header_df, extract_line_items_df, extract_values_from_dict_file, extract_po_from_file


def test_extract_values_only():
    data = {
        "field1": {"value": "val1", "coordinates": []},
        "field2": {"nested": {"value": "val2"}},
        "field3": "simple_val",
        "field4": [{"value": "list_val1"}, {"value": "list_val2"}]
    }
    expected = {
        "field1": "val1",
        "field2.nested": "val2",
        "field3": "simple_val",
        "field4": [{"value": "list_val1"}, {"value": "list_val2"}]
    }
    assert extract_values_only(data) == expected

def test_extract_header_df_with_data():
    llm_json = {
        "page_1": {
            "priority_fields": {
                "po_number": {"value": "PO-001"},
                "customer_details": {"buyer_info": {"value": "Buyer A"}},
                "order_summary": {"total_amount": {"value": "100.00"}}
            }
        }
    }
    df = extract_header_df(llm_json)
    assert not df.empty
    assert df['po_number'][0] == "PO-001"
    assert df['buyer_info'][0] == "Buyer A"
    assert df['total_amount'][0] == "100.00"

def test_extract_header_df_no_pages():
    llm_json = {}
    df = extract_header_df(llm_json)
    assert df.empty

def test_extract_line_items_df_with_data():
    llm_json = {
        "page_1": {
            "priority_fields": {
                "line_items": [
                    {"item_description": {"value": "Item A"}, "quantity": "1"},
                    {"item_description": {"value": "Item B"}, "quantity": "2"}
                ]
            }
        }
    }
    df = extract_line_items_df(llm_json)
    assert not df.empty
    assert len(df) == 2
    assert df['item_description'][0] == "Item A"
    assert df['quantity'][1] == "2"

def test_extract_line_items_df_no_line_items():
    llm_json = {
        "page_1": {
            "priority_fields": {}
        }
    }
    df = extract_line_items_df(llm_json)
    assert df.empty

    def test_extract_line_items_df_not_a_list():
        """Test that line_items that are not a list are skipped (covers lines 82-84)."""
    llm_json = {
        "page_1": {
            "priority_fields": {
                "line_items": "not a list"  # This should be skipped
            }
        },
        "page_2": {
            "priority_fields": {
                "line_items": [
                    {"item_description": {"value": "Item A"}, "quantity": "1"}
                ]
            }
        }
    }
    df = extract_line_items_df(llm_json)
    # Should only have items from page_2, page_1 should be skipped
    assert not df.empty
    assert len(df) == 1
    assert df['item_description'][0] == "Item A"

def test_extract_values_from_dict_file(tmp_path):
    # Create a dummy file
    file_content = """
{'data': {'page_1': {'priority_fields': {'po_number': {'value': '123', 'coordinates': []}}}}}
"""
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text(file_content)

    extracted = extract_values_from_dict_file(str(dummy_file))
    assert extracted == {'data.page_1.priority_fields.po_number': '123'}

def test_extract_values_from_dict_file_with_list(tmp_path):
    """Test extract_values_from_dict_file with list data (covers line 145)."""
    # Create a file with list data
    file_content = """
{'data': {'items': [{'name': {'value': 'Item1'}}, {'name': {'value': 'Item2'}}]}}
"""
    dummy_file = tmp_path / "dummy_list.txt"
    dummy_file.write_text(file_content)

    extracted = extract_values_from_dict_file(str(dummy_file))
    assert 'data.items[0].name' in extracted
    assert 'data.items[1].name' in extracted
    assert extracted['data.items[0].name'] == 'Item1'
    assert extracted['data.items[1].name'] == 'Item2'

def test_extract_values_from_dict_file_invalid_syntax(tmp_path):
    """Test extract_values_from_dict_file with invalid file content (covers lines 127-128)."""
    # Create a file with invalid Python syntax
    file_content = "This is not a valid Python dict"
    dummy_file = tmp_path / "invalid.txt"
    dummy_file.write_text(file_content)

    with pytest.raises(ValueError) as exc_info:
        extract_values_from_dict_file(str(dummy_file))
    assert "Error parsing dict from file" in str(exc_info.value)

def test_extract_po_from_file(tmp_path):
    # Create a dummy file
    file_content = """
{'data': {
    'page_1': {
        'priority_fields': {
            'po_number': {'value': 'PO-TEST', 'coordinates': []},
            'line_items': [
                {'item_description': {'value': 'Test Item', 'coordinates': []}, 'quantity': '5'}
            ]
        }
    }
}}
"""
    dummy_file = tmp_path / "po_data.txt"
    dummy_file.write_text(file_content)

    header_df, line_items_df = extract_po_from_file(str(dummy_file))

    assert not header_df.empty
    assert header_df['po_number'][0] == "PO-TEST"

    assert not line_items_df.empty
    assert line_items_df['item_description'][0] == "Test Item"
    assert line_items_df['quantity'][0] == "5"
