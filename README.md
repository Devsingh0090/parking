# Smart Parking Validation System

An intelligent solution that automates parking fee validation based on shopping receipts using OCR technology.

## Features

- **Bill Upload**: Upload parking and shopping bills via drag & drop interface
- **OCR Processing**: Automatic text extraction from uploaded images using EasyOCR
- **Database Storage**: All extracted data is stored in SQLite database
- **Gallery View**: Visual gallery of all uploaded receipts
- **Parking Validation**: Automated validation of parking fees based on shopping amounts
- **Dashboard**: Real-time statistics and analytics

## System Workflow

1. **Upload Bills**: Users upload parking bills first, then shopping bills
2. **OCR Processing**: System extracts text and data from uploaded images
3. **Database Storage**: Extracted data is stored in receipts database
4. **Gallery Display**: Bills appear in the receipts gallery
5. **Validation**: System determines if parking fees should be waived based on shopping amount

## Installation

### Windows
1. Run `setup.bat`
2. Activate virtual environment: `venv\Scripts\activate`
3. Start application: `python app.py`

### Linux/Mac
1. Run `chmod +x setup.sh && ./setup.sh`
2. Activate virtual environment: `source venv/bin/activate`
3. Start application: `python app.py`

### Manual Installation
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p static/receipts

# Run application
python app.py
```

## Dependencies

- Flask (Web framework)
- EasyOCR (OCR processing)
- Pillow (Image processing)
- SQLite (Database)
- PyTorch (Deep learning backend for OCR)

## Usage

1. **Access the Application**: Open http://localhost:5000 in your browser
2. **Upload Bills**: Go to Validator page and upload bills in sequence
3. **View Results**: Check Gallery and Database for processed bills
4. **Monitor Stats**: Use Dashboard for analytics

## API Endpoints

- `POST /upload_receipt` - Upload and process receipt files
- `POST /api/validate_uploaded_bills` - Validate parking based on uploaded bills
- `GET /api/receipts` - Get all receipts data
- `GET /api/dashboard_stats` - Get dashboard statistics

## File Structure

```
parking/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── setup.bat                      # Windows setup script
├── setup.sh                       # Linux/Mac setup script
├── receipts.db                    # SQLite database (auto-created)
├── static/
│   └── receipts/                  # Uploaded receipt images
└── templates/
    ├── index.html                 # Home page
    ├── parking_validation.html    # Upload and validation page
    ├── receipts.html              # Database records page
    └── receipts_folder.html       # Gallery page
```

## Database Schema

### receipts table
- `id` - Primary key
- `filename` - Uploaded file name
- `bill_number` - Extracted bill number
- `store_name` - Store/merchant name
- `total_amount` - Bill total amount
- `date_time` - Transaction date/time
- `phone_number` - Customer phone number
- `items` - JSON array of purchased items
- `parking_status` - Validation status
- `raw_ocr_text` - Raw OCR extracted text
- `processed_at` - Processing timestamp
- `upload_type` - Type of upload (validation/direct)

## Configuration

- Upload folder: `static/receipts`
- Max file size: 16MB
- Supported formats: PNG, JPG, JPEG, GIF, PDF
- Minimum shopping amount for parking waiver: ₹500
- Default parking fee: ₹50

## OCR Data Extraction

The system extracts the following information from receipts:
- Bill numbers (various formats)
- Total amounts (₹ symbols, decimal amounts)
- Phone numbers (10-digit Indian format)
- Dates and times
- Store names
- Individual items and prices

## Troubleshooting

1. **OCR not working**: Ensure EasyOCR is properly installed with PyTorch
2. **Upload failing**: Check file permissions in static/receipts folder
3. **Database errors**: Delete receipts.db to reset database
4. **Port conflicts**: Change port in app.py if 5000 is in use

## Support

For technical support or feature requests, please check the system logs or contact the development team.
