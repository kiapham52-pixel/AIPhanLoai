from ultralytics import YOLO

# Load model YOLO11 Nano
model = YOLO("yolo11n.pt")

# Train nhẹ để kiểm tra model
results = model.train(
    data="data.yaml",

    # Train nhanh
    epochs=30,
    imgsz=320,
    batch=2,

    # Chạy CPU
    device="cpu",

    # Giảm tải hệ thống
    workers=0,

    # Lưu kết quả
    project="runs",
    name="phan_loai_rac",

    save=True,
    plots=True
)

print("\n🔥 TRAIN HOÀN TẤT!")
print("Model tốt nhất:")
print("runs/phan_loai_rac/weights/best.pt")