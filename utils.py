from PIL import Image
import pytesseract
import re
import cv2
import numpy as np
from datetime import datetime

def extract_text_from_image(image_path):
    try:
        # Open image with PIL first
        img_pil = Image.open(image_path)
        
        # Convert to RGB if needed
        if img_pil.mode != 'RGB':
            img_pil = img_pil.convert('RGB')
            
        # Convert PIL Image to OpenCV format
        img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # ENHANCED IMAGE PREPROCESSING FOR LOW QUALITY MOBILE IMAGES
        
        # 1. Denoise the image
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # 2. Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        
        # 3. Apply different thresholding techniques and pick the best one
        thresh_methods = [
            # Regular binary threshold
            cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            
            # Adaptive thresholding - better for uneven lighting
            cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2),
                                  
            # Adaptive thresholding with different parameters
            cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                  cv2.THRESH_BINARY, 15, 5)
        ]
        
        # Try different OCR configurations for better results - ENHANCED FOR LOW QUALITY
        custom_configs = [
            '--psm 6 --oem 3',  # Assume a uniform block of text
            '--psm 4 --oem 3',  # Assume a single column of text
            '--psm 3 --oem 3',  # Fully automatic page segmentation
            '--psm 1 --oem 3',  # Automatic page segmentation with OSD
            # Additional configs that might work better for low quality images
            '--psm 11 --oem 3',  # Sparse text - good for finding isolated text fragments
            '--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ:.-',  # Restricted character set
        ]
        
        # Try multiple preprocessing methods and OCR configurations
        best_text = ""
        for img_processed in thresh_methods:
            for config in custom_configs:
                try:
                    # Use the processed image for better OCR accuracy
                    text = pytesseract.image_to_string(img_processed, config=config)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
                except Exception as config_error:
                    print(f"OCR config failed: {config} - {config_error}")
                    continue
        
        # If no config worked, try default on the best processed image
        if not best_text.strip():
            best_text = pytesseract.image_to_string(thresh_methods[0])
        
        print(f"OCR extracted {len(best_text)} characters from {image_path}")
        
        return best_text
            
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""
        
        # Try multiple configurations and use the one with the most text
        best_text = ""
        for config in custom_configs:
            try:
                # Use the thresholded image for better OCR accuracy
                text = pytesseract.image_to_string(thresh, config=config)
                if len(text.strip()) > len(best_text.strip()):
                    best_text = text
            except Exception as config_error:
                print(f"OCR config failed: {config} - {config_error}")
                continue
        
        # If no config worked, try default
        if not best_text.strip():
            best_text = pytesseract.image_to_string(thresh)
        
        print(f"OCR extracted {len(best_text)} characters from {image_path}")
        print(f"Sample text (first 200 chars): {best_text[:200]}...")
        
        return best_text.strip()
        
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

