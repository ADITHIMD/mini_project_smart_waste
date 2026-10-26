import os
import sys

# Fix encoding for Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("\n" + "="*70)
print("SMART WASTE MANAGEMENT SYSTEM - COMPLETE SETUP")
print("="*70 + "\n")

files_to_create = {}

# ============== 1. app.py (Flask Backend) ==============
files_to_create['app.py'] = '''import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image
import numpy as np

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure folders exist
os.makedirs('uploads', exist_ok=True)
os.makedirs('model', exist_ok=True)

# Load AI Model
print("\\n" + "="*60)
print("LOADING AI MODEL...")
print("="*60)

try:
    ai_model = load_model('model/waste_model.h5')
    print("✅ AI Model Loaded Successfully!")
except Exception as e:
    print(f"❌ Model Error: {e}")
    print("⚠️  Run python train_model.py first!")
    ai_model = None

print("="*60 + "\\n")

# Class mapping
CLASS_MAPPING = {0: 'Metal', 1: 'Organic', 2: 'Plastic'}
WASTE_TYPES = ['Metal', 'Organic', 'Plastic']

# Initialize Database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS waste_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waste_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filename TEXT,
            image_path TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS bin_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin_name TEXT UNIQUE NOT NULL,
            fill_level INTEGER DEFAULT 0,
            status TEXT DEFAULT 'OK'
        )
    """)
    
    # Initialize bins if not exist
    for waste_type in WASTE_TYPES:
        try:
            c.execute("INSERT INTO bin_status (bin_name, fill_level, status) VALUES (?, ?, ?)",
                     (waste_type, 0, 'OK'))
        except:
            pass
    
    conn.commit()
    conn.close()

init_db()

# AI Prediction Function
def predict_waste(image_path):
    """Predict waste type from image"""
    try:
        if not os.path.exists(image_path):
            return None, None, "Image not found"
        
        img = Image.open(image_path).convert('RGB')
        img = img.resize((224, 224))
        img_array = np.array(img, dtype=np.float32) / 255.0
        img_array = np.expand_dims(img_array, axis=0)
        
        prediction = ai_model.predict(img_array, verbose=0)
        class_idx = np.argmax(prediction[0])
        confidence = float(prediction[0][class_idx]) * 100
        waste_type = CLASS_MAPPING[class_idx]
        
        return waste_type, round(confidence, 2), None
    
    except Exception as e:
        return None, None, str(e)

# Update Bin Level
def update_bin(waste_type, confidence):
    """Increment bin level by 5%"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get current level
    c.execute("SELECT fill_level FROM bin_status WHERE bin_name = ?", (waste_type,))
    row = c.fetchone()
    current_level = row[0] if row else 0
    
    # Increment by 5%, cap at 100%
    new_level = min(current_level + 5, 100)
    
    # Determine status
    if new_level == 100:
        status = 'FULL'
    elif new_level >= 80:
        status = 'ALMOST_FULL'
    else:
        status = 'OK'
    
    # Update bin
    c.execute("""
        UPDATE bin_status 
        SET fill_level = ?, status = ? 
        WHERE bin_name = ?
    """, (new_level, status, waste_type))
    
    conn.commit()
    conn.close()
    
    return new_level, status

# Flask Routes
@app.route('/')
def index():
    """Home page with upload"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    return render_template('dashboard.html')

@app.route('/detect-waste', methods=['POST'])
def detect_waste():
    """API: Detect waste type"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.content_type.startswith('image/'):
        return jsonify({'error': 'Only image files allowed'}), 400
    
    if ai_model is None:
        return jsonify({'error': 'Model not loaded'}), 500
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Predict
        waste_type, confidence, error = predict_waste(filepath)
        
        if error:
            return jsonify({'error': error}), 400
        
        # Update bin
        bin_level, status = update_bin(waste_type, confidence)
        
        # Store in database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO waste_records (waste_type, confidence, filename, image_path)
            VALUES (?, ?, ?, ?)
        """, (waste_type, confidence, filename, filepath))
        conn.commit()
        conn.close()
        
        return jsonify({
            'waste_type': waste_type,
            'confidence': confidence,
            'bin_level': bin_level,
            'bin_status': status,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-bins')
def get_bins():
    """API: Get bin status"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT bin_name, fill_level, status FROM bin_status ORDER BY bin_name")
    rows = c.fetchall()
    conn.close()
    
    bins = {
        row[0]: {'level': row[1], 'status': row[2]}
        for row in rows
    }
    
    return jsonify(bins)

@app.route('/get-history')
def get_history():
    """API: Get detection history"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        SELECT waste_type, confidence, detection_time, filename
        FROM waste_records
        ORDER BY detection_time DESC
        LIMIT 20
    """)
    rows = c.fetchall()
    conn.close()
    
    history = [
        {
            'waste_type': row[0],
            'confidence': row[1],
            'time': row[2],
            'filename': row[3]
        }
        for row in rows
    ]
    
    return jsonify(history)

@app.route('/get-stats')
def get_stats():
    """API: Get statistics"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Total detections per type
    c.execute("SELECT waste_type, COUNT(*) as count FROM waste_records GROUP BY waste_type")
    distribution = {row[0]: row[1] for row in c.fetchall()}
    
    # Total detections
    c.execute("SELECT COUNT(*) FROM waste_records")
    total = c.fetchone()[0]
    
    # Bin status
    c.execute("SELECT bin_name, fill_level FROM bin_status")
    bins = {row[0]: row[1] for row in c.fetchall()}
    
    conn.close()
    
    return jsonify({
        'total_detections': total,
        'distribution': distribution,
        'bin_status': bins
    })

@app.route('/reset-data', methods=['POST'])
def reset_data():
    """API: Reset all data"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("DELETE FROM waste_records")
    c.execute("UPDATE bin_status SET fill_level = 0, status = 'OK'")
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Data reset successfully'})

if __name__ == '__main__':
    print("\\n" + "="*60)
    print("✅ SMART WASTE MANAGEMENT SYSTEM STARTED")
    print("="*60)
    print("🌐 Open: http://127.0.0.1:5000")
    print("="*60 + "\\n")
    app.run(debug=False, port=5000)
'''

