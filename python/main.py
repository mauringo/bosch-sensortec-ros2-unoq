"""App Lab console: print STM32 measurements. ROS runs alongside in the Brick."""
import json
import math
import time

from arduino.app_utils import Bridge

PRINT_INTERVAL_SECONDS = 0.5
RPC_TIMEOUT_SECONDS = 2.0
LISTENER_LOG_COMMAND = (
    r'find "$HOME/ArduinoApps" -type f -name UNO_Q_BMI088_APP.marker '
    r'-execdir docker compose -f .cache/app-compose.yaml logs -f --tail=30 ros2 \; -quit'
)


def read_imu(compact=False):
    """Use compact cached measurements when supported; older sketches use JSON."""
    reply = Bridge.call("read_imu_cached" if compact else "read_imu", timeout=RPC_TIMEOUT_SECONDS)
    if compact:
        # Cached packet: [ready, target_hz, ax, ay, az, gx, gy, gz, temperature].
        if not isinstance(reply, (list, tuple)) or len(reply) != 9 or isinstance(reply[0], bool) or reply[0] != 1:
            raise ValueError("BMI088 cached sample is not ready")
        sample = dict(zip(("ax", "ay", "az", "gx", "gy", "gz", "temperature"), reply[2:]))
        sample["ok"] = True
    else:
        sample = json.loads(reply) if isinstance(reply, (str, bytes)) else reply
    if not isinstance(sample, dict) or sample.get("ok") is not True:
        raise ValueError("BMI088 not ready; STM32 will retry initialization")
    for name in ("ax", "ay", "az", "gx", "gy", "gz", "temperature"):
        value = sample[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid {name}: {value!r}")
    return sample


def print_measurements(sample):
    print(
        f"[STM32] Accel (m/s²): X={sample['ax']:+.3f} "
        f"Y={sample['ay']:+.3f} Z={sample['az']:+.3f} | "
        f"Gyro (rad/s): X={sample['gx']:+.4f} "
        f"Y={sample['gy']:+.4f} Z={sample['gz']:+.4f} | "
        f"Temperature: {sample['temperature']:.2f} °C",
        flush=True,
    )


def print_configuration():
    """Report the settings selected by the sketch's one configuration line."""
    reply = Bridge.call("imu_config", timeout=RPC_TIMEOUT_SECONDS)
    config = json.loads(reply) if isinstance(reply, (str, bytes)) else reply
    print(
        f"[STM32 config] Target {config['rate_hz']} Hz | "
        f"Accel ±{config['accel_range_g']} g | Gyro ±{config['gyro_range_dps']} °/s | "
        f"Filter {config['filter']} | "
        f"Sensor ODR: accel {config['accel_odr_hz']} Hz, gyro {config['gyro_odr_hz']} Hz | "
        f"Bandwidth: accel {config['accel_bandwidth_hz']} Hz, gyro {config['gyro_bandwidth_hz']} Hz",
        flush=True,
    )
    return config


def main():
    print("BMI088 console started. Reading STM32 via RouterBridge every 0.5 s.", flush=True)
    print("Look for [ROS listener] in the Brick logs to confirm ROS delivery.", flush=True)
    print("Listener checks: open a terminal on the UNO Q (not inside a container).", flush=True)
    print("Run this one line from any folder, including ~, to follow the automatic listener:", flush=True)
    print(f"  {LISTENER_LOG_COMMAND}", flush=True)
    print("It finds UNO_Q_BMI088_APP.marker and runs Docker Compose from that app folder.", flush=True)
    print("Deploy the marker file with the app. If nothing is found, check ~/ArduinoApps.", flush=True)
    print("If you have multiple copies, it selects the first matching app.", flush=True)
    print("To start an additional live listener, run this FROM the deployed app folder:", flush=True)
    print("  docker compose -f .cache/app-compose.yaml exec ros2 bash /app/check_ros.sh", flush=True)
    print("Press Ctrl+C to stop either terminal check; the app keeps running.", flush=True)
    print("Tune the sketch's IMU line: {Hz, accel ±g, gyro ±°/s, Filter::NORMAL}.", flush=True)
    print("ROS follows that rate automatically; the listener reports the achieved Hz.", flush=True)
    print("Temperature is refreshed every 2 s; console reads reuse cached IMU data when ROS is active.", flush=True)
    configuration_printed = False
    compact_console = False
    try:
        while True:
            try:
                print_measurements(read_imu(compact_console))
                if not configuration_printed:
                    try:
                        config = print_configuration()
                        compact_console = config.get("fast_protocol") == 1
                        configuration_printed = True
                    except Exception as error:
                        print(f"[STM32 config] Waiting for imu_config: {error}", flush=True)
            except Exception as error:
                print(f"[STM32] Waiting for sensor/Bridge: {error}", flush=True)
            time.sleep(PRINT_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("BMI088 console stopped.", flush=True)


if __name__ == "__main__":
    main()
