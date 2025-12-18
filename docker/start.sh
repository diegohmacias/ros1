#!/bin/bash
# Start the ROS1 container with X11 forwarding for GUI applications

# Allow X11 forwarding
xhost +local:docker 2>/dev/null

# Start container in detached mode
docker compose up -d

echo "Container started! Use ./run.sh to enter the container."