# ============== 2. train_model.py ==============
files_to_create['train_model.py'] = '''import os
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import numpy as np
import matplotlib.pyplot as plt

print("\\n" + "="*70)
print("TRAINING WASTE CLASSIFICATION AI MODEL")
print("="*70 + "\\n")

# Settings
DATASET_PATH = 'dataset'
MODEL_SAVE_PATH = 'model/waste_model.h5'
EPOCHS = 25
BATCH_SIZE = 16
IMG_SIZE = (224, 224)
WASTE_CLASSES = ['metal', 'organic', 'plastic']

print(f"📊 Configuration:")
print(f"   Epochs: {EPOCHS}")
print(f"   Batch Size: {BATCH_SIZE}")
print(f"   Image Size: {IMG_SIZE}")
print(f"   Classes: {WASTE_CLASSES}\\n")

# Verify dataset
print("📁 Checking dataset...")
for category in WASTE_CLASSES:
    path = os.path.join(DATASET_PATH, category)
    if os.path.exists(path):
        count = len([f for f in os.listdir(path) if f.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.bmp'))])
        print(f"   ✅ {category.upper()}: {count} images")
    else:
        print(f"   ❌ {category.upper()}: FOLDER NOT FOUND")
        exit()

# Data augmentation
train_datagen = ImageDataGenerator(
    rescale=1./255,
    rotation_range=20,
    width_shift_range=0.2,
    height_shift_range=0.2,
    shear_range=0.2,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest'
)

print("\\n🔄 Loading training data...")
train_generator = train_datagen.flow_from_directory(
    DATASET_PATH,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    classes=WASTE_CLASSES
)

# Build model
print("\\n🧠 Building model...")
base_model = MobileNetV2(input_shape=(*IMG_SIZE, 3), include_top=False, weights='imagenet')
base_model.trainable = False  # Freeze base weights

model = Sequential([
    base_model,
    GlobalAveragePooling2D(),
    Dense(256, activation='relu'),
    Dropout(0.5),
    Dense(128, activation='relu'),
    Dropout(0.3),
    Dense(3, activation='softmax')
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

print("✅ Model built!")
print(f"Total parameters: {model.count_params():,}\\n")

# Train
print("🚀 Training model (this may take 10-15 minutes)...\\n")
history = model.fit(
    train_generator,
    epochs=EPOCHS,
    verbose=1
)

# Save model
os.makedirs('model', exist_ok=True)
model.save(MODEL_SAVE_PATH)
print(f"\\n✅ Model saved to {MODEL_SAVE_PATH}")

# Save metrics
print("\\n📈 Saving training metrics...")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].plot(history.history['loss'])
axes[0].set_title('Training Loss')
axes[0].set_xlabel('Epoch')
axes[0].set_ylabel('Loss')
axes[0].grid(True)

axes[1].plot(history.history['accuracy'])
axes[1].set_title('Training Accuracy')
axes[1].set_xlabel('Epoch')
axes[1].set_ylabel('Accuracy')
axes[1].grid(True)

plt.tight_layout()
plt.savefig('model/training_metrics.png', dpi=100)
print("✅ Metrics saved to model/training_metrics.png")

print("\\n" + "="*70)
print("✅ TRAINING COMPLETE!")
print("="*70 + "\\n")
'''

