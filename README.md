# AI Phân Loại Rác

Ứng dụng web nhận diện và phân loại rác bằng YOLO, cung cấp thông tin tái chế và gợi ý các dự án tái sử dụng. Giao diện và nội dung hướng dẫn bằng tiếng Việt.

## Mục lục

- [Tính năng](#tính-năng)
- [Công nghệ](#công-nghệ)
- [Yêu cầu](#yêu-cầu)
- [Cài đặt và chạy](#cài-đặt-và-chạy)
- [Cấu hình trợ lý chat](#cấu-hình-trợ-lý-chat-tùy-chọn)
- [Huấn luyện lại mô hình](#huấn-luyện-lại-mô-hình)
- [API](#api)
- [Chạy kiểm thử](#chạy-kiểm-thử)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Lưu ý](#lưu-ý)

## Tính năng

- Tải ảnh lên để nhận diện các vật thể thuộc sáu nhóm: `BIODEGRADABLE`, `CARDBOARD`, `GLASS`, `METAL`, `PAPER` và `PLASTIC`.
- Hiển thị nhãn, độ tin cậy, số lượng vật thể và ảnh kết quả có khung nhận diện.
- Dùng camera trực tiếp để nhận diện vật thể.
- Tra cứu cách phân loại, chuẩn bị và xử lý vật liệu; tìm kiếm ý tưởng tái sử dụng và dự án DIY.
- Lưu dự án yêu thích, xem lịch sử nhận diện và trò chuyện về tái chế.
- Dữ liệu dự án và kiến thức tái chế được cung cấp cục bộ; có thể bật trợ lý ngôn ngữ OpenAI hoặc Gemini bằng API key riêng.

## Công nghệ

- Python và Flask
- Ultralytics YOLO
- OpenCV và NumPy
- SQLite
- HTML, CSS và JavaScript

## Yêu cầu

- Python 3.14.7 (các phiên bản Python khác cần bộ phiên bản thư viện tương thích)
- `pip`
- Git để tải mã nguồn
- Camera nếu muốn dùng tính năng nhận diện trực tiếp

Mô hình ứng dụng đã được đưa vào repository tại `models/phan_loai_rac.pt`. Không cần tải bộ dữ liệu để chạy ứng dụng. Nhận diện chạy trên CPU; tốc độ phụ thuộc vào máy tính.

Trước khi chạy, xác nhận tệp `models/phan_loai_rac.pt` tồn tại. Nếu model thiếu hoặc không tải được, ứng dụng ghi lỗi vào log nhưng vẫn phục vụ phần kiến thức/dự án; `/api/health` báo model `unavailable` và các yêu cầu nhận diện trả HTTP 503.

## Cài đặt và chạy

### Windows (PowerShell)

```powershell
git clone https://github.com/kiapham52-pixel/AIPhanLoai.git
cd AIPhanLoai

py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python app.py
```

Nếu PowerShell không cho phép kích hoạt môi trường ảo, có thể gọi Python trực tiếp:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

### macOS / Linux

```bash
git clone https://github.com/kiapham52-pixel/AIPhanLoai.git
cd AIPhanLoai

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
cp .env.example .env
python -m pip install -r requirements.txt
python app.py
```

Mở [http://localhost:5000](http://localhost:5000) trong trình duyệt. Khi được hỏi, cho phép trang web truy cập camera. Camera thường cần `localhost` hoặc kết nối HTTPS.

Tệp `.env.example` đặt `APP_ENV=development` để cookie hoạt động khi chạy HTTP trên localhost. Khi triển khai HTTPS, đổi thành `APP_ENV=production`; cấu hình này luôn bật thuộc tính `Secure` và từ chối cấu hình production không an toàn. `SESSION_COOKIE_HTTPONLY` và `SameSite=Lax` luôn được bật.

Ứng dụng tự tạo cơ sở dữ liệu `waste_ai.db`, thư mục tải ảnh `uploads/`, thư mục kết quả `static/results/` và khóa phiên Flask khi khởi động lần đầu. Đây là dữ liệu cục bộ; không cần tạo các tệp này trước.

## Cấu hình trợ lý chat (tùy chọn)

Không cấu hình API key vẫn có thể sử dụng phần tra cứu kiến thức tái chế có sẵn. Để bật câu trả lời từ mô hình ngôn ngữ:

1. Sao chép `.env.example` thành `.env` ở thư mục gốc.
2. Chọn nhà cung cấp và điền API key tương ứng.
3. Khởi động lại ứng dụng.

Ví dụ dùng OpenAI:

```dotenv
CHAT_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

Hoặc dùng Gemini:

```dotenv
CHAT_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

Có thể đặt `CHAT_PROVIDER=auto` để ứng dụng tự chọn OpenAI nếu có key, nếu không thì dùng Gemini. Tên model có thể đổi theo model mà tài khoản/API của bạn hỗ trợ.

`FLASK_SECRET_KEY` là tùy chọn. Nếu không đặt, ứng dụng tự tạo khóa cục bộ trong `instance/flask_secret_key`. Không đưa `.env`, API key hoặc khóa bí mật lên Git. `.env` và `instance/` đã được loại khỏi Git bằng `.gitignore`.

## Huấn luyện lại mô hình

Bộ dữ liệu huấn luyện không được bao gồm trong repository. Muốn chạy `train.py`, hãy chuẩn bị dữ liệu YOLO theo cấu trúc sau:

```text
dataset_balanced/
├── images/
│   ├── train/
│   └── val/
└── labels/
    ├── train/
    └── val/
```

`data.yaml` khai báo sáu lớp và dùng đường dẫn tương đối `dataset_balanced`. Nhãn cần theo định dạng YOLO, trong đó ID lớp từ `0` đến `5` tương ứng với thứ tự các lớp ghi trong tệp này.

Cài đặt các gói chạy ứng dụng ở trên, sau đó chạy:

```bash
python check_dataset.py
python train.py
```

`train.py` dùng trọng số khởi tạo `yolo11n.pt`, huấn luyện 30 epoch trên CPU và lưu kết quả trong `runs/`. Ultralytics có thể tải trọng số khởi tạo nếu chúng chưa có trên máy. Sau khi huấn luyện thành công, thay `models/phan_loai_rac.pt` bằng tệp `best.pt` mới trong thư mục kết quả huấn luyện để ứng dụng sử dụng mô hình vừa huấn luyện. Nếu dùng PowerShell:

```powershell
Copy-Item .\runs\phan_loai_rac\weights\best.pt .\models\phan_loai_rac.pt
```

Nếu Ultralytics tạo thư mục chạy có hậu tố khác, hãy thay đường dẫn nguồn bằng vị trí `best.pt` thực tế. Để cân bằng dữ liệu, có thể xem `rebalance_dataset.py`; hãy kiểm tra cấu hình thư mục và sao lưu dữ liệu trước khi chạy vì script tạo dữ liệu mới.

## API

Các endpoint chính:

| Phương thức | Đường dẫn | Mô tả |
| --- | --- | --- |
| `GET` | `/api/health` | Trạng thái ứng dụng, cơ sở dữ liệu, model và chat |
| `POST` | `/predict` | Nhận ảnh tải lên và hiển thị trang kết quả |
| `POST` | `/camera/predict` | Nhận ảnh từ camera và trả về kết quả JSON |
| `GET` | `/api/recycling` | Liệt kê vật liệu được hỗ trợ |
| `GET` | `/api/recycling/<material>` | Chi tiết hướng dẫn tái chế vật liệu |
| `GET` | `/api/projects` | Liệt kê dự án; hỗ trợ lọc theo `material`, `difficulty`, `max_minutes`, `category` |
| `GET` | `/api/projects/<project_id>` | Chi tiết một dự án |
| `GET`, `POST` | `/api/favorites` | Đọc hoặc lưu/bỏ lưu dự án yêu thích theo phiên trình duyệt |
| `GET` | `/api/history` | Lịch sử nhận diện của phiên trình duyệt |
| `GET` | `/api/search?q=<từ_khóa>` | Tìm kiếm kiến thức tái chế |
| `POST` | `/api/chat` | Gửi câu hỏi cho trợ lý chat |

Ví dụ kiểm tra trạng thái:

```bash
curl http://localhost:5000/api/health
```

`/camera/predict` nhận multipart form-data với trường `image`. `/api/chat` nhận JSON có trường `message`, ví dụ:

```json
{
  "message": "Làm sạch chai nhựa trước khi tái chế như thế nào?"
}
```

Chat giới hạn 20 yêu cầu mỗi phút cho mỗi phiên trình duyệt. Ảnh tải lên tối đa 16 MB; ngưỡng tin cậy và kích thước ảnh có thể gửi dưới dạng `confidence` (0–1) và `image_size` (được giới hạn trong khoảng 320–640).

## Chạy kiểm thử

Cài các dependency kiểm thử trong môi trường ảo rồi chạy:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

`pytest.ini` giới hạn việc tìm test trong `tests/`; các script demo `test_camera.py` và `test_yolo.py` ở thư mục gốc mở camera và không phải test tự động.

## Cấu trúc dự án

```text
app.py                          Ứng dụng Flask và các route/API
services/                       Nhận diện, chat, kiến thức và gợi ý dự án
models/phan_loai_rac.pt         Model YOLO được ứng dụng sử dụng
requirements.txt                Dependency chạy ứng dụng
requirements-dev.txt            Dependency kiểm thử
pytest.ini                      Cấu hình tìm test tự động
data/recycling_knowledge.json   Dữ liệu kiến thức tái chế
templates/                      Giao diện HTML
static/                         CSS, JavaScript và tài nguyên giao diện
tests/                          Kiểm thử tự động
data.yaml                       Cấu hình lớp và đường dẫn dataset YOLO
train.py                        Huấn luyện model
check_dataset.py                Kiểm tra cấu trúc và nhãn dataset
rebalance_dataset.py             Tạo dataset cân bằng
```

## Lưu ý

- Ảnh tải lên, lịch sử, yêu thích và khóa phiên được lưu cục bộ; cơ sở dữ liệu mặc định là `waste_ai.db`.
- Dataset huấn luyện, môi trường Python, cơ sở dữ liệu, ảnh tải lên, kết quả huấn luyện và trọng số gốc bị loại khỏi Git. Chỉ model ứng dụng `models/phan_loai_rac.pt` được theo dõi phiên bản.
- Nhận diện chỉ hỗ trợ sáu lớp đã huấn luyện. Kết quả có độ tin cậy thấp hoặc vật thể ngoài các lớp này có thể được trả về là chưa xác định.
- Nếu triển khai ra Internet, hãy dùng máy chủ WSGI phù hợp, HTTPS, quản lý secret an toàn và cân nhắc chính sách lưu trữ ảnh/dữ liệu. `python app.py` dành cho chạy cục bộ, không phải cấu hình triển khai production.
