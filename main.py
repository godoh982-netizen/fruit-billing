import os
import sqlite3
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView

SHOP_NAME = "FRESH FRUIT SHOP"
GST_RATE = 5.0
CURRENCY = "₹"

DEFAULT_PRODUCTS = [
    ("Apple", 85, 100),
    ("Banana", 60, 100),
    ("Mango", 95, 100),
    ("Orange", 70, 100),
    ("Grapes", 80, 100),
    ("Pineapple", 100, 50),
    ("Papaya", 55, 50),
    ("Watermelon", 40, 50),
    ("Guava", 65, 50),
    ("Pomegranate", 120, 50),
]

KV = r"""
#:import dp kivy.metrics.dp

<MainRoot>:
    orientation: "vertical"
    padding: dp(8)
    spacing: dp(6)

    BoxLayout:
        size_hint_y: None
        height: dp(55)
        spacing: dp(6)
        Label:
            text: "🍎 " + app.shop_name
            font_size: "21sp"
            bold: True
        Button:
            text: "New Bill"
            size_hint_x: .28
            on_release: app.new_bill()

    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(6)
        TextInput:
            id: search
            hint_text: "🔎 Search product..."
            multiline: False
            on_text: app.refresh_products(self.text)
        TextInput:
            id: customer
            hint_text: "👤 Customer name"
            multiline: False
            size_hint_x: .48

    BoxLayout:
        size_hint_y: .45
        spacing: dp(6)

        ScrollView:
            do_scroll_x: False
            GridLayout:
                id: product_grid
                cols: 2
                spacing: dp(6)
                size_hint_y: None
                padding: dp(2)
                height: self.minimum_height

        BoxLayout:
            orientation: "vertical"
            size_hint_x: .55
            spacing: dp(5)

            Label:
                text: "🛒 CART"
                bold: True
                font_size: "18sp"
                size_hint_y: None
                height: dp(35)

            ScrollView:
                do_scroll_x: False
                GridLayout:
                    id: cart_grid
                    cols: 1
                    spacing: dp(4)
                    size_hint_y: None
                    height: self.minimum_height

    BoxLayout:
        orientation: "vertical"
        size_hint_y: .25
        spacing: dp(3)

        Label:
            id: subtotal
            text: "Subtotal: ₹0.00"
            halign: "right"
            text_size: self.size
        Label:
            id: discount
            text: "Discount: ₹0.00"
            halign: "right"
            text_size: self.size
        Label:
            id: gst
            text: "GST: ₹0.00"
            halign: "right"
            text_size: self.size
        Label:
            id: total
            text: "TOTAL: ₹0.00"
            font_size: "21sp"
            bold: True
            halign: "right"
            text_size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(52)
        spacing: dp(5)
        Button:
            text: "💰 Discount"
            on_release: app.discount_popup()
        Button:
            text: "💾 Save Bill"
            on_release: app.save_bill()
        Button:
            text: "📤 Share"
            on_release: app.share_bill()
        Button:
            text: "📊 History"
            on_release: app.show_history()
        Button:
            text: "📦 Stock"
            on_release: app.show_stock()
"""


class MainRoot(BoxLayout):
    pass


