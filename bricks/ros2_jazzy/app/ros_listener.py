"""Show received IMU speed and the latest slow temperature update.

This node listens to ROS only. It does not request anything from the Arduino.
"""
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, Temperature


class ImuListener(Node):
    def __init__(self):
        super().__init__("uno_q_bmi088_listener")
        self.latest_imu = None
        self.latest_temperature = None
        self.imu_count = 0
        self.last_received = [0.0, 0.0]
        self.last_report = time.monotonic()
        self.create_subscription(Imu, "/imu/data_raw", self.on_imu, qos_profile_sensor_data)
        self.create_subscription(Temperature, "/imu/temperature", self.on_temperature, qos_profile_sensor_data)
        self.create_timer(1.0, self.report)
        self.get_logger().info("[ROS listener] Listening to /imu/data_raw and /imu/temperature")

    def on_imu(self, message):
        self.latest_imu = message
        self.imu_count += 1
        self.last_received[0] = time.monotonic()

    def on_temperature(self, message):
        self.latest_temperature = message
        self.last_received[1] = time.monotonic()

    def report(self):
        now = time.monotonic()
        interval = now - self.last_report
        imu_hz = self.imu_count / interval
        self.imu_count = 0
        self.last_report = now
        if self.latest_imu is None or now - self.last_received[0] > 2.0:
            self.get_logger().warning("[ROS listener] Waiting for fresh messages on /imu/data_raw")
            return
        temperature_age = now - self.last_received[1]
        # Temperature is intentionally slower. Allow three update periods before
        # marking it stale, and keep displaying IMU data if temperature is absent.
        if self.latest_temperature is None or temperature_age > 6.0:
            temperature_text = "T=waiting (expected every 2 s)"
        else:
            temperature_text = f"T={self.latest_temperature.temperature:.2f} °C (age {temperature_age:.1f} s)"
        acceleration = self.latest_imu.linear_acceleration
        rotation = self.latest_imu.angular_velocity
        self.get_logger().info(
            f"[ROS listener] Accel=({acceleration.x:+.3f}, {acceleration.y:+.3f}, {acceleration.z:+.3f}) m/s² | "
            f"Gyro=({rotation.x:+.4f}, {rotation.y:+.4f}, {rotation.z:+.4f}) rad/s | "
            f"{temperature_text} | received: IMU {imu_hz:.1f} Hz"
        )


def main():
    rclpy.init()
    node = ImuListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
