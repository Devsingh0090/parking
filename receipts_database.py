# receipts_database.py - Receipts Database Tab Functionality
from flask import render_template, jsonify, request, send_file
import mysql.connector
from mysql.connector import Error
import pandas as pd
from io import BytesIO
from datetime import datetime
import os

def init_receipts_database_routes(app, execute_query):
    """Initialize all routes related to receipts database functionality"""
    
    @app.route('/receipts')
    def view_receipts():
        """Main receipts database view page"""
        # First, get all records
        query = """
        SELECT id, store_name, shopping_bill_no, shopping_amount, shopping_date, 
               parking_ticket_no, vehicle_no, parking_ticket_date, parking_fee_waived, 
               processed_at, filename, session_id, status, bill_number, total_amount, 
               date_time, phone_number, merchant_info
        FROM receipts 
        ORDER BY processed_at DESC
        """
        all_receipts = execute_query(query, fetch=True)
        
        if all_receipts is None:
            all_receipts = []
        
        # Group receipts by session ID to avoid duplicates
        grouped_receipts = []
        sessions = {}
        standalone_receipts = []
        
        # Process all receipts and group them by session
        for receipt in all_receipts:
            receipt_id, store_name, shopping_bill_no, shopping_amount, shopping_date, \
            parking_ticket_no, vehicle_no, parking_ticket_date, parking_fee_waived, \
            processed_at, filename, session_id, status, bill_number, total_amount, \
            date_time, phone_number, merchant_info = receipt
            
            receipt_dict = {
                'id': receipt_id,
                'store_name': store_name,
                'shopping_bill_no': shopping_bill_no or bill_number,
                'shopping_amount': shopping_amount or total_amount,
                'shopping_date': shopping_date or date_time,
                'parking_ticket_no': parking_ticket_no,
                'vehicle_no': vehicle_no,
                'parking_ticket_date': parking_ticket_date,
                'parking_fee_waived': parking_fee_waived,
                'processed_at': processed_at,
                'filename': filename,
                'session_id': session_id,
                'status': status,
                'phone_number': phone_number,
                'merchant_info': merchant_info
            }
            
            if session_id and session_id.strip():
                if session_id not in sessions:
                    sessions[session_id] = []
                sessions[session_id].append(receipt_dict)
            else:
                standalone_receipts.append(receipt_dict)
        
        # Combine session records and add them to the final list
        for session_id, records in sessions.items():
            if len(records) == 1:
                # Single record in session, treat as standalone
                grouped_receipts.append(records[0])
            else:
                # Multiple records, combine them
                combined = records[0].copy()  # Start with first record
                
                # Merge data from all records in the session
                for record in records[1:]:
                    if record['store_name'] and not combined['store_name']:
                        combined['store_name'] = record['store_name']
                    if record['shopping_bill_no'] and not combined['shopping_bill_no']:
                        combined['shopping_bill_no'] = record['shopping_bill_no']
                    if record['shopping_amount'] and not combined['shopping_amount']:
                        combined['shopping_amount'] = record['shopping_amount']
                    if record['shopping_date'] and not combined['shopping_date']:
                        combined['shopping_date'] = record['shopping_date']
                
                grouped_receipts.append(combined)
        
        # Add standalone receipts
        grouped_receipts.extend(standalone_receipts)
        
        return render_template('receipts.html', receipts=grouped_receipts)

    @app.route('/export_receipts_excel')
    def export_receipts_excel():
        """Export receipts data to Excel"""
        try:
            query = """
            SELECT id, store_name, shopping_bill_no, shopping_amount, shopping_date, 
                   parking_ticket_no, vehicle_no, parking_ticket_date, parking_fee_waived, 
                   processed_at, filename, session_id, status, created_at, updated_at
            FROM receipts 
            ORDER BY processed_at DESC
            """
            receipts = execute_query(query, fetch=True)
            
            if not receipts:
                return jsonify({'error': 'No receipts found'}), 404
            
            # Create DataFrame
            columns = ['ID', 'Store Name', 'Shopping Bill No', 'Shopping Amount', 'Shopping Date',
                      'Parking Ticket No', 'Vehicle No', 'Parking Date', 'Parking Fee Waived',
                      'Processed At', 'Filename', 'Session ID', 'Status', 'Created At', 'Updated At']
            
            df = pd.DataFrame(receipts, columns=columns)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Receipts', index=False)
                
                # Get the workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Receipts']
                
                # Add some formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                # Write headers with formatting
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Adjust column widths
                for i, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, min(max_len, 50))
            
            output.seek(0)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'receipts_export_{timestamp}.xlsx'
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            print(f"Error exporting receipts to Excel: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/delete_receipt', methods=['POST'])
    def delete_receipt():
        """Delete a receipt from database"""
        try:
            data = request.get_json()
            receipt_id = data.get('id')
            
            if not receipt_id:
                return jsonify({'error': 'Receipt ID is required'}), 400
            
            # First get the filename for file deletion
            query = "SELECT filename, shopping_filename, parking_filename FROM receipts WHERE id = %s"
            result = execute_query(query, (receipt_id,), fetch=True)
            
            if not result:
                return jsonify({'error': 'Receipt not found'}), 404
            
            filenames = result[0]
            
            # Delete from database
            delete_query = "DELETE FROM receipts WHERE id = %s"
            delete_result = execute_query(delete_query, (receipt_id,))
            
            if delete_result is None:
                return jsonify({'error': 'Failed to delete from database'}), 500
            
            # Delete physical files if they exist
            for filename in filenames:
                if filename:
                    file_paths = [
                        os.path.join('receipts', filename),
                        os.path.join('processed_receipts', filename)
                    ]
                    for file_path in file_paths:
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                print(f"Deleted file: {file_path}")
                            except Exception as e:
                                print(f"Error deleting file {file_path}: {e}")
            
            return jsonify({'message': 'Receipt deleted successfully'})
            
        except Exception as e:
            print(f"Error deleting receipt: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/clean_receipts_db', methods=['POST'])
    def clean_receipts_db():
        """Clean up receipts database - remove duplicates and orphaned records"""
        try:
            cleaned_count = 0
            
            # Find and remove exact duplicates based on multiple fields
            duplicate_query = """
            DELETE r1 FROM receipts r1
            INNER JOIN receipts r2 
            WHERE r1.id > r2.id 
            AND (
                (r1.shopping_bill_no IS NOT NULL AND r1.shopping_bill_no = r2.shopping_bill_no)
                OR (r1.parking_ticket_no IS NOT NULL AND r1.parking_ticket_no = r2.parking_ticket_no)
                OR (r1.filename IS NOT NULL AND r1.filename = r2.filename)
            )
            """
            
            result = execute_query(duplicate_query)
            if result is not None and result > 0:
                cleaned_count += result
                print(f"Removed {result} duplicate records")
            
            # Remove records with missing critical data (optional cleanup)
            orphaned_query = """
            DELETE FROM receipts 
            WHERE shopping_bill_no IS NULL 
            AND parking_ticket_no IS NULL 
            AND filename IS NULL
            AND created_at < DATE_SUB(NOW(), INTERVAL 1 DAY)
            """
            
            result = execute_query(orphaned_query)
            if result is not None and result > 0:
                cleaned_count += result
                print(f"Removed {result} orphaned records")
            
            return jsonify({
                'message': f'Database cleaned successfully. Removed {cleaned_count} records.',
                'cleaned_count': cleaned_count
            })
            
        except Exception as e:
            print(f"Error cleaning database: {e}")
            return jsonify({'error': str(e)}), 500

    return app
