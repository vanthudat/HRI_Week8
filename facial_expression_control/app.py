"""Vietnamese desktop dashboard for facial expression control."""
import argparse
import os
import signal
import sys
import threading
import time

# OpenCV pip wheels can otherwise point Qt to their incompatible plugins.
import cv2
for key in ('QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_QPA_FONTDIR'):
    if 'cv2' in os.environ.get(key, ''):
        os.environ.pop(key, None)

from PyQt5 import QtCore, QtGui, QtWidgets as W
from .control import Controller, EMOTIONS, Settings, MAX_LINEAR_SPEED
from .vision import Vision

STYLE = '''
QWidget { background: #0b1120; color: #e2e8f0; font-family: "DejaVu Sans"; font-size: 13px; }
QFrame#card { background: #131e32; border: 1px solid #26354e; border-radius: 14px; }
QLabel { background: transparent; border: none; }
QLabel#muted { color: #94a3b8; }
QLabel#title { font-size: 26px; font-weight: 700; }
QLabel#emotion { font-size: 29px; font-weight: 700; color: #5eead4; }
QLabel#video { background: #070d18; border-radius: 12px; color: #64748b; font-size: 16px; }
QPushButton { background: #20324c; border: 1px solid #344862; border-radius: 9px; padding: 13px; font-weight: 700; }
QPushButton:hover { background: #2b4260; }
QPushButton#start { background: #0f766e; border-color: #14b8a6; }
QPushButton#stop { background: #9f2341; border-color: #fb7185; font-size: 14px; }
QPushButton:disabled { color: #64748b; background: #182236; border-color: #26354e; }
QDoubleSpinBox { background: #1b2b43; border: 1px solid #344862; border-radius: 5px; padding: 5px; }
QTextEdit { background: #0e1728; border: none; color: #94a3b8; font-size: 11px; }
'''


def label(text, name=None):
    widget = W.QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setTextFormat(QtCore.Qt.PlainText)
    widget.setSizePolicy(W.QSizePolicy.Preferred, W.QSizePolicy.Minimum)
    return widget


def card():
    frame = W.QFrame()
    frame.setObjectName('card')
    layout = W.QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


