"""Latest-frame camera and inference workers; no frame backlog."""
import os
import threading
import time
import traceback

import cv2

from .stabilization import EmotionFilter


class Vision:
    def __init__(self, camera=0, demo=False, detector_backend='yunet'):
        self.camera, self.demo = camera, demo
        self.detector_backend = detector_backend
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.frame = None
        self.captured_at = 0.0
        self.result = None
        self.sequence = 0
        self.filter = EmotionFilter()
        self.display_emotion = None
        self.camera_error = ''
        self.inference_error = ''
        self.model_status = 'Đang tải DeepFace…' if not demo else 'DEMO • Không điều khiển robot'
        self.camera_ok = False
        self.ready = False
        self.threads = []

    def start(self):
        for target in (self._camera, self._inference):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads.append(thread)

    def snapshot(self):
        with self.lock:
            return (None if self.frame is None else self.frame.copy(), self.captured_at,
                    self.result, self.sequence, self.camera_error or self.inference_error,
                    self.camera_ok, self.model_status, self.display_emotion)

    def _camera(self):
        # Release and reopen the device after disconnects instead of ending the worker.
        while not self.quit.is_set():
            cap = cv2.VideoCapture(self.camera)
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
                while not self.quit.is_set():
                    ok, frame = cap.read()
                    with self.lock:
                        self.camera_ok = ok
                        if ok:
                            self.camera_error = ''
                            self.frame, self.captured_at = cv2.flip(frame, 1), time.monotonic()
                        else:
                            self.camera_error = f'Không đọc được camera {self.camera}. Đang kết nối lại…'
                    if not ok:
                        break
                    self.quit.wait(0.025)
            except Exception as exc:
                with self.lock:
                    self.camera_ok = False
                    self.camera_error = f'Camera: {exc}'
            finally:
                cap.release()
            self.quit.wait(1.0)

    def _inference(self):
        if not self.demo:
            try:
                os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
                from .deepface_backend import DeepFaceBackend

                def progress(message):
                    with self.lock:
                        self.model_status = message

                backend = DeepFaceBackend(self.detector_backend, progress=progress)
                with self.lock:
                    self.model_status = f'DeepFace + {self.detector_backend} • Sẵn sàng'
                    self.ready = True
            except Exception as exc:
                traceback.print_exc()
                with self.lock:
                    self.inference_error = f'Không tải được DeepFace: {exc}. Đóng ứng dụng, chạy bash install.sh rồi bash run.sh.'
                    self.model_status = 'Lỗi mô hình • Xem README cài đặt'
                return
        if self.demo:
            with self.lock:
                self.ready = True
        last_stamp = 0.0
        while not self.quit.is_set():
            frame, stamp, *_ = self.snapshot()
            if frame is None or stamp == last_stamp or time.monotonic() - stamp > 0.7:
                self.quit.wait(0.05)
                continue
            last_stamp = stamp
            box, scores, emotion = None, {}, None
            try:
                if self.demo:
                    names = ['neutral', 'happy', 'sad', 'angry', 'surprise', 'fear']
                    emotion = names[int(time.monotonic() / 5) % len(names)]
                    scores = {emotion: 95.0}
                else:
                    scores, box, note = backend.analyze(frame)
                    emotion = max(scores, key=scores.get) if scores else None
                with self.lock:
                    self.inference_error = note if not self.demo else ''
            except ValueError as exc:
                if 'Face could not be detected' in str(exc):
                    with self.lock:
                        self.inference_error = ''
                else:
                    with self.lock:
                        self.inference_error = f'Lỗi nhận diện: {exc}'
            except Exception as exc:
                with self.lock:
                    self.inference_error = f'Lỗi nhận diện: {exc}'
            # Filter only real detections, never retain scores through a missing face.
            if emotion is not None and time.monotonic() - stamp <= self.filter.max_gap:
                emotion, scores = self.filter.update(scores, stamp, box)
            else:
                self.filter.reset()
                emotion, scores = None, {}
            with self.lock:
                self.display_emotion = self.filter.display
                self.result = (emotion, scores, box, stamp)
                self.sequence += 1
            self.quit.wait(0.15)

    def close(self):
        self.quit.set()
        for thread in self.threads:
            thread.join(timeout=0.4)
