# ROS1 Noetic Docker Environment

A Docker-based development environment for ROS1 Noetic with utilities for working with ROS bag files.

## Features

- 🐳 Dockerized ROS1 Noetic environment
- 📊 **PlotJuggler** for visualizing bag data
- 📁 **Bag to CSV** converter with PyQt5 GUI

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/ros1.git
cd ros1
```

### 2. Build the Docker Image

```bash
cd docker
./build.sh
```

### 3. Start the Container

```bash
./start.sh
```

### 4. Enter the Container

```bash
./run.sh
```

## Adding Bag Files

Place your ROS bag files (`.bag`) in the `bags/` directory:

```bash
# From your host machine
cp /path/to/your/file.bag /path/to/ros1/bags/
```

The `bags/` folder is mounted inside the container at `/ros_ws/bags/`.

## Utilities

### Bag to CSV Converter

Convert ROS bag topics to CSV files using a GUI or command line.

**Launch GUI:**
```bash
python3 /ros_ws/utils/bag_tool.py
```

CSV files are saved to `/ros_ws/output/` (mapped to `output/` on your host).

### PlotJuggler

Visualize and analyze bag file data with PlotJuggler.

**Quick launch:**
```bash
plotjuggler
```

