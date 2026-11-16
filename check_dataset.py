from pathlib import Path

# =========================
# CẤU HÌNH
# =========================

DATASET = Path("dataset_balanced")

TRAIN_IMAGES = DATASET / "images" / "train"
TRAIN_LABELS = DATASET / "labels" / "train"

VAL_IMAGES = DATASET / "images" / "val"
VAL_LABELS = DATASET / "labels" / "val"

CLASS_NAMES = {
    0: "BIODEGRADABLE",
    1: "CARDBOARD",
    2: "GLASS",
    3: "METAL",
    4: "PAPER",
    5: "PLASTIC"
}

image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]


# =========================
# KIỂM TRA FOLDER
# =========================

folders = [
    TRAIN_IMAGES,
    TRAIN_LABELS,
    VAL_IMAGES,
    VAL_LABELS
]

print("=" * 60)
print("       KIỂM TRA DATASET YOLO")
print("=" * 60)

for folder in folders:
    if folder.exists():
        print(f"[OK] {folder}")
    else:
        print(f"[ERROR] Thiếu: {folder}")


# =========================
# LẤY ẢNH
# =========================

def get_images(folder):
    if not folder.exists():
        return []

    return [
        file for file in folder.iterdir()
        if file.suffix.lower() in image_extensions
    ]


train_images = get_images(TRAIN_IMAGES)
val_images = get_images(VAL_IMAGES)

print("\n" + "=" * 60)
print("THỐNG KÊ")
print("=" * 60)

print(f"Train images : {len(train_images)}")
print(f"Val images   : {len(val_images)}")


# =========================
# KIỂM TRA LABEL + ĐẾM CLASS
# =========================

def check_labels(images, label_folder, split_name):

    print(f"\n--- {split_name.upper()} ---")

    missing_labels = []
    invalid_labels = []
    total_objects = 0

    class_counts = {
        class_id: 0
        for class_id in CLASS_NAMES
    }

    for image in images:

        label_file = label_folder / f"{image.stem}.txt"

        if not label_file.exists():
            missing_labels.append(image.name)
            continue

        try:
            with open(label_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line_number, line in enumerate(lines, start=1):

                line = line.strip()

                if not line:
                    continue

                parts = line.split()

                if len(parts) != 5:
                    invalid_labels.append(
                        f"{label_file.name} dòng {line_number}: "
                        f"phải có 5 giá trị"
                    )
                    continue

                try:
                    class_id = int(parts[0])

                    x = float(parts[1])
                    y = float(parts[2])
                    w = float(parts[3])
                    h = float(parts[4])

                except ValueError:
                    invalid_labels.append(
                        f"{label_file.name} dòng {line_number}: "
                        f"giá trị không hợp lệ"
                    )
                    continue

                # Kiểm tra class
                if class_id not in CLASS_NAMES:
                    invalid_labels.append(
                        f"{label_file.name}: "
                        f"class {class_id} không tồn tại"
                    )
                    continue

                # Kiểm tra tọa độ
                if not (
                    0 <= x <= 1 and
                    0 <= y <= 1 and
                    0 <= w <= 1 and
                    0 <= h <= 1
                ):
                    invalid_labels.append(
                        f"{label_file.name}: "
                        f"tọa độ không hợp lệ"
                    )
                    continue

                total_objects += 1
                class_counts[class_id] += 1

        except Exception as e:
            invalid_labels.append(
                f"{label_file.name}: {e}"
            )

    print(f"Objects       : {total_objects}")
    print(f"Missing label : {len(missing_labels)}")
    print(f"Invalid label : {len(invalid_labels)}")

    print("\nPhân bố class:")

    for class_id, class_name in CLASS_NAMES.items():
        print(
            f"  {class_id} - {class_name:<15}: "
            f"{class_counts[class_id]}"
        )

    if missing_labels:
        print("\nẢNH THIẾU LABEL:")
        for item in missing_labels[:10]:
            print(" -", item)

    if invalid_labels:
        print("\nLABEL LỖI:")
        for item in invalid_labels[:10]:
            print(" -", item)

    return len(missing_labels), len(invalid_labels)


# =========================
# CHẠY KIỂM TRA
# =========================

train_missing, train_invalid = check_labels(
    train_images,
    TRAIN_LABELS,
    "train"
)

val_missing, val_invalid = check_labels(
    val_images,
    VAL_LABELS,
    "val"
)


# =========================
# KẾT QUẢ
# =========================

print("\n" + "=" * 60)
print("KẾT QUẢ")
print("=" * 60)

if (
    len(train_images) > 0 and
    len(val_images) > 0 and
    train_missing == 0 and
    train_invalid == 0 and
    val_missing == 0 and
    val_invalid == 0
):
    print("🔥 DATASET SẠCH - CÓ THỂ TRAIN YOLO!")
else:
    print("⚠️ DATASET CHƯA SẴN SÀNG.")

print("=" * 60)