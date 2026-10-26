import os
import sys
import sqlite3
import json
import traceback
import numpy as np
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import tensorflow as tf
from tensorflow.keras.models import load_model # type: ignore
from PIL import Image

# ============= PATH RESOLUTION =============
def get_resource_path(relative_path):
    """Get correct path for PyInstaller .exe or normal Python"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ============= FLASK APP =============
app = Flask(__name__, 
    template_folder=get_resource_path('templates'),
    static_folder=get_resource_path('static')
)

app.config['UPLOAD_FOLDER'] = get_resource_path('uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============= LOAD MODEL =============
ai_model = None
try:
    model_path = get_resource_path('model/waste_model.h5')
    if os.path.exists(model_path):
        ai_model = load_model(model_path)
        print(f"✅ Model loaded: {model_path}")
    else:
        print(f"❌ Model not found: {model_path}")
except Exception as e:
    print(f"❌ Error loading model: {str(e)}")
    print(traceback.format_exc())

# ============= CONSTANTS =============
CLASS_MAPPING = {0: 'Metal', 1: 'Organic', 2: 'Plastic'}
WASTE_TYPES = ['Metal', 'Organic', 'Plastic']
BIN_INCREMENT = 5  # +5% per detection
BIN_CAPACITY = 100

# ============= DATABASE =============
def get_db_path():
    return get_resource_path('database.db')

def init_db():
    """Initialize database tables"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Waste records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waste_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waste_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filename TEXT,
            image_path TEXT,
            bin_status TEXT
        )
    ''')
    
    # Bin status table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bin_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin_name TEXT UNIQUE NOT NULL,
            fill_level INTEGER DEFAULT 0,
            status TEXT DEFAULT 'OK'
        )
    ''')
    
    conn.commit()
    
    # Initialize bins if empty
    cursor.execute('SELECT COUNT(*) FROM bin_status')
    if cursor.fetchone()[0] == 0:
        for waste_type in WASTE_TYPES:
            bin_name = f"{waste_type} Bin"
            cursor.execute(
                'INSERT INTO bin_status (bin_name, fill_level, status) VALUES (?, ?, ?)',
                (bin_name, 0, 'OK')
            )
        conn.commit()
    
    conn.close()

def get_bin_status(waste_type):
    """Get current bin status for waste type"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    bin_name = f"{waste_type} Bin"
    cursor.execute(
        'SELECT fill_level, status FROM bin_status WHERE bin_name = ?',
        (bin_name,)
    )
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'fill_level': result[0], 'status': result[1]}
    return {'fill_level': 0, 'status': 'OK'}

def update_bin_level(waste_type):
    """Update bin level after detection"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    bin_name = f"{waste_type} Bin"
    
    # Get current level
    cursor.execute('SELECT fill_level FROM bin_status WHERE bin_name = ?', (bin_name,))
    result = cursor.fetchone()
    current_level = result[0] if result else 0
    
    # Calculate new level
    new_level = min(current_level + BIN_INCREMENT, BIN_CAPACITY)
    
    # Determine status
    if new_level >= 100:
        new_status = 'FULL'
    elif new_level >= 80:
        new_status = 'ALMOST_FULL'
    else:
        new_status = 'OK'
    
    # Update database
    cursor.execute(
        'UPDATE bin_status SET fill_level = ?, status = ? WHERE bin_name = ?',
        (new_level, new_status, bin_name)
    )
    conn.commit()
    conn.close()
    
    return {'fill_level': new_level, 'status': new_status}

