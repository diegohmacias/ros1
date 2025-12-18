# ROS1 Noetic Docker Environment

A Docker-based development environment for ROS1 Noetic with utilities for working with ROS bag files.

## Features

- 🐳 Dockerized ROS1 Noetic environment
- 📊 **PlotJuggler** for visualizing bag data
- 📁 **Bag to CSV** converter with PyQt5 GUI
- 🎨 Colored terminal with helpful aliases

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

# Or from a USB drive
cp /media/<username>/<drive_name>/*.bag /path/to/ros1/bags/
```

The `bags/` folder is mounted inside the container at `/ros_ws/bags/`.

> **Note:** Bag files are ignored by git (via `.gitignore`) to keep the repository lightweight.

## Utilities

### Bag to CSV Converter

Convert ROS bag topics to CSV files using a GUI or command line.

**Launch GUI (recommended):**
```bash
python3 /ros_ws/utils/bag_tool.py
```

**Command line usage:**
```bash
# List topics in a bag file
python3 /ros_ws/utils/bag_tool.py --bag <bag_file> --list-topics

# Export specific topics to CSV
python3 /ros_ws/utils/bag_tool.py --bag <bag_file> -t /topic1 -t /topic2
```

CSV files are saved to `/ros_ws/output/` (mapped to `output/` on your host).

### PlotJuggler

Visualize and analyze bag file data with PlotJuggler.

**Quick launch:**
```bash
plotjuggler
```

**Using the utility script:**
```bash
# Launch PlotJuggler
python3 /ros_ws/utils/plotjuggler_tool.py

# Launch with a specific bag file
python3 /ros_ws/utils/plotjuggler_tool.py --bag <bag_file>

# Open file picker to select a bag
python3 /ros_ws/utils/plotjuggler_tool.py --select

# List available bag files
python3 /ros_ws/utils/plotjuggler_tool.py --list
```

## Directory Structure

```
ros1/
├── bags/           # Place your .bag files here (gitignored)
├── output/         # CSV exports are saved here (gitignored)
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── build.sh    # Build the Docker image
│   ├── start.sh    # Start the container
│   └── run.sh      # Enter the container
├── utils/
│   ├── bag_tool.py         # Bag to CSV converter
│   └── plotjuggler_tool.py # PlotJuggler launcher
└── README.md
```

## Requirements

- Docker
- Docker Compose
- X11 (for GUI applications on Linux)

### X11 Forwarding (Linux)

The scripts automatically handle X11 forwarding. If you encounter display issues, run:

```bash
xhost +local:docker
```

## License

MIT

