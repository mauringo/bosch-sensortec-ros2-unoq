FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-jazzy-sensor-msgs \
    python3-msgpack \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip3 install \
    --no-cache-dir \
    --break-system-packages \
    -r requirements.txt

COPY app/ /app/

RUN chmod +x /app/check_ros.sh

ENV ROS_DOMAIN_ID=0
ENV PYTHONUNBUFFERED=1

CMD ["/bin/bash", "-c", \
     "source /opt/ros/jazzy/setup.bash && exec python3 -u /app/run.py"]
