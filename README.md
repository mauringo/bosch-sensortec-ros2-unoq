# ROS 2 Jazzy + BMI088 on Arduino UNO Q

The STM32 reads the BMI088 over Qwiic (`Wire1`). The App Lab Python console prints its measurements, while the ROS Brick publishes them and runs a listener in parallel. The built-in matrix shows rounded sensor temperature, for example `25C`.

## Run from App Lab

1. Deploy this entire app, including `sketch/`, `python/` and `bricks/`.
2. Stop the old app and Run/Deploy the updated app so App Lab applies the changed Brick Compose configuration.
3. Open the Python console for lines beginning `[STM32]`.
4. Open the ROS Brick/service logs for `[ROS runtime]` and `[ROS listener]`.

Illustrative output (these are not hardware test results):

```text
[STM32] Accel (m/s²): X=+0.010 Y=+0.020 Z=+9.810 | Gyro (rad/s): X=+0.0010 Y=+0.0020 Z=+0.0030 | Temperature: 25.50 °C
[ROS runtime] Source revision a1b2c3d4e5f6; starting publisher + listener
[ROS listener] Accel=(+0.010, +0.020, +9.810) m/s² | Gyro=(+0.0010, +0.0020, +0.0030) rad/s | T=25.50 °C (age 1.0 s) | received: IMU 98.0 Hz
```

The Python console requests cached measurements twice per second. The listener runs as a separate ROS process and reports received IMU values/rate once per second. Temperature publishes once every two seconds; its age is shown separately. The listener does not make additional Bridge requests, and missing temperature does not hide working IMU data.

The STM32 exposes request/response RPC functions. The fast ROS path uses `read_imu_fast`; the console switches to `read_imu_cached` after checking the sketch's capabilities. The older `read_imu` JSON endpoint remains available for compatibility.

## Faster Bridge communication

The BMI088 library is unchanged. The optimization is how readings travel over RouterBridge:

- The IMU response is a native MessagePack array: `[ready, target_hz, ax, ay, az, gx, gy, gz]`. It avoids building a JSON string on the STM32 and parsing JSON for every ROS sample. Library-provided physical units and axis signs are preserved.
- Temperature has its own small RPC and ROS timer, once every two seconds. It is omitted from high-rate IMU packets.
- The console uses a compact cached response, adding temperature as a ninth field. When ROS readings are fresh, console requests do not trigger extra sensor reads. Without ROS, the console can still refresh the sensor.
- ROS reuses its message objects. The matrix skips redraws when its displayed value has not changed. Serial measurement output is suppressed at targets of 100 Hz or higher.
- Configuration is fetched once per connection/recovery attempt. It is not requested on each IMU poll. Python can still use the older JSON transport if the new sketch has not been deployed yet.

Deploy **both sketch and Python/Brick files** to enable compact transport. Look for `Compact IMU transport enabled` in the ROS logs. No new packages or Docker image rebuild are needed for this change after the existing source mount is installed.

Temperature shown in the console and matrix is a two-second cache, and `/imu/temperature` publishes at 0.5 Hz. The unchanged BMI088 library still reads temperature internally as part of `accel.readSensor()`; this change reduces Bridge traffic and ROS work rather than modifying that library or bypassing it. RouterBridge still makes one request/response round trip per IMU sample; measured board throughput must be checked after deployment.

## Tune everything with one sketch line

Edit this line near the top of `sketch/sketch.ino`, then Deploy:

```cpp
constexpr ImuSettings IMU = {100, 6, 500, Filter::NORMAL};
//                          Hz   ±g  ±°/s  filtering
```

| Setting | Allowed values |
| --- | --- |
| Target ROS polling/publishing rate | Integer 1–1600 Hz |
| Accelerometer range | ±3, ±6, ±12 or ±24 g |
| Gyroscope range | ±125, ±250, ±500, ±1000 or ±2000 °/s |
| Filtering | `Filter::WIDE`, `Filter::NORMAL`, `Filter::SMOOTH` |

For example, `{400, 12, 1000, Filter::WIDE}` requests 400 Hz with wider measurement ranges and filtering bandwidth. Start with the default, then increase the first number and watch the listener's received Hz. `WIDE` passes faster motion and more noise; `SMOOTH` selects narrower available filtering. The gyro has fewer bandwidth choices: at 400 Hz its bandwidth is 47 Hz for all three filters, and at 1000 Hz it is 116 Hz for all three. These are convenient profiles over the pinned library's supported settings, not arbitrary filter cutoff values.

