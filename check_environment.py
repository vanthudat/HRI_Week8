"""Import diagnostics only: never opens cameras, models, ROS nodes or Gazebo."""
import importlib
import os
import sys
import traceback


def main():
    if sys.flags.no_user_site == 0:
        print('Hãy chạy bash run.sh --check để tắt thư viện ở ~/.local.', flush=True)
        return 1
    print('Python:', sys.executable, flush=True)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    try:
        for name in ('numpy', 'pandas', 'scipy', 'absl', 'cv2', 'PyQt5.QtCore',
                     'tf_keras', 'deepface.DeepFace', 'tensorflow.keras.preprocessing'):
            module = importlib.import_module(name)
            print('OK:', name, getattr(module, '__file__', ''), flush=True)
        cv = importlib.import_module('cv2')
        if not hasattr(cv, 'FaceDetectorYN_create'):
            raise RuntimeError('OpenCV chưa hỗ trợ YuNet. Chạy bash install.sh.')
        print('DeepFace/Keras và API YuNet sẵn sàng. Không mở webcam hoặc robot.', flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        print('Lỗi môi trường. Chạy bash install.sh và gửi traceback nếu vẫn lỗi.', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
