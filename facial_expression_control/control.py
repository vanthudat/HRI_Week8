"""Pure motion policy. All timestamps are monotonic seconds."""
import math
from dataclasses import dataclass

# Simulation velocity limits.
MAX_LINEAR_SPEED = 0.46
MAX_ANGULAR_SPEED = 1.9

EMOTIONS = {
    'happy': ('Vui vẻ', 'Quành trái nửa vòng', '#34d399'),
    'sad': ('Buồn', 'Quành phải nửa vòng', '#60a5fa'),
    'neutral': ('Bình thường', 'Dừng tại chỗ', '#94a3b8'),
    'angry': ('Tức giận', 'Lùi nhẹ', '#fb7185'),
    'surprise': ('Ngạc nhiên', 'Xoay một vòng', '#c4b5fd'),
    'fear': ('Sợ hãi', 'Tiến nhẹ', '#fbbf24'),
}


@dataclass
class Settings:
    confidence: float = 0.60
    stable_seconds: float = 0.7
    stale_seconds: float = 2.0
    linear: float = MAX_LINEAR_SPEED
    angular: float = MAX_ANGULAR_SPEED
    arc_angular: float = 0.46
    arc_radius: float = 1.0
    arc_angle: float = math.pi
    spin_angle: float = 2 * math.pi
    step_distance: float = 1.0


class Controller:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.armed = False
        self.candidate = None
        self.candidate_since = 0.0
        self.observed_at = -math.inf
        self.accepted = None
        self.consumed = None
        self.active = None
        self.started = 0.0
        self.yaw = None
        self.odom_at = -math.inf
        self.turn = 0.0
        self.status = 'Chưa bật điều khiển'

    def stop(self, reason='Đã dừng'):
        self.armed = False
        self.active = None
        self.candidate = self.accepted = self.consumed = None
        self.observed_at = -math.inf
        self.status = reason

    def arm(self):
        self.stop('Chờ biểu cảm ổn định')
        self.armed = True

    def observe(self, emotion, confidence, captured_at, *, face_present=None):
        # A face may be tracked while its emotion is uncertain. Keep input freshness
        # separate from emotion confidence so an accepted action can finish.
        if face_present is None:
            face_present = emotion in EMOTIONS
        self.observed_at = captured_at if face_present else -math.inf
        valid = face_present and emotion in EMOTIONS and confidence >= self.settings.confidence
        if not valid:
            self.candidate = self.accepted = None
            if self.active is None:
                self.status = 'Chờ một khuôn mặt rõ và biểu cảm ổn định'
            return
        # Vision's temporal filter has already confirmed Neutral. Stop immediately
        # on this confirmed event, without a second confirmation delay.
        if emotion == 'neutral':
            self.candidate = self.accepted = 'neutral'
            self.candidate_since = captured_at
            self.active = self.consumed = None
            return
        if emotion != self.candidate:
            self.candidate = emotion
            self.candidate_since = captured_at
            self.accepted = None
        if captured_at - self.candidate_since >= self.settings.stable_seconds:
            self.accepted = emotion

    def odometry(self, yaw, now):
        if self.yaw is not None and self.active in ('happy', 'sad', 'surprise'):
            delta = math.atan2(math.sin(yaw - self.yaw), math.cos(yaw - self.yaw))
            direction = -1 if self.active == 'sad' else 1
            self.turn += direction * delta
        self.yaw, self.odom_at = yaw, now

    def command(self, now):
        if not self.armed:
            return 0.0, 0.0
        if now - self.observed_at > self.settings.stale_seconds:
            self.active = self.accepted = self.candidate = None
            self.status = 'Dừng: mất khuôn mặt hoặc kết quả đã cũ'
            return 0.0, 0.0
        if self.accepted == 'neutral':
            self.active = None
            self.status = 'Bình thường • Robot dừng, sẵn sàng nhận lệnh mới'
            return 0.0, 0.0
        if self.active is None:
            if self.consumed is not None:
                self.status = 'Đã thực hiện • Giữ Neutral để nhận lệnh mới'
                return 0.0, 0.0
            if self.accepted is None:
                self.status = 'Đang xác nhận biểu cảm…'
                return 0.0, 0.0
            self.active = self.consumed = self.accepted
            self.started, self.turn = now, 0.0
        # Once latched, finish this action despite uncertain or other non-neutral
        # expressions. Do not replace it or queue a command while it is running.
        s, action = self.settings, self.active
        elapsed = now - self.started
        if action in ('happy', 'sad', 'surprise'):
            if now - self.odom_at > 0.5:
                self.active = None
                self.status = 'Dừng: thiếu hoặc mất odometry /odom'
                return 0.0, 0.0
            spinning = action == 'surprise'
            target = s.spin_angle if spinning else s.arc_angle
            angular = s.angular if spinning else min(s.arc_angular, s.linear / s.arc_radius)
            if self.turn >= target:
                self.active = None
                self.status = ('Đã hoàn thành vòng quay 360°' if spinning
                               else 'Đã hoàn thành cung nửa vòng 180°')
                return 0.0, 0.0
            if elapsed > 2 * target / angular + 3:
                self.active = None
                self.status = 'Dừng: quá thời gian thực hiện góc quay'
                return 0.0, 0.0
            remaining = target - self.turn
            # Slow down near the spin target; do not subtract tolerance from 360°.
            speed = min(angular, max(0.08 if spinning else 0.04, 1.5 * remaining))
            if spinning:
                self.status = f'Xoay tại chỗ • {max(0, math.degrees(self.turn)):.1f}° / 360°'
                return 0.0, speed
            direction = -1 if action == 'sad' else 1
            self.status = f'{EMOTIONS[action][1]} • {max(0, math.degrees(self.turn)):.1f}° / 180°'
            # Scale both velocities together to preserve the circular radius.
            return s.linear * speed / angular, direction * speed
        duration = s.step_distance / s.linear
        if elapsed >= duration:
            self.active = None
            self.status = 'Hoàn thành • Giữ Neutral để nhận lệnh mới'
            return 0.0, 0.0
        self.status = f'{EMOTIONS[action][1]} • {duration - elapsed:.1f}s'
        return {
            'angry': (-s.linear, 0.0), 'fear': (s.linear, 0.0),
        }[action]
