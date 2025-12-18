#!/usr/bin/env python3
"""
PlotJuggler Launcher for ROS1 Bags

Usage:
    Launch PlotJuggler GUI:
        python3 plotjuggler_tool.py
    
    Launch with a specific bag file:
        python3 plotjuggler_tool.py --bag <bag_file>
    
    Launch with bag file selection GUI:
        python3 plotjuggler_tool.py --select
"""

import sys
import os
import subprocess
from optparse import OptionParser

# Default paths
BAGS_DIR = "/ros_ws/bags"


# =============================================================================
# Terminal Colors
# =============================================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_color(text, color=Colors.GREEN):
    print(f"{color}{text}{Colors.ENDC}")


def get_bag_path(bag_name):
    """Resolve bag file path."""
    if os.path.isabs(bag_name):
        return bag_name
    
    bag_path = os.path.join(BAGS_DIR, bag_name)
    
    if not bag_path.endswith('.bag'):
        bag_path += '.bag'
    
    return bag_path


def select_bag_file():
    """Open a GUI file picker to select a bag file."""
    from PyQt5 import QtWidgets
    
    app = QtWidgets.QApplication(sys.argv)
    
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        caption="Select ROS Bag File",
        directory=BAGS_DIR,
        filter="Bag Files (*.bag);;All Files (*)"
    )
    
    return file_path if file_path else None


def list_bags():
    """List available bag files in the bags directory."""
    if not os.path.exists(BAGS_DIR):
        print_color(f"Bags directory not found: {BAGS_DIR}", Colors.WARNING)
        return []
    
    bags = [f for f in os.listdir(BAGS_DIR) if f.endswith('.bag')]
    return sorted(bags)


def launch_plotjuggler(bag_file=None):
    """Launch PlotJuggler, optionally with a bag file."""
    print_color("=" * 50, Colors.HEADER)
    print_color("  PlotJuggler Launcher", Colors.HEADER)
    print_color("=" * 50, Colors.HEADER)
    
    # Build the command
    cmd = ["rosrun", "plotjuggler", "plotjuggler"]
    
    if bag_file:
        if not os.path.exists(bag_file):
            print_color(f"Error: Bag file not found: {bag_file}", Colors.FAIL)
            sys.exit(1)
        cmd.extend(["--data", bag_file])
        print_color(f"\nLoading bag file: {bag_file}", Colors.CYAN)
    
    print_color("\nStarting PlotJuggler...", Colors.GREEN)
    print_color("(Close PlotJuggler window to return to terminal)\n", Colors.WARNING)
    
    try:
        # Need to source ROS setup first
        full_cmd = f"source /opt/ros/noetic/setup.bash && {' '.join(cmd)}"
        subprocess.run(full_cmd, shell=True, executable='/bin/bash')
    except KeyboardInterrupt:
        print_color("\nPlotJuggler closed.", Colors.WARNING)
    except Exception as e:
        print_color(f"Error launching PlotJuggler: {e}", Colors.FAIL)
        sys.exit(1)


def main():
    parser = OptionParser(usage="%prog [options]")
    parser.add_option("-b", "--bag", dest="bag_file",
                      help="Bag file to load (name or full path)")
    parser.add_option("-s", "--select", dest="select",
                      action="store_true", default=False,
                      help="Open file picker to select a bag file")
    parser.add_option("-l", "--list", dest="list_bags",
                      action="store_true", default=False,
                      help="List available bag files")
    
    (options, args) = parser.parse_args()
    
    # List bags mode
    if options.list_bags:
        bags = list_bags()
        if bags:
            print_color(f"\nAvailable bag files in {BAGS_DIR}:", Colors.HEADER)
            print_color("-" * 50, Colors.CYAN)
            for bag in bags:
                print_color(f"  {bag}", Colors.GREEN)
        else:
            print_color("No bag files found.", Colors.WARNING)
        return
    
    # Select bag file with GUI
    if options.select:
        bag_file = select_bag_file()
        if bag_file:
            launch_plotjuggler(bag_file)
        else:
            print_color("No file selected.", Colors.WARNING)
        return
    
    # Load specific bag file
    if options.bag_file:
        bag_path = get_bag_path(options.bag_file)
        launch_plotjuggler(bag_path)
        return
    
    # Default: just launch PlotJuggler
    launch_plotjuggler()


if __name__ == '__main__':
    main()