# ============== 3. validate_accuracy.py ==============
files_to_create['validate_accuracy.py'] = '''import os
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

print("\\n" + "="*60)
print("VALIDATING MODEL ACCURACY")
print("="*60 + "\\n")

# Load model
try:
    model = load_model('model/waste_model.h5')
    print("✅ Model loaded successfully!\\n")
except Exception as e:
    print(f"❌ Model error: {e}")
    print("Run: python train_model.py")
    exit()

class_mapping = {0: 'Metal', 1: 'Organic', 2: 'Plastic'}

y_true = []
y_pred = []

for category_idx, category in enumerate(['metal', 'organic', 'plastic']):
    path = f'dataset/{category}'
    
    if not os.path.exists(path):
        print(f"❌ {category} folder not found")
        continue
    
    files = [f for f in os.listdir(path) if f.lower().endswith(('.jpg', '.png', '.jpeg', '.gif', '.bmp'))]
    
    if not files:
        print(f"❌ No images in {category}")
        continue
    
    print(f"Testing {category.upper()} ({len(files)} images)...")
    correct = 0
    
    for filename in files:
        filepath = os.path.join(path, filename)
        
        try:
            img = Image.open(filepath).convert('RGB')
            img = img.resize((224, 224))
            img_array = np.array(img, dtype=np.float32) / 255.0
            img_array = np.expand_dims(img_array, axis=0)
            
            prediction = model.predict(img_array, verbose=0)
            class_idx = np.argmax(prediction[0])
            
            y_true.append(category_idx)
            y_pred.append(class_idx)
            
            if class_idx == category_idx:
                correct += 1
        except:
            pass
    
    accuracy_pct = (correct / len(files)) * 100 if files else 0
    status = "✅" if accuracy_pct >= 85 else "⚠️" if accuracy_pct >= 70 else "❌"
    print(f"  {status} {category.upper()}: {correct}/{len(files)} correct ({accuracy_pct:.1f}%)\\n")

print("="*60)
print("OVERALL METRICS")
print("="*60 + "\\n")

if y_true and y_pred:
    overall_accuracy = accuracy_score(y_true, y_pred) * 100
    print(f"Overall Accuracy: {overall_accuracy:.2f}%\\n")
    
    cm = confusion_matrix(y_true, y_pred)
    print("Confusion Matrix:")
    print(f"         Metal  Organic  Plastic")
    for i, cat in enumerate(['Metal', 'Organic', 'Plastic']):
        print(f"{cat:8}  {cm[i][0]:3d}    {cm[i][1]:3d}      {cm[i][2]:3d}")
    
    print("\\n" + "="*60)
    print("CLASSIFICATION REPORT")
    print("="*60 + "\\n")
    print(classification_report(y_true, y_pred, target_names=['Metal', 'Organic', 'Plastic']))
    
    print("="*60)
    if overall_accuracy >= 92:
        print("✅ EXCELLENT: Production ready!")
    elif overall_accuracy >= 85:
        print("✅ GOOD: Ready for deployment")
    elif overall_accuracy >= 70:
        print("⚠️  ACCEPTABLE: Can improve")
    else:
        print("❌ POOR: Needs more training")
    print("="*60 + "\\n")
else:
    print("❌ No test data available")
'''

