from ultralytics import YOLO

# Load model mới nhất
model = YOLO("models/phan_loai_rac.pt")

# Mở camera
model.predict(
    source=0,
    show=True,
    conf=0.4
)