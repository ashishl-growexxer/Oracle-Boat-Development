import pytest
from utils.queries import QueryManager
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_query_manager_initialization():
    """Ensure QueryManager initializes and contains all expected SQL attributes."""
    qm = QueryManager()

    assert hasattr(qm, "select_all")
    assert hasattr(qm, "insert_po_header_sql")
    assert hasattr(qm, "insert_po_line_items_sql")
    assert hasattr(qm, "truncate_fa_recon_query")

    assert isinstance(qm.select_all, str)
    assert isinstance(qm.insert_po_header_sql, str)
    assert isinstance(qm.insert_po_line_items_sql, str)


def test_get_insertion_queries_returns_dict():
    """Ensure get_insertion_queries returns the correct dict keys and values."""
    qm = QueryManager()
    queries = qm.get_insertion_queries()

    assert isinstance(queries, dict)
    assert "insert_po_header_sql" in queries
    assert "insert_po_line_items_sql" in queries

    assert queries["insert_po_header_sql"] == qm.insert_po_header_sql
    assert queries["insert_po_line_items_sql"] == qm.insert_po_line_items_sql


def test_insert_header_sql_has_correct_placeholders():
    """Verify that the header insert SQL contains exactly 17 bind variables."""
    qm = QueryManager()
    sql = qm.insert_po_header_sql

    # Count :1, :2, ..., :17
    placeholders = [p for p in sql.split() if p.startswith(":")]
    assert len(placeholders) == 17


def test_insert_line_items_sql_has_correct_placeholders():
    """Verify that line-item insert SQL contains exactly 13 bind variables."""
    qm = QueryManager()
    sql = qm.insert_po_line_items_sql

    placeholders = [p for p in sql.split() if p.startswith(":")]
    assert len(placeholders) == 13


def test_select_all_contains_expected_columns():
    qm = QueryManager()
    sql = qm.select_all.lower()

    assert "select" in sql
    assert "po_name" in sql
    assert "start_time" in sql
    assert "end_time" in sql
    assert "extracted_json" in sql
