
import os
import traceback
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta

try:
    from PIL import Image
except ImportError:
    Image = None

from utils import COLORS, make_button
from models import load_data, save_data
from controller import (
    SESSION_TIMEOUT_SECONDS,
    ROLE_PERMISSIONS,
    ROLE_ACTIONS,
    get_allowed_sections,
    can_access_section,
    has_permission,
    check_session_expired,
)
from sections import (
    AttendanceSection,
    DashboardSection,
    EmployeeSection,
    ExpensesSection,
    InventorySection,
    LoadingScreen,
    LoginScreen,
    LogsSection,
    MenuSection,
    POSSection,
    PromosSection,
    ReportsSection,
    SettingsSection,
)


class MilkTeaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.data = load_data()
        self.current_user = None
        self.session_timeout_id = None
        self.last_activity = datetime.now()
        self.geometry("1280x780")
        self.minsize(1100, 700)
        self.configure(fg_color=self.data.get("settings", {}).get("bg_primary", COLORS["bg_primary"]))
        self.update_branding()

        self.withdraw()
        self.after(50, self._start_loading)

    def report_callback_exception(self, exc, val, tb):
        try:
            if isinstance(val, tk.TclError) and "bad window path name" in str(val):
                return
        except Exception as e:
            from utils import log_error
            log_error(self, "Callback Exception Check Error", f"Failed to check exception type: {e}")
        try:
            from utils import log_error
            log_error(self, "Exception", str(val), details="".join(traceback.format_exception(exc, val, tb))[-4000:])
        except Exception as e:
            print(f"Failed to log exception: {e}")
        return super().report_callback_exception(exc, val, tb)

    def load_logo_image(self, size=(32, 32)):
        logo_path = self.data.get("settings", {}).get("logo_path", "")
        if not logo_path or not os.path.exists(logo_path) or Image is None:
            return None
        try:
            pil_image = Image.open(logo_path)
            return ctk.CTkImage(pil_image, size=size)
        except Exception as e:
            from utils import log_error
            log_error(self, "Logo Loading Error", f"Failed to load logo from {logo_path}: {e}")
            return None

    def update_branding(self):
        shop_name = self.data.get("settings", {}).get("shop_name", "Brewster's Cup")
        self.title(f"{shop_name} Management System")
        if hasattr(self, "sidebar_shop_name_label"):
            self.sidebar_shop_name_label.configure(text=shop_name)
        if hasattr(self, "sidebar_tagline_label"):
            self.sidebar_tagline_label.configure(text=self.data.get("settings", {}).get("tagline", ""))
        if hasattr(self, "sidebar_logo_label"):
            logo = self.load_logo_image((32, 32))
            if logo:
                self.sidebar_logo_label.configure(image=logo, text="")
                self.sidebar_logo_image = logo
            else:
                self.sidebar_logo_label.configure(image=None, text="🧋", font=("Helvetica", 32))
        if hasattr(self, "current_login_screen") and self.current_login_screen is not None:
            try:
                if self.current_login_screen.winfo_exists():
                    self.current_login_screen.set_data(self.data)
                else:
                    self.current_login_screen = None
            except Exception as e:
                self.current_login_screen = None
                from utils import log_error
                log_error(self, "Update Branding Error", f"Failed to update login screen: {e}")
        if hasattr(self, "sections") and "dashboard" in self.sections:
            try:
                self.sections["dashboard"].refresh()
            except Exception as e:
                from utils import log_error
                log_error(self, "Update Branding Error", f"Failed to refresh dashboard: {e}")

    def get_allowed_sections(self):
        return get_allowed_sections(self.current_user)

    def can_access_section(self, key):
        return can_access_section(self.current_user, key)

    def has_permission(self, action):
        return has_permission(self.current_user, action)

    def reset_session_timer(self, event=None):
        self.last_activity = datetime.now()
        if self.session_timeout_id:
            try:
                self.after_cancel(self.session_timeout_id)
            except Exception as e:
                from utils import log_error
                log_error(self, "Session Timer Error", f"Failed to cancel session timeout: {e}")
        self.session_timeout_id = self.after(1000, self.check_session_timeout)

    def start_session_timer(self):
        self.last_activity = datetime.now()
        self.reset_session_timer()
        self.bind_all("<Any-KeyPress>", self.reset_session_timer)
        self.bind_all("<Any-ButtonPress>", self.reset_session_timer)

    def stop_session_timer(self):
        if self.session_timeout_id:
            try:
                self.after_cancel(self.session_timeout_id)
            except Exception as e:
                from utils import log_error
                log_error(self, "Session Timer Error", f"Failed to cancel session timeout: {e}")
            self.session_timeout_id = None
        self.unbind_all("<Any-KeyPress>")
        self.unbind_all("<Any-ButtonPress>")

    def check_session_timeout(self):
        if not self.current_user:
            return
        if check_session_expired(self.last_activity):
            from utils import log_activity
            log_activity(self, "Session Timeout", f"{self.current_user.get('name', 'Unknown')} automatically logged out")
            messagebox.showinfo("Session Timeout", "You have been logged out due to inactivity.", parent=self)
            self.show_login()
            return
        self.session_timeout_id = self.after(1000, self.check_session_timeout)

    def _start_loading(self):
        self._loading = LoadingScreen(self, self._finish_startup)

    def _finish_startup(self):
        self.deiconify()
        try:
            self.state("zoomed")
        except Exception as e:
            from utils import log_error
            log_error(self, "Startup Error", f"Failed to maximize window: {e}")
            try:
                self.attributes("-zoomed", True)
            except Exception as e2:
                log_error(self, "Startup Error", f"Failed to maximize window (fallback): {e2}")
        self.show_login()

    def show_login(self):
        from utils import log_activity

        if self.current_user:
            log_activity(self, "Logout", f"User logged out: {self.current_user.get('name','')}")
        self.current_user = None
        self.stop_session_timer()
        self.current_login_screen = None
        for w in self.winfo_children():
            w.destroy()
        login = LoginScreen(self, self.on_login)
        self.current_login_screen = login
        login.set_data(self.data)

    def on_login(self, user):
        from utils import log_activity

        self.current_user = user
        log_activity(self, "Login", f"User logged in: {user['name']} ({user['role']})", user=user['name'])
        self.build_main()

    def build_main(self):
        for w in self.winfo_children():
            w.destroy()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, fg_color="#1F140E", width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(20, weight=1)

        self.sidebar_logo_label = ctk.CTkLabel(self.sidebar, text="🧋", font=("Helvetica", 32))
        self.sidebar_logo_label.grid(row=0, column=0, pady=(24, 0), padx=20, sticky="w")
        self.sidebar_shop_name_label = ctk.CTkLabel(self.sidebar,
                                                    text=self.data["settings"].get("shop_name", "Brewster's Cup"),
                                                    font=("Georgia", 16, "bold"),
                                                    text_color="#D4A373")
        self.sidebar_shop_name_label.grid(row=1, column=0, padx=20, sticky="w")
        self.sidebar_tagline_label = ctk.CTkLabel(self.sidebar,
                                                  text=self.data["settings"].get("tagline", ""),
                                                  font=("Helvetica", 10), text_color="#A88B76")
        self.sidebar_tagline_label.grid(row=2, column=0, padx=20, sticky="w", pady=(0, 8))

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#5B4633").grid(row=3, column=0, sticky="ew", padx=16, pady=8)

        ctk.CTkLabel(self.sidebar,
                     text=f"👤 {self.current_user['name']}\n    {self.current_user['role']}",
                     font=("Helvetica", 10), text_color="#D6C0AD",
                     justify="left").grid(row=4, column=0, padx=20, sticky="w", pady=(0, 8))

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#5B4633").grid(row=5, column=0, sticky="ew", padx=16, pady=8)

        nav_items = [
            ("🏠", "Dashboard", "dashboard"),
            ("📋", "Menu", "menu"),
            ("🛒", "POS", "pos"),
            ("📦", "Inventory", "inventory"),
            ("👥", "Employees", "employees"),
            ("✓", "Attendance", "attendance"),
            ("📊", "Reports", "reports"),
            ("💰", "Expenses", "expenses"),
            ("🎁", "Promotions", "promos"),
            ("📜", "Logs", "logs"),
            ("⚙️", "Settings", "settings"),
        ]

        allowed_nav = self.get_allowed_sections()
        self.nav_buttons = {}
        self.active_nav = ctk.StringVar(value="dashboard" if "dashboard" in allowed_nav else (allowed_nav[0] if allowed_nav else "dashboard"))

        for icon, label, key in nav_items:
            if key not in allowed_nav:
                continue
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {icon}  {label}",
                anchor="w", height=42, corner_radius=10,
                fg_color="transparent", hover_color="#5D4935",
                font=("Helvetica", 12), text_color="#D6C0AD",
                command=lambda k=key: self.navigate(k))
            btn.grid(row=6 + len(self.nav_buttons), column=0, padx=12, pady=2, sticky="ew")
            self.nav_buttons[key] = btn

        make_button(self.sidebar, "🚪 Logout", self.show_login,
                    style="danger", width=180).grid(row=21, column=0, padx=20, pady=20, sticky="s")

        self.content = ctk.CTkFrame(self, fg_color="#2B1F15")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.sections = {}
        self.navigate(self.active_nav.get())
        self.start_session_timer()
        self.update_branding()

    def navigate(self, key):
        self.active_nav.set(key)
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color="#D4A373", text_color="#F7E8D0")
            else:
                btn.configure(fg_color="transparent", text_color="#D6C0AD")

        for w in self.content.winfo_children():
            w.grid_forget()

        if key not in self.get_allowed_sections():
            messagebox.showwarning("Access Denied", "You are not permitted to access that page.", parent=self)
            return

        if key not in self.sections:
            section_map = {
                "dashboard": DashboardSection,
                "menu": MenuSection,
                "pos": POSSection,
                "inventory": InventorySection,
                "employees": EmployeeSection,
                "attendance": AttendanceSection,
                "reports": ReportsSection,
                "expenses": ExpensesSection,
                "promos": PromosSection,
                "logs": LogsSection,
                "settings": SettingsSection,
            }
            cls = section_map.get(key)
            if cls:
                self.sections[key] = cls(self.content, self)

        if key in self.sections:
            self.sections[key].grid(row=0, column=0, sticky="nsew", padx=20, pady=16)
            if hasattr(self.sections[key], "refresh"):
                self.sections[key].refresh()


def main():
    app = MilkTeaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
