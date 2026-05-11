-- =============================================================================
--  BubbleBrew Milk Tea Shop — MySQL Additions
--  Procedures, Triggers, Functions, and Views
--  Compatible with milktea_mysql_schema.sql
-- =============================================================================

DELIMITER $$

-- =============================================================================
--  FUNCTIONS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fn_apply_promo
--   Applies a promo code to a subtotal and returns the discounted total.
--   Returns the original amount if the promo is invalid/inactive.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_apply_promo$$
CREATE FUNCTION fn_apply_promo(subtotal DECIMAL(12,2), promo_code_in VARCHAR(50))
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    DECLARE promo_type  VARCHAR(50)  DEFAULT '';
    DECLARE promo_value DECIMAL(10,2) DEFAULT 0;
    DECLARE is_active   TINYINT(1)   DEFAULT 0;
    DECLARE result      DECIMAL(12,2);

    SELECT type, value, active
      INTO promo_type, promo_value, is_active
      FROM promos
     WHERE code = promo_code_in
     LIMIT 1;

    IF is_active = 0 OR promo_type = '' THEN
        RETURN subtotal;
    END IF;

    IF promo_type = 'percent' THEN
        SET result = subtotal - (subtotal * promo_value / 100);
    ELSEIF promo_type = 'fixed' THEN
        SET result = subtotal - promo_value;
    ELSE
        SET result = subtotal;
    END IF;

    RETURN IF(result < 0, 0, result);
END$$


-- -----------------------------------------------------------------------------
-- fn_employee_hours_worked
--   Counts distinct working days for an employee within a date range
--   by looking at their attendance_logs with status = 'Time In'.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_employee_hours_worked$$
CREATE FUNCTION fn_employee_hours_worked(
    emp_id_in  INT,
    date_from  DATE,
    date_to    DATE
)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE day_count INT DEFAULT 0;

    SELECT COUNT(DISTINCT DATE(timestamp))
      INTO day_count
      FROM attendance_logs
     WHERE employee_id = emp_id_in
       AND status      = 'Time In'
       AND DATE(timestamp) BETWEEN date_from AND date_to;

    RETURN day_count;
END$$


-- -----------------------------------------------------------------------------
-- fn_inventory_value
--   Returns the total value of all inventory stock (quantity × cost_per_unit).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_inventory_value$$
CREATE FUNCTION fn_inventory_value()
RETURNS DECIMAL(14,2)
READS SQL DATA
BEGIN
    DECLARE total DECIMAL(14,2) DEFAULT 0;

    SELECT IFNULL(SUM(quantity * cost_per_unit), 0)
      INTO total
      FROM inventory;

    RETURN total;
END$$


-- -----------------------------------------------------------------------------
-- fn_daily_revenue
--   Returns the total revenue for a given date.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_daily_revenue$$
CREATE FUNCTION fn_daily_revenue(target_date DATE)
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    DECLARE rev DECIMAL(12,2) DEFAULT 0;

    SELECT IFNULL(SUM(total_amount), 0)
      INTO rev
      FROM orders
     WHERE DATE(order_datetime) = target_date;

    RETURN rev;
END$$


-- =============================================================================
--  STORED PROCEDURES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- sp_restock_inventory
--   Adds quantity to an inventory item and logs the activity.
-- -----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_restock_inventory$$
CREATE PROCEDURE sp_restock_inventory(
    IN p_inventory_id INT,
    IN p_qty_added    DECIMAL(12,2),
    IN p_done_by      VARCHAR(255)
)
BEGIN
    DECLARE v_item_name VARCHAR(255) DEFAULT '';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT name INTO v_item_name FROM inventory WHERE id = p_inventory_id;

    IF v_item_name = '' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Inventory item not found';
    END IF;

    UPDATE inventory
       SET quantity = quantity + p_qty_added
     WHERE id = p_inventory_id;

    -- Log the restock action
    INSERT INTO activity_logs (id, timestamp, `user`, action, details)
    VALUES (
        (SELECT IFNULL(MAX(id), 0) + 1 FROM activity_logs al_inner),
        NOW(),
        p_done_by,
        'Restock Inventory',
        CONCAT('Restocked "', v_item_name, '" by ', p_qty_added, ' units')
    );

    COMMIT;
END$$


