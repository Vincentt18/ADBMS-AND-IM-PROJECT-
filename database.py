"""
Milk Tea Shop Management System
Database layer - MySQL persistence and connection management.
"""

import json
import os
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

try:
    import mysql.connector as mysql
    from mysql.connector import errorcode
except ImportError:
    mysql = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_HOST = os.environ.get("MILKTEA_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("MILKTEA_DB_PORT", 3306))
DB_USER = os.environ.get("MILKTEA_DB_USER", "root")
DB_PASSWORD = os.environ.get("MILKTEA_DB_PASSWORD", "")
DB_NAME = os.environ.get("MILKTEA_DB_NAME", "milktea_db")
DB_INITIALIZED = False


def _get_db_connection(use_database=True):
    if mysql is None:
        raise RuntimeError(
            "mysql.connector is required. Install mysql-connector-python or set up the MySQL client."
        )
    config = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "charset": "utf8mb4",
        "use_unicode": True,
    }
    if use_database:
        config["database"] = DB_NAME
    return mysql.connect(**config)


def _execute(conn, query, params=None, fetch=False, multi=False):
    try:
        with conn.cursor(dictionary=True) as cursor:
            if multi:
                for _ in cursor.execute(query, multi=True):
                    pass
                return None
            cursor.execute(query, params or ())
            if fetch:
                return cursor.fetchall()
            return cursor.rowcount
    except mysql.Error as e:
        error_message = f"Database query failed: {e}. Query: {query}. Params: {params}"
        print(error_message)
        traceback.print_exc()
        raise RuntimeError(error_message) from e


def _get_next_id(conn, table, id_col="id"):
    VALID_ID_TABLES = {
        "activity_logs", "error_logs", "orders", "order_items", "order_item_toppings",
        "inventory", "employees", "users", "expenses", "promos", "menu_items",
        "menu_prices", "recipes", "payment_methods",
    }
    if table not in VALID_ID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    if not isinstance(id_col, str) or not id_col.isidentifier():
        raise ValueError(f"Invalid column name: {id_col}")

    row = _execute(conn, f"SELECT MAX({id_col}) AS max_id FROM {table}", fetch=True)
    if not row or row[0].get("max_id") is None:
        return 1
    return int(row[0]["max_id"]) + 1


def _split_sql_statements(sql):
    statements = []
    buf = []
    in_single = in_double = in_backtick = False
    in_line_comment = in_block_comment = False
    routine_depth = 0
    token = []
    i = 0
    length = len(sql)

    def flush_token():
        nonlocal token
        tok = ''.join(token).lower()
        token = []
        return tok

    while i < length:
        ch = sql[i]
        next_ch = sql[i + 1] if i + 1 < length else ""

        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buf.append(ch)
            if ch == "*" and next_ch == "/":
                buf.append(next_ch)
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and sql[i - 1:i] != "\\":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"' and sql[i - 1:i] != "\\":
                in_double = False
            i += 1
            continue

        if in_backtick:
            buf.append(ch)
            if ch == "`":
                in_backtick = False
            i += 1
            continue

        if ch == "-" and next_ch == "-":
            buf.append(ch)
            buf.append(next_ch)
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and next_ch == "*":
            buf.append(ch)
            buf.append(next_ch)
            in_block_comment = True
            i += 2
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue

        if ch == "`":
            in_backtick = True
            buf.append(ch)
            i += 1
            continue

        buf.append(ch)

        if ch.isalpha() or ch == "_":
            token.append(ch)
        else:
            keyword = flush_token()
            if keyword == "begin":
                routine_depth += 1
            elif keyword == "end" and routine_depth > 0:
                routine_depth -= 1

        if ch == ";" and routine_depth == 0:
            statement = ''.join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []

        i += 1

    if buf:
        remaining = ''.join(buf).strip()
        if remaining:
            statements.append(remaining)

    return statements


def _resolve_id_by_value(conn, table, value_col, value, insert_if_missing=False):
    if not value:
        return None
    rows = _execute(conn, f"SELECT id FROM {table} WHERE {value_col} = %s LIMIT 1", (value,), fetch=True)
    if rows:
        return rows[0]["id"]
    if insert_if_missing:
        new_id = _get_next_id(conn, table)
        _execute(conn, f"INSERT INTO {table} (id, {value_col}) VALUES (%s, %s)", (new_id, value), fetch=False)
        return new_id
    return None


def _resolve_promo_id(conn, promo_code):
    return _resolve_id_by_value(conn, "promos", "code", promo_code)


def _resolve_user_id(conn, user_name):
    if not user_name:
        return None
    rows = _execute(conn, "SELECT id FROM users WHERE username = %s OR name = %s LIMIT 1", (user_name, user_name), fetch=True)
    return rows[0]["id"] if rows else None


def _resolve_payment_method_id(conn, payment_method):
    return _resolve_id_by_value(conn, "payment_methods", "method", payment_method, insert_if_missing=True)


def _persist_activity_log(conn, action, details="", user="Unknown"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    next_id = _get_next_id(conn, "activity_logs")
    _execute(
        conn,
        "INSERT INTO activity_logs (id, timestamp, `user`, action, details) VALUES (%s, %s, %s, %s, %s)",
        (next_id, timestamp, user, action, details),
        fetch=False,
    )
    return next_id


def _persist_error_log(conn, error_type, message, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    next_id = _get_next_id(conn, "error_logs")
    _execute(
        conn,
        "INSERT INTO error_logs (id, timestamp, type, message, details) VALUES (%s, %s, %s, %s, %s)",
        (next_id, timestamp, error_type, message, details),
        fetch=False,
    )
    return next_id


def _persist_order(conn, order):
    prev_autocommit = getattr(conn, "autocommit", None)
    try:
        if prev_autocommit is not None:
            conn.autocommit = False

        order_id = order.get("id") or _get_next_id(conn, "orders")
        order_total = order.get("total", order.get("total_amount", 0))
        order_payment = order.get("payment", order.get("payment_method", ""))
        promo_id = _resolve_promo_id(conn, order.get("promo_code", ""))
        created_by_user_id = _resolve_user_id(conn, order.get("created_by", ""))
        payment_method_id = _resolve_payment_method_id(conn, order_payment)
        _execute(
            conn,
            "INSERT INTO orders (id, order_datetime, customer_name, total_amount, promo_id, created_by_user_id, payment_method_id, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                order_id,
                order.get("order_datetime", None),
                order.get("customer_name", ""),
                order_total,
                promo_id,
                created_by_user_id,
                payment_method_id,
                order.get("notes", ""),
            ),
            fetch=False,
        )
        next_item_id = _get_next_id(conn, "order_items")
        for item in order.get("items", []):
            item_id = item.get("id") or next_item_id
            if item.get("id") is None:
                next_item_id += 1
            _execute(
                conn,
                "INSERT INTO order_items (id, order_id, menu_item_id, `size`, quantity, unit_price, line_total) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    item_id,
                    order_id,
                    item.get("item", {}).get("id"),
                    item.get("size", ""),
                    item.get("quantity", 1),
                    item.get("unit_price", 0),
                    item.get("total", 0),
                ),
                fetch=False,
            )
            for topping in item.get("toppings", []):
                _execute(
                    conn,
                    "INSERT INTO order_item_toppings (order_item_id, topping_id, quantity, price) VALUES (%s, %s, %s, %s)",
                    (
                        item_id,
                        topping.get("id"),
                        topping.get("quantity", 1),
                        topping.get("price", 0),
                    ),
                    fetch=False,
                )
        conn.commit()
        return order_id
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if prev_autocommit is not None:
            conn.autocommit = prev_autocommit


def _persist_inventory_item(conn, item):
    item_id = item.get("id") or _get_next_id(conn, "inventory")
    _execute(
        conn,
        "INSERT INTO inventory (id, name, unit, quantity, threshold, cost_per_unit) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name), unit=VALUES(unit), quantity=VALUES(quantity), threshold=VALUES(threshold), cost_per_unit=VALUES(cost_per_unit)",
        (
            item_id,
            item.get("name", ""),
            item.get("unit", ""),
            item.get("quantity", 0),
            item.get("threshold", 0),
            item.get("cost_per_unit", 0),
        ),
        fetch=False,
    )
    item["id"] = item_id
    return item_id


def _update_inventory_quantity(conn, item_id, delta):
    _execute(
        conn,
        "UPDATE inventory SET quantity = GREATEST(quantity + %s, 0) WHERE id = %s",
        (delta, item_id),
        fetch=False,
    )


def _delete_inventory_item(conn, item_id):
    _execute(conn, "DELETE FROM inventory WHERE id = %s", (item_id,), fetch=False)


def _delete_order_by_id(conn, order_id):
    _execute(
        conn,
        "DELETE FROM order_item_toppings WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = %s)",
        (order_id,),
        fetch=False,
    )
    _execute(conn, "DELETE FROM order_items WHERE order_id = %s", (order_id,), fetch=False)
    _execute(conn, "DELETE FROM orders WHERE id = %s", (order_id,), fetch=False)


def _table_empty(conn, table_name):
    """Check if table is empty using whitelist to prevent SQL injection."""
    VALID_TABLES = {
        "categories", "sugar_levels", "ice_levels", "settings", "users",
        "inventory", "employees", "toppings", "promos", "menu_items",
        "menu_prices", "recipes", "expenses", "attendance_logs", "orders",
        "order_items", "order_item_toppings", "activity_logs", "error_logs"
    }
    if table_name not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table_name}")
    row = _execute(conn, f"SELECT COUNT(*) AS cnt FROM {table_name}", fetch=True)
    return not row or row[0]["cnt"] == 0


def _init_db(default_data):
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    if mysql is None:
        raise RuntimeError(
            "mysql.connector is required. Install mysql-connector-python."
        )
    with _get_db_connection(use_database=False) as conn:
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    with _get_db_connection() as conn:
        conn.autocommit = False
        cursor = conn.cursor()
        schema_path = os.path.join(BASE_DIR, "milktea_mysql_schema.sql")
        if not os.path.exists(schema_path):
            raise RuntimeError(f"MySQL schema file not found: {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        for statement in _split_sql_statements(schema_sql):
            if statement:
                cursor.execute(statement)
        _seed_default_data(conn, default_data)
        conn.commit()
    DB_INITIALIZED = True


def _seed_default_data(conn, default_data):
    if _table_empty(conn, "categories"):
        for idx, category in enumerate(default_data["categories"], start=1):
            _execute(conn, "INSERT INTO categories (id, name) VALUES (%s, %s)", (idx, category))
    if _table_empty(conn, "sugar_levels"):
        for idx, level in enumerate(default_data["sugar_levels"], start=1):
            _execute(conn, "INSERT INTO sugar_levels (id, level, sort_order) VALUES (%s, %s, %s)", (idx, level, idx))
    if _table_empty(conn, "ice_levels"):
        for idx, level in enumerate(default_data["ice_levels"], start=1):
            _execute(conn, "INSERT INTO ice_levels (id, level, sort_order) VALUES (%s, %s, %s)", (idx, level, idx))
    if _table_empty(conn, "settings"):
        for key, value in default_data["settings"].items():
            _execute(conn, "INSERT INTO settings (`key`, `value`) VALUES (%s, %s)", (key, str(value)))
    if _table_empty(conn, "users"):
        for user in default_data["users"]:
            _execute(conn, "INSERT INTO users (id, username, password, role, name, must_change_password, active) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                     (user["id"], user["username"], user["password"], user["role"], user["name"], int(user.get("must_change_password", False)), int(user.get("active", True))))
    if _table_empty(conn, "inventory"):
        for item in default_data["inventory"]:
            _execute(conn, "INSERT INTO inventory (id, name, unit, quantity, threshold, cost_per_unit) VALUES (%s, %s, %s, %s, %s, %s)",
                     (item["id"], item["name"], item["unit"], item["quantity"], item["threshold"], item["cost_per_unit"]))
    if _table_empty(conn, "employees"):
        for emp in default_data["employees"]:
            _execute(conn, "INSERT INTO employees (id, name, role, phone, hire_date, hourly_rate, active) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                     (emp["id"], emp["name"], emp["role"], emp["phone"], emp["hire_date"], emp["hourly_rate"], int(emp.get("active", True))))
    if _table_empty(conn, "toppings"):
        for topping in default_data["toppings"]:
            _execute(conn, "INSERT INTO toppings (id, name, price, available) VALUES (%s, %s, %s, %s)",
                     (topping["id"], topping["name"], topping["price"], int(topping.get("available", True))))
    if _table_empty(conn, "promos"):
        for promo in default_data["promos"]:
            _execute(conn, "INSERT INTO promos (id, code, description, type, value, active) VALUES (%s, %s, %s, %s, %s, %s)",
                     (promo["id"], promo["code"], promo["description"], promo["type"], promo["value"], int(promo.get("active", True))))
    if _table_empty(conn, "menu_items"):
        for item in default_data["menu_items"]:
            category_id = None
            if item.get("category"):
                category_row = _execute(conn, "SELECT id FROM categories WHERE name = %s", (item["category"],), fetch=True)
                category_id = category_row[0]["id"] if category_row else None
            _execute(conn, "INSERT INTO menu_items (id, name, category_id, available, image_path) VALUES (%s, %s, %s, %s, %s)",
                     (item["id"], item["name"], category_id, int(item.get("available", True)), item.get("image_path", "")))
            for size, price in item.get("prices", {}).items():
                _execute(conn, "INSERT INTO menu_prices (menu_item_id, size, price) VALUES (%s, %s, %s)",
                         (item["id"], size, price))
            for recipe_item in item.get("recipe", []):
                _execute(conn, "INSERT INTO recipes (menu_item_id, inventory_id, qty) VALUES (%s, %s, %s)",
                         (item["id"], recipe_item["inventory_id"], recipe_item["qty"]))
