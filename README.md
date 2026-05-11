# Milk Tea Shop Management System

A Python desktop application for managing milk tea shop operations, including menu management, POS, inventory, employees, attendance, reports, promotions, and logs.

## Features

- CustomTkinter GUI with multiple management sections
- MySQL-based persistence for menu, inventory, orders, employees, and settings
- Append-only logging for activity and error history
- Session management with automatic timeout
- Role-based access control for sections and actions

## Repository Structure

- `app.py` - Main application entry point and GUI controller
- `sections.py` - UI section classes and screen definitions
- `models.py` - Data persistence and save/load logic
- `database.py` - MySQL connection and persistence helpers
- `controller.py` - Permissions, session timeout, and role logic
- `utils.py` - Helper functions, constants, and logging utilities
- `milktea_mysql_schema.sql` - Database schema creation script
- `milktea_mysql_additions.sql` - Optional additional schema or seed data
- `backup/` - Backup files folder
- `receipts/` - Stored receipt CSV files

## Requirements

- Python 3.9+
- `customtkinter`
- `mysql-connector-python`
- `Pillow` (optional, for logo image support)
- MySQL server accessible with configured credentials

## Setup

1. Install Python dependencies:

```bash
pip install customtkinter mysql-connector-python Pillow
```

2. Create the MySQL database and tables:

```bash
mysql -u root -p < milktea_mysql_schema.sql
```

If you want additional default data, apply:

```bash
mysql -u root -p < milktea_mysql_additions.sql
```

3. Configure the database connection if needed by setting environment variables:

- `MILKTEA_DB_HOST` (default: `127.0.0.1`)
- `MILKTEA_DB_PORT` (default: `3306`)
- `MILKTEA_DB_USER` (default: `root`)
- `MILKTEA_DB_PASSWORD` (default: empty)
- `MILKTEA_DB_NAME` (default: `milktea_db`)

## Run

From the project root:

```bash
python app.py
```

## Default Credentials

- Username: `admin`
- Password: `Admin@2026!`

The default admin account is created when the database is initialized. It is configured from `models.py` and can be overridden by setting `MILKTEA_ADMIN_PASSWORD` before first startup.

## Notes

- The application is designed as a desktop GUI. Running multiple copies against the same database is not recommended.
- If Pillow is unavailable, logo image loading is disabled and a text icon is used instead.
- The app initializes missing data and tables automatically on startup when needed.

## License

This project does not include a license file. Add one if you plan to share or distribute the code.
