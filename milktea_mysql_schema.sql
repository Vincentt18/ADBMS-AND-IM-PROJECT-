CREATE TABLE IF NOT EXISTS app_meta (
    entity VARCHAR(64) PRIMARY KEY,
    next_id INT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS categories (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sugar_levels (
    id INT PRIMARY KEY,
    level VARCHAR(50) NOT NULL,
    sort_order INT NOT NULL
);

CREATE TABLE IF NOT EXISTS ice_levels (
    id INT PRIMARY KEY,
    level VARCHAR(50) NOT NULL,
    sort_order INT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(100) PRIMARY KEY,
    `value` TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    must_change_password TINYINT(1) NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    quantity DECIMAL(12,2) NOT NULL DEFAULT 0,
    threshold DECIMAL(12,2) NOT NULL DEFAULT 0,
    cost_per_unit DECIMAL(12,4) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS employees (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    phone VARCHAR(50) DEFAULT '',
    hire_date DATE DEFAULT NULL,
    hourly_rate DECIMAL(10,2) NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS toppings (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL DEFAULT 0,
    available TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS promos (
    id INT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    type VARCHAR(50) NOT NULL,
    value DECIMAL(10,2) NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payment_methods (
    id INT PRIMARY KEY,
    method VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS menu_items (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INT,
    available TINYINT(1) NOT NULL DEFAULT 1,
    image_path VARCHAR(500) DEFAULT '',
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS menu_prices (
    menu_item_id INT NOT NULL,
    `size` VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (menu_item_id, `size`),
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);

CREATE TABLE IF NOT EXISTS recipes (
    menu_item_id INT NOT NULL,
    inventory_id INT NOT NULL,
    qty DECIMAL(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (menu_item_id, inventory_id),
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id),
    FOREIGN KEY (inventory_id) REFERENCES inventory(id)
);

CREATE TABLE IF NOT EXISTS attendance_logs (
    id INT PRIMARY KEY,
    employee_id INT,
    status VARCHAR(50) DEFAULT '',
    timestamp DATETIME DEFAULT NULL,
    time_out DATETIME DEFAULT NULL,
    hours DECIMAL(5,2) DEFAULT 0.0,
    note TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY,
    order_datetime DATETIME DEFAULT NULL,
    customer_name VARCHAR(255) DEFAULT '',
    total_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    promo_id INT DEFAULT NULL,
    created_by_user_id INT DEFAULT NULL,
    payment_method_id INT DEFAULT NULL,
    notes TEXT,
    FOREIGN KEY (promo_id) REFERENCES promos(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id),
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT,
    `size` VARCHAR(50) DEFAULT '',
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    line_total DECIMAL(12,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);

CREATE TABLE IF NOT EXISTS order_item_toppings (
    order_item_id INT NOT NULL,
    topping_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    price DECIMAL(10,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (order_item_id, topping_id),
    FOREIGN KEY (order_item_id) REFERENCES order_items(id),
    FOREIGN KEY (topping_id) REFERENCES toppings(id)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INT PRIMARY KEY,
    timestamp DATETIME DEFAULT NULL,
    `user` VARCHAR(255) DEFAULT '',
    action VARCHAR(255) DEFAULT '',
    details TEXT
);

CREATE TABLE IF NOT EXISTS error_logs (
    id INT PRIMARY KEY,
    timestamp DATETIME DEFAULT NULL,
    `type` VARCHAR(100) DEFAULT '',
    message TEXT,
    details TEXT
);

INSERT INTO app_meta (entity, next_id) VALUES
    ('users', 5),
    ('employees', 4),
    ('inventory', 9),
    ('toppings', 7),
    ('promos', 4),
    ('menu_items', 9),
    ('expenses', 4),
    ('orders', 1001),
    ('attendance_logs', 1),
    ('activity_logs', 1),
    ('error_logs', 1)
ON DUPLICATE KEY UPDATE next_id = VALUES(next_id);

DROP VIEW IF EXISTS vw_active_menu_items;
CREATE VIEW vw_active_menu_items AS
SELECT mi.id, mi.name, c.name AS category, mi.available, mi.image_path, mp.`size`, mp.price
FROM menu_items mi
LEFT JOIN categories c ON mi.category_id = c.id
LEFT JOIN menu_prices mp ON mp.menu_item_id = mi.id;

DROP VIEW IF EXISTS vw_order_summary;
CREATE VIEW vw_order_summary AS
SELECT o.id,
       o.order_datetime,
       o.customer_name,
       o.total_amount,
       p.code AS promo_code,
       u.name AS created_by,
       pm.method AS payment_method,
       COUNT(oi.id) AS item_count
FROM orders o
LEFT JOIN promos p ON p.id = o.promo_id
LEFT JOIN users u ON u.id = o.created_by_user_id
LEFT JOIN payment_methods pm ON pm.id = o.payment_method_id
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, p.code, u.name, pm.method;

