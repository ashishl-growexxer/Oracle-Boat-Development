"""
This module defines the `QueryManager` class, which encapsulates SQL queries
for interacting with purchase order (PO) related tables in a database.
"""

class QueryManager(object):
    """Manages SQL queries for purchase order (PO) header and line item insertions, and other database operations."""
    def __init__(self):
        """Initializes the QueryManager with predefined SQL queries."""
        self.select_all = """
            SELECT PO_NAME, START_TIME, END_TIME, EXTRACTED_JSON FROM j_purchaseorder
        """

        self.insert_po_header_sql = """
            INSERT INTO PO_HEADER_DETAILS (
                po_number,
                po_date,
                due_date,
                buyer_info,
                bill_to,
                vendor_id,
                name,
                address,
                contact,
                ship_to,
                ship_from,
                ship_date,
                ship_via,
                shipping_instruction,
                total_amount,
                po_doc_name,
                response_time
            ) VALUES (
                :1, :2, :3, :4, :5, :6, :7, :8, :9,
                :10, :11, :12, :13, :14, :15, :16, :17
            )
        """

        self.insert_po_line_items_sql = """
            INSERT INTO PO_LINE_ITEMS (
                po_number,
                po_doc_name,
                response_time,
                item_description,
                timeline,
                rate_type,
                total_price,
                item_serial_no,
                item_code,
                quantity,
                uom,
                unit_price,
                page_no
            ) VALUES (
                :1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13
            )
        """


        self.truncate_fa_recon_query = """
        """

    def get_insertion_queries(self):
        """Returns a dictionary containing the SQL queries for inserting PO header and line items.

        Returns:
            dict: A dictionary with keys 'insert_po_header_sql' and 'insert_po_line_items_sql'
                  mapping to their respective SQL query strings.
        """
        return {
            "insert_po_header_sql":self.insert_po_header_sql,
            "insert_po_line_items_sql":self.insert_po_line_items_sql
        }





# Header_ fields
# CREATE TABLE PO_HEADER_DETAILS (
#     serial_no              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
#     po_number              VARCHAR2(100),
#     po_date                DATE,
#     due_date               DATE,
#     buyer_info             VARCHAR2(4000),
#     bill_to                VARCHAR2(4000),
#     vendor_id              VARCHAR2(200),
#     name                   VARCHAR2(4000),
#     address                VARCHAR2(4000),
#     contact                VARCHAR2(4000),
#     ship_to                VARCHAR2(4000),
#     ship_from              VARCHAR2(4000),
#     ship_date              DATE,
#     ship_via               VARCHAR2(4000),
#     shipping_instruction   VARCHAR2(4000),
#     total_amount           NUMBER,
#     response_time          INTERVAL DAY(2) TO SECOND(6),
#     po_doc_name            VARCHAR2(500)
# );


# Line items
# CREATE TABLE PO_LINE_ITEMS (
#     serial_no          NUMBER GENERATED ALWAYS AS IDENTITY,   -- auto increment, but NOT a PK
#     po_number          VARCHAR2(100),         -- optional link to header
#     po_doc_name        VARCHAR2(500),
#     response_time      INTERVAL DAY(2) TO SECOND(6),
#     item_description   VARCHAR2(4000),
#     timeline           VARCHAR2(1000),
#     rate_type          VARCHAR2(500),
#     total_price        VARCHAR2(200),
#     item_serial_no     VARCHAR2(200),         -- JSON Serial_no
#     item_code          VARCHAR2(200),
#     quantity           VARCHAR2(100),
#     uom                VARCHAR2(100),
#     unit_price         VARCHAR2(200),
#     page_no            VARCHAR2(50)
# );
