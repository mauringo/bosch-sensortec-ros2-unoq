"""Move BMI088 measurements from the Arduino Bridge to ROS.

Fast stream: request six IMU values as a small numeric array, then publish Imu.
Slow stream: request cached temperature once every two seconds, then publish it.
The BMI088 library in the sketch already supplies the correct physical units.
"""
import json
import math
import os
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, Temperature

from app_utils import Bridge

TEMPERATURE_INTERVAL_SECONDS = 2.0
BRIDGE_TIMEOUT_SECONDS = 0.5
RETRY_DELAY_SECONDS = 2.0
AXIS_NAMES = ("ax", "ay", "az", "gx", "gy", "gz")


def decode_fast_sample(packet):
    """Library measurements arrive as a native MessagePack array, with no JSON."""
    if not isinstance(packet, (list, tuple)) or len(packet) != 8:
        raise ValueError("Invalid fast IMU packet")
    # Packet layout: [ready, requested_hz, ax, ay, az, gx, gy, gz].
    # Reject invalid values before they can reach ROS subscribers.
    for value in packet:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Fast IMU packet must contain finite numbers")
    ok, rate, *axes = packet
    if ok != 1:
        raise ValueError("BMI088 not ready")
    sample = dict(zip(AXIS_NAMES, axes))
    sample["rate_hz"] = rate
    requested_rate(sample)
    return sample


def requested_rate(sample):
    """Older sketches have no rate field and keep the original 100 Hz target."""
    rate = sample.get("rate_hz", 100)
    if (isinstance(rate, bool) or not isinstance(rate, (int, float))
            or not math.isfinite(rate) or not 1 <= rate <= 1600):
        raise ValueError("Sketch rate_hz must be between 1 and 1600")
    return float(rate)


def decode_sample(reply):
    """Compatibility with the older sketch's JSON response."""
    sample = json.loads(reply) if isinstance(reply, (str, bytes)) else reply
    if not isinstance(sample, dict) or sample.get("ok") is not True:
        raise ValueError("BMI088 not ready; waiting for STM32 initialization")
    for key in ("ax", "ay", "az", "gx", "gy", "gz", "temperature"):
        value = sample[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid measurement {key}: {value!r}")
    requested_rate(sample)
    return sample


class ImuPublisher(Node):
    def __init__(self):
        super().__init__("uno_q_bmi088")
        self.target_rate = 100.0  # Updated by the first successful sketch response.
        self.frame_id = os.getenv("IMU_FRAME_ID", "imu_link")
        self.imu = self.create_publisher(Imu, "/imu/data_raw", qos_profile_sensor_data)
        self.temperature = self.create_publisher(Temperature, "/imu/temperature", qos_profile_sensor_data)
        self.retry_at = 0.0
        self.fast_protocol = None  # None = not checked; True = compact; False = older JSON.
        self.legacy_temperature = None
        # Reuse messages instead of allocating new objects for every sample.
        self.imu_message = Imu()
        self.imu_message.header.frame_id = self.frame_id
        self.imu_message.orientation_covariance[0] = -1.0
        self.temperature_message = Temperature()
        self.temperature_message.header.frame_id = self.frame_id
        self.last_slow_warning = float("-inf")
        self.timer = self.create_timer(1.0 / self.target_rate, self.publish_measurements)
        # Temperature never runs inside the high-rate IMU callback.
        self.temperature_timer = self.create_timer(TEMPERATURE_INTERVAL_SECONDS, self.publish_temperature)
        self.get_logger().info(f"BMI088 publisher ready; rate follows sketch IMU settings, frame {self.frame_id}")

    def follow_sketch_rate(self, sample):
        """The sketch's one configuration line controls the ROS timer."""
        rate = requested_rate(sample)
        if rate != self.target_rate:
            self.timer.timer_period_ns = round(1_000_000_000 / rate)
            self.target_rate = rate
            self.get_logger().info(f"Sketch requests {rate:g} Hz; ROS timer updated automatically")

    def read_measurements(self):
        """Select the transport once, then make just one RPC per IMU sample."""
        if self.fast_protocol is None:
            reply = Bridge.call("imu_config", timeout=BRIDGE_TIMEOUT_SECONDS)
            config = json.loads(reply) if isinstance(reply, (str, bytes)) else reply
            self.fast_protocol = config.get("fast_protocol") == 1
            description = (
                "Compact IMU transport enabled; temperature publishes every 2 s"
                if self.fast_protocol else
                "Legacy JSON transport; deploy the updated sketch for compact IMU transport"
            )
            self.get_logger().info(description)

        if self.fast_protocol:
            reply = Bridge.call("read_imu_fast", timeout=BRIDGE_TIMEOUT_SECONDS)
            return decode_fast_sample(reply)

        # Let updated Python run with an older sketch during deployment.
        sample = decode_sample(Bridge.call("read_imu", timeout=BRIDGE_TIMEOUT_SECONDS))
        self.legacy_temperature = sample["temperature"]
        return sample

    def publish_measurements(self):
        """Fast path: one Bridge request and one IMU publication."""
        if time.monotonic() < self.retry_at:
            return
        try:
            started = time.monotonic()
            sample = self.read_measurements()
            rpc_seconds = time.monotonic() - started
            self.follow_sketch_rate(sample)
            if rpc_seconds > 1.0 / self.target_rate and time.monotonic() - self.last_slow_warning >= 5:
                self.get_logger().warning(
                    f"Bridge request took {rpc_seconds * 1000:.1f} ms, exceeding the "
                    f"{1000 / self.target_rate:.1f} ms period for {self.target_rate:g} Hz. "
                    "Check the listener's measured Hz to find the sustainable rate."
                )
                self.last_slow_warning = time.monotonic()
            # Reuse the message; rclpy serializes it synchronously during publish.
            imu = self.imu_message
            imu.header.stamp = self.get_clock().now().to_msg()
            imu.linear_acceleration.x = float(sample["ax"])
            imu.linear_acceleration.y = float(sample["ay"])
            imu.linear_acceleration.z = float(sample["az"])
            imu.angular_velocity.x = float(sample["gx"])
            imu.angular_velocity.y = float(sample["gy"])
            imu.angular_velocity.z = float(sample["gz"])
            self.imu.publish(imu)
        except Exception as error:
            self.fast_protocol = None
            self.legacy_temperature = None
            self.get_logger().warning(f"Sensor/Bridge unavailable: {error}; retrying in 2 s")
            self.retry_at = time.monotonic() + RETRY_DELAY_SECONDS

    def publish_temperature(self):
        """Independent low-rate stream; temperature failure does not stop IMU."""
        if self.fast_protocol is None:
            return
        try:
            if self.fast_protocol:
                value = Bridge.call("read_temperature", timeout=BRIDGE_TIMEOUT_SECONDS)
            else:
                value = self.legacy_temperature
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Temperature is not ready")
            message = self.temperature_message
            message.header.stamp = self.get_clock().now().to_msg()
            message.temperature = float(value)
            self.temperature.publish(message)
        except Exception as error:
            self.get_logger().warning(f"Temperature unavailable: {error}; retrying in 2 s")


def main():
    rclpy.init()
    node = None
    try:
        node = ImuPublisher()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        Bridge.close()
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