# ============== 4. index.html ==============
files_to_create['templates/index.html'] = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Waste Management</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <header>
            <h1>♻️ Smart Waste Management System</h1>
            <p>AI-Powered Waste Classification</p>
        </header>

        <nav>
            <a href="/" class="nav-btn active">Upload</a>
            <a href="/dashboard" class="nav-btn">Dashboard</a>
        </nav>

        <main>
            <section class="upload-section">
                <div class="upload-area" id="uploadArea">
                    <div class="upload-icon">📸</div>
                    <h2>Drag & Drop Image Here</h2>
                    <p>or click to select</p>
                    <input type="file" id="fileInput" accept="image/*" style="display:none;">
                </div>

                <div id="previewArea" style="display:none;">
                    <img id="previewImage" src="" alt="Preview">
                    <button id="detectBtn" class="btn-primary">🔍 DETECT WASTE</button>
                    <button id="resetBtn" class="btn-secondary">↺ Upload Another</button>
                </div>

                <div id="resultArea" style="display:none;">
                    <div class="result-card">
                        <h2 id="wasteType">Metal</h2>
                        <div class="confidence-box">
                            <div class="confidence-text">Confidence</div>
                            <div id="confidenceScore">95%</div>
                        </div>
                        <div class="bin-status">
                            <h3>Bin Status</h3>
                            <div class="bin-info">
                                <span id="binName">Metal Bin</span>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="binFill" style="width: 0%"></div>
                                </div>
                                <span id="binLevel">0%</span>
                            </div>
                            <div class="status-badge" id="statusBadge">OK</div>
                        </div>
                        <div id="timestamp" class="timestamp"></div>
                    </div>
                </div>

                <div id="errorArea" style="display:none;" class="error-box">
                    <p id="errorMsg"></p>
                </div>
            </section>
        </main>

        <footer>
            <p>Powered by TensorFlow & Flask | AI Classification Model</p>
        </footer>
    </div>

    <script src="{{ url_for('static', filename='script.js') }}"></script>
</body>
</html>
'''

# ============== 5. dashboard.html ==============
files_to_create['templates/dashboard.html'] = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Smart Waste Management</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <header>
            <h1>♻️ Smart Waste Management System</h1>
            <p>Real-Time Monitoring Dashboard</p>
        </header>

        <nav>
            <a href="/" class="nav-btn">Upload</a>
            <a href="/dashboard" class="nav-btn active">Dashboard</a>
        </nav>

        <main>
            <!-- Bin Status Section -->
            <section class="dashboard-section">
                <h2>📦 Bin Status</h2>
                <div class="bins-grid" id="binsGrid">
                    <!-- Generated by JavaScript -->
                </div>
            </section>

            <!-- Statistics Section -->
            <section class="dashboard-section">
                <h2>📊 Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value" id="totalDetections">0</div>
                        <div class="stat-label">Total Detections</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="metalCount">0</div>
                        <div class="stat-label">Metal Items</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="organicCount">0</div>
                        <div class="stat-label">Organic Items</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="plasticCount">0</div>
                        <div class="stat-label">Plastic Items</div>
                    </div>
                </div>
            </section>

            <!-- Distribution Chart -->
            <section class="dashboard-section">
                <h2>📈 Waste Distribution</h2>
                <canvas id="distributionChart" width="400" height="200"></canvas>
            </section>

            <!-- Recent Detections -->
            <section class="dashboard-section">
                <h2>📋 Recent Detections</h2>
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Confidence</th>
                            <th>Time</th>
                            <th>Image</th>
                        </tr>
                    </thead>
                    <tbody id="historyBody">
                        <!-- Generated by JavaScript -->
                    </tbody>
                </table>
            </section>

            <!-- Reset Button -->
            <section class="dashboard-section">
                <button id="resetDataBtn" class="btn-danger">🗑️ Reset All Data</button>
            </section>
        </main>

        <footer>
            <p>Powered by TensorFlow & Flask | Real-Time Monitoring</p>
        </footer>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <script src="{{ url_for('static', filename='script.js') }}"></script>
</body>
</html>
'''

