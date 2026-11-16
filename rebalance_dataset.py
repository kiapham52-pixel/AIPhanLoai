from pathlib import Path
import random
import shutil

# =========================
# CẤU HÌNH
# =========================

DATASET = Path("dataset")

OLD_TRAIN_IMAGES = DATASET / "images" / "train"
OLD_TRAIN_LABELS = DATASET / "labels" / "train"

OLD_VAL_IMAGES = DATASET / "images" / "val"
OLD_VAL_LABELS = DATASET / "labels" / "val"

NEW_DATASET = Path("dataset_balanced")

NEW_TRAIN_IMAGES = NEW_DATASET / "images" / "train"
NEW_TRAIN_LABELS = NEW_DATASET / "labels" / "train"

NEW_VAL_IMAGES = NEW_DATASET / "images" / "val"
NEW_VAL_LABELS = NEW_DATASET / "labels" / "val"

CLASS_NAMES = {
    0: "BIODEGRADABLE",
    1: "CARDBOARD",
    2: "GLASS",
    3: "METAL",
    4: "PAPER",
    5: "PLASTIC"
}

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

# Giữ khoảng 20% ảnh validation
VAL_RATIO = 0.20

random.seed(42)


# =========================
# TẠO FOLDER
# =========================

for folder in [
    NEW_TRAIN_IMAGES,
    NEW_TRAIN_LABELS,
    NEW_VAL_IMAGES,
    NEW_VAL_LABELS
]:
    folder.mkdir(parents=True, exist_ok=True)


# =========================
# LẤY TOÀN BỘ ẢNH
# =========================

all_images = []

for image_folder, label_folder in [
    (OLD_TRAIN_IMAGES, OLD_TRAIN_LABELS),
    (OLD_VAL_IMAGES, OLD_VAL_LABELS)
]:

    for image in image_folder.iterdir():

        if image.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        label = label_folder / f"{image.stem}.txt"

        if label.exists():
            all_images.append((image, label))


print("=" * 60)
print("TẠO DATASET TRAIN / VAL MỚI")
print("=" * 60)

print(f"Tổng số ảnh: {len(all_images)}")


# =========================
# TRỘN NGẪU NHIÊN
# =========================

random.shuffle(all_images)


# =========================
# CHIA TRAIN / VAL
# =========================

val_count = int(len(all_images) * VAL_RATIO)

val_data = all_images[:val_count]
train_data = all_images[val_count:]


print(f"Train mới: {len(train_data)}")
print(f"Val mới  : {len(val_data)}")


# =========================
# COPY FILE
# =========================

def copy_data(data, image_folder, label_folder):

    for image, label in data:

        shutil.copy2(
            image,
            image_folder / image.name
        )

        shutil.copy2(
            label,
            label_folder / label.name
        )


print("\nĐang copy TRAIN...")
copy_data(
    train_data,
    NEW_TRAIN_IMAGES,
    NEW_TRAIN_LABELS
)

print("Đang copy VAL...")
copy_data(
    val_data,
    NEW_VAL_IMAGES,
    NEW_VAL_LABELS
)


# =========================
# HOÀN TẤT
# =========================

print("\n" + "=" * 60)
print("🔥 HOÀN TẤT!")
print("=" * 60)

print("Dataset mới:")
print(NEW_DATASET)

print("\nCấu trúc:")
print("dataset_balanced/")
print("├── images/")
print("│   ├── train/")
print("│   └── val/")
print("└── labels/")
print("    ├── train/")
print("    └── val/")