def parse_parking_text(text):
    """Parse parking-specific text to extract parking ticket number, vehicle number, and date"""
    data = {
        'parking_ticket_no': None,
        'vehicle_no': None,
        'parking_ticket_date': None,
        'phone_number': None
    }
    if not text:
        return data
    print(f"[DEBUG] RAW TEXT:\n{text}")

    # --- Prioritize exact patterns for Ticket No. and Veh No. ---
    parking_ticket_patterns = [
        r'Ticket\s*Number\s*[:=|\-\'‘’]*\s*([0-9]{3,10})',  # Most specific, only numbers
        r'Ticket\s*No[.,:]*\s*[:=\-\'‘’]*\s*([0-9]{3,10})',
        r'Ticket\s*No\.?\s*[:=\-\'‘’]*\s*([0-9]{3,10})',
        r'(?:Ticket|TKT)\s*(?:No|Number|ID|Id|#)\s*[:.]?\s*([0-9]{3,10})',  # Only numbers
        r'(?:Parking|Park)\s*(?:Ticket|Receipt|No|Number|#)\s*[:.]?\s*([0-9]{3,10})',
        r'No\.?\s*[:#-]?\s*([0-9]{3,10})',
        r'#\s*([0-9]{3,10})',
        r'(?<!\w)([A-Z]{2,}[0-9]{4,}|[0-9]{4,}[A-Z]{2,})(?!\w)',
        r'(?<!\w)([A-Z][0-9]{5,}[A-Z]?)(?!\w)',
        r'(?<!\w)([A-Z0-9]{7,})(?!\w)'
    ]
    lines = text.split('\n')
    ticket_no = None
    found = False
    for i, line in enumerate(lines):
        if found:
            break
        clean = line.strip()
        # Direct match: Ticket Number : 8218
        m = re.search(r'Ticket\s*Number\s*[:=|\-\'‘’]*\s*([0-9]{3,10})', clean, re.IGNORECASE)
        if m:
            ticket_no = m.group(1)
            print(f"[DEBUG] Line direct extracted ticket_no: {ticket_no} from line: {clean}")
            found = True
        # If line contains 'Ticket' and 'Number' but not the number, check next line
        if 'ticket' in clean.lower() and 'number' in clean.lower() and not re.search(r'[0-9]{3,10}', clean):
            # noisy OCR can put the actual number several lines below; look ahead up to 4 lines
            for j in range(1, 5):
                idx = i + j
                if idx >= len(lines):
                    break
                candidate = lines[idx].strip()
                m2 = re.search(r'([0-9]{3,12})', candidate)
                if m2:
                    ticket_no = m2.group(1)
                    print(f"[DEBUG] Lookahead extracted ticket_no: {ticket_no} from line {idx}: {candidate}")
                    found = True
                    break
    if not found:
        # fallback to your patterns
        for pattern in parking_ticket_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ticket_no = match.group(1).strip()
                if ticket_no.isdigit():
                    data['parking_ticket_no'] = ticket_no
                    print(f"[DEBUG] Pattern extracted ticket_no: {ticket_no}")
                    break
    else:
        data['parking_ticket_no'] = ticket_no

    # --- Prioritize exact pattern for Veh No. ---
    vehicle_patterns = [
        r'Vehicle\s*Number\s*[:=|\-\'‘’]*\s*([A-Za-z0-9]{6,15})',
        r'([A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4})',  # Standard Indian format
        r'([A-Z]{2,3}[A-Z]*\d{4,5})',
        r'([A-Z]{2,3}[A-Z]*\s*\d{3,5})',
        r'([A-Z]{2,3}[A-Z]*[0-9]{3,5})',
        r'Vehicle\s*Number\s*[:=|\\-]*\\s*([A-Za-z0-9]{6,15})'
    ]
    for pattern in vehicle_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            vehicle_no = match.group(1).strip().replace('?', '').replace('/', '').replace(' ', '').upper()
            print(f"[DEBUG] Extracted vehicle_no: {vehicle_no} (pattern: {pattern}) from line: {line}")
            if 6 <= len(vehicle_no) <= 15:
                data['vehicle_no'] = vehicle_no
                break

    # --- Date extraction (unchanged) ---
    date_patterns = [
        r'(?:Date|Entry|Exit)\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(?:Date|Entry|Exit)\s*[:.]?\s*(\d{1,2}\s+\w+\s+\d{2,4})',
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            try:
                if '/' in date_str or '-' in date_str:
                    if len(date_str.split('/')[0]) == 2:
                        parsed_date = datetime.strptime(date_str, '%d/%m/%Y')
                    else:
                        parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
                else:
                    parsed_date = datetime.strptime(date_str, '%d %b %Y')
                data['parking_ticket_date'] = parsed_date
                print(f"[DEBUG] Extracted parking_ticket_date: {parsed_date}")
                break
            except ValueError:
                continue
    # Phone extraction: prefer labeled phone numbers; avoid mistaking ticket number for phone
    phone_patterns = [
        r'(?:Phone|Tel|Mobile|Contact)\s*[:.]?\s*([+]?\d[\d\-\s]{7,20})',
        r'([+]?91[-.\s]?\d{10})',
        r'(\d{10,})',
    ]

    # 1) prefer labeled phone
    labeled_match = re.search(phone_patterns[0], text, re.IGNORECASE)
    if labeled_match:
        phone = re.sub(r'[^\d+]', '', labeled_match.group(1).strip())
        if len(phone) >= 10:
            data['phone_number'] = phone
            print(f"[DEBUG] Extracted labeled phone_number: {phone}")

    # 2) fallback: find any standalone 10+ digit number but skip the ticket_no if it matches
    if not data['phone_number']:
        for pattern in phone_patterns[1:]:
            for m in re.finditer(pattern, text):
                phone = re.sub(r'[^\d+]', '', m.group(1).strip())
                if len(phone) >= 10:
                    if ticket_no and phone == ticket_no:
                        print(f"[DEBUG] Skipping phone candidate equal to ticket_no: {phone}")
                        continue
                    data['phone_number'] = phone
                    print(f"[DEBUG] Extracted phone_number: {phone}")
                    break
            if data['phone_number']:
                break
    print(f"[DEBUG] Final parsed parking data: {data}")
    return data

def parse_shopping_text(text):
    """Parse shopping receipt text to extract shopping-specific data"""
    print("Parsing shopping receipt text...")
    
    if not text:
        print("No text to parse")
        return {
            'store_name': None,
            'shopping_bill_no': None,
            'shopping_amount': None,
            'shopping_date': None
        }
    
    data = {
        'store_name': None,
        'shopping_bill_no': None,
        'shopping_amount': None,
        'shopping_date': None
    }
    
    print(f"Raw shopping OCR text:\n{text}\n" + "="*50)
    
    # STORE NAME (from top of receipt)
    lines = text.split('\n')
    for line in lines[:5]:  # Check first 5 lines
        line = line.strip()
        if 3 <= len(line) <= 50 and not line.isdigit() and not re.match(r'^[\d\s\-\/\:]+$', line):
            # Skip lines that are just numbers, dates, or times
            if not re.search(r'(invoice|bill|receipt|order|date|time|total|amount)', line, re.IGNORECASE):
                data['store_name'] = line
                print(f"Found store name: {data['store_name']}")
                break
    
    # SHOPPING BILL NUMBER
    # This is a critical section - we need to ensure reliable bill number extraction
    # Create a direct function to extract bill number with high reliability
    def extract_bill_number(text):
        """Extract bill number with maximum reliability"""
        if not text:
            return None
        
        # Process text line by line for best results with structured receipts
        for line in text.split('\n'):
            line = line.strip()
            
            # Skip very long lines
            if len(line) > 100:
                continue
                
            # CANTEEN BILL FORMAT - Highest priority: "Bill No.:116" - Exact pattern
            canteen_match = re.search(r'Bill\s*No\.?:(\d+)', line, re.IGNORECASE)
            if canteen_match:
                return canteen_match.group(1).strip()
            
            # Other common formats - try on this specific line
            common_patterns = [
                # Bill patterns
                r'Bill\s*No\.?[\s:\.]*(\d+)',  # Various "Bill No" formats
                r'Bill[\s\-]*Number[\s:\.]*(\d+)',  # "Bill-Number: 123"
                r'Bill\s*#[\s:\.]*(\d+)',   # "Bill # 123"
                
                # Receipt patterns
                r'Receipt\s*No[\s:\.]*(\d+)',  # "Receipt No: 123"
                r'Ticket\s*Number[\s:\.]*(\d+)',  # "Ticket Number: 123"
                
                # Invoice patterns
                r'Invoice\s*No[\s:\.]*([A-Z0-9\-]+)',  # "Invoice No: INV123"
                r'Invoice\s*Number[\s:\.]*([A-Z0-9\-]+)',  # "Invoice Number: INV123"
                
                # Transaction/Order patterns
                r'Transaction\s*(?:ID|Id|No)[\s:\.]*([A-Z0-9\-]+)',  # "Transaction ID: TR123"
                r'Order\s*(?:ID|Id|No)[\s:\.]*([A-Z0-9\-]+)',  # "Order ID: ORD123"
                
                # ID patterns
                r'T\.ID\.[\s:]*([A-Z0-9\-]+)',  # "T.ID.: MESO1"
                r'\bID[\s:\.]*([A-Z0-9\-]+)',  # "ID: 123"
            ]
            
            for pattern in common_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        # If still not found, try the full text with more generic patterns
        last_resort_patterns = [
            r'(?:Invoice|Receipt|Bill|Transaction|Ref)\s*(?:No|Number|ID|#)?[\s:\.]+([A-Z0-9\-]{1,})',
            r'\bNo[\s:\.]*([A-Z0-9\-]{1,})',
            r'\bID[\s:\.]*([A-Z0-9\-]{1,})',
            r'([A-Z]{2}[0-9]{4,})',  # Short prefix + numbers
            r'([0-9]{3}\-[0-9]{3,}(?:\-[0-9]{3,})?)',  # Number patterns like 123-456
        ]
        
        for pattern in last_resort_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        return None
    
    # Handle special case for "#INV" format first (before general extraction)
    for line in text.split('\n'):
        if '#' in line:
            # Try to find patterns like "INVOICE #INV-2025-07-04-001"
            hash_match = re.search(r'#([A-Z0-9\-]+)', line, re.IGNORECASE)
            if hash_match:
                data['shopping_bill_no'] = hash_match.group(1).strip()
                print(f"Found bill number (# format): {data['shopping_bill_no']}")
                break
    
    # If not found with special case, use our dedicated function
    if not data['shopping_bill_no']:
        bill_number = extract_bill_number(text)
        if bill_number:
            data['shopping_bill_no'] = bill_number
            print(f"Found bill number: {bill_number}")
        else:
            # Final fallback - look specifically for numbers in specific positions
            for line in text.split('\n'):
                if 'bill' in line.lower() and re.search(r'\d+', line):
                    # Extract the first number found in a line containing "bill"
                    number_match = re.search(r'\d+', line)
                    if number_match:
                        data['shopping_bill_no'] = number_match.group(0)
                        print(f"Found bill number (fallback): {data['shopping_bill_no']}")
                        break
    
    # SHOPPING AMOUNT
    amount_str = extract_total_amount(text)
    if amount_str:
        try:
            data['shopping_amount'] = float(amount_str)
            print(f"Found shopping amount: ₹{data['shopping_amount']}")
        except ValueError:
            print(f"Error converting shopping amount: {amount_str}")
            
    # Use the old method as fallback if the new method fails
    if not data['shopping_amount']:
        amount_patterns = [
            # Tax invoice specific patterns
            r'AMOUNT\s*CHARGEABLE\s*\(?IN\s*WORDS\)?[:\s]*(?:INR|RS)?\.?\s*(\d+[.,]\d{2,3})',
            r'E\s*&\s*O\.E\s*AMOUNT[:\s]*(?:INR|RS)?\.?\s*(\d+[.,]\d{2,3})',
            r'TOTAL\s*INVOICE\s*VALUE\s*(?:\(INR\))?[:\s]*(\d+[.,]\d{2,3})',
            r'INVOICE\s*VALUE\s*(?:\(INR\))?[:\s]*(\d+[.,]\d{2,3})',
            r'TOTAL\s*AMOUNT\s*DUE\s*(?:\(INR\))?[:\s]*(\d+[.,]\d{2,3})',
            # Regular patterns
            r'TOTAL\s*PRICE[:\s]*(\d+[.,]\d{2,3})',
            r'TOTAL[:\s]*(\d+[.,]\d{2,3})',
            r'Total[:\s]*(\d+[.,]\d{2,3})',
            r'Amount[:\s]*(\d+[.,]\d{2,3})',
            r'Grand\s*Total[:\s]*(\d+[.,]\d{2,3})',
            r'Net\s*Total[:\s]*(\d+[.,]\d{2,3})',
            r'₹\s*(\d+[.,]\d{2,3})',
            r'Rs[.\s]*(\d+[.,]\d{2,3})',
            r'(\d+[.,]\d{2})\s*$'  # Amount at end of line
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                # Take the last/largest amount found
                amounts = []
                for match in matches:
                    try:
                        amount = float(match.replace(',', '.'))
                        amounts.append(amount)
                    except ValueError:
                        continue
                if amounts:
                    data['shopping_amount'] = max(amounts)  # Take the largest amount
                    print(f"Found shopping amount (fallback): ₹{data['shopping_amount']}")
                    break
    
    # SHOPPING DATE & TIME
    date_patterns = [
        r'Date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})',
        r'Date[:\s]*(\d{1,2}\s+\w+\s+\d{2,4})',
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})'
    ]
    
    time_patterns = [
        r'Time[:\s]*(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M?)',
        r'(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M)',
        r'(\d{1,2}:\d{2}(?::\d{2})?)'
    ]
    
    date_found = None
    time_found = None
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            date_found = match.group(1).strip()
            print(f"Found shopping date: {date_found}")
            break
    
    for pattern in time_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            time_found = match.group(1).strip()
            print(f"Found shopping time: {time_found}")
            break
    
    if date_found:
        try:
            if time_found:
                datetime_str = f"{date_found} {time_found}"
                # Try different datetime formats
                formats = [
                    '%d/%m/%Y %H:%M:%S',
                    '%d/%m/%Y %H:%M',
                    '%d-%m-%Y %H:%M:%S',
                    '%d-%m-%Y %H:%M',
                    '%d/%m/%y %H:%M:%S',
                    '%d/%m/%y %H:%M'
                ]
                
                for fmt in formats:
                    try:
                        parsed_date = datetime.strptime(datetime_str, fmt)
                        data['shopping_date'] = parsed_date
                        print(f"Parsed shopping datetime: {data['shopping_date']}")
                        break
                    except ValueError:
                        continue
            else:
                # Only date, no time
                date_formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_found, fmt)
                        data['shopping_date'] = parsed_date
                        print(f"Parsed shopping date: {data['shopping_date']}")
                        break
                    except ValueError:
                        continue
        except Exception as e:
            print(f"Error parsing shopping date: {e}")
    
    print(f"Final shopping parsed data: {data}")
    return data

