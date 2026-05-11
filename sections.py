import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import json
import math
import traceback
from datetime import datetime

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import cv2
except ImportError:
    cv2 = None

from utils import (
    COLORS,
    FONTS,
    make_card,
    make_label,
    make_button,
    make_entry,
    load_image,
    make_stat_card,
    themed_table,
    Dialog,
    show_error,
    validate_numeric_input,
    log_activity,
    log_error,
)
from models import save_data, hash_password, verify_password, DEFAULT_DATA


class MenuSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 16))
        make_label(hdr, "Menu Management", "heading").pack(side="left")
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.pack(side="right")
        make_button(btn_frame, "📁 Categories", self.manage_categories, width=120).pack(side="left", padx=4)
        make_button(btn_frame, "+ Add Item", self.add_item_dialog, width=110).pack(side="left", padx=4)

        flt = ctk.CTkFrame(self, fg_color="transparent")
        flt.pack(fill="x", pady=(0, 10))
        self.cat_filter_frame = flt
        self.cat_var = ctk.StringVar(value="All")
        self.menu_search_var = ctk.StringVar(value="")
        self._build_category_filters()

        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("ID", "Name", "Category", "Small", "Medium", "Large", "Status")
        self.tree, sb = themed_table(card, cols, height=14)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.pack(fill="x", pady=8)
        can_edit = self.app.has_permission("edit_item")
        can_delete = self.app.has_permission("delete_item")
        can_toggle = self.app.has_permission("toggle_stock")
        make_button(acts, "✏ Edit", self.edit_item, style="secondary",
                    state="normal" if can_edit else "disabled").pack(side="left", padx=4)
        make_button(acts, "🗑 Delete", self.delete_item, style="danger",
                    state="normal" if can_delete else "disabled").pack(side="left", padx=4)
        make_button(acts, "⚡ Toggle Stock", self.toggle_stock, style="outline",
                    state="normal" if can_toggle else "disabled").pack(side="left", padx=4)

        tp_card = make_card(self)
        tp_card.pack(fill="x", pady=(8, 0))
        th = ctk.CTkFrame(tp_card, fg_color="transparent")
        th.pack(fill="x", padx=16, pady=10)
        make_label(th, "Toppings & Add-ons", "subheading").pack(side="left")
        body = ctk.CTkFrame(tp_card, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 12))

        table_wrap = ctk.CTkFrame(body, fg_color="transparent")
        table_wrap.pack(side="left", fill="both", expand=True)

        cols2 = ("ID", "Name", "Price", "Available")
        self.top_tree, sb2 = themed_table(table_wrap, cols2, height=5)
        self.top_tree.pack(side="left", fill="both", expand=True, padx=(0, 8))
        sb2.pack(side="right", fill="y")

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(side="right", fill="y")

        btn_w = 190
        make_button(actions, "+ Add Topping", self.add_topping_dialog, width=btn_w).pack(anchor="e", pady=(0, 8))
        make_button(actions, "✏ Edit Topping", self.edit_topping_dialog, style="secondary", width=btn_w).pack(anchor="e", pady=(0, 8))
        make_button(actions, "🗑 Delete Topping", self.delete_topping, style="danger", width=btn_w).pack(anchor="e", pady=(0, 8))
        make_button(actions, "⚡ Toggle Availability", self.toggle_topping, style="outline", width=btn_w).pack(anchor="e")

        self.refresh()

    def refresh(self):
        cat = self.cat_var.get()
        q = (self.menu_search_var.get() or "").strip().lower()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.app.data["menu_items"]:
            if cat != "All" and item.get("category", "") != cat:
                continue
            if q and q not in (item.get("name", "").lower()):
                continue
            p = item["prices"]
            status = "✅ Available" if item["available"] else "❌ Out of Stock"
            self.tree.insert("", "end", values=(
                item["id"], item["name"], item["category"],
                f"₱{p.get('Small', '-')}", f"₱{p.get('Medium', '-')}", f"₱{p.get('Large', '-')}",
                status))
        for row in self.top_tree.get_children():
            self.top_tree.delete(row)
        for t in self.app.data["toppings"]:
            self.top_tree.insert("", "end", values=(
                t["id"], t["name"], f"₱{t['price']}", "✅ Yes" if t["available"] else "❌ No"))

    def _build_category_filters(self):
        for child in self.cat_filter_frame.winfo_children():
            child.destroy()

        make_label(self.cat_filter_frame, "Filter:", "small", COLORS["text_muted"]).pack(side="left", padx=(0, 8))
        categories = ["All"] + self.app.data["categories"]
        for cat in categories:
            btn = ctk.CTkRadioButton(self.cat_filter_frame, text=cat, variable=self.cat_var,
                                     value=cat, command=self.refresh,
                                     fg_color=COLORS["bg_secondary"], text_color=COLORS["text_primary"],
                                     hover_color=COLORS["hover"])
            btn.pack(side="left", padx=4)

        search_wrap = ctk.CTkFrame(self.cat_filter_frame, fg_color="transparent")
        search_wrap.pack(side="right")
        make_label(search_wrap, "Search", "small", COLORS["text_muted"]).pack(side="left", padx=(0, 8))
        menu_search = make_entry(search_wrap, "Search menu items…", 260, textvariable=self.menu_search_var)
        menu_search.pack(side="left")
        menu_search.bind("<KeyRelease>", lambda e: self.refresh())

    def get_selected_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select Item", "Please select an item first.", parent=self)
            return None
        iid = self.tree.item(sel[0])["values"][0]
        return next((i for i in self.app.data["menu_items"] if i["id"] == iid), None)

    def get_selected_topping(self):
        sel = self.top_tree.selection()
        if not sel:
            messagebox.showwarning("Select Topping", "Please select a topping first.", parent=self)
            return None
        tid = self.top_tree.item(sel[0])["values"][0]
        return next((t for t in self.app.data["toppings"] if t["id"] == tid), None)

    def add_item_dialog(self):
        if not self.app.has_permission("add_item"):
            messagebox.showwarning("Permission Denied", "You do not have permission to add menu items.", parent=self)
            return
        self._item_dialog()

    def edit_item(self):
        if not self.app.has_permission("edit_item"):
            messagebox.showwarning("Permission Denied", "You do not have permission to edit menu items.", parent=self)
            return
        item = self.get_selected_item()
        if item:
            self._item_dialog(item)

    def _item_dialog(self, item=None):
        dlg = Dialog(self.app, "Add Menu Item" if not item else "Edit Menu Item", 520, 560)
        dlg.add_header("Add Menu Item" if not item else "Edit Menu Item")

        form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24)

        def row(lbl, widget):
            f = ctk.CTkFrame(form, fg_color="transparent")
            f.pack(fill="x", pady=4)
            make_label(f, lbl, "small", COLORS["text_muted"]).pack(anchor="w")
            widget.master = f
            widget.pack(anchor="w")
            return widget

        name_e = make_entry(form, "Drink name", 320)
        if item:
            name_e.insert(0, item.get("name", ""))
        name_e.bind("<Return>", lambda e: cat_dd.focus())
        row("Name", name_e)

        cat_var = ctk.StringVar(value=item["category"] if item else self.app.data["categories"][0])
        cat_dd = ctk.CTkOptionMenu(form, variable=cat_var, values=self.app.data["categories"],
                                   fg_color=COLORS["bg_secondary"], button_color=COLORS["accent"],
                                   width=200)
        row("Category", cat_dd)

        prices_frame = ctk.CTkFrame(form, fg_color="transparent")
        prices_frame.pack(fill="x", pady=4)
        make_label(prices_frame, "Prices", "small", COLORS["text_muted"]).pack(anchor="w")
        pf = ctk.CTkFrame(prices_frame, fg_color="transparent")
        pf.pack(anchor="w")

        price_entries = {}
        size_list = ["Small", "Medium", "Large"]
        for idx, size in enumerate(size_list):
            sf = ctk.CTkFrame(pf, fg_color="transparent")
            sf.pack(side="left", padx=6)
            make_label(sf, size, "small").pack()
            e = make_entry(sf, "0", 80)
            if item:
                e.insert(0, str(item.get("prices", {}).get(size, 0) or 0))
            e.pack()
            price_entries[size] = e
            if idx < len(size_list) - 1:
                next_size = size_list[idx + 1]
                e.bind("<Return>", lambda event, ns=next_size: price_entries[ns].focus())
            else:
                e.bind("<Return>", lambda event: form.focus())
        cat_dd.bind("<Return>", lambda e: price_entries["Small"].focus())

        photo_path = item.get("image_path", "") if item else ""
        photo_desc_label = make_label(form, photo_path and os.path.basename(photo_path) or "No image selected", "small", COLORS["text_secondary"])
        photo_desc_label.pack(anchor="w", pady=(6, 0))
        img_preview = ctk.CTkLabel(form, text="No Image", width=120, height=120,
                                   fg_color=COLORS["bg_secondary"], corner_radius=12)
        img_preview.pack(padx=4, pady=(0, 8))
        if photo_path:
            img = load_image(photo_path, size=(120, 120))
            if img:
                img_preview.configure(image=img, text="")
                img_preview.image = img

        photo_path_var = {"path": photo_path}

        def choose_photo():
            file_path = filedialog.askopenfilename(
                title="Choose item photo",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")],
                parent=dlg)
            if not file_path:
                return
            photo_path_var["path"] = file_path
            photo_desc_label.configure(text=os.path.basename(file_path))
            img = load_image(file_path, size=(120, 120))
            if img:
                img_preview.configure(image=img, text="")
                img_preview.image = img
            else:
                img_preview.configure(image=None, text="No Image")

        make_button(form, "Choose Photo", choose_photo, style="secondary", width=140).pack(anchor="w", pady=(0, 8))

        make_label(form, "Consumes from Inventory (per drink)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(10, 2))
        recipe_card = ctk.CTkFrame(form, fg_color=COLORS["bg_card"], corner_radius=10,
                                   border_width=1, border_color=COLORS["border"])
        recipe_card.pack(fill="x", pady=(0, 6))

        search_frame = ctk.CTkFrame(recipe_card, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=(10, 0))
        self.recipe_search_var = ctk.StringVar(value="")
        make_label(search_frame, "Search inventory", "small", COLORS["text_muted"]).pack(side="left", padx=(0, 8))
        recipe_search = make_entry(search_frame, "Search inventory…", 220, textvariable=self.recipe_search_var)
        recipe_search.pack(side="left")

        recipe_scroll = ctk.CTkScrollableFrame(recipe_card, fg_color="transparent", height=170)
        recipe_scroll.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        existing_recipe = {r.get("inventory_id"): r.get("qty") for r in (item.get("recipe", []) if item else [])}
        recipe_saved_state = {inv_id: (True, str(qty)) for inv_id, qty in existing_recipe.items()}
        inv_recipe_vars = {}
        recipe_items_frame = ctk.CTkFrame(recipe_scroll, fg_color="transparent")
        recipe_items_frame.pack(fill="both", expand=True)

        def rebuild_recipe_rows():
            query = (self.recipe_search_var.get() or "").strip().lower()
            for inv_id, (use_var, qty_e) in list(inv_recipe_vars.items()):
                try:
                    recipe_saved_state[inv_id] = (use_var.get(), qty_e.get().strip())
                except Exception:
                    recipe_saved_state[inv_id] = (use_var.get(), "")
            for child in recipe_items_frame.winfo_children():
                child.destroy()
            inv_recipe_vars.clear()
            hdr_row = ctk.CTkFrame(recipe_items_frame, fg_color="transparent")
            hdr_row.pack(fill="x", pady=(0, 6))
            make_label(hdr_row, "Select inventory items and set quantity used", "small", COLORS["text_muted"]).pack(side="left")
            make_label(hdr_row, "Qty", "small", COLORS["text_muted"]).pack(side="right")
            for inv in self.app.data.get("inventory", []):
                inv_id = inv.get("id")
                if inv_id is None:
                    continue
                inv_name = (inv.get("name") or "").strip()
                if inv_name.lower() in {"small cups", "medium cups", "large cups"}:
                    continue
                if query and query not in inv_name.lower():
                    continue
                rowf = ctk.CTkFrame(recipe_items_frame, fg_color="transparent")
                rowf.pack(fill="x", pady=3)

                prev_use, prev_qty = recipe_saved_state.get(inv_id, (inv_id in existing_recipe, ""))
                use_var = ctk.BooleanVar(value=prev_use)
                qty_e = make_entry(rowf, "0", 90)
                qty = prev_qty or (str(existing_recipe.get(inv_id)) if existing_recipe.get(inv_id) is not None else "")
                if qty:
                    qty_e.insert(0, qty)

                ctk.CTkCheckBox(rowf,
                                text=f"{inv_name}  ({inv.get('unit','')})",
                                variable=use_var,
                                fg_color=COLORS["accent"],
                                hover_color=COLORS["accent2"],
                                text_color=COLORS["text_secondary"]).pack(side="left")
                qty_e.pack(side="right")
                inv_recipe_vars[inv_id] = (use_var, qty_e)

        recipe_search.bind("<KeyRelease>", lambda e: rebuild_recipe_rows())
        rebuild_recipe_rows()

        def save():
            name = name_e.get().strip()
            if not name:
                show_error(dlg, "Error", "Name required.")
                return
            prices = {}
            for size, e in price_entries.items():
                success, price, error = validate_numeric_input(e.get(), f"{size} price", allow_zero=False, max_value=100000, is_price=True)
                if not success:
                    show_error(dlg, "Error", error)
                    return
                prices[size] = int(price)

            recipe = []
            for inv_id, (use_var, qty_e) in inv_recipe_vars.items():
                if not use_var.get():
                    continue
                success, qty, error = validate_numeric_input(qty_e.get(), "Consumption quantity", allow_zero=False, max_value=1000000, is_price=False)
                if not success:
                    show_error(dlg, "Error", error)
                    return
                recipe.append({"inventory_id": inv_id, "qty": qty})
            if item:
                item["name"] = name
                item["category"] = cat_var.get()
                item["prices"] = prices
                item["recipe"] = recipe
                item["image_path"] = photo_path_var["path"]
                log_activity(self.app, "Edit Menu Item", f"{name} ({cat_var.get()})")
            else:
                self.app.data["menu_items"].append({
                    "id": self.app.data["next_item_id"],
                    "name": name, "category": cat_var.get(),
                    "prices": prices, "available": True,
                    "recipe": recipe,
                    "image_path": photo_path_var["path"]})
                self.app.data["next_item_id"] += 1
                log_activity(self.app, "Add Menu Item", f"{name} ({cat_var.get()})")
            save_data(self.app.data)
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)

    def delete_item(self):
        if not self.app.has_permission("delete_item"):
            messagebox.showwarning("Permission Denied", "You do not have permission to delete menu items.", parent=self)
            return
        item = self.get_selected_item()
        if item and messagebox.askyesno("Confirm", f"Delete '{item['name']}'?", parent=self):
            removed_id = item["id"]
            log_activity(self.app, "Delete Menu Item", item["name"])
            self.app.data["menu_items"].remove(item)
            for order in self.app.data.get("orders", []):
                items = order.get("items", [])
                filtered_items = [i for i in items if i.get("menu_item_id") != removed_id]
                if len(filtered_items) != len(items):
                    order["items"] = filtered_items
                    order["total"] = sum(i.get("line_total", i.get("total", 0)) for i in filtered_items)
            save_data(self.app.data)
            self.refresh()

    def toggle_stock(self):
        if not self.app.has_permission("toggle_stock"):
            messagebox.showwarning("Permission Denied", "You do not have permission to update stock status.", parent=self)
            return
        item = self.get_selected_item()
        if item:
            item["available"] = not item["available"]
            log_activity(self.app, "Toggle Menu Item Stock", f"{item['name']} -> {'Available' if item['available'] else 'Out of Stock'}")
            save_data(self.app.data)
            self.refresh()

    def manage_categories(self):
        dlg = Dialog(self.app, "Manage Categories", 460, 350)
        dlg.add_header("Edit Categories")

        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24, pady=10)

        make_label(form, "Current Categories:", "small", COLORS["text_muted"]).pack(anchor="w", pady=(0, 5))
        list_frame = ctk.CTkFrame(form, fg_color=COLORS["bg_card"], corner_radius=8)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        self.cat_listbox = tk.Listbox(list_frame, bg=COLORS["bg_secondary"], 
                                       fg=COLORS["text_primary"], borderwidth=0,
                                       selectbackground=COLORS["accent"],
                                       font=FONTS["body"])
        self.cat_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.cat_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.cat_listbox.configure(yscrollcommand=scrollbar.set)
        for cat in self.app.data["categories"]:
            self.cat_listbox.insert("end", cat)

        add_frame = ctk.CTkFrame(form, fg_color="transparent")
        add_frame.pack(fill="x", pady=5)
        make_label(add_frame, "Add New:", "small", COLORS["text_muted"]).pack(side="left")

        new_cat_e = make_entry(add_frame, "Category name", 180)
        new_cat_e.pack(side="left", padx=8)

        def add_category():
            new_cat = new_cat_e.get().strip()
            if new_cat and new_cat not in self.app.data["categories"]:
                self.app.data["categories"].append(new_cat)
                self.cat_listbox.insert("end", new_cat)
                new_cat_e.delete(0, "end")
                log_activity(self.app, "Add Category", new_cat)
                save_data(self.app.data)
                self._build_category_filters()
                self.refresh()
            elif new_cat in self.app.data["categories"]:
                messagebox.showwarning("Warning", "Category already exists.", parent=dlg)
            else:
                show_error(dlg, "Error", "Please enter a category name.")

        make_button(add_frame, "+ Add", add_category, style="primary", width=70).pack(side="left")

        def delete_category():
            sel = self.cat_listbox.curselection()
            if sel:
                idx = sel[0]
                cat_name = self.app.data["categories"][idx]
                if len(self.app.data["categories"]) <= 1:
                    show_error(dlg, "Error", "Cannot delete the last category.")
                    return
                items_using = [i for i in self.app.data["menu_items"] if i["category"] == cat_name]
                prompt = f"Delete category '{cat_name}'?"
                if items_using:
                    prompt = f"Category '{cat_name}' is used by {len(items_using)} menu items. Delete anyway?"
                if not messagebox.askyesno("Confirm", prompt, parent=dlg):
                    return
                if items_using:
                    fallback = next((c for c in self.app.data["categories"] if c != cat_name), None)
                    if fallback:
                        for it in items_using:
                            it["category"] = fallback

                del self.app.data["categories"][idx]
                self.cat_listbox.delete(idx)
                if self.cat_var.get() == cat_name:
                    self.cat_var.set("All")
                log_activity(self.app, "Delete Category", cat_name)
                save_data(self.app.data)
                self._build_category_filters()
                self.refresh()
            else:
                messagebox.showwarning("Select", "Please select a category to delete.", parent=dlg)

        make_button(add_frame, "🗑 Delete Selected", delete_category, style="danger", width=160).pack(side="right", padx=(8, 0))

        dlg.add_buttons(lambda: None, dlg.destroy)

    def add_topping_dialog(self):
        self._topping_dialog()

    def edit_topping_dialog(self):
        topping = self.get_selected_topping()
        if topping:
            self._topping_dialog(topping)

    def _topping_dialog(self, topping=None):
        dlg = Dialog(self.app, "Add Topping" if not topping else "Edit Topping", 380, 320)
        dlg.add_header("Add Topping" if not topping else "Edit Topping")
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24)

        make_label(form, "Name", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        name_e = make_entry(form, "Topping name", 300)
        name_e.pack(anchor="w")
        name_e.bind("<Return>", lambda e: price_e.focus())

        make_label(form, "Price (₱)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        price_e = make_entry(form, "0", 120)
        price_e.pack(anchor="w")
        price_e.bind("<Return>", lambda e: form.focus())

        make_label(form, "Available", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        avail_var = ctk.BooleanVar(value=(topping["available"] if topping else True))
        ctk.CTkSwitch(form, text="In stock", variable=avail_var,
                      fg_color=COLORS["accent"], progress_color=COLORS["accent2"],
                      text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 6))

        if topping:
            name_e.insert(0, topping.get("name", ""))
            price_e.insert(0, str(topping.get("price", 0)))

        def save():
            name = name_e.get().strip()
            if not name:
                show_error(dlg, "Error", "Name required.")
                return
            success, price, error = validate_numeric_input(price_e.get(), "Price", allow_zero=False, max_value=100000, is_price=True)
            if not success:
                show_error(dlg, "Error", error)
                return
            price = int(price)

            if topping:
                topping["name"] = name
                topping["price"] = price
                topping["available"] = bool(avail_var.get())
                log_activity(self.app, "Edit Topping", f"{name} (₱{price})")
            else:
                self.app.data["toppings"].append({
                    "id": self.app.data["next_topping_id"],
                    "name": name,
                    "price": price,
                    "available": bool(avail_var.get()),
                })
                self.app.data["next_topping_id"] += 1
                log_activity(self.app, "Add Topping", f"{name} (₱{price})")

            save_data(self.app.data)
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)

    def delete_topping(self):
        topping = self.get_selected_topping()
        if not topping:
            return
        if messagebox.askyesno("Confirm", f"Delete topping '{topping['name']}'?", parent=self):
            log_activity(self.app, "Delete Topping", topping["name"])
            self.app.data["toppings"].remove(topping)
            save_data(self.app.data)
            self.refresh()

    def toggle_topping(self):
        topping = self.get_selected_topping()
        if topping:
            topping["available"] = not topping.get("available", True)
            log_activity(self.app, "Toggle Topping Availability", f"{topping['name']} -> {'Yes' if topping['available'] else 'No'}")
            save_data(self.app.data)
            self.refresh()


class POSSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.cart = []
        self.active_promo = None
        self.build()

    def build(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left = make_card(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        make_label(left, "🧋  Select Item", "subheading").grid(row=0, column=0, padx=16, pady=12, sticky="w")

        self.cat_frame = ctk.CTkFrame(left, fg_color=COLORS["bg_secondary"], corner_radius=8)
        self.cat_frame.grid(row=0, column=0, padx=16, sticky="e")

        self.selected_cat = ctk.StringVar(value="All")
        self.pos_search_var = ctk.StringVar(value="")
        cats = ["All"] + self.app.data["categories"]
        for cat in cats:
            ctk.CTkRadioButton(self.cat_frame, text=cat, variable=self.selected_cat,
                               value=cat, command=self.refresh_menu,
                               text_color=COLORS["text_secondary"],
                               fg_color=COLORS["accent"],
                               hover_color=COLORS["accent2"]).pack(side="left", padx=8, pady=4)

        search_row = ctk.CTkFrame(left, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        search_wrap = ctk.CTkFrame(search_row, fg_color="transparent")
        search_wrap.pack(anchor="w")
        make_label(search_wrap, "Search", "small", COLORS["text_muted"]).pack(side="left", padx=(0, 10))
        pos_search = make_entry(search_wrap, "Search menu…", 260, textvariable=self.pos_search_var)
        pos_search.pack(side="left")
        pos_search.bind("<KeyRelease>", lambda e: self.refresh_menu())

        self.menu_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.menu_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        self.menu_scroll.grid_columnconfigure((0, 1, 2), weight=1)
        self.refresh_menu()

        right = make_card(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        make_label(right, "🛒  Order Cart", "subheading").grid(row=0, column=0, padx=16, pady=12, sticky="w")

        cart_frame = ctk.CTkFrame(right, fg_color=COLORS["bg_secondary"], corner_radius=8)
        cart_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        cart_frame.grid_columnconfigure(0, weight=1)
        cart_frame.grid_rowconfigure(0, weight=1)

        self.cart_scroll = ctk.CTkScrollableFrame(cart_frame, fg_color="transparent")
        self.cart_scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.cart_scroll.grid_columnconfigure(0, weight=1)

        summary = ctk.CTkFrame(right, fg_color=COLORS["bg_secondary"], corner_radius=8)
        summary.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

        sf = ctk.CTkFrame(summary, fg_color="transparent")
        sf.pack(fill="x", padx=12, pady=8)

        self.promo_entry = make_entry(sf, "Promo code", 140)
        self.promo_entry.pack(side="left", padx=(0, 6))
        make_button(sf, "Apply", self.apply_promo, width=80).pack(side="left")
        self.promo_lbl = make_label(sf, "", "small", COLORS["success"])
        self.promo_lbl.pack(side="left", padx=8)

        totals = ctk.CTkFrame(summary, fg_color="transparent")
        totals.pack(fill="x", padx=12)
        totals.grid_columnconfigure(1, weight=1)

        self.subtotal_lbl = make_label(totals, "Subtotal: ₱0.00", "body")
        self.subtotal_lbl.grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        self.discount_lbl = make_label(totals, "", "body", COLORS["success"])
        self.discount_lbl.grid(row=1, column=0, columnspan=2, sticky="w")
        self.total_lbl = ctk.CTkLabel(totals, text="TOTAL: ₱0.00",
                                       font=("Georgia", 18, "bold"),
                                       text_color=COLORS["accent"])
        self.total_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)

        otf = ctk.CTkFrame(right, fg_color="transparent")
        otf.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 6))
        make_label(otf, "Order Type: ", "small", COLORS["text_muted"]).pack(side="left")
        self.order_type_var = ctk.StringVar(value="Dine-in")
        for ot in ["Dine-in", "Takeout", "Delivery"]:
            ctk.CTkRadioButton(otf, text=ot, variable=self.order_type_var, value=ot,
                               text_color=COLORS["text_secondary"],
                               fg_color=COLORS["accent"],
                               hover_color=COLORS["accent2"]).pack(side="left", padx=8)

        pmf = ctk.CTkFrame(right, fg_color="transparent")
        pmf.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 6))
        make_label(pmf, "Payment: ", "small", COLORS["text_muted"]).pack(side="left")
        self.payment_var = ctk.StringVar(value="Cash")
        for pm in ["Cash", "GCash", "Card"]:
            ctk.CTkRadioButton(pmf, text=pm, variable=self.payment_var, value=pm,
                               text_color=COLORS["text_secondary"],
                               fg_color=COLORS["accent"],
                               hover_color=COLORS["accent2"]).pack(side="left", padx=8)

        btn_f = ctk.CTkFrame(right, fg_color="transparent")
        btn_f.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 10))
        make_button(btn_f, "🗑 Clear Cart", self.clear_cart, style="danger", width=130).pack(side="left", padx=4)
        make_button(btn_f, "✔ Checkout", self.checkout, style="success", width=150).pack(side="right", padx=4)

    def refresh_menu(self):
        for w in self.menu_scroll.winfo_children():
            w.destroy()
        cat = self.selected_cat.get()
        q = (self.pos_search_var.get() or "").strip().lower()
        items = [i for i in self.app.data["menu_items"]
                 if i["available"]
                 and (cat == "All" or i["category"] == cat)
                 and (not q or q in i.get("name", "").lower())]
        for idx, item in enumerate(items):
            r, c = divmod(idx, 3)
            item_frame = ctk.CTkFrame(
                self.menu_scroll, fg_color=COLORS["bg_secondary"],
                corner_radius=10, border_width=1, border_color=COLORS["border"])
            item_frame.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            item_frame.grid_propagate(False)

            img = load_image(item.get("image_path", ""), size=(160, 100))
            if img:
                image_label = ctk.CTkLabel(item_frame, image=img, text="")
                image_label.image = img
                image_label.pack(padx=8, pady=(8, 4))
            else:
                no_img = ctk.CTkLabel(item_frame, text="No image",
                                      font=FONTS["small"], text_color=COLORS["text_secondary"],
                                      fg_color=COLORS["bg_card"], corner_radius=10,
                                      width=160, height=100)
                no_img.pack(padx=8, pady=(8, 4))

            name_label = ctk.CTkLabel(
                item_frame, text=item['name'],
                font=FONTS["small"], text_color=COLORS["text_primary"],
                wraplength=160)
            name_label.pack(padx=8, pady=(4, 4), anchor="w", fill="x")

            prices = list(item['prices'].values())
            medium_price = prices[1] if len(prices) > 1 else (prices[0] if prices else 0)
            price_label = ctk.CTkLabel(
                item_frame, text=f"₱{medium_price}",
                font=("Helvetica", 11, "bold"), text_color=COLORS["accent"])
            price_label.pack(padx=8, pady=(0, 8), anchor="w")

            add_btn = ctk.CTkButton(
                item_frame, text="🛒 Add to Cart",
                command=lambda i=item: self.add_to_cart(i),
                fg_color=COLORS["accent"], hover_color=COLORS["accent2"],
                text_color=COLORS["text_primary"], corner_radius=8,
                font=FONTS["small"], height=32)
            add_btn.pack(padx=8, pady=(0, 8), fill="x")

        for i in range(3):
            self.menu_scroll.grid_columnconfigure(i, weight=1)

    def add_to_cart(self, item):
        dlg = Dialog(self.app, "Customize Order", 420, 520)
        dlg.add_header(item["name"])

        form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        make_label(form, "Size", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        size_var = ctk.StringVar(value="Medium")
        sf = ctk.CTkFrame(form, fg_color="transparent")
        sf.pack(anchor="w")
        for s in ["Small", "Medium", "Large"]:
            p = item["prices"].get(s, 0)
            ctk.CTkRadioButton(sf, text=f"{s} (₱{p})", variable=size_var, value=s,
                               text_color=COLORS["text_secondary"],
                               fg_color=COLORS["accent"],
                               hover_color=COLORS["accent2"]).pack(side="left", padx=6)

        make_label(form, "Sugar Level", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        sugar_var = ctk.StringVar(value="100%")
        sugar_dd = ctk.CTkOptionMenu(form, variable=sugar_var,
                                     values=self.app.data["sugar_levels"],
                                     fg_color=COLORS["bg_secondary"],
                                     button_color=COLORS["accent"], width=180)
        sugar_dd.pack(anchor="w")

        make_label(form, "Ice Level", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        ice_var = ctk.StringVar(value="Regular Ice")
        ice_dd = ctk.CTkOptionMenu(form, variable=ice_var,
                                   values=self.app.data["ice_levels"],
                                   fg_color=COLORS["bg_secondary"],
                                   button_color=COLORS["accent"], width=180)
        ice_dd.pack(anchor="w")

        make_label(form, "Toppings (+)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        top_frame = ctk.CTkFrame(form, fg_color="transparent")
        top_frame.pack(anchor="w")
        top_vars = {}
        for t in self.app.data["toppings"]:
            if t["available"]:
                v = ctk.BooleanVar()
                top_vars[t["id"]] = (v, t)
                ctk.CTkCheckBox(top_frame, text=f"{t['name']} +₱{t['price']}",
                                variable=v, fg_color=COLORS["accent"],
                                hover_color=COLORS["accent2"],
                                text_color=COLORS["text_secondary"]).pack(anchor="w")

        make_label(form, "Quantity", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        qty_var = ctk.IntVar(value=1)
        qf = ctk.CTkFrame(form, fg_color="transparent")
        qf.pack(anchor="w")
        make_button(qf, "-", lambda: qty_var.set(max(1, qty_var.get() - 1)), style="secondary", width=36).pack(side="left")
        qty_lbl = ctk.CTkLabel(qf, textvariable=qty_var, font=FONTS["subheading"],
                               text_color=COLORS["text_primary"], width=40)
        qty_lbl.pack(side="left")
        make_button(qf, "+", lambda: qty_var.set(qty_var.get() + 1), style="secondary", width=36).pack(side="left")

        def add():
            size = size_var.get()
            price = item["prices"].get(size, 0)
            selected_tops = [(v, t) for _, (v, t) in top_vars.items() if v.get()]
            top_total = sum(t["price"] for _, t in selected_tops)
            unit_price = price + top_total
            qty = qty_var.get()
            self.cart.append({
                "item": item,
                "size": size,
                "sugar": sugar_var.get(),
                "ice": ice_var.get(),
                "toppings": [t for _, t in selected_tops],
                "quantity": qty,
                "unit_price": unit_price,
                "total": unit_price * qty,
            })
            tops_str = ", ".join(t["name"] for _, t in selected_tops) if selected_tops else "No toppings"
            log_activity(self.app, "Add to Cart", 
                        f"Item: {item['name']} ({size}) x{qty} | Toppings: {tops_str} | Total: ₱{unit_price * qty}")
            self.refresh_cart()
            dlg.destroy()

        dlg.add_buttons(add, dlg.destroy, save_text="Place Order", save_style="success")

    def refresh_cart(self):
        for w in self.cart_scroll.winfo_children():
            w.destroy()
        for idx, entry in enumerate(self.cart):
            f = ctk.CTkFrame(self.cart_scroll, fg_color=COLORS["bg_card"],
                             corner_radius=8, border_width=1, border_color=COLORS["border"])
            f.pack(fill="x", pady=3, padx=2)
            f.grid_columnconfigure(0, weight=1)
            tops_str = ", ".join(t["name"] for t in entry["toppings"]) or "No toppings"
            desc = f"{entry['item']['name']} ({entry['size']}) x{entry['quantity']}"
            make_label(f, desc, "small").grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))
            make_label(f, f"  {entry['sugar']} | {entry['ice']} | {tops_str}",
                       "small", COLORS["text_muted"]).grid(row=1, column=0, sticky="w", padx=8)
            make_label(f, f"₱{entry['total']:.0f}", "small",
                       COLORS["accent"]).grid(row=0, column=1, sticky="e", padx=8)
            i = idx
            ctk.CTkButton(f, text="✕", width=28, height=24, corner_radius=6,
                          fg_color=COLORS["danger"], hover_color="#C62828",
                          command=lambda ii=i: self.remove_cart_item(ii)).grid(row=0, column=2, padx=6)

        self.update_totals()

    def remove_cart_item(self, idx):
        if 0 <= idx < len(self.cart):
            removed = self.cart.pop(idx)
            log_activity(self.app, "Remove from Cart", f"Removed: {removed['item']['name']} ({removed['size']}) x{removed['quantity']}")
            self.refresh_cart()

    def clear_cart(self):
        if self.cart:
            log_activity(self.app, "Clear Cart", f"Cleared {len(self.cart)} items from cart")
        self.cart.clear()
        self.active_promo = None
        self.promo_lbl.configure(text="")
        self.promo_entry.delete(0, "end")
        self.refresh_cart()

    def apply_promo(self):
        code = self.promo_entry.get().strip().upper()
        promo = next((p for p in self.app.data["promos"]
                      if p["code"].upper() == code and p["active"]), None)
        if promo:
            self.active_promo = promo
            self.promo_lbl.configure(text=f"✓ {promo['description']}")
            log_activity(self.app, "Apply Promo", f"Applied promo code: {code} ({promo['description']})")
            self.update_totals()
        else:
            self.active_promo = None
            self.promo_lbl.configure(text="✗ Invalid code")
            if code:
                log_activity(self.app, "Invalid Promo", f"Attempted invalid promo code: {code}")
            self.update_totals()

    def update_totals(self):
        subtotal = sum(e["total"] for e in self.cart)
        discount = 0
        if self.active_promo:
            if self.active_promo["type"] == "percent":
                discount = subtotal * self.active_promo["value"] / 100
        total = subtotal - discount
        self.subtotal_lbl.configure(text=f"Subtotal: ₱{subtotal:.2f}")
        if discount:
            self.discount_lbl.configure(text=f"Discount: -₱{discount:.2f}")
        else:
            self.discount_lbl.configure(text="")
        self.total_lbl.configure(text=f"TOTAL: ₱{total:.2f}")

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Add items to the cart first.", parent=self)
            return

        ok, msg = self._validate_inventory_for_cart()
        if not ok:
            log_error(self.app, "Insufficient Inventory", msg, details="Checkout blocked due to low stock.")
            show_error(self, "Insufficient Inventory", msg, details="Checkout blocked due to low stock.")
            return

        subtotal = sum(e["total"] for e in self.cart)
        discount = 0
        if self.active_promo and self.active_promo["type"] == "percent":
            discount = subtotal * self.active_promo["value"] / 100
        total = subtotal - discount
        payment = self.payment_var.get()
        order_type = self.order_type_var.get()

        delivery_info = None
        if order_type == "Delivery":
            self._collect_delivery_info(total, subtotal, discount, payment, order_type)
        else:
            self._process_checkout(total, subtotal, discount, payment, order_type, None)

    def _process_checkout(self, total, subtotal, discount, payment, order_type, delivery_info=None):
        if payment == "Cash":
            cash_dlg = Dialog(self.app, "Cash Payment", 320, 220)
            cash_dlg.add_header("Cash Tendered")
            make_label(cash_dlg, f"Total: ₱{total:.2f}", "subheading").pack(pady=4)
            cash_e = make_entry(cash_dlg, "Enter cash amount", 220)
            cash_e.pack(pady=8)
            cash_e.insert(0, str(math.ceil(total)))

            def confirm_cash():
                try:
                    cash = float(cash_e.get())
                except ValueError:
                    show_error(cash_dlg, "Error", "Invalid amount.")
                    return
                if cash < total:
                    show_error(cash_dlg, "Error", "Insufficient cash.")
                    return
                change = cash - total
                self._finalize_order(total, subtotal, discount, payment, change, order_type, delivery_info=delivery_info)
                cash_dlg.destroy()

            cash_e.bind("<Return>", lambda e: confirm_cash())
            make_button(cash_dlg, "Confirm", confirm_cash, width=200).pack(pady=8)
        elif payment == "GCash":
            self._process_gcash_checkout(total, subtotal, discount, order_type, delivery_info)
        else:
            self._finalize_order(total, subtotal, discount, payment, 0, order_type, delivery_info=delivery_info)

    def _collect_delivery_info(self, total, subtotal, discount, payment, order_type):
        dlg = Dialog(self.app, "Delivery Information", 420, 340)
        dlg.add_header("Delivery Details")
        make_label(dlg, "Customer Name", "small", COLORS["text_muted"]).pack(anchor="w", padx=20, pady=(12, 0))
        name_e = make_entry(dlg, "Enter customer name", 360)
        name_e.pack(padx=20, pady=(0, 8))

        make_label(dlg, "Delivery Address", "small", COLORS["text_muted"]).pack(anchor="w", padx=20, pady=(8, 0))
        address_e = make_entry(dlg, "Enter delivery address", 360)
        address_e.pack(padx=20, pady=(0, 8))

        make_label(dlg, "Contact Number", "small", COLORS["text_muted"]).pack(anchor="w", padx=20, pady=(8, 0))
        phone_e = make_entry(dlg, "Enter contact number", 360)
        phone_e.pack(padx=20, pady=(0, 12))

        def confirm_delivery():
            name = name_e.get().strip()
            address = address_e.get().strip()
            phone = phone_e.get().strip()
            if not name:
                show_error(dlg, "Error", "Customer name is required.")
                return
            if not address:
                show_error(dlg, "Error", "Delivery address is required.")
                return
            if not phone:
                show_error(dlg, "Error", "Contact number is required.")
                return
            delivery_info = {
                "customer_name": name,
                "delivery_address": address,
                "delivery_phone": phone,
            }
            dlg.destroy()
            self._process_checkout(total, subtotal, discount, payment, order_type, delivery_info)

        make_button(dlg, "Continue to Payment", confirm_delivery, style="success", width=360).pack(pady=12)

    def _process_gcash_checkout(self, total, subtotal, discount, order_type, delivery_info=None):
        self.gcash_qr_data = None
        dlg = Dialog(self.app, "GCash Payment", 420, 320)
        dlg.add_header("GCash QR Payment")
        make_label(dlg, f"Total: ₱{total:.2f}", "subheading").pack(pady=4)
        self.gcash_scan_status = make_label(dlg, "Scan a GCash QR code to proceed.", "small", COLORS["text_muted"])
        self.gcash_scan_status.pack(pady=(0, 8))
        self.gcash_qr_label = make_label(dlg, "No QR scanned yet.", "small", COLORS["text_secondary"])
        self.gcash_qr_label.pack(pady=(0, 12))

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(pady=4)
        make_button(btn_frame, "Scan via Camera", lambda: self._scan_gcash_qr(dlg), width=160).pack(side="left", padx=4)
        make_button(btn_frame, "Load QR Image", lambda: self._load_gcash_qr_image(dlg), width=160).pack(side="left", padx=4)

        def confirm_gcash():
            if not getattr(self, "gcash_qr_data", None):
                show_error(dlg, "No QR Scanned", "Please scan or load a GCash QR code before confirming payment.")
                return
            self._finalize_order(total, subtotal, discount, "GCash", 0, order_type, gcash_reference=self.gcash_qr_data)
            dlg.destroy()

        make_button(dlg, "Confirm Payment", confirm_gcash, style="success", width=320).pack(pady=12)

    def _scan_gcash_qr(self, parent):
        if cv2 is None:
            show_error(parent, "Scan Error", "OpenCV is not installed. Use Load QR Image instead.")
            return

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else 0)
        if not cap.isOpened():
            show_error(parent, "Camera Error", "Unable to open camera. Use Load QR Image instead.")
            return

        detector = cv2.QRCodeDetector()
        messagebox.showinfo("GCash QR Scan", "A camera window will open. Present the QR code to the camera and press 'q' to cancel.", parent=parent)
        scanned = None
        start_time = datetime.now()

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            data, points, _ = detector.detectAndDecode(frame)
            if points is not None:
                points = points.astype(int).reshape(-1, 2)
                for i in range(len(points)):
                    pt1 = tuple(points[i])
                    pt2 = tuple(points[(i + 1) % len(points)])
                    cv2.line(frame, pt1, pt2, (0, 255, 0), 2)
            cv2.imshow("GCash QR Scan", frame)
            if data:
                scanned = data.strip()
                break
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if (datetime.now() - start_time).seconds > 30:
                break

        cap.release()
        cv2.destroyAllWindows()

        if scanned:
            self.gcash_qr_data = scanned
            self.gcash_scan_status.configure(text="QR successfully scanned.", text_color=COLORS["success"])
            self.gcash_qr_label.configure(text=f"Data: {scanned}", text_color=COLORS["text_secondary"])
        else:
            show_error(parent, "Scan Failed", "No QR code was detected. Try again or use Load QR Image.")

    def _load_gcash_qr_image(self, parent):
        path = filedialog.askopenfilename(parent=parent, title="Select QR Code Image",
                                          filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")])
        if not path:
            return
        data = self._decode_qr_from_image(path)
        if not data:
            show_error(parent, "Decode Error", "No QR code was detected in the selected image.")
            return
        self.gcash_qr_data = data.strip()
        self.gcash_scan_status.configure(text="QR successfully loaded.", text_color=COLORS["success"])
        self.gcash_qr_label.configure(text=f"Data: {self.gcash_qr_data}", text_color=COLORS["text_secondary"])

    def _decode_qr_from_image(self, image_path):
        if cv2 is not None:
            try:
                image = cv2.imread(image_path)
                if image is None:
                    return None
                detector = cv2.QRCodeDetector()
                data, _, _ = detector.detectAndDecode(image)
                if data:
                    return data
            except Exception:
                pass

        try:
            pyzbar_mod = __import__("pyzbar.pyzbar", fromlist=["decode"])
            pyzbar_decode = pyzbar_mod.decode
        except ImportError:
            pyzbar_decode = None

        if pyzbar_decode is not None and Image is not None:
            try:
                img = Image.open(image_path)
                decoded = pyzbar_decode(img)
                if decoded:
                    return decoded[0].data.decode("utf-8")
            except Exception:
                pass

        return None

    def _finalize_order(self, total, subtotal, discount, payment, change, order_type, delivery_info=None, gcash_reference=None):
        self._consume_inventory_for_cart()

        now = datetime.now()
        order = {
            "id": self.app.data["next_order_id"],
            "order_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "order_type": order_type,
            "customer_name": delivery_info.get("customer_name", "") if delivery_info else "",
            "delivery_address": delivery_info.get("delivery_address", "") if delivery_info else "",
            "delivery_phone": delivery_info.get("delivery_phone", "") if delivery_info else "",
            "created_by": self.app.current_user["name"] if getattr(self.app, "current_user", None) else "",
            "items": [
                {
                    "menu_item_id": e["item"]["id"],
                    "name": e["item"]["name"],
                    "size": e["size"],
                    "sugar": e["sugar"],
                    "ice": e["ice"],
                    "toppings": [
                        {"topping_id": t["id"], "name": t["name"], "quantity": 1, "price": t["price"]}
                        for t in e["toppings"]
                    ],
                    "quantity": e["quantity"],
                    "unit_price": e["unit_price"],
                    "line_total": e["total"],
                    "total": e["total"],
                } for e in self.cart
            ],
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "payment": payment,
            "change": change,
            "promo_code": self.active_promo["code"] if self.active_promo else None,
        }
        self.app.data["orders"].append(order)
        self.app.data["next_order_id"] += 1
        save_data(self.app.data)
        if "dashboard" in self.app.sections:
            self.app.sections["dashboard"].mark_dirty()

        promo_str = f" (Promo: {self.active_promo['code']})" if self.active_promo else ""
        log_activity(self.app, "Checkout", 
                    f"Order #{order['id']} | Type: {order_type} | Payment: {payment} | Amount: ₱{total:.2f}{promo_str} | Items: {len(order['items'])}")

        shop_name = self.app.data.get("settings", {}).get("shop_name", "Brewster's Cup")
        tagline = self.app.data.get("settings", {}).get("tagline", "")
        receipt = (
            f"{shop_name:^38}\n"
            f"{tagline:^38}\n"
            f"{'─' * 38}\n"
            f"Order #: {order['id']}\n"
            f"Date: {order['date']}  Time: {order['time']}\n"
            f"Type: {order_type}\n"
            f"{'─' * 38}\n"
        )
        for item in order["items"]:
            tops = ", ".join(t["name"] for t in item["toppings"]) or "No toppings"
            receipt += f"  {item['name']} ({item['size']}) x{item['quantity']}\n"
            receipt += f"    {item['sugar']} | {item['ice']}\n"
            receipt += f"    {tops}\n"
            receipt += f"    ₱{item['total']:.2f}\n"
        receipt += f"{'─' * 38}\n"
        receipt += f"Subtotal:   ₱{subtotal:.2f}\n"
        if discount:
            receipt += f"Discount:  -₱{discount:.2f}\n"
        receipt += f"TOTAL:      ₱{total:.2f}\n"
        if order.get("customer_name"):
            receipt += f"Customer:   {order['customer_name']}\n"
        if order.get("delivery_address"):
            receipt += f"Address:    {order['delivery_address']}\n"
        if order.get("delivery_phone"):
            receipt += f"Phone:      {order['delivery_phone']}\n"
        receipt += f"Payment:    {payment}\n"
        if payment == "GCash" and order.get("gcash_reference"):
            receipt += f"GCash QR:   {order['gcash_reference']}\n"
        if payment == "Cash":
            receipt += f"Change:     ₱{change:.2f}\n"
        receipt += f"{'─' * 38}\n"
        receipt += f"{'Thank you! Come again!':^38}\n"

        rdlg = ctk.CTkToplevel(self.app)
        rdlg.title("Receipt")
        rdlg.geometry("420x540")
        rdlg.configure(fg_color=COLORS["bg_primary"])
        rdlg.grab_set()
        make_label(rdlg, "Order Receipt", "heading", COLORS["accent"]).pack(pady=12)
        tb = ctk.CTkTextbox(rdlg, font=FONTS["mono"], fg_color=COLORS["bg_card"],
                            text_color=COLORS["text_primary"])
        tb.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        tb.insert("1.0", receipt)
        tb.configure(state="disabled")

        bf = ctk.CTkFrame(rdlg, fg_color="transparent")
        bf.pack(fill="x", padx=16, pady=8)

        def print_receipt():
            try:
                file_path = filedialog.asksaveasfilename(
                    title="Save Receipt as CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv")],
                    initialfile=f"receipt_{order['id']}.csv",
                    parent=rdlg,
                )
                if not file_path:
                    return
                import csv
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Order Receipt"])
                    writer.writerow(["Shop Name", shop_name])
                    writer.writerow(["Tagline", tagline])
                    writer.writerow([])
                    writer.writerow(["Order #", order["id"]])
                    writer.writerow(["Date", order.get("date", "")])
                    writer.writerow(["Time", order.get("time", "")])
                    writer.writerow(["Type", order.get("order_type", "")])
                    writer.writerow(["Payment", order.get("payment", "")])
                    writer.writerow(["Customer", order.get("customer_name", "")])
                    writer.writerow(["Address", order.get("delivery_address", "")])
                    writer.writerow(["Phone", order.get("delivery_phone", "")])
                    if order.get("payment") == "Cash":
                        writer.writerow(["Change", f"{float(order.get('change', 0)):.2f}"])
                    if order.get("payment") == "GCash" and order.get("gcash_reference"):
                        writer.writerow(["GCash QR", order.get("gcash_reference")])
                    writer.writerow([])
                    writer.writerow(["Item Name", "Size", "Quantity", "Sugar", "Ice", "Toppings", "Unit Price", "Line Total"])
                    for item in order.get("items", []):
                        writer.writerow([
                            item.get("name", ""),
                            item.get("size", ""),
                            item.get("quantity", 1),
                            item.get("sugar", ""),
                            item.get("ice", ""),
                            ", ".join(t.get("name", "") for t in item.get("toppings", []) if t.get("name")),
                            f"{float(item.get('unit_price', 0)):.2f}",
                            f"{float(item.get('total', item.get('line_total', 0))):.2f}",
                        ])
                    writer.writerow([])
                    writer.writerow(["Subtotal", f"{float(order.get('subtotal', 0)):.2f}"])
                    writer.writerow(["Discount", f"{float(order.get('discount', 0)):.2f}"])
                    writer.writerow(["Total", f"{float(order.get('total', 0)):.2f}"])
                messagebox.showinfo("Saved", f"Receipt saved to CSV:\n{file_path}", parent=rdlg)
            except Exception as e:
                show_error(rdlg, "Save Error", f"Failed to save receipt to CSV: {str(e)}")

        make_button(bf, "🖨 Print", print_receipt, style="primary", width=90).pack(side="left", padx=4)
        make_button(bf, "📋 Copy", lambda: rdlg.clipboard_clear() or rdlg.clipboard_append(receipt), 
                    style="secondary", width=90).pack(side="left", padx=4)
        make_button(bf, "✕ Close", rdlg.destroy, style="outline", width=90).pack(side="right", padx=4)

        self.clear_cart()

    def _cart_inventory_requirements(self):
        req = {}
        for e in self.cart:
            item = e.get("item", {})
            qty_orders = int(e.get("quantity", 0) or 0)
            size = (e.get("size") or "").strip()
            if qty_orders > 0:
                cup_inv = self._cup_inventory_item_for_size(size)
                if cup_inv:
                    req[cup_inv["id"]] = req.get(cup_inv["id"], 0) + (1 * qty_orders)
            for r in item.get("recipe", []) or []:
                inv_id = r.get("inventory_id")
                per = r.get("qty", 0)
                try:
                    per = float(per)
                except Exception:
                    per = 0
                if not inv_id or per <= 0 or qty_orders <= 0:
                    continue
                req[inv_id] = req.get(inv_id, 0) + per * qty_orders
        return req

    def _cup_inventory_item_for_size(self, size):
        name_map = {
            "Small": "Small Cups",
            "Medium": "Medium Cups",
            "Large": "Large Cups",
        }
        target = name_map.get(size)
        if not target:
            return None
        return next((i for i in self.app.data.get("inventory", [])
                     if (i.get("name") or "").strip().lower() == target.lower()), None)

    def _validate_inventory_for_cart(self):
        req = self._cart_inventory_requirements()
        if not req:
            return True, ""

        problems = []
        for inv_id, needed in req.items():
            inv = next((i for i in self.app.data.get("inventory", []) if i.get("id") == inv_id), None)
            if not inv:
                problems.append(f"- Missing inventory item (ID {inv_id})")
                continue
            available = float(inv.get("quantity", 0) or 0)
            if available < needed:
                problems.append(f"- {inv.get('name','Item')}: need {needed:g} {inv.get('unit','')}, have {available:g} {inv.get('unit','')}")

        if problems:
            return False, "Not enough stock to complete this order:\n\n" + "\n".join(problems)
        return True, ""

    def _consume_inventory_for_cart(self):
        req = self._cart_inventory_requirements()
        if not req:
            return

        for inv_id, needed in req.items():
            inv = next((i for i in self.app.data.get("inventory", []) if i.get("id") == inv_id), None)
            if not inv:
                continue
            inv["quantity"] = float(inv.get("quantity", 0) or 0) - needed

        save_data(self.app.data)


class InventorySection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        make_label(hdr, "Inventory Management", "heading").pack(side="left")
        self.inv_search_var = ctk.StringVar(value="")
        hdr_right = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_right.pack(side="right")
        make_button(hdr_right, "+ Add Item", self.add_dialog, width=110).pack(side="right")
        make_button(hdr_right, "📦 Restock", self.restock_dialog, style="secondary", width=110).pack(side="right", padx=(8, 8))
        make_button(hdr_right, "🔄 Refresh", self.refresh, style="outline", width=100).pack(side="right", padx=(0, 8))
        inv_search_wrap = ctk.CTkFrame(hdr_right, fg_color="transparent")
        inv_search_wrap.pack(side="right", padx=(0, 8))
        make_label(inv_search_wrap, "Search", "small", COLORS["text_muted"]).pack(side="left", padx=(0, 8))
        inv_search = make_entry(inv_search_wrap, "Search inventory…", 220, textvariable=self.inv_search_var)
        inv_search.pack(side="left")
        inv_search.bind("<KeyRelease>", lambda e: self.refresh())

        self.alert_frame = ctk.CTkFrame(self, fg_color="#3A1515", corner_radius=8,
                                         border_width=1, border_color=COLORS["danger"])
        self.alert_lbl = make_label(self.alert_frame, "", "small", COLORS["danger"])
        self.alert_lbl.pack(padx=12, pady=6)

        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("ID", "Item", "Unit", "Quantity", "Threshold", "Cost/Unit", "Status")
        self.tree, sb = themed_table(card, cols, height=14)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.pack(fill="x", pady=8)
        make_button(acts, "✏ Edit", self.edit_dialog, style="secondary").pack(side="left", padx=4)
        make_button(acts, "🗑 Delete", self.delete_item, style="danger").pack(side="left", padx=4)
        make_button(acts, "📋 Log Wastage", self.wastage_dialog, style="outline").pack(side="left", padx=4)

        self.refresh()

    def refresh(self):
        low = []
        q = (self.inv_search_var.get() or "").strip().lower()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in self.app.data["inventory"]:
            if q and q not in item.get("name", "").lower():
                continue
            status = "✅ OK"
            if item["quantity"] <= 0:
                status = "❌ Empty"
            elif item["quantity"] <= item["threshold"]:
                status = "⚠ Low"
                low.append(item["name"])
            self.tree.insert("", "end", values=(
                item["id"], item["name"], item["unit"],
                f"{item['quantity']:.1f}", item["threshold"],
                f"₱{item['cost_per_unit']}", status))
        if low:
            self.alert_frame.pack(fill="x", pady=(0, 8))
            self.alert_lbl.configure(text="⚠ LOW STOCK: " + ", ".join(low))
        else:
            self.alert_frame.pack_forget()

    def _inv_dialog(self, item=None):
        dlg = Dialog(self.app, "Add Inventory Item" if not item else "Edit Inventory Item", 420, 450)
        dlg.add_header("Inventory Item")
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        fields = {}
        field_names = ["Name", "Unit", "Quantity", "Threshold", "Cost per Unit (₱)"]
        for idx, (lbl, ph, default) in enumerate([
            ("Name", "Item name", item["name"] if item else ""),
            ("Unit", "e.g. grams/ml/pcs", item["unit"] if item else ""),
            ("Quantity", "Current quantity", str(item["quantity"]) if item else "0"),
            ("Threshold", "Low stock alert at", str(item["threshold"]) if item else "50"),
            ("Cost per Unit (₱)", "e.g. 0.5", str(item["cost_per_unit"]) if item else "0"),
        ]):
            make_label(form, lbl, "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
            e = make_entry(form, ph, 320)
            e.insert(0, default)
            e.pack(anchor="w")
            if idx < len(field_names) - 1:
                next_field = field_names[idx + 1]
                e.bind("<Return>", lambda event, nf=next_field: fields[nf].focus())
            else:
                e.bind("<Return>", lambda event: form.focus())
            fields[lbl] = e

        def save():
            name = fields["Name"].get().strip()
            unit = fields["Unit"].get().strip()
            if not name or not unit:
                show_error(dlg, "Error", "Name and unit required.")
                return

            success, qty, error = validate_numeric_input(fields["Quantity"].get(), "Quantity", allow_zero=True, max_value=1000000, is_price=False)
            if not success:
                show_error(dlg, "Error", error)
                return

            success, thresh, error = validate_numeric_input(fields["Threshold"].get(), "Threshold", allow_zero=True, max_value=1000000, is_price=False)
            if not success:
                show_error(dlg, "Error", error)
                return

            success, cost, error = validate_numeric_input(fields["Cost per Unit (₱)"].get(), "Cost per unit", allow_zero=True, max_value=100000, is_price=True)
            if not success:
                show_error(dlg, "Error", error)
                return
            if item:
                item.update({"name": name, "unit": unit, "quantity": qty,
                             "threshold": thresh, "cost_per_unit": cost})
                log_activity(self.app, "Edit Inventory Item", name)
            else:
                self.app.data["inventory"].append({
                    "id": self.app.data["next_inventory_id"],
                    "name": name, "unit": unit, "quantity": qty,
                    "threshold": thresh, "cost_per_unit": cost})
                self.app.data["next_inventory_id"] += 1
                log_activity(self.app, "Add Inventory Item", name)
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)

    def add_dialog(self): self._inv_dialog()

    def edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an item.", parent=self)
            return
        iid = self.tree.item(sel[0])["values"][0]
        item = next((i for i in self.app.data["inventory"] if i["id"] == iid), None)
        if item:
            self._inv_dialog(item)

    def delete_item(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = self.tree.item(sel[0])["values"][0]
        item = next((i for i in self.app.data["inventory"] if i["id"] == iid), None)
        if item and messagebox.askyesno("Confirm", f"Delete '{item['name']}'?", parent=self):
            log_activity(self.app, "Delete Inventory Item", item["name"])
            self.app.data["inventory"].remove(item)
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()

    def restock_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an inventory item to restock.", parent=self)
            return
        iid = self.tree.item(sel[0])["values"][0]
        item = next((i for i in self.app.data["inventory"] if i["id"] == iid), None)
        if not item:
            return
        dlg = Dialog(self.app, "Restock Item", 340, 240)
        dlg.add_header(f"Restock: {item['name']}")
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)
        make_label(form, f"Current: {item['quantity']} {item['unit']}", "body").pack(pady=8)
        make_label(form, "Add Quantity", "small", COLORS["text_muted"]).pack(anchor="w")
        qty_e = make_entry(form, "Enter quantity to add", 260)
        qty_e.pack(anchor="w")

        def save():
            success, qty, error = validate_numeric_input(qty_e.get(), "Restock quantity", allow_zero=False, max_value=1000000, is_price=False)
            if not success:
                show_error(dlg, "Error", error)
                return
            item["quantity"] += qty
            log_activity(self.app, "Restock Inventory", f"{item['name']} +{qty} {item['unit']}")
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()
            dlg.destroy()
            messagebox.showinfo("Restocked", f"Added {qty} {item['unit']} to {item['name']}.", parent=self)

        qty_e.bind("<Return>", lambda e: save())
        dlg.add_buttons(save, dlg.destroy)

    def wastage_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an inventory item.", parent=self)
            return
        iid = self.tree.item(sel[0])["values"][0]
        item = next((i for i in self.app.data["inventory"] if i["id"] == iid), None)
        if not item:
            return
        dlg = Dialog(self.app, "Log Wastage", 340, 240)
        dlg.add_header(f"Wastage: {item['name']}")
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)
        make_label(form, f"Current: {item['quantity']} {item['unit']}", "body").pack(pady=8)
        make_label(form, "Wastage Quantity", "small", COLORS["text_muted"]).pack(anchor="w")
        qty_e = make_entry(form, "Enter wasted quantity", 260)
        qty_e.pack(anchor="w")

        def save():
            success, qty, error = validate_numeric_input(qty_e.get(), "Wastage quantity", allow_zero=False, max_value=1000000, is_price=False)
            if not success:
                show_error(dlg, "Error", error)
                return
            if qty > item["quantity"]:
                show_error(dlg, "Error", "Wastage exceeds available stock.")
                return
            item["quantity"] -= qty
            log_activity(self.app, "Inventory Wastage", f"{item['name']} -{qty} {item['unit']}")
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()
            dlg.destroy()

        qty_e.bind("<Return>", lambda e: save())
        dlg.add_buttons(save, dlg.destroy)


class AttendanceSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        make_label(self, "Employee Attendance", "heading").pack(anchor="w", pady=(0, 12))

        quick_card = make_card(self)
        quick_card.pack(fill="x", pady=(0, 16))
        make_label(quick_card, "Quick Time-In / Time-Out", "subheading").pack(padx=16, pady=(12, 8), anchor="w")
        form = ctk.CTkFrame(quick_card, fg_color="transparent")
        form.pack(fill="x", padx=16, pady=(0, 16))
        form.grid_columnconfigure(0, weight=1)

        make_label(form, "Select Employee", "small", COLORS["text_muted"]).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.emp_var = ctk.StringVar()
        emp_options = [f"{e['name']} ({e['role']})" for e in self.app.data["employees"] if e.get("active", True)]
        emp_dd = ctk.CTkOptionMenu(form, variable=self.emp_var, values=emp_options or ["No employees"],
                                   fg_color=COLORS["bg_secondary"], button_color=COLORS["accent"], width=300)
        emp_dd.grid(row=0, column=1, sticky="w", padx=(0, 8))

        bf = ctk.CTkFrame(form, fg_color="transparent")
        bf.grid(row=0, column=2, sticky="w")
        make_button(bf, "🟢 Time-In", self.time_in, style="success", width=100).pack(side="left", padx=4)
        make_button(bf, "🔴 Time-Out", self.time_out, style="danger", width=100).pack(side="left", padx=4)

        self.status_frame = make_card(self)
        self.status_frame.pack(fill="x", pady=(0, 16))
        self.status_lbl = make_label(self.status_frame, "", "body")
        self.status_lbl.pack(padx=16, pady=12)

        make_label(self, "Attendance Log", "subheading").pack(anchor="w", pady=(8, 4))
        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("Date", "Employee", "Role", "Time-In", "Time-Out", "Hours", "Status")
        self.tree, sb = themed_table(card, cols, height=14)
        for col, w in zip(cols, [100, 140, 100, 100, 100, 80, 80]):
            self.tree.column(col, width=w)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        flt = ctk.CTkFrame(self, fg_color="transparent")
        flt.pack(fill="x", pady=8)
        make_label(flt, "Filter: ", "small", COLORS["text_muted"]).pack(side="left")
        self.filter_date_var = ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.filter_date = make_entry(flt, "", 120, textvariable=self.filter_date_var)
        self.filter_date.pack(side="left", padx=4)
        self.filter_date_var.trace("w", lambda *args: self.refresh())
        make_button(flt, "Refresh", self.refresh, style="secondary", width=80).pack(side="left", padx=4)

        self.refresh()

    def get_selected_employee(self):
        sel = self.emp_var.get()
        if not sel or sel == "No employees":
            messagebox.showwarning("Select Employee", "Please select an employee.", parent=self)
            return None
        emp_name = sel.split(" (")[0]
        return next((e for e in self.app.data["employees"] if e["name"] == emp_name), None)

    def time_in(self):
        emp = self.get_selected_employee()
        if not emp:
            return
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        logged_today = next((log for log in self.app.data["attendance_logs"]
                           if log["employee_id"] == emp["id"] and log["date"] == today and not log.get("time_out")),
                          None)
        if logged_today:
            messagebox.showwarning("Already Timed In", 
                                 f"{emp['name']} is already timed in at {logged_today['time_in']}", 
                                 parent=self)
            return
        self.app.data["attendance_logs"].append({
            "date": today,
            "employee_id": emp["id"],
            "employee_name": emp["name"],
            "employee_role": emp["role"],
            "time_in": now.strftime("%H:%M:%S"),
            "time_out": None,
            "hours": 0.0,
            "status": "In",
            "note": ""
        })
        save_data(self.app.data)
        messagebox.showinfo("Success", f"✓ {emp['name']} timed in at {now.strftime('%H:%M:%S')}", parent=self)
        self.refresh()

    def time_out(self):
        emp = self.get_selected_employee()
        if not emp:
            return
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        logged = next((log for log in self.app.data["attendance_logs"]
                      if log["employee_id"] == emp["id"] and log["date"] == today and not log.get("time_out")),
                     None)
        if not logged:
            messagebox.showwarning("Not Timed In", 
                                 f"{emp['name']} hasn't timed in today or already timed out.", 
                                 parent=self)
            return
        time_in_obj = datetime.strptime(logged["time_in"], "%H:%M:%S")
        time_out_obj = now
        hours = (time_out_obj - time_in_obj.replace(year=now.year, month=now.month, day=now.day)).total_seconds() / 3600
        logged["time_out"] = now.strftime("%H:%M:%S")
        logged["hours"] = round(hours, 2)
        save_data(self.app.data)
        messagebox.showinfo("Success", 
                          f"✓ {emp['name']} timed out at {now.strftime('%H:%M:%S')}\nHours worked: {hours:.2f}h", 
                          parent=self)
        self.refresh()

    def refresh(self):
        filter_date = self.filter_date.get().strip()
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        timed_in = [log for log in self.app.data["attendance_logs"]
                   if log.get("date", "") == today and not log.get("time_out")]
        status_text = "Current Status:\n"
        if timed_in:
            status_text += "✅ STAFF ON DUTY:\n"
            for log in timed_in:
                status_text += f"  • {log['employee_name']} - In since {log['time_in']}\n"
        else:
            status_text += "No staff currently on duty"
        self.status_lbl.configure(text=status_text)
        for row in self.tree.get_children():
            self.tree.delete(row)
        for log in sorted(self.app.data["attendance_logs"], 
                         key=lambda x: (x.get("date", ""), x.get("employee_name", "")), reverse=True):
            if log.get("date", "") == filter_date:
                hours = f"{log.get('hours', 0):.2f}" if log.get("hours") else "-"
                time_out = log.get("time_out") or "-"
                status = "✅ Completed" if log.get("time_out") else "🟡 On Duty"
                self.tree.insert("", "end", values=(
                    log.get("date", ""),
                    log["employee_name"],
                    log["employee_role"],
                    log["time_in"],
                    time_out,
                    hours,
                    status
                ))


class EmployeeSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        make_label(hdr, "Employee Management", "heading").pack(side="left")
        self.emp_search_var = ctk.StringVar(value="")
        hdr_right = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_right.pack(side="right")
        make_button(hdr_right, "+ Add Employee", self.add_dialog, width=140).pack(side="right")
        emp_search_wrap = ctk.CTkFrame(hdr_right, fg_color="transparent")
        emp_search_wrap.pack(side="right", padx=(0, 8))
        make_label(emp_search_wrap, "Search", "small", COLORS["text_muted"]).pack(side="left", padx=(0, 8))
        emp_search = make_entry(emp_search_wrap, "Search employees…", 220, textvariable=self.emp_search_var)
        emp_search.pack(side="left")
        emp_search.bind("<KeyRelease>", lambda e: self.refresh())

        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("ID", "Name", "Role", "Phone", "Hire Date", "Rate/hr", "Status")
        self.tree, sb = themed_table(card, cols, height=10)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.pack(fill="x", pady=8)
        make_button(acts, "✏ Edit", self.edit_dialog, style="secondary").pack(side="left", padx=4)
        make_button(acts, "⚡ Toggle Active", self.toggle_active, style="outline").pack(side="left", padx=4)
        make_button(acts, "🗑 Delete", self.delete_emp, style="danger").pack(side="left", padx=4)

        pay_card = make_card(self)
        pay_card.pack(fill="x", pady=(8, 0))
        make_label(pay_card, "Payroll Summary (Current Month)", "subheading").pack(padx=16, pady=(12, 4))
        self.pay_lbl = make_label(pay_card, "", "small", COLORS["text_secondary"])
        self.pay_lbl.pack(padx=16, pady=(0, 12), anchor="w")

        self.refresh()

    def refresh(self):
        q = (self.emp_search_var.get() or "").strip().lower()
        for row in self.tree.get_children():
            self.tree.delete(row)
        pay_lines = []
        for emp in self.app.data["employees"]:
            hay = f"{emp.get('name','')} {emp.get('role','')} {emp.get('phone','')}".lower()
            if q and q not in hay:
                continue
            status = "✅ Active" if emp.get("active", True) else "❌ Inactive"
            self.tree.insert("", "end", values=(
                emp["id"], emp["name"], emp["role"], emp["phone"],
                emp["hire_date"], f"₱{emp['hourly_rate']}/hr", status))
            monthly = emp["hourly_rate"] * 8 * 22
            pay_lines.append(f"  {emp['name']:20s} ({emp['role']:10s}) — ₱{monthly:,.0f}/month")
        self.pay_lbl.configure(text="\n".join(pay_lines) if pay_lines else "No employees.")

    def _emp_dialog(self, emp=None):
        dlg = Dialog(self.app, "Add Employee" if not emp else "Edit Employee", 440, 450)
        dlg.add_header("Employee Details")
        form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        fields = {}
        field_names = ["Full Name", "Phone", "Hire Date (YYYY-MM-DD)", "Hourly Rate (₱)"]
        for idx, (lbl, ph, default) in enumerate([
            ("Full Name", "Employee name", emp["name"] if emp else ""),
            ("Phone", "Phone number", emp["phone"] if emp else ""),
            ("Hire Date (YYYY-MM-DD)", "2024-01-01", emp["hire_date"] if emp else datetime.now().strftime("%Y-%m-%d")),
            ("Hourly Rate (₱)", "e.g. 65", str(emp["hourly_rate"]) if emp else "65"),
        ]):
            make_label(form, lbl, "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
            e = make_entry(form, ph, 340)
            e.insert(0, default)
            e.pack(anchor="w")
            if idx < len(field_names) - 1:
                next_field = field_names[idx + 1]
                e.bind("<Return>", lambda event, nf=next_field: fields[nf].focus())
            else:
                e.bind("<Return>", lambda event: role_dd.focus())
            fields[lbl] = e

        make_label(form, "Role", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        role_var = ctk.StringVar(value=emp["role"] if emp else "Cashier")
        role_dd = ctk.CTkOptionMenu(form, variable=role_var,
                                    values=["Admin", "Manager", "Cashier", "Barista"],
                                    fg_color=COLORS["bg_secondary"],
                                    button_color=COLORS["accent"], width=200)
        role_dd.pack(anchor="w")
        role_dd.bind("<Return>", lambda e: form.focus())

        def save():
            name = fields["Full Name"].get().strip()
            phone = fields["Phone"].get().strip()
            hire = fields["Hire Date (YYYY-MM-DD)"].get().strip()
            if not name:
                show_error(dlg, "Error", "Name required.")
                return
            success, rate, error = validate_numeric_input(fields["Hourly Rate (₱)"].get(), "Hourly rate", allow_zero=False, max_value=100000, is_price=True)
            if not success:
                show_error(dlg, "Error", error)
                return
            if emp:
                emp.update({"name": name, "role": role_var.get(),
                            "phone": phone, "hire_date": hire, "hourly_rate": rate})
                log_activity(self.app, "Edit Employee", f"{name} ({role_var.get()})")
            else:
                self.app.data["employees"].append({
                    "id": self.app.data["next_employee_id"],
                    "name": name, "role": role_var.get(),
                    "phone": phone, "hire_date": hire,
                    "hourly_rate": rate, "active": True})
                self.app.data["next_employee_id"] += 1
                log_activity(self.app, "Add Employee", f"{name} ({role_var.get()})")
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)

    def add_dialog(self): self._emp_dialog()

    def edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an employee.", parent=self)
            return
        iid = self.tree.item(sel[0])["values"][0]
        emp = next((e for e in self.app.data["employees"] if e["id"] == iid), None)
        if emp:
            self._emp_dialog(emp)

    def toggle_active(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = self.tree.item(sel[0])["values"][0]
        emp = next((e for e in self.app.data["employees"] if e["id"] == iid), None)
        if emp:
            emp["active"] = not emp.get("active", True)
            log_activity(self.app, "Toggle Employee Active", f"{emp['name']} -> {'Active' if emp['active'] else 'Inactive'}")
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()

    def delete_emp(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = self.tree.item(sel[0])["values"][0]
        emp = next((e for e in self.app.data["employees"] if e["id"] == iid), None)
        if emp and messagebox.askyesno("Confirm", f"Delete '{emp['name']}'?", parent=self):
            log_activity(self.app, "Delete Employee", emp["name"])
            self.app.data["employees"].remove(emp)
            save_data(self.app.data)
            if "dashboard" in self.app.sections:
                self.app.sections["dashboard"].mark_dirty()
            self.refresh()


class ReportsSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        make_label(hdr, "Sales & Reports", "heading").pack(side="left")
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.pack(side="right")
        make_button(btn_frame, "🗑️ Delete Selected", self.delete_selected_orders,
                   style="danger", width=140).pack(side="left", padx=(0, 8))
        make_button(btn_frame, "🧹 Clear History", self.clear_history,
                   style="danger", width=120).pack(side="left")

        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.pack(fill="x", pady=(0, 12))
        make_label(pf, "Period: ", "small", COLORS["text_muted"]).pack(side="left")
        self.period_var = ctk.StringVar(value="Today")
        for period in ["Today", "This Week", "This Month", "All Time"]:
            ctk.CTkRadioButton(pf, text=period, variable=self.period_var,
                               value=period, command=self.refresh,
                               text_color=COLORS["text_secondary"],
                               fg_color=COLORS["accent"],
                               hover_color=COLORS["accent2"]).pack(side="left", padx=8)

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(0, 12))
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        make_label(self, "Order History", "subheading").pack(anchor="w", pady=(8, 4))
        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("Order #", "Date", "Time", "Type", "Items", "Subtotal", "Discount", "Total", "Payment")
        self.tree, sb = themed_table(card, cols, height=10)
        for col, w in zip(cols, [80, 90, 70, 80, 220, 90, 80, 90, 80]):
            self.tree.column(col, width=w)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)
        self.tree.bind("<Double-1>", self.on_order_double_click)

        self.refresh()

    def get_filtered_orders(self):
        today = datetime.now().date()
        orders = self.app.data["orders"]
        period = self.period_var.get()
        result = []
        for o in orders:
            try:
                d = datetime.strptime(o["date"], "%Y-%m-%d").date()
            except Exception:
                continue
            if period == "Today" and d == today:
                result.append(o)
            elif period == "This Week" and (today - d).days < 7:
                result.append(o)
            elif period == "This Month" and d.year == today.year and d.month == today.month:
                result.append(o)
            elif period == "All Time":
                result.append(o)
        return result

    def refresh(self):
        orders = self.get_filtered_orders()
        for w in self.stats_frame.winfo_children():
            w.destroy()
        total_rev = sum(o["total"] for o in orders)
        total_disc = sum(o.get("discount", 0) for o in orders)
        order_count = len(orders)
        avg = total_rev / order_count if order_count else 0
        stats = [
            ("Total Revenue", f"₱{total_rev:,.2f}", "", COLORS["accent"]),
            ("Orders", str(order_count), "Transactions", COLORS["success"]),
            ("Avg Order", f"₱{avg:,.2f}", "Per order", COLORS["warning"]),
            ("Total Discounts", f"₱{total_disc:,.2f}", "Given", COLORS["danger"]),
        ]
        for i, (title, val, sub, color) in enumerate(stats):
            card = make_stat_card(self.stats_frame, title, val, sub, color)
            card.grid(row=0, column=i, sticky="nsew", padx=4)

        item_counts = {}
        for o in orders:
            for item in o.get("items", []):
                name = item["name"]
                item_counts[name] = item_counts.get(name, 0) + item.get("quantity", 1)
        for row in self.tree.get_children():
            self.tree.delete(row)
        for o in reversed(orders):
            items_str = "; ".join(f"{i['name']}({i['size']})x{i['quantity']}" for i in o.get("items", []))
            self.tree.insert("", "end", values=(
                o["id"], o["date"], o["time"], o.get("order_type", "dine-in"),
                items_str[:60] + ("..." if len(items_str) > 60 else ""),
                f"₱{o['subtotal']:.2f}",
                f"₱{o.get('discount', 0):.2f}",
                f"₱{o['total']:.2f}",
                o["payment"]))

    def delete_selected_orders(self):
        if not self.app.has_permission("delete_order"):
            messagebox.showwarning("Permission Denied", "You do not have permission to delete orders.", parent=self)
            return
        selected = list(self.tree.selection())
        if not selected:
            messagebox.showwarning("Select", "Please select order(s) to delete.", parent=self)
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(selected)} selected order(s)? This cannot be undone.", parent=self):
            return
        order_ids = []
        for iid in selected:
            values = self.tree.item(iid)["values"]
            if values:
                order_ids.append(values[0])
        orders_to_delete = []
        for order_id in order_ids:
            order = next((o for o in self.app.data["orders"] if o["id"] == order_id), None)
            if order:
                orders_to_delete.append(order)
        for order in orders_to_delete:
            log_activity(self.app, "Delete Order", f"Order #{order['id']} - {order.get('customer_name', '')} - ₱{order['total']:.2f}")
            self.app.data["orders"].remove(order)
        save_data(self.app.data)
        if "dashboard" in self.app.sections:
            self.app.sections["dashboard"].mark_dirty()
        self.refresh()

    def on_order_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        values = self.tree.item(iid).get("values", [])
        if not values:
            return
        order_id = values[0]
        order = next((o for o in self.app.data["orders"] if o["id"] == order_id), None)
        if order:
            self.show_order_receipt(order)

    def show_order_receipt(self, order):
        shop_name = self.app.data.get("settings", {}).get("shop_name", "Brewster's Cup")
        tagline = self.app.data.get("settings", {}).get("tagline", "")
        receipt = (
            f"{shop_name:^38}\n"
            f"{tagline:^38}\n"
            f"{'─' * 38}\n"
            f"Order #: {order['id']}\n"
            f"Date: {order.get('date', '')}  Time: {order.get('time', '')}\n"
            f"Type: {order.get('order_type', 'dine-in')}\n"
            f"{'─' * 38}\n"
        )
        for item in order.get("items", []):
            tops = ", ".join(t.get("name", "") for t in item.get("toppings", []) if t.get("name")) or "No toppings"
            receipt += f"  {item.get('name', 'Item')} ({item.get('size', '')}) x{item.get('quantity', 1)}\n"
            receipt += f"    {item.get('sugar', '')} | {item.get('ice', '')}\n"
            receipt += f"    {tops}\n"
            receipt += f"    ₱{float(item.get('total', item.get('line_total', 0))):.2f}\n"
        receipt += f"{'─' * 38}\n"
        receipt += f"Subtotal:   ₱{float(order.get('subtotal', 0)):.2f}\n"
        if order.get('discount'):
            receipt += f"Discount:  -₱{float(order.get('discount', 0)):.2f}\n"
        receipt += f"TOTAL:      ₱{float(order.get('total', 0)):.2f}\n"
        if order.get('customer_name'):
            receipt += f"Customer:   {order.get('customer_name')}\n"
        if order.get('delivery_address'):
            receipt += f"Address:    {order.get('delivery_address')}\n"
        if order.get('delivery_phone'):
            receipt += f"Phone:      {order.get('delivery_phone')}\n"
        receipt += f"Payment:    {order.get('payment', '')}\n"
        if order.get('payment') == 'GCash' and order.get('gcash_reference'):
            receipt += f"GCash QR:   {order.get('gcash_reference')}\n"
        if order.get('payment') == 'Cash':
            receipt += f"Change:     ₱{float(order.get('change', 0)):.2f}\n"
        receipt += f"{'─' * 38}\n"
        receipt += f"{'Thank you! Come again!':^38}\n"

        rdlg = ctk.CTkToplevel(self.app)
        rdlg.title("Receipt")
        rdlg.geometry("420x540")
        rdlg.configure(fg_color=COLORS["bg_primary"])
        rdlg.grab_set()
        make_label(rdlg, "Order Receipt", "heading", COLORS["accent"]).pack(pady=12)
        tb = ctk.CTkTextbox(rdlg, font=FONTS["mono"], fg_color=COLORS["bg_card"],
                            text_color=COLORS["text_primary"])
        tb.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        tb.insert("1.0", receipt)
        tb.configure(state="disabled")

        bf = ctk.CTkFrame(rdlg, fg_color="transparent")
        bf.pack(fill="x", padx=16, pady=8)

        def save_receipt_csv():
            try:
                file_path = filedialog.asksaveasfilename(
                    title="Save Receipt as CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv")],
                    initialfile=f"receipt_{order['id']}.csv",
                    parent=rdlg,
                )
                if not file_path:
                    return
                import csv
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Order Receipt"])
                    writer.writerow(["Shop Name", shop_name])
                    writer.writerow(["Tagline", tagline])
                    writer.writerow([])
                    writer.writerow(["Order #", order["id"]])
                    writer.writerow(["Date", order.get("date", "")])
                    writer.writerow(["Time", order.get("time", "")])
                    writer.writerow(["Type", order.get("order_type", "")])
                    writer.writerow(["Payment", order.get("payment", "")])
                    writer.writerow(["Customer", order.get("customer_name", "")])
                    writer.writerow(["Address", order.get("delivery_address", "")])
                    writer.writerow(["Phone", order.get("delivery_phone", "")])
                    if order.get("payment") == "Cash":
                        writer.writerow(["Change", f"{float(order.get('change', 0)):.2f}"])
                    if order.get("payment") == "GCash" and order.get("gcash_reference"):
                        writer.writerow(["GCash QR", order.get("gcash_reference")])
                    writer.writerow([])
                    writer.writerow(["Item Name", "Size", "Quantity", "Sugar", "Ice", "Toppings", "Unit Price", "Line Total"])
                    for item in order.get("items", []):
                        writer.writerow([
                            item.get("name", ""),
                            item.get("size", ""),
                            item.get("quantity", 1),
                            item.get("sugar", ""),
                            item.get("ice", ""),
                            ", ".join(t.get("name", "") for t in item.get("toppings", []) if t.get("name")),
                            f"{float(item.get('unit_price', 0)):.2f}",
                            f"{float(item.get('total', item.get('line_total', 0))):.2f}",
                        ])
                    writer.writerow([])
                    writer.writerow(["Subtotal", f"{float(order.get('subtotal', 0)):.2f}"])
                    writer.writerow(["Discount", f"{float(order.get('discount', 0)):.2f}"])
                    writer.writerow(["Total", f"{float(order.get('total', 0)):.2f}"])
                messagebox.showinfo("Saved", f"Receipt saved to CSV:\n{file_path}", parent=rdlg)
            except Exception as e:
                show_error(rdlg, "Save Error", f"Failed to save receipt to CSV: {str(e)}")

        make_button(bf, "🖨 Print", save_receipt_csv, style="primary", width=90).pack(side="left", padx=4)
        make_button(bf, "📋 Copy", lambda: rdlg.clipboard_clear() or rdlg.clipboard_append(receipt),
                    style="secondary", width=90).pack(side="left", padx=4)
        make_button(bf, "✕ Close", rdlg.destroy, style="outline", width=90).pack(side="right", padx=4)

    def clear_history(self):
        if not self.app.has_permission("delete_order"):
            messagebox.showwarning("Permission Denied", "You do not have permission to clear order history.", parent=self)
            return
        order_count = len(self.app.data["orders"])
        if order_count == 0:
            messagebox.showinfo("No Orders", "There are no orders to clear.", parent=self)
            return
        if not messagebox.askyesno("Confirm", f"Clear ALL {order_count} orders from history? This cannot be undone.", parent=self):
            return
        log_activity(self.app, "Clear Order History", f"Cleared {order_count} orders")
        self.app.data["orders"] = []
        save_data(self.app.data)
        if "dashboard" in self.app.sections:
            self.app.sections["dashboard"].mark_dirty()
        self.refresh()


class ExpensesSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        make_label(hdr, "Expense Tracking", "heading").pack(side="left")
        make_button(hdr, "+ Log Expense", self.add_dialog, width=130).pack(side="right")

        sf = ctk.CTkFrame(self, fg_color="transparent")
        sf.pack(fill="x", pady=(0, 12))
        sf.grid_columnconfigure((0, 1, 2), weight=1)
        self.total_card = make_stat_card(sf, "Total Expenses (Month)", "₱0", "", COLORS["danger"])
        self.total_card.grid(row=0, column=0, sticky="nsew", padx=4)
        self.revenue_card = make_stat_card(sf, "Revenue (Month)", "₱0", "", COLORS["success"])
        self.revenue_card.grid(row=0, column=1, sticky="nsew", padx=4)
        self.profit_card = make_stat_card(sf, "Net Profit (Month)", "₱0", "", COLORS["warning"])
        self.profit_card.grid(row=0, column=2, sticky="nsew", padx=4)

        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("ID", "Date", "Category", "Description", "Amount")
        self.tree, sb = themed_table(card, cols, height=12)
        for col, w in zip(cols, [50, 100, 120, 300, 100]):
            self.tree.column(col, width=w)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.pack(fill="x", pady=8)
        make_button(acts, "✏ Edit", self.edit_exp, style="secondary").pack(side="left", padx=4)
        make_button(acts, "🗑 Delete", self.delete_exp, style="danger").pack(side="left", padx=4)

        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        total_exp = 0
        today = datetime.now()
        for exp in self.app.data["expenses"]:
            try:
                d = datetime.strptime(exp["date"], "%Y-%m-%d")
                if d.month == today.month and d.year == today.year:
                    total_exp += exp["amount"]
            except Exception:
                pass
            self.tree.insert("", "end", values=(
                exp["id"], exp["date"], exp["category"],
                exp["description"], f"₱{exp['amount']:,.2f}"))
        orders = self.app.data["orders"]
        monthly_rev = sum(o["total"] for o in orders
                          if o["date"].startswith(today.strftime("%Y-%m")))
        profit = monthly_rev - total_exp
        self.total_card.winfo_children()[1].configure(text=f"₱{total_exp:,.2f}")
        self.revenue_card.winfo_children()[1].configure(text=f"₱{monthly_rev:,.2f}")
        color = COLORS["success"] if profit >= 0 else COLORS["danger"]
        self.profit_card.winfo_children()[1].configure(text=f"₱{profit:,.2f}", text_color=color)

    def add_dialog(self):
        self._expense_dialog()

    def delete_exp(self):
        sel = self.tree.selection()
        if not sel:
            return
        eid = self.tree.item(sel[0])["values"][0]
        exp = next((e for e in self.app.data["expenses"] if e["id"] == eid), None)
        if exp and messagebox.askyesno("Confirm", f"Delete expense '{exp['description']}'?", parent=self):
            log_activity(self.app, "Delete Expense", f"{exp['description']} (₱{exp['amount']})")
            self.app.data["expenses"].remove(exp)
            save_data(self.app.data)
            self.refresh()

    def edit_exp(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an expense to edit.", parent=self)
            return
        eid = self.tree.item(sel[0])["values"][0]
        exp = next((e for e in self.app.data["expenses"] if e["id"] == eid), None)
        if exp:
            self._expense_dialog(exp)

    def _expense_dialog(self, expense=None):
        dlg = Dialog(self.app, "Edit Expense" if expense else "Log Expense", 420, 460)
        dlg.add_header("Edit Expense" if expense else "Log Expense")
        form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        make_label(form, "Category", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        cat_var = ctk.StringVar(value=expense["category"] if expense else "Supplies")
        cat_dd = ctk.CTkOptionMenu(form, variable=cat_var,
                                   values=["Rent", "Utilities", "Supplies", "Salaries", "Maintenance", "Other"],
                                   fg_color=COLORS["bg_secondary"],
                                   button_color=COLORS["accent"], width=240)
        cat_dd.pack(anchor="w")

        make_label(form, "Description", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        desc_e = make_entry(form, "Expense description", 340)
        desc_e.pack(anchor="w")
        desc_e.bind("<Return>", lambda e: amount_e.focus())
        if expense:
            desc_e.insert(0, expense["description"])

        make_label(form, "Amount (₱)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        amount_e = make_entry(form, "0.00", 200)
        amount_e.pack(anchor="w")
        amount_e.bind("<Return>", lambda e: date_e.focus())
        if expense:
            amount_e.insert(0, str(expense["amount"]))

        make_label(form, "Date (YYYY-MM-DD)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(8, 0))
        date_e = make_entry(form, datetime.now().strftime("%Y-%m-%d"), 200)
        date_e.pack(anchor="w")
        date_e.bind("<Return>", lambda e: form.focus())
        if expense:
            date_e.insert(0, expense["date"])
        else:
            date_e.insert(0, datetime.now().strftime("%Y-%m-%d"))

        def save():
            desc = desc_e.get().strip()
            if not desc:
                show_error(dlg, "Error", "Description required.")
                return
            success, amount, error = validate_numeric_input(amount_e.get(), "Amount", allow_zero=False, max_value=10000000, is_price=True)
            if not success:
                show_error(dlg, "Error", error)
                return
            if expense:
                expense["date"] = date_e.get().strip()
                expense["category"] = cat_var.get()
                expense["description"] = desc
                expense["amount"] = amount
                log_activity(self.app, "Edit Expense", f"{desc} (₱{amount})")
            else:
                self.app.data["expenses"].append({
                    "id": self.app.data["next_expense_id"],
                    "date": date_e.get().strip(),
                    "category": cat_var.get(),
                    "description": desc,
                    "amount": amount})
                self.app.data["next_expense_id"] += 1
                log_activity(self.app, "Log Expense", f"{desc} (₱{amount})")
            save_data(self.app.data)
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)


class PromosSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        make_label(hdr, "Promotions & Discounts", "heading").pack(side="left")
        make_button(hdr, "+ Add Promo", self.add_dialog, width=120).pack(side="right")

        card = make_card(self)
        card.pack(fill="both", expand=True)
        cols = ("ID", "Code", "Description", "Type", "Value", "Status")
        self.tree, sb = themed_table(card, cols, height=12)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        acts = ctk.CTkFrame(self, fg_color="transparent")
        acts.pack(fill="x", pady=8)
        make_button(acts, "✏ Edit", self.edit_dialog, style="secondary").pack(side="left", padx=4)
        make_button(acts, "⚡ Toggle Active", self.toggle_promo, style="outline").pack(side="left", padx=4)
        make_button(acts, "🗑 Delete", self.delete_promo, style="danger").pack(side="left", padx=4)

        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in self.app.data["promos"]:
            val = f"{p['value']}%" if p["type"] == "percent" else f"₱{p['value']}"
            status = "✅ Active" if p["active"] else "❌ Inactive"
            self.tree.insert("", "end", values=(
                p["id"], p["code"], p["description"],
                p["type"].capitalize(), val, status))

    def _promo_dialog(self, promo=None):
        dlg = Dialog(self.app, "Add Promo" if not promo else "Edit Promo", 400, 380)
        dlg.add_header("Promo / Discount")
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        make_label(form, "Code", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        code_e = make_entry(form, "PROMO2025", 280)
        code_e.pack(anchor="w")
        code_e.bind("<Return>", lambda e: desc_e.focus())

        make_label(form, "Description", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        desc_e = make_entry(form, "Description", 280)
        desc_e.pack(anchor="w")
        desc_e.bind("<Return>", lambda e: val_e.focus())

        make_label(form, "Type", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        type_var = ctk.StringVar(value=promo["type"] if promo else "percent")
        tf = ctk.CTkFrame(form, fg_color="transparent")
        tf.pack(anchor="w")
        for t in ["percent", "flat"]:
            ctk.CTkRadioButton(tf, text=t.capitalize(), variable=type_var, value=t,
                               text_color=COLORS["text_secondary"],
                               fg_color=COLORS["accent"],
                               hover_color=COLORS["accent2"]).pack(side="left", padx=8)

        make_label(form, "Value (% or ₱)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        val_e = make_entry(form, "10", 120)
        val_e.pack(anchor="w")
        val_e.bind("<Return>", lambda e: form.focus())

        if promo:
            code_e.insert(0, promo["code"])
            desc_e.insert(0, promo["description"])
            val_e.insert(0, str(promo["value"]))

        def save():
            code = code_e.get().strip().upper()
            desc = desc_e.get().strip()
            if not code or not desc:
                show_error(dlg, "Error", "Code and description required.")
                return
            success, val, error = validate_numeric_input(val_e.get(), "Promo value", allow_zero=False, max_value=100, is_price=True)
            if not success:
                show_error(dlg, "Error", error)
                return
            if promo:
                promo.update({"code": code, "description": desc,
                              "type": type_var.get(), "value": val})
                log_activity(self.app, "Edit Promo", f"{code} ({desc})")
            else:
                self.app.data["promos"].append({
                    "id": self.app.data["next_promo_id"],
                    "code": code, "description": desc,
                    "type": type_var.get(), "value": val, "active": True})
                self.app.data["next_promo_id"] += 1
                log_activity(self.app, "Add Promo", f"{code} ({desc})")
            save_data(self.app.data)
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)

    def add_dialog(self): self._promo_dialog()

    def edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a promo.", parent=self)
            return
        pid = self.tree.item(sel[0])["values"][0]
        promo = next((p for p in self.app.data["promos"] if p["id"] == pid), None)
        if promo:
            self._promo_dialog(promo)

    def toggle_promo(self):
        sel = self.tree.selection()
        if not sel:
            return
        pid = self.tree.item(sel[0])["values"][0]
        promo = next((p for p in self.app.data["promos"] if p["id"] == pid), None)
        if promo:
            promo["active"] = not promo["active"]
            log_activity(self.app, "Toggle Promo", f"{promo['code']} -> {'Active' if promo['active'] else 'Inactive'}")
            save_data(self.app.data)
            self.refresh()

    def delete_promo(self):
        sel = self.tree.selection()
        if not sel:
            return
        pid = self.tree.item(sel[0])["values"][0]
        promo = next((p for p in self.app.data["promos"] if p["id"] == pid), None)
        if promo and messagebox.askyesno("Confirm", f"Delete promo '{promo['code']}'?", parent=self):
            log_activity(self.app, "Delete Promo", promo["code"])
            self.app.data["promos"].remove(promo)
            save_data(self.app.data)
            self.refresh()


class DashboardSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._last_order_count = -1
        self._last_low_stock_count = -1
        self._last_active_emp_count = -1
        self._last_today_revenue = -1
        self._needs_refresh = True
        self.build()

    def build(self):
        settings = self.app.data["settings"]
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 16))
        make_label(hdr, f"Welcome back 👋", "small", COLORS["text_muted"]).pack(anchor="w")
        make_label(hdr, settings["shop_name"], "title", COLORS["accent"]).pack(anchor="w")
        make_label(hdr, f"Today: {datetime.now().strftime('%A, %B %d, %Y')}", "small",
                   COLORS["text_secondary"]).pack(anchor="w")
        make_button(hdr, "🔄 Refresh", self.refresh, style="secondary", width=100).pack(side="right")

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(0, 16))
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.charts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.charts_frame.pack(fill="x", pady=(0, 16))
        self.charts_frame.grid_columnconfigure(0, weight=1)
        self.charts_frame.grid_columnconfigure(1, weight=1)

        self.category_card = make_card(self.charts_frame)
        self.category_card.grid(row=0, column=0, sticky="nsew", padx=4, pady=0)
        make_label(self.category_card, "Sales by Category", "subheading").pack(anchor="w", padx=16, pady=(12, 4))
        self.category_canvas = tk.Canvas(self.category_card, bg=COLORS["bg_secondary"],
                                        highlightthickness=0, bd=0, width=420, height=260)
        self.category_canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.top_items_card = make_card(self.charts_frame)
        self.top_items_card.grid(row=0, column=1, sticky="nsew", padx=4, pady=0)
        make_label(self.top_items_card, "Top Items Sold", "subheading").pack(anchor="w", padx=16, pady=(12, 4))
        self.top_items_canvas = tk.Canvas(self.top_items_card, bg=COLORS["bg_secondary"],
                                         highlightthickness=0, bd=0, width=420, height=260)
        self.top_items_canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.recent_frame = make_card(self)
        self.recent_frame.pack(fill="both", expand=True)
        header = ctk.CTkFrame(self.recent_frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        make_label(header, "Recent Orders", "subheading").pack(anchor="w")
        self.recent_scroll = ctk.CTkScrollableFrame(self.recent_frame, fg_color="transparent")
        self.recent_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.refresh()

    def refresh(self):
        today = datetime.now().strftime("%Y-%m-%d")
        orders = self.app.data["orders"]
        today_orders = [o for o in orders if o["date"] == today]
        today_rev = sum(o["total"] for o in today_orders)
        low_stock = sum(1 for i in self.app.data["inventory"] if i["quantity"] <= i["threshold"])
        active_emps = sum(1 for e in self.app.data["employees"] if e.get("active", True))
        current_state = (len(orders), low_stock, active_emps, today_rev)
        cached_state = (self._last_order_count, self._last_low_stock_count, self._last_active_emp_count, self._last_today_revenue)
        if current_state == cached_state and not self._needs_refresh:
            return
        self._last_order_count = len(orders)
        self._last_low_stock_count = low_stock
        self._last_active_emp_count = active_emps
        self._last_today_revenue = today_rev
        self._needs_refresh = False
        for w in self.stats_frame.winfo_children():
            w.destroy()
        stats = [
            ("Today's Revenue", f"₱{today_rev:,.2f}", f"{len(today_orders)} orders", COLORS["accent"]),
            ("Active Employees", str(active_emps), "On roster", COLORS["success"]),
            ("Low Stock Items", str(low_stock), "Need restocking", COLORS["warning"] if low_stock == 0 else COLORS["danger"]),
            ("Menu Items", str(len(self.app.data["menu_items"])), "Available", COLORS["accent2"]),
        ]
        for i, (title, val, sub, color) in enumerate(stats):
            card = make_stat_card(self.stats_frame, title, val, sub, color)
            card.grid(row=0, column=i, sticky="nsew", padx=4)
        self._draw_category_sales_chart(orders)
        self._draw_top_items_chart(orders)
        for w in self.recent_scroll.winfo_children():
            w.destroy()
        if not orders:
            make_label(self.recent_scroll, "No orders yet. Start selling! 🧋", "body", COLORS["text_muted"]).pack(pady=20)
        else:
            for o in list(reversed(orders))[:8]:
                row = ctk.CTkFrame(self.recent_scroll, fg_color=COLORS["bg_secondary"],
                                   corner_radius=8)
                row.pack(fill="x", padx=0, pady=3)
                row.grid_columnconfigure(1, weight=1)
                make_label(row, f"#{o['id']}", "small", COLORS["accent"]).grid(
                    row=0, column=0, padx=10, pady=8)
                items_str = ", ".join(f"{i['name']}x{i['quantity']}" for i in o.get("items", []))
                make_label(row, items_str[:60], "small").grid(row=0, column=1, sticky="w", padx=4)
                make_label(row, f"₱{o['total']:.2f}", "small", COLORS["success"]).grid(row=0, column=2, padx=10)
                make_label(row, o["time"], "small", COLORS["text_muted"]).grid(row=0, column=3, padx=10)

    def mark_dirty(self):
        self._needs_refresh = True

    def _draw_category_sales_chart(self, orders):
        self.category_canvas.delete("all")
        category_sales = {}
        menu_by_name = {item["name"]: item for item in self.app.data["menu_items"]}
        for order in orders:
            for item in order.get("items", []):
                item_name = item.get("name", "")
                revenue = float(item.get("total", item.get("line_total", 0)) or 0)
                category = menu_by_name.get(item_name, {}).get("category", "Other")
                category_sales[category] = category_sales.get(category, 0) + revenue
        if not category_sales:
            self.category_canvas.create_text(210, 130, text="No sales data yet", fill=COLORS["text_muted"], font=FONTS["subheading"])
            return
        total = sum(category_sales.values())
        colors = [COLORS["accent"], COLORS["accent2"], COLORS["success"], COLORS["warning"], COLORS["danger"], COLORS["text_secondary"]]
        start_angle = 0
        x0, y0, x1, y1 = 40, 40, 220, 220
        labels = []
        sorted_categories = sorted(category_sales.items(), key=lambda x: x[1], reverse=True)
        for idx, (category, value) in enumerate(sorted_categories):
            extent = round(360 * (value / total)) if total else 0
            self.category_canvas.create_arc(x0, y0, x1, y1, start=start_angle, extent=extent,
                                            fill=colors[idx % len(colors)], outline=COLORS["bg_secondary"])
            start_angle += extent
            labels.append((category, value, colors[idx % len(colors)]))
        if start_angle < 360:
            self.category_canvas.create_arc(x0, y0, x1, y1, start=start_angle, extent=360 - start_angle,
                                            fill=COLORS["bg_secondary"], outline=COLORS["bg_secondary"])
        self.category_canvas.create_text(280, 56, text="Category share", fill=COLORS["text_primary"], anchor="nw", font=FONTS["small"])
        for i, (category, value, color) in enumerate(labels[:6]):
            percent = value / total * 100 if total else 0
            y = 96 + i * 24
            self.category_canvas.create_rectangle(280, y, 296, y + 14, fill=color, outline="")
            self.category_canvas.create_text(302, y + 7, text=f"{category}: {percent:.0f}%", fill=COLORS["text_secondary"], anchor="w", font=FONTS["small"])

    def _draw_top_items_chart(self, orders):
        self.top_items_canvas.delete("all")
        item_totals = {}
        for order in orders:
            for item in order.get("items", []):
                name = item.get("name", "")
                item_totals[name] = item_totals.get(name, 0) + int(item.get("quantity", 0) or 0)
        if not item_totals:
            self.top_items_canvas.create_text(210, 130, text="No sales data yet", fill=COLORS["text_muted"], font=FONTS["subheading"])
            return
        sorted_items = sorted(item_totals.items(), key=lambda x: x[1], reverse=True)[:6]
        max_qty = max(q for _, q in sorted_items) or 1
        chart_x = 150
        chart_width = 220
        self.top_items_canvas.create_text(14, 18, text="Item", fill=COLORS["text_primary"], anchor="nw", font=FONTS["small"])
        self.top_items_canvas.create_text(412, 18, text="Qty", fill=COLORS["text_primary"], anchor="ne", font=FONTS["small"])
        for idx, (name, qty) in enumerate(sorted_items):
            y = 40 + idx * 36
            bar_len = int((qty / max_qty) * chart_width)
            self.top_items_canvas.create_rectangle(chart_x, y, chart_x + bar_len, y + 22,
                                                   fill=COLORS["accent"], outline="")
            self.top_items_canvas.create_text(14, y + 11, text=name, fill=COLORS["text_secondary"], anchor="w", font=FONTS["small"])
            self.top_items_canvas.create_text(412, y + 11, text=str(qty), fill=COLORS["text_primary"], anchor="e", font=FONTS["small"])


class SettingsSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        make_label(self, "System Settings", "heading").pack(anchor="w", pady=(0, 16))

        scrollable = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scrollable.pack(fill="both", expand=True)

        card = make_card(scrollable)
        card.pack(fill="x", pady=(0, 16))
        make_label(card, "Shop Information", "subheading").pack(padx=16, pady=(12, 8), anchor="w")

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=(0, 16))

        settings = self.app.data["settings"]
        self.fields = {}
        for key, label, ph in [
            ("shop_name", "Shop Name", "Your shop name"),
            ("tagline", "Tagline", "Your slogan"),
            ("address", "Address", "Your address"),
            ("phone", "Phone", "Contact number"),
        ]:
            make_label(form, label, "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
            e = make_entry(form, ph, 400)
            e.insert(0, settings.get(key, ""))
            e.pack(anchor="w")
            self.fields[key] = e

        can_edit_settings = self.app.has_permission("edit_settings")
        make_button(card, "💾 Save Settings", self.save_settings, width=160,
                    state="normal" if can_edit_settings else "disabled").pack(padx=20, pady=(0, 16), anchor="w")

        brand_card = make_card(scrollable)
        brand_card.pack(fill="x", pady=(0, 16))
        make_label(brand_card, "Branding & Data", "subheading").pack(padx=16, pady=(12, 8), anchor="w")

        brand_body = ctk.CTkFrame(brand_card, fg_color="transparent")
        brand_body.pack(fill="x", padx=16, pady=(0, 16))
        brand_body.grid_columnconfigure(1, weight=1)

        make_label(brand_body, "Logo File", "small", COLORS["text_muted"]).grid(row=0, column=0, sticky="w")
        self.logo_path_label = make_label(brand_body,
                                         settings.get("logo_path", "") or "No logo selected",
                                         "small", COLORS["text_secondary"])
        self.logo_path_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.logo_buttons_frame = ctk.CTkFrame(brand_body, fg_color="transparent")
        self.logo_buttons_frame.grid(row=0, column=2, columnspan=2, sticky="e")
        self._update_logo_buttons()

        make_label(brand_body, "Login Background", "small", COLORS["text_muted"]).grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.login_bg_path_label = make_label(brand_body,
                                             settings.get("login_bg_path", "") or "No background selected",
                                             "small", COLORS["text_secondary"])
        self.login_bg_path_label.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(12, 0))
        self.login_bg_buttons_frame = ctk.CTkFrame(brand_body, fg_color="transparent")
        self.login_bg_buttons_frame.grid(row=1, column=2, columnspan=2, sticky="e", pady=(12, 0))
        self._update_login_bg_buttons()

        can_manage_data = self.app.has_permission("backup_data")
        data_actions = ctk.CTkFrame(brand_card, fg_color="transparent")
        data_actions.pack(fill="x", padx=16, pady=(0, 4))
        make_button(data_actions, "Backup Data", self.backup_data, width=140,
                    state="normal" if can_manage_data else "disabled").pack(side="left", padx=4)
        make_button(data_actions, "Restore Data", self.restore_data, style="danger", width=140,
                    state="normal" if can_manage_data else "disabled").pack(side="left", padx=4)

        ucard = make_card(scrollable)
        ucard.pack(fill="x", pady=(0, 16))
        uh = ctk.CTkFrame(ucard, fg_color="transparent")
        uh.pack(fill="x", padx=16, pady=(12, 8))
        make_label(uh, "User Accounts", "subheading").pack(side="left")

        body = ctk.CTkFrame(ucard, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 12))

        table_wrap = ctk.CTkFrame(body, fg_color="transparent")
        table_wrap.pack(side="left", fill="both", expand=True)

        cols = ("ID", "Username", "Name", "Role")
        self.user_tree, sb = themed_table(table_wrap, cols, height=5)
        self.user_tree.pack(side="left", fill="both", expand=True, padx=(0, 8))
        sb.pack(side="right", fill="y")

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(side="right", fill="y")

        can_manage_users = self.app.has_permission("manage_users")
        btn_w = 140
        make_button(actions, "+ Add User", self.add_user_dialog, width=btn_w,
                    state="normal" if can_manage_users else "disabled").pack(anchor="e", pady=(0, 8))
        make_button(actions, "✏ Edit User", self.edit_user_dialog, style="secondary",
                    width=btn_w, state="normal" if can_manage_users else "disabled").pack(anchor="e", pady=(0, 8))
        make_button(actions, "🗑 Delete User", self.delete_user, style="danger",
                    width=btn_w, state="normal" if can_manage_users else "disabled").pack(anchor="e")

        self.refresh()

    def _update_logo_buttons(self):
        for child in self.logo_buttons_frame.winfo_children():
            child.destroy()
        logo_path = self.app.data["settings"].get("logo_path", "")
        if logo_path:
            make_button(self.logo_buttons_frame, "Change Logo", self.change_logo, style="secondary", width=120).pack(side="left", padx=4)
            make_button(self.logo_buttons_frame, "Remove Logo", self.remove_logo, style="danger", width=120).pack(side="left", padx=4)
        else:
            make_button(self.logo_buttons_frame, "Add Logo", self.change_logo, style="primary", width=120).pack(side="left", padx=4)

    def save_settings(self):
        for key, e in self.fields.items():
            self.app.data["settings"][key] = e.get().strip()
        log_activity(self.app, "Save Settings", "Updated shop settings")
        save_data(self.app.data)
        self.app.update_branding()
        messagebox.showinfo("Saved", "Settings saved successfully!", parent=self)

    def change_logo(self):
        file_path = filedialog.askopenfilename(
            title="Choose logo image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")],
            parent=self)
        if not file_path:
            return
        if not os.path.exists(file_path):
            messagebox.showerror("Invalid File", "Selected file does not exist.", parent=self)
            return
        try:
            Image.open(file_path)
        except Exception:
            messagebox.showerror("Invalid Image", "Selected file is not a valid image.", parent=self)
            return
        self.app.data["settings"]["logo_path"] = file_path
        self.logo_path_label.configure(text=file_path)
        log_activity(self.app, "Change Logo", file_path)
        save_data(self.app.data)
        self.app.update_branding()
        self._update_logo_buttons()
        messagebox.showinfo("Logo Updated", "Logo image updated successfully.", parent=self)

    def remove_logo(self):
        if not self.app.data["settings"].get("logo_path", ""):
            messagebox.showinfo("No Logo", "No logo to remove.", parent=self)
            return
        if messagebox.askyesno("Confirm", "Remove the current logo?", parent=self):
            self.app.data["settings"]["logo_path"] = ""
            self.logo_path_label.configure(text="No logo selected")
            log_activity(self.app, "Remove Logo", "Logo cleared")
            save_data(self.app.data)
            self.app.update_branding()
            self._update_logo_buttons()
            messagebox.showinfo("Logo Removed", "Logo has been removed successfully.", parent=self)

    def _update_login_bg_buttons(self):
        for child in self.login_bg_buttons_frame.winfo_children():
            child.destroy()
        login_bg_path = self.app.data["settings"].get("login_bg_path", "")
        if login_bg_path:
            make_button(self.login_bg_buttons_frame, "Change Background", self.change_login_bg, style="secondary", width=140).pack(side="left", padx=4)
            make_button(self.login_bg_buttons_frame, "Remove Background", self.remove_login_bg, style="danger", width=140).pack(side="left", padx=4)
        else:
            make_button(self.login_bg_buttons_frame, "Add Background", self.change_login_bg, style="primary", width=140).pack(side="left", padx=4)

    def change_login_bg(self):
        file_path = filedialog.askopenfilename(
            title="Choose login background image or video",
            filetypes=[("Image/Video files", "*.png *.jpg *.jpeg *.gif *.bmp *.mp4 *.avi *.mov")],
            parent=self)
        if not file_path:
            return
        if not os.path.exists(file_path):
            messagebox.showerror("Invalid File", "Selected file does not exist.", parent=self)
            return
        is_image = file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
        is_video = file_path.lower().endswith(('.mp4', '.avi', '.mov'))
        if is_image:
            try:
                Image.open(file_path)
            except Exception:
                messagebox.showerror("Invalid Image", "Selected file is not a valid image.", parent=self)
                return
        elif is_video:
            if cv2 is None:
                messagebox.showerror("Video Not Supported", "OpenCV is required for video backgrounds. Install opencv-python.", parent=self)
                return
            try:
                cap = cv2.VideoCapture(file_path)
                if not cap.isOpened():
                    raise Exception("Cannot open video")
                cap.release()
            except Exception:
                messagebox.showerror("Invalid Video", "Selected file is not a valid video.", parent=self)
                return
        else:
            messagebox.showerror("Unsupported File", "Please select an image or video file.", parent=self)
            return
        self.app.data["settings"]["login_bg_path"] = file_path
        self.login_bg_path_label.configure(text=file_path)
        log_activity(self.app, "Change Login Background", file_path)
        save_data(self.app.data)
        self.app.update_branding()
        self._update_login_bg_buttons()
        messagebox.showinfo("Background Updated", "Login background updated successfully.", parent=self)

    def remove_login_bg(self):
        if not self.app.data["settings"].get("login_bg_path", ""):
            messagebox.showinfo("No Background", "No background to remove.", parent=self)
            return
        if messagebox.askyesno("Confirm", "Remove the current login background?", parent=self):
            self.app.data["settings"]["login_bg_path"] = ""
            self.login_bg_path_label.configure(text="No background selected")
            log_activity(self.app, "Remove Login Background", "Background cleared")
            save_data(self.app.data)
            self.app.update_branding()
            self._update_login_bg_buttons()
            messagebox.showinfo("Background Removed", "Login background has been removed successfully.", parent=self)

    def backup_data(self):
        default_name = f"milktea_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = filedialog.asksaveasfilename(
            title="Backup Data File",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=default_name,
            parent=self)
        if not file_path:
            return
        try:
            backup_data = dict(DEFAULT_DATA)
            backup_data.update(self.app.data or {})
            for key, default_value in DEFAULT_DATA.items():
                if key not in backup_data:
                    backup_data[key] = default_value
            with open(file_path, "w", encoding="utf-8") as out:
                json.dump(backup_data, out, indent=2)
            log_activity(self.app, "Backup Data", file_path)
            messagebox.showinfo("Backup Complete", f"Backup saved to:\n{file_path}", parent=self)
        except Exception as e:
            show_error(self, "Backup Failed", "Unable to create backup file.", details=str(e))

    def restore_data(self):
        if not messagebox.askyesno("Confirm Restore",
                                   "Restoring will replace the current system data. Continue?",
                                   parent=self):
            return
        file_path = filedialog.askopenfilename(
            title="Restore Data File",
            filetypes=[("JSON files", "*.json")],
            parent=self)
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as inp:
                new_data = json.load(inp)
            if not isinstance(new_data, dict):
                raise ValueError("Invalid backup format")
            merged_data = dict(DEFAULT_DATA)
            merged_data.update(new_data)
            for key, default_value in DEFAULT_DATA.items():
                if key not in merged_data:
                    merged_data[key] = default_value
            self.app.data = merged_data
            save_data(self.app.data)
            self.logo_path_label.configure(text=self.app.data["settings"].get("logo_path", "") or "No logo selected")
            self.app.update_branding()
            log_activity(self.app, "Restore Data", file_path)
            messagebox.showinfo("Restore Complete", "Data restored successfully. Please refresh or restart.", parent=self)
            self.refresh()
        except Exception as e:
            show_error(self, "Restore Failed", "Unable to restore from file.", details=str(e))

    def refresh(self):
        for row in self.user_tree.get_children():
            self.user_tree.delete(row)
        for u in self.app.data["users"]:
            self.user_tree.insert("", "end", values=(u["id"], u["username"], u["name"], u["role"]))

    def _get_selected_user(self):
        sel = self.user_tree.selection()
        if not sel:
            messagebox.showwarning("Select User", "Please select a user first.", parent=self)
            return None
        uid = self.user_tree.item(sel[0])["values"][0]
        return next((u for u in self.app.data["users"] if u["id"] == uid), None)

    def add_user_dialog(self):
        dlg = Dialog(self.app, "Add User", 420, 520)
        dlg.add_header("New User Account")
        form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        make_label(form, "Name", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        name_e = make_entry(form, "Full name", 300)
        name_e.pack(anchor="w")

        make_label(form, "Username", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        user_e = make_entry(form, "Username", 300)
        user_e.pack(anchor="w")

        make_label(form, "Password", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        pass_frame = ctk.CTkFrame(form, fg_color="transparent")
        pass_frame.pack(anchor="w", fill="x")
        pass_e = make_entry(pass_frame, "Password", 260, show="*")
        pass_e.pack(side="left")
        show_pass_var = ctk.BooleanVar(value=False)
        def toggle_password():
            pass_e.configure(show="" if show_pass_var.get() else "*")
        ctk.CTkCheckBox(pass_frame, text="Show", variable=show_pass_var,
                       command=toggle_password, fg_color=COLORS["accent"],
                       hover_color=COLORS["accent2"], text_color=COLORS["text_secondary"]).pack(side="left", padx=(6, 0))

        make_label(form, "Role", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        role_var = ctk.StringVar(value="Cashier")
        ctk.CTkOptionMenu(form, variable=role_var,
                          values=["Admin", "Manager", "Cashier", "Barista"],
                          fg_color=COLORS["bg_secondary"],
                          button_color=COLORS["accent"], width=200).pack(anchor="w")

        make_label(form, "Phone", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        phone_e = make_entry(form, "Phone number", 300)
        phone_e.pack(anchor="w")

        make_label(form, "Hire Date (YYYY-MM-DD)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        hire_e = make_entry(form, "2024-01-01", 300)
        hire_e.insert(0, datetime.now().strftime("%Y-%m-%d"))
        hire_e.pack(anchor="w")

        make_label(form, "Hourly Rate (₱)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        rate_e = make_entry(form, "e.g. 65", 300)
        rate_e.pack(anchor="w")

        def save():
            name = name_e.get().strip()
            username = user_e.get().strip()
            password = pass_e.get().strip()
            phone = phone_e.get().strip()
            hire_date = hire_e.get().strip()
            hourly_rate_input = rate_e.get().strip()
            if not all([name, username, password, phone, hire_date, hourly_rate_input]):
                show_error(dlg, "Error", "All fields required.")
                return
            if any(u["username"] == username for u in self.app.data["users"]):
                show_error(dlg, "Error", "Username already exists.")
                return
            success, hourly_rate, error = validate_numeric_input(hourly_rate_input, "Hourly rate", allow_zero=False, max_value=100000, is_price=True)
            if not success:
                show_error(dlg, "Error", error)
                return
            try:
                datetime.strptime(hire_date, "%Y-%m-%d")
            except ValueError:
                show_error(dlg, "Error", "Hire date must be YYYY-MM-DD.")
                return
            uid = max((u["id"] for u in self.app.data["users"]), default=0) + 1
            self.app.data["users"].append({
                "id": uid, "username": username,
                "password": hash_password(password),
                "role": role_var.get(), "name": name})
            employee_id = self.app.data.get("next_employee_id", 1)
            self.app.data["employees"].append({
                "id": employee_id,
                "name": name,
                "role": role_var.get(),
                "phone": phone,
                "hire_date": hire_date,
                "hourly_rate": hourly_rate,
                "active": True,
            })
            self.app.data["next_employee_id"] = employee_id + 1
            log_activity(self.app, "Add User", f"{username} ({role_var.get()})")
            log_activity(self.app, "Add Employee", f"{name} ({role_var.get()})")
            save_data(self.app.data)
            self.refresh()
            dlg.destroy()

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", padx=20, pady=10)
        make_button(btn_frame, "Cancel", dlg.destroy, style="secondary").pack(side="right", padx=5)
        make_button(btn_frame, "Save", save, style="primary").pack(side="right", padx=5)

    def edit_user_dialog(self):
        user = self._get_selected_user()
        if not user:
            return
        dlg = Dialog(self.app, "Edit User", 380, 360)
        dlg.add_header("Edit User Account")
        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        make_label(form, "Name", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        name_e = make_entry(form, "Full name", 300)
        name_e.insert(0, user.get("name", ""))
        name_e.pack(anchor="w")

        make_label(form, "Username", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        user_e = make_entry(form, "Username", 300)
        user_e.insert(0, user.get("username", ""))
        user_e.pack(anchor="w")

        make_label(form, "New Password (optional)", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        pass_frame = ctk.CTkFrame(form, fg_color="transparent")
        pass_frame.pack(anchor="w", fill="x")
        pass_e = make_entry(pass_frame, "Leave blank to keep current", 260, show="*")
        pass_e.pack(side="left")
        show_pass_var = ctk.BooleanVar(value=False)
        def toggle_password():
            pass_e.configure(show="" if show_pass_var.get() else "*")
        ctk.CTkCheckBox(pass_frame, text="Show", variable=show_pass_var,
                       command=toggle_password, fg_color=COLORS["accent"],
                       hover_color=COLORS["accent2"], text_color=COLORS["text_secondary"]).pack(side="left", padx=(6, 0))

        make_label(form, "Role", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        role_var = ctk.StringVar(value=user.get("role", "Cashier"))
        ctk.CTkOptionMenu(form, variable=role_var,
                          values=["Admin", "Manager", "Cashier", "Barista"],
                          fg_color=COLORS["bg_secondary"],
                          button_color=COLORS["accent"], width=200).pack(anchor="w")

        def save():
            name = name_e.get().strip()
            username = user_e.get().strip()
            new_password = pass_e.get().strip()
            if not all([name, username]):
                show_error(dlg, "Error", "Name and username are required.")
                return
            if any(u["username"] == username and u["id"] != user["id"] for u in self.app.data["users"]):
                show_error(dlg, "Error", "Username already exists.")
                return
            user["name"] = name
            user["username"] = username
            user["role"] = role_var.get()
            if new_password:
                user["password"] = hash_password(new_password)
                log_activity(self.app, "Change Password", f"User: {username}")
            log_activity(self.app, "Edit User", f"{username} ({role_var.get()})")
            save_data(self.app.data)
            self.refresh()
            dlg.destroy()

        dlg.add_buttons(save, dlg.destroy)

    def delete_user(self):
        sel = self.user_tree.selection()
        if not sel:
            messagebox.showwarning("Select User", "Please select a user first.", parent=self)
            return
        uid = self.user_tree.item(sel[0])["values"][0]
        if uid == self.app.current_user["id"]:
            show_error(self, "Error", "Cannot delete current user.")
            return
        user = next((u for u in self.app.data["users"] if u["id"] == uid), None)
        if user and messagebox.askyesno("Confirm", f"Delete user '{user['username']}'?", parent=self):
            log_activity(self.app, "Delete User", user["username"])
            self.app.data["users"].remove(user)
            save_data(self.app.data)
            self.refresh()


class LogsSection(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.build()

    def build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 16))
        make_label(hdr, "📋 System Logs", "heading").pack(side="left")
        make_button(hdr, "🗑 Delete Selected", self.delete_selected_logs, style="outline", width=150).pack(side="right", padx=4)
        make_button(hdr, "🗑 Clear All", self.clear_all_logs, style="danger", width=110).pack(side="right", padx=4)
        make_button(hdr, "🔄 Refresh", self.refresh, style="secondary", width=110).pack(side="right", padx=4)

        tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        tab_frame.pack(fill="x", pady=(0, 12))
        self.log_type = ctk.StringVar(value="activity")
        ctk.CTkRadioButton(tab_frame, text="📝 Activity Logs", variable=self.log_type, value="activity",
                          command=self.refresh, text_color=COLORS["text_secondary"],
                          fg_color=COLORS["accent"], hover_color=COLORS["accent2"]).pack(side="left", padx=8)
        ctk.CTkRadioButton(tab_frame, text="⚠️  Error Logs", variable=self.log_type, value="error",
                          command=self.refresh, text_color=COLORS["text_secondary"],
                          fg_color=COLORS["accent"], hover_color=COLORS["accent2"]).pack(side="left", padx=8)

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 12))
        make_label(filter_frame, "Filter: ", "small", COLORS["text_muted"]).pack(side="left")
        self.filter_var = ctk.StringVar(value="")
        filter_entry = ctk.CTkEntry(filter_frame, textvariable=self.filter_var, placeholder_text="Search logs...",
                                    width=400, fg_color=COLORS["bg_secondary"], border_color=COLORS["border"],
                                    text_color=COLORS["text_primary"], placeholder_text_color=COLORS["text_muted"],
                                    corner_radius=8)
        filter_entry.pack(side="left", padx=(0, 8))
        filter_entry.bind("<KeyRelease>", lambda e: self.refresh())

        self.card = make_card(self)
        self.card.pack(fill="both", expand=True)

        self.activity_card = make_card(self.card)
        self.activity_card.pack(fill="both", expand=True, padx=8, pady=8)
        act_cols = ("Timestamp", "User", "Action", "Details")
        self.act_tree, self.act_sb = themed_table(self.activity_card, act_cols, height=16)
        self.act_tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.act_sb.pack(side="right", fill="y", pady=2)

        self.error_card = make_card(self.card)
        self.error_card.pack(fill="both", expand=True, padx=8, pady=8)
        err_cols = ("Timestamp", "Type", "Message", "Details")
        self.err_tree, self.err_sb = themed_table(self.error_card, err_cols, height=16)
        self.err_tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.err_sb.pack(side="right", fill="y", pady=2)

        self.refresh()

    def refresh(self):
        log_type = self.log_type.get()
        filter_text = self.filter_var.get().lower()
        if log_type == "activity":
            self.activity_card.pack(fill="both", expand=True, padx=8, pady=8)
            self.error_card.pack_forget()
            for row in self.act_tree.get_children():
                self.act_tree.delete(row)
            logs = self.app.data.get("activity_logs", [])
            for idx, log in enumerate(reversed(logs)):
                if filter_text in str(log).lower():
                    original_idx = len(logs) - 1 - idx
                    self.act_tree.insert("", "end", values=(
                        log.get("timestamp", ""),
                        log.get("user", ""),
                        log.get("action", ""),
                        log.get("details", "")[:50]
                    ), iid=str(original_idx))
        else:
            self.error_card.pack(fill="both", expand=True, padx=8, pady=8)
            self.activity_card.pack_forget()
            for row in self.err_tree.get_children():
                self.err_tree.delete(row)
            logs = self.app.data.get("error_logs", [])
            for idx, log in enumerate(reversed(logs)):
                if filter_text in str(log).lower():
                    original_idx = len(logs) - 1 - idx
                    self.err_tree.insert("", "end", values=(
                        log.get("timestamp", ""),
                        log.get("type", ""),
                        log.get("message", ""),
                        log.get("details", "")[:50]
                    ), iid=str(original_idx))

    def delete_selected_logs(self):
        log_type = self.log_type.get()
        tree = self.act_tree if log_type == "activity" else self.err_tree
        selected = list(tree.selection())
        if not selected:
            messagebox.showwarning("Select", "Please select log rows to delete.", parent=self)
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(selected)} selected {log_type} log(s)?", parent=self):
            return
        key = "activity_logs" if log_type == "activity" else "error_logs"
        logs = self.app.data.get(key, [])
        indices = []
        for iid in selected:
            try:
                indices.append(int(iid))
            except ValueError:
                continue
        for i in sorted(set(indices), reverse=True):
            if 0 <= i < len(logs):
                del logs[i]
        self.app.data[key] = logs
        save_data(self.app.data)
        self.refresh()

    def clear_all_logs(self):
        log_type = self.log_type.get()
        if messagebox.askyesno("Confirm", f"Clear all {log_type} logs? This cannot be undone.", parent=self):
            if log_type == "activity":
                self.app.data["activity_logs"] = []
            else:
                self.app.data["error_logs"] = []
            save_data(self.app.data)
            self.refresh()


class LoginScreen(ctk.CTkFrame):
    def __init__(self, parent, on_login):
        super().__init__(parent, fg_color="transparent")
        self.on_login = on_login
        self.pack(fill="both", expand=True)
        self.bg_label = None
        self.bg_image = None
        self.cap = None
        self.build()

    def build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.bg_label = ctk.CTkLabel(self, text="", fg_color="transparent")
        self.bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        self.bind("<Configure>", self._on_resize)

        logo = make_card(center, width=380)
        logo.pack(padx=8, pady=8)

        self.login_logo_label = ctk.CTkLabel(logo, text="", fg_color="transparent")
        self.login_logo_label.pack(pady=(24, 0))
        self.login_logo_img = None
        shop_name = self.master.data.get("settings", {}).get("shop_name", "Brewster's Cup")
        tagline = self.master.data.get("settings", {}).get("tagline", "Management System") or "Management System"
        self.login_shop_label = ctk.CTkLabel(logo, text=shop_name, font=("Georgia", 32, "bold"),
                                             text_color=COLORS["accent"])
        self.login_shop_label.pack()
        self.login_tagline_label = ctk.CTkLabel(logo, text=tagline, font=FONTS["body"],
                                                text_color=COLORS["text_muted"])
        self.login_tagline_label.pack(pady=(0, 18))

        make_label(logo, "Username", "small", COLORS["text_muted"]).pack(anchor="w", padx=36)
        username_frame = ctk.CTkFrame(logo, fg_color=COLORS["bg_secondary"], corner_radius=12,
                                      border_width=1, border_color=COLORS["border"])
        username_frame.pack(padx=36, pady=(4, 16), fill="x")
        self.user_combo = ctk.CTkComboBox(
            username_frame,
            values=[],
            width=280,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["bg_secondary"],
            text_color=COLORS["text_primary"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent2"],
            corner_radius=12,
            state="normal"
        )
        self.user_combo.pack(side="left", padx=(8, 0), pady=4, fill="both", expand=True)
        self.user_combo.bind("<Return>", lambda e: self.pass_e.focus())

        make_label(logo, "Password", "small", COLORS["text_muted"]).pack(anchor="w", padx=36)
        password_frame = ctk.CTkFrame(logo, fg_color=COLORS["bg_secondary"], corner_radius=12,
                                      border_width=1, border_color=COLORS["border"])
        password_frame.pack(padx=36, pady=(4, 10), fill="x")

        self.pass_e = make_entry(password_frame, "Enter password", 220, show="*")
        self.pass_e.pack(side="left", padx=(8, 0), pady=4, fill="x", expand=True)
        self.pass_e.bind("<Return>", lambda e: self.login())

        self.show_password = False
        self.show_btn = ctk.CTkButton(password_frame, text="👁️",
                                      width=40, height=36,
                                      fg_color=COLORS["bg_secondary"],
                                      hover_color=COLORS["hover"],
                                      text_color=COLORS["text_primary"],
                                      corner_radius=12,
                                      command=self.toggle_show_password)
        self.show_btn.pack(side="right", padx=8, pady=4)

        self.err_lbl = make_label(logo, "", "small", COLORS["danger"])
        self.err_lbl.pack(pady=(0, 6))

        make_button(logo, "Login", self.login, width=320).pack(pady=(4, 14), padx=36)

    def login(self):
        username = self.user_combo.get().strip()
        password = self.pass_e.get().strip()
        if not username or not password:
            self.err_lbl.configure(text="❌ Username and password required.")
            return

        user = next((u for u in self.app_data["users"] if u["username"] == username), None)
        if user and verify_password(user["password"], password):
            if not user["password"].startswith("scrypt$"):
                user["password"] = hash_password(password)
                save_data(self.app_data)
            if user.get("must_change_password"):
                self.prompt_password_change(user)
                return
            self.on_login(user)
            return

        log_error(self.master, "Login Failed", "Invalid username or password", details=f"Username: {username}")
        self.err_lbl.configure(text="❌ Invalid username or password")

    def prompt_password_change(self, user):
        dlg = Dialog(self, "Change Password", 420, 260)
        dlg.add_header("Change Default Password")

        form = ctk.CTkFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20)

        make_label(form, "New Password", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        new_pass_e = make_entry(form, "Enter new password", 320, show="*")
        new_pass_e.pack(anchor="w")
        new_pass_e.bind("<Return>", lambda e: confirm_pass_e.focus())

        make_label(form, "Confirm Password", "small", COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))
        confirm_pass_e = make_entry(form, "Confirm new password", 320, show="*")
        confirm_pass_e.pack(anchor="w")
        confirm_pass_e.bind("<Return>", lambda e: form.focus())

        def save_new_password():
            new_pass = new_pass_e.get().strip()
            confirm = confirm_pass_e.get().strip()
            if not new_pass or not confirm:
                show_error(dlg, "Error", "Both password fields are required.")
                return
            if new_pass != confirm:
                show_error(dlg, "Error", "Passwords do not match.")
                return
            user["password"] = hash_password(new_pass)
            user["must_change_password"] = False
            save_data(self.app_data)
            log_activity(self.master, "Change Password", f"User: {user['username']}")
            dlg.destroy()
            self.on_login(user)

        dlg.add_buttons(save_new_password, dlg.destroy)

    def toggle_show_password(self):
        self.show_password = not self.show_password
        self.pass_e.configure(show="" if self.show_password else "*")
        self.show_btn.configure(text="🙈" if self.show_password else "👁️")

    def set_data(self, data):
        self.app_data = data
        self._refresh_bg_image()
        self._refresh_logo_image()
        self.login_shop_label.configure(text=self.app_data.get("settings", {}).get("shop_name", "Brewster's Cup"))
        self.login_tagline_label.configure(text=self.app_data.get("settings", {}).get("tagline", "Management System") or "Management System")
        usernames = [u["username"] for u in data.get("users", [])]
        self.user_combo.configure(values=usernames)
        self.user_combo.set("")

    def _refresh_logo_image(self):
        logo_path = self.app_data.get("settings", {}).get("logo_path", "") if hasattr(self, "app_data") else ""
        if logo_path and os.path.exists(logo_path) and Image is not None:
            try:
                pil_image = Image.open(logo_path)
                self.login_logo_img = ctk.CTkImage(pil_image, size=(72, 72))
                self.login_logo_label.configure(image=self.login_logo_img, text="")
                return
            except Exception:
                pass
        self.login_logo_img = None
        self.login_logo_label.configure(image=None, text="🧋", font=("Helvetica", 56))

    def _refresh_bg_image(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            self.after_cancel(self._video_update_id) if hasattr(self, '_video_update_id') else None

        bg_path = self.app_data.get("settings", {}).get("login_bg_path", "") if hasattr(self, "app_data") else ""
        if not bg_path or not os.path.exists(bg_path):
            self.bg_image = None
            self.bg_label.configure(image=None, text="", fg_color=COLORS["bg_primary"])
            return

        is_video = bg_path.lower().endswith(('.mp4', '.avi', '.mov'))
        if is_video and cv2 is not None:
            try:
                self.cap = cv2.VideoCapture(bg_path)
                if self.cap.isOpened():
                    self._update_video_frame()
                else:
                    self.cap = None
                    self.bg_label.configure(image=None, text="", fg_color=COLORS["bg_primary"])
            except Exception:
                self.cap = None
                self.bg_label.configure(image=None, text="", fg_color=COLORS["bg_primary"])
        elif Image is not None:
            try:
                pil_image = Image.open(bg_path)
                width = self.winfo_width() or 800
                height = self.winfo_height() or 600
                pil_image.thumbnail((width, height), Image.Resampling.LANCZOS)
                self.bg_image = ctk.CTkImage(pil_image, size=(width, height))
                self.bg_label.configure(image=self.bg_image, text="")
            except Exception:
                self.bg_image = None
                self.bg_label.configure(image=None, text="", fg_color=COLORS["bg_primary"])
        else:
            self.bg_image = None
            self.bg_label.configure(image=None, text="", fg_color=COLORS["bg_primary"])

    def _update_video_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame)
            width = self.winfo_width() or 800
            height = self.winfo_height() or 600
            pil_image.thumbnail((width, height), Image.Resampling.LANCZOS)
            self.bg_image = ctk.CTkImage(pil_image, size=(width, height))
            self.bg_label.configure(image=self.bg_image, text="")
            self._video_update_id = self.after(33, self._update_video_frame)
        else:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._video_update_id = self.after(33, self._update_video_frame)

    def _on_resize(self, event):
        if hasattr(self, 'app_data') and self.app_data.get("settings", {}).get("login_bg_path", ""):
            self._refresh_bg_image()


class LoadingScreen(ctk.CTkToplevel):
    def __init__(self, parent, on_done, width=520, height=260, duration_ms=1400):
        super().__init__(parent)
        self._on_done = on_done
        self._duration_ms = max(600, int(duration_ms))
        self._tick_ms = 30
        self._progress = 0.0

        self.title("Loading...")
        self.geometry(f"{width}x{height}")
        self.configure(fg_color=COLORS["bg_primary"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = self.winfo_screenwidth() // 2 - width // 2
        y = self.winfo_screenheight() // 2 - height // 2
        self.geometry(f"+{x}+{y}")

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(wrap, text="🧋", font=("Helvetica", 46)).pack(pady=(0, 6))
        ctk.CTkLabel(wrap, text=parent.data.get("settings", {}).get("shop_name", "Brewster's Cup"),
                     font=("Georgia", 22, "bold"), text_color=COLORS["accent"]).pack()
        self.msg = ctk.CTkLabel(wrap, text="Starting up...", font=FONTS["body"],
                                text_color=COLORS["text_secondary"])
        self.msg.pack(pady=(8, 16))

        self.bar = ctk.CTkProgressBar(wrap, width=420, height=16,
                                      fg_color=COLORS["bg_secondary"],
                                      progress_color=COLORS["accent"])
        self.bar.pack()
        self.bar.set(0)

        self.pct = ctk.CTkLabel(wrap, text="0%", font=FONTS["small"],
                                text_color=COLORS["text_muted"])
        self.pct.pack(pady=(8, 0))

        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.after(self._tick_ms, self._tick)

    def _tick(self):
        steps = max(1, self._duration_ms // self._tick_ms)
        self._progress = min(1.0, self._progress + 1.0 / steps)

        if self._progress < 0.35:
            self.msg.configure(text="Loading data...")
        elif self._progress < 0.7:
            self.msg.configure(text="Preparing interface...")
        else:
            self.msg.configure(text="Almost ready...")

        self.bar.set(self._progress)
        self.pct.configure(text=f"{int(self._progress * 100)}%")

        if self._progress >= 1.0:
            try:
                self.grab_release()
            except Exception:
                pass
            self.destroy()
            self._on_done()
            return

        self.after(self._tick_ms, self._tick)
