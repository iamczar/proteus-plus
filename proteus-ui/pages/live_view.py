import os
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import time
import altair as alt
import random
from common.utils import random_color
from common.utils import show_toast
from common.utils import render_toast_area
from common.utils import inject_button_theme
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService

st.set_page_config(page_title="Live View", layout="wide")
st.title("Live View")

MQTT_TOPIC = "sequence-commands"

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
table_titles = [
    "Oxygen Pressure",
    "PressureKi",
    "PressureKd",
    "PressureKp",
    "Temperature",
    "Pump Speed",
]


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
                .transform_filter("datum.index >= datum.max_index - 100")
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
                .transform_filter("datum.index >= datum.max_index - 100")
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
        st.session_state.live_i = 0
        st.session_state.live_last_values = [0.0 for _ in range(6)]
        st.session_state._live_init_key = init_key


if module_selected:
    _init_charts_if_needed()


@st.fragment(run_every=0.1)
def update_loop():
    # Reinitialize when module changes or after navigation reset
    _init_charts_if_needed()

    # Generate and add one new point per chart
    i = st.session_state.live_i
    last_values = st.session_state.live_last_values
    chart_elements = st.session_state.chart_elements_v2
    for chart_idx, chart in enumerate(chart_elements):
        if chart_idx == 0:
            new_y = float(np.sin(i * 0.1) + np.random.normal(0, 0.1))
        elif chart_idx == 1:
            new_y = float(np.cos(i * 0.15) + np.random.normal(0, 0.1))
        elif chart_idx == 2:
            new_y = float((i % 20) / 10 + np.random.normal(0, 0.1))
        elif chart_idx == 3:
            new_y = float((1 if (i // 10) % 2 == 0 else -1) + np.random.normal(0, 0.1))
        elif chart_idx == 4:
            new_y = float(20 + i * 0.01 + np.random.normal(0, 0.2))
        else:
            new_y = float(last_values[chart_idx] + np.random.normal(0, 0.3))
        last_values[chart_idx] = new_y
        try:
            chart.add_rows(pd.DataFrame({"x": [i], "y": [new_y]}))
        except Exception:
            # If chart refs became invalid (e.g., after navigation), reinitialize once
            _init_charts_if_needed(force=True)
            return

    st.session_state.live_i = i + 1


if module_selected:
    update_loop()
