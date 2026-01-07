#!/usr/bin/env python3
"""
ROS1 Bag to CSV Tool with PyQt5 GUI - FIXED VERSION
Properly populates virtual motor feedback columns

Usage:
    Launch GUI (default):
        python3 bag_tool.py
    
    Command line export:
        python3 bag_tool.py --bag <bag_file> --topics /topic1 /topic2
    
    List topics:
        python3 bag_tool.py --bag <bag_file> --list-topics
"""

import sys
import os
from datetime import datetime
from optparse import OptionParser

# Default paths
BAGS_DIR = "/ros_ws/bags"
OUTPUT_DIR = "/ros_ws/output"


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


# =============================================================================
# PyQt5 GUI Kit (based on SimplePyQtGUIKit from rosbag_to_csv)
# =============================================================================
class SimplePyQtGUIKit:
    @classmethod
    def GetFilePath(cls, caption="Open File", filefilter="", isApp=False, initial_dir=BAGS_DIR):
        """Open file dialog to select files."""
        from PyQt5 import QtWidgets
        
        if not isApp:
            app = QtWidgets.QApplication(sys.argv)
        
        files = QtWidgets.QFileDialog.getOpenFileNames(
            caption=caption, 
            filter=filefilter,
            directory=initial_dir
        )
        
        strlist = []
        for file in files:
            if type(file) == list:
                for f in file:
                    strlist.append(str(f))
            else:
                strlist.append(str(file))
        return strlist
    
    @classmethod
    def GetCheckButtonSelect(cls, selectList, title="Select", msg="", app=None):
        """
        Get selected check button options with a scrollable list.
        Returns dictionary: {'topic_name': True/False, ...}
        """
        from PyQt5 import QtCore, QtWidgets
        
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        win = QtWidgets.QWidget()
        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollAreaWidgetContents = QtWidgets.QWidget(scrollArea)
        scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 500, 400))
        scrollArea.setWidget(scrollAreaWidgetContents)
        
        layout = QtWidgets.QGridLayout()
        verticalLayoutScroll = QtWidgets.QVBoxLayout(scrollAreaWidgetContents)
        layoutIndex = 0
        
        if msg != "":
            label = QtWidgets.QLabel(msg)
            label.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(label, layoutIndex, 0)
            layoutIndex += 1
        
        checkboxs = []
        for select in selectList:
            checkbox = QtWidgets.QCheckBox(select)
            checkbox.setStyleSheet("font-size: 12px;")
            verticalLayoutScroll.addWidget(checkbox)
            layoutIndex += 1
            checkboxs.append(checkbox)
        
        layout.addWidget(scrollArea)
        
        # Select All / Deselect All buttons
        btnFrame = QtWidgets.QWidget()
        btnLayout = QtWidgets.QHBoxLayout(btnFrame)
        
        selectAllBtn = QtWidgets.QPushButton("Select All")
        selectAllBtn.clicked.connect(lambda: [cb.setChecked(True) for cb in checkboxs])
        btnLayout.addWidget(selectAllBtn)
        
        deselectAllBtn = QtWidgets.QPushButton("Deselect All")
        deselectAllBtn.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxs])
        btnLayout.addWidget(deselectAllBtn)
        
        layout.addWidget(btnFrame, layoutIndex, 0)
        layoutIndex += 1
        
        # OK button
        btn = QtWidgets.QPushButton("OK - Convert Selected Topics")
        btn.setStyleSheet("font-weight: bold; padding: 10px;")
        btn.clicked.connect(app.quit)
        layout.addWidget(btn, layoutIndex, 0)
        
        win.setLayout(layout)
        win.setWindowTitle(title)
        win.setMinimumSize(550, 500)
        win.show()
        app.exec_()
        
        result = {}
        for (checkbox, select) in zip(checkboxs, selectList):
            result[select] = checkbox.isChecked()
        
        return result


# =============================================================================
# Message Flattening and Motor Feedback Extraction
# =============================================================================
def _is_ros_msg(x):
    """Check if object is a ROS message."""
    return hasattr(x, "__slots__") and hasattr(x, "_slot_types")


