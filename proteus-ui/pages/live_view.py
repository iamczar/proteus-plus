import os
import json
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import time
import altair as alt
from collections import deque
import random
from common.utils import random_color
from common.utils import show_toast
from common.utils import render_toast_area
from common.utils import inject_button_theme
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService

st.set_page_config(page_title="Live View", layout="wide")
st.title("Live View")

# Topics and history window
MQTT_TOPIC = "sequence-commands"
LIVE_TOPIC_PREFIX = "live-sensor-data"
MAX_POINTS = 8640  # show last ~2.4h at 1 Hz (adjust as needed)

# Disable interactivity for charts globally (keeps visuals the same)
st.markdown(
    """
    <style>
    /* Disable all pointer interactions on Vega-Lite charts */
    div[data-testid="stVegaLiteChart"],
    div[data-testid="stVegaLiteChart"] * {
        pointer-events: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Consistent button styling across the app
inject_button_theme(
    height="44px",
    min_width="190px",
    radius="12px",
    gap="12px",
)

# Unique token for this script run (used to safely rebuild charts after navigation)
st.session_state._current_run_token = f"run_{int(time.time()*1000)}_{random.randint(0, 1_000_000)}"

# Module selection
ModuleManager().select_module()

# Ensure persistent toast store exists early
if "_toasts" not in st.session_state:
    st.session_state._toasts = []

# Ensure state for experiment selection and logs
if "experiment_file_path" not in st.session_state:
    st.session_state.experiment_file_path = None
if "_show_experiment_dialog" not in st.session_state:
    st.session_state._show_experiment_dialog = False
if "system_logs" not in st.session_state:
    st.session_state["system_logs"] = []


def _append_system_log(message: str, level: str = "INFO") -> None:
    from datetime import datetime
    st.session_state["system_logs"].append(f"{datetime.now()} [{level}] - {message}")
    st.session_state["system_logs"] = st.session_state["system_logs"][-100:]


def _get_experiments_dir() -> Path:
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[2]
    return repo_root / "sequence_files"


# -------- Persistence helpers (file-backed history per module) --------
def _live_data_dir() -> Path:
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[2]
    d = repo_root / "proteus-ui" / "data" / "live"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _live_file_path(module_id: str) -> Path:
    return _live_data_dir() / f"module_{module_id}.jsonl"


def _append_live_record(module_id: str, x_value: int, data: dict) -> None:
    try:
        fp = _live_file_path(module_id)
        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"x": x_value, "data": data}) + "\n")
    except Exception:
        pass


def _load_live_records(module_id: str, max_points: int) -> list[dict]:
    fp = _live_file_path(module_id)
    if not fp.exists():
        return []
    try:
        with fp.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max_points:]
        out: list[dict] = []
        for ln in lines:
            try:
                obj = json.loads(ln.strip())
                if isinstance(obj, dict) and "x" in obj and isinstance(obj.get("data"), dict):
                    out.append(obj)
            except Exception:
                continue
        return out
    except Exception:
        return []


def _list_experiment_files() -> list[str]:
    base = _get_experiments_dir()
    try:
        if not base.exists() or not base.is_dir():
            return []
        return [name for name in os.listdir(base) if (base / name).is_file()]
    except Exception:
        return []


@st.dialog("Select Experiment File", width="large")
def _experiment_picker_dialog() -> None:
    base = _get_experiments_dir()
    files = _list_experiment_files()
    st.markdown(f"Select a file from `{str(base)}`")
    if not files:
        st.warning("No files found in the experiments folder.")
        if st.button("Close"):
            st.session_state._show_experiment_dialog = False
            st.rerun()
        return
    current_filename = None
    if st.session_state.experiment_file_path:
        try:
            current_filename = Path(st.session_state.experiment_file_path).name
        except Exception:
            current_filename = None
    selected = st.selectbox("Experiment file", options=files, index=(files.index(current_filename) if current_filename in files else 0))
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Cancel"):
            st.session_state._show_experiment_dialog = False
            show_toast("File selection canceled.", "info", source="New Experiment")
            _append_system_log("Toast [info]: File selection canceled.", level="INFO")
            st.rerun()
    with c2:
        if st.button("Select"):
            full_path = str((base / selected).resolve())
            st.session_state.experiment_file_path = full_path
            st.session_state._show_experiment_dialog = False
            show_toast(f"Selected experiment file: `{selected}`", "success", source="New Experiment")
            _append_system_log(f"Toast [success]: Selected experiment file -> {full_path}", level="INFO")
            st.rerun()


# Experiment controls (merged with required behavior)
@st.fragment
def experiment_controls():
    with st.container(border=True, key="experiment_controls_container_v2"):
        labels = [
            "New Experiment",
            "Start Experiment",
            "Stop Experiment",
            "Pause Experiment",
            "Resume Experiment",
            "Start Logging",
            "Stop Logging",
            "Retrieve Logs",
        ]

        for row_start in range(0, len(labels), 4):
            row_labels = labels[row_start:row_start + 4]
            cols = st.columns(len(row_labels), gap="small")
            for col, label in zip(cols, row_labels):
                with col:
                    if label == "New Experiment":
                        if st.button(label, key=f"btn_{label}"):
                            st.session_state._show_experiment_dialog = True
                            st.rerun()
                    elif label == "Start Experiment":
                        if st.button(label, key=f"btn_{label}"):
                            module_id = st.session_state.get("selected_module")
                            file_path = st.session_state.get("experiment_file_path")
                            if not file_path:
                                msg = "No experiment file selected."
                                show_toast(msg, "error", source="Start Experiment")
                                _append_system_log(f"Toast [error]: {msg}", level="ERROR")
                            elif not module_id:
                                msg = "No module selected."
                                show_toast(msg, "error", source="Start Experiment")
                                _append_system_log(f"Toast [error]: {msg}", level="ERROR")
                            else:
                                topic = f"{MQTT_TOPIC}/{module_id}"
                                try:
                                    MQTTService().publish(topic, file_path)
                                    msg = f"Sent MQTT to `{topic}` with file `{Path(file_path).name}`"
                                    show_toast(msg, "success", source="Start Experiment")
                                    _append_system_log(f"Toast [success]: {msg}", level="INFO")
                                except Exception as exc:
                                    msg = f"Failed to publish MQTT: {exc}"
                                    show_toast(msg, "error", source="Start Experiment")
                                    _append_system_log(f"Toast [error]: {msg}", level="ERROR")
                    else:
                        if st.button(label, key=f"btn_{label}"):
                            # Placeholder behaviors for other controls
                            result = random.choice(["success", "error", "warning", "info"]) 
                            message_map = {
                                "success": "Operation completed successfully!",
                                "error": "**Error**: Oops! Something went wrong. This event has been recorded in the logs.",
                                "warning": "**Warning**: Incomplete input. Please try again.",
                                "info": "Informational message.",
                            }
                            msg = message_map[result]
                            show_toast(msg, result, source=label)
                            _append_system_log(f"Toast [{result}]: {msg}", level=("ERROR" if result == "error" else "INFO"))


module_selected = bool(st.session_state.get("selected_module"))

if module_selected:
    experiment_controls()

    # Open dialog if requested by button click
    if st.session_state.get("_show_experiment_dialog"):
        _experiment_picker_dialog()
else:
    st.info("Select a module to view live controls and graphs.")

# Persistent toast area placeholder between controls and charts
toast_placeholder = st.empty()

# Immediate render (first paint)
render_toast_area(max_messages=3, container=toast_placeholder.container())

# Fragment to keep toasts fresh and expiring, independent of charts
@st.fragment(run_every=0.2)
def update_toasts():
    render_toast_area(max_messages=3, container=toast_placeholder.container())

# Invoke toast updater so it starts ticking immediately
update_toasts()


@st.cache_data
def get_colors(number: int) -> list:
    return [random_color() for _ in range(number)]


colors = get_colors(6)
# Charts map to fields from data_logger 'data' payload
METRICS = [
    ("Oxygen PID", "oxygen_pid"),
    ("Pressure PID", "pressure_pid"),
    ("Temperature (C)", "temp_measured"),
    ("Flow (SLPM)", "flow_measured"),
    ("Pressure Measured", "pressure_measured"),
    ("Circ Pump Speed", "circ_pump_speed"),
]
table_titles = [m[0] for m in METRICS]


def render_base_charts() -> list:
    chart_elements = []
    for row in range(3):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"{table_titles[row * 2]}")
            init_df = pd.DataFrame({"x": [], "y": []})
            base_chart = (
                alt.Chart(init_df)
                .mark_line(color=colors[row * 2])
                .encode(x=alt.X("x:Q", title=None), y=alt.Y("y:Q", title=None))
                .transform_window(index="row_number()", sort=[alt.SortField("x")])
                .transform_window(max_index="max(index)", frame=[None, None])
                .transform_filter(f"datum.index >= datum.max_index - {MAX_POINTS}")
            )
            chart_elements.append(st.altair_chart(base_chart, use_container_width=True))
        with col2:
            st.subheader(f"{table_titles[row * 2 + 1]}")
            init_df = pd.DataFrame({"x": [], "y": []})
            base_chart = (
                alt.Chart(init_df)
                .mark_line(color=colors[row * 2 + 1])
                .encode(x=alt.X("x:Q", title=None), y=alt.Y("y:Q", title=None))
                .transform_window(index="row_number()", sort=[alt.SortField("x")])
                .transform_window(max_index="max(index)", frame=[None, None])
                .transform_filter(f"datum.index >= datum.max_index - {MAX_POINTS}")
            )
            chart_elements.append(st.altair_chart(base_chart, use_container_width=True))
    return chart_elements


def _init_charts_if_needed(force: bool = False) -> None:
    current_module = st.session_state.get("selected_module")
    run_token = st.session_state.get("_current_run_token")
    init_key = ("live_v3", current_module, run_token)
    need_init = force or (st.session_state.get("_live_init_key") != init_key)
    need_init = need_init or ("chart_elements_v2" not in st.session_state)
    need_init = need_init or (len(st.session_state.get("chart_elements_v2", [])) != 6)
    if need_init:
        st.session_state.chart_elements_v2 = render_base_charts()
        # Initialize registries
        if "_live_buffers" not in st.session_state:
            st.session_state._live_buffers = {}
        mod = str(current_module) if current_module else ""
        # Painted counters per-module per-metric (how many points already rendered)
        if "_live_painted" not in st.session_state:
            st.session_state._live_painted = {}
        # X counters per-module (advance per received message)
        if "_live_x_counters" not in st.session_state:
            st.session_state._live_x_counters = {}
        # Set counters based on existing buffer length (so reselecting module restores history)
        buffers = st.session_state._live_buffers.get(mod) if mod else None
        pre_len = 0
        if buffers:
            try:
                pre_len = max((len(b) for b in buffers), default=0)
            except Exception:
                pre_len = 0
        st.session_state.live_i = pre_len
        st.session_state.live_last_values = [0.0 for _ in range(len(METRICS))]
        st.session_state._live_init_key = init_key
        # Subscribe to live topic for selected module
        if current_module:
            topic = f"{LIVE_TOPIC_PREFIX}/{current_module}"
            if st.session_state.get("_live_sub_topic") != topic:
                try:
                    MQTTService().subscribe(topic)
                    st.session_state._live_sub_topic = topic
                except Exception:
                    pass
        # If we have buffered history for this module, paint it
        has_points = False
        if buffers:
            try:
                has_points = any(len(b) > 0 for b in buffers)
            except Exception:
                has_points = False
        if has_points:
            charts = st.session_state.chart_elements_v2
            # Refill charts from buffers efficiently in chunks
            for idx, buf in enumerate(buffers):
                if not buf:
                    continue
                try:
                    df = pd.DataFrame({
                        "x": [pt[0] for pt in buf],
                        "y": [pt[1] for pt in buf],
                    })
                    charts[idx].add_rows(df)
                except Exception:
                    pass
            # Mark painted lengths
            st.session_state._live_painted[mod] = [len(b) for b in buffers]
        else:
            # If no in-memory buffer, try to hydrate from persisted file
            records = _load_live_records(mod, MAX_POINTS)
            if records:
                if not buffers:
                    st.session_state._live_buffers[mod] = [deque(maxlen=MAX_POINTS) for _ in range(len(METRICS))]
                    buffers = st.session_state._live_buffers[mod]
                charts = st.session_state.chart_elements_v2
                for rec in records:
                    x_val = int(rec.get("x", 0))
                    dct = rec.get("data", {})
                    for idx, (_, key) in enumerate(METRICS):
                        try:
                            y_val = float(dct.get(key, 0.0))
                        except Exception:
                            y_val = 0.0
                        buffers[idx].append((x_val, y_val))
                # Paint hydrated history
                for idx, buf in enumerate(buffers):
                    if not buf:
                        continue
                    try:
                        df = pd.DataFrame({
                            "x": [pt[0] for pt in buf],
                            "y": [pt[1] for pt in buf],
                        })
                        charts[idx].add_rows(df)
                    except Exception:
                        pass
                st.session_state._live_painted[mod] = [len(b) for b in buffers]
                # Advance x counter to end of file
                last_x = records[-1]["x"] if records else 0
                st.session_state._live_x_counters[mod] = int(last_x) + 1


if module_selected:
    _init_charts_if_needed()


@st.fragment(run_every=0.2)
def update_loop():
    # Reinitialize when module changes or after navigation reset
    _init_charts_if_needed()

    current_module = st.session_state.get("selected_module")
    if not current_module:
        return

    mod = str(current_module)
    buffers = st.session_state._live_buffers.get(mod)
    if not buffers:
        return
    chart_elements = st.session_state.chart_elements_v2
    painted = st.session_state._live_painted.get(mod, [0 for _ in range(len(METRICS))])
    for idx, buf in enumerate(buffers):
        try:
            start = painted[idx]
            if start >= len(buf):
                continue
            df = pd.DataFrame({
                "x": [pt[0] for pt in list(buf)[start:]],
                "y": [pt[1] for pt in list(buf)[start:]],
            })
            chart_elements[idx].add_rows(df)
            painted[idx] = len(buf)
        except Exception:
            pass
    st.session_state._live_painted[mod] = painted


# Background collector: subscribe to all module live topics and buffer data
@st.fragment(run_every=0.2)
def background_collector():
    modules = st.session_state.get("_available_modules", [])
    if not modules:
        return
    # Ensure subs set
    if "_live_all_subs" not in st.session_state:
        st.session_state._live_all_subs = set()
    subs = st.session_state._live_all_subs
    # Subscribe to all module live topics
    for m in modules:
        topic = f"{LIVE_TOPIC_PREFIX}/{m}"
        if topic not in subs:
            try:
                MQTTService().subscribe(topic)
                subs.add(topic)
            except Exception:
                pass
    # Drain each topic and append to per-module buffers
    for m in modules:
        topic = f"{LIVE_TOPIC_PREFIX}/{m}"
        updates = MQTTService().drain(topic, max_items=500)
        if not updates:
            continue
        mod = str(m)
        if "_live_buffers" not in st.session_state:
            st.session_state._live_buffers = {}
        if mod not in st.session_state._live_buffers:
            st.session_state._live_buffers[mod] = [deque(maxlen=MAX_POINTS) for _ in range(len(METRICS))]
        if "_live_x_counters" not in st.session_state:
            st.session_state._live_x_counters = {}
        x_counter = st.session_state._live_x_counters.get(mod, 0)
        buffers = st.session_state._live_buffers[mod]
        last_values = st.session_state.get("live_last_values", [0.0 for _ in range(len(METRICS))])
        for _, payload in updates:
            try:
                if not isinstance(payload, dict) or payload.get("message_source") != "data_logger":
                    continue
                data = payload.get("data") or {}
                if not isinstance(data, dict):
                    continue
                row_x = x_counter
                for idx, (_, key) in enumerate(METRICS):
                    val = data.get(key, last_values[idx])
                    try:
                        new_y = float(val)
                    except Exception:
                        new_y = float(last_values[idx])
                    buffers[idx].append((row_x, new_y))
                    last_values[idx] = new_y
                # Persist to disk for recovery after refresh
                _append_live_record(mod, row_x, data)
                x_counter += 1
            except Exception:
                continue
        st.session_state._live_x_counters[mod] = x_counter


# Kick off background collector
background_collector()


if module_selected:
    update_loop()
