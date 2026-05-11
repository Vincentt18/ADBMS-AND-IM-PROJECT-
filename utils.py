import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import json
import traceback
from datetime import datetime
import math

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import cv2
except ImportError:
    cv2 = None

from database import _get_db_connection, _persist_activity_log, _persist_error_log

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

COLORS = {
    "bg_primary": "#2B1F15",
    "bg_secondary": "#3E2C23",
    "bg_card": "#453525",
    "bg_sidebar": "#1F140E",
    "accent": "#D4A373",
    "accent2": "#A86F46",
    "accent_light": "#E8C6A5",
    "success": "#7CC576",
    "warning": "#D9A05F",
    "danger": "#C9552A",
    "text_primary": "#F7E8D0",
    "text_secondary": "#D6C0AD",
    "text_muted": "#A88B76",
    "border": "#5B4633",
    "hover": "#5D4935",
}

FONTS = {
    "title": ("Georgia", 22, "bold"),
    "heading": ("Georgia", 16, "bold"),
    "subheading": ("Helvetica", 13, "bold"),
    "body": ("Helvetica", 12),
    "small": ("Helvetica", 10),
    "mono": ("Courier", 11),
}

SESSION_TIMEOUT_SECONDS = 600  # Auto-logout after 10 minutes of inactivity
ROLE_PERMISSIONS = {
    "Admin": ["dashboard", "menu", "pos", "inventory", "employees", "attendance", "reports", "expenses", "promos", "logs", "settings", "delete_order"],
    "Manager": ["dashboard", "menu", "pos", "inventory", "employees", "attendance", "reports", "expenses", "promos", "delete_order"],
    "Cashier": ["dashboard", "pos", "attendance"],
    "Barista": ["dashboard", "attendance"],
}
ROLE_ACTIONS = {
    "Admin": ["all"],
    "Manager": ["view_dashboard", "edit_item", "add_item", "toggle_stock", "edit_inventory", "edit_employee", "view_reports", "add_expense", "manage_promos", "record_attendance", "delete_item"],
    "Cashier": ["view_dashboard", "pos_checkout", "record_attendance"],
    "Barista": ["view_dashboard", "record_attendance"],
}


def make_card(parent, **kwargs):
    return ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=12,
                        border_width=1, border_color=COLORS["border"], **kwargs)


def make_label(parent, text, font_key="body", color=None, **kwargs):
    return ctk.CTkLabel(parent, text=text,
                        font=FONTS[font_key],
                        text_color=color or COLORS["text_primary"], **kwargs)


def make_button(parent, text, command=None, style="primary", width=120, **kwargs):
    colors = {
        "primary": (COLORS["accent"], COLORS["accent2"]),
        "secondary": (COLORS["bg_secondary"], COLORS["hover"]),
        "success": (COLORS["success"], "#89C77C"),
        "danger": (COLORS["danger"], "#AB4221"),
        "outline": (COLORS["border"], COLORS["hover"]),
    }
    fg, hover = colors.get(style, colors["primary"])
    return ctk.CTkButton(parent, text=text, command=command,
                         fg_color=fg, hover_color=hover,
                         font=FONTS["subheading"], corner_radius=8,
                         width=width, **kwargs)


def make_entry(parent, placeholder="", width=200, **kwargs):
    return ctk.CTkEntry(parent, placeholder_text=placeholder,
                        width=width, fg_color=COLORS["bg_secondary"],
                        border_color=COLORS["border"],
                        text_color=COLORS["text_primary"],
                        placeholder_text_color=COLORS["text_muted"],
                        corner_radius=8, **kwargs)


def load_image(path, size=(100, 100)):
    if not path or not os.path.exists(path) or Image is None:
        return None
    try:
        pil_image = Image.open(path)
        pil_image.thumbnail(size, Image.LANCZOS)
        return ctk.CTkImage(pil_image, size=size)
    except Exception:
        return None


def make_stat_card(parent, title, value, subtitle="", color=None):
    card = make_card(parent)
    card.grid_columnconfigure(0, weight=1)
    accent = color or COLORS["accent"]
    ctk.CTkLabel(card, text=title, font=FONTS["small"],
                 text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(14, 0))
    ctk.CTkLabel(card, text=str(value), font=("Georgia", 26, "bold"),
                 text_color=accent).pack(anchor="w", padx=16)
    if subtitle:
        ctk.CTkLabel(card, text=subtitle, font=FONTS["small"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(0, 14))
    else:
        ctk.CTkLabel(card, text="", font=FONTS["small"]).pack(pady=(0, 10))
    return card


def themed_table(parent, columns, height=10):
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Custom.Treeview",
                    background=COLORS["bg_secondary"],
                    foreground=COLORS["text_primary"],
                    rowheight=36,
                    fieldbackground=COLORS["bg_secondary"],
                    bordercolor=COLORS["border"],
                    darkcolor=COLORS["bg_card"],
                    lightcolor=COLORS["bg_card"],
                    font=("Helvetica", 11))
    style.configure("Custom.Treeview.Heading",
                    background=COLORS["bg_sidebar"],
                    foreground=COLORS["accent"],
                    relief="flat",
                    font=("Helvetica", 11, "bold"))
    style.map("Custom.Treeview",
              background=[("selected", COLORS["accent"])],
              foreground=[("selected", "#FFFFFF")])
    style.map("Custom.Treeview.Heading",
              background=[("active", COLORS["hover"])])

    tree = ttk.Treeview(parent, columns=columns, show="headings",
                        style="Custom.Treeview", height=height)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, anchor="center", width=120)
    sb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    return tree, sb