def _flatten_msg(msg, parent="", out=None):
    """
    Recursively flatten a ROS message (or python builtin) to a dict of column->value.
    Arrays/lists get indexed: parent.0.field, parent.1.field, ...
    """
    if out is None:
        out = {}

    # Base cases
    if msg is None:
        out[parent] = ""
        return out

    # Primitive
    if isinstance(msg, (str, int, float, bool)):
        key = parent if parent else "value"
        out[key] = msg
        return out

    # Bytes
    if isinstance(msg, (bytes, bytearray)):
        key = parent if parent else "value"
        out[key] = msg.decode(errors="ignore")
        return out

    # Dict-like
    if isinstance(msg, dict):
        for k, v in msg.items():
            child = f"{parent}.{k}" if parent else str(k)
            _flatten_msg(v, child, out)
        return out

    # List / tuple
    if isinstance(msg, (list, tuple)):
        for i, v in enumerate(msg):
            child = f"{parent}.{i}" if parent else str(i)
            _flatten_msg(v, child, out)
        return out

    # ROS message
    if _is_ros_msg(msg):
        for slot in msg.__slots__:
            v = getattr(msg, slot)
            child = f"{parent}.{slot}" if parent else slot
            _flatten_msg(v, child, out)
        return out

    # Fallback
    key = parent if parent else "value"
    out[key] = str(msg)
    return out


def _extract_feedback_velocities(flat):
    """
    Look through flattened keys to build the two 'virtual' columns:
    - device_number_37.velocity
    - device_number_38.velocity
    
    Assumes messages contain an array field named 'feedbacks' where each item has
    'device_number' and 'velocity' fields.
    
    FIXED: Now properly extracts and returns velocity values, not just empty strings.
    """
    res = {
        "device_number_37.velocity": "",
        "device_number_38.velocity": "",
    }

    # Build a temporary map from idx -> {device_number: X, velocity: Y}
    buckets = {}
    for k, v in flat.items():
        if ".feedbacks." not in k and "feedbacks." not in k:
            continue
        try:
            # Handle both ".feedbacks." and "feedbacks." patterns
            if ".feedbacks." in k:
                after = k.split(".feedbacks.", 1)[1]
            else:
                after = k.split("feedbacks.", 1)[1]
            idx, rest = after.split(".", 1)
        except ValueError:
            # Scalar in feedbacks (unlikely), skip
            continue
        d = buckets.setdefault(idx, {})
        if rest.endswith("device_number"):
            try:
                d["device_number"] = int(v) if str(v).replace('-','').isdigit() else None
            except (ValueError, TypeError):
                d["device_number"] = None
        elif rest.endswith("velocity"):
            d["velocity"] = v

    # Map device numbers to their velocities
    for d in buckets.values():
        dn = d.get("device_number", None)
        vel = d.get("velocity", "")
        if dn == 37:
            res["device_number_37.velocity"] = vel
        elif dn == 38:
            res["device_number_38.velocity"] = vel

    return res


# =============================================================================
# CSV Conversion Functions (Updated with Motor Feedback Support)
# =============================================================================
def message_type_to_csv(stream, msg):
    """
    Write header row once, using flattened keys + virtual motor feedback columns.
    Returns the header order for subsequent rows.
    
    FIXED: Only adds virtual columns if feedback data is present in the message.
    """
    flat = _flatten_msg(msg)
    
    # Check if this message contains motor feedback data
    has_feedback = any("feedbacks" in k for k in flat.keys())
    
    cols = ["time"] + list(flat.keys())
    
    # Only add virtual columns if feedback data exists
    if has_feedback:
        virtual_cols = ["device_number_37.velocity", "device_number_38.velocity"]
        cols = cols + virtual_cols
    
    # De-duplicate while preserving order
    seen = set()
    ordered = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    
    stream.write(",".join(ordered) + "\n")
    return ordered


def message_to_csv(stream, msg, header_order):
    """
    Write a data row matching header_order produced by message_type_to_csv.
    Handles virtual motor feedback columns only when they're in the header.
    
    FIXED: Properly writes values from virtual columns, and only processes them if present.
    """
    flat = _flatten_msg(msg)
    
    # Only extract virtual columns if they're expected in the header
    has_virtual_cols = any("device_number_" in col and ".velocity" in col for col in header_order)
    if has_virtual_cols:
        virtual = _extract_feedback_velocities(flat)
    else:
        virtual = {}
    
    row = []
    for col in header_order:
        if col == "time":
            row.append("")  # Placeholder; timestamp already written by caller
        elif col in virtual:
            val = virtual.get(col, "")
            # Write the actual value, not empty string
            row.append(str(val) if val != "" and val is not None else "")
        else:
            row.append(str(flat.get(col, "")))
    
    # Skip first element (timestamp already written)
    stream.write("," + ",".join(row[1:]) + "\n")


