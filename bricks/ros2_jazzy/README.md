# ROS 2 Jazzy BMI088 Brick

The `ros2` service starts two Python processes automatically:

- `ros_sensor.py` polls STM32 `read_imu_fast` using compact numeric packets and publishes `/imu/data_raw`. A separate timer publishes `/imu/temperature` every two seconds.
- `ros_listener.py` logs received IMU measurements/rate once per second and shows temperature plus its age. A missing temperature message does not hide IMU output.

The BMI088 library and its physical units stay unchanged. The fast path avoids JSON text conversion; the console uses a separate cached numeric packet. Updated Python detects older sketches and can fall back to their JSON endpoint until the new sketch is deployed.

Tune rate, accelerometer range, gyroscope range and filtering in the sketch's single `IMU` configuration line. The publisher follows `rate_hz` from the sketch automatically; no Python or Compose rate setting is needed.

`run.py` supervises both processes and reloads them when mounted Python source changes. The read-only `./app:/app` mount avoids stale Python copied into cached Docker images. Deploy must apply the new Compose mount and command once; Dockerfile/dependency changes still require a rebuild.

Read the [project README](../../README.md) for first deployment, limitations, configuration and recovery behavior.
