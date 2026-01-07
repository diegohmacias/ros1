#!/usr/bin/env python3
"""
Time-Synchronized CSV Merger for ROS Bag Data - FIXED VERSION
Handles both feedbacks.X.velocity and device_number_X.velocity patterns

Usage:
    python3 merge_topics.py --input-dir /ros_ws/output/my_bag --topics cmd_vel odom motor_feedback
    
    Or interactively:
    python3 merge_topics.py
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from optparse import OptionParser
import sys

# ======================
# Default Configuration
# ======================
DEFAULT_INPUT_DIR = Path("/ros_ws/output")
DEFAULT_TOLERANCE_S = 0.05  # Time sync tolerance in seconds

# Signal mapping - maps logical names to column patterns
SIGNAL_MAPPINGS = {
    # cmd_vel topic
    'cmd_vel_linear_x': ['linear.x', 'twist.linear.x'],
    'cmd_vel_angular_z': ['angular.z', 'twist.angular.z'],
    
    # odom topic
    'odom_linear_x': ['twist.twist.linear.x', 'linear.x'],
    'odom_angular_z': ['twist.twist.angular.z', 'angular.z'],
    
    # motor feedback - UPDATED to handle both patterns
    'motor_37_velocity': ['device_number_37.velocity', 'feedbacks.0.velocity'],
    'motor_38_velocity': ['device_number_38.velocity', 'feedbacks.1.velocity'],
}


# ======================
# Terminal Colors
# ======================
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


# ======================
# Helper Functions
# ======================
def _to_seconds_since_start(series: pd.Series) -> pd.Series:
    """
    Convert timestamps to seconds since start.
    Handles:
      - float seconds (already relative or absolute epoch)
      - string datetime like 'YYYY/MM/DD/HH:MM:SS.ffffff'
    """
    # If already numeric
    if pd.api.types.is_numeric_dtype(series):
        base = float(series.iloc[0])
        return series.astype(float) - base

    # Try specific format first
    dt = pd.to_datetime(series, format="%Y/%m/%d/%H:%M:%S.%f", errors="coerce")
    if dt.notna().any():
        base = dt.iloc[0]
        return (dt - base).dt.total_seconds()

    # Fallback generic
    dt = pd.to_datetime(series, errors="coerce")
    if dt.notna().any():
        base = dt.iloc[0]
        return (dt - base).dt.total_seconds()

    # Last resort: numeric coercion
    coerced = pd.to_numeric(series, errors="coerce")
    return coerced - coerced.iloc[0]


def _find_col(df: pd.DataFrame, wants):
    """
    Find a column by suffix match among flattened/dotted headers.
    'wants' can be a list of candidate suffixes; returns the first match.
    """
    cols = list(df.columns)
    if isinstance(wants, str):
        wants = [wants]
    
    for w in wants:
        # Exact match
        if w in cols:
            return w
        # Suffix match with dot notation
        for c in cols:
            if c.endswith(w) or c.endswith("." + w) or c.replace(":", ".").endswith(w):
                return c
    return None


def _find_time_col(df: pd.DataFrame):
    """Find the time/timestamp column."""
    candidates = ["time", "timestamp", "stamp", "header.stamp", "secs"]
    return _find_col(df, candidates)


def _extract_motor_velocity_smart(df: pd.DataFrame, motor_num: int):
    """
    Smart extraction of motor velocity that handles multiple formats:
    1. Virtual column: device_number_X.velocity
    2. Flattened column: feedbacks.0.velocity or feedbacks.1.velocity
    3. Match by device_number to determine which feedback index
    
    Args:
        df: DataFrame containing motor feedback data
        motor_num: Motor device number (37 or 38)
        
    Returns:
        pd.Series with motor velocity values
    """
    # Try virtual column first (new bag_tool format)
    virtual_col = f"device_number_{motor_num}.velocity"
    if virtual_col in df.columns:
        series = pd.to_numeric(df[virtual_col], errors="coerce")
        # Check if it actually has data
        if series.notna().sum() > 0:
            return series
    
    # Fall back to feedbacks.X.velocity format
    # Need to determine which index (0 or 1) corresponds to motor_num
    device_0_col = _find_col(df, "feedbacks.0.device_number")
    device_1_col = _find_col(df, "feedbacks.1.device_number")
    
    if device_0_col and device_1_col:
        # Check first row to see which index corresponds to which motor
        device_0_val = df[device_0_col].iloc[0]
        device_1_val = df[device_1_col].iloc[0]
        
        if int(device_0_val) == motor_num:
            vel_col = _find_col(df, "feedbacks.0.velocity")
            if vel_col:
                return pd.to_numeric(df[vel_col], errors="coerce")
        elif int(device_1_val) == motor_num:
            vel_col = _find_col(df, "feedbacks.1.velocity")
            if vel_col:
                return pd.to_numeric(df[vel_col], errors="coerce")
    
    # Last resort: try direct column lookup
    for pattern in [f"feedbacks.0.velocity", f"feedbacks.1.velocity"]:
        col = _find_col(df, pattern)
        if col:
            # Can't verify this is the right motor, but return it anyway
            return pd.to_numeric(df[col], errors="coerce")
    
    # No data found
    n = len(df)
    return pd.Series([np.nan] * n)


def _load_topic_csv(csv_path: Path, signal_map: dict) -> pd.DataFrame:
    """
    Load a topic CSV and extract specified signals.
    
    Args:
        csv_path: Path to CSV file
        signal_map: Dict mapping output column names to list of candidate column patterns
        
    Returns:
        DataFrame with 't' (time) column and extracted signals
    """
    if not csv_path.exists():
        print_color(f"Warning: File not found: {csv_path}", Colors.WARNING)
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    
    # Find time column
    tcol = _find_time_col(df)
    if tcol is None:
        print_color(f"Error: No time column found in {csv_path.name}", Colors.FAIL)
        return pd.DataFrame()
    
    # Extract time
    result = {"t": _to_seconds_since_start(df[tcol])}
    
    # Extract each signal
    for sig_name, patterns in signal_map.items():
        # Special handling for motor velocities
        if 'motor_37' in sig_name or 'motor_38' in sig_name:
            motor_num = 37 if 'motor_37' in sig_name else 38
            result[sig_name] = _extract_motor_velocity_smart(df, motor_num)
        else:
            col = _find_col(df, patterns)
            if col:
                result[sig_name] = pd.to_numeric(df[col], errors="coerce")
            else:
                print_color(f"Warning: Signal '{sig_name}' not found in {csv_path.name}", Colors.WARNING)
                result[sig_name] = np.nan
    
    out_df = pd.DataFrame(result)
    return out_df.dropna(subset=["t"]).sort_values("t").reset_index(drop=True)


def _merge_dataframes(dfs: list, tol: float = DEFAULT_TOLERANCE_S) -> pd.DataFrame:
    """
    Merge multiple dataframes on time using nearest-neighbor synchronization.
    
    Args:
        dfs: List of DataFrames, each with 't' column
        tol: Time tolerance for matching (seconds)
        
    Returns:
        Merged DataFrame
    """
    if len(dfs) == 0:
        return pd.DataFrame()
    
    # Start with first dataframe
    merged = dfs[0].sort_values("t")
    
    # Merge remaining dataframes
    for df in dfs[1:]:
        if df.empty:
            continue
        merged = pd.merge_asof(
            merged.sort_values("t"),
            df.sort_values("t"),
            on="t",
            direction="nearest",
            tolerance=tol
        )
    
    # Rename 't' to 'timestamp'
    return merged.rename(columns={"t": "timestamp"})


def find_csv_files(input_dir: Path, topics: list) -> dict:
    """
    Find CSV files for requested topics in the input directory.
    
    Args:
        input_dir: Directory containing CSV files
        topics: List of topic names (e.g., ['cmd_vel', 'odom'])
        
    Returns:
        Dict mapping topic names to CSV file paths
    """
    csv_files = {}
    
    for topic in topics:
        # Look for files matching the topic name
        # Handle both /topic_name format and topic-name format
        pattern = topic.replace('/', '-').lstrip('-')
        
        candidates = list(input_dir.glob(f"*{pattern}*.csv"))
        
        if candidates:
            csv_files[topic] = candidates[0]
            print_color(f"Found {topic}: {candidates[0].name}", Colors.GREEN)
        else:
            print_color(f"Warning: No CSV found for topic '{topic}'", Colors.WARNING)
    
    return csv_files


def save_txt_format(df: pd.DataFrame, output_path: Path):
    """
    Save DataFrame in TXT format (Modelica-style array).
    Each row ends with ';' and is enclosed in brackets.
    """
    with open(output_path, "w") as f:
        f.write("[\n")
        for _, row in df.iterrows():
            def fmt(v):
                if isinstance(v, (float, np.floating)):
                    return f"{0.0:.6f}" if np.isnan(v) else f"{v:.6f}"
                return str(v)
            arr = ", ".join(fmt(row[c]) for c in df.columns)
            f.write("  " + arr + ";\n")
        f.write("]\n")


def interactive_mode():
    """Interactive mode for selecting files and topics."""
    from PyQt5 import QtWidgets
    
    print_color("=" * 60, Colors.HEADER)
    print_color("  Time-Synchronized CSV Merger", Colors.HEADER)
    print_color("=" * 60, Colors.HEADER)
    
    app = QtWidgets.QApplication(sys.argv)
    
    # Select input directory
    print_color("\nStep 1: Select trial folder containing CSV files...", Colors.CYAN)
    input_dir = QtWidgets.QFileDialog.getExistingDirectory(
        caption="Select Trial Folder (bag output directory)",
        directory=str(DEFAULT_INPUT_DIR)
    )
    
    if not input_dir:
        print_color("Error: No directory selected. Exiting.", Colors.FAIL)
        sys.exit(1)
    
    input_dir = Path(input_dir)
    print_color(f"Selected: {input_dir}", Colors.GREEN)
    
    # List available CSV files
    csv_files = list(input_dir.glob("*.csv"))
    if not csv_files:
        print_color("Error: No CSV files found in directory.", Colors.FAIL)
        sys.exit(1)
    
    print_color(f"\nFound {len(csv_files)} CSV file(s):", Colors.CYAN)
    for f in csv_files:
        print(f"  - {f.name}")
    
    # Let user select which CSVs to merge
    file_names = [f.name for f in csv_files]
    
    # Simple selection dialog
    selected_items = []
    for fname in file_names:
        reply = QtWidgets.QMessageBox.question(
            None,
            "Select Files to Merge",
            f"Include '{fname}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            selected_items.append(fname)
    
    if not selected_items:
        print_color("Error: No files selected.", Colors.FAIL)
        sys.exit(1)
    
    print_color(f"\nSelected {len(selected_items)} file(s) to merge:", Colors.GREEN)
    for item in selected_items:
        print(f"  - {item}")
    
    # Output will be saved in the same directory
    print_color(f"\nOutput will be saved to: {input_dir}", Colors.CYAN)
    
    return input_dir, selected_items, input_dir


def main():
    parser = OptionParser(usage="%prog [options]")
    parser.add_option("-i", "--input-dir", dest="input_dir",
                      help="Input directory containing CSV files (output will also be saved here)")
    parser.add_option("-o", "--output-dir", dest="output_dir",
                      help="Output directory for merged files (optional, defaults to input-dir)")
    parser.add_option("-t", "--topics", dest="topics",
                      action="append",
                      help="Topic CSV to include (e.g., cmd_vel, odom)")
    parser.add_option("--tolerance", dest="tolerance",
                      type="float", default=DEFAULT_TOLERANCE_S,
                      help=f"Time sync tolerance in seconds (default: {DEFAULT_TOLERANCE_S})")
    parser.add_option("-n", "--output-name", dest="output_name",
                      default="merged_data",
                      help="Output filename prefix (default: merged_data)")
    
    (options, args) = parser.parse_args()
    
    # Interactive mode if no arguments
    if not options.input_dir:
        input_dir, selected_files, output_dir = interactive_mode()
        
        # Load selected CSVs
        dfs = []
        for fname in selected_files:
            csv_path = input_dir / fname
            # Try to auto-detect signal types based on filename
            if 'cmd_vel' in fname.lower() or 'cmd-vel' in fname.lower():
                signals = {
                    'cmd_vel_linear_x': SIGNAL_MAPPINGS['cmd_vel_linear_x'],
                    'cmd_vel_angular_z': SIGNAL_MAPPINGS['cmd_vel_angular_z']
                }
            elif 'odom' in fname.lower():
                signals = {
                    'odom_linear_x': SIGNAL_MAPPINGS['odom_linear_x'],
                    'odom_angular_z': SIGNAL_MAPPINGS['odom_angular_z']
                }
            elif 'motor' in fname.lower() or 'feedback' in fname.lower():
                signals = {
                    'motor_37_velocity': SIGNAL_MAPPINGS['motor_37_velocity'],
                    'motor_38_velocity': SIGNAL_MAPPINGS['motor_38_velocity']
                }
            else:
                # Generic: load all numeric columns
                df_temp = pd.read_csv(csv_path)
                signals = {col: [col] for col in df_temp.columns if col.lower() != 'time'}
            
            df = _load_topic_csv(csv_path, signals)
            if not df.empty:
                dfs.append(df)
        
        output_name = "merged_data"
        tolerance = DEFAULT_TOLERANCE_S
        
    else:
        # CLI mode
        input_dir = Path(options.input_dir)
        
        # If output_dir not specified, use input_dir (save in same folder)
        if options.output_dir:
            output_dir = Path(options.output_dir)
        else:
            output_dir = input_dir
            print_color(f"Output directory not specified, using input directory: {output_dir}", Colors.CYAN)
        
        if not options.topics:
            print_color("Error: No topics specified. Use -t/--topics", Colors.FAIL)
            sys.exit(1)
        
        # Find CSV files for topics
        csv_files = find_csv_files(input_dir, options.topics)
        
        if not csv_files:
            print_color("Error: No CSV files found for specified topics.", Colors.FAIL)
            sys.exit(1)
        
        # Load each topic
        dfs = []
        for topic, csv_path in csv_files.items():
            # Determine signal mappings based on topic name
            if 'cmd_vel' in topic.lower() or 'cmd-vel' in topic.lower():
                signals = {
                    'cmd_vel_linear_x': SIGNAL_MAPPINGS['cmd_vel_linear_x'],
                    'cmd_vel_angular_z': SIGNAL_MAPPINGS['cmd_vel_angular_z']
                }
            elif 'odom' in topic.lower():
                signals = {
                    'odom_linear_x': SIGNAL_MAPPINGS['odom_linear_x'],
                    'odom_angular_z': SIGNAL_MAPPINGS['odom_angular_z']
                }
            elif 'motor' in topic.lower() or 'feedback' in topic.lower():
                signals = {
                    'motor_37_velocity': SIGNAL_MAPPINGS['motor_37_velocity'],
                    'motor_38_velocity': SIGNAL_MAPPINGS['motor_38_velocity']
                }
            else:
                print_color(f"Warning: Unknown topic type '{topic}', loading all columns", Colors.WARNING)
                df_temp = pd.read_csv(csv_path)
                signals = {col: [col] for col in df_temp.columns if col.lower() != 'time'}
            
            df = _load_topic_csv(csv_path, signals)
            if not df.empty:
                dfs.append(df)
        
        output_name = options.output_name
        tolerance = options.tolerance
    
    if not dfs:
        print_color("Error: No data loaded from CSV files.", Colors.FAIL)
        sys.exit(1)
    
    # Merge dataframes
    print_color(f"\nMerging {len(dfs)} dataframe(s) with tolerance={tolerance}s...", Colors.CYAN)
    merged = _merge_dataframes(dfs, tol=tolerance)
    
    if merged.empty:
        print_color("Error: Merged dataframe is empty.", Colors.FAIL)
        sys.exit(1)
    
    print_color(f"Merged data shape: {merged.shape}", Colors.GREEN)
    print_color(f"Columns: {list(merged.columns)}", Colors.CYAN)
    
    # Check for NaN values in motor columns
    if 'motor_37_velocity' in merged.columns:
        motor_37_valid = merged['motor_37_velocity'].notna().sum()
        motor_38_valid = merged['motor_38_velocity'].notna().sum()
        print_color(f"Motor 37 velocity: {motor_37_valid}/{len(merged)} valid values", 
                   Colors.GREEN if motor_37_valid > 0 else Colors.WARNING)
        print_color(f"Motor 38 velocity: {motor_38_valid}/{len(merged)} valid values", 
                   Colors.GREEN if motor_38_valid > 0 else Colors.WARNING)
    
    # Save outputs in the same directory as input
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_out = output_dir / f"{output_name}.csv"
    txt_out = output_dir / f"{output_name}.txt"
    
    merged.to_csv(csv_out, index=False)
    save_txt_format(merged, txt_out)
    
    print_color("\n" + "=" * 60, Colors.HEADER)
    print_color("  Merge Complete!", Colors.GREEN)
    print_color("=" * 60, Colors.HEADER)
    print_color(f"\nOutput saved to: {output_dir}", Colors.BOLD)
    print_color(f"  CSV: {csv_out.name}", Colors.CYAN)
    print_color(f"  TXT: {txt_out.name}", Colors.CYAN)
    print_color(f"\nData summary:", Colors.HEADER)
    print_color(f"  Rows: {len(merged)}", Colors.GREEN)
    print_color(f"  Columns: {len(merged.columns)}", Colors.GREEN)
    print_color(f"  Time range: {merged['timestamp'].min():.3f}s to {merged['timestamp'].max():.3f}s", Colors.GREEN)


if __name__ == "__main__":
    main()