-- -----------------------------------------------------------------------------
-- sp_get_sales_report
--   Returns a day-by-day sales summary between two dates.
-- -----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_get_sales_report$$
CREATE PROCEDURE sp_get_sales_report(
    IN p_date_from DATE,
    IN p_date_to   DATE
)
BEGIN
    SELECT
        DATE(o.order_datetime)      AS sale_date,
        COUNT(DISTINCT o.id)        AS total_orders,
        SUM(oi.quantity)            AS total_items_sold,
        SUM(o.total_amount)         AS total_revenue,
        AVG(o.total_amount)         AS avg_order_value,
        SUM(CASE WHEN o.promo_id IS NOT NULL THEN 1 ELSE 0 END) AS promo_orders
    FROM orders o
    LEFT JOIN order_items oi ON oi.order_id = o.id
    WHERE DATE(o.order_datetime) BETWEEN p_date_from AND p_date_to
    GROUP BY DATE(o.order_datetime)
    ORDER BY sale_date;
END$$


-- -----------------------------------------------------------------------------
-- sp_get_top_menu_items
--   Returns the top N best-selling menu items within a date range.
-- -----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_get_top_menu_items$$
CREATE PROCEDURE sp_get_top_menu_items(
    IN p_date_from DATE,
    IN p_date_to   DATE,
    IN p_limit     INT
)
BEGIN
    SELECT
        mi.id,
        mi.name                     AS item_name,
        c.name                      AS category,
        SUM(oi.quantity)            AS total_qty_sold,
        SUM(oi.line_total)          AS total_revenue
    FROM order_items oi
    JOIN orders o      ON o.id  = oi.order_id
    JOIN menu_items mi ON mi.id = oi.menu_item_id
    LEFT JOIN categories c ON c.id = mi.category_id
    WHERE DATE(o.order_datetime) BETWEEN p_date_from AND p_date_to
    GROUP BY mi.id, mi.name, c.name
    ORDER BY total_qty_sold DESC
    LIMIT p_limit;
END$$

-- =============================================================================
--  TRIGGERS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- trg_after_order_insert
--   After a new order is created, deduct recipe ingredients from inventory.
--   Runs per row — iterates order_items belonging to the new order.
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_order_insert$$
CREATE TRIGGER trg_after_order_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    -- Deduct inventory based on recipes for each order item
    UPDATE inventory inv
    JOIN (
        SELECT r.inventory_id,
               SUM(r.qty * oi.quantity) AS total_used
          FROM order_items oi
          JOIN recipes r ON r.menu_item_id = oi.menu_item_id
         WHERE oi.order_id = NEW.id
         GROUP BY r.inventory_id
    ) deductions ON deductions.inventory_id = inv.id
    SET inv.quantity = GREATEST(inv.quantity - deductions.total_used, 0);
END$$


-- -----------------------------------------------------------------------------
-- trg_before_order_item_insert
--   Validates that the menu item exists and is available before inserting
--   an order item, preventing ghost line items.
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_before_order_item_insert$$
CREATE TRIGGER trg_before_order_item_insert
BEFORE INSERT ON order_items
FOR EACH ROW
BEGIN
    DECLARE v_available TINYINT(1) DEFAULT 0;

    SELECT available INTO v_available
      FROM menu_items
     WHERE id = NEW.menu_item_id
     LIMIT 1;

    IF v_available = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Cannot add order item: menu item is unavailable or does not exist';
    END IF;
END$$


-- -----------------------------------------------------------------------------
-- trg_after_employee_insert
--   Logs a welcome activity entry whenever a new employee is created.
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_employee_insert$$
CREATE TRIGGER trg_after_employee_insert
AFTER INSERT ON employees
FOR EACH ROW
BEGIN
    INSERT INTO activity_logs (id, timestamp, `user`, action, details)
    VALUES (
        (SELECT IFNULL(MAX(id), 0) + 1 FROM activity_logs al_inner),
        NOW(),
        'System',
        'New Employee Added',
        CONCAT('Employee "', NEW.name, '" (', NEW.role, ') added on ', CURDATE())
    );
END$$


-- -----------------------------------------------------------------------------
-- trg_after_expense_insert
--   Logs each new expense entry into activity_logs automatically.
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_after_expense_insert$$
CREATE TRIGGER trg_after_expense_insert
AFTER INSERT ON expenses
FOR EACH ROW
BEGIN
    INSERT INTO activity_logs (id, timestamp, `user`, action, details)
    VALUES (
        (SELECT IFNULL(MAX(id), 0) + 1 FROM activity_logs al_inner),
        NOW(),
        'System',
        'Expense Recorded',
        CONCAT('Category: ', NEW.category, ' | Desc: ', IFNULL(NEW.description, ''),
               ' | Amount: ₱', NEW.amount)
    );
END$$


-- =============================================================================
--  VIEWS
-- =============================================================================

DELIMITER ;

-- -----------------------------------------------------------------------------
-- vw_low_stock_items
--   Lists all inventory items currently at or below their alert threshold.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_low_stock_items;
CREATE VIEW vw_low_stock_items AS
SELECT
    id,
    name,
    unit,
    quantity,
    threshold,
    cost_per_unit,
    (quantity * cost_per_unit)   AS stock_value,
    (threshold - quantity)       AS deficit
