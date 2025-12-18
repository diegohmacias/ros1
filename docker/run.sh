#!/bin/bash
# Allow X11 forwarding for GUI applications
xhost +local:docker 2>/dev/null

docker exec -it -w /ros_ws ros1_noetic bash -c "source /opt/ros/noetic/setup.bash && exec bash"