def extract_total_amount(text):
    """
    Extract total amount from receipt text using advanced pattern matching
    Works with various receipt formats including retail stores like D-Mart and tax invoices
    """
    if not text:
        return ""
    
    # Clean and prepare text
    original_text = text  # Keep original text with newlines for some patterns
    text = text.replace('\n', ' ').upper()
    
    # Tax Invoice specific patterns (highest priority)
    tax_invoice_patterns = [
        r'AMOUNT\s*CHARGEABLE\s*\(IN\s*WORDS\)[^\d]*(?:INR|RS)\.?\s*([0-9]+[\.,][0-9]+)', # Amount Chargeable (in words) ... INR 1234.56
        r'E\s*&\s*O\.E\s*AMOUNT\s*:\s*(?:INR|RS)\.?\s*([0-9]+[\.,][0-9]+)', # E & O.E AMOUNT: INR 1234.56
        r'TOTAL\s*INVOICE\s*VALUE\s*[\(\)INR\s]*([0-9]+[\.,][0-9]+)', # TOTAL INVOICE VALUE (INR) 1234.56
        r'INVOICE\s*VALUE\s*[\(\)INR\s]*([0-9]+[\.,][0-9]+)', # INVOICE VALUE (INR) 1234.56
        r'TOTAL\s*AMOUNT\s*DUE\s*[\(\)INR\s]*([0-9]+[\.,][0-9]+)', # TOTAL AMOUNT DUE (INR) 1234.56
        r'TOTAL\s*AMOUNT\s*(?:INR|RS)\.?\s*([0-9]+[\.,][0-9]+)', # TOTAL AMOUNT INR 1234.56
        r'TOTAL\s*(?:INR|RS)\.?\s*([0-9]+[\.,][0-9]+)', # TOTAL INR 1234.56
    ]
    
    # Try tax invoice patterns first
    for pattern in tax_invoice_patterns:
        # Try both in the space-normalized text and original text with newlines
        for search_text in [text, original_text.upper()]:
            matches = re.search(pattern, search_text)
            if matches:
                amount_str = matches.group(1).replace(',', '')
                try:
                    return str(float(amount_str))
                except:
                    pass
    
    # D-Mart and retail specific patterns 
    dmart_patterns = [
        r'AMOUNT\s*RECEIVED\s*FROM\s*CUSTOMER[^0-9]*([0-9]+[\.,][0-9]+)',  # Amount Received From Customer: 951.00
        r'CASH\s*:\s*([0-9]+[\.,][0-9]+)', # Cash: 951.00/-
        r'(?:ITEMS|TOTAL\s*ITEMS)[^:]?(\d+)[^:]?QTY[^:]?(\d+)[^:]?([0-9]+[\.,][0-9]+)', # Items: 10 Qty: 13 951.00
        r'T:\s*[0-9.]+\s+[0-9.]+\s+[0-9.]+\s+[.]+\s+([0-9]+[\.,][0-9]+)', # T: 887.96 31.52 31.52 .... 951.00
        r'BILL\s*(?:NO|AMT)[^:]?[0-9]+[^:]?(?:BILL\s*DT|BILL\s*AMT)[^:]?[^0-9]([0-9]+[\.,][0-9]+)', # Next to BILL NO or BILL AMT
    ]
    
    # Try the retail-specific patterns
    for pattern in dmart_patterns:
        matches = re.search(pattern, text)
        if matches:
            # If the pattern has multiple capturing groups, get the last one
            amount_str = matches.group(matches.lastindex or 1).replace(',', '')
            try:
                return str(float(amount_str))
            except:
                pass
    
    # Try multiple patterns for different bill formats
    total_patterns = [
        r'GRAND\s*TOTAL\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)',  # GRAND TOTAL ₹100.00
        r'TOTAL\s*AMOUNT\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)',  # TOTAL AMOUNT ₹100.00
        r'TOTAL\s*:\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)',       # TOTAL: ₹100.00
        r'AMOUNT\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)',          # AMOUNT ₹100.00
        r'NET\s*AMOUNT\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)',    # NET AMOUNT ₹100.00
        r'(?:TOTAL|AMT)(?:\s*PAID)?\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)', # TOTAL PAID ₹100.00
        r'FINAL\s*AMOUNT\s*(?:[₹RS\.])?\s([0-9]+[\.,][0-9]+)',   # FINAL AMOUNT ₹100.00
    ]
    
    # Now try the common patterns
    for pattern in total_patterns:
        matches = re.search(pattern, text)
        if matches:
            amount = matches.group(1).replace(',', '')
            try:
                return str(float(amount))
            except:
                pass
    
    # Look for "Total" with currency symbol nearby
    total_with_currency = re.search(r'TOTAL[^0-9₹][₹RS\.]\s*([0-9]+[\.,][0-9]+)', text)
    if total_with_currency:
        try:
            return str(float(total_with_currency.group(1).replace(',', '')))
        except:
            pass
                
    # Last resort - find any numbers that could be totals near specific keywords
    last_resort_patterns = [
        r'(?:[₹RS\.])\s([0-9]+[\.,][0-9]+)\s*(?:\/[-])?',  # ₹100.00/-
        r'TOTAL(?:[^0-9]*?)([0-9]+[\.,][0-9]+)', # TOTAL followed by number
        r'AMOUNT\s*(?:IN|DUE|PAYABLE)[^0-9]*([0-9]+[\.,][0-9]+)', # Amount payable/due/in 100.00
        r'INVOICE\s*(?:VALUE|AMOUNT|TOTAL)[^0-9]*([0-9]+[\.,][0-9]+)', # Invoice value/amount 100.00
        r'PAYABLE\s*(?:AMOUNT|VALUE)[^0-9]*([0-9]+[\.,][0-9]+)', # Payable amount 100.00
    ]
    
    for pattern in last_resort_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Take the largest amount found as it's likely the total
            try:
                amounts = [float(m.replace(',', '.')) for m in matches]
                amounts.sort(reverse=True)
                return str(amounts[0])
            except:
                pass
    
    # Try to find amounts in multi-line tax invoice format
    # Look for a total line followed by an amount on the next line
    if '\n' in original_text:
        lines = original_text.upper().split('\n')
        for i in range(len(lines)-1):
            # Check if current line contains total keywords
            if re.search(r'(TOTAL|AMOUNT|INVOICE|GRAND|SUM|NET)\s*(VALUE|AMOUNT|DUE|PAYABLE)?', lines[i]):
                # Check if next line contains just a number that could be an amount
                amount_match = re.search(r'^[₹RS\.\s]*([0-9]+[\.,][0-9]+)', lines[i+1].strip())
                if amount_match:
                    try:
                        return str(float(amount_match.group(1).replace(',', '')))
                    except:
                        pass
    
    # If we still haven't found a match, try to find the highest value in the text
    # that appears near keywords like TOTAL, AMT, SUM
    amount_candidates = re.findall(r'([0-9]+[\.,][0-9]+)', text)
    if amount_candidates:
        try:
            # Filter out very small values (less than 10) as they're unlikely to be totals
            filtered_candidates = []
            for candidate in amount_candidates:
                try:
                    value = float(candidate.replace(',', '.'))
                    if value >= 10.0:  # Only consider values of 10 or more
                        filtered_candidates.append(value)
                except:
                    pass
                    
            if filtered_candidates:
                # If there are multiple same-valued maximums, prioritize values that appear later
                # in the receipt as totals typically appear near the end
                max_amount = max(filtered_candidates)
                # Convert back to original format for searching
                original_candidates = [a for a in amount_candidates if float(a.replace(',', '.')) == max_amount]
                
                # Prefer amounts near total keywords
                for pattern in ['TOTAL', 'AMOUNT', 'INVOICE', 'BILL', 'SUM', 'NET']:
                    for i in range(len(original_text) - 20):
                        window = original_text[i:i+20].upper()
                        if pattern in window:
                            for candidate in original_candidates:
                                if candidate in original_text[i:i+40]:
                                    return str(max_amount)
                
                # If no preferred context found, return the highest value
                return str(max_amount)
        except:
            pass
    
    return ""

