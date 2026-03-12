# app.py - Main Flask Application
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
import os
import mysql.connector
from mysql.connector import Error, IntegrityError
import traceback
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
from datetime import datetime
from decimal import Decimal
import threading
import pandas as pd
from io import BytesIO

from werkzeug.utils import secure_filename
from utils import extract_text_from_image, parse_receipt_text, parse_shopping_text, parse_parking_text
from config import MYSQL_CONFIG, MIN_PURCHASE_FOR_FREE_PARKING

# Import the separate tab modules
from receipts_database import init_receipts_database_routes
from receipt_gallery import init_receipt_gallery_routes
from parking_validator import init_parking_validator_routes
from data_analytics import init_data_analytics_routes

# Set the Tesseract-OCR path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)

# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Configuration
UPLOAD_FOLDER = 'receipts'
PROCESSED_FOLDER = 'processed_receipts'

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# MySQL connection helper functions
def get_db_connection():
    """Create and return a MySQL database connection"""
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def execute_query(query, params=None, fetch=False):
    """Execute a MySQL query with optional parameters"""
    connection = get_db_connection()
    if not connection:
        print("ERROR: Could not establish database connection")
        return None
    
    try:
        cursor = connection.cursor()
        print(f"DEBUG: Executing query: {query[:100]}...")
        if params:
            print(f"DEBUG: Query params: {params}")
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
            print(f"DEBUG: Fetched {len(result)} rows")
        else:
            result = cursor.rowcount
            print(f"DEBUG: Query affected {result} rows")
            
        # Make sure we commit the transaction
        connection.commit()
        print(f"DEBUG: Transaction committed successfully")
        return result
    except mysql.connector.Error as e:
        print(f"ERROR: MySQL Error executing query: {e}")
        print(f"ERROR: Query was: {query}")
        print(f"ERROR: Params were: {params}")
        
        # Handle duplicate entry errors specially
        if hasattr(e, 'errno') and e.errno == 1062:  # Duplicate entry error
            print("INFO: Duplicate entry detected - this may be expected in some cases")
            # We still need to rollback
            connection.rollback()
            # Return a special negative value to indicate duplicate entry
            return -1062
        else:
            connection.rollback()
            return None
    except Exception as e:
        print(f"ERROR: General error executing query: {e}")
        print(f"ERROR: Query was: {query}")
        print(f"ERROR: Params were: {params}")
        print(f"ERROR: Exception type: {type(e)}")
        traceback.print_exc()
        connection.rollback()
        return None
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# Initialize database
def init_db():
    """Initialize the MySQL database and create tables"""
    # First, create the database if it doesn't exist
    try:
        # Connect without specifying database
        temp_config = MYSQL_CONFIG.copy()
        temp_config.pop('database', None)
        
        connection = mysql.connector.connect(**temp_config)
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
        cursor.close()
        connection.close()
        
        print(f"Database '{MYSQL_CONFIG['database']}' created or already exists")
        
    except Error as e:
        print(f"Error creating database: {e}")
        return False
    
    # Now create the tables with enhanced structure for combined parking+shopping records
    create_table_query = """
    CREATE TABLE IF NOT EXISTS receipts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        -- Parking data (filled first)
        parking_ticket_no VARCHAR(255),
        vehicle_no VARCHAR(50),
        parking_ticket_date DATETIME,
        parking_filename VARCHAR(255),
        parking_image_path VARCHAR(500),
        parking_raw_text TEXT,
        -- Shopping data (filled second, same row)
        store_name VARCHAR(255),
        shopping_bill_no VARCHAR(255),
        shopping_amount DECIMAL(10,2),
        shopping_date DATETIME,
        shopping_filename VARCHAR(255),
        shopping_image_path VARCHAR(500),
        shopping_raw_text TEXT,
        -- System fields
        session_id VARCHAR(255),
        parking_fee_waived BOOLEAN DEFAULT FALSE,
        processed_at DATETIME,
        completed_at DATETIME NULL,
        status ENUM('parking_only', 'completed') DEFAULT 'parking_only',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        -- Additional fields for compatibility
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
    
    result = execute_query(create_table_query)
    if result is not None:
        print("Receipts table created or already exists")
        return True
    else:
        print("Failed to create receipts table")
        return False

def migrate_database():
    """Add new columns for parking validation tracking and direct payment if they don't exist"""
    try:
        # Check if parking_validation_used column exists
        check_column_query = """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'receipts' AND COLUMN_NAME = 'parking_validation_used'
        """
        result = execute_query(check_column_query, (MYSQL_CONFIG['database'],), fetch=True)
        
        if not result:
            # Add parking_validation_used column
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
        
        # Check if direct_payment column exists
        check_column_query = """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'receipts' AND COLUMN_NAME = 'direct_payment'
        """
        result = execute_query(check_column_query, (MYSQL_CONFIG['database'],), fetch=True)
        
        if not result:
            # Add direct payment columns
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

# Initialize database
init_db()
migrate_database()

# Web Routes
@app.route('/')
def index():
    return render_template('index.html')

# Initialize all tab modules
init_receipts_database_routes(app, execute_query)
init_receipt_gallery_routes(app, execute_query)  
init_parking_validator_routes(app, execute_query, MIN_PURCHASE_FOR_FREE_PARKING)
init_data_analytics_routes(app, execute_query)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8505)
