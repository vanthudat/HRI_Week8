"""ROS transport with an independent 20 Hz control/watchdog loop."""
import math
import threading
import time


class RosBridge:
    def __init__(self, controller, lock, topic='/cmd_vel', odom='/odom'):
        import rclpy
        from rclpy.signals import SignalHandlerOptions
        from rclpy.qos import qos_profile_sensor_data
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        self.rclpy, self.Twist = rclpy, Twist
        self.controller, self.lock = controller, lock
        self.velocity = (0.0, 0.0)
        self.error = ''
        self.quit = threading.Event()
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        self.node = rclpy.create_node('facial_expression_control')
        self.publisher = self.node.create_publisher(Twist, topic, 10)
        self.subscription = self.node.create_subscription(
            Odometry, odom, self._odom, qos_profile_sensor_data)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _odom(self, msg):
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y*q.y + q.z*q.z))
        if math.isfinite(yaw):
            with self.lock:
                self.controller.odometry(yaw, time.monotonic())

    def _publish(self, linear, angular):
        msg = self.Twist()
        msg.linear.x, msg.angular.z = float(linear), float(angular)
        self.publisher.publish(msg)
        self.velocity = (linear, angular)

    def _run(self):
        try:
            while not self.quit.is_set() and self.rclpy.ok():
                self.rclpy.spin_once(self.node, timeout_sec=0.0)
                with self.lock:
                    command = self.controller.command(time.monotonic())
                self._publish(*command)
                self.quit.wait(0.05)
        except Exception as exc:
            self.error = f'ROS 2: {exc}'
            with self.lock:
                self.controller.stop(self.error)
        finally:
            try:
                self._publish(0.0, 0.0)
            except Exception:
                pass

    def close(self):
        with self.lock:
            self.controller.stop()
        self.quit.set()
        self.thread.join(timeout=1.0)
        for _ in range(3):
            self._publish(0.0, 0.0)
        self.node.destroy_node()
        self.rclpy.shutdown()
