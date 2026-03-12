# config.py
# MySQL Database Configuration

# MySQL connection settings
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Change this to your MySQL username
    'password': 'ExuLTSofT123',  # Change this to your MySQL password
    'database': 'smartbill_parking',  # Updated to match new database name
    'port': 3306,
    'charset': 'utf8mb4',
    'autocommit': True
}



# Other app configurations
MIN_PURCHASE_FOR_FREE_PARKING = 100  # Minimum amount for free parking - any purchase qualifies