class Dashboard(W.QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args, self.lock = args, threading.RLock()
        self.controller = Controller(Settings())
        self.bridge = None
        self.last_sequence = -1
        self.last_status = ''
        self.last_model_error = ''
        self.last_frame_stamp = 0.0
        self.fps = 0.0
        self.setWindowTitle('Emotion Pilot | TurtleBot Control Studio')
        screen = W.QApplication.primaryScreen().availableGeometry()
        self.resize(min(1320, screen.width() - 40), min(860, screen.height() - 50))
        self.setMinimumSize(980, 600)
        self.setStyleSheet(STYLE)
        root = W.QWidget()
        self.setCentralWidget(root)
        outer = W.QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(18)
        header = W.QHBoxLayout()
        heading = W.QVBoxLayout()
        heading.addWidget(label('EMOTION PILOT', 'title'))
        heading.addWidget(label('Nhận diện biểu cảm  /  Điều khiển TurtleBot', 'muted'))
        header.addLayout(heading)
        header.addStretch()
        self.mode = label('●  DEMO' if args.demo else '●  XEM TRƯỚC' if args.preview else '●  ROS 2 HUMBLE')
        self.mode.setStyleSheet('color: #5eead4; font-weight: 700;')
        header.addWidget(self.mode)
        outer.addLayout(header)
        columns = W.QHBoxLayout()
        columns.setSpacing(18)
        outer.addLayout(columns, 1)
        left = W.QVBoxLayout()
        columns.addLayout(left, 7)
        camera_card, camera_layout = card()
        title = W.QHBoxLayout()
        title.addWidget(label('CAMERA TRỰC TIẾP'))
        title.addStretch()
        self.camera_info = label('Đang kết nối…', 'muted')
        title.addWidget(self.camera_info)
        camera_layout.addLayout(title)
        self.video = label('Đang mở webcam…', 'video')
        self.video.setAlignment(QtCore.Qt.AlignCenter)
        self.video.setMinimumSize(320, 220)
        self.video.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Ignored)
        camera_layout.addWidget(self.video, 1)
        self.model = label('Đang khởi tạo mô hình…', 'muted')
        self.model.setWordWrap(True)
        self.model.setMinimumWidth(0)
        self.model.setMinimumHeight(42)
        self.model.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Minimum)
        camera_layout.addWidget(self.model)
        left.addWidget(camera_card, 1)
        telemetry, tl = card()
        metrics = W.QHBoxLayout()
        self.linear = label('0.00 m/s')
        self.angular = label('0.00 rad/s')
        for title_text, value in [('VẬN TỐC THẲNG', self.linear), ('VẬN TỐC GÓC', self.angular)]:
            col = W.QVBoxLayout()
            col.addWidget(label(title_text, 'muted'))
            value.setStyleSheet('font-size: 24px; font-weight: 700;')
            col.addWidget(value)
            metrics.addLayout(col)
        tl.addLayout(metrics)
        self.status = label('Chưa bật điều khiển')
        self.status.setWordWrap(True)
        tl.addWidget(self.status)
        left.addWidget(telemetry)
        sidebar = W.QScrollArea()
        sidebar.setWidgetResizable(True)
        sidebar.setFrameShape(W.QFrame.NoFrame)
        sidebar.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        sidebar.setMinimumWidth(360)
        sidebar.setMaximumWidth(440)
        sidebar_content = W.QWidget()
        right = W.QVBoxLayout(sidebar_content)
        right.setContentsMargins(0, 0, 6, 0)
        right.setSpacing(16)
        right.setSizeConstraint(W.QLayout.SetMinAndMaxSize)
        sidebar.setWidget(sidebar_content)
        columns.addWidget(sidebar, 4)
        emotion_card, el = card()
        el.addWidget(label('BIỂU CẢM HIỆN TẠI', 'muted'))
        self.emotion = label('Đang chờ…', 'emotion')
        self.emotion.setMinimumHeight(44)
        self.emotion.setWordWrap(True)
        el.addWidget(self.emotion)
        self.action = label('Hãy nhìn thẳng vào camera', 'muted')
        self.action.setWordWrap(True)
        el.addWidget(self.action)
        self.emotion_state = label('Chờ khuôn mặt rõ và kết quả ổn định', 'muted')
        self.emotion_state.setWordWrap(True)
        el.addWidget(self.emotion_state)
        right.addWidget(emotion_card)
        controls, cl = card()
        cl.addWidget(label('ĐIỀU KHIỂN PHIÊN', 'muted'))
        form = W.QFormLayout()
        form.setFieldGrowthPolicy(W.QFormLayout.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(12)
        self.speed = W.QDoubleSpinBox()
        self.speed.setMinimumHeight(34)
        self.speed.setRange(0.03, MAX_LINEAR_SPEED)
        self.speed.setSingleStep(0.01)
        self.speed.setValue(self.controller.settings.linear)
        self.speed.setSuffix(' m/s')
        self.threshold = W.QDoubleSpinBox()
        self.threshold.setMinimumHeight(34)
        self.threshold.setRange(40, 95)
        self.threshold.setValue(60)
        self.threshold.setSuffix(' %')
        form.addRow('Tốc độ tiến / lùi', self.speed)
        form.addRow('Ngưỡng tin cậy', self.threshold)
        cl.addLayout(form)
        self.start = W.QPushButton('BẬT ĐIỀU KHIỂN')
        self.start.setObjectName('start')
        self.start.clicked.connect(self.arm)
        cl.addWidget(self.start)
        self.stop_button = W.QPushButton('■ DỪNG ROBOT · SPACE')
        self.stop_button.setObjectName('stop')
        self.stop_button.clicked.connect(self.stop)
        cl.addWidget(self.stop_button)
        note = label('Xác nhận biểu cảm 1–2 giây, robot tự chạy hết động tác. Neutral để dừng và nhận lệnh mới.\nKhông cần giữ nét mặt suốt lúc chạy. Space để dừng phiên.', 'muted')
        note.setWordWrap(True)
        cl.addWidget(note)
        right.addWidget(controls)
        right.addStretch()
        self.log = W.QTextEdit()
        self.log.setReadOnly(True)
        self.log.document().setMaximumBlockCount(200)
        self.log.setMaximumHeight(75)
        outer.addWidget(self.log)
        footer = label(f'CAM {args.camera}   •   {args.cmd_vel}   •   {args.odom}   |   SPACE: dừng   •   ESC: thoát', 'muted')
        outer.addWidget(footer)
        W.QShortcut(QtGui.QKeySequence('Space'), self, activated=self.stop)
        W.QShortcut(QtGui.QKeySequence('Escape'), self, activated=self.close)
        self.vision = Vision(args.camera, args.demo, args.face_detector)
        if not args.preview and not args.demo:
            try:
                from .ros_bridge import RosBridge
                self.bridge = RosBridge(self.controller, self.lock, args.cmd_vel, args.odom)
            except Exception as exc:
                self.log.append(f'Không khởi tạo được ROS 2: {exc}. Khởi động lại sau khi source ROS.')
                self.start.setEnabled(False)
        self.start.setEnabled(False)
        self.vision.start()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)

    def arm(self):
        if not self.vision.ready:
            self.log.append('Mô hình chưa sẵn sàng. Xem thông báo dưới camera.')
            return
        with self.lock:
            self.controller.settings.linear = self.speed.value()
            self.controller.settings.confidence = self.threshold.value() / 100
            self.vision.filter.confidence = self.threshold.value() / 100
            self.controller.arm()
        self.speed.setEnabled(False)
        self.threshold.setEnabled(False)
        self.start.setEnabled(False)
        self.log.append('Bật phiên điều khiển' + (' • chỉ xem trước' if not self.bridge else ''))

    def stop(self):
        with self.lock:
            self.controller.stop('Đã dừng bằng nút / phím SPACE')
        self.speed.setEnabled(True)
        self.threshold.setEnabled(True)
        self.start.setEnabled(self.bridge is not None or self.args.preview or self.args.demo)

    def refresh(self):
        now = time.monotonic()
        frame, stamp, result, sequence, error, camera_ok, model, display_emotion = self.vision.snapshot()
        fresh = camera_ok and now - stamp < 0.7
        transport_ok = ((self.bridge is not None and not self.bridge.error)
                        or self.args.preview or self.args.demo)
        self.start.setEnabled(self.vision.ready and fresh and transport_ok and not self.controller.armed)
        with self.lock:
            if sequence != self.last_sequence and result:
                emotion, scores, box, captured = result
                self.controller.observe(emotion, scores.get(emotion, 0) / 100, captured,
                                        face_present=bool(scores))
                self.last_sequence = sequence
            if not fresh:
                self.controller.observe(None, 0, now, face_present=False)
            if not self.bridge:
                velocity = self.controller.command(now)
            else:
                velocity = self.bridge.velocity
            state = self.controller.status
            running_action = self.controller.active
        self.status.setText(state)
        if state != self.last_status:
            self.log.append(time.strftime('%H:%M:%S') + '  ' + state)
            self.last_status = state
        self.linear.setText(f'{velocity[0]:+.2f} m/s')
        self.angular.setText(f'{velocity[1]:+.2f} rad/s')
        model_message = error or model
        self.model.setText(model_message[:280] + ('… (xem terminal)' if len(model_message) > 280 else ''))
        self.model.setToolTip(model_message)
        if error and error != self.last_model_error:
            self.log.append(error)
        self.last_model_error = error
        valid_result = result and now - result[3] < self.controller.settings.stale_seconds and fresh
        emotion, scores, box = result[:3] if valid_result else (None, {}, None)
        shown = display_emotion if valid_result else None
        self.emotion.setText(EMOTIONS[shown][0] if shown in EMOTIONS else 'Đang xác nhận…')
        action_text = EMOTIONS[emotion][1] if emotion in EMOTIONS else 'Chờ một khuôn mặt / đủ độ tin cậy'
        if emotion in EMOTIONS and scores.get(emotion, 0) < self.controller.settings.confidence * 100:
            action_text = 'Kết quả chưa đủ tin cậy • Robot dừng'
        elif emotion == 'disgust':
            action_text = 'Disgust không gán chuyển động • Robot dừng'
        if valid_result and scores and emotion is None:
            action_text = 'Đang xác nhận biểu cảm • Robot dừng'
        elif not scores:
            action_text = 'Chờ khuôn mặt rõ, nhìn thẳng camera'
        if running_action is not None:
            action_text = f'Đang thực hiện: {EMOTIONS[running_action][1]} • Neutral để dừng'
        self.action.setText(action_text)
        if emotion in EMOTIONS and valid_result:
            self.emotion_state.setText('● Biểu cảm đã được xác nhận')
            self.emotion_state.setStyleSheet('color: #5eead4;')
        elif shown in EMOTIONS and valid_result and scores:
            self.emotion_state.setText('Tên đang hiển thị là kết quả gần nhất; đang xác nhận lại')
            self.emotion_state.setStyleSheet('color: #fbbf24;')
        else:
            self.emotion_state.setText('Chưa có biểu cảm được xác nhận')
            self.emotion_state.setStyleSheet('color: #94a3b8;')
        if frame is not None:
            if stamp != self.last_frame_stamp:
                self.fps = 1 / max(stamp - self.last_frame_stamp, 0.001) if self.last_frame_stamp else 0
                self.last_frame_stamp = stamp
            if box:
                x, y, w, h = box
                cv2.rectangle(frame, (x, y), (x+w, y+h), (190, 230, 45), 2)
            if self.args.demo:
                cv2.putText(frame, 'DEMO - SYNTHETIC EMOTIONS', (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 210, 250), 2)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = QtGui.QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QtGui.QImage.Format_RGB888).copy()
            self.video.setPixmap(QtGui.QPixmap.fromImage(image).scaled(self.video.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.camera_info.setText(f'● {self.fps:.0f} FPS' if fresh else '● Camera ngắt kết nối')

    def closeEvent(self, event):
        self.timer.stop()
        self.stop()
        try:
            if self.bridge:
                self.bridge.close()
        finally:
            self.vision.close()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Emotion Pilot — TurtleBot facial expression control')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--face-detector', default='yunet', choices=['yunet', 'retinaface', 'opencv'],
                        help='Bộ phát hiện/căn mặt bên trong DeepFace (mặc định YuNet)')
    parser.add_argument('--cmd-vel', default='/cmd_vel')
    parser.add_argument('--odom', default='/odom')
    parser.add_argument('--preview', action='store_true', help='Nhận diện thật, không kết nối ROS')
    parser.add_argument('--demo', action='store_true', help='Biểu cảm giả lập để xem UI; luôn tắt ROS')
    args = parser.parse_args(argv)
    app = W.QApplication([sys.argv[0]])
    app.setApplicationName('Emotion Pilot')
    window = Dashboard(args)
    signal.signal(signal.SIGINT, lambda *_: window.close())
    window.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
