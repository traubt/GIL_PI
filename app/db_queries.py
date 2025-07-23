import pymysql
import json
from flask import session
import pandas as pd



# Database connection details
db_config = {
    'host': '172.234.160.57',
    'user': 'dor_pi',
    'password': 'T0m3r!970',
    'database': 'dor_pi'
}

def get_db_connection():
    return pymysql.connect(**db_config)

def get_top_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT item_name, SUM(net_amt) AS total_amount
    FROM toc_ls_sales_item
    WHERE time_of_sale >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
    GROUP BY item_name
    ORDER BY total_amount DESC
    LIMIT 5;
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def get_sales_summary():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to get the sales summary
    cursor.execute("SELECT * FROM toc_sales_summary")
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_sales_data_for_lineChart():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    # Query to get the sales data
    query = """
    SELECT ts.time_of_sale, SUM(tsi.net_amt)
    FROM toc_ls_sales ts
    JOIN toc_ls_sales_item tsi ON ts.sales_id = tsi.sales_id
    WHERE ts.store_name = 'TOC - Sandton City'
    AND ts.time_of_sale > '2024-11-08'
    GROUP BY ts.time_of_sale
    ORDER BY ts.time_of_sale;
    """
    cursor.execute(query)
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    # Format the result as a list of dictionaries
    data = [{"time_of_sale": row[0], "total_sales": row[1]} for row in result]
    return data

# db_queries.py
def get_recent_sales(shop_name, from_date, to_date):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = '''              
            SELECT 
                CONCAT(m.first_name, ' ', m.last_name) AS customer,
                m.email as email,
                ROUND(SUM(i.net_amt)) AS total_spent,
                COUNT(DISTINCT s.sales_id) AS total_purchases,
                MAX(s.time_of_sale) AS last_purchase_date,
                
                -- Most Frequent Store: find the store with the maximum visits
                (SELECT ts.blName
                 FROM toc_ls_sales s2
                 JOIN toc_shops ts ON s2.store_code = ts.store
                 WHERE s2.sales_id = s.sales_id
                 GROUP BY ts.blName
                 ORDER BY COUNT(ts.blName) DESC
                 LIMIT 1) AS Most_Frequent_Store,
            
                -- Count of unique Store Visits: using blName
                COUNT(DISTINCT ts.blName) AS Count_Store_Visits
            
            FROM 
                toc_ls_sales s
            JOIN 
                toc_ls_sales_item i ON s.sales_id = i.sales_id
            JOIN 
                toc_ls_payments p ON s.sales_id = p.sales_id
            JOIN 
                toc_canna_member m ON p.email = m.email 
            JOIN 
                toc_shops ts ON s.store_code = ts.store  -- Join toc_shops to get blName
                            WHERE
                                s.time_of_sale >= %s
                                AND s.time_of_sale < %s           
            GROUP BY 
                m.email, m.first_name, m.last_name
            ORDER BY 
                total_spent DESC
            LIMIT 30               
                ;
        '''
        cursor.execute(query, (from_date, to_date))

    elif shop_name == "Online":
        query = '''
            SELECT                 
                wo.customer_name,
                wo.customer_email,
                ROUND(SUM(wi.total_amount) / 1.15, 2) AS total_spent_excl_vat, 
                COUNT(DISTINCT wo.order_id) AS total_orders,
                MAX(wo.order_date) AS last_order_date
            FROM 
                toc_wc_sales_order wo
            JOIN 
                toc_wc_sales_items wi 
            ON 
                wo.order_id = wi.order_id
            WHERE
                    wo.order_date >= %s
                    and wo.order_date < %s
                    and wo.status not in ('wc-cancelled','wc-pending')
            GROUP BY 
                wo.customer_name, wo.customer_email
            ORDER BY 
                total_spent_excl_vat DESC
            LIMIT 30;
        '''
        cursor.execute(query, (from_date,to_date))  # No placeholders, so no additional parameters

    else:
        query = '''
                SELECT 
                    CONCAT(m.first_name, ' ', m.last_name) AS customer,
                    m.email as email,
                    ROUND(SUM(i.net_amt)) AS total_spent,
                    COUNT(DISTINCT s.sales_id) AS total_purchases,
                    MAX(s.time_of_sale) AS last_purchase_date
                FROM 
                    toc_ls_sales s
                JOIN 
                    toc_ls_sales_item i ON s.sales_id = i.sales_id
                JOIN 
                    toc_ls_payments p ON s.sales_id = p.sales_id
                JOIN 
                    toc_canna_member m ON p.email = m.email 
                WHERE 
                    s.store_name = %s
                    and
                    s.time_of_sale >= %s
                    AND s.time_of_sale < %s   
                GROUP BY 
                    m.email, m.first_name, m.last_name
                ORDER BY 
                    total_spent DESC
                LIMIT 30;
        '''
        cursor.execute(query, (shop_name,from_date,to_date))  # Only this query uses placeholders

    # Fetch all rows from the query result
    rows = cursor.fetchall()

    # Get column names from the cursor description
    column_names = [desc[0] for desc in cursor.description]

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows




# db_queries.py
def get_product_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
            SELECT product_name, SUM(total_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product
            WHERE total_sales_{timeframe} IS NOT NULL 
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 5;
        '''
        cursor.execute(query)
    else:
        query = f'''
            SELECT product_name, SUM(total_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product
            WHERE total_sales_{timeframe} IS NOT NULL AND shop_name = %s
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 5;
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_specials_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
            SELECT product_name, SUM(count_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product ts
            join toc_product p ON p.item_name = ts.product_name
            WHERE count_sales_{timeframe} IS NOT NULL AND p.acct_group = 'Specials'
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 10;
        '''
        cursor.execute(query)
    else:
        query = f'''
            SELECT product_name, SUM(count_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product ts
            join toc_product p ON p.item_name = ts.product_name
            WHERE count_sales_{timeframe} IS NOT NULL AND p.acct_group = 'Specials' and ts.shop_name = %s
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 10;
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_recent_product_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
                SELECT 
                    p.product_name, 
                    SUM(p.count_sales_{timeframe}) AS total_count, 
                    SUM(p.total_sales_{timeframe}) AS total_sales, 
                    prod.cost_price * SUM(p.count_sales_{timeframe}) AS total_cost, 
                    (CASE 
                        WHEN SUM(p.total_sales_{timeframe}) IS NOT NULL AND prod.cost_price IS NOT NULL 
                        THEN round((SUM(p.total_sales_{timeframe}) - (SUM(p.count_sales_{timeframe}) * prod.cost_price)) / SUM(p.total_sales_{timeframe}) * 100 )
                        ELSE NULL 
                    END) AS gross_profit_percentage
                FROM 
                    toc_sales_summary_product p
                JOIN 
                    toc_product prod 
                ON 
                    p.product_name = prod.item_name
                WHERE 
                    p.total_sales_{timeframe} IS NOT NULL
                    and prod.acct_group <> 'Specials'
                GROUP BY 
                    p.product_name, prod.cost_price
                ORDER BY 
                    total_sales DESC;
        
        '''
        cursor.execute(query)
    else:
        query = f'''       
                SELECT 
                    p.product_name, 
                    SUM(p.count_sales_{timeframe}) AS total_count, 
                    SUM(p.total_sales_{timeframe}) AS total_sales, 
                    prod.cost_price * SUM(p.count_sales_{timeframe}) AS total_cost,
                    (CASE 
                        WHEN SUM(p.total_sales_{timeframe}) IS NOT NULL AND prod.cost_price IS NOT NULL 
                        THEN round((SUM(p.total_sales_{timeframe}) - (SUM(p.count_sales_{timeframe}) * prod.cost_price)) / SUM(p.total_sales_{timeframe}) * 100 )
                        ELSE NULL 
                    END) AS gross_profit_percentage
                FROM 
                    toc_sales_summary_product p
                JOIN 
                    toc_product prod 
                ON 
                    p.product_name = prod.item_name
                WHERE 
                    p.total_sales_{timeframe} IS NOT NULL and shop_name = %s
                    and prod.acct_group <> 'Specials'
                GROUP BY 
                    p.product_name, prod.cost_price
                ORDER BY 
                    total_sales DESC;           
        '''
        cursor.execute(query, (shop_name,))

    rows = cursor.fetchall()

    # Get column names from the cursor description
    column_names = [desc[0] for desc in cursor.description]

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows

# db_queries.py
# db_queries.py
def get_hourly_sales(shop_name, timeframe):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"shop_name: {shop_name}")
    # print(f"time_frame: {timeframe}")

    if shop_name == "Head Office":
        if timeframe == "hourly":
            query = '''                             
                SELECT 
                    'Head Office' as store_name,
                    DATE_FORMAT(s.time_of_sale, '%Y-%m-%d %H:00') AS sale_hour, 
                    ROUND(SUM(net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item i
				JOIN
					toc_ls_sales s 
				ON i.sales_id = s.sales_id
                GROUP BY 
                    sale_hour
                ORDER BY 
                    sale_hour DESC
                LIMIT 200;
            '''
            cursor.execute(query)
        elif timeframe == "daily":
            query = '''
                SELECT 
                    'Head Office' AS store_name,
                    DATE_FORMAT(i.time_of_sale, '%Y-%m-%d') AS sale_date,
                    ROUND(SUM(net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item i
                JOIN
                    toc_ls_sales s on i.sales_id = s.sales_id
                GROUP BY 
                    DATE_FORMAT(i.time_of_sale, '%Y-%m-%d')
                ORDER BY 
                    sale_date
                limit 200;
            '''
            cursor.execute(query)
    elif shop_name == "Online":
        if timeframe == "hourly":
            query = '''                             
                SELECT 
                    'Online' AS store_name,
                    DATE_FORMAT(o.creation_date, '%Y-%m-%d %H:00') AS sale_hour, 
                    ROUND(SUM(o.total_amount / 1.15), 2) AS total_amount -- Removing 15% VAT
                FROM 
                    toc_wc_sales_order o
                GROUP BY 
                    sale_hour
                ORDER BY 
                    sale_hour DESC
                LIMIT 200;
            '''
            cursor.execute(query)
        elif timeframe == "daily":
            query = '''
                SELECT 
                    'Online' AS store_name,
                    DATE_FORMAT(o.creation_date, '%Y-%m-%d') AS sale_hour, 
                    ROUND(SUM(o.total_amount / 1.15), 2) AS total_amount -- Removing 15% VAT
                FROM 
                    toc_wc_sales_order o
                GROUP BY 
                    sale_hour
                ORDER BY 
                    sale_hour DESC
                LIMIT 200;
            '''
            cursor.execute(query)
    else:
        if timeframe == "hourly":
            query = '''
                SELECT 
                    ts.store_name,
                    DATE_FORMAT(tlsi.time_of_sale, '%%Y-%%m-%%d %%H:00') AS sale_hour,
                    ROUND(SUM(tlsi.net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item tlsi
                JOIN 
                    toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
                WHERE
                    ts.store_name = %s
                GROUP BY 
                    ts.store_name, sale_hour
                ORDER BY 
                    ts.store_name, sale_hour
                limit 200;
            '''
            cursor.execute(query, (shop_name,))
        elif timeframe == "daily":
            query = '''
                SELECT 
                    ts.store_name,
                    DATE_FORMAT(tlsi.time_of_sale, '%%Y-%%m-%%d') AS sale_date,
                    ROUND(SUM(tlsi.net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item tlsi
                JOIN 
                    toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
                WHERE 
                    ts.store_name = %s
                GROUP BY 
                    ts.store_name, sale_date
                ORDER BY 
                    ts.store_name, sale_date limit 200;
            
            '''
            cursor.execute(query, (shop_name,))

    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result


def get_stock_order_template():
    shop_data = json.loads(session.get('shop'))
    shop = shop_data["customer"]

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to get the sales summary
    query = '''
        SELECT 
            toc_product.item_sku AS sku,
            toc_product.item_name AS product_name,
            0 AS stock_count,
            0 AS last_stock_qty,
            0 AS calc_stock_qty,
            0 AS variance,
            'NA' AS variance_rsn,
            0 AS stock_recount,
            0 AS rejects_qty,
            'NA' AS comments
        FROM 
            toc_shops
        CROSS JOIN 
            toc_product
        WHERE 
            toc_product.acct_group <> 'Specials'
            AND toc_shops.customer = %s;
    '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def distribute_product_to_shops(sku):
    # Connect to the database
    conn = get_db_connection()  # Assuming this function is defined elsewhere to get the connection
    cursor = conn.cursor()

    # Query to insert the product into the toc_stock table for all shops
    query = '''
        INSERT INTO toc_stock (
            shop_id, sku, stock_qty_date, product_name, shop_name, final_stock_qty,
            stock_count, count_by, last_stock_qty, calc_stock_qty, variance, variance_rsn,
             rejects_qty, replenish_id, comments, pastel_date
        )
        SELECT 
            toc_shops.customer AS shop_id,
            toc_product.item_sku AS sku,
            '2000-01-01' AS stock_qty_date,
            toc_product.item_name AS product_name,
            toc_shops.blName AS shop_name,
            0 AS final_stock_qty,
            0 AS stock_count,
            'NA' AS count_by,
            0 AS last_stock_qty,
            0 AS calc_stock_qty,
            0 AS variance,
            'NA' AS variance_rsn,
            0 AS rejects_qty,
            'NA' AS replenish_id,  -- Replacing transfer_id with replenish_id
            'NA' AS comments,
            '2020-02-02' as pastel_date           
        FROM 
            toc_shops
        CROSS JOIN 
            toc_product
        WHERE 
            toc_product.item_sku = %s;
    '''

    try:
        # Execute the query with the sku parameter
        cursor.execute(query, (sku,))

        # Commit the transaction to save the changes to the database
        conn.commit()

    except Exception  as err:
        # Rollback in case of error
        conn.rollback()
        print(f"Error occurred: {err}")
        return {"status": "error", "message": str(err)}

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

    # If successful, return a success message
    return {"status": "success", "message": f"Product {sku} distributed to shops successfully."}


def get_stock_order_form():
    shop_data = json.loads(session.get('shop'))
    shop = shop_data["customer"]

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
        SELECT 
            p.item_sku AS sku,
            p.item_name AS product_name,
            0 AS stock_count,
            0 AS last_stock_qty,
            0 AS calc_stock_qty,
            0 AS variance,
            'NA' AS variance_rsn,
            0 AS stock_recount,
            COALESCE(o.order_qty, 0) AS order_qty,
            'NA' AS comments
        FROM 
            toc_shops s
        CROSS JOIN 
            toc_product p
        LEFT JOIN 
            toc_stock_order o
        ON 
            s.customer = o.shop_id 
            AND p.item_sku = o.sku
            AND o.order_status = 'New'
        WHERE 
            p.acct_group <> 'Specials'
            AND s.customer = %s
		ORDER BY order_qty desc, product_name asc;
    '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_replenish_order_form(order_id, shop, threshold, replenish):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
               WITH sales_data AS (
               SELECT 
                d.item_sku,
                d.item_name,
                b.store_customer,
                c.blName AS shop_name,
                COUNT(CASE WHEN a.time_of_sale > CURDATE() - INTERVAL %s DAY THEN a.sales_id END) AS threshold_sold_qty,
                COUNT(CASE WHEN a.time_of_sale > CURDATE() - INTERVAL %s DAY THEN a.sales_id END) AS replenish_qty,
             --    COUNT(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.sales_id END) AS sales_since_stock_read
                 COALESCE(SUM(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.quantity END), 0) AS sales_since_stock_read
            FROM 
                toc_product d
             JOIN 
                toc_ls_sales_item a
                ON d.item_sku = a.item_sku
             JOIN 
                toc_ls_sales b 
                ON a.sales_id = b.sales_id
             JOIN 
                toc_shops c
                ON b.store_customer = c.customer
             JOIN
                toc_stock st
                ON d.item_sku = st.sku AND b.store_customer = st.shop_id
            WHERE 
                d.acct_group <> 'Specials'
                AND c.blName = %s
                AND d.item_sku <> '9568'  -- Refund item
            GROUP BY 
                d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date
            UNION ALL
            SELECT 
                st.sku AS item_sku,
                d.item_name,
                st.shop_id AS store_customer,
                c.blName AS shop_name,
                0 AS threshold_sold_qty,
                0 AS replenish_qty,
                0 AS sales_since_stock_read
            FROM 
                toc_stock st
             JOIN 
                toc_product d 
                ON st.sku = d.item_sku 
                AND d.acct_group <> 'Specials' 
                AND d.item_sku <> '9568'  -- Exclude refund item
             JOIN 
                toc_shops c 
                ON st.shop_id = c.customer
            WHERE 
                c.blName = %s
                AND NOT EXISTS (
                    SELECT 1
                    FROM toc_ls_sales_item a
                    JOIN toc_ls_sales b ON a.sales_id = b.sales_id
                    WHERE a.item_sku = st.sku 
                    AND b.store_customer = st.shop_id
                )
            )
            SELECT 
                s.item_sku,
                s.item_name,
                s.store_customer,
                s.shop_name,
                s.threshold_sold_qty,
                s.replenish_qty,
                s.sales_since_stock_read,
                st.final_stock_qty AS last_stock_update,
                st.stock_qty_date AS last_stock_update_date,
                st.final_stock_qty - s.sales_since_stock_read + st.stock_transfer AS current_stock_qty,
                CASE 
                    WHEN %s IS NOT NULL THEN (
                        SELECT replenish_qty FROM toc_replenish_order 
                        WHERE order_id = %s AND sku = s.item_sku
                    )     
                    WHEN st.final_stock_qty - s.sales_since_stock_read + st.stock_transfer > s.threshold_sold_qty THEN 0              
                    ELSE s.replenish_qty
                END AS replenish_order
            FROM 
                sales_data s
            LEFT JOIN 
                toc_stock st
            ON 
                s.item_sku = st.sku AND s.store_customer = st.shop_id
            ORDER BY s.sales_since_stock_read DESC;
    '''

    # Execute the query with the parameters
    cursor.execute(query, (threshold, replenish, shop, shop, order_id, order_id))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result


# def get_stock_count_per_shop(shop):
#
#     # Connect to the database
#     conn = get_db_connection()
#     cursor = conn.cursor()
#
#     # Query to retrieve the stock order form
#     query = '''
# WITH sales_data AS (
#     SELECT
#         d.item_sku,
#         d.item_name,
#         b.store_customer,
#         c.blName AS shop_name,
#         st.stock_qty_date,
#         -- COUNT(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.sales_id END) AS sales_since_stock_read
#         SUM(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.quantity END) AS sales_since_stock_read
#     FROM
#         toc_product d
#     LEFT JOIN
#         toc_ls_sales_item a
#         ON d.item_sku = a.item_sku
#     LEFT JOIN
#         toc_ls_sales b
#         ON a.sales_id = b.sales_id
#     LEFT JOIN
#         toc_shops c
#         ON b.store_customer = c.customer
#     LEFT JOIN
#         toc_stock st
#         ON d.item_sku = st.sku AND b.store_customer = st.shop_id
#     WHERE
#         d.acct_group <> 'Specials'
#         AND c.blName = %s -- Ensures we only get sales related to this shop
#     GROUP BY
#         d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date
# )
# SELECT DISTINCT
#     st.sku AS item_sku,
#     st.product_name AS item_name,
#     st.shop_id AS store_customer,
#     st.shop_name,
#     st.stock_count AS last_stock_count, -- Last stock count (final_stock_qty from toc_stock)
#     st.stock_qty_date AS last_stock_count_date, -- Last stock count date (stock_qty_date from toc_stock)
#     COALESCE(s.sales_since_stock_read, 0) AS sold_quantity, -- Sold quantity (sales_since_stock_read from sales_data, or 0 if no sales data)
#     st.final_stock_qty - COALESCE(s.sales_since_stock_read, 0) AS current_quantity, -- Current quantity (last stock count - sold quantity)
#     st.stock_transfer AS received_stock
# FROM
#     toc_stock st
# LEFT JOIN
#     sales_data s
# ON
#     st.sku = s.item_sku AND st.shop_id = s.store_customer
# WHERE
#     st.shop_name = %s -- Filter to include only entries for the specified shop
# ORDER BY
#     COALESCE(s.sales_since_stock_read, 0) DESC;
#     '''
#
#     # Execute the query with the parameter
#     cursor.execute(query, (shop,shop))
#     result = cursor.fetchall()
#
#     cursor.close()
#     conn.close()
#
#     return result

def get_stock_count_per_shop(shop):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
WITH sales_data AS (
    SELECT 
        d.item_sku,
        d.item_name,
        b.store_customer,
        c.blName AS shop_name,
        st.stock_qty_date,
        SUM(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.quantity END) AS sales_since_stock_read
    FROM 
        toc_product d
    LEFT JOIN toc_ls_sales_item a ON d.item_sku = a.item_sku
    LEFT JOIN toc_ls_sales b ON a.sales_id = b.sales_id
    LEFT JOIN toc_shops c ON b.store_customer = c.customer
    LEFT JOIN toc_stock st ON d.item_sku = st.sku AND b.store_customer = st.shop_id
    WHERE 
        d.acct_group <> 'Specials'
        AND c.blName = %s
    GROUP BY 
        d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date
),
damaged_data AS (
    SELECT 
        d.sku,
        d.shop_id,
        SUM(d.rcv_damaged) AS total_damaged
    FROM 
        toc_damaged d
    INNER JOIN toc_stock st
        ON d.sku = st.sku AND d.shop_id = st.shop_name
    WHERE 
        d.order_open_date > st.stock_qty_date
        AND d.shop_id = %s
    GROUP BY 
        d.sku, d.shop_id
)
SELECT DISTINCT
    st.sku AS item_sku,
    st.product_name AS item_name,
    st.shop_id AS store_customer,
    st.shop_name,
    st.stock_count AS last_stock_count,
    st.stock_qty_date AS last_stock_count_date,
    COALESCE(s.sales_since_stock_read, 0) AS sold_quantity,
    st.final_stock_qty - COALESCE(s.sales_since_stock_read, 0) AS current_quantity,
    st.stock_transfer - COALESCE(dd.total_damaged, 0) AS received_stock
FROM 
    toc_stock st
LEFT JOIN sales_data s
    ON st.sku = s.item_sku AND st.shop_id = s.store_customer
LEFT JOIN damaged_data dd
    ON st.sku = dd.sku AND st.shop_name = dd.shop_id
WHERE 
    st.shop_name = %s
ORDER BY 
    COALESCE(s.sales_since_stock_read, 0) DESC;
    '''

    # Execute the query with the shop name as parameter (used 3 times)
    cursor.execute(query, (shop, shop, shop))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result



def get_receive_stock_order(shop,order_id):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
                select * from toc_replenish_order where shop_id = %s and order_id = %s
            '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,order_id))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_sales_by_shop_last_three_months(user_shop):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    if user_shop == 'Head Office':
        query = '''
                SELECT 
                    ts.store_name,
                    DATE_FORMAT(tlsi.time_of_sale, '%Y-%m') AS sale_month,
                    ROUND(SUM(tlsi.net_amt)) AS total_sales
                FROM 
                    toc_ls_sales_item tlsi
                JOIN 
                    toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
                JOIN toc_shops s on ts.store_customer = s.customer
                WHERE 
                    tlsi.time_of_sale >= DATE_FORMAT(CURDATE() - INTERVAL 2 MONTH, '%Y-%m-01')
                    AND s.actv_ind = 1
                GROUP BY 
                    ts.store_name, sale_month
                UNION ALL
                SELECT 
                    'Online' AS store_name,
                    DATE_FORMAT(order_date, '%Y-%m') AS sale_month, -- Grouping by creation_date
                    ROUND(SUM(total_amount / 1.15)) AS total_sales -- Removing 15% VAT
                FROM 
                    toc_wc_sales_order
                WHERE 
                    order_date >= DATE_FORMAT(CURDATE() - INTERVAL 2 MONTH, '%Y-%m-01')
                    AND status NOT IN ('wc-cancelled','wc-pending')
                GROUP BY 
                    store_name, sale_month;
                '''
        # Execute the query
        cursor.execute(query)

    else:
        query = '''
            SELECT 
                ts.store_name,
                DATE_FORMAT(tlsi.time_of_sale, '%%Y-%%m') AS sale_month,
                ROUND(SUM(tlsi.net_amt)) AS total_sales
            FROM 
                toc_ls_sales_item tlsi
            JOIN 
                toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
            JOIN toc_shops s ON ts.store_customer = s.customer
            WHERE 
                tlsi.time_of_sale >= DATE_FORMAT(CURDATE() - INTERVAL 2 MONTH, '%%Y-%%m-01')
                AND s.actv_ind = 1
                AND TRIM(LOWER(ts.store_name)) = TRIM(LOWER(%s))
            GROUP BY 
                ts.store_name, sale_month
            ORDER BY 
                sale_month asc;
                '''
        # Execute the query
        cursor.execute(query, (user_shop,))

    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts



def get_top_agents (shop_name, timeframe):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"shop_name: {shop_name}")
    # print(f"time_frame: {timeframe}")

    if shop_name == "Head Office":
        if timeframe == "daily":
            query = '''                             
            SELECT 
                staff_name,                
                s.store_name,
                ROUND(SUM(i.net_amt)) AS total_net_amt
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 DAY
                AND i.time_of_sale < CURDATE()
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;
            '''
            cursor.execute(query)
        elif timeframe == "monthly":
            query = '''
            SELECT 
                staff_name,                
                s.store_name,
                ROUND(SUM(i.net_amt)) AS total_net_amt
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 MONTH
                AND i.time_of_sale < CURDATE()
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;
            '''
            cursor.execute(query)
    else:
        if timeframe == "daily":
            query = '''
            SELECT 
                staff_name,                
                s.store_name,
                ROUND(SUM(i.net_amt)) AS total_net_amt
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
			join
				toc_shops ts on ts.blName = s.store_name
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 DAY
                AND i.time_of_sale < CURDATE()
                AND store_name = %s
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;
            '''
            cursor.execute(query, (shop_name,))
        elif timeframe == "monthly":
            query = '''
            SELECT 
                staff_name,                
                s.store_name,
                ROUND(SUM(i.net_amt)) AS total_net_amt
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
			join
				toc_shops ts on ts.blName = s.store_name
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 MONTH
                AND i.time_of_sale < CURDATE()
                AND store_name = %s
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;

            '''
            cursor.execute(query, (shop_name,))

    # Fetch all rows from the query result
    rows = cursor.fetchall()

    # Get column names from the cursor description
    column_names = [desc[0] for desc in cursor.description]

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows

def get_sales_data(shop_name, from_date, to_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"query input sales")
    # print(f"Shop: {shop_name}")
    # print(f"from date: {from_date}")
    # print(f"to date: {to_date}")

    try:

    # Default query for Head Office or non-specific shop
        if shop_name == "Head Office":
            query = '''
                SELECT
                    DATE_FORMAT(ts.time_of_sale, '%%Y-%%m-%%d') AS date,  
                    ROUND(SUM(ti.net_amt), 2) AS total_net_amount  ,
                    count(distinct ts.sales_id) as count_orders,
                    round(SUM(ti.net_amt)/count( distinct ts.sales_id)) as average
                FROM
                    toc_ls_sales ts
                JOIN
                    toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                where
                    ts.time_of_sale >= %s and ts.time_of_sale < %s
                GROUP BY
                    date
                ORDER BY
                    date ASC;
                               
            '''
            cursor.execute(query, (from_date, to_date))

        elif shop_name == "Online":
            query = '''
                SELECT
                    DATE_FORMAT(wo.order_date, '%%Y-%%m-%%d') AS date,  
                    ROUND(SUM(wo.total_amount / 1.15), 2) AS total_net_amount ,
                    count(wo.order_id) as count_orders,
                    round(SUM(wo.total_amount / 1.15)/count(wo.order_id)) as average
                FROM
                    toc_wc_sales_order wo
                WHERE
                    wo.order_date >= %s and wo.order_date < %s
                    and wo.status not in ('wc-cancelled','wc-pending')
                GROUP BY
                    date
                ORDER BY
                    date ASC; 
            '''
            cursor.execute(query, (from_date, to_date))

        else:
            query = '''
                SELECT
                    DATE_FORMAT(tlsi.time_of_sale, '%%Y-%%m-%%d') AS date,  
                    ROUND(SUM(tlsi.net_amt), 2) AS total_net_amount  ,
                    count(distinct ts.sales_id) as count_orders,
                    round(SUM(tlsi.net_amt)/count(distinct ts.sales_id)) as average
                FROM
                    toc_ls_sales_item tlsi
				JOIN 
					toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
				JOIN 
				    toc_shops s ON ts.store_customer = s.customer
                WHERE
                    ts.store_name = %s
                    AND ts.time_of_sale >= %s AND ts.time_of_sale < %s
                GROUP BY
                    date
                ORDER BY
                    date ASC;
            '''

            # Execute the query with parameterized values
            cursor.execute(query, (shop_name, from_date, to_date))

        rows = cursor.fetchall()

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]
    except Exception as e:
        print(f"Error executing query: {e}")
        column_names = []
        rows = []

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows


def get_product_sales_data(shop_name, from_date, to_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"query input sales")
    # print(f"Shop: {shop_name}")
    # print(f"from date: {from_date}")
    # print(f"to date: {to_date}")

    try:

        # Default query for Head Office or non-specific shop
        if shop_name == "Head Office":
            query = '''
                    SELECT
                        p.item_name,  
                        round(sum(ti.quantity),2) AS count,
                        ROUND(SUM(ti.net_amt), 2) AS total_net_amount,
                        ROUND(SUM(p.cost_price), 2) AS total_cost_price,
                        ROUND(
                            (SUM(ti.net_amt) - SUM(p.cost_price)) / SUM(ti.net_amt) * 100, 2
                        ) AS gross_profit_percentage
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE
                        ts.time_of_sale >= %s
                        AND ts.time_of_sale < %s
                    GROUP BY
                        p.item_name
                    ORDER BY
                        total_net_amount DESC;
            '''
            cursor.execute(query, (from_date, to_date))

        elif shop_name == "Online":
            query = '''
                SELECT
                    a.product_name,  
                    round(sum(a.quantity),2) AS count,
                    ROUND(SUM(a.total_amount/1.15), 2) AS total_net_amount,
                    ROUND(SUM(p.cost_price), 2) AS total_cost_price,
                    ROUND(
                        (SUM(a.total_amount/1.15) - SUM(p.cost_price)) / SUM(a.total_amount/1.15) * 100, 2
                    ) AS gross_profit_percentage
                FROM
                    toc_wc_sales_items a
                JOIN
                    toc_product p ON a.sku = p.item_sku
                WHERE
                    a.creation_date >= %s
                    AND a.creation_date < %s
                GROUP BY
                    a.product_name
                ORDER BY
                    total_net_amount DESC;
            '''
            cursor.execute(query, (from_date, to_date))

        else:
            query = '''
                    SELECT
                        p.item_name,  
                        round(sum(ti.quantity),2) AS count,
                        ROUND(SUM(ti.net_amt), 2) AS total_net_amount
                    --    ROUND(SUM(p.cost_price), 2) AS total_cost_price
                    --    ROUND(
                    --        (SUM(ti.net_amt) - SUM(p.cost_price)) / SUM(ti.net_amt) * 100, 2
                    --    ) AS gross_profit_percentage
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE
                        ts.store_name = %s
                        AND ts.time_of_sale >= %s
                        AND ts.time_of_sale < %s
                    GROUP BY
                        p.item_name
                    ORDER BY
                        total_net_amount DESC;
            '''

            # Execute the query with parameterized values
            cursor.execute(query, (shop_name, from_date, to_date))

        rows = cursor.fetchall()

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]
    except Exception as e:
        print(f"Error executing query: {e}")
        column_names = []
        rows = []

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows


def get_top_sellers(shop_name, from_date, to_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"query input sales")
    # print(f"Shop: {shop_name}")
    # print(f"from date: {from_date}")
    # print(f"to date: {to_date}")

    try:

        # Default query for Head Office or non-specific shop
        if shop_name == "Head Office":
            query = '''
            SELECT 
                staff_name,                
                s.store_name,
                ROUND(SUM(i.net_amt)) AS total_net_amt
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
            WHERE 
                i.time_of_sale >= %s
                AND i.time_of_sale < %s
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC;


            '''
            cursor.execute(query, (from_date, to_date))

        else:
            query = '''
            SELECT 
                staff_name,                
                s.store_name,
                ROUND(SUM(i.net_amt)) AS total_net_amt
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
			join
				toc_shops ts on ts.blName = s.store_name
            WHERE 
                i.time_of_sale >= %s
                AND i.time_of_sale < %s
                AND store_name = %s
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC;
            
            '''
            # Execute the query with parameterized values
            cursor.execute(query, (from_date, to_date,shop_name))

        rows = cursor.fetchall()

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]
    except Exception as e:
        print(f"Error executing query: {e}")
        column_names = []
        rows = []

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows


def get_top_specials(shop_name, from_date, to_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"query input sales")
    # print(f"Shop: {shop_name}")
    # print(f"from date: {from_date}")
    # print(f"to date: {to_date}")

    try:

        # Default query for Head Office or non-specific shop
        if shop_name == "Head Office":
            query = '''
                    SELECT
                        p.item_name,  
                        p.stat_group,
                        round(sum(ti.quantity),2) AS count
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE
                        ts.time_of_sale >= %s
                        AND ts.time_of_sale < %s
                        and p.acct_group = 'Specials'
                    GROUP BY
                        p.item_name
                    ORDER BY
                        3 DESC;
            '''
            cursor.execute(query, (from_date, to_date))

        elif shop_name == "Online":
            query = '''
                SELECT
                    a.product_name,
                    p.stat_group,  
                    round(sum(a.quantity),2) AS count
                FROM
                    toc_wc_sales_items a
                JOIN
                    toc_product p ON a.sku = p.item_sku
                WHERE
                    a.creation_date >= %s
                    AND a.creation_date < %s
                    and p.acct_group = 'Specials'
                GROUP BY
                    a.product_name
                ORDER BY
                    3 DESC;
            '''
            cursor.execute(query, (from_date, to_date))

        else:
            query = '''
                    SELECT
                        p.item_name,  
                        p.stat_group,
                        round(sum(ti.quantity),2) AS count
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE
                        ts.store_name = %s
                        AND ts.time_of_sale >= %s
                        AND ts.time_of_sale < %s
                        and p.acct_group = 'Specials'
                    GROUP BY
                        p.item_name
                    ORDER BY
                        3 DESC;
            '''

            # Execute the query with parameterized values
            cursor.execute(query, (shop_name, from_date, to_date))

        rows = cursor.fetchall()

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]
    except Exception as e:
        print(f"Error executing query: {e}")
        column_names = []
        rows = []

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows

def get_top_brand(shop_name, from_date, to_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    # print(f"query input sales")
    # print(f"Shop: {shop_name}")
    # print(f"from date: {from_date}")
    # print(f"to date: {to_date}")

    try:

        # Default query for Head Office or non-specific shop
        if shop_name == "Head Office":
            query = '''
                    SELECT
                        p.acct_group as category,  
                        count(p.acct_group) AS count,
                        ROUND(SUM(ti.net_amt), 2) AS total_net_amount,
                        ROUND(SUM(p.cost_price), 2) AS total_cost_price,
                        ROUND(
                            (SUM(ti.net_amt) - SUM(p.cost_price)) / SUM(ti.net_amt) * 100, 2
                        ) AS gross_profit_percentage
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE
                        ts.time_of_sale >= %s
                        AND ts.time_of_sale < %s
                    GROUP BY
                        p.acct_group
                    ORDER BY
                        3 DESC;
            '''
            cursor.execute(query, (from_date, to_date))

        elif shop_name == "Online":
            query = '''
                SELECT
                    p.acct_group as category,
                    count(p.acct_group) AS count,
                    ROUND(SUM(a.total_amount/1.15), 2) AS total_net_amount,
                    ROUND(SUM(p.cost_price), 2) AS total_cost_price,
                    ROUND(
                        (SUM(a.total_amount/1.15) - SUM(p.cost_price)) / SUM(a.total_amount/1.15) * 100, 2
                    ) AS gross_profit_percentage
                FROM
                    toc_wc_sales_items a
                JOIN
                    toc_product p ON a.sku = p.item_sku
                WHERE
                    a.creation_date >= %s
                    AND a.creation_date < %s
                GROUP BY
                    p.acct_group
                ORDER BY
                    3 DESC;
            '''
            cursor.execute(query, (from_date, to_date))

        else:
            query = '''
                    SELECT
                        p.acct_group as category,  
                        count(p.acct_group) AS count,
                        ROUND(SUM(ti.net_amt), 2) AS total_net_amount
                   --     ROUND(SUM(p.cost_price), 2) AS total_cost_price,
                   --     ROUND(
                   --         (SUM(ti.net_amt) - SUM(p.cost_price)) / SUM(ti.net_amt) * 100, 2
                   --     ) AS gross_profit_percentage
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE
                        ts.store_name = %s
                        AND ts.time_of_sale >= %s
                        AND ts.time_of_sale < %s
                    GROUP BY
                        p.acct_group
                    ORDER BY
                        3 DESC;
            '''

            # Execute the query with parameterized values
            cursor.execute(query, (shop_name, from_date, to_date))

        rows = cursor.fetchall()

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]
    except Exception as e:
        print(f"Error executing query: {e}")
        column_names = []
        rows = []

    cursor.close()
    conn.close()

    # Return both column names and data
    return column_names, rows


################################################  REPORT SECTION

def get_sales_report(report_type, from_date, to_date, group_by):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if report_type == "Sales Report Per Shop":

        # Start with the base query for all report types
        query = '''
                    SELECT 
                        a.store_name, 
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        count(*) AS total_sales_quantity,
                        ROUND(SUM(b.net_amt)) AS total_sales_amount,
                        ROUND(SUM(d.cost_price)) AS total_cost_price,
                        ROUND(SUM(b.net_amt)) -  ROUND(SUM(d.cost_price)) AS gross_profit,
                        ROUND(
                            (SUM(b.net_amt) - SUM(d.cost_price)) / SUM(b.net_amt) * 100, 2
                        ) AS gross_profit_percentage                        
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        count(*) AS total_sales_quantity,
                        ROUND(SUM(b.net_amt)) AS total_sales_amount,
                        ROUND(SUM(d.cost_price)) AS total_cost_price,
                        ROUND(
                            (SUM(b.net_amt) - SUM(d.cost_price)) / SUM(b.net_amt) * 100, 2
                        ) AS gross_profit_percentage   
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        count(*) AS total_sales_quantity,
                        ROUND(SUM(b.net_amt)) AS total_sales_amount,
                        ROUND(SUM(d.cost_price)) AS total_cost_price,
                        ROUND(
                            (SUM(b.net_amt) - SUM(d.cost_price)) / SUM(b.net_amt) * 100, 2
                        ) AS gross_profit_percentage   
                    '''

        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    LEFT JOIN 
                        toc_product d ON b.item_sku = d.item_sku 
           --         LEFT JOIN 
           --             toc_ls_payments c ON b.sales_id = c.sales_id
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= DATE_ADD(%s, INTERVAL 1 DAY)
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += f''' 
                         GROUP BY a.store_name
                         
                         union all
                         
                         SELECT 
                            "Online" AS source,
                            COUNT(DISTINCT wo.order_id) AS no_sales, 
                            ROUND(SUM(wo.total_amount / 1.15), 2) AS net_amount,  -- Matches Query A
                            ROUND(SUM(order_cost.total_cost), 2) AS cost_price, 
                            round(ROUND(SUM(wo.total_amount / 1.15), 2) - ROUND(SUM(order_cost.total_cost), 2)) as gross_profit,
                             ROUND((SUM(wo.total_amount / 1.15) - SUM(order_cost.total_cost)) / SUM(wo.total_amount / 1.15) * 100, 2) as gross_prof_pct
                        FROM 
                            toc_wc_sales_order wo
                        LEFT JOIN (
                            -- Aggregate cost per order to avoid duplication
                            SELECT 
                                a.order_id, 
                                SUM(b.cost_price) AS total_cost
                            FROM 
                                toc_wc_sales_items a
                            LEFT JOIN 
                                toc_product b ON a.sku = b.item_sku
                            GROUP BY 
                                a.order_id
                        ) order_cost ON wo.order_id = order_cost.order_id
                        WHERE 
                            wo.order_date > '{from_date}'
                            and wo.order_date  <= DATE_ADD('{to_date}', INTERVAL 1 DAY)
                            AND wo.status NOT IN ('wc-cancelled', 'wc-pending');
                        
                                        
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY a.store_name, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY a.store_name, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month (e.g., Oct/2024)
                    '''

        # Add ORDER BY clause
        # query += '''
        #             ORDER BY 3 desc;
        #         '''

    elif report_type == "Sales Report Per Staff":
        # Start the query with columns specific to "Sales Report Per Staff"
        query = '''
                    SELECT 
                        a.store_name,
                        b.staff_name,
                        s.tier,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_shops s on a.store_name = s.blName
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= DATE_ADD(%s, INTERVAL 1 DAY)                 
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY a.store_name, b.staff_name, s.tier
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY a.store_name, b.staff_name,s.tier, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY a.store_name, b.staff_name, s.tier DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC;
                '''

    elif report_type == "Product Sales Report":
        # Start the query with columns specific to "Product Sales Report"
        query = '''
                    SELECT 
                        b.item_name,
                        b.item_sku,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt,
                        ROUND(SUM(d.cost_price)) AS total_cost_price,
                        ROUND(
                            (SUM(b.net_amt) - SUM(d.cost_price)) / SUM(b.net_amt) * 100, 2
                        ) AS gross_profit_percentage   
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_product d ON b.item_sku = d.item_sku
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= DATE_ADD(%s, INTERVAL 1 DAY)
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY b.item_name, b.item_sku
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY b.item_name, b.item_sku, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY b.item_name, b.item_sku, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC;
                '''

    elif report_type == "Brand Sales Report":
        # Start the query with columns specific to "Product Category Sales Report"
        query = '''
                    SELECT 
                        d.stat_group as Brand,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt,
                        ROUND(SUM(d.cost_price)) AS total_cost_price,
                        ROUND(
                            (SUM(b.net_amt) - SUM(d.cost_price)) / SUM(b.net_amt) * 100, 2
                        ) AS gross_profit_percentage   
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_product d ON b.item_sku = d.item_sku
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= DATE_ADD(%s, INTERVAL 1 DAY)
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY d.stat_group
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY d.stat_group, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY d.stat_group, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC;
                '''

    elif report_type == "Product Category Sales Report":
        # Start the query with columns specific to "Product Category Sales Report"
        query = '''
                    SELECT 
                        p.acct_group as Category,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        count(p.acct_group) AS count,
                        ROUND(SUM(ti.net_amt), 2) AS total_net_amount,
                        ROUND(SUM(p.cost_price), 2) AS total_cost_price,
                        ROUND(
                            (SUM(ti.net_amt) - SUM(p.cost_price)) / SUM(ti.net_amt) * 100, 2
                        ) AS gross_profit_percentage  
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(ti.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        SUM(ti.quantity) AS total_quantity,
                        ROUND(SUM(ti.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(ti.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        SUM(ti.quantity) AS total_quantity,
                        ROUND(SUM(ti.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM
                        toc_ls_sales ts
                    JOIN
                        toc_ls_sales_item ti ON ts.sales_id = ti.sales_id
                    JOIN
                        toc_product p ON ti.item_sku = p.item_sku
                    WHERE 
                        ts.time_of_sale >= %s AND ts.time_of_sale <= DATE_ADD(%s, INTERVAL 1 DAY)
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY p.acct_group
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY p.stat_group, DATE_FORMAT(ti.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY p.stat_group, DATE_FORMAT(ti.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY 3 DESC;
                '''

    elif report_type == "Customer Sales Report":
        # Start the query with columns specific to "Customer Sales Report"
        query = '''
                    SELECT 
                        CONCAT(m.first_name,' ', m.last_name) AS name,
                        m.email,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_ls_payments p ON p.sales_id = a.sales_id
                    JOIN
                        toc_canna_member m ON p.email = m.email
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= DATE_ADD(%s, INTERVAL 1 DAY)
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY m.first_name, m.last_name, m.email
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY m.first_name, m.last_name, m.email, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY m.first_name, m.last_name, m.email, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC
                    LIMIT 40;
                '''

    # Execute the query with the given date range
    cursor.execute(query, (from_date, to_date))  # Pass dates as parameters to prevent SQL injection
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_db_variance_report(report_type, from_date, to_date, group_by):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Base query initialization
    query = """
        SELECT 
    """

    # Add fields for `group_by == 'none'` change
    if group_by == 'none':
        query += """
            a.replenish_id as order_id,
            a.creation_date,
            a.shop_name,
            a.sku,
            a.product_name,
            a.count_by,
            round(a.calc_stock_qty,2) as Sent_Calc_Qty,
            a.final_stock_qty as Received_Counted_Qty,
            a.rejects_qty as damaged,
            round(a.variance,2) as variance,
            round(a.variance * b.cost_price) as variance_amount,  
            coalesce(ts.blName,"NA") as sent_from,       
            a.rejects_qty as damaged,                        
            a.comments
        """
    elif group_by == 'day':
        query += """
            a.shop_name,
            DATE_FORMAT(a.stock_qty_date, '%%Y-%%m-%%d') AS Date,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(a.variance)), 2) AS total_variance
        """
    elif group_by == 'month':
        query += """
            a.shop_name,
            DATE_FORMAT(a.stock_qty_date, '%%b/%%Y') AS Month,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(a.variance)), 2) AS total_variance
        """
    elif group_by == 'user':
        query += """
            a.count_by AS user,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(a.variance)), 2) AS total_variance
        """
    elif group_by == 'shop':
        query += """
            a.shop_name,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(a.variance)), 2) AS total_variance
        """

    # Add FROM clause
    query += """
        FROM toc_stock_variance a
        JOIN toc_product b on a.sku = b.item_sku
        LEFT JOIN toc_replenish_ctrl trc on a.replenish_id = trc.order_id
        LEFT JOIN toc_shops ts on trc.sent_from = ts.store
        WHERE a.stock_qty_date >= %s AND a.stock_qty_date <= %s
    """

    # Filter by report type
    if report_type == "Stock Count Variance":
        query += " AND a.replenish_id LIKE '%%C'"
    elif report_type == "Stock Receive Variance":
        query += " AND a.replenish_id LIKE '%%R' OR a.replenish_id LIKE '%%I'"

    # Add dynamic GROUP BY clause if not `none`
    if group_by == 'day':
        query += " GROUP BY a.shop_name, DATE_FORMAT(a.stock_qty_date, '%%Y-%%m-%%d')"
    elif group_by == 'month':
        query += " GROUP BY a.shop_name, DATE_FORMAT(a.stock_qty_date, '%%b/%%Y')"
    elif group_by == 'user':
        query += " GROUP BY a.count_by"
    elif group_by == 'shop':
        query += " GROUP BY a.shop_name"

    # Add ORDER BY clause
    if group_by != 'none':
        query += " ORDER BY a.creation_date DESC"
        if group_by in ['day', 'month']:
            query += ", a.stock_qty_date ASC"

    # Execute the query with the given parameters
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_stock_value():

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
            WITH sales_counts AS (
              SELECT
                  st.sku,
                  st.shop_id,
                  st.stock_qty_date,
                  COUNT(*) AS count_items
              FROM toc_stock st
              JOIN toc_ls_sales_item ti ON st.sku = ti.item_sku
              JOIN toc_ls_sales ts ON ti.sales_id = ts.sales_id and st.shop_id = ts.store_customer
              WHERE ts.time_of_sale > st.stock_qty_date
              GROUP BY st.sku, st.shop_id, st.stock_qty_date
            )
            SELECT
                d.item_sku,
                d.item_name,
                st.shop_name,
                st.shop_id,
                st.stock_qty_date,
                st.final_stock_qty as gross_stock_qty,
                st.stock_transfer as stock_movement,
                COALESCE(sc.count_items, 0) AS sold_items,
                st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0) AS current_stock,
                ROUND((st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0)) * d.cost_price) AS total_cost_price,
                ROUND((st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0)) * d.retail_price) AS total_retail_price
            FROM toc_stock st
            JOIN toc_product d 
              ON st.sku = d.item_sku
            LEFT JOIN sales_counts sc 
              ON st.sku = sc.sku 
              AND st.shop_id = sc.shop_id
              AND st.stock_qty_date = sc.stock_qty_date
            WHERE d.acct_group <> 'Specials'
              AND d.item_sku <> '9568'  
            --  and st.shop_name = 'CC - Menlyn'
              AND st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0) > 0;
            '''

    # Execute the query with the parameter
    cursor.execute(query)
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_stock_value_per_shop():

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
          WITH sales_counts AS (
            SELECT
                st.sku,
                st.shop_id,
                st.stock_qty_date,
                COUNT(*) AS count_items
            FROM toc_stock st
            JOIN toc_ls_sales_item ti 
              ON st.sku = ti.item_sku
            JOIN toc_ls_sales ts 
              ON ti.sales_id = ts.sales_id and st.shop_id = ts.store_customer
            WHERE ts.time_of_sale > st.stock_qty_date
            GROUP BY st.sku, st.shop_id, st.stock_qty_date
        ),
        stock_data AS (
            SELECT
                st.shop_name,
                st.shop_id,
                st.stock_qty_date,
                st.final_stock_qty as gross_stock_qty,
                st.stock_transfer,
                COALESCE(sc.count_items, 0) AS count_items,
                (st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0)) AS current_stock,
                ROUND((st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0)) * d.cost_price) AS total_cost_price,
                ROUND((st.final_stock_qty +st.stock_transfer - COALESCE(sc.count_items, 0)) * d.retail_price) AS total_retail_price
            FROM toc_stock st
            JOIN toc_product d 
              ON st.sku = d.item_sku
            LEFT JOIN sales_counts sc 
              ON st.sku = sc.sku 
              AND st.shop_id = sc.shop_id
              AND st.stock_qty_date = sc.stock_qty_date
            WHERE d.acct_group <> 'Specials'
              AND d.item_sku <> '9568'           -- Exclude refund item
              AND st.final_stock_qty + st.stock_transfer - COALESCE(sc.count_items, 0) > 0
        )
        SELECT
            shop_name,
            SUM(total_cost_price) AS total_cost_price,
            SUM(total_retail_price) AS total_retail_price
        FROM stock_data
        GROUP BY shop_name;
            '''

    # Execute the query with the parameter
    cursor.execute(query)
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_back_order():

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
            WITH sales_data AS (
               SELECT 
                d.item_sku,
                d.item_name,
                b.store_customer,
                c.blName AS shop_name,
                COUNT(CASE WHEN a.time_of_sale > CURDATE() - INTERVAL 14 DAY THEN a.sales_id END) AS threshold_sold_qty,
                COUNT(CASE WHEN a.time_of_sale > CURDATE() - INTERVAL 35 DAY THEN a.sales_id END) AS replenish_qty,
                -- COUNT(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.sales_id END) AS sales_since_stock_read
                SUM(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.quantity END) AS sales_since_stock_read
            FROM 
                toc_product d
             JOIN 
                toc_ls_sales_item a
                ON d.item_sku = a.item_sku
             JOIN 
                toc_ls_sales b 
                ON a.sales_id = b.sales_id
             JOIN 
                toc_shops c
                ON b.store_customer = c.customer
             JOIN
                toc_stock st
                ON d.item_sku = st.sku AND b.store_customer = st.shop_id
            WHERE 
                d.acct_group <> 'Specials'
              --  AND c.blName = %s
                AND d.item_sku <> '9568'  -- Refund item
            GROUP BY 
                d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date
            UNION ALL
            SELECT 
                st.sku AS item_sku,
                d.item_name,
                st.shop_id AS store_customer,
                c.blName AS shop_name,
                0 AS threshold_sold_qty,
                0 AS replenish_qty,
                0 AS sales_since_stock_read
            FROM 
                toc_stock st
             JOIN 
                toc_product d 
                ON st.sku = d.item_sku 
                AND d.acct_group <> 'Specials' 
                AND d.item_sku <> '9568'  -- Exclude refund item
             JOIN 
                toc_shops c 
                ON st.shop_id = c.customer
            WHERE 
              --  c.blName = %s
                 NOT EXISTS (
                    SELECT 1
                    FROM toc_ls_sales_item a
                    JOIN toc_ls_sales b ON a.sales_id = b.sales_id
                    WHERE a.item_sku = st.sku 
                    AND b.store_customer = st.shop_id
                )
            )
            SELECT 
                s.item_sku,
                s.item_name,
                s.shop_name,
                
                st.final_stock_qty 
                    - s.sales_since_stock_read 
                    + COALESCE((
                        SELECT SUM(tro.received_qty) 
                        FROM toc_replenish_order tro
                        WHERE tro.shop_id = s.store_customer 
                          AND tro.sku = s.item_sku
                          AND tro.received_date > st.stock_qty_date
                    ), 0) AS gross_stock_qty,  -- Updated current_stock_qty calculation
                    st.stock_transfer as stock_movement,
                    s.replenish_qty AS 5_weeks_sales,
                ( 
                    st.final_stock_qty + st.stock_transfer
                    - s.sales_since_stock_read 
               --     + COALESCE((
               --         SELECT SUM(tro.received_qty) 
               --         FROM toc_replenish_order tro
               --         WHERE tro.shop_id = s.store_customer 
               --           AND tro.sku = s.item_sku
               --           AND tro.received_date > st.stock_qty_date
               --     ), 0) 
                    - s.replenish_qty
                ) AS order_back -- Added column for stock difference
            FROM 
                sales_data s
            LEFT JOIN 
                toc_stock st
            ON 
                s.item_sku = st.sku AND s.store_customer = st.shop_id
            WHERE 
                ( 
                    st.final_stock_qty 
                    - s.sales_since_stock_read + st.stock_transfer
            --        + COALESCE((
            --            SELECT SUM(tro.received_qty) 
            --            FROM toc_replenish_order tro
            --            WHERE tro.shop_id = s.store_customer 
            --              AND tro.sku = s.item_sku
            --              AND tro.received_date > st.stock_qty_date
            --        ), 0)
                ) > s.replenish_qty -- Filter records where current_stock_qty > 3_weeks_sales
            ORDER BY  
                3 DESC, 6 desc;
            '''

    # Execute the query with the parameter
    cursor.execute(query)
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_transactions(from_date,to_date):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
                SELECT DISTINCT 
                    a.sales_id, 
                    a.store_name, 
                    DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d %%H:%%i') AS time_of_sale, 
                    MONTH(a.time_of_sale) AS monnth, 
                    a.quantity AS sales_quantity, 
                    a.owner_name, 
                    b.salesline_id, 
                    b.item_name,
                    b.item_sku, 
                    b.quantity AS item_quantity, 
                    b.tot_amt, 
                    b.net_amt, 
                    b.tax_amt, 
                    b.discount_amt, 
                    b.stat_group, 
                    b.staff_name, 
                    d.acct_group, 
                    d.retail_price, 
                    d.cost_price, 
                    d.wh_price, 
                    d.cann_cost_price, 
                    c.email
                FROM toc_ls_sales a
                JOIN toc_ls_sales_item b ON a.sales_id = b.sales_id
                JOIN toc_product d ON b.item_sku = d.item_sku 
                LEFT JOIN toc_ls_payments c ON b.sales_id = c.sales_id
                WHERE a.time_of_sale > %s 
                  AND a.time_of_sale < %s
                ORDER BY a.time_of_sale ASC;
            '''

    # Execute the query with the parameter
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_online_transactions(from_date,to_date):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
                select 
                a.order_id, b.sales_id, 
                 DATE_FORMAT(a.order_date, '%%Y-%%m-%%d %%H:%%i') AS time_of_sale,
                 a.total_amount,
                 a.discount_amount, a.customer_id, a.customer_name,
                  a.customer_email, a.customer_phone, a.status, b.sales_id, b.product_name,
                   b.sku, b.quantity, b.total_amount as charge_amount
                from toc_wc_sales_order a
                JOIN toc_wc_sales_items b on a.order_id = b.order_id
                WHERE a.order_date > %s 
                  AND a.order_date < %s
                ORDER BY 3 desc;
            '''

    # Execute the query with the parameter
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_product_category_per_staff(from_date,to_date):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
            select a.staff_name, b.store_name, s.tier, p.acct_group as category, round(sum(a.net_amt)) as total, count(*) as count
            from toc_ls_sales_item a 
            JOIN toc_ls_sales b on a.sales_id = b.sales_id
            JOIN toc_product p on a.item_sku = p.item_sku
            JOIN toc_shops s on b.store_customer = s.customer
            WHERE a.time_of_sale > %s  AND a.time_of_sale < %s
            GROUP BY a.staff_name, b.store_name, s.tier, p.acct_group
            ORDER BY 5 desc;
            '''

    # Execute the query with the parameter
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_timesheet_history(from_date,to_date):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
            SELECT 
                s.blName AS shop_name, 
                c.week, 
                DATE_FORMAT(w.from_date, '%%Y-%%m-%%d') AS from_date, 
                DATE_FORMAT(w.to_date, '%%Y-%%m-%%d') AS to_date, 
                c.status, 
                DATE_FORMAT(c.status_date, '%%Y-%%m-%%d %%H:%%i') AS status_date, 
                c.confirmed_by, 
                b.casuals AS list_of_casuals, 
                DATE_FORMAT(b.date, '%%Y-%%m-%%d') AS date_worked
            FROM toc_casuals_ctrl c
            JOIN toc_shops s ON c.shop_id = s.customer
            JOIN toc_casuals b ON c.shop_id = b.shop_id AND c.week = b.week
            JOIN toc_weeks w ON c.week = w.week
            WHERE w.from_date > %s  
            AND w.to_date < %s
            ORDER BY w.to_date DESC;

            '''

    # Execute the query with the parameter
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_user_activities():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
               select * from toc_user_activity order by 2 desc limit 300; 
            '''

    # Execute the query with the parameter
    cursor.execute(query)
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to a list of dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return columns, result_as_dicts  # Now returning two values

def get_replenishment_data(order_id):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
            select a.order_id,s2.blName as From_Shop, s1.blName as To_Shop, a.order_open_date as Open_Date, a.user as Replenisher, a.order_status as Status ,
             o.sku, o.item_name, o.replenish_qty, o.comments,o.received_date , o.received_qty, o.variance, o.received_comment
            from toc_replenish_ctrl a
            JOIN toc_shops s1 on a.shop_id = s1.customer
            JOin toc_shops s2 on a.sent_from = s2.store
            JOIN toc_replenish_order o on a.order_id = o.order_id
            where a.order_id = %s ;
            '''

    # Execute the query with the parameter
    cursor.execute(query,(order_id))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to a list of dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return columns, result_as_dicts  # Now returning two values

def   get_detailed_damaged_return(from_date, to_date):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    query = f'''
        SELECT 
            d.shop_id,
            d.order_id,
            d.sku,
            d.order_open_date,
            d.user,
            d.item_name,
            d.rejected_qty,
            d.rcv_damaged,
            d.variance,
            p.cost_price,
            p.retail_price,
            ROUND(d.rejected_qty * p.cost_price, 2) AS total_cost_value,
            ROUND(d.rejected_qty * p.retail_price, 2) AS total_retail_value
        FROM toc_damaged d
        JOIN toc_product p ON d.sku = p.item_sku
        WHERE d.order_open_date BETWEEN %s AND %s
        ORDER BY d.order_open_date DESC
    '''
    # Execute the query with the parameter
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts


def get_consolidated_damaged_return(from_date, to_date):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    query = f'''
        SELECT 
            d.shop_id,
            DATE(d.order_open_date) AS order_date,
            SUM(d.rejected_qty) AS total_damaged_qty,
            SUM(d.rcv_damaged) AS total_rcv_damaged,
            SUM(d.variance) AS total_variance,
            round(SUM(d.rejected_qty * p.cost_price)) AS total_cost_value,
            round(SUM(d.rejected_qty * p.retail_price)) AS total_retail_value
        FROM toc_damaged d
        JOIN toc_product p ON d.sku = p.item_sku
        WHERE d.order_open_date BETWEEN %s AND %s
        GROUP BY d.shop_id
     --   ORDER BY order_date DESC
    '''
    # Execute the query with the parameter
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts










