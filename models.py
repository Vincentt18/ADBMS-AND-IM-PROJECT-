"""
Milk Tea Shop Management System
Data models and persistence layer.
"""

import json
import os
import hmac
import hashlib
import traceback
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

from database import (
    _get_db_connection,
    _execute,
    _get_next_id,
    _persist_activity_log,
    _persist_error_log,
    _persist_order,
    _persist_inventory_item,
    _update_inventory_quantity,
    _delete_inventory_item,
    _delete_order_by_id,
    _table_empty,
    _init_db,
)


def hash_password(password):
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(stored_password, password):
    if stored_password.startswith("scrypt$"):
        try:
            _, salt_hex, key_hex = stored_password.split("$", 2)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(key_hex)
            key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=len(expected))
            return hmac.compare_digest(key, expected)
        except Exception:
            return False
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored_password)

DEFAULT_DATA = {
    "menu_items": [],
    "toppings": [],
    "attendance_logs": [],
    "categories": ["Milk Tea", "Fruit Tea", "Coffee", "Special"],
    "sugar_levels": ["0%", "25%", "50%", "75%", "100%"],
    "ice_levels": ["No Ice", "Less Ice", "Regular Ice", "Extra Ice"],
    "inventory": [],
    "employees": [],
    "orders": [],
    "expenses": [],
    "promos": [],
    "users": [
        {"id": 1, "username": "admin", "password": hash_password(os.environ.get("MILKTEA_ADMIN_PASSWORD", "Admin@2026!")), "role": "Admin", "name": "Administrator", "must_change_password": True},
        {"id": 2, "username": "cashier", "password": hash_password(os.environ.get("MILKTEA_CASHIER_PASSWORD", "Cashier@2026!")), "role": "Cashier", "name": "Juan Cruz"},
        {"id": 3, "username": "manager", "password": hash_password(os.environ.get("MILKTEA_MANAGER_PASSWORD", "Manager@2026!")), "role": "Manager", "name": "Manager"},
        {"id": 4, "username": "barista", "password": hash_password(os.environ.get("MILKTEA_BARISTA_PASSWORD", "Barista@2026!")), "role": "Barista", "name": "Barista"},
    ],
    "settings": {
        "shop_name": "Brewster's Cup",
        "tagline": "Management System",
        "address": "Lian, Batangas",
        "phone": "09171234567",
        "logo_path": "",
        "login_bg_path": "",
    },
    "error_logs": [],
    "activity_logs": [],
    "next_order_id": 1001,
    "next_expense_id": 1,
    "next_employee_id": 1,
    "next_item_id": 1,
    "next_topping_id": 1,
    "next_promo_id": 1,
    "next_inventory_id": 1,
}





def _build_default_data():
    return json.loads(json.dumps(DEFAULT_DATA))


def _sync_and_load_app_meta(conn, data):
    entities = {
        'orders': 1000,
        'expenses': 0,
        'employees': 0,
        'menu_items': 0,
        'toppings': 0,
        'promos': 0,
        'inventory': 0,
        'users': 0,
        'attendance_logs': 0,
        'activity_logs': 0,
        'error_logs': 0
    }
    for entity, default_min in entities.items():
        row = _execute(conn, f"SELECT MAX(id) AS max_id FROM {entity}", fetch=True)
        max_id = row[0]['max_id'] if row and row[0].get('max_id') is not None else default_min
        if max_id < default_min:
            max_id = default_min
        _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", (entity, max_id + 1), fetch=False)
    
    app_meta = _execute(conn, "SELECT entity, next_id FROM app_meta", fetch=True)
    meta_map = {row["entity"]: row["next_id"] for row in app_meta}
    
    data["next_order_id"] = meta_map.get("orders", 1001)
    data["next_expense_id"] = meta_map.get("expenses", 1)
    data["next_employee_id"] = meta_map.get("employees", 1)
    data["next_item_id"] = meta_map.get("menu_items", 1)
    data["next_topping_id"] = meta_map.get("toppings", 1)
    data["next_promo_id"] = meta_map.get("promos", 1)
    data["next_inventory_id"] = meta_map.get("inventory", 1)
    return data


