# Emotion Pilot — Điều khiển TurtleBot bằng biểu cảm

Cần Ubuntu 22.04, ROS 2 Humble, Gazebo Fortress và webcam.
Cần Internet khi cài đặt và tải mô hình lần đầu.

## Cài đặt lần đầu

```bash
sudo apt install python3-venv python3-pyqt5 python3-colcon-common-extensions \
  ros-humble-turtlebot4-simulator ros-humble-turtlebot4-navigation \
  ros-humble-turtlebot4-viz ros-humble-ros-gz-bridge ros-humble-ros-ign-gazebo

cd ~/ros2_ws/src/facial_expression_control
bash install.sh

cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select facial_expression_control --symlink-install
```

## Chạy dự án

**Terminal 1 — mở Gazebo với robot trên sân trống:**

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=24
ros2 launch facial_expression_control empty_sim.launch.py
```

**Terminal 2 — mở nhận diện và điều khiển:**

```bash
cd ~/ros2_ws/src/facial_expression_control
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=24
bash run.sh
```

## Thao tác

- Chờ mô hình báo **Sẵn sàng**, nhấn **BẬT ĐIỀU KHIỂN** và giữ biểu cảm khoảng 1–2 giây.
- Robot thực hiện động tác sau khi xác nhận. Giữ mặt **bình thường (Neutral)** để dừng hoặc nhận lệnh tiếp theo.
- Nhấn **DỪNG ROBOT / Space** để kết thúc phiên điều khiển; nhấn **BẬT ĐIỀU KHIỂN** để tiếp tục.
- Khi thoát: dừng robot, đóng ứng dụng và nhấn **Ctrl+C** ở terminal Gazebo.

## Chỉ xem nhận diện

```bash
cd ~/ros2_ws/src/facial_expression_control
bash run.sh --preview
```

Chế độ `--preview` không điều khiển robot. Thêm `--camera 1` nếu cần đổi webcam.
Nếu gặp lỗi thư viện, chạy `bash run.sh --check` để xem lỗi.
