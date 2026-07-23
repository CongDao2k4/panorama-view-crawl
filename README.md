# Google Maps & Street View Panorama Crawler (Automated CSV Version)

Công cụ này giúp bạn tự động hóa việc cào ảnh Panorama (360 độ) từ danh sách địa điểm trong tệp CSV bằng Python và Selenium.

---

## 📋 Mô Tả Hệ Thống

Hệ thống hoạt động tự động theo quy trình khép kín như sau:

1.  **Đọc tệp đầu vào:** Hệ thống đọc tọa độ (latitude, longitude) và thông tin địa điểm từ tệp [tram_thu_phi_gg_crawl.csv](file:///d:/1%20-%20GreenSM%20Project/panorama-view-crawl/csv_raw/tram_thu_phi_gg_crawl.csv).
2.  **Mở Bản Đồ Zoom Cận Cảnh:** Crawler tự động tạo liên kết và mở Google Maps 2D trực tiếp tại tọa độ trạm với mức zoom lớn được cấu hình sẵn (ví dụ: `17z` hoặc `18z`):
    `https://www.google.com/maps/@{latitude},{longitude},{MAPS_ZOOM}`
    *(Bạn có thể tùy chỉnh hằng số `MAPS_ZOOM` ở đầu file `crawler.py` để điều chỉnh độ phóng to mặc định).*
3.  **Tương tác thủ công (Manual View):** Trình duyệt Chrome sẽ giữ nguyên vị trí để bạn tự do di chuyển chuột, xoay góc nhìn, click đi lại trên đường nhằm tìm được các góc nhìn 360 độ ưng ý nhất.
4.  **Tự động nhận diện Pano ID:** Trong khi bạn tương tác, crawler sẽ lắng nghe log mạng của Chrome. Mỗi khi phát hiện ra một mã Panorama ID (`panoid`) mới, hệ thống sẽ ghi nhận.
5.  **Tự động chuyển tiếp (Auto-Switch):** Khi hệ thống ghi nhận đủ **5 mã Pano ID khác nhau** tại địa điểm đó, chương trình sẽ hiển thị đếm ngược 5 giây trên console và tự động chuyển Chrome sang địa điểm tiếp theo trong CSV.
    *   *Mẹo:* Bạn có thể nhấn phím **ENTER** hoặc **SPACE** tại cửa sổ terminal bất kỳ lúc nào để chủ động bỏ qua và chuyển sang địa điểm tiếp theo ngay lập tức.
6.  **Tải ảnh dạng Lưới API (Chỉ mức Zoom 3 và 4):**
    Ngay khi chuyển địa điểm, crawler sẽ tự động tính toán lưới tọa độ `x, y` và tải trọn vẹn toàn bộ các ô ảnh nhỏ của 5 Pano ID đã thu thập được ở **chỉ mức Zoom 3** (Lưới 8x4 ô ảnh) và **Zoom 4** (Lưới 16x8 ô ảnh) để ghép lại thành ảnh panorama siêu nét.

---

## 🚀 Hướng dẫn Chạy Code

### Bước 1: Cài đặt thư viện cần thiết
Mở terminal/cmd tại thư mục dự án và chạy lệnh sau:
```powershell
pip install -r requirements.txt
```

### Bước 2: Đảm bảo tệp CSV đầu vào hợp lệ
Kiểm tra xem tệp dữ liệu trạm thu phí đã nằm đúng vị trí chưa:
[tram_thu_phi_gg_crawl.csv](file:///d:/1%20-%20GreenSM%20Project/panorama-view-crawl/csv_raw/tram_thu_phi_gg_crawl.csv)

### Bước 3: Khởi động chương trình
Chạy file python chính:
```powershell
python crawler.py
```

### Bước 4: Tương tác trên Chrome
*   Trình duyệt sẽ tự động load vào điểm đầu tiên trong CSV.
*   Bạn dùng chuột kéo xoay góc nhìn, click đi lại trên đường để tìm vị trí đẹp.
*   Khi terminal báo đã nhận đủ 5 Pano ID, hệ thống sẽ tự đếm ngược và chuyển trang. Bạn có thể gõ **ENTER** ở terminal để chuyển nhanh.
*   Tiến độ cào được tự động lưu trong `crawled_progress.json`. Nếu chương trình bị tắt giữa chừng, lần chạy sau sẽ tự động tiếp tục từ hàng chưa hoàn thành trong CSV.

---

## 📁 Cấu trúc thư mục dữ liệu tải về

Dữ liệu ảnh và luồng được tải về thư mục `downloads/`:
*   `downloads/<panoid>/thumbnail.jpg`: Ảnh xem trước (thumbnail) của panorama.
*   `downloads/<panoid>/zoom_3/tile_<x>_<y>.jpg`: Các mảnh ảnh nhỏ ghép lại ở mức **Zoom 3** (Lưới 8x4 ô ảnh).
*   `downloads/<panoid>/zoom_4/tile_<x>_<y>.jpg`: Các mảnh ảnh nhỏ ghép lại ở mức **Zoom 4** (Lưới 16x8 ô ảnh).
*   `downloads/metadata/pb_<nội_dung_pb>.bin`: Các file dữ liệu luồng protobuf chứa tọa độ liên kết điểm.