def format_csv_filename(bag_name, topic_name, output_dir=OUTPUT_DIR):
    """Format the output CSV filename with bag-specific subdirectory."""
    safe_topic = topic_name.replace('/', '-')[1:]  # Remove leading slash and replace others
    filename = f"{safe_topic}.csv"
    # Create subdirectory named after the bag file
    bag_output_dir = os.path.join(output_dir, bag_name)
    os.makedirs(bag_output_dir, exist_ok=True)
    return os.path.join(bag_output_dir, filename)


def get_topic_list(bag_path):
    """Get list of topics from a bag file."""
    import rosbag
    bag = rosbag.Bag(bag_path)
    topics = list(bag.get_type_and_topic_info()[1].keys())
    bag.close()
    return topics


def get_topic_info(bag_path):
    """Get detailed topic info from a bag file."""
    import rosbag
    bag = rosbag.Bag(bag_path)
    info = bag.get_type_and_topic_info()[1]
    bag.close()
    return info


def bag_to_csv(bag_path, topic_names, output_dir=OUTPUT_DIR, include_header=True):
    """Convert selected topics from bag file to CSV files."""
    import rosbag
    
    os.makedirs(output_dir, exist_ok=True)
    bag_name = os.path.splitext(os.path.basename(bag_path))[0]
    
    try:
        bag = rosbag.Bag(bag_path)
        streamdict = {}       # topic -> open file handle
        header_orders = {}    # topic -> list of header columns
    except Exception as e:
        print_color(f"Failed to load bag file: {e}", Colors.FAIL)
        return []
    
    print_color(f"Loaded bag file: {bag_path}", Colors.CYAN)
    
    try:
        for topic, msg, time in bag.read_messages(topics=topic_names):
            # Open per-topic CSV on first encounter
            if topic in streamdict:
                stream = streamdict[topic]
            else:
                csv_path = format_csv_filename(bag_name, topic, output_dir)
                stream = open(csv_path, 'w')
                streamdict[topic] = stream
                print_color(f"  Creating: {os.path.basename(csv_path)}", Colors.GREEN)
                
                # Write header and store column order
                if include_header:
                    header_order = message_type_to_csv(stream, msg)
                    header_orders[topic] = header_order
            
            # Write timestamp
            timestamp = datetime.fromtimestamp(time.to_time()).strftime('%Y/%m/%d/%H:%M:%S.%f')
            stream.write(timestamp)
            
            # Write data row aligned to header order
            if include_header:
                message_to_csv(stream, msg, header_orders[topic])
            else:
                # Fallback to old behavior without header alignment
                flat = _flatten_msg(msg)
                stream.write("," + ",".join(str(v) for v in flat.values()) + "\n")
        
        # Close all streams
        for s in streamdict.values():
            s.close()
            
    except Exception as e:
        print_color(f"Error during conversion: {e}", Colors.FAIL)
    finally:
        bag.close()
    
    return list(streamdict.keys())


# =============================================================================
# CLI Functions
# =============================================================================
def get_bag_path(bag_name):
    """Resolve bag file path."""
    if os.path.isabs(bag_name):
        return bag_name
    
    bag_path = os.path.join(BAGS_DIR, bag_name)
    
    if not bag_path.endswith('.bag'):
        bag_path += '.bag'
    
    return bag_path


def list_topics_cli(bag_path):
    """List all topics in a bag file (CLI version)."""
    import rosbag
    try:
        bag = rosbag.Bag(bag_path)
        topics = bag.get_type_and_topic_info()[1]
        print_color(f"\nTopics in {os.path.basename(bag_path)}:", Colors.HEADER)
        print_color("-" * 50, Colors.CYAN)
        for topic in sorted(topics.keys()):
            info = topics[topic]
            print_color(f"  {topic}", Colors.GREEN)
            print(f"    Type: {info.msg_type}")
            print(f"    Messages: {info.message_count}")
        bag.close()
        return list(topics.keys())
    except Exception as e:
        print_color(f"Error reading bag file: {e}", Colors.FAIL)
        sys.exit(1)


