from ultralytics import YOLO

# Tải model đã train
model = YOLO("models/phan_loai_rac.pt")

# Mở camera
model.predict(
    source=0,
    show=True,
    conf=0.3
)