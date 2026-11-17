"""DeepFace emotion analysis with landmark detection and an explicit BGR crop.

Keep face extraction and classification separate: detect/align once, choose the
foreground face, then classify only that verified crop without re-detection.
"""
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

import numpy as np


def ensure_yunet_weights():
    """Avoid saving Git LFS pointers / partial downloads as detector weights."""
    root = Path(os.environ.get('DEEPFACE_HOME', str(Path.home()))) / '.deepface' / 'weights'
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'face_detection_yunet_2023mar.onnx'
    if target.exists() and target.stat().st_size > 10000:
        return target
    url = ('https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/'
           'face_detection_yunet/face_detection_yunet_2023mar.onnx')
    temporary = None
    try:
        request = Request(url, headers={'User-Agent': 'EmotionPilot/0.2'})
        with urlopen(request, timeout=20) as response:
            expected = response.headers.get('Content-Length')
            size = 0
            with tempfile.NamedTemporaryFile(dir=root, suffix='.part', delete=False) as output:
                temporary = Path(output.name)
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    output.write(chunk)
                    size += len(chunk)
        if size < 10000 or (expected and size != int(expected)):
            raise ValueError('File YuNet tải chưa đầy đủ')
        os.replace(temporary, target)
        return target
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


class DeepFaceBackend:
    def __init__(self, detector='yunet', progress=None):
        from deepface import DeepFace
        self.api = DeepFace
        self.detector = detector
        if progress:
            progress('DeepFace • Đang nạp mô hình Emotion…')
        self.api.build_model('Emotion', task='facial_attribute')
        if detector == 'yunet':
            if progress:
                progress('DeepFace • Đang chuẩn bị YuNet và điểm mốc khuôn mặt…')
            ensure_yunet_weights()
        self.api.build_model(detector, task='face_detector')

    def analyze(self, frame):
        try:
            faces = self.api.extract_faces(
                img_path=frame, detector_backend=self.detector,
                enforce_detection=True, align=True, expand_percentage=0,
                color_face='bgr', normalize_face=False,
            )
        except ValueError as exc:
            if 'Face could not be detected' in str(exc):
                return {}, None, 'Chưa thấy mặt rõ • Nhìn thẳng và đứng gần camera'
            raise
        # Ignore tiny distant faces before foreground selection.
        faces = [f for f in faces if min(f['facial_area']['w'], f['facial_area']['h']) >= 80]
        faces.sort(key=lambda f: f['facial_area']['w'] * f['facial_area']['h'], reverse=True)
        if not faces:
            return {}, None, 'Khuôn mặt còn nhỏ • Đứng gần camera hơn'
        area = lambda face: face['facial_area']['w'] * face['facial_area']['h']
        if len(faces) > 1 and area(faces[0]) <= 1.8 * area(faces[1]):
            return {}, None, 'Chưa rõ người điều khiển • Có nhiều khuôn mặt lớn'
        face = faces[0]
        region = face['facial_area']
        box = tuple(int(region[key]) for key in ('x', 'y', 'w', 'h'))
        if self.detector in ('yunet', 'retinaface'):
            if region.get('left_eye') is None or region.get('right_eye') is None:
                return {}, box, 'Chưa xác định được hai mắt • Nhìn thẳng camera'
        crop = np.ascontiguousarray(face['face'])
        if crop.size == 0 or crop.ndim != 3 or crop.shape[2] != 3:
            return {}, box, 'Vùng mặt không hợp lệ'
        # extract_faces returns unnormalized BGR; analyze owns all model preprocessing.
        result = self.api.analyze(
            img_path=crop, actions=['emotion'], detector_backend='skip',
            enforce_detection=True, align=False, silent=True,
        )
        if not result:
            return {}, box, 'Chưa có kết quả nhận diện'
        scores = {name: float(value) for name, value in result[0]['emotion'].items()}
        if not scores or not all(np.isfinite(value) and value >= 0 for value in scores.values()):
            raise ValueError('Mô hình trả điểm số không hợp lệ')
        return scores, box, ''