def parse_receipt_text(text, receipt_type='auto'):
    """
    Parse receipt text - can auto-detect type or be explicitly set
    receipt_type: 'auto', 'parking', 'shopping'
    """
    print(f"Parsing receipt text (type: {receipt_type})...")
    
    if not text:
        print("No text to parse")
        return {
            'parking_ticket_no': None,
            'vehicle_no': None,
            'parking_ticket_date': None,
            'store_name': None,
            'shopping_bill_no': None,
            'shopping_amount': None,
            'shopping_date': None
        }
    
    # Auto-detect receipt type if not specified
    if receipt_type == 'auto':
        parking_keywords = ['parking', 'ticket', 'vehicle', 'car', 'bike', 'slot', 'entry', 'exit']
        shopping_keywords = ['invoice', 'total', 'amount', 'store', 'shop', 'purchase', 'order', 'receipt']
        
        text_lower = text.lower()
        parking_score = sum(1 for keyword in parking_keywords if keyword in text_lower)
        shopping_score = sum(1 for keyword in shopping_keywords if keyword in text_lower)
        
        if parking_score > shopping_score:
            receipt_type = 'parking'
        else:
            receipt_type = 'shopping'
        
        print(f"Auto-detected receipt type: {receipt_type} (parking_score: {parking_score}, shopping_score: {shopping_score})")
    
    # Parse based on type
    if receipt_type == 'parking':
        return parse_parking_text(text)
    elif receipt_type == 'shopping':
        return parse_shopping_text(text)
    else:
        # Return combined result for backward compatibility
        parking_data = parse_parking_text(text)
        shopping_data = parse_shopping_text(text)
        return {**parking_data, **shopping_data}
    bill_patterns = [
        r'Invoice\s+No[:\s]*([A-Z0-9\-]+)',
        r'Order\s+Id[:\s]*([A-Z0-9\-]+)',
        r'Order\s+No[:\s]*([A-Z0-9\-]+)',
        r'Transaction\s+Id[:\s]*([A-Z0-9\-]+)',
        r'Receipt\s+No[:\s]*([A-Z0-9\-]+)',
        r'Bill\s+No[:\s]*([A-Z0-9\-]+)',
        r'Ref\s+No[:\s]*([A-Z0-9\-]+)',
        r'(?:Invoice|Order|Receipt|Bill|Transaction|Ref)[\s:]+([A-Z0-9\-]{6,})',
        r'No[:\s]*([A-Z0-9\-]{6,})',
        r'ID[:\s]*([A-Z0-9\-]{6,})',
        r'([A-Z]{2,}[0-9]{8,})',
        r'([0-9]{3}\-[0-9]{7}\-[0-9]{7})',
        r'([A-Z0-9]{10,})',
    ]
    for pattern in bill_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            bill_number = match.group(1).strip()
            if not re.match(r'^\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}$', bill_number) and not re.match(r'^\d+\.\d{2}$', bill_number):
                data['shopping_bill_no'] = bill_number
                print(f"Found shopping bill number: {bill_number}")
                break
    # AMOUNT
    # ... existing amount extraction logic ...
    # (replace data['total_amount'] with data['shopping_amount'])
    # DATE
    # ... existing date extraction logic ...
    # (replace data['date_time'] with data['shopping_date'])
    # PARKING TICKET NO
    parking_ticket_patterns = [
        r'Parking\s*Ticket\s*No[:\s]*([A-Z0-9\-]+)',
        r'Parking\s*No[:\s]*([A-Z0-9\-]+)',
        r'Ticket\s*No[:\s]*([A-Z0-9\-]+)',
        r'Parking\s*Slip\s*No[:\s]*([A-Z0-9\-]+)',
        r'Parking\s*ID[:\s]*([A-Z0-9\-]+)'
    ]
    for pattern in parking_ticket_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            data['parking_ticket_no'] = match.group(1).strip()
            print(f"Found parking ticket number: {data['parking_ticket_no']}")
            break
    # VEHICLE NO - Enhanced extraction using specialized function
    vehicle_no = extract_vehicle_no(text)
    if vehicle_no:
        data['vehicle_no'] = vehicle_no
        print(f"Found vehicle number using specialized function: {data['vehicle_no']}")
    else:
        # Fallback to basic patterns if specialized extraction fails
        vehicle_patterns = [
            r'Vehicle\s*No[:\s]*([A-Z]{2,3}\s*\d{1,4}\s*[A-Z]{0,2}\s*\d{1,4})',
            r'Vehicle\s*Number[:\s]*([A-Z]{2,3}\s*\d{1,4}\s*[A-Z]{0,2}\s*\d{1,4})',
            r'Car\s*No[:\s]*([A-Z]{2,3}\s*\d{1,4}\s*[A-Z]{0,2}\s*\d{1,4})',
            r'Bike\s*No[:\s]*([A-Z]{2,3}\s*\d{1,4}\s*[A-Z]{0,2}\s*\d{1,4})',
            r'Vehicle[:\s]*([A-Z]{2,3}\s*\d{1,4}\s*[A-Z]{0,2}\s*\d{1,4})'
        ]
        for pattern in vehicle_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                data['vehicle_no'] = match.group(1).strip()
                print(f"Found vehicle number using fallback pattern: {data['vehicle_no']}")
                break
    # ... rest of the function ...
    return data