def load_data():
    _init_db(DEFAULT_DATA)
    try:
        with _get_db_connection() as conn:
            data = _build_default_data()
            data["categories"] = [row["name"] for row in _execute(conn, "SELECT id, name FROM categories ORDER BY id", fetch=True)]
            data["sugar_levels"] = [row["level"] for row in _execute(conn, "SELECT id, level FROM sugar_levels ORDER BY sort_order", fetch=True)]
            data["ice_levels"] = [row["level"] for row in _execute(conn, "SELECT id, level FROM ice_levels ORDER BY sort_order", fetch=True)]
            data["settings"] = {row["key"]: row["value"] for row in _execute(conn, "SELECT `key`, `value` FROM settings", fetch=True)}
            data["users"] = [
                {
                    "id": row["id"],
                    "username": row["username"],
                    "password": row["password"],
                    "role": row["role"],
                    "name": row["name"],
                    "must_change_password": bool(row["must_change_password"]),
                    "active": bool(row["active"]),
                }
                for row in _execute(conn, "SELECT * FROM users ORDER BY id", fetch=True)
            ]
            data["inventory"] = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "unit": row["unit"],
                    "quantity": float(row["quantity"]),
                    "threshold": float(row["threshold"]),
                    "cost_per_unit": float(row["cost_per_unit"]),
                }
                for row in _execute(conn, "SELECT * FROM inventory ORDER BY id", fetch=True)
            ]
            data["employees"] = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "role": row["role"],
                    "phone": row["phone"],
                    "hire_date": row["hire_date"].strftime("%Y-%m-%d") if row.get("hire_date") else "",
                    "hourly_rate": float(row["hourly_rate"]),
                    "active": bool(row["active"]),
                }
                for row in _execute(conn, "SELECT * FROM employees ORDER BY id", fetch=True)
            ]
            data["toppings"] = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price": float(row["price"]),
                    "available": bool(row["available"]),
                }
                for row in _execute(conn, "SELECT * FROM toppings ORDER BY id", fetch=True)
            ]
            data["promos"] = [
                {
                    "id": row["id"],
                    "code": row["code"],
                    "description": row["description"],
                    "type": row["type"],
                    "value": float(row["value"]),
                    "active": bool(row["active"]),
                }
                for row in _execute(conn, "SELECT * FROM promos ORDER BY id", fetch=True)
            ]
            prices = {}
            for row in _execute(conn, "SELECT * FROM menu_prices", fetch=True):
                prices.setdefault(row["menu_item_id"], {})[row["size"]] = float(row["price"])
            recipes = {}
            for row in _execute(conn, "SELECT * FROM recipes", fetch=True):
                recipes.setdefault(row["menu_item_id"], []).append(
                    {"inventory_id": row["inventory_id"], "qty": float(row["qty"])}
                )
            data["menu_items"] = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "category": row["category_name"],
                    "available": bool(row["available"]),
                    "image_path": row["image_path"] or "",
                    "prices": prices.get(row["id"], {}),
                    "recipe": recipes.get(row["id"], []),
                }
                for row in _execute(
                    conn,
                    "SELECT mi.id, mi.name, c.name AS category_name, mi.available, mi.image_path "
                    "FROM menu_items mi "
                    "LEFT JOIN categories c ON mi.category_id = c.id "
                    "ORDER BY mi.id",
                    fetch=True,
                )
            ]
            menu_items_by_id = {item["id"]: item for item in data["menu_items"]}
            order_items_by_id = {}
            order_items_by_order = {}
            for row in _execute(conn, "SELECT * FROM order_items ORDER BY id", fetch=True):
                menu_item = menu_items_by_id.get(row["menu_item_id"], {})
                item = {
                    "id": row["id"],
                    "order_id": row["order_id"],
                    "menu_item_id": row["menu_item_id"],
                    "name": menu_item.get("name", "Unknown Item"),
                    "size": row["size"],
                    "quantity": int(row["quantity"]),
                    "unit_price": float(row["unit_price"]),
                    "line_total": float(row["line_total"]),
                    "toppings": [],
                }
                item["total"] = float(row["line_total"])
                order_items_by_id[row["id"]] = item
                order_items_by_order.setdefault(row["order_id"], []).append(item)
            for row in _execute(conn, "SELECT * FROM order_item_toppings ORDER BY order_item_id", fetch=True):
                order_item = order_items_by_id.get(row["order_item_id"])
                if order_item is not None:
                    order_item["toppings"].append(
                        {"topping_id": row["topping_id"], "quantity": int(row["quantity"]), "price": float(row["price"])}
                    )
            data["orders"] = []
            for row in _execute(
                conn,
                "SELECT o.*, p.code AS promo_code, u.name AS created_by, pm.method AS payment_method "
                "FROM orders o "
                "LEFT JOIN promos p ON p.id = o.promo_id "
                "LEFT JOIN users u ON u.id = o.created_by_user_id "
                "LEFT JOIN payment_methods pm ON pm.id = o.payment_method_id "
                "ORDER BY o.order_datetime DESC",
                fetch=True,
            ):
                items = order_items_by_order.get(row["id"], [])
                order_datetime_str = row["order_datetime"].strftime("%Y-%m-%d %H:%M:%S") if row.get("order_datetime") else ""
                total_amount = float(row["total_amount"])
                subtotal = sum(item.get("line_total", 0) for item in items) if items else total_amount
                discount = subtotal - total_amount if subtotal > total_amount else 0
                data["orders"].append(
                    {
                        "id": row["id"],
                        "order_datetime": order_datetime_str,
                        "date": order_datetime_str.split(" ")[0] if order_datetime_str else "",
                        "time": order_datetime_str.split(" ")[1] if order_datetime_str and " " in order_datetime_str else "",
                        "customer_name": row["customer_name"],
                        "total": total_amount,
                        "subtotal": subtotal,
                        "discount": discount,
                        "promo_code": row.get("promo_code") or "",
                        "created_by": row.get("created_by") or "",
                        "payment": row.get("payment_method") or "",
                        "notes": row["notes"],
                        "items": items,
                    }
                )
            data["expenses"] = [
                {
                    "id": row["id"],
                    "date": row["date"].strftime("%Y-%m-%d") if row.get("date") else "",
                    "category": row["category"],
                    "description": row["description"],
                    "amount": float(row["amount"]),
                }
                for row in _execute(conn, "SELECT * FROM expenses ORDER BY date DESC", fetch=True)
            ]
            data["attendance_logs"] = [
                {
                    "id": row["id"],
                    "employee_id": row["employee_id"],
                    "employee_name": row.get("employee_name") or "",
                    "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if row.get("timestamp") else "",
                    "date": row["timestamp"].strftime("%Y-%m-%d") if row.get("timestamp") else "",
                    "time_in": row["timestamp"].strftime("%H:%M:%S") if row.get("timestamp") else "",
                    "time_out": row["time_out"].strftime("%H:%M:%S") if row.get("time_out") else None,
                    "hours": float(row["hours"]) if row.get("hours") is not None else 0.0,
                    "employee_role": row.get("employee_role") or "",
                    "status": row["status"],
                    "note": row["note"],
                }
                for row in _execute(
                    conn,
                    "SELECT al.*, e.name AS employee_name, e.role AS employee_role "
                    "FROM attendance_logs al "
                    "LEFT JOIN employees e ON e.id = al.employee_id "
                    "ORDER BY al.timestamp DESC",
                    fetch=True,
                )
            ]
            data["activity_logs"] = [
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if row.get("timestamp") else "",
                    "user": row["user"],
                    "action": row["action"],
                    "details": row["details"],
                }
                for row in _execute(conn, "SELECT * FROM activity_logs ORDER BY timestamp DESC", fetch=True)
            ]
            data["error_logs"] = [
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if row.get("timestamp") else "",
                    "type": row["type"],
                    "message": row["message"],
                    "details": row["details"],
                }
                for row in _execute(conn, "SELECT * FROM error_logs ORDER BY timestamp DESC", fetch=True)
            ]
            data = _sync_and_load_app_meta(conn, data)
            return data
    except Exception as e:
        print(f"Load error: {e}")
        try:
            messagebox.showerror(
                "Load Failed",
                f"Could not load application data from the database.\n\nError: {e}",
            )
        except Exception:
            pass
    return _build_default_data()


def save_data(data):
    """Save data using UPSERT logic instead of DELETE+re-INSERT for data safety.
    
    Uses INSERT ... ON DUPLICATE KEY UPDATE (MySQL upsert) to avoid data loss
    from crashes mid-save. Only deletes records that were explicitly removed.
    """
    VALID_SAVE_TABLES = {
        "activity_logs", "error_logs", "orders", "order_items", "order_item_toppings",
        "inventory", "employees", "users", "expenses", "promos", "menu_items",
        "menu_prices", "recipes", "categories", "sugar_levels", "ice_levels",
        "settings", "toppings", "attendance_logs",
    }
    try:
        _init_db(DEFAULT_DATA)
        with _get_db_connection() as conn:
            conn.autocommit = False
            
            def load_existing_ids(table, id_col):
                if table not in VALID_SAVE_TABLES:
                    raise ValueError(f"Invalid table name: {table}")
                if not isinstance(id_col, str) or not id_col.isidentifier():
                    raise ValueError(f"Invalid column name: {id_col}")
                rows = _execute(conn, f"SELECT {id_col} FROM {table}", fetch=True)
                return {row[id_col] for row in rows} if rows else set()
            
            def delete_orphaned(table, id_col, kept_ids):
                if table not in VALID_SAVE_TABLES:
                    raise ValueError(f"Invalid table name: {table}")
                if not isinstance(id_col, str) or not id_col.isidentifier():
                    raise ValueError(f"Invalid column name: {id_col}")
                if kept_ids:
                    placeholders = ",".join(["%s"] * len(kept_ids))
                    _execute(conn, f"DELETE FROM {table} WHERE {id_col} NOT IN ({placeholders})", tuple(kept_ids), fetch=False)
                else:
                    _execute(conn, f"DELETE FROM {table}", fetch=False)
            
            def find_id(table, column, value):
                if not value:
                    return None
                rows = _execute(conn, f"SELECT id FROM {table} WHERE {column} = %s LIMIT 1", (value,), fetch=True)
                return rows[0]["id"] if rows else None

            def get_payment_method_id(method_name):
                if not method_name:
                    return None
                pm_id = find_id("payment_methods", "method", method_name)
                if pm_id is None:
                    pm_id = _get_next_id(conn, "payment_methods")
                    _execute(conn, "INSERT INTO payment_methods (id, method) VALUES (%s, %s)", (pm_id, method_name), fetch=False)
                return pm_id

            new_cats = set(range(1, len(data.get("categories", [])) + 1))
            delete_orphaned("categories", "id", new_cats)
            for idx, category in enumerate(data.get("categories", []), start=1):
                _execute(conn, 
                    "INSERT INTO categories (id, name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name)",
                    (idx, category))
            
            new_sugar = set(range(1, len(data.get("sugar_levels", [])) + 1))
            delete_orphaned("sugar_levels", "id", new_sugar)
            for idx, level in enumerate(data.get("sugar_levels", []), start=1):
                _execute(conn,
                    "INSERT INTO sugar_levels (id, level, sort_order) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE level=VALUES(level), sort_order=VALUES(sort_order)",
                    (idx, level, idx))
            
            new_ice = set(range(1, len(data.get("ice_levels", [])) + 1))
            delete_orphaned("ice_levels", "id", new_ice)
            for idx, level in enumerate(data.get("ice_levels", []), start=1):
                _execute(conn,
                    "INSERT INTO ice_levels (id, level, sort_order) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE level=VALUES(level), sort_order=VALUES(sort_order)",
                    (idx, level, idx))
            
            existing_settings = {row["key"] for row in _execute(conn, "SELECT `key` FROM settings", fetch=True)}
            new_settings = set(data.get("settings", {}).keys())
            delete_orphaned_settings = existing_settings - new_settings
            for key in delete_orphaned_settings:
                _execute(conn, "DELETE FROM settings WHERE `key` = %s", (key,), fetch=False)
            for key, value in data.get("settings", {}).items():
                _execute(conn,
                    "INSERT INTO settings (`key`, `value`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)",
                    (key, str(value)))
            
            new_user_ids = {u.get("id") for u in data.get("users", []) if u.get("id") is not None}
            delete_orphaned("users", "id", new_user_ids)
            next_user_id = max(new_user_ids, default=0) + 1 if new_user_ids else 1
            for user in data.get("users", []):
                user_id = user.get("id") or next_user_id
                if user.get("id") is None:
                    next_user_id += 1
                _execute(conn,
                    "INSERT INTO users (id, username, password, role, name, must_change_password, active) VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE username=VALUES(username), password=VALUES(password), role=VALUES(role), name=VALUES(name), must_change_password=VALUES(must_change_password), active=VALUES(active)",
                    (user_id, user.get("username", ""), user.get("password", ""), user.get("role", ""), user.get("name", ""), int(user.get("must_change_password", False)), int(user.get("active", True))))
            
            new_emp_ids = {e.get("id") for e in data.get("employees", []) if e.get("id") is not None}
            
            existing_emp = load_existing_ids("employees", "id")
            deleted_emp_ids = existing_emp - new_emp_ids
            if deleted_emp_ids:
                placeholders = ",".join(["%s"] * len(deleted_emp_ids))
                _execute(conn, f"DELETE FROM attendance_logs WHERE employee_id IN ({placeholders})", tuple(deleted_emp_ids), fetch=False)
                data["attendance_logs"] = [
                    log for log in data.get("attendance_logs", [])
                    if log.get("employee_id") not in deleted_emp_ids
                ]

            delete_orphaned("employees", "id", new_emp_ids)
            next_employee_id = max(new_emp_ids, default=0) + 1 if new_emp_ids else 1
            for emp in data.get("employees", []):
                emp_id = emp.get("id") or next_employee_id
                if emp.get("id") is None:
                    next_employee_id += 1
                _execute(conn,
                    "INSERT INTO employees (id, name, role, phone, hire_date, hourly_rate, active) VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name), role=VALUES(role), phone=VALUES(phone), hire_date=VALUES(hire_date), hourly_rate=VALUES(hourly_rate), active=VALUES(active)",
                    (emp_id, emp.get("name", ""), emp.get("role", ""), emp.get("phone", ""), emp.get("hire_date", ""), emp.get("hourly_rate", 0), int(emp.get("active", True))))
            
            new_inv_ids = {i.get("id") for i in data.get("inventory", []) if i.get("id") is not None}
            delete_orphaned("inventory", "id", new_inv_ids)
            next_inventory_id = max(new_inv_ids, default=0) + 1 if new_inv_ids else 1
            for item in data.get("inventory", []):
                inv_id = item.get("id") or next_inventory_id
                if item.get("id") is None:
                    next_inventory_id += 1
                _execute(conn,
                    "INSERT INTO inventory (id, name, unit, quantity, threshold, cost_per_unit) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name), unit=VALUES(unit), quantity=VALUES(quantity), threshold=VALUES(threshold), cost_per_unit=VALUES(cost_per_unit)",
                    (inv_id, item.get("name", ""), item.get("unit", ""), item.get("quantity", 0), item.get("threshold", 0), item.get("cost_per_unit", 0)))
            
            new_topping_ids = {t.get("id") for t in data.get("toppings", []) if t.get("id") is not None}
            delete_orphaned("toppings", "id", new_topping_ids)
            next_topping_id = max(new_topping_ids, default=0) + 1 if new_topping_ids else 1
            for topping in data.get("toppings", []):
                topping_id = topping.get("id") or next_topping_id
                if topping.get("id") is None:
                    next_topping_id += 1
                _execute(conn,
                    "INSERT INTO toppings (id, name, price, available) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name), price=VALUES(price), available=VALUES(available)",
                    (topping_id, topping.get("name", ""), topping.get("price", 0), int(topping.get("available", True))))
            
            new_promo_ids = {p.get("id") for p in data.get("promos", []) if p.get("id") is not None}
            delete_orphaned("promos", "id", new_promo_ids)
            next_promo_id = max(new_promo_ids, default=0) + 1 if new_promo_ids else 1
            for promo in data.get("promos", []):
                promo_id = promo.get("id") or next_promo_id
                if promo.get("id") is None:
                    next_promo_id += 1
                _execute(conn,
                    "INSERT INTO promos (id, code, description, type, value, active) VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE code=VALUES(code), description=VALUES(description), type=VALUES(type), value=VALUES(value), active=VALUES(active)",
                    (promo_id, promo.get("code", ""), promo.get("description", ""), promo.get("type", ""), promo.get("value", 0), int(promo.get("active", True))))
            
            existing_menu = load_existing_ids("menu_items", "id")
            new_menu_ids = {i.get("id") for i in data.get("menu_items", []) if i.get("id") is not None}
            deleted_menu_ids = existing_menu - new_menu_ids
            for mid in deleted_menu_ids:
                _execute(conn, "DELETE FROM order_item_toppings WHERE order_item_id IN (SELECT id FROM order_items WHERE menu_item_id = %s)", (mid,), fetch=False)
                _execute(conn, "DELETE FROM order_items WHERE menu_item_id = %s", (mid,), fetch=False)
                _execute(conn, "DELETE FROM recipes WHERE menu_item_id = %s", (mid,), fetch=False)
                _execute(conn, "DELETE FROM menu_prices WHERE menu_item_id = %s", (mid,), fetch=False)
                _execute(conn, "DELETE FROM menu_items WHERE id = %s", (mid,), fetch=False)
            
            next_menu_item_id = max(new_menu_ids, default=0) + 1 if new_menu_ids else 1
            for item in data.get("menu_items", []):
                item_id = item.get("id") or next_menu_item_id
                if item.get("id") is None:
                    next_menu_item_id += 1
                category_name = item.get("category", "")
                category_id = _execute(conn, "SELECT id FROM categories WHERE name = %s", (category_name,), fetch=True)
                category_id = category_id[0]["id"] if category_id else None
                _execute(conn,
                    "INSERT INTO menu_items (id, name, category_id, available, image_path) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE name=VALUES(name), category_id=VALUES(category_id), available=VALUES(available), image_path=VALUES(image_path)",
                    (item_id, item.get("name", ""), category_id, int(item.get("available", True)), item.get("image_path", "")))
                existing_prices = _execute(conn, "SELECT size FROM menu_prices WHERE menu_item_id = %s", (item_id,), fetch=True)
                existing_sizes = {row["size"] for row in existing_prices} if existing_prices else set()
                new_sizes = set(item.get("prices", {}).keys())
                deleted_sizes = existing_sizes - new_sizes
                for size in deleted_sizes:
                    _execute(conn, "DELETE FROM menu_prices WHERE menu_item_id = %s AND size = %s", (item_id, size), fetch=False)
                for size, price in item.get("prices", {}).items():
                    _execute(conn,
                        "INSERT INTO menu_prices (menu_item_id, size, price) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE price=VALUES(price)",
                        (item_id, size, price))
                _execute(conn, "DELETE FROM recipes WHERE menu_item_id = %s", (item_id,), fetch=False)
                for recipe_item in item.get("recipe", []):
                    _execute(conn, "INSERT INTO recipes (menu_item_id, inventory_id, qty) VALUES (%s, %s, %s)",
                        (item_id, recipe_item.get("inventory_id"), recipe_item.get("qty", 0)))
            
            available_menu_ids = {item.get("id") for item in data.get("menu_items", []) if item.get("id") is not None and item.get("available", True)}
            valid_topping_ids = {topping.get("id") for topping in data.get("toppings", []) if topping.get("id") is not None}
            for order in data.get("orders", []):
                if "items" not in order:
                    continue
                sanitized_items = []
                for item in order.get("items", []):
                    if item.get("menu_item_id") not in available_menu_ids:
                        continue
                    item["toppings"] = [t for t in item.get("toppings", []) if t.get("topping_id") in valid_topping_ids]
                    sanitized_items.append(item)
                if len(sanitized_items) != len(order.get("items", [])):
                    order["items"] = sanitized_items
                    order["total"] = sum(i.get("line_total", i.get("total", 0)) for i in sanitized_items)
            
            existing_expenses = load_existing_ids("expenses", "id")
            new_expense_ids = {e.get("id") for e in data.get("expenses", []) if e.get("id") is not None}
            delete_orphaned("expenses", "id", new_expense_ids)
            next_expense_id = max(new_expense_ids, default=0) + 1 if new_expense_ids else 1
            for expense in data.get("expenses", []):
                expense_id = expense.get("id") or next_expense_id
                if expense.get("id") is None:
                    next_expense_id += 1
                _execute(conn,
                    "INSERT INTO expenses (id, date, category, description, amount) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE date=VALUES(date), category=VALUES(category), description=VALUES(description), amount=VALUES(amount)",
                    (expense_id, expense.get("date", ""), expense.get("category", ""), expense.get("description", ""), expense.get("amount", 0)))
            
            new_attendance_ids = {log.get("id") for log in data.get("attendance_logs", []) if log.get("id") is not None}
            delete_orphaned("attendance_logs", "id", new_attendance_ids)
            next_attendance_id = max(new_attendance_ids, default=0) + 1 if new_attendance_ids else 1
            for log in data.get("attendance_logs", []):
                attendance_id = log.get("id") or next_attendance_id
                if log.get("id") is None:
                    log["id"] = attendance_id
                    next_attendance_id += 1
                attendance_timestamp = log.get("timestamp")
                if not attendance_timestamp and log.get("date") and log.get("time_in"):
                    attendance_timestamp = f"{log.get('date')} {log.get('time_in')}"
                
                time_out_val = None
                if log.get("time_out"):
                    time_out_val = f"{log.get('date')} {log.get('time_out')}"
                
                hours_val = log.get("hours", 0.0)

                _execute(conn,
                    "INSERT INTO attendance_logs (id, employee_id, status, timestamp, time_out, hours, note) VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE status=VALUES(status), time_out=VALUES(time_out), hours=VALUES(hours), note=VALUES(note)",
                    (attendance_id, log.get("employee_id"), log.get("status", ""), attendance_timestamp, time_out_val, hours_val, log.get("note", "")))
            
            existing_orders = load_existing_ids("orders", "id")
            new_order_ids = {o.get("id") for o in data.get("orders", []) if o.get("id") is not None}
            deleted_order_ids = existing_orders - new_order_ids
            for oid in deleted_order_ids:
                _execute(conn, "DELETE FROM order_item_toppings WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = %s)", (oid,), fetch=False)
                _execute(conn, "DELETE FROM order_items WHERE order_id = %s", (oid,), fetch=False)
                _execute(conn, "DELETE FROM orders WHERE id = %s", (oid,), fetch=False)
            
            next_order_id = max(new_order_ids, default=1000) + 1 if new_order_ids else 1001
            next_order_item_id = _get_next_id(conn, "order_items")
            for order in data.get("orders", []):
                order_id = order.get("id") or next_order_id
                if order.get("id") is None:
                    next_order_id += 1
                promo_id = find_id("promos", "code", order.get("promo_code", ""))
                created_by_value = order.get("created_by", "")
                created_by_user_id = None
                if created_by_value:
                    created_user = _execute(conn, "SELECT id FROM users WHERE username = %s OR name = %s LIMIT 1", (created_by_value, created_by_value), fetch=True)
                    created_by_user_id = created_user[0]["id"] if created_user else None
                payment_method_id = get_payment_method_id(order.get("payment", order.get("payment_method", "")))
                _execute(conn,
                    "INSERT INTO orders (id, order_datetime, customer_name, total_amount, promo_id, created_by_user_id, payment_method_id, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name), total_amount=VALUES(total_amount), promo_id=VALUES(promo_id), created_by_user_id=VALUES(created_by_user_id), payment_method_id=VALUES(payment_method_id), notes=VALUES(notes)",
                    (order_id, order.get("order_datetime", None), order.get("customer_name", ""), order.get("total", order.get("total_amount", 0)), promo_id, created_by_user_id, payment_method_id, order.get("notes", "")))
                _execute(conn, "DELETE FROM order_item_toppings WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = %s)", (order_id,), fetch=False)
                _execute(conn, "DELETE FROM order_items WHERE order_id = %s", (order_id,), fetch=False)
                for item in order.get("items", []):
                    item_id = item.get("id") or next_order_item_id
                    if item.get("id") is None:
                        item["id"] = item_id
                        next_order_item_id += 1
                    _execute(conn,
                        "INSERT INTO order_items (id, order_id, menu_item_id, size, quantity, unit_price, line_total) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (item_id, order_id, item.get("menu_item_id"), item.get("size", ""), item.get("quantity", 1), item.get("unit_price", 0), item.get("line_total", item.get("total", 0))))
                    for topping_item in item.get("toppings", []):
                        _execute(conn,
                            "INSERT INTO order_item_toppings (order_item_id, topping_id, quantity, price) VALUES (%s, %s, %s, %s)",
                            (item_id, topping_item.get("topping_id"), topping_item.get("quantity", 1), topping_item.get("price", 0)))
            
            existing_activities = load_existing_ids("activity_logs", "id")
            new_activity_ids = {log.get("id") for log in data.get("activity_logs", []) if log.get("id") is not None}
            delete_orphaned("activity_logs", "id", new_activity_ids)
            next_activity_id = max(existing_activities, default=0) + 1 if existing_activities else 1
            for log in data.get("activity_logs", []):
                activity_id = log.get("id") or next_activity_id
                if log.get("id") is None:
                    next_activity_id += 1
                _execute(conn,
                    "INSERT INTO activity_logs (id, timestamp, user, action, details) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE timestamp=VALUES(timestamp), user=VALUES(user), action=VALUES(action), details=VALUES(details)",
                    (activity_id, log.get("timestamp", None), log.get("user", ""), log.get("action", ""), log.get("details", "")))
            
            existing_errors = load_existing_ids("error_logs", "id")
            new_error_ids = {log.get("id") for log in data.get("error_logs", []) if log.get("id") is not None}
            delete_orphaned("error_logs", "id", new_error_ids)
            next_error_id = max(existing_errors, default=0) + 1 if existing_errors else 1
            for log in data.get("error_logs", []):
                error_id = log.get("id") or next_error_id
                if log.get("id") is None:
                    next_error_id += 1
                _execute(conn,
                    "INSERT INTO error_logs (id, timestamp, type, message, details) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE timestamp=VALUES(timestamp), type=VALUES(type), message=VALUES(message), details=VALUES(details)",
                    (error_id, log.get("timestamp", None), log.get("type", ""), log.get("message", ""), log.get("details", "")))
            
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("users", next_user_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("employees", next_employee_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("inventory", next_inventory_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("toppings", next_topping_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("promos", next_promo_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("menu_items", next_menu_item_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("expenses", next_expense_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("orders", next_order_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("attendance_logs", next_attendance_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("activity_logs", next_activity_id), fetch=False)
            _execute(conn, "INSERT INTO app_meta (entity, next_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE next_id = GREATEST(next_id, VALUES(next_id))", ("error_logs", next_error_id), fetch=False)
            
            conn.commit()
    except Exception as e:
        messagebox.showerror(
            "Save Failed",
            f"Could not persist application data. Please save again or restart the app after checking the database.\n\nError: {e}",
        )
        raise
