# parking_validator.py - Parking Validator Tab Functionality
from flask import render_template, jsonify, request
from datetime import datetime, timedelta
import re

def init_parking_validator_routes(app, execute_query, MIN_PURCHASE_FOR_FREE_PARKING):
    @app.route('/api/update_shopping_bill', methods=['POST'])
    def update_shopping_bill():
        """Update shopping bill details (store, bill no, amount, date) by session_id"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            store_name = data.get('store_name')
            shopping_bill_no = data.get('shopping_bill_no')
            shopping_amount = data.get('shopping_amount')
            shopping_date = data.get('shopping_date')
            print(f"[DEBUG] /api/update_shopping_bill called with session_id={session_id}, store_name={store_name}, bill_no={shopping_bill_no}, amount={shopping_amount}, date={shopping_date}")
            if not session_id:
                return jsonify({'success': False, 'message': 'Session ID required'}), 400
            # Check if session_id exists
            check_query = "SELECT COUNT(*) FROM receipts WHERE session_id=%s"
            check_result = execute_query(check_query, (session_id,), fetch=True)
            if not check_result or check_result[0][0] == 0:
                print(f"[DEBUG] No receipt found for session_id={session_id}")
                return jsonify({'success': False, 'message': 'No receipt found for this session. Please upload shopping bill again.'}), 404
            try:
                shopping_amount = float(shopping_amount) if shopping_amount is not None and shopping_amount != '' else None
            except Exception:
                shopping_amount = None
            update_query = """
                UPDATE receipts SET store_name=%s, shopping_bill_no=%s, shopping_amount=%s, shopping_date=%s, updated_at=NOW()
                WHERE session_id=%s
            """
            result = execute_query(update_query, (store_name, shopping_bill_no, shopping_amount, shopping_date, session_id))
            print(f"[DEBUG] Update result for session_id={session_id}: {result}")
            if result is None or result == 0:
                print(f"[DEBUG] Database update failed for session_id={session_id}")
                return jsonify({'success': False, 'message': 'Database update failed'}), 500
            return jsonify({'success': True, 'message': 'Shopping bill updated'})
        except Exception as e:
            print(f"Error updating shopping bill: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500
    """Initialize all routes related to parking validator functionality"""
    
    @app.route('/parking_validation')
    def parking_validation():
        """Main parking validation page"""
        return render_template('parking_validation.html')

    @app.route('/api/upload_parking_bill', methods=['POST'])
    def upload_parking_bill():
        """Handle parking bill image uploads"""
        import os
        import uuid
        from werkzeug.utils import secure_filename
        from datetime import datetime
        from utils import extract_text_from_image, parse_parking_text
        
        try:
            # Accept optional session_id from frontend (for retries or advanced flows)
            session_id = None
            if 'session_id' in request.form and request.form['session_id']:
                session_id = request.form['session_id']
            else:
                session_id = str(uuid.uuid4())

            if 'file' not in request.files:
                return jsonify({'success': False, 'message': 'No file provided'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': 'No file selected'}), 400

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"parking_{timestamp}_{secure_filename(file.filename)}"

            # Save the uploaded file
            UPLOAD_FOLDER = 'receipts'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            # Extract text using OCR
            extracted_text = extract_text_from_image(filepath)

            # Parse the extracted text for parking info
            parking_data = parse_parking_text(extracted_text)

            # Add current timestamp if no date found
            if not parking_data.get('parking_ticket_date'):
                parking_data['parking_ticket_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Defensive: check if a row with this session_id already exists
            check_query = "SELECT COUNT(*) FROM receipts WHERE session_id=%s"
            check_result = execute_query(check_query, (session_id,), fetch=True)
            if check_result and check_result[0][0] > 0:
                # If a row exists, update it with new parking bill data
                update_query = """
                UPDATE receipts SET parking_ticket_no=%s, vehicle_no=%s, parking_ticket_date=%s, parking_filename=%s, parking_image_path=%s, parking_raw_text=%s, status=%s, updated_at=NOW() WHERE session_id=%s
                """
                execute_query(
                    update_query,
                    (
                        parking_data.get('parking_ticket_no', ''),
                        parking_data.get('vehicle_no', ''),
                        parking_data.get('parking_ticket_date'),
                        filename,
                        filepath,
                        extracted_text,
                        'parking_only',
                        session_id
                    )
                )
            else:
                # Insert a new row with this session_id
                insert_query = """
                INSERT INTO receipts (
                    parking_ticket_no, vehicle_no, parking_ticket_date, 
                    parking_filename, parking_image_path, parking_raw_text,
                    session_id, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                execute_query(
                    insert_query, 
                    (
                        parking_data.get('parking_ticket_no', ''),
                        parking_data.get('vehicle_no', ''),
                        parking_data.get('parking_ticket_date'),
                        filename,
                        filepath,
                        extracted_text,
                        session_id,
                        'parking_only',
                        datetime.now()
                    )
                )

            return jsonify({
                'success': True,
                'message': 'Parking bill uploaded successfully',
                'session_id': session_id,
                'parking_data': parking_data,
                'raw_text': extracted_text
            })

        except Exception as e:
            print(f"Error uploading parking bill: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
            
    @app.route('/api/check_parking', methods=['POST'])
    def check_parking():
        """Check parking fee waiver eligibility"""
        try:
            data = request.get_json()
            bill_number = data.get('bill_number', '').strip()
            phone_number = data.get('phone_number', '').strip()
            
            if not bill_number and not phone_number:
                return jsonify({
                    'eligible': False,
                    'message': 'Please provide either bill number or phone number'
                }), 400
            
            # Clean and normalize inputs
            if phone_number:
                phone_number = re.sub(r'[^\d+]', '', phone_number)
                if phone_number.startswith('+91'):
                    phone_number = phone_number[3:]
                elif phone_number.startswith('91') and len(phone_number) == 12:
                    phone_number = phone_number[2:]
            
#.......................................... Build search query based on available inputs........................................................................................
            search_conditions = []
            search_params = []
            
            if bill_number:
                search_conditions.append("shopping_bill_no LIKE %s")
                search_params.append(f"%{bill_number}%")
            
            if phone_number:
                search_conditions.append("phone_number LIKE %s")
                search_params.append(f"%{phone_number}%")
            
            search_query = f"""
            SELECT id, shopping_bill_no, shopping_amount, shopping_date, store_name, 
                   phone_number, parking_fee_waived, parking_validation_used,
                   parking_validation_date, vehicle_no, parking_ticket_no
            FROM receipts 
            WHERE ({' OR '.join(search_conditions)})
            AND shopping_amount IS NOT NULL
            AND shopping_amount >= %s
            ORDER BY shopping_date DESC
            LIMIT 10
            """
            
            search_params.append(MIN_PURCHASE_FOR_FREE_PARKING)
            
            results = execute_query(search_query, search_params, fetch=True)
            
            if not results:
                return jsonify({
                    'eligible': False,
                    'message': f'No qualifying purchases found. Minimum purchase amount: ₹{MIN_PURCHASE_FOR_FREE_PARKING}',
                    'receipts': []
                })
            
            # Process results
            eligible_receipts = []
            for result in results:
                receipt_id, bill_no, amount, shop_date, store, phone, fee_waived, \
                validation_used, validation_date, vehicle, parking_ticket = result
                
                # Check if parking validation has already been used
                validation_status = 'available'
                if validation_used:
                    validation_status = 'used'
                    if validation_date:
                        validation_status = f'used on {validation_date.strftime("%d/%m/%Y %H:%M")}'
                
                # Check if this is within valid time frame (e.g., same day)
                is_valid_timeframe = True
                if shop_date:
                    time_diff = datetime.now() - shop_date
                    if time_diff.days > 1:  # More than 1 day old 
                        is_valid_timeframe = False
                
                receipt_data = {
                    'id': receipt_id,
                    'bill_number': bill_no,
                    'amount': float(amount) if amount else 0,
                    'date': shop_date.strftime('%d/%m/%Y %H:%M') if shop_date else 'N/A',
                    'store_name': store or 'Unknown',
                    'phone_number': phone,
                    'validation_status': validation_status,
                    'eligible': not validation_used and is_valid_timeframe,
                    'vehicle_number': vehicle,
                    'parking_ticket': parking_ticket,
                    'time_valid': is_valid_timeframe
                }
                eligible_receipts.append(receipt_data)
            
            # Check if any receipts are eligible
            has_eligible = any(r['eligible'] for r in eligible_receipts)
            
            response = {
                'eligible': has_eligible,
                'message': 'Eligible receipts found' if has_eligible else 'No eligible receipts found',
                'receipts': eligible_receipts,
                'min_purchase': MIN_PURCHASE_FOR_FREE_PARKING
            }
            
            return jsonify(response)
            
        except Exception as e:
            print(f"Error checking parking eligibility: {e}")
            return jsonify({
                'eligible': False,
                'message': f'Error: {str(e)}',
                'receipts': []
            }), 500

    @app.route('/api/validate_shopping_bill', methods=['POST'])
    def validate_shopping_bill():
        """Validate and mark a shopping bill for parking fee waiver"""
        try:
            data = request.get_json()
            receipt_id = data.get('receipt_id')
            vehicle_number = data.get('vehicle_number', '').strip()
            parking_ticket_no = data.get('parking_ticket_no', '').strip()
            
            if not receipt_id:
                return jsonify({'error': 'Receipt ID is required'}), 400
            
            # Get the receipt details
            query = """
            SELECT id, shopping_bill_no, shopping_amount, shopping_date, store_name,
                   parking_validation_used, parking_fee_waived
            FROM receipts 
            WHERE id = %s
            """
            
            result = execute_query(query, (receipt_id,), fetch=True)
            if not result:
                return jsonify({'error': 'Receipt not found'}), 404
            
            receipt = result[0]
            receipt_id, bill_no, amount, shop_date, store, validation_used, fee_waived = receipt
            
            # Check if already validated
            if validation_used:
                return jsonify({'error': 'This receipt has already been used for parking validation'}), 400
            
            # Check if amount qualifies
            if not amount or amount < MIN_PURCHASE_FOR_FREE_PARKING:
                return jsonify({'error': f'Purchase amount does not qualify. Minimum: ₹{MIN_PURCHASE_FOR_FREE_PARKING}'}), 400
            
            # Check time validity (same day or within 24 hours)
            if shop_date:
                time_diff = datetime.now() - shop_date
                if time_diff.days > 1:
                    return jsonify({'error': 'Receipt is too old for parking validation (max 24 hours)'}), 400
            
            # Update the receipt to mark validation as used
            update_query = """
            UPDATE receipts 
            SET parking_validation_used = TRUE,
                parking_validation_date = %s,
                parking_fee_waived = TRUE,
                vehicle_no = COALESCE(vehicle_no, %s),
                parking_ticket_no = COALESCE(parking_ticket_no, %s),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            
            update_result = execute_query(update_query, (
                datetime.now(),
                vehicle_number if vehicle_number else None,
                parking_ticket_no if parking_ticket_no else None,
                receipt_id
            ))
            
            if update_result is None:
                return jsonify({'error': 'Failed to update receipt'}), 500
            
            # Create validation record/receipt
            validation_data = {
                'receipt_id': receipt_id,
                'bill_number': bill_no,
                'amount': float(amount),
                'store_name': store,
                'shopping_date': shop_date.strftime('%d/%m/%Y %H:%M') if shop_date else 'N/A',
                'validation_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'vehicle_number': vehicle_number,
                'parking_ticket': parking_ticket_no,
                'status': 'validated'
            }
            
            return jsonify({
                'message': 'Parking fee waiver validated successfully',
                'validation_data': validation_data
            })
            
        except Exception as e:
            print(f"Error validating shopping bill: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/get_receipt_status/<filename>')
    def get_receipt_status(filename):
        """Get the processing status of a receipt file"""
        try:
            query = """
            SELECT status, processed_at, shopping_bill_no, parking_ticket_no,
                   shopping_amount, parking_fee_waived
            FROM receipts 
            WHERE shopping_filename = %s OR parking_filename = %s
            """
            result = execute_query(query, (filename, filename), fetch=True)
            
            if result:
                status, processed_at, shopping_bill, parking_ticket, amount, fee_waived = result[0]
                return jsonify({
                    'processed': True,
                    'status': status,
                    'processed_at': processed_at.isoformat() if processed_at else None,
                    'bill_number': shopping_bill or parking_ticket,
                    'amount': float(amount) if amount else None,
                    'parking_fee_waived': bool(fee_waived),
                    'filename': filename
                })
            else:
                return jsonify({
                    'processed': False,
                    'status': 'unprocessed',
                    'filename': filename
                })
                
        except Exception as e:
            print(f"Error getting receipt status: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/parking_stats')
    def parking_stats():
        """Get parking-related statistics"""
        try:
            # Get parking validation statistics
            stats_queries = {
                'total_validations': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_validation_used = TRUE
                """,
                'today_validations': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_validation_used = TRUE 
                    AND DATE(parking_validation_date) = CURDATE()
                """,
                'this_month_validations': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_validation_used = TRUE 
                    AND YEAR(parking_validation_date) = YEAR(CURDATE())
                    AND MONTH(parking_validation_date) = MONTH(CURDATE())
                """,
                'avg_validation_amount': """
                    SELECT AVG(shopping_amount) FROM receipts 
                    WHERE parking_validation_used = TRUE 
                    AND shopping_amount IS NOT NULL
                """,
                'total_parking_receipts': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_ticket_no IS NOT NULL
                """,
                'fee_waived_count': """
                    SELECT COUNT(*) FROM receipts 
                    WHERE parking_fee_waived = TRUE
                """
            }
            
            stats = {}
            for key, query in stats_queries.items():
                result = execute_query(query, fetch=True)
                if result and result[0][0] is not None:
                    stats[key] = float(result[0][0]) if 'avg' in key else int(result[0][0])
                else:
                    stats[key] = 0
            
            # Get monthly validation trend
            monthly_trend_query = """
            SELECT 
                DATE_FORMAT(parking_validation_date, '%Y-%m') as month,
                COUNT(*) as validations,
                AVG(shopping_amount) as avg_amount
            FROM receipts 
            WHERE parking_validation_used = TRUE 
            AND parking_validation_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(parking_validation_date, '%Y-%m')
            ORDER BY month DESC
            """
            
            monthly_result = execute_query(monthly_trend_query, fetch=True)
            monthly_trend = []
            if monthly_result:
                for row in monthly_result:
                    month, validations, avg_amount = row
                    monthly_trend.append({
                        'month': month,
                        'validations': int(validations),
                        'avg_amount': float(avg_amount) if avg_amount else 0
                    })
            
            return jsonify({
                'stats': stats,
                'monthly_trend': monthly_trend
            })
            
        except Exception as e:
            print(f"Error getting parking stats: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/update_parking_bill', methods=['POST'])
    def update_parking_bill():
        """Update parking bill details (ticket no, vehicle no, date) by session_id"""
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            ticket_no = data.get('parking_ticket_no')
            vehicle_no = data.get('vehicle_no')
            ticket_date = data.get('parking_ticket_date')
            if not session_id:
                return jsonify({'success': False, 'message': 'Session ID required'}), 400
            update_query = """
                UPDATE receipts SET parking_ticket_no=%s, vehicle_no=%s, parking_ticket_date=%s, updated_at=NOW()
                WHERE session_id=%s
            """
            result = execute_query(update_query, (ticket_no, vehicle_no, ticket_date, session_id))
            if result is None:
                return jsonify({'success': False, 'message': 'Database update failed'}), 500
            return jsonify({'success': True, 'message': 'Parking bill updated'})
        except Exception as e:
            print(f"Error updating parking bill: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/upload_shopping_bill', methods=['POST'])
    def upload_shopping_bill():
        """Handle shopping bill image uploads and update the session, or just return status if only session_id is sent"""
        import os
        from werkzeug.utils import secure_filename
        from datetime import datetime
        from utils import extract_text_from_image, parse_shopping_text
        try:
            # If only session_id is sent (no file), just return current status
            if ('file' not in request.files or request.files['file'].filename == '') and 'session_id' in (request.form or request.values):
                session_id = request.form.get('session_id') or request.values.get('session_id')
                if not session_id:
                    return jsonify({'success': False, 'message': 'Session ID required'}), 400
                select_query = "SELECT parking_ticket_no, vehicle_no, parking_ticket_date, store_name, shopping_bill_no, shopping_amount, shopping_date FROM receipts WHERE session_id=%s"
                combined = execute_query(select_query, (session_id,), fetch=True)
                combined_data = {}
                if combined:
                    row = combined[0]
                    combined_data = {
                        'parking_ticket_no': row[0],
                        'vehicle_no': row[1],
                        'parking_date': row[2],
                        'store_name': row[3],
                        'shopping_bill_no': row[4],
                        'shopping_amount': float(row[5]) if row[5] else 0,
                        'shopping_date': row[6]
                    }
                min_purchase = MIN_PURCHASE_FOR_FREE_PARKING
                parking_fee_waived = False
                savings = 0
                if combined_data and combined_data.get('shopping_amount') and float(combined_data['shopping_amount']) >= min_purchase:
                    parking_fee_waived = True
                    savings = 50
                    combined_data['savings'] = savings
                return jsonify({
                    'success': True,
                    'message': 'Shopping bill status fetched',
                    'combined_data': combined_data,
                    'parking_fee_waived': parking_fee_waived
                })
            # Normal upload flow
            if 'file' not in request.files or 'session_id' not in request.form:
                return jsonify({'success': False, 'message': 'File and session_id required'}), 400
            file = request.files['file']
            session_id = request.form['session_id']
            if file.filename == '':
                return jsonify({'success': False, 'message': 'No file selected'}), 400
            # Save file
            UPLOAD_FOLDER = 'receipts'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = f"shopping_{timestamp}_{secure_filename(file.filename)}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            # OCR and parse
            extracted_text = extract_text_from_image(filepath)
            shopping_data = parse_shopping_text(extracted_text)
            # Save to DB (update the same session)
            update_query = """
                UPDATE receipts SET 
                    store_name=%s, shopping_bill_no=%s, shopping_amount=%s, shopping_date=%s,
                    shopping_filename=%s, shopping_image_path=%s, shopping_raw_text=%s, updated_at=NOW(), status='completed'
                WHERE session_id=%s
            """
            shopping_amount = shopping_data.get('shopping_amount')
            try:
                shopping_amount = float(shopping_amount) if shopping_amount else None
            except Exception:
                shopping_amount = None
            shopping_date = shopping_data.get('shopping_date')
            if not shopping_date:
                shopping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result = execute_query(update_query, (
                shopping_data.get('store_name'),
                shopping_data.get('shopping_bill_no'),
                shopping_amount,
                shopping_date,
                filename,
                filepath,
                extracted_text,
                session_id
            ))
            if result is None:
                return jsonify({'success': False, 'message': 'Database update failed'}), 500
            # Optionally, fetch combined data for response
            select_query = "SELECT parking_ticket_no, vehicle_no, parking_ticket_date, store_name, shopping_bill_no, shopping_amount, shopping_date FROM receipts WHERE session_id=%s"
            combined = execute_query(select_query, (session_id,), fetch=True)
            combined_data = {}
            if combined:
                row = combined[0]
                combined_data = {
                    'parking_ticket_no': row[0],
                    'vehicle_no': row[1],
                    'parking_date': row[2],
                    'store_name': row[3],
                    'shopping_bill_no': row[4],
                    'shopping_amount': float(row[5]) if row[5] else 0,
                    'shopping_date': row[6]
                }
            # Check for parking fee waiver
            min_purchase = MIN_PURCHASE_FOR_FREE_PARKING
            parking_fee_waived = False
            savings = 0
            if combined_data and combined_data.get('shopping_amount') and float(combined_data['shopping_amount']) >= min_purchase:
                parking_fee_waived = True
                savings = 50  # Example: fixed parking fee
                combined_data['savings'] = savings
            return jsonify({
                'success': True,
                'message': 'Shopping bill uploaded successfully',
                'combined_data': combined_data,
                'parking_fee_waived': parking_fee_waived
            })
        except Exception as e:
            print(f"Error uploading shopping bill: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500

    return app
