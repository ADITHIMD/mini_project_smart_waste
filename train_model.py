import os
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import GlobalAveragePooling2D, Dense, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import numpy as np
import matplotlib.pyplot as plt

print("\n" + "="*70)
print("TRAINING WASTE CLASSIFICATION AI MODEL")
print("="*70 + "\n")

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
print(f"   Classes: {WASTE_CLASSES}\n")

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

print("\n🔄 Loading training data...")
train_generator = train_datagen.flow_from_directory(
    DATASET_PATH,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    classes=WASTE_CLASSES
)

# Build model
print("\n🧠 Building model...")
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
print(f"Total parameters: {model.count_params():,}\n")

# Train
print("🚀 Training model (this may take 10-15 minutes)...\n")
history = model.fit(
    train_generator,
    epochs=EPOCHS,
    verbose=1
)

# Save model
os.makedirs('model', exist_ok=True)
model.save(MODEL_SAVE_PATH)
print(f"\n✅ Model saved to {MODEL_SAVE_PATH}")

# Save metrics
print("\n📈 Saving training metrics...")
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

print("\n" + "="*70)
print("✅ TRAINING COMPLETE!")
print("="*70 + "\n")