class Dialog(ctk.CTkToplevel):
    def __init__(self, parent, title, width=500, height=400):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.configure(fg_color=COLORS["bg_primary"])
        self.grab_set()
        self.resizable(False, False)
        self.result = None
        self.update_idletasks()
        x = parent.winfo_rootx() + parent.winfo_width() // 2 - width // 2
        y = parent.winfo_rooty() + parent.winfo_height() // 2 - height // 2
        self.geometry(f"+{x}+{y}")

    def add_header(self, text):
        ctk.CTkLabel(self, text=text, font=FONTS["heading"],
                     text_color=COLORS["accent"]).pack(pady=(20, 10))

    def add_buttons(self, save_cmd, cancel_cmd, save_text="Save", cancel_text="Cancel",
                    save_style="primary", cancel_style="secondary"):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=10)
        make_button(f, cancel_text, cancel_cmd, style=cancel_style).pack(side="right", padx=5)
        make_button(f, save_text, save_cmd, style=save_style).pack(side="right", padx=5)


def _resolve_app_from_widget(widget):
    if widget is None:
        return None
    if hasattr(widget, "data") and hasattr(widget, "current_user"):
        return widget
    if hasattr(widget, "app") and widget.app is not None:
        return widget.app
    cur = widget
    for _ in range(12):
        try:
            if hasattr(cur, "data") and hasattr(cur, "current_user"):
                return cur
            if hasattr(cur, "app") and cur.app is not None:
                return cur.app
            if hasattr(cur, "master"):
                cur = cur.master
            else:
                break
        except Exception:
            break
    return None


def show_error(parent, title, message, details=""):
    try:
        app = _resolve_app_from_widget(parent)
        if app is not None:
            log_error(app, title, message, details=details)
    except Exception:
        pass
    return messagebox.showerror(title, message, parent=parent)


def validate_numeric_input(value_str, field_name, allow_zero=True, max_value=1000000, is_price=False):
    try:
        value = float(value_str.strip()) if is_price else int(float(value_str.strip()))
    except ValueError:
        return (False, None, f"{field_name} must be a number.")
    if value < 0:
        return (False, None, f"{field_name} cannot be negative.")
    if value == 0 and not allow_zero:
        return (False, None, f"{field_name} must be greater than 0.")
    if value > max_value:
        return (False, None, f"{field_name} cannot exceed {max_value}.")
    if not is_price and value == int(value):
        value = int(value)
    return (True, value, "")


def log_activity(app, action, details="", user=None):
    if user is None and hasattr(app, 'current_user'):
        user = app.current_user['name'] if app.current_user else "Unknown"
    elif user is None:
        user = "Unknown"

    log_id = None
    try:
        with _get_db_connection() as conn:
            conn.autocommit = False
            log_id = _persist_activity_log(conn, action, details, user)
            conn.commit()
    except Exception as e:
        messagebox.showerror("Logging Failed", f"Could not persist activity log: {e}", parent=getattr(app, 'root', None))
        return

    entry = {
        "id": log_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "action": action,
        "details": details,
    }
    if "activity_logs" not in app.data:
        app.data["activity_logs"] = []
    app.data["activity_logs"].append(entry)
    if len(app.data["activity_logs"]) > 1000:
        app.data["activity_logs"] = app.data["activity_logs"][-1000:]


def log_error(app, error_type, message, details=""):
    error_id = None
    try:
        with _get_db_connection() as conn:
            conn.autocommit = False
            error_id = _persist_error_log(conn, error_type, message, details)
            conn.commit()
    except Exception as e:
        messagebox.showerror("Error Logging Failed", f"Could not persist error log: {e}", parent=getattr(app, 'root', None))
        return

    entry = {
        "id": error_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": error_type,
        "message": message,
        "details": details,
    }
    if "error_logs" not in app.data:
        app.data["error_logs"] = []
    app.data["error_logs"].append(entry)
    if len(app.data["error_logs"]) > 500:
        app.data["error_logs"] = app.data["error_logs"][-500:]
