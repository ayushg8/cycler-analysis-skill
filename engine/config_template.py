"""
config_template.py - Non-discoverable constants. RUNS / TESTS / DOE_GROUPS
are injected by pipeline.discover at runtime into analysis/config.py.
"""

# Extraction parameters
CYCLING_START_CYCLE  = 28
CYCLING_END_CYCLE    = 2500
CYCLING_INCREMENT    = 10
RPT_COUNTER_RESET    = 90
RPT_SKIP             = 36

DEFAULT_COLOR  = "#777777"
DEFAULT_MARKER = "o"

# Plot appearance
FONT_FAMILY      = "DejaVu Sans"
FONT_SIZE_AXIS   = 11
FONT_SIZE_LEGEND = 9
FONT_SIZE_TITLE  = 12
MARKER_SIZE      = 8
LINE_STYLE       = ":"
FIGURE_SIZE      = (10, 6)

# Output
PLOT_DPI    = 150
PLOT_FORMAT = "png"

# Cycle counting thresholds (peak CC/D current in Amps)
# C/20 ~3.5A, C/10 ~7A, C/2 ~35A -> all excluded (below 1C threshold)
# HPPC pulses excluded via explicit RPT cycle set in build_cycle_map
# 1C  ~70A discharge -> threshold 68A
# 2C ~140A discharge -> threshold 138A
CURRENT_1C_MIN = 68.0
CURRENT_2C_MIN = 138.0

# vCap settings
VCAP_START = 28
VCAP_STEP  = 50

# dQ/dV settings
DQDV_SMOOTH_WINDOW = 41
DQDV_SMOOTH_POLY   = 3
DQDV_GRID_POINTS   = 900
