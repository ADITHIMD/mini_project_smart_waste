import os
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

print("\n" + "="*60)
print("VALIDATING MODEL ACCURACY")
print("="*60 + "\n")

# Load model
try:
    model = load_model('model/waste_model.h5')
    print("✅ Model loaded successfully!\n")
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
    print(f"  {status} {category.upper()}: {correct}/{len(files)} correct ({accuracy_pct:.1f}%)\n")

print("="*60)
print("OVERALL METRICS")
print("="*60 + "\n")

if y_true and y_pred:
    overall_accuracy = accuracy_score(y_true, y_pred) * 100
    print(f"Overall Accuracy: {overall_accuracy:.2f}%\n")
    
    cm = confusion_matrix(y_true, y_pred)
    print("Confusion Matrix:")
    print(f"         Metal  Organic  Plastic")
    for i, cat in enumerate(['Metal', 'Organic', 'Plastic']):
        print(f"{cat:8}  {cm[i][0]:3d}    {cm[i][1]:3d}      {cm[i][2]:3d}")
    
    print("\n" + "="*60)
    print("CLASSIFICATION REPORT")
    print("="*60 + "\n")
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
    print("="*60 + "\n")
else:
    print("❌ No test data available")
