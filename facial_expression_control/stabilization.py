"""Temporal emotion filtering, independent of camera, Qt and ROS."""
import math

LABELS = ('angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral')


def overlap(a, b):
    """Intersection over union for (x, y, width, height) boxes."""
    x = max(a[0], b[0])
    y = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    intersection = max(0, right - x) * max(0, bottom - y)
    union = a[2] * a[3] + b[2] * b[3] - intersection
    return intersection / union if union > 0 else 0.0


class EmotionFilter:
    def __init__(self, confidence=0.60, margin=0.12, settle_seconds=0.65,
                 min_samples=3, time_constant=0.45, max_gap=1.5):
        self.confidence = confidence
        self.margin = margin
        self.settle_seconds = settle_seconds
        self.min_samples = min_samples
        self.time_constant = time_constant
        self.max_gap = max_gap
        self.reset()

    def reset(self):
        self.scores = {}
        self.display = None
        self.candidate = None
        self.since = None
        self.samples = 0
        self.last_at = None
        self.box = None

    def update(self, scores, now, box=None):
        """Return a command label or None; display may retain a previous confirmed label.

        Retained display labels must never be used as robot commands.
        Missing/ambiguous faces must call reset(), rather than feeding old scores.
        """
        values = {key: float(scores.get(key, 0.0)) for key in LABELS}
        if not all(math.isfinite(v) and v >= 0 for v in values.values()) or sum(values.values()) <= 0:
            self.reset()
            return None, {}
        if self.last_at is not None:
            gap = now - self.last_at
            if gap <= 0 or gap > self.max_gap or (self.box is not None and box is not None
                                                and overlap(self.box, box) < 0.2):
                self.reset()
        total = sum(values.values())
        raw = {key: value / total for key, value in values.items()}
        if not self.scores:
            self.scores = raw.copy()
        else:
            alpha = 1 - math.exp(-(now - self.last_at) / self.time_constant)
            self.scores = {key: alpha * raw[key] + (1 - alpha) * self.scores[key]
                           for key in LABELS}
        self.last_at, self.box = now, box
        ranked = sorted(self.scores, key=self.scores.get, reverse=True)
        top, second = ranked[:2]
        raw_top = max(raw, key=raw.get)
        qualifies = (self.scores[top] >= self.confidence
                     and self.scores[top] - self.scores[second] >= self.margin)
        # Stop on strong new evidence before smoothing catches up; don't drive the old action.
        if raw_top != top and raw[raw_top] - raw[top] >= self.margin:
            qualifies = False
        if not qualifies:
            self.candidate, self.since, self.samples = None, None, 0
            return None, self.percentages()
        if top != self.candidate:
            self.candidate, self.since, self.samples = top, now, 1
        else:
            self.samples += 1
        if self.samples >= self.min_samples and now - self.since >= self.settle_seconds:
            self.display = top
            return top, self.percentages()
        return None, self.percentages()

    def percentages(self):
        return {key: 100 * value for key, value in self.scores.items()}