# ============== 6. style.css ==============
files_to_create['static/style.css'] = '''* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    text-align: center;
    color: white;
    margin-bottom: 30px;
    padding: 30px 0;
}

header h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

header p {
    font-size: 1.1em;
    opacity: 0.9;
}

nav {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-bottom: 30px;
    flex-wrap: wrap;
}

.nav-btn {
    padding: 12px 30px;
    background: white;
    color: #667eea;
    text-decoration: none;
    border-radius: 25px;
    font-weight: bold;
    transition: all 0.3s ease;
    border: 2px solid white;
}

.nav-btn:hover {
    background: transparent;
    color: white;
}

.nav-btn.active {
    background: #ff6b6b;
    color: white;
    border-color: #ff6b6b;
}

main {
    background: white;
    border-radius: 15px;
    padding: 40px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
}

/* Upload Section */
.upload-section {
    text-align: center;
}

.upload-area {
    border: 3px dashed #667eea;
    border-radius: 10px;
    padding: 60px 20px;
    cursor: pointer;
    transition: all 0.3s ease;
    background: #f8f9ff;
}

.upload-area:hover {
    border-color: #764ba2;
    background: #f0f1ff;
}

.upload-area.drag-over {
    border-color: #ff6b6b;
    background: #ffe5e5;
}

.upload-icon {
    font-size: 3em;
    margin-bottom: 20px;
}

.upload-area h2 {
    color: #667eea;
    margin-bottom: 10px;
}

.upload-area p {
    color: #999;
}

/* Preview Area */
#previewArea {
    text-align: center;
    margin-top: 30px;
}

#previewImage {
    max-width: 100%;
    max-height: 300px;
    border-radius: 10px;
    margin-bottom: 20px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
}

/* Result Card */
.result-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 15px;
    margin-top: 30px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
}

.result-card h2 {
    font-size: 2em;
    margin-bottom: 20px;
}

.confidence-box {
    background: rgba(255,255,255,0.2);
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 20px;
}

.confidence-text {
    font-size: 0.9em;
    opacity: 0.8;
}

#confidenceScore {
    font-size: 2em;
    font-weight: bold;
    margin-top: 10px;
}

.bin-status {
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 10px;
    text-align: left;
}

.bin-status h3 {
    margin-bottom: 15px;
}

.bin-info {
    display: flex;
    align-items: center;
    gap: 15px;
}

.progress-bar {
    flex: 1;
    height: 25px;
    background: rgba(255,255,255,0.2);
    border-radius: 12px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #8BC34A);
    transition: width 0.5s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8em;
    font-weight: bold;
}

.status-badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: bold;
    margin-top: 15px;
    background: #4CAF50;
    color: white;
}

.status-badge.almost-full {
    background: #FFC107;
    color: #333;
}

.status-badge.full {
    background: #f44336;
}

.timestamp {
    font-size: 0.9em;
    opacity: 0.7;
    margin-top: 15px;
}

/* Buttons */
.btn-primary, .btn-secondary, .btn-danger {
    padding: 12px 30px;
    margin: 10px;
    border: none;
    border-radius: 25px;
    font-size: 1em;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-primary {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
    background: #ddd;
    color: #333;
}

.btn-secondary:hover {
    background: #ccc;
}

.btn-danger {
    background: #f44336;
    color: white;
}

.btn-danger:hover {
    background: #da190b;
}

/* Error Box */
.error-box {
    background: #ffebee;
    color: #c62828;
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid #f44336;
    margin-top: 20px;
}

/* Dashboard Sections */
.dashboard-section {
    margin-bottom: 40px;
}

.dashboard-section h2 {
    color: #667eea;
    margin-bottom: 20px;
    font-size: 1.5em;
    border-bottom: 2px solid #667eea;
    padding-bottom: 10px;
}

/* Bins Grid */
.bins-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
}

.bin-card {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
}

.bin-card h3 {
    margin-bottom: 15px;
    font-size: 1.3em;
}

.bin-card .progress-bar {
    height: 30px;
    margin-bottom: 15px;
    background: rgba(255,255,255,0.2);
}

.bin-card .status {
    font-weight: bold;
    padding: 8px 16px;
    border-radius: 20px;
    background: rgba(255,255,255,0.2);
    display: inline-block;
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 20px;
}

.stat-card {
    background: #f5f5f5;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    border-left: 4px solid #667eea;
}

.stat-value {
    font-size: 2em;
    font-weight: bold;
    color: #667eea;
    margin-bottom: 10px;
}

.stat-label {
    color: #999;
    font-size: 0.9em;
}

/* History Table */
.history-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}

.history-table th {
    background: #667eea;
    color: white;
    padding: 15px;
    text-align: left;
    font-weight: bold;
}

.history-table td {
    padding: 12px 15px;
    border-bottom: 1px solid #eee;
}

.history-table tr:hover {
    background: #f5f5f5;
}

/* Footer */
footer {
    text-align: center;
    color: white;
    margin-top: 40px;
    padding: 20px 0;
    opacity: 0.8;
}

/* Responsive */
@media (max-width: 768px) {
    header h1 {
        font-size: 1.8em;
    }
    
    main {
        padding: 20px;
    }
    
    .upload-area {
        padding: 40px 20px;
    }
    
    .bins-grid, .stats-grid {
        grid-template-columns: 1fr;
    }
    
    nav {
        flex-direction: column;
    }
    
    .nav-btn {
        width: 100%;
    }
}
'''