def save_detection(waste_type, confidence, filename, bin_status):
    """Save detection record to database"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    detection_time = datetime.now().isoformat()  # ISO format for JSON compatibility
    
    cursor.execute('''
        INSERT INTO waste_records 
        (waste_type, confidence, detection_time, filename, image_path, bin_status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (waste_type, confidence, detection_time, filename, image_path, bin_status))
    
    conn.commit()
    conn.close()
    
    return detection_time

def get_all_detections():
    """Get all detection records"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT waste_type, confidence, detection_time, bin_status
        FROM waste_records
        ORDER BY detection_time DESC
        LIMIT 20
    ''')
    
    records = []
    for row in cursor.fetchall():
        records.append({
            'waste_type': row[0],
            'confidence': row[1],
            'detection_time': row[2],
            'status': row[3]
        })
    
    conn.close()
    return records

def get_statistics():
    """Get waste statistics"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total detections
    cursor.execute('SELECT COUNT(*) FROM waste_records')
    total = cursor.fetchone()[0]
    
    # Count by type
    stats = {
        'total_detections': total,
        'metal_count': 0,
        'organic_count': 0,
        'plastic_count': 0,
        'distribution': {
            'metal': 0,
            'organic': 0,
            'plastic': 0
        }
    }
    
    for waste_type in WASTE_TYPES:
        cursor.execute('SELECT COUNT(*) FROM waste_records WHERE waste_type = ?', (waste_type,))
        count = cursor.fetchone()[0]
        key = waste_type.lower()
        stats[f'{key}_count'] = count
        stats['distribution'][key] = count
    
    conn.close()
    return stats

def get_all_bins():
    """Get all bins status"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT bin_name, fill_level, status FROM bin_status ORDER BY bin_name')
    
    bins = []
    for row in cursor.fetchall():
        bins.append({
            'bin_name': row[0],
            'fill_level': row[1],
            'status': row[2]
        })
    
    conn.close()
    return bins

def reset_all_data():
    """Reset all bins and detection history"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Delete all records
    cursor.execute('DELETE FROM waste_records')
    cursor.execute('UPDATE bin_status SET fill_level = 0, status = "OK"')
    
    conn.commit()
    conn.close()

# ============= ROUTES =============

@app.route('/', methods=['GET'])
def index():
    """Upload page"""
    return render_template('index.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Dashboard page"""
    return render_template('dashboard.html')

@app.route('/detect-waste', methods=['POST'])
def detect_waste():
    """AI detection endpoint"""
    try:
        if not ai_model:
            return jsonify({'error': 'Model not loaded'}), 500
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Load and preprocess image
        image = Image.open(filepath).convert('RGB')
        image = image.resize((224, 224))
        image_array = np.array(image) / 255.0
        image_array = np.expand_dims(image_array, axis=0)
        
        # Predict
        predictions = ai_model.predict(image_array, verbose=0)
        confidence = float(np.max(predictions[0]))  # Convert to Python float
        class_idx = int(np.argmax(predictions[0]))
        waste_type = CLASS_MAPPING[class_idx]
        
        # Update bin
        bin_data = update_bin_level(waste_type)
        
        # Save to database
        detection_time = save_detection(
            waste_type, 
            confidence, 
            filename, 
            bin_data['status']
        )
        
        # Return response
        response = {
            'waste_type': waste_type,
            'confidence': confidence,  # 0-1 range
            'bin_name': f"{waste_type} Bin",
            'bin_fill_level': bin_data['fill_level'],
            'bin_status': bin_data['status'],
            'detection_time': detection_time,
            'filename': filename
        }
        
        print(f"✅ Detection: {waste_type} ({confidence:.2%}), Bin: {bin_data['fill_level']}%")
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ Error in detect_waste: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/get-bins', methods=['GET'])
def get_bins():
    """Get all bin status"""
    try:
        bins = get_all_bins()
        return jsonify({'bins': bins}), 200
    except Exception as e:
        print(f"❌ Error in get_bins: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-history', methods=['GET'])
def get_history():
    """Get detection history"""
    try:
        history = get_all_detections()
        return jsonify({'history': history}), 200
    except Exception as e:
        print(f"❌ Error in get_history: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    try:
        stats = get_statistics()
        return jsonify(stats), 200
    except Exception as e:
        print(f"❌ Error in get_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reset-data', methods=['POST'])
def reset_data():
    """Reset all data"""
    try:
        reset_all_data()
        return jsonify({'message': 'All data reset successfully!'}), 200
    except Exception as e:
        print(f"❌ Error in reset_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============= INITIALIZATION =============

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Smart Waste Management System Starting...")
    print("=" * 60)
    
    init_db()
    
    print(f"📁 Project Root: {get_resource_path('.')}")
    print(f"📁 Upload Folder: {app.config['UPLOAD_FOLDER']}")
    print(f"🗄️  Database: {get_db_path()}")
    print(f"🤖 Model: {'✅ LOADED' if ai_model else '❌ NOT LOADED'}")
    print("=" * 60)
    print("🌐 Starting server...")
    print("📍 URL: http://127.0.0.1:5000")
    print("=" * 60)
    
    app.run(
        debug=False,
        host='127.0.0.1',
        port=5000,
        use_reloader=False,
        threaded=True
    )