def clean_ticket_number(ticket_no):
    """Clean a ticket number by removing common suffix patterns and noise"""
    if not ticket_no:
        return ticket_no
        
    # Remove underscore followed by digits pattern (e.g., "1234567_18_112" -> "1234567")
    # This handles the specific issue mentioned by the user
    ticket_no = re.sub(r'_\d+(_\d+)?$', '', ticket_no)
    
    # Remove any trailing noise after slashes, dashes or underscores if they don't appear to be part of the main number
    if '/' in ticket_no or '-' in ticket_no or '_' in ticket_no:
        # Keep the main part plus one level of hierarchy
        parts = re.split(r'[/_-]', ticket_no)
        if len(parts) > 2:
            # For formats like "AB/2023-24/123", keep all parts
            if re.match(r'\d{2,4}(-|/)\d{2,4}', parts[1]):
                cleaned = '/'.join(parts[:3]) if '/' in ticket_no else '-'.join(parts[:3])
            else:
                # For other formats, just keep two parts
                cleaned = '/'.join(parts[:2]) if '/' in ticket_no else \
                       '-'.join(parts[:2]) if '-' in ticket_no else \
                       '_'.join(parts[:2])
            ticket_no = cleaned
    
    return ticket_no

def extract_vehicle_no(text):
    """Specialized function to extract vehicle numbers from receipt text - ENHANCED FOR LOW QUALITY IMAGES"""
    if not text:
        return None
    
    # List of Indian state codes for validation
    indian_state_codes = [
        'AP', 'AR', 'AS', 'BR', 'CG', 'CH', 'DD', 'DL', 'DN', 'GA', 'GJ', 
        'HP', 'HR', 'JH', 'JK', 'KA', 'KL', 'LA', 'LD', 'MH', 'ML', 'MN', 
        'MP', 'MZ', 'NL', 'OD', 'PB', 'PY', 'RJ', 'SK', 'TN', 'TR', 'TS', 
        'UK', 'UP', 'WB'
    ]
    
    # Common OCR errors for state codes
    state_code_fixes = {
        'I<A': 'KA', 'l<A': 'KA', 'XA': 'KA', 'IKA': 'KA', 'LKA': 'KA', '1<A': 'KA', 'KR': 'KA',
        'I(A': 'KA', 'l(A': 'KA', 'ICA': 'KA',
        'OL': 'DL', '0L': 'DL', 'D1': 'DL', '01': 'DL',
        'TH': 'TN', '1N': 'TN', 'IN': 'TN',
        'MII': 'MH', 'NH': 'MH', 'HH': 'MH',
        'I(P': 'KP', 'l(P': 'KP',
        'I(L': 'KL', 'l(L': 'KL',
        'BJ': 'RJ', 'R1': 'RJ', 'RJ1': 'RJ',
        'O0': 'OD', 'OD': '0D'
    }
    
    # Clean the text for better pattern matching
    clean_text = re.sub(r'[\s\n]+', ' ', text).upper().strip()
    
    # STRATEGY 1: Try labeled patterns first (most reliable)
    labeled_patterns = [
        # Terminal format patterns with labels
        r'VEH(?:ICLE)?\s*(?:NO|NUMBER|TYPE)\.?\s*[:=]\s*([A-Z0-9]{2}\s*\d{2,4}\s*[A-Z0-9]{1,4}\s*\d{1,4})',
        r'VEH(?:ICLE)?\s*(?:NO|NUMBER|TYPE)\.?\s*[:=]\s*([A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4})',
        
        # Common Indian vehicle number patterns with labels
        r'(?:CAR|VEHICLE|VEH)(?:ICLE)?\s*(?:NO|NUMBER|#)\.?\s*[:=]?\s*([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})',
        r'REG(?:ISTRATION)?\s*(?:NO|NUMBER)\.?\s*[:=]?\s*([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{1,4})',
        
        # Extra flexible patterns for low quality images
        r'VEH.*NO.*[:=]\s*([A-Z0-9]{2}[^A-Z]{0,4}\d{1,4}[^0-9]{0,4}[A-Z0-9]{1,4}[^A-Z]{0,4}\d{1,4})',
        r'[VUY]EH.*(?:NO|HD|ND).*[:=;.,]?\s*([A-Z0-9]{2}[^A-Z]{0,4}\d{1,4}[^0-9]{0,4}[A-Z0-9]{1,4}[^0-9]{0,4}\d{1,4})'
    ]
    
    for pattern in labeled_patterns:
        match = re.search(pattern, clean_text)
        if match:
            raw_vehicle_no = match.group(1).strip()
            # Clean up the match by removing non-alphanumeric characters
            vehicle_no = re.sub(r'[^A-Z0-9]', '', raw_vehicle_no)
            
            # Apply state code corrections
            if len(vehicle_no) >= 2:
                state_part = vehicle_no[:2]
                if state_part in state_code_fixes:
                    vehicle_no = state_code_fixes[state_part] + vehicle_no[2:]
                
                # Apply positional corrections for OCR errors
                vehicle_no = apply_ocr_fixes(vehicle_no)
                
                # Validate the vehicle number
                if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                    print(f"Found vehicle number from labeled pattern: {vehicle_no}")
                    return vehicle_no
    
    # STRATEGY 2: Line-by-line approach for terminal tickets
    lines = text.split('\n')
    for line in lines:
        line = line.strip().upper()
        
        # Skip long lines - vehicle numbers usually appear in shorter lines
        if len(line) > 40:
            continue
            
        # Look for lines containing vehicle number indicators
        if re.search(r'VEH|VEHICLE|CAR|REG|PLATE', line):
            # Extract the part after any separator
            separator_index = -1
            for sep in [':', '=', '-', '.', ' ']:
                if sep in line:
                    pos = line.find(sep)
                    if pos > 5 and (separator_index == -1 or pos < separator_index):
                        separator_index = pos
            
            if separator_index > -1:
                after_separator = line[separator_index+1:].strip()
                
                # Try to extract a vehicle number from this part
                for state in indian_state_codes:
                    veh_match = re.search(f"{state}\\s*\\d{{1,2}}\\s*[A-Z0-9]{{1,3}}\\s*\\d{{1,4}}", after_separator)
                    if veh_match:
                        vehicle_no = re.sub(r'[^A-Z0-9]', '', veh_match.group(0))
                        vehicle_no = apply_ocr_fixes(vehicle_no)
                        if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                            print(f"Found vehicle number from line with separator: {vehicle_no}")
                            return vehicle_no
            
            # For lines without clear separators but with vehicle indicators
            # Try to extract any pattern that looks like a vehicle number
            for state in indian_state_codes:
                veh_match = re.search(f"{state}\\s*\\d{{1,2}}\\s*[A-Z0-9]{{1,3}}\\s*\\d{{1,4}}", line)
                if veh_match:
                    vehicle_no = re.sub(r'[^A-Z0-9]', '', veh_match.group(0))
                    vehicle_no = apply_ocr_fixes(vehicle_no)
                    if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                        print(f"Found vehicle number from line with vehicle indicators: {vehicle_no}")
                        return vehicle_no
        
        # Check every line for standalone vehicle number patterns (common in terminal tickets)
        # Look for state code followed by digits and letters
        for state in indian_state_codes:
            if state in line:
                veh_patterns = [
                    f"{state}\\s*\\d{{1,2}}\\s*[A-Z]{{1,3}}\\s*\\d{{1,4}}",  # Standard format with spaces
                    f"{state}\\d{{1,2}}[A-Z]{{1,3}}\\d{{1,4}}",              # Standard format without spaces
                    f"{state}[^A-Z0-9]*\\d{{1,2}}[^A-Z0-9]*[A-Z]{{1,3}}[^A-Z0-9]*\\d{{1,4}}" # Very flexible
                ]
                
                for pattern in veh_patterns:
                    veh_match = re.search(pattern, line)
                    if veh_match:
                        vehicle_no = re.sub(r'[^A-Z0-9]', '', veh_match.group(0))
                        vehicle_no = apply_ocr_fixes(vehicle_no)
                        if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                            print(f"Found vehicle number from standalone line: {vehicle_no}")
                            return vehicle_no
                
                # Terminal/airport format where vehicle number is like "ka56df4578"
                terminal_match = re.search(f"{state}\\s*\\d{{2,4}}\\s*[A-Z0-9]{{1,4}}\\s*\\d{{1,4}}", line)
                if terminal_match:
                    vehicle_no = re.sub(r'[^A-Z0-9]', '', terminal_match.group(0))
                    vehicle_no = apply_ocr_fixes(vehicle_no)
                    if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                        print(f"Found terminal format vehicle number: {vehicle_no}")
                        return vehicle_no
    
    # STRATEGY 3: Look for special terminal formats in entire text
    terminal_formats = [
        # Terminal-specific formats with more tolerance for OCR errors
        r'[KX][AO]\s*\d{2,4}\s*[A-Z0-9]{1,4}\s*\d{1,4}',  # KA format (common in Karnataka)
        r'[DQ][L1I]\s*\d{2,4}\s*[A-Z0-9]{1,4}\s*\d{1,4}',  # DL format (common in Delhi)
        r'[MT][HN]\s*\d{2,4}\s*[A-Z0-9]{1,4}\s*\d{1,4}',  # MH format (common in Maharashtra)
        r'[TI][NH]\s*\d{2,4}\s*[A-Z0-9]{1,4}\s*\d{1,4}',  # TN format (common in Tamil Nadu)
    ]
    
    for pattern in terminal_formats:
        match = re.search(pattern, clean_text)
        if match:
            vehicle_no = re.sub(r'[^A-Z0-9]', '', match.group(0))
            vehicle_no = apply_ocr_fixes(vehicle_no)
            if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                print(f"Found vehicle number from terminal format: {vehicle_no}")
                return vehicle_no
    
    # STRATEGY 4: Last resort - look for any sequence that could be a vehicle number
    # This catches very poor OCR where even the state code is badly mangled
    for state in indian_state_codes:
        for variant in [state, state.replace('A', '4'), state.replace('I', '1'), state.replace('O', '0')]:
            last_resort_pattern = f"{variant}[^A-Z]*\\d{{1,4}}[^A-Z0-9]*[A-Z0-9]{{1,4}}[^A-Z0-9]*\\d{{1,4}}"
            match = re.search(last_resort_pattern, clean_text)
            if match:
                vehicle_no = re.sub(r'[^A-Z0-9]', '', match.group(0))
                # Replace the detected variant with the correct state code
                vehicle_no = state + vehicle_no[len(variant):]
                vehicle_no = apply_ocr_fixes(vehicle_no)
                if is_valid_vehicle_no(vehicle_no, indian_state_codes):
                    print(f"Found vehicle number from last resort pattern: {vehicle_no}")
                    return vehicle_no
    
    return None

