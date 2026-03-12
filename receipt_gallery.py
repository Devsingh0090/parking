# receipt_gallery.py - Receipt Gallery Tab Functionality
from flask import render_template, jsonify, request, send_from_directory
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
import traceback

def init_receipt_gallery_routes(app, execute_query):
    """Initialize all routes related to receipt gallery functionality"""
    
    @app.route('/receipts_folder')
    def receipts_folder():
        """Main receipt gallery page"""
        return render_template('receipts_folder.html')

    @app.route('/receipts_folder_data')
    def receipts_folder_data():
        """Get receipt files from the receipts folder"""
        try:
            receipts_folder = 'receipts'
            if not os.path.exists(receipts_folder):
                return jsonify({'files': []})
            
            files = []
            for filename in os.listdir(receipts_folder):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    filepath = os.path.join(receipts_folder, filename)
                    file_stat = os.stat(filepath)
                    files.append({
                        'name': filename,
                        'size': file_stat.st_size,
                        'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    })
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            return jsonify({'files': files})
        except Exception as e:
            print(f"Error getting receipts folder data: {e}")
            return jsonify({'error': str(e), 'files': []})

    @app.route('/receipts/<filename>')
    def receipts_file(filename):
        """Serve receipt image files"""
        return send_from_directory('receipts', filename)

    @app.route('/process_receipt_ocr', methods=['POST'])
    def process_receipt_ocr():
        """Process receipt using OCR and save to database"""
        try:
            data = request.get_json()
            filename = data.get('filename')
            
            if not filename:
                return jsonify({'error': 'Filename is required'}), 400
            
            file_path = os.path.join('receipts', filename)
            if not os.path.exists(file_path):
                return jsonify({'error': 'File not found'}), 404
            
            print(f"Processing receipt: {filename}")
            
            # Import OCR functions
            from utils import extract_text_from_image, parse_receipt_text
            
            # Extract text using OCR
            raw_text = extract_text_from_image(file_path)
            if not raw_text:
                return jsonify({'error': 'Failed to extract text from image'}), 500
            
            print(f"Extracted text length: {len(raw_text)} characters")
            
            # Parse the receipt text
            parsed_data = parse_receipt_text(raw_text)
            
            # Determine if this is a parking or shopping receipt
            is_parking = any(keyword in raw_text.lower() for keyword in 
                           ['parking', 'vehicle', 'car', 'bike', 'ticket'])
            
            if is_parking:
                # Process as parking receipt
                from utils import parse_parking_text
                parking_data = parse_parking_text(raw_text)
                
                # Check if parking record already exists
                check_query = """
                SELECT id FROM receipts 
                WHERE parking_ticket_no = %s OR parking_filename = %s
                """
                existing = execute_query(check_query, 
                                       (parking_data.get('ticket_number'), filename), 
                                       fetch=True)
                
                if existing:
                    return jsonify({'error': 'Parking receipt already exists in database'}), 400
                
                # Insert parking data
                insert_query = """
                INSERT INTO receipts (
                    parking_ticket_no, vehicle_no, parking_ticket_date, 
                    parking_filename, parking_image_path, parking_raw_text,
                    processed_at, status, session_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                session_id = f"parking_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                params = (
                    parking_data.get('ticket_number'),
                    parking_data.get('vehicle_number'),
                    parking_data.get('date_time'),
                    filename,
                    file_path,
                    raw_text,
                    datetime.now(),
                    'parking_only',
                    session_id
                )
                
            else:
                # Process as shopping receipt
                from utils import parse_shopping_text
                shopping_data = parse_shopping_text(raw_text)
                
                # Check if shopping record already exists
                check_query = """
                SELECT id FROM receipts 
                WHERE shopping_bill_no = %s OR shopping_filename = %s
                """
                existing = execute_query(check_query, 
                                       (parsed_data.get('bill_number'), filename), 
                                       fetch=True)
                
                if existing:
                    return jsonify({'error': 'Shopping receipt already exists in database'}), 400
                
                # Extract store name from text
                store_name = extract_store_name(raw_text)
                
                # Insert shopping data
                insert_query = """
                INSERT INTO receipts (
                    store_name, shopping_bill_no, shopping_amount, shopping_date,
                    shopping_filename, shopping_image_path, shopping_raw_text,
                    processed_at, status, session_id, phone_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                session_id = f"shopping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Parse date if available
                shopping_date = None
                if parsed_data.get('date_time'):
                    try:
                        shopping_date = datetime.strptime(parsed_data['date_time'], '%d/%m/%Y %H:%M')
                    except:
                        try:
                            shopping_date = datetime.strptime(parsed_data['date_time'], '%d/%m/%Y')
                        except:
                            pass
                
                params = (
                    store_name,
                    parsed_data.get('bill_number'),
                    parsed_data.get('total_amount'),
                    shopping_date,
                    filename,
                    file_path,
                    raw_text,
                    datetime.now(),
                    'completed',
                    session_id,
                    parsed_data.get('phone_number')
                )
            
            # Execute the insert
            result = execute_query(insert_query, params)
            
            if result is None:
                return jsonify({'error': 'Failed to save receipt to database'}), 500
            
            # Move file to processed folder
            processed_path = os.path.join('processed_receipts', filename)
            try:
                import shutil
                shutil.move(file_path, processed_path)
                print(f"Moved {filename} to processed_receipts folder")
            except Exception as e:
                print(f"Warning: Could not move file to processed folder: {e}")
            
            response_data = {
                'message': 'Receipt processed successfully',
                'type': 'parking' if is_parking else 'shopping',
                'data': parking_data if is_parking else parsed_data,
                'raw_text': raw_text[:500] + '...' if len(raw_text) > 500 else raw_text
            }
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f"Error processing receipt OCR: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/upload_receipt', methods=['POST'])
    def upload_receipt():
        """Upload a new receipt file"""
        try:
            if 'receipt' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['receipt']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Add timestamp to avoid filename conflicts
                name, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{name}_{timestamp}{ext}"
                
                file_path = os.path.join('receipts', filename)
                file.save(file_path)
                
                return jsonify({
                    'message': 'Receipt uploaded successfully',
                    'filename': filename
                })
            else:
                return jsonify({'error': 'Invalid file type'}), 400
                
        except Exception as e:
            print(f"Error uploading receipt: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/batch_process_receipts', methods=['POST'])
    def batch_process_receipts():
        """Process multiple receipts at once"""
        try:
            data = request.get_json()
            filenames = data.get('filenames', [])
            
            if not filenames:
                return jsonify({'error': 'No filenames provided'}), 400
            
            results = []
            successful = 0
            failed = 0
            
            for filename in filenames:
                try:
                    # Process each file
                    file_path = os.path.join('receipts', filename)
                    if not os.path.exists(file_path):
                        results.append({
                            'filename': filename,
                            'status': 'failed',
                            'error': 'File not found'
                        })
                        failed += 1
                        continue
                    
                    # Import OCR functions
                    from utils import extract_text_from_image, parse_receipt_text
                    
                    # Extract and process
                    raw_text = extract_text_from_image(file_path)
                    if raw_text:
                        parsed_data = parse_receipt_text(raw_text)
                        
                        # Basic insertion (simplified for batch processing)
                        insert_query = """
                        INSERT INTO receipts (
                            shopping_bill_no, shopping_amount, shopping_date,
                            shopping_filename, shopping_image_path, shopping_raw_text,
                            processed_at, status, session_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        
                        session_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                        
                        params = (
                            parsed_data.get('bill_number'),
                            parsed_data.get('total_amount'),
                            parsed_data.get('date_time'),
                            filename,
                            file_path,
                            raw_text,
                            datetime.now(),
                            'completed',
                            session_id
                        )
                        
                        result = execute_query(insert_query, params)
                        
                        if result is not None:
                            results.append({
                                'filename': filename,
                                'status': 'success',
                                'data': parsed_data
                            })
                            successful += 1
                        else:
                            results.append({
                                'filename': filename,
                                'status': 'failed',
                                'error': 'Database insertion failed'
                            })
                            failed += 1
                    else:
                        results.append({
                            'filename': filename,
                            'status': 'failed',
                            'error': 'OCR extraction failed'
                        })
                        failed += 1
                        
                except Exception as e:
                    results.append({
                        'filename': filename,
                        'status': 'failed',
                        'error': str(e)
                    })
                    failed += 1
            
            return jsonify({
                'message': f'Batch processing completed: {successful} successful, {failed} failed',
                'results': results,
                'summary': {
                    'total': len(filenames),
                    'successful': successful,
                    'failed': failed
                }
            })
            
        except Exception as e:
            print(f"Error in batch processing: {e}")
            return jsonify({'error': str(e)}), 500

def allowed_file(filename):
    """Check if the file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_store_name(text):
    """Extract store/merchant name from receipt text"""
    if not text:
        return None
    
    lines = text.split('\n')
    
    # Enhanced patterns for store/company names
    store_patterns = [
        # Look for company names in common formats
        r'([A-Z][A-Z\s&]+(?:ENTERPRISES|COMPANY|CORP|INC|LTD|LLC|PVT|LIMITED))',
        r'([A-Z][A-Z\s&]+(?:STORE|SHOP|MARKET|MALL|RESTAURANT|CAFE|BAR|HOTEL))',
        r'^([A-Z][A-Z\s&]{2,})',  # Uppercase text at beginning of line 
        r'Sold\s+By[\s:]*([A-Z][A-Za-z\s&]+)',  # "Sold By" pattern
        r'([A-Z][A-Za-z\s&]+(?:Enterprises|Company|Corp|Inc|Ltd|LLC|Pvt|Limited))',
    ]
    
    # Check first few lines for store name
    for i, line in enumerate(lines[:7]):  # Check more lines
        line = line.strip()
        if len(line) > 2 and not line.isdigit():
            for pattern in store_patterns:
                import re
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    store_name = match.group(1).strip()
                    if len(store_name) >= 3:
                        return store_name
    
    # Fallback: return first meaningful line that looks like a company name
    for line in lines[:5]:
        line = line.strip()
        if (len(line) >= 5 and len(line) <= 60 and 
            not line.isdigit() and 
            not re.match(r'^[0-9\-/\s:]+$', line) and
            any(c.isupper() for c in line)):
            return line
    
    return None

def get_receipt_status(filename, execute_query):
    """Get the processing status of a receipt"""
    query = """
    SELECT status, processed_at, shopping_bill_no, parking_ticket_no
    FROM receipts 
    WHERE shopping_filename = %s OR parking_filename = %s
    """
    result = execute_query(query, (filename, filename), fetch=True)
    
    if result:
        status, processed_at, shopping_bill, parking_ticket = result[0]
        return {
            'processed': True,
            'status': status,
            'processed_at': processed_at.isoformat() if processed_at else None,
            'bill_number': shopping_bill or parking_ticket
        }
    else:
        return {
            'processed': False,
            'status': 'unprocessed'
        }

    return app