class FruitBillingApp(App):
    shop_name = StringProperty(SHOP_NAME)

    def build(self):
        self.title = SHOP_NAME
        self.cart = {}
        self.discount_percent = 0.0
        self.current_bill_text = ""
        Builder.load_string(KV)
        self.init_db()
        self.refresh_products()
        self.refresh_cart()
        return MainRoot()

    # ---------- Database ----------
    def db_path(self):
        return os.path.join(self.user_data_dir, "fruit_billing.db")

    def bills_dir(self):
        path = os.path.join(self.user_data_dir, "bills")
        os.makedirs(path, exist_ok=True)
        return path

    def db(self):
        return sqlite3.connect(self.db_path())

    def init_db(self):
        with self.db() as con:
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    price REAL NOT NULL,
                    stock INTEGER NOT NULL DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_no INTEGER UNIQUE NOT NULL,
                    customer TEXT,
                    subtotal REAL NOT NULL,
                    discount_percent REAL NOT NULL,
                    discount_amount REAL NOT NULL,
                    gst REAL NOT NULL,
                    total REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bill_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bill_no INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    amount REAL NOT NULL
                )
            """)
            count = cur.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count == 0:
                cur.executemany(
                    "INSERT INTO products(name,price,stock) VALUES(?,?,?)",
                    DEFAULT_PRODUCTS
                )

    # ---------- Products ----------
    def get_products(self, search=""):
        with self.db() as con:
            if search.strip():
                return con.execute(
                    "SELECT id,name,price,stock FROM products "
                    "WHERE name LIKE ? ORDER BY name",
                    (f"%{search.strip()}%",)
                ).fetchall()
            return con.execute(
                "SELECT id,name,price,stock FROM products ORDER BY name"
            ).fetchall()

    def refresh_products(self, search=""):
        grid = self.root.ids.product_grid
        grid.clear_widgets()

        for pid, name, price, stock in self.get_products(search):
            btn = Button(
                text=f"{name}\n{CURRENCY}{price:.2f}\nStock: {stock}",
                font_size="15sp",
                size_hint_y=None,
                height=dp(78),
                disabled=(stock <= 0),
            )
            btn.bind(on_release=lambda _, p=pid: self.add_product(p))
            grid.add_widget(btn)

    def add_product(self, product_id):
        with self.db() as con:
            row = con.execute(
                "SELECT name,price,stock FROM products WHERE id=?",
                (product_id,)
            ).fetchone()

        if not row:
            return

        name, price, stock = row
        old_qty = self.cart.get(product_id, {}).get("quantity", 0)
        if old_qty >= stock:
            self.message("Stock limit reached.")
            return

        self.cart[product_id] = {
            "name": name,
            "price": float(price),
            "quantity": old_qty + 1,
        }
        self.refresh_cart()

    # ---------- Cart ----------
    def refresh_cart(self):
        grid = self.root.ids.cart_grid
        grid.clear_widgets()

        for pid, item in self.cart.items():
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(2))

            row.add_widget(Label(
                text=f"{item['name']}  x{item['quantity']}",
                halign="left",
                text_size=(None, None)
            ))

            minus = Button(text="−", size_hint_x=None, width=dp(42))
            plus = Button(text="+", size_hint_x=None, width=dp(42))
            remove = Button(text="🗑", size_hint_x=None, width=dp(45))

            minus.bind(on_release=lambda _, p=pid: self.change_qty(p, -1))
            plus.bind(on_release=lambda _, p=pid: self.change_qty(p, 1))
            remove.bind(on_release=lambda _, p=pid: self.remove_product(p))

            row.add_widget(minus)
            row.add_widget(plus)
            row.add_widget(remove)
            grid.add_widget(row)

        self.update_totals()

    def change_qty(self, product_id, delta):
        if product_id not in self.cart:
            return

        new_qty = self.cart[product_id]["quantity"] + delta

        with self.db() as con:
            stock = con.execute(
                "SELECT stock FROM products WHERE id=?",
                (product_id,)
            ).fetchone()[0]

        if new_qty <= 0:
            self.cart.pop(product_id, None)
        elif new_qty <= stock:
            self.cart[product_id]["quantity"] = new_qty
        else:
            self.message("Not enough stock.")

        self.refresh_cart()

    def remove_product(self, product_id):
        self.cart.pop(product_id, None)
        self.refresh_cart()

    # ---------- Totals ----------
    def calculate(self):
        subtotal = sum(
            item["price"] * item["quantity"]
            for item in self.cart.values()
        )
        discount = subtotal * self.discount_percent / 100.0
        taxable = max(0.0, subtotal - discount)
        gst = taxable * GST_RATE / 100.0
        total = taxable + gst
        return subtotal, discount, gst, total

    def update_totals(self):
        subtotal, discount, gst, total = self.calculate()
        self.root.ids.subtotal.text = f"Subtotal: {CURRENCY}{subtotal:.2f}"
        self.root.ids.discount.text = (
            f"Discount ({self.discount_percent:g}%): {CURRENCY}{discount:.2f}"
        )
        self.root.ids.gst.text = f"GST ({GST_RATE:g}%): {CURRENCY}{gst:.2f}"
        self.root.ids.total.text = f"TOTAL: {CURRENCY}{total:.2f}"

    def discount_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        inp = TextInput(
            text=str(self.discount_percent),
            hint_text="Discount % (0-100)",
            input_filter="float",
            multiline=False,
            size_hint_y=None,
            height=dp(45)
        )
        apply_btn = Button(text="Apply", size_hint_y=None, height=dp(48))
        box.add_widget(inp)
        box.add_widget(apply_btn)

        popup = Popup(title="Discount", content=box, size_hint=(.85, .35))

        def apply(_):
            try:
                value = max(0.0, min(100.0, float(inp.text or 0)))
                self.discount_percent = value
                self.update_totals()
                popup.dismiss()
            except ValueError:
                self.message("Enter a valid discount.")

        apply_btn.bind(on_release=apply)
        popup.open()

    # ---------- Bills ----------
    def next_bill_no(self):
        with self.db() as con:
            row = con.execute("SELECT MAX(bill_no) FROM bills").fetchone()
        return max(1000, row[0] or 1000) + 1

    def create_bill_text(self, bill_no, customer, created_at,
                         subtotal, discount, gst, total):
        lines = [
            SHOP_NAME,
            "=" * 32,
            f"Bill No : {bill_no}",
            f"Date    : {created_at}",
            f"Customer: {customer or 'Walk-in Customer'}",
            "-" * 32,
        ]

        for item in self.cart.values():
            amount = item["price"] * item["quantity"]
            lines.append(
                f"{item['name']} x{item['quantity']} "
                f"@ {CURRENCY}{item['price']:.2f} = {CURRENCY}{amount:.2f}"
            )

        lines += [
            "-" * 32,
            f"Subtotal : {CURRENCY}{subtotal:.2f}",
            f"Discount : {CURRENCY}{discount:.2f}",
            f"GST      : {CURRENCY}{gst:.2f}",
            f"TOTAL    : {CURRENCY}{total:.2f}",
            "=" * 32,
            "Thank you!",
        ]
        return "\n".join(lines)

    def save_bill(self):
        if not self.cart:
            self.message("Cart is empty.")
            return

        customer = self.root.ids.customer.text.strip()
        subtotal, discount, gst, total = self.calculate()
        bill_no = self.next_bill_no()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.db() as con:
            # Check stock again immediately before saving.
            for pid, item in self.cart.items():
                stock = con.execute(
                    "SELECT stock FROM products WHERE id=?", (pid,)
                ).fetchone()[0]
                if item["quantity"] > stock:
                    self.message(f"Insufficient stock: {item['name']}")
                    return

            con.execute("""
                INSERT INTO bills
                (bill_no,customer,subtotal,discount_percent,discount_amount,
                 gst,total,created_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, (
                bill_no, customer, subtotal, self.discount_percent,
                discount, gst, total, created_at
            ))

            for pid, item in self.cart.items():
                amount = item["price"] * item["quantity"]
                con.execute("""
                    INSERT INTO bill_items
                    (bill_no,product_name,price,quantity,amount)
                    VALUES(?,?,?,?,?)
                """, (
                    bill_no, item["name"], item["price"],
                    item["quantity"], amount
                ))
                con.execute(
                    "UPDATE products SET stock=stock-? WHERE id=?",
                    (item["quantity"], pid)
                )

        self.current_bill_text = self.create_bill_text(
            bill_no, customer, created_at, subtotal, discount, gst, total
        )

        bill_path = os.path.join(self.bills_dir(), f"bill_{bill_no}.txt")
        with open(bill_path, "w", encoding="utf-8") as f:
            f.write(self.current_bill_text)

        self.message(f"Bill #{bill_no} saved.")
        self.cart.clear()
        self.discount_percent = 0.0
        self.root.ids.customer.text = ""
        self.refresh_products()
        self.refresh_cart()

    def new_bill(self):
        self.cart.clear()
        self.discount_percent = 0.0
        self.current_bill_text = ""
        self.root.ids.customer.text = ""
        self.refresh_products()
        self.refresh_cart()

    # ---------- History / Stock ----------
    def show_history(self):
        with self.db() as con:
            rows = con.execute("""
                SELECT bill_no,customer,total,created_at
                FROM bills ORDER BY id DESC LIMIT 50
            """).fetchall()

        text = "\n".join(
            f"#{b} | {c or 'Walk-in'} | {CURRENCY}{t:.2f} | {d}"
            for b, c, t, d in rows
        ) or "No sales yet."

        self.text_popup("Sales History", text)

    def show_stock(self):
        rows = self.get_products()
        text = "\n".join(
            f"{name}: {stock} | {CURRENCY}{price:.2f}"
            for _, name, price, stock in rows
        )
        self.text_popup("Inventory / Stock", text)

    # ---------- Android sharing ----------
    def share_bill(self):
        if not self.current_bill_text:
            self.message("Save a bill first.")
            return

        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")

            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType("text/plain")
            intent.putExtra(
                Intent.EXTRA_TEXT,
                String(self.current_bill_text)
            )
            chooser = Intent.createChooser(intent, "Share Bill")
            PythonActivity.mActivity.startActivity(chooser)
        except Exception as exc:
            self.message(f"Share unavailable: {exc}")

    # ---------- UI helpers ----------
    def message(self, text):
        Popup(
            title="Fruit Billing",
            content=Label(text=text),
            size_hint=(.82, .25)
        ).open()

    def text_popup(self, title, text):
        scroll = ScrollView()
        label = Label(
            text=text,
            size_hint_y=None,
            halign="left",
            valign="top",
            padding=(dp(8), dp(8))
        )
        label.bind(
            texture_size=lambda inst, value: setattr(
                inst, "height", max(value[1], dp(80))
            )
        )
        scroll.add_widget(label)
        Popup(
            title=title,
            content=scroll,
            size_hint=(.92, .8)
        ).open()


if __name__ == "__main__":
    FruitBillingApp().run()