# =============================================================================
# Main GUI Function
# =============================================================================
def main_gui():
    """Launch the GUI for bag to CSV conversion."""
    from PyQt5 import QtWidgets
    
    print_color("=" * 50, Colors.HEADER)
    print_color("  ROS Bag to CSV Converter", Colors.HEADER)
    print_color("=" * 50, Colors.HEADER)
    
    app = QtWidgets.QApplication(sys.argv)
    
    # Step 1: Select bag file(s)
    print_color("\nStep 1: Select bag file(s)...", Colors.CYAN)
    files = SimplePyQtGUIKit.GetFilePath(
        isApp=True,
        caption="Select ROS Bag File(s)",
        filefilter="Bag Files (*.bag);;All Files (*)",
        initial_dir=BAGS_DIR
    )
    
    if len(files) < 1 or files[0] == '':
        print_color("Error: No bag file selected. Exiting.", Colors.FAIL)
        sys.exit(1)
    
    print_color(f"Selected {len(files)} file(s):", Colors.GREEN)
    for f in files:
        if f:
            print(f"  - {f}")
    
    # Step 2: Get topics from first bag file
    print_color("\nStep 2: Loading topics...", Colors.CYAN)
    topics = get_topic_list(files[0])
    print_color(f"Found {len(topics)} topics", Colors.GREEN)
    
    # Step 3: Select topics to convert
    print_color("\nStep 3: Select topics to convert...", Colors.CYAN)
    selected = SimplePyQtGUIKit.GetCheckButtonSelect(
        topics,
        app=app,
        title="Select Topics",
        msg="Select topics to convert to CSV files:"
    )
    
    # Get selected topic names
    topic_names = [k for k, v in selected.items() if v]
    
    if len(topic_names) == 0:
        print_color("Error: No topics selected. Exiting.", Colors.FAIL)
        sys.exit(1)
    
    print_color(f"\nSelected {len(topic_names)} topic(s):", Colors.GREEN)
    for t in topic_names:
        print(f"  - {t}")
    
    # Step 4: Convert
    print_color(f"\nStep 4: Converting to CSV...", Colors.CYAN)
    print_color(f"Output directory: {OUTPUT_DIR}", Colors.CYAN)
    
    for bag_file in files:
        if not bag_file:
            continue
        print_color(f"\nProcessing: {os.path.basename(bag_file)}", Colors.HEADER)
        converted = bag_to_csv(bag_file, topic_names, OUTPUT_DIR)
        print_color(f"  Converted {len(converted)} topic(s)", Colors.GREEN)
    
    # Show completion message
    QtWidgets.QMessageBox.information(
        QtWidgets.QWidget(),
        "Conversion Complete",
        f"Successfully converted {len(topic_names)} topic(s) to CSV!\n\nOutput directory:\n{OUTPUT_DIR}"
    )
    
    print_color("\n" + "=" * 50, Colors.HEADER)
    print_color("  Conversion Complete!", Colors.GREEN)
    print_color("=" * 50, Colors.HEADER)
    print_color(f"\nCSV files saved to: {OUTPUT_DIR}", Colors.CYAN)


# =============================================================================
# Main Entry Point
# =============================================================================
def main():
    parser = OptionParser(usage="%prog [options]")
    parser.add_option("-b", "--bag", dest="bag_file",
                      help="Bag file path (launches GUI if not provided)")
    parser.add_option("-t", "--topic", dest="topic_names",
                      action="append",
                      help="Topic name to export (can be used multiple times)")
    parser.add_option("-l", "--list-topics", dest="list_topics",
                      action="store_true", default=False,
                      help="List all topics in the bag file")
    parser.add_option("-o", "--output", dest="output_dir",
                      default=OUTPUT_DIR,
                      help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_option("-n", "--no-header", dest="header",
                      action="store_false", default=True,
                      help="Don't include header row in CSV")
    
    (options, args) = parser.parse_args()
    
    # If no bag file specified, launch GUI
    if not options.bag_file:
        main_gui()
        return
    
    # CLI mode
    bag_path = get_bag_path(options.bag_file)
    
    if not os.path.exists(bag_path):
        print_color(f"Error: Bag file not found: {bag_path}", Colors.FAIL)
        sys.exit(1)
    
    # List topics mode
    if options.list_topics:
        list_topics_cli(bag_path)
        return
    
    # Export mode
    if not options.topic_names:
        print_color("Error: No topics specified. Use -t/--topic or -l/--list-topics", Colors.FAIL)
        print_color("Or run without arguments to launch the GUI", Colors.CYAN)
        sys.exit(1)
    
    print_color(f"\nConverting {len(options.topic_names)} topic(s) to CSV...", Colors.CYAN)
    converted = bag_to_csv(
        bag_path, 
        options.topic_names, 
        options.output_dir,
        include_header=options.header
    )
    
    print_color(f"\nConversion complete! {len(converted)} CSV file(s) created.", Colors.GREEN)
    print_color(f"Output directory: {options.output_dir}", Colors.CYAN)


if __name__ == '__main__':
    main()