The sketch automatically selects hardware output data rates at least as high as the requested rate: accel 25/50/100/200/400/800/1600 Hz, gyro 100/200/400/1000/2000 Hz. Python prints the effective settings, including both bandwidths. ROS reads `rate_hz` from each sample and adjusts its timer, including after a sketch restart. No Compose or Python rate edit is required. Invalid ranges and rates are rejected when compiling the sketch.

The first number is a **requested Bridge/ROS rate**, not a fixed STM32 acquisition schedule or a guarantee of fresh sensor data on every poll. Hardware ODR and polling are asynchronous. Measurements are still read on request, without buffering or data-ready interrupts. At high targets, the publisher warns when an RPC exceeds the requested period; the listener shows the actual delivery rate. Temperature is published independently every two seconds.

At 100 Hz and above, verbose Serial measurement printing is skipped to reduce overhead. Serial printing uses cached samples at lower targets. The Python console and matrix continue working, and the STM32's periodic I²C health check remains active. The practical limit depends on I²C, RPC transport and board load; setting 1600 does not establish that the system can sustain 1600 Hz. Larger ranges capture stronger motion but reduce resolution; use the smallest range that does not clip your motion.

### Check the listener from the UNO Q terminal

Deploy `UNO_Q_BMI088_APP.marker` with the rest of the app, keeping it beside `app.yaml`. Then open a terminal on the UNO Q and run this single line from any folder, including `~`:

```bash
find "$HOME/ArduinoApps" -type f -name UNO_Q_BMI088_APP.marker -execdir docker compose -f .cache/app-compose.yaml logs -f --tail=30 ros2 \; -quit
```

This finds the marker, runs Compose from its directory and follows the already-running listener's logs. Folder names containing spaces are supported. If multiple copies exist, it uses the first match. If nothing happens, check that the marker was deployed under `~/ArduinoApps`.

The relative path `.cache/app-compose.yaml` alone only works from the deployed app directory. Running Compose directly from `~` searches `/home/arduino/.cache/app-compose.yaml`, causing the earlier "no such file or directory" error. The marker command handles the working directory automatically.

From that app directory, start an additional live listener:

```bash
docker compose -f .cache/app-compose.yaml exec ros2 bash /app/check_ros.sh
```

This lists the ROS topics, then prints received IMU values, temperature and measured rates. To follow the automatic listener already running in the Brick instead:

```bash
docker compose -f .cache/app-compose.yaml logs -f --tail=30 ros2
```

`python/main.py` prints both commands at startup. Press Ctrl+C to stop either terminal check; the app and its automatic listener continue running.

## Fixing the stale container after Deploy

Previously the Dockerfile copied Python into the image. If App Lab reused that image, Deploy could run old code until a manual rebuild.

The updated Brick uses:

- A read-only source mount: `./app:/app:ro`, relative to the Brick Compose file.
- A Compose startup command that launches `/app/run.py`, even with a cached image.
- A small supervisor that runs the publisher and listener in parallel. It hashes Python source every 0.5 seconds and reloads both processes when deployed files change.
- A source revision in startup logs, allowing you to see whether the deployed code changed.
- Automatic process recovery and Docker's `unless-stopped` restart policy.

After the new mount and command have been applied once, editing the Brick's Python files and pressing Deploy should use the new source without rebuilding the image. There is no dependency on `docker compose watch`, which ordinary App Lab Run may not start. Reloads briefly interrupt publishing and allow a one-second upload settling period.

**First-deployment limitation:** an already running old container cannot give itself a new mount or startup command. App Lab must recreate it once with this Compose configuration. Try Stop, then Deploy/Run. This setup still needs verification on your installed App Lab version and board.

Dockerfile, base-image and dependency changes still require an image rebuild. A cached image must already contain ROS Jazzy, `rclpy`, `sensor_msgs` and MessagePack; the original ros-base image normally includes the ROS interfaces, and the updated Dockerfile explicitly installs them.

If App Lab still fails to recreate the container initially, the existing one-time host-side workaround remains:

```bash
docker compose -f .cache/app-compose.yaml up -d --build --force-recreate ros2
```

Run that from the app directory on the UNO Q. It should no longer be necessary for ordinary Python source edits after the mount is installed.

`python/main.py` cannot rebuild a Docker service through the normal RouterBridge API. This app does not expose the host Docker daemon to Python. A `no space left on device` image extraction error is a separate host storage problem and occurs before the ROS runtime starts.

## Data flow

```text
BMI088 -> STM32 / Wire1 -> RouterBridge numeric packets
                           |                 |
                           v                 v
                    python/main.py     ROS publisher
                    readable console         |
                                      /imu/data_raw
                                      /imu/temperature
                                             |
                                       ROS listener
                                       values + rates

STM32 -> built-in LED matrix: rounded temperature in °C
```

| Topic | Message | Target rate |
| --- | --- | --- |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` | Sketch setting (default 100 Hz) |
| `/imu/temperature` | `sensor_msgs/msg/Temperature` | 0.5 Hz (every 2 seconds) |

100 Hz is a target, not a guaranteed rate. RouterBridge/I²C latency, console requests and system load affect throughput. Use the automatic listener's measured rates to assess the board.

Measurements use the Bolder Flight library's acceleration in m/s² and angular velocity in rad/s. No raw-register scaling is applied. `imu_link` represents the sensor's axes; there is no mounting transform or calibration. Orientation is unavailable (`orientation_covariance[0] = -1`). Other covariances are zero, meaning unknown. Topics are timestamped separately on Linux receipt; there is no hardware acquisition timestamp. The received temperature comes from the STM32's cache and can already be up to two seconds old; the listener's displayed age measures time since the last ROS temperature message arrived.

The matrix uses a small built-in font with no extra graphics library. It refreshes without scrolling delays, shows whole degrees plus C, scrolls wider values and shows `--` while the sensor is unavailable. Console and ROS temperature retain decimals. This is BMI088 die temperature, not a calibrated ambient thermometer.

## Files to edit

| File | Purpose |
| --- | --- |
| `python/main.py` | Read, validate and print STM32 values in simple functions |
| `sketch/sketch.ino` | BMI088, Bridge services, matrix display and initialization retry |
| `bricks/ros2_jazzy/app/ros_sensor.py` | Validate samples and publish ROS messages |
| `bricks/ros2_jazzy/app/ros_listener.py` | Subscribe and show received measurements/rates |
| `bricks/ros2_jazzy/app/run.py` | Start both processes, recover crashes, reload source |
| `bricks/ros2_jazzy/app/app_utils/bridge.py` | Bounded MessagePack RPC and reconnect-on-failure |
| `bricks/ros2_jazzy/brick_compose.yaml` | Source/socket mounts, startup and ROS configuration |
| `bricks/ros2_jazzy/Dockerfile` | ROS image and installed dependencies |

Change rate, sensor ranges and filtering in the sketch's `IMU` line. The old `IMU_PUBLISH_HZ` environment variable is no longer used. Change `IMU_FRAME_ID` or `ROS_DOMAIN_ID` in the Compose environment, then Stop and Deploy/Run to apply those configuration changes. External subscribers must use the same ROS domain and compatible sensor-data QoS (best effort).

The old `read_a0` RPC remains available for compatibility. This version publishes the BMI088 topics instead of `/analog_sensor`.

## Recovery and diagnostics

- STM32 initialization retries every five seconds while unavailable. A periodic I²C address check detects disconnected devices and requests reinitialization. The unchanged BMI088 1.0.1 `readSensor()` returns void; this is an address-level health check, not a guarantee that every sample is valid.
- The ROS Bridge has a 0.5-second RPC timeout, closes failed connections and reconnects on the next attempt. The publisher waits two seconds after an error, with one warning per failed attempt.
- If either ROS process exits, the supervisor stops its sibling and restarts both after two seconds.
- Container restarts recover runtime failures; they cannot fix a missing image, dependency or bad source.
- `[STM32]` output proves the RPC path works. `[ROS listener]` output proves messages arrived at a subscriber. Neither alone guarantees calibration or a stable 100 Hz.

Optional terminal checks inside the ROS container:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic list
ros2 topic echo /imu/data_raw --qos-reliability best_effort
ros2 topic echo /imu/temperature --qos-reliability best_effort
ros2 topic hz /imu/data_raw
/app/check_ros.sh
```

No board or ROS installation is available in the development workspace. Local tests exercise RPC framing/reconnection, message conversion, sketch-driven ROS rate changes and source reload with simulated peers. A host C++ check uses the pinned BMI088 declarations and Arduino stubs to check syntax and six configuration profiles. Actual board compilation, register behavior, matrix output and achievable rates must be verified on the UNO Q.

## API references

- [Arduino Python Bridge API](https://github.com/arduino/app-bricks-py/blob/main/src/arduino/app_utils/bridge.py)
- [UNO Q matrix implementation](https://github.com/arduino/ArduinoCore-zephyr/blob/main/libraries/Arduino_LED_Matrix/src/Arduino_LED_Matrix.h)
- [Pinned BMI088 v1.0.1 header](https://github.com/bolderflight/bmi088-arduino/blob/v1.0.1/src/BMI088.h)
- [ROS Jazzy timer period API](https://github.com/ros2/rclpy/blob/jazzy/rclpy/rclpy/timer.py)
- [Arduino MessagePack native array support](https://github.com/hideakitai/MsgPack/blob/master/MsgPack/Packer.h)
