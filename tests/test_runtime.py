"""Run with: python3 -m unittest discover -s tests -v (requires msgpack)."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import queue
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import msgpack

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "bricks/ros2_jazzy/app"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Bridge = load("test_bridge", APP / "app_utils/bridge.py").Bridge
SAMPLE = dict(ok=True, ax=0.1, ay=-0.2, az=9.81, gx=0.01, gy=0.02, gz=-0.03, temperature=25.5)
FAST_SAMPLE = [1.0, 100.0, 0.1, -0.2, 9.81, 0.01, 0.02, -0.03]


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir="/tmp")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.directory.name + "/router.sock")
        self.server.listen()
        self.server.settimeout(3)
        Bridge.SOCKET_PATH = self.directory.name + "/router.sock"
        self.errors = []

    def tearDown(self):
        Bridge.close()
        self.server.close()
        self.directory.cleanup()

    def serve(self, handler):
        def run():
            try:
                handler()
            except BaseException as error:
                self.errors.append(error)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def request(self, connection):
        unpacker = msgpack.Unpacker(raw=False)
        while True:
            unpacker.feed(connection.recv(4096))
            for message in unpacker:
                return message

    def finish(self, thread):
        thread.join(4)
        self.assertFalse(thread.is_alive())
        if self.errors:
            raise self.errors[0]

    def test_fragmented_response_and_repeated_polling(self):
        def handler():
            with self.server.accept()[0] as connection:
                for _ in range(2):
                    request = self.request(connection)
                    self.assertEqual(request[2:], ["read_imu", []])
                    reply = msgpack.packb([1, request[1], None, json.dumps(SAMPLE)])
                    connection.sendall(reply[:3])
                    connection.sendall(reply[3:])
        thread = self.serve(handler)
        for _ in range(2):
            self.assertEqual(json.loads(Bridge.call("read_imu")), SAMPLE)
        self.finish(thread)

    def test_disconnect_reconnects_next_call(self):
        def handler():
            with self.server.accept()[0] as connection:
                self.request(connection)  # Close without replying.
            with self.server.accept()[0] as connection:
                request = self.request(connection)
                connection.sendall(msgpack.packb([1, request[1], None, 42]))
        thread = self.serve(handler)
        with self.assertRaises(ConnectionError):
            Bridge.call("read_imu")
        self.assertEqual(Bridge.call("read_a0"), 42)
        self.finish(thread)

    def test_timeout_drops_socket_and_late_response(self):
        def handler():
            with self.server.accept()[0] as connection:
                self.request(connection)
                time.sleep(0.15)
            with self.server.accept()[0] as connection:
                request = self.request(connection)
                connection.sendall(msgpack.packb([1, request[1], None, 7]))
        thread = self.serve(handler)
        with self.assertRaises(TimeoutError):
            Bridge.call("read_imu", timeout=0.05)
        self.assertIsNone(Bridge._socket)
        self.assertEqual(Bridge.call("read_a0"), 7)
        self.finish(thread)

    def test_rpc_error_is_reported_and_connection_discarded(self):
        def handler():
            with self.server.accept()[0] as connection:
                request = self.request(connection)
                connection.sendall(msgpack.packb([1, request[1], "unknown method", None]))
        thread = self.serve(handler)
        with self.assertRaisesRegex(RuntimeError, "unknown method"):
            Bridge.call("missing")
        self.assertIsNone(Bridge._socket)
        self.finish(thread)


class FakeMessage:
    def __init__(self):
        self.header = types.SimpleNamespace(stamp=None, frame_id="")
        self.orientation_covariance = [0.0] * 9
        self.linear_acceleration = types.SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.angular_velocity = types.SimpleNamespace(x=0.0, y=0.0, z=0.0)
        self.temperature = 0.0


class FakeNode:
    """Record publishers and timer periods without requiring an installed ROS."""
    def __init__(self, name):
        self.log_messages = []

    def create_publisher(self, *args):
        messages = []
        return types.SimpleNamespace(publish=messages.append, messages=messages)

    def create_timer(self, period, callback):
        return types.SimpleNamespace(period=period, callback=callback, timer_period_ns=round(period * 1e9))

    def get_logger(self):
        return types.SimpleNamespace(info=self.log_messages.append, warning=self.log_messages.append)

    def get_clock(self):
        return types.SimpleNamespace(now=lambda: types.SimpleNamespace(to_msg=lambda: "stamp"))


class ConversionTests(unittest.TestCase):
    def setUp(self):
        modules = {
            "rclpy": types.ModuleType("rclpy"),
            "rclpy.node": types.SimpleNamespace(Node=FakeNode),
            "rclpy.qos": types.SimpleNamespace(qos_profile_sensor_data=object()),
            "sensor_msgs": types.ModuleType("sensor_msgs"),
            "sensor_msgs.msg": types.SimpleNamespace(Imu=FakeMessage, Temperature=FakeMessage),
            "app_utils": types.SimpleNamespace(Bridge=Bridge),
            "arduino": types.ModuleType("arduino"),
            "arduino.app_utils": types.SimpleNamespace(Bridge=Bridge),
        }
        with patch.dict(sys.modules, modules):
            self.publisher = load("test_sensor", APP / "ros_sensor.py")
            self.listener = load("test_listener", APP / "ros_listener.py")
            self.console = load("test_console", ROOT / "python/main.py")

    def test_message_units_frame_timestamp_and_missing_orientation(self):
        node = self.publisher.ImuPublisher()
        node.fast_protocol = False  # Exercise compatibility with the older sketch.
        node.last_slow_warning = time.monotonic()
        node.frame_id = "imu_link"
        imu, temperature = [], []
        node.imu = types.SimpleNamespace(publish=imu.append)
        node.temperature = types.SimpleNamespace(publish=temperature.append)
        node.get_clock = lambda: types.SimpleNamespace(now=lambda: types.SimpleNamespace(to_msg=lambda: "stamp"))
        with patch.object(Bridge, "call", return_value=json.dumps(SAMPLE)):
            node.publish_measurements()
        self.assertEqual(temperature, [])  # High-rate callback must not publish temperature.
        node.publish_temperature()  # Called separately by its two-second timer.
        self.assertEqual(imu[0].linear_acceleration.z, 9.81)
        self.assertEqual(imu[0].angular_velocity.z, -0.03)
        self.assertEqual(imu[0].orientation_covariance[0], -1.0)
        self.assertEqual(temperature[0].temperature, 25.5)
        self.assertEqual(imu[0].header.frame_id, "imu_link")
        self.assertEqual(imu[0].header.stamp, temperature[0].header.stamp)

    def test_compact_transport_preserves_library_units(self):
        sample = self.publisher.decode_fast_sample(FAST_SAMPLE)
        for key in self.publisher.AXIS_NAMES:
            self.assertEqual(sample[key], SAMPLE[key])
        self.assertNotIn("temperature", sample)

    def test_invalid_compact_packets_are_rejected(self):
        for packet in ([], FAST_SAMPLE[:-1], [0] + FAST_SAMPLE[1:],
                       [True] + FAST_SAMPLE[1:], [1, 0] + FAST_SAMPLE[2:],
                       FAST_SAMPLE[:-1] + [float("nan")], FAST_SAMPLE[:-1] + ["0"]):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                self.publisher.decode_fast_sample(packet)

    def test_fast_path_sends_only_imu_requests_and_reuses_message(self):
        node = self.publisher.ImuPublisher()
        node.fast_protocol = True
        with patch.object(Bridge, "call", return_value=FAST_SAMPLE) as call:
            for _ in range(10):
                node.publish_measurements()
        self.assertEqual([entry.args[0] for entry in call.call_args_list], ["read_imu_fast"] * 10)
        self.assertEqual(len(node.imu.messages), 10)
        self.assertEqual(len({id(message) for message in node.imu.messages}), 1)
        self.assertEqual(node.temperature.messages, [])
        self.assertEqual(node.temperature_timer.period, 2.0)
        with patch.object(Bridge, "call", return_value=27.88) as call:
            node.publish_temperature()
        call.assert_called_once_with("read_temperature", timeout=0.5)
        self.assertEqual(node.temperature.messages[0].temperature, 27.88)

    def test_temperature_error_does_not_pause_imu(self):
        node = self.publisher.ImuPublisher()
        node.fast_protocol = True
        with patch.object(Bridge, "call", side_effect=TimeoutError):
            node.publish_temperature()
        self.assertEqual(node.retry_at, 0)
        with patch.object(Bridge, "call", return_value=FAST_SAMPLE):
            node.publish_measurements()
        self.assertEqual(len(node.imu.messages), 1)

    def test_compact_transport_is_negotiated_once(self):
        node = self.publisher.ImuPublisher()
        with patch.object(Bridge, "call", side_effect=[{"fast_protocol": 1}, FAST_SAMPLE, FAST_SAMPLE]) as call:
            node.publish_measurements()
            node.publish_measurements()
        self.assertEqual([entry.args[0] for entry in call.call_args_list],
                         ["imu_config", "read_imu_fast", "read_imu_fast"])

    def test_compact_payload_is_smaller_than_json(self):
        compact_bytes = msgpack.packb(FAST_SAMPLE, use_single_float=True)
        legacy_bytes = msgpack.packb(json.dumps(SAMPLE))
        self.assertLess(len(compact_bytes), len(legacy_bytes) / 2)

    def test_ros_rate_follows_sketch_after_redeployment(self):
        node = object.__new__(self.publisher.ImuPublisher)
        node.target_rate = 100.0
        node.timer = types.SimpleNamespace(timer_period_ns=10_000_000)
        messages = []
        node.get_logger = lambda: types.SimpleNamespace(info=messages.append)
        node.follow_sketch_rate(dict(SAMPLE, rate_hz=400))
        self.assertEqual(node.timer.timer_period_ns, 2_500_000)
        self.assertEqual(node.target_rate, 400)
        node.follow_sketch_rate(dict(SAMPLE, rate_hz=25))
        self.assertEqual(node.timer.timer_period_ns, 40_000_000)
        self.assertEqual(len(messages), 2)
        self.assertEqual(self.publisher.requested_rate(SAMPLE), 100)

    def test_invalid_sketch_rate_is_rejected(self):
        for rate in (0, -1, 1601, True, "400", float("nan"), float("inf")):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                self.publisher.decode_sample(dict(SAMPLE, rate_hz=rate))

    def test_console_explains_effective_sketch_configuration(self):
        config = dict(rate_hz=400, accel_range_g=12, gyro_range_dps=1000,
                      filter="SMOOTH", accel_odr_hz=400, gyro_odr_hz=400,
                      accel_bandwidth_hz=40, gyro_bandwidth_hz=47)
        output = io.StringIO()
        with patch.object(Bridge, "call", return_value=json.dumps(config)), contextlib.redirect_stdout(output):
            self.console.print_configuration()
        for phrase in ("Target 400 Hz", "±12 g", "±1000 °/s", "SMOOTH", "gyro 47 Hz"):
            self.assertIn(phrase, output.getvalue())

    def test_reject_unready_missing_nonfinite_and_boolean_measurements(self):
        for value in (dict(ok=False), dict(SAMPLE, ax=True), dict(SAMPLE, az=float("nan")),
                      dict(SAMPLE, gx=float("inf")), {"ok": True}, [], "broken json"):
            with self.subTest(value=value), self.assertRaises((ValueError, KeyError)):
                self.publisher.decode_sample(value)

    def test_console_reports_sensor_values(self):
        with patch.object(Bridge, "call", return_value=json.dumps(SAMPLE)):
            sample = self.console.read_imu()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.console.print_measurements(sample)
        self.assertIn("[STM32]", output.getvalue())
        self.assertIn("25.50 °C", output.getvalue())
        self.assertIn("Z=+9.810", output.getvalue())

    def test_console_accepts_cached_compact_measurements(self):
        with patch.object(Bridge, "call", return_value=FAST_SAMPLE + [27.88]) as call:
            sample = self.console.read_imu(compact=True)
        call.assert_called_once_with("read_imu_cached", timeout=2.0)
        self.assertEqual(sample["temperature"], 27.88)
        self.assertEqual(sample["az"], 9.81)

    def test_listener_accepts_slow_temperature_and_reports_imu_independently(self):
        listener = object.__new__(self.listener.ImuListener)
        listener.latest_imu = listener.latest_temperature = FakeMessage()
        listener.imu_count = 100
        now = time.monotonic()
        listener.last_report = now - 1
        listener.last_received = [now, now - 2.5]
        logs = []
        listener.get_logger = lambda: types.SimpleNamespace(info=logs.append, warning=logs.append)
        listener.report()
        self.assertIn("age 2.5 s", logs[0])
        self.assertIn("received: IMU", logs[0])
        listener.last_received[1] = now - 7
        listener.report()
        self.assertIn("T=waiting", logs[-1])
        self.assertIn("received: IMU", logs[-1])
        listener.last_received[0] = now - 3
        listener.report()
        self.assertIn("Waiting for fresh messages", logs[-1])


class ReloadTests(unittest.TestCase):
    def test_parallel_children_reload_crash_recovery_and_shutdown(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            app = Path(directory)
            shutil.copy(APP / "run.py", app / "run.py")
            for script in ("ros_sensor.py", "ros_listener.py"):
                (app / script).write_text(
                    "import time\nprint('" + script + " started', flush=True)\n"
                    "try:\n    time.sleep(60)\nexcept KeyboardInterrupt:\n    pass\n"
                )
            process = subprocess.Popen(
                [sys.executable, "-u", str(app / "run.py")],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            lines = queue.Queue()
            def collect():
                for line in process.stdout:
                    lines.put(line)
            thread = threading.Thread(target=collect, daemon=True)
            thread.start()

            def expect(fragment, timeout=8):
                deadline = time.monotonic() + timeout
                observed = []
                while time.monotonic() < deadline:
                    try:
                        line = lines.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    observed.append(line)
                    if fragment in line:
                        return
                self.fail(f"Missing {fragment!r}: {observed}")

            try:
                expect("starting publisher + listener")
                # Both are independent children, started without blocking on each other.
                starts = {lines.get(timeout=3).strip(), lines.get(timeout=3).strip()}
                self.assertEqual(starts, {"ros_sensor.py started", "ros_listener.py started"})
                (app / "ros_sensor.py").write_text("print('new deployed source', flush=True)\n")
                expect("Deployed source changed")
                expect("new deployed source")
                expect("A ROS process exited")
                expect("starting publisher + listener")
            finally:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=8)
                thread.join(2)
                process.stdout.close()
            self.assertEqual(process.returncode, 0)


if __name__ == "__main__":
    unittest.main()