def apply_ocr_fixes(vehicle_no):
    """Apply OCR fixes based on position in vehicle number"""
    if len(vehicle_no) < 4:
        return vehicle_no
        
    # First two chars should be letters (state code)
    state_part = vehicle_no[:2].replace('0', 'O').replace('1', 'I').replace('8', 'B')
    
    # Characters 3-4 should be numbers (region code)
    region_part = ''
    if len(vehicle_no) >= 4:
        region_part = vehicle_no[2:4].replace('O', '0').replace('I', '1').replace('S', '5').replace('B', '8')
    
    # Characters 5+ have mixed letters and numbers
    remaining_part = ''
    if len(vehicle_no) > 4:
        # For the letter part (series)
        series_len = min(3, len(vehicle_no) - 4)  # Up to 3 letters for series
        series_part = vehicle_no[4:4+series_len].replace('0', 'O').replace('1', 'I').replace('5', 'S')
        
        # For the number part (last 4 digits)
        number_part = ''
        if len(vehicle_no) > 4+series_len:
            number_part = vehicle_no[4+series_len:].replace('O', '0').replace('I', '1').replace('S', '5').replace('B', '8')
        
        remaining_part = series_part + number_part
    
    # Compose the corrected vehicle number
    return state_part + region_part + remaining_part

def is_valid_vehicle_no(vehicle_no, indian_state_codes):
    """Validate that the vehicle number has a valid state code and reasonable format"""
    if len(vehicle_no) < 6:  # Minimum reasonable length
        return False
        
    # Validate state code
    state_part = vehicle_no[:2]
    if state_part not in indian_state_codes:
        return False
        
    # Validate region code is numeric
    if not vehicle_no[2:4].isdigit():
        return False
        
    # Make sure we have both letter and number components after region
    if len(vehicle_no) <= 4:
        return False
        
    return True

