#!/bin/bash

source /opt/ros/jazzy/setup.bash

echo "Available ROS 2 topics:"
ros2 topic list

echo
echo "Listening to /imu/data_raw and /imu/temperature..."
exec python3 /app/ros_listener.py
