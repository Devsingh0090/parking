"""create_db.py
Standalone script to create the MySQL database and receipts table used by the app.
Run: python create_db.py
"""
import copy
import sys
import traceback
import mysql.connector
from mysql.connector import Error

from config import MYSQL_CONFIG


def get_db_connection(config_override=None):
    cfg = config_override or MYSQL_CONFIG
    try:
        conn = mysql.connector.connect(**cfg)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


def execute_query(query, params=None, fetch=False):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch:
            result = cursor.fetchall()
        else:
            result = cursor.rowcount

        connection.commit()
        return result
    except Exception as e:
        print(f"Error executing query: {e}")
        traceback.print_exc()
        try:
            connection.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            cursor.close()
            connection.close()
        except Exception:
            pass


def init_db():
    try:
        temp_config = copy.deepcopy(MYSQL_CONFIG)
        temp_config.pop('database', None)

        conn = mysql.connector.connect(**temp_config)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
        cur.close()
        conn.close()
        print(f"Database '{MYSQL_CONFIG['database']}' created or already exists")
    except Error as e:
        print(f"Error creating database: {e}")
        return False

    # Create receipts table
    create_table_query = """
    CREATE TABLE IF NOT EXISTS receipts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        parking_ticket_no VARCHAR(255),
        vehicle_no VARCHAR(50),
        parking_ticket_date DATETIME,
        parking_filename VARCHAR(255),
        parking_image_path VARCHAR(500),
        parking_raw_text TEXT,
        store_name VARCHAR(255),
        shopping_bill_no VARCHAR(255),
        shopping_amount DECIMAL(10,2),
        shopping_date DATETIME,
        shopping_filename VARCHAR(255),
        shopping_image_path VARCHAR(500),
        shopping_raw_text TEXT,
        session_id VARCHAR(255),
        parking_fee_waived BOOLEAN DEFAULT FALSE,
        processed_at DATETIME,
        completed_at DATETIME NULL,
        status ENUM('parking_only', 'completed') DEFAULT 'parking_only',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        filename VARCHAR(255),
        bill_number VARCHAR(255),
        total_amount DECIMAL(10,2),
        date_time VARCHAR(255),
        phone_number VARCHAR(50),
        merchant_info TEXT,
        parking_validation_used BOOLEAN DEFAULT FALSE,
        parking_validation_date DATETIME NULL,
        direct_payment BOOLEAN DEFAULT FALSE,
        direct_payment_amount DECIMAL(10,2) DEFAULT NULL,
        direct_payment_date DATETIME DEFAULT NULL,
        INDEX idx_parking_ticket_no (parking_ticket_no),
        INDEX idx_shopping_bill_no (shopping_bill_no),
        INDEX idx_vehicle_no (vehicle_no),
        INDEX idx_store_name (store_name),
        INDEX idx_session_id (session_id),
        INDEX idx_status (status),
        INDEX idx_processed_at (processed_at),
        INDEX idx_parking_validation_used (parking_validation_used),
        INDEX idx_direct_payment (direct_payment)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """

    res = execute_query(create_table_query)
    if res is None:
        print("Failed to create receipts table")
        return False
    print("Receipts table created or already exists")
    return True


def migrate_database():
    # Add migration steps similar to the app's migrate function
    try:
        check_column_query = """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'receipts' AND COLUMN_NAME = 'parking_validation_used'
        """
        result = execute_query(check_column_query, (MYSQL_CONFIG['database'],), fetch=True)

        if not result:
            alter_query1 = """
            ALTER TABLE receipts 
            ADD COLUMN parking_validation_used BOOLEAN DEFAULT FALSE,
            ADD COLUMN parking_validation_date DATETIME NULL,
            ADD INDEX idx_parking_validation_used (parking_validation_used)
            """
            execute_query(alter_query1)
            print("Added parking validation tracking columns to receipts table")
        else:
            print("Parking validation tracking columns already exist")

        check_column_query = """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'receipts' AND COLUMN_NAME = 'direct_payment'
        """
        result = execute_query(check_column_query, (MYSQL_CONFIG['database'],), fetch=True)

        if not result:
            alter_query2 = """
            ALTER TABLE receipts 
            ADD COLUMN direct_payment BOOLEAN DEFAULT FALSE,
            ADD COLUMN direct_payment_amount DECIMAL(10,2) DEFAULT NULL,
            ADD COLUMN direct_payment_date DATETIME DEFAULT NULL,
            ADD INDEX idx_direct_payment (direct_payment)
            """
            execute_query(alter_query2)
            print("Added direct payment columns to receipts table")
        else:
            print("Direct payment columns already exist")

    except Exception as e:
        print(f"Error migrating database: {e}")


def main():
    ok = init_db()
    if not ok:
        print("Database initialization failed")
        sys.exit(1)

    migrate_database()
    print("Database initialization and migration complete")


if __name__ == '__main__':
    main()