def extract_parking_ticket_no(text):
    """Specialized function to extract parking ticket numbers from text - ENHANCED FOR LOW QUALITY IMAGES"""
    if not text:
        return None
    
    # Clean up the text for better pattern matching
    clean_text = re.sub(r'[\s\n]+', ' ', text).strip()
    
    # List of common OCR errors in parking tickets and their corrections
    ocr_corrections = {
        'o': '0', 'O': '0',
        'l': '1', 'I': '1',
        'S': '5', 'B': '8',
        'G': '6',
        'Z': '2',
        'T': '7',
        'A': '4',
        'U': '0'
    }
    
    # Patterns specific to parking ticket numbers - ordered by specificity
    parking_ticket_patterns = [
        # AIRPORT/TERMINAL SPECIFIC PATTERNS FOR STANDALONE NUMBERS (like "1188202")
        r'(?:[Tt][Ee][Rr][Mm][Ii][Nn][Aa][Ll]|[Aa][Ii][Rr][Pp][Oo][Rr][Tt])\s*[Pp][Aa][Rr][Kk][Ii][Nn][Gg].*?(?:^|\s)(\d{6,8})(?:$|\s)',
        r'[Pp][Aa][Rr][Kk][Ii][Nn][Gg]\s*(?:[Tt][Ee][Rr][Mm][Ii][Nn][Aa][Ll]|[Aa][Ii][Rr][Pp][Oo][Rr][Tt]).*?(?:^|\s)(\d{6,8})(?:$|\s)',
        
        # NEW PATTERNS FOR TERMINAL/AIRPORT TICKETS - HIGHEST PRIORITY
        r'[tT][eE][rR][mM][iI][nN][aA][lL].*[iI][dD].*[tT][iI][cC][kK][eE][tT].*[nN][oO].*[:=\-.]?\s*(\d{5,8})',
        r'[tT][iI][cC][kK][eE][tT].*[nN][oO].*[:=\-.]?\s*(\d{5,8})',
        r'[eE][nN][tT][rR][yY].*[tT][iI][cC][kK][eE][tT].*[nN][oO].*[:=\-.]?\s*(\d{5,8})',
        
        # ENHANCED PATTERN FOR TERMINAL TICKETS WITH LOW QUALITY OCR
        # More permissive matching for "Ticket No" with potential OCR errors
        r'T[l1Ii]CKE[tT][\s.]*(?:NO|N0|NUM(?:BER)?)[\s.]*[:=,.]?\s*(\d{5,8})',
        r'T[l1Ii]CKE[tT][\s.]*(?:NO|N0|NUM(?:BER)?)[\s.]*[:=,.]?\s*(\d+)',
        
        # PATTERNS FOR AIRPORT/TERMINAL TICKETS (like in sample: "1188202")
        r'(?:TERMINAL|TERM)[\s.]*[lI1]D[\s.]*:?\s*\d+\s*(?:TICKET|TKT)[\s.]*(?:NO|N0)[\s.]*:?\s*(\d+)',
        
        # Completely separated patterns (when ticket number is on its own line)
        r'(?:TERMINAL|TERM|AIRPORT).*\n\s*(\d{6,8})(?:\s|$)',
        r'(?:TICKET|TKT).*(?:NO|N0).*\n\s*(\d{6,8})(?:\s|$)',
        
        # Regular patterns
        r'(?:Parking|Park)\s*(?:Ticket|Receipt)\s*(?:No|Number|#|ID)?\s*[:.]?\s*([A-Za-z0-9\-_/]{4,})',
        r'(?:Ticket|TKT)\s*(?:No|Number|ID|Id|#)\s*[:.]?\s*([A-Za-z0-9\-_/]{4,})',
        r'(?:Receipt|Bill)\s*(?:No|Number|#)\s*[:.]?\s*([A-Za-z0-9\-_/]{4,})',
        
        # Mall-specific formats that might be seen on parking tickets
        r'(?:Mall|Parking)\s*(?:ID|No|Code)\s*[:.]?\s*([A-Za-z0-9\-_/]{4,})',
        r'(?:Token|Tokens)\s*(?:ID|No|Number)\s*[:.]?\s*([A-Za-z0-9\-_/]{4,})',
        
        # Common ticket number formats with different separators
        r'[Nn]o\.?\s*[:.]?\s*([A-Z0-9\-_/]{4,})',  # For "No: 12345" or "No. 12345"
        r'#\s*([A-Z0-9\-_/]{4,})',  # For "# 12345"
        
        # Look for specific patterns common in parking tickets
        r'(?<!\w)([A-Z]{1,3}[0-9]{4,8})(?!\w)',  # Like "P12345" or "PKG123456"
        r'(?<!\w)(PKG|PRK|TKT|TCK|PK|PT)[_\-]?([0-9]{4,8})(?!\w)',  # Like "PKG-12345"
        r'(?<!\w)(PKG|PRK|TKT|TCK|PK|PT)[_\-\s]([0-9]{4,8})(?!\w)',  # Like "PKG 12345"
        
        # For handling common formats in Indian parking systems
        r'(?<!\w)([A-Z]{1,2}\-[0-9]{4,8})(?!\w)',  # Like "P-12345"
        r'(?<!\w)([A-Z]{1,2}[0-9]{4,8})(?!\w)',     # Like "P12345"
        
        # Last resort patterns (more strict validation to avoid false positives)
        r'(?<!\w)([0-9]{5,8})(?!\w)'  # 5-8 digits in a row, standalone
    ]
    
    # First pass: try all patterns on the full text
    for pattern in parking_ticket_patterns:
        # Try on original text
        ticket_match = re.search(pattern, clean_text, re.IGNORECASE)
        if ticket_match:
            # If the pattern has two groups, combine them
            if len(ticket_match.groups()) > 1 and ticket_match.group(2):
                extracted_ticket = f"{ticket_match.group(1)}{ticket_match.group(2)}"
            else:
                extracted_ticket = ticket_match.group(1).strip()
            
            # Validate and clean the extracted ticket number
            if len(extracted_ticket) >= 4 and not re.match(r'^(0{4,}|1{4,}|total|amount|paid|date|time)$', extracted_ticket, re.IGNORECASE):
                cleaned_ticket = clean_ticket_number(extracted_ticket)
                print(f"Found parking ticket number: {extracted_ticket}, cleaned to: {cleaned_ticket}")
                return cleaned_ticket
    
    # Second pass: try line-by-line analysis - ENHANCED FOR AIRPORT/TERMINAL TICKET NUMBERS
    lines = text.split('\n')
    
    # First check for context clues that we're dealing with an airport/terminal ticket
    is_terminal_ticket = False
    for line in lines:
        if re.search(r'(?:terminal|airport|entry|exit|parking)\s*(?:ticket|parking|fee)', line, re.IGNORECASE):
            is_terminal_ticket = True
            print("Detected terminal/airport parking context")
            break
    
    # Now look for standalone ticket numbers, with priority for airport/terminal format
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Airport/Terminal ticket handling - special focus on 6-8 digit numbers as in "1188202"
        if is_terminal_ticket and len(line) < 20:
            # Check for standalone 6-8 digit numbers first (highest priority for airport/terminal tickets)
            if re.match(r'^[0-9]{6,8}$', line):
                cleaned_ticket = clean_ticket_number(line)
                print(f"Found terminal/airport ticket number: {line}, cleaned to: {cleaned_ticket}")
                return cleaned_ticket
        
        # Regular parking ticket processing
        if line and len(line) < 30:  # Short lines are more likely to be just the ticket number
            # Look for standalone numeric or alphanumeric strings that could be ticket numbers
            if re.match(r'^[A-Z0-9\-_/]{4,}$', line, re.IGNORECASE) and not re.match(r'^(date|time|total|amount|paid|cash|card|payment).*$', line, re.IGNORECASE):
                # Check for common parking ticket prefixes
                for prefix in ['PKG', 'PRK', 'TKT', 'TCK', 'PT', 'PK', 'P']:
                    if line.upper().startswith(prefix) and (len(line) - len(prefix) >= 4):
                        cleaned_ticket = clean_ticket_number(line)
                        print(f"Found parking ticket number from prefix match: {line}, cleaned to: {cleaned_ticket}")
                        return cleaned_ticket
                
                # If line is just digits and reasonable length for a ticket number
                if re.match(r'^[0-9]{4,8}$', line):
                    cleaned_ticket = clean_ticket_number(line)
                    print(f"Found parking ticket number from digits-only line: {line}, cleaned to: {cleaned_ticket}")
                    return cleaned_ticket
                
                # If line looks like a ticket ID with reasonable length (but not a date)
                if not re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$', line) and len(line) >= 5:
                    cleaned_ticket = clean_ticket_number(line)
                    print(f"Found parking ticket number from standalone line: {line}, cleaned to: {cleaned_ticket}")
                    return cleaned_ticket
    
    # Third pass: Context-aware extraction
    # Look for specific lines that often precede or follow ticket numbers
    context_indicators = ['ticket', 'number', 'parking', 'id', 'token']
    for i, line in enumerate(lines):
        if i < len(lines) - 1:  # Check if not the last line
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in context_indicators):
                next_line = lines[i + 1].strip()
                # If the next line looks like a ticket number
                if next_line and len(next_line) >= 4 and len(next_line) <= 15:
                    if re.match(r'^[A-Z0-9\-_/]+$', next_line, re.IGNORECASE) and not re.match(r'^(date|time|total|amount|paid).*$', next_line, re.IGNORECASE):
                        cleaned_ticket = clean_ticket_number(next_line)
                        print(f"Found parking ticket number from context: {next_line}, cleaned to: {cleaned_ticket}")
                        return cleaned_ticket
    
    # SPECIAL HANDLING FOR AIRPORT/TERMINAL TICKETS (like "1188202")
    # Look specifically for standalone 6-8 digit sequences in the text
    standalone_matches = re.finditer(r'(?<![A-Za-z0-9])(\d{6,8})(?![A-Za-z0-9])', text)
    for match in standalone_matches:
        potential_ticket = match.group(1)
        # Verify it's not likely to be a date, amount, or phone number
        if not re.search(r'\d{2}[/:-]\d{2}[/:-]\d{4}|\d{1,3},\d{3}|[+]\d', potential_ticket):
            cleaned_ticket = clean_ticket_number(potential_ticket)
            print(f"Found standalone airport/terminal ticket number: {potential_ticket}, cleaned to: {cleaned_ticket}")
            return cleaned_ticket
    
    # Try fixing common OCR errors in numeric sequences that might be ticket numbers
    # This is our last resort
    num_sequences = re.finditer(r'[A-Za-z0-9]{4,}', text)
    for match in num_sequences:
        potential_ticket = match.group(0)
        
        # Apply OCR corrections
        fixed_ticket = ''.join([ocr_corrections.get(c, c) for c in potential_ticket])
        
        # If it now looks like a ticket number (has more digits)
        if sum(c.isdigit() for c in fixed_ticket) >= 4:
            cleaned_ticket = clean_ticket_number(fixed_ticket)
            print(f"Found parking ticket number after OCR correction: {fixed_ticket} (was {potential_ticket}), cleaned to: {cleaned_ticket}")
            return cleaned_ticket
    
    return None