# ============== 7. script.js ==============
files_to_create['static/script.js'] = '''// ============= SOUND FUNCTIONS =============
function playBuzzerSound() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = 800;
    oscillator.type = 'square';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 2);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 2);
}

function playWarningBeep() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
    for (let i = 0; i < 3; i++) {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 1000;
        oscillator.type = 'sine';
        
        const startTime = audioContext.currentTime + (i * 0.4);
        gainNode.gain.setValueAtTime(0.2, startTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, startTime + 0.2);
        
        oscillator.start(startTime);
        oscillator.stop(startTime + 0.2);
    }
}

// ============= UPLOAD HANDLING =============
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const previewArea = document.getElementById('previewArea');
const previewImage = document.getElementById('previewImage');
const resultArea = document.getElementById('resultArea');
const errorArea = document.getElementById('errorArea');

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

// ============= FILE HANDLING =============
function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        showError('Please select an image file');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImage.src = e.target.result;
        uploadArea.style.display = 'none';
        previewArea.style.display = 'block';
        resultArea.style.display = 'none';
        errorArea.style.display = 'none';
        
        // Auto-detect after 500ms
        setTimeout(() => detectWaste(file), 500);
    };
    reader.readAsDataURL(file);
}

// ============= DETECTION =============
async function detectWaste(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/detect-waste', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showResult(data);
        } else {
            showError(data.error || 'Detection failed');
        }
    } catch (error) {
        showError('Error: ' + error.message);
    }
}

function showResult(data) {
    document.getElementById('wasteType').textContent = data.waste_type;
    document.getElementById('confidenceScore').textContent = data.confidence + '%';
    document.getElementById('binName').textContent = data.waste_type + ' Bin';
    document.getElementById('binFill').style.width = data.bin_level + '%';
    document.getElementById('binLevel').textContent = data.bin_level + '%';
    document.getElementById('timestamp').textContent = 'Detected: ' + data.timestamp;
    
    const badge = document.getElementById('statusBadge');
    badge.textContent = data.bin_status;
    
    // Update badge color
    badge.classList.remove('almost-full', 'full');
    if (data.bin_status === 'FULL') {
        badge.classList.add('full');
        playBuzzerSound();  // Buzzer at 100%
    } else if (data.bin_status === 'ALMOST_FULL') {
        badge.classList.add('almost-full');
        playWarningBeep();  // Warning beep at 80%
    }
    
    previewArea.style.display = 'block';
    resultArea.style.display = 'block';
    errorArea.style.display = 'none';
}

function showError(message) {
    document.getElementById('errorMsg').textContent = message;
    errorArea.style.display = 'block';
    resultArea.style.display = 'none';
}

// ============= RESET BUTTONS =============
document.getElementById('detectBtn').addEventListener('click', () => {
    const file = fileInput.files[0];
    if (file) {
        detectWaste(file);
    }
});

document.getElementById('resetBtn').addEventListener('click', () => {
    uploadArea.style.display = 'block';
    previewArea.style.display = 'none';
    resultArea.style.display = 'none';
    errorArea.style.display = 'none';
    fileInput.value = '';
});

// ============= DASHBOARD FUNCTIONS =============
async function refreshDashboard() {
    try {
        const binsRes = await fetch('/get-bins');
        const bins = await binsRes.json();
        
        const statsRes = await fetch('/get-stats');
        const stats = await statsRes.json();
        
        const historyRes = await fetch('/get-history');
        const history = await historyRes.json();
        
        // Update bins grid
        const binsGrid = document.getElementById('binsGrid');
        if (binsGrid) {
            binsGrid.innerHTML = '';
            Object.entries(bins).forEach(([name, data]) => {
                const card = document.createElement('div');
                card.className = 'bin-card';
                card.innerHTML = `
                    <h3>${name} Bin</h3>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${data.level}%; background: ${data.level === 100 ? '#f44336' : data.level >= 80 ? '#FFC107' : '#4CAF50'}"></div>
                    </div>
                    <div>${data.level}%</div>
                    <div class="status">${data.status}</div>
                `;
                binsGrid.appendChild(card);
            });
        }
        
        // Update statistics
        if (document.getElementById('totalDetections')) {
            document.getElementById('totalDetections').textContent = stats.total_detections;
            document.getElementById('metalCount').textContent = stats.distribution['Metal'] || 0;
            document.getElementById('organicCount').textContent = stats.distribution['Organic'] || 0;
            document.getElementById('plasticCount').textContent = stats.distribution['Plastic'] || 0;
        }
        
        // Update distribution chart
        const chartCanvas = document.getElementById('distributionChart');
        if (chartCanvas && stats.distribution) {
            drawChart(stats.distribution);
        }
        
        // Update history table
        const historyBody = document.getElementById('historyBody');
        if (historyBody) {
            historyBody.innerHTML = '';
            history.forEach(record => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${record.waste_type}</td>
                    <td>${record.confidence}%</td>
                    <td>${new Date(record.time).toLocaleString()}</td>
                    <td>${record.filename}</td>
                `;
                historyBody.appendChild(row);
            });
        }
    } catch (error) {
        console.error('Dashboard refresh error:', error);
    }
}

// ============= CHART =============
let chart = null;
function drawChart(distribution) {
    const ctx = document.getElementById('distributionChart').getContext('2d');
    const labels = Object.keys(distribution);
    const data = Object.values(distribution);
    
    if (chart) {
        chart.destroy();
    }
    
    chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#FF6B6B',
                    '#4ECDC4',
                    '#45B7D1'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// ============= RESET DATA =============
document.addEventListener('DOMContentLoaded', () => {
    const resetBtn = document.getElementById('resetDataBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', async () => {
            if (confirm('Reset all data? This cannot be undone!')) {
                try {
                    await fetch('/reset-data', { method: 'POST' });
                    alert('Data reset successfully!');
                    refreshDashboard();
                } catch (error) {
                    alert('Error resetting data');
                }
            }
        });
    }
    
    // Auto-refresh dashboard
    if (document.getElementById('binsGrid')) {
        refreshDashboard();
        setInterval(refreshDashboard, 3000);  // Refresh every 3 seconds
    }
});
'''

# Create all files
print("📝 Creating Python files...\n")

count = 0
for filepath, content in files_to_create.items():
    os.makedirs(os.path.dirname(filepath) if '/' in filepath else '.', exist_ok=True)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {filepath}")
        count += 1
    except Exception as e:
        print(f"❌ {filepath}: {e}")

print(f"\n✅ Created {count}/{len(files_to_create)} files\n")

print("="*70)
print("✅ SETUP COMPLETE!")
print("="*70)
print("\n📋 NEXT STEPS:\n")
print("1. Download images (40-50 per category):")
print("   📁 dataset/metal/   - Download metal waste images")
print("   📁 dataset/organic/ - Download organic waste images")
print("   📁 dataset/plastic/ - Download plastic waste images")
print("\n2. Train the model:")
print("   python train_model.py")
print("\n3. Validate accuracy:")
print("   python validate_accuracy.py")
print("\n4. Start the web app:")
print("   python app.py")
print("\n5. Open in browser:")
print("   http://127.0.0.1:5000")
print("\n" + "="*70 + "\n")