FROM inventory
WHERE quantity <= threshold
ORDER BY deficit DESC;


-- -----------------------------------------------------------------------------
-- vw_daily_sales_summary
--   Aggregates orders by date, useful for the Reports section dashboard.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_daily_sales_summary;
CREATE VIEW vw_daily_sales_summary AS
SELECT
    DATE(o.order_datetime)              AS sale_date,
    COUNT(DISTINCT o.id)                AS total_orders,
    IFNULL(SUM(oi.quantity), 0)         AS total_items_sold,
    IFNULL(SUM(o.total_amount), 0)      AS total_revenue,
    IFNULL(AVG(o.total_amount), 0)      AS avg_order_value,
    COUNT(DISTINCT CASE WHEN o.promo_id IS NOT NULL THEN o.id END) AS promo_orders
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.id
GROUP BY DATE(o.order_datetime)
ORDER BY sale_date DESC;


-- -----------------------------------------------------------------------------
-- vw_menu_item_revenue
--   Shows lifetime revenue and units sold per menu item, useful for the
--   "Top Items" section in Reports.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_menu_item_revenue;
CREATE VIEW vw_menu_item_revenue AS
SELECT
    mi.id                               AS menu_item_id,
    mi.name                             AS item_name,
    c.name                              AS category,
    mi.available,
    IFNULL(SUM(oi.quantity), 0)         AS total_qty_sold,
    IFNULL(SUM(oi.line_total), 0)       AS total_revenue,
    IFNULL(AVG(oi.unit_price), 0)       AS avg_unit_price
FROM menu_items mi
LEFT JOIN categories c     ON c.id  = mi.category_id
LEFT JOIN order_items oi   ON oi.menu_item_id = mi.id
GROUP BY mi.id, mi.name, c.name, mi.available
ORDER BY total_revenue DESC;


-- -----------------------------------------------------------------------------
-- vw_employee_attendance_summary
--   Counts Time In / Time Out events per active employee.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_employee_attendance_summary;
CREATE VIEW vw_employee_attendance_summary AS
SELECT
    e.id                                            AS employee_id,
    e.name                                          AS employee_name,
    e.role,
    e.hourly_rate,
    COUNT(CASE WHEN al.status = 'Time In'  THEN 1 END) AS total_time_ins,
    COUNT(CASE WHEN al.status = 'Time Out' THEN 1 END) AS total_time_outs,
    MAX(al.timestamp)                               AS last_attendance
FROM employees e
LEFT JOIN attendance_logs al ON al.employee_id = e.id
WHERE e.active = 1
GROUP BY e.id, e.name, e.role, e.hourly_rate
ORDER BY e.name;


-- -----------------------------------------------------------------------------
-- vw_promo_usage
--   Shows how many orders used each promo code and the total discount given.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_promo_usage;
CREATE VIEW vw_promo_usage AS
SELECT
    p.id,
    p.code,
    p.description,
    p.type,
    p.value,
    p.active,
    COUNT(o.id)                         AS times_used,
    IFNULL(SUM(o.total_amount), 0)      AS total_revenue_with_promo
FROM promos p
LEFT JOIN orders o ON o.promo_id = p.id
GROUP BY p.id, p.code, p.description, p.type, p.value, p.active
ORDER BY times_used DESC;


-- -----------------------------------------------------------------------------
-- vw_order_detail
--   Flat view of every order line including topping names — useful for
--   receipt printing and the order history screen.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_order_detail;
CREATE VIEW vw_order_detail AS
SELECT
    o.id                                AS order_id,
    o.order_datetime,
    o.customer_name,
    p.code                              AS promo_code,
    pm.method                           AS payment_method,
    u.name                              AS created_by,
    o.total_amount                      AS order_total,
    oi.id                               AS order_item_id,
    mi.name                             AS item_name,
    oi.size,
    oi.quantity,
    oi.unit_price,
    oi.line_total,
    t.name                              AS topping_name,
    oit.quantity                        AS topping_qty,
    oit.price                           AS topping_price
FROM orders o
JOIN  order_items oi         ON oi.order_id     = o.id
JOIN  menu_items mi          ON mi.id           = oi.menu_item_id
LEFT JOIN order_item_toppings oit ON oit.order_item_id = oi.id
LEFT JOIN toppings t         ON t.id            = oit.topping_id
LEFT JOIN promos p           ON p.id            = o.promo_id
LEFT JOIN payment_methods pm ON pm.id           = o.payment_method_id
LEFT JOIN users u            ON u.id            = o.created_by_user_id
ORDER BY o.order_datetime DESC, oi.id;