def extract_bill_number(text):
    """Specialized function to extract bill numbers from shopping receipt text"""
    if not text:
        return None
    
    # Enhanced bill number extraction with comprehensive patterns
    bill_patterns = [
        # Common explicit bill number patterns with various labels
        r'(?:Receipt|Bill|Invoice)\s*(?:No|Number|ID|Id|#)\s*[:.]?\s*([A-Za-z0-9\-_/]+)',
        r'(?:Memo|Receipt|Bill|Invoice)\s*[:.]?\s*(?:#|No|Number)?\s*([A-Za-z0-9\-_/]+)',
        r'(?:Trans|Transaction)\s*(?:No|Number|ID|Id|#)\s*[:.]?\s*([A-Za-z0-9\-_/]+)',
        r'(?:Order|ORD)\s*(?:No|Number|ID|Id|#)\s*[:.]?\s*([A-Za-z0-9\-_/]+)',
        r'(?:Ref|Reference)\s*(?:No|Number|ID|Id|#)\s*[:.]?\s*([A-Za-z0-9\-_/]+)',
        
        # Common formats with alternative separators
        r'No\.?\s*[:#]?\s*([A-Za-z0-9\-_/]+)',  # For "No: 12345" or "No. 12345"
        r'#\s*([A-Za-z0-9\-_/]{4,})',  # For "# 12345"
        
        # Format without labels but with predictable structure
        r'(?<!\w)([A-Z]{2,}[0-9]{4,}|[0-9]{4,}[A-Z]{2,})(?!\w)',  # For patterns like "INV12345" or "12345INV"
        r'(?<!\w)([A-Z][0-9]{5,}[A-Z]?)(?!\w)',  # For patterns like "A12345B"
    ]
    
    # Step 1: Try the explicit patterns first
    for pattern in bill_patterns:
        bill_match = re.search(pattern, text, re.IGNORECASE)
        if bill_match:
            extracted_bill = bill_match.group(1).strip()
            # Enhanced filtering of false positives
            if (not re.match(r'^(spices|chefs|food|court|payment|receipt|advance|thanks|total|amount|cash|card|paid)$', 
                           extracted_bill, re.IGNORECASE) and
                not re.match(r'^[0-9]{1,2}[:.][0-9]{1,2}$', extracted_bill) and  # Filter out time formats like "10:30"
                len(extracted_bill) >= 3):  # Must be at least 3 characters
                cleaned_bill = clean_ticket_number(extracted_bill)
                print(f"Found bill number using pattern '{pattern}': {extracted_bill}, cleaned to: {cleaned_bill}")
                return cleaned_bill
    
    # Step 2: Try line-by-line analysis
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        # Look for lines that might contain just the bill number
        if i > 0 and i < 10:  # Check first 10 lines, skip the very first line (often store name)
            # Check for patterns like "No. 12345" or just "12345" on their own line
            isolated_match = re.match(r'^(?:No\.?|#)?\s*([A-Z0-9\-_/]{5,})$', line, re.IGNORECASE)
            if isolated_match:
                extracted_bill = isolated_match.group(1).strip()
                if (not re.match(r'^(spices|chefs|food|court|payment|receipt|advance|thanks|total|amount|cash|card|paid)$', 
                               extracted_bill, re.IGNORECASE) and
                    len(extracted_bill) >= 5):  # Must be at least 5 characters for isolated matches
                    cleaned_bill = clean_ticket_number(extracted_bill)
                    print(f"Found bill number from isolated line: {extracted_bill}, cleaned to: {cleaned_bill}")
                    return cleaned_bill
    
    # Step 3: Context-aware bill number extraction
    for i in range(len(lines) - 1):
        current_line = lines[i].strip().lower()
        next_line = lines[i + 1].strip()
        
        # Look for key phrases in the current line that suggest the next line contains the bill number
        if any(phrase in current_line for phrase in ['bill', 'invoice', 'receipt', 'transaction', 'order', 'no.', 'number']):
            # Check if the next line looks like a bill number (alphanumeric with optional separators)
            if re.match(r'^[A-Z0-9\-_/]{5,}$', next_line, re.IGNORECASE):
                if not re.match(r'^(spices|chefs|food|court|payment|receipt|advance|thanks|total|amount|cash|card|paid)$', 
                              next_line, re.IGNORECASE):
                    cleaned_bill = clean_ticket_number(next_line)
                    print(f"Found bill number using context-aware approach: {next_line}, cleaned to: {cleaned_bill}")
                    return cleaned_bill
            
            # Try to extract from the next line if it has a specific format
            next_line_match = re.search(r'(?<!\w)([A-Z0-9]{5,}[\-_/]?[A-Z0-9]{2,})(?!\w)', next_line, re.IGNORECASE)
            if next_line_match:
                extracted_bill = next_line_match.group(1).strip()
                if len(extracted_bill) >= 5:
                    print(f"Found bill number from next line after key phrase: {extracted_bill}")
                    return extracted_bill
    
    # No bill number found
    return None