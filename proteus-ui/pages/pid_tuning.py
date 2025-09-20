import json
import time
from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt

from common.utils import inject_button_theme
from common.utils import show_toast
from common.utils import render_toast_area
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService
from datetime import datetime
from collections import deque


st.set_page_config(page_title="PID Tuning", layout="wide")
st.title("PID Tuning")

# Consistent button styling (compact)
inject_button_theme(height="32px", min_width="110px", font_size="14px", padding_x="10px")


# -----------------------------
# Page-local state
# -----------------------------
if "pt_selected_module" not in st.session_state:
    st.session_state.pt_selected_module = None

# Flow PID values
defaults_flow = {"desired_oxygen": 2000.0, "kp": 0.1, "ki": 1.0, "kd": 3.0}
defaults_pressure = {"desired_pressure": 2.0, "kp": 0.1, "ki": 1.0, "kd": 3.0}

for k, v in defaults_flow.items():
    st.session_state.setdefault(f"pt_flow_{k}", v)
for k, v in defaults_pressure.items():
    st.session_state.setdefault(f"pt_pressure_{k}", v)

st.session_state.setdefault("pt_pressure_enabled", False)
st.session_state.setdefault("pt_flow_enabled", False)
st.session_state.setdefault("pt_running", False)
st.session_state.setdefault("pt_flow_status", {})
st.session_state.setdefault("pt_pressure_status", {})
st.session_state.setdefault("_pt_pid_ack_seen", False)

# Data buffers for demo charts (simple ring buffers)
st.session_state.setdefault("pt_data", {
    "t": [],
    "ox_desired": [],
    "ox_meas1": [],
    "ox_meas2": [],
    "ox_meas3": [],
    "flow_desired": [],
    "flow_actual": [],
    "press_pump_desired": [],
    "press_pump_actual": [],
    "pressure_desired": [],
    "pressure_actual": [],
})
st.session_state.setdefault("_pt_live_buffers", None)
st.session_state.setdefault("_pt_live_painted", 0)
st.session_state.setdefault("_pt_live_sub_topic", None)

# Live data topic and window
LIVE_TOPIC_PREFIX = "live-sensor-data"
MAX_POINTS = 18000  # ~5 hours @ 1 Hz


# -----------------------------
# Helpers
# -----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
PID_CONFIG_DIR = BASE_DIR / "data" / "pid_configs"
PID_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _status_chip(label: str, active: bool) -> None:
    bg = "#10B981" if active else "#F59E0B"
    txt = "white" if active else "#111827"
    st.markdown(
        f"""
        <div style='text-align:center;padding:10px;border-radius:8px;background:{bg};color:{txt};font-weight:800;'>
            {label}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _save_config(kind: str) -> None:
    ts = time.strftime("%Y%m%d-%H%M%S")
    if kind == "flow":
        payload = {
            "kind": "flow",
            "desired_oxygen": float(st.session_state.pt_flow_desired_oxygen),
            "kp": float(st.session_state.pt_flow_kp),
            "ki": float(st.session_state.pt_flow_ki),
            "kd": float(st.session_state.pt_flow_kd),
        }
    else:
        payload = {
            "kind": "pressure",
            "desired_pressure": float(st.session_state.pt_pressure_desired_pressure),
            "kp": float(st.session_state.pt_pressure_kp),
            "ki": float(st.session_state.pt_pressure_ki),
            "kd": float(st.session_state.pt_pressure_kd),
        }
    fname = PID_CONFIG_DIR / f"{kind}_pid_{ts}.json"
    fname.write_text(json.dumps(payload, indent=2))
    show_toast(f"Saved {kind} PID config to {fname.name}", "success", source="PID Tuning")


def _load_config(kind: str, filename: str | None) -> None:
    if not filename:
        show_toast("Select a config file to load.", "warning", source="PID Tuning")
        return
    path = PID_CONFIG_DIR / filename
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        show_toast(f"Failed to load: {exc}", "error", source="PID Tuning")
        return
    if kind == "flow" and data.get("kind") in (None, "flow"):
        st.session_state.pt_flow_desired_oxygen = float(data.get("desired_oxygen", defaults_flow["desired_oxygen"]))
        st.session_state.pt_flow_kp = float(data.get("kp", defaults_flow["kp"]))
        st.session_state.pt_flow_ki = float(data.get("ki", defaults_flow["ki"]))
        st.session_state.pt_flow_kd = float(data.get("kd", defaults_flow["kd"]))
        show_toast("Flow PID config loaded.", "success", source="PID Tuning")
    elif kind == "pressure" and data.get("kind") in (None, "pressure"):
        st.session_state.pt_pressure_desired_pressure = float(data.get("desired_pressure", defaults_pressure["desired_pressure"]))
        st.session_state.pt_pressure_kp = float(data.get("kp", defaults_pressure["kp"]))
        st.session_state.pt_pressure_ki = float(data.get("ki", defaults_pressure["ki"]))
        st.session_state.pt_pressure_kd = float(data.get("kd", defaults_pressure["kd"]))
        show_toast("Pressure PID config loaded.", "success", source="PID Tuning")
    else:
        show_toast("Config kind does not match.", "error", source="PID Tuning")


def _publish_pid_command(module_id: str | int, payload: dict) -> bool:
    try:
        topic = f"pid-commands/{module_id}"
        envelope = {
            "message_source": "proteus-ui",
            "timestamp": datetime.now().isoformat(),
            "message": payload,
        }
        MQTTService().publish(topic, envelope)
        return True
    except Exception as exc:
        show_toast(f"Publish failed: {exc}", "error", source="PID Tuning")
        return False


def _append_live_point(payload: dict) -> None:
    try:
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            return
        # Timestamp
        ts = payload.get("timestamp")
        try:
            t_epoch = int(time.time()) if ts is None else int(pd.to_datetime(ts).timestamp())
        except Exception:
            t_epoch = int(time.time())
        buf = st.session_state.pt_data
        buf["t"].append(t_epoch)
        # Series values from live data
        buf["ox_desired"].append(float(data.get("oxygen_setpoint", 0.0)))
        buf["ox_meas1"].append(float(data.get("oxygen_measured_1", 0.0)))
        buf["ox_meas2"].append(float(data.get("oxygen_measured_2", 0.0)))
        buf["ox_meas3"].append(float(data.get("oxygen_measured_3", 0.0)))
        buf["flow_desired"].append(float(data.get("circ_flow_speed_desired", 0.0)))
        buf["flow_actual"].append(float(data.get("flow_measured", 0.0)))
        buf["press_pump_desired"].append(float(data.get("pressure_flow_speed_desired", 0.0)))
        buf["press_pump_actual"].append(float(data.get("pressure_pump_speed", 0.0)))
        buf["pressure_desired"].append(float(data.get("pressure_setpoint", 0.0)))
        buf["pressure_actual"].append(float(data.get("pressure_measured", 0.0)))
        # Ring buffer trim
        N = MAX_POINTS
        for k in list(buf.keys()):
            if len(buf[k]) > N:
                buf[k] = buf[k][-N:]
    except Exception:
        pass


# --- Background collector and painter, mirroring live_view ---
@st.fragment(run_every=0.5)
def _pt_background_collector():
    mod = st.session_state.get("pt_selected_module")
    if not mod:
        return
    topic = f"{LIVE_TOPIC_PREFIX}/{mod}"
    # Subscribe once per module selection
    if st.session_state.get("_pt_live_sub_topic") != topic:
        try:
            MQTTService().subscribe(topic)
            st.session_state._pt_live_sub_topic = topic
        except Exception:
            return
        # Reset buffers and painted counter on module change
        st.session_state._pt_live_painted = 0

    updates = MQTTService().drain(topic, max_items=500)
    if not updates:
        return
    for _, payload in updates:
        try:
            if isinstance(payload, dict) and payload.get("alpha_command") == "sensor_data":
                _append_live_point(payload)
        except Exception:
            continue


# Start background collector
_pt_background_collector()

# -----------------------------
# First block: Module selection + Toasts
# -----------------------------
modules = ModuleManager().get_available_modules() or []
with st.container(border=True):
    if not modules:
        st.info("No modules detected.")
    else:
        placeholder_label = "— Select a module —"
        previous_value = st.session_state.get("pt_selected_module")
        if previous_value is not None and previous_value not in modules:
            try:
                del st.session_state["pt_selected_module"]
            except Exception:
                pass
            previous_value = None

        if previous_value is None:
            chosen = st.selectbox(
                label="Module Selection (local):",
                options=[placeholder_label] + modules,
                index=0,
                key="_pt_module_select_first",
            )
        else:
            chosen = st.selectbox(
                label="Module Selection (local):",
                options=modules,
                index=(modules.index(previous_value) if previous_value in modules else 0),
                key="_pt_module_select_final",
            )

        if chosen != placeholder_label and chosen != previous_value:
            st.session_state.pt_selected_module = chosen
            # Reset chart state and buffers on module change
            try:
                st.session_state.pt_chart_elements = []
                st.session_state.pt_painted_len = 0
                st.session_state.pt_data = {
                    "t": [],
                    "ox_desired": [],
                    "ox_meas1": [],
                    "ox_meas2": [],
                    "ox_meas3": [],
                    "flow_desired": [],
                    "flow_actual": [],
                    "press_pump_desired": [],
                    "press_pump_actual": [],
                    "pressure_desired": [],
                    "pressure_actual": [],
                }
            except Exception:
                pass
            show_toast(f"Selected module: **{chosen}**", "success", source="Module Selection (local)")
            st.rerun()

# Toasts area
toast_placeholder = st.empty()
render_toast_area(container=toast_placeholder.container())

@st.fragment(run_every=0.6)
def _refresh_toasts():
    render_toast_area(container=toast_placeholder.container())

_refresh_toasts()


# PID status subscription and polling
@st.fragment(run_every=1.0)
def _pid_status_tick():
    mod = st.session_state.get("pt_selected_module")
    if not mod:
        return
    try:
        t_flow = f"pid-flow-status/{mod}"
        t_press = f"pid-pressure-status/{mod}"
        t_am = f"alphacommsmanager-status/{mod}"
        MQTTService().subscribe(t_flow)
        MQTTService().subscribe(t_press)
        MQTTService().subscribe(t_am)
        # Drain and keep only the latest
        for _, payload in MQTTService().drain(t_flow, max_items=100):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "flow":
                    st.session_state.pt_flow_status = inner
            except Exception:
                pass
        for _, payload in MQTTService().drain(t_press, max_items=100):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "pressure":
                    st.session_state.pt_pressure_status = inner
            except Exception:
                pass
        # Alpha acks for PID
        for _, payload in MQTTService().drain(t_am, max_items=50):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                cmd = str(inner.get("command", "")).lower() if isinstance(inner, dict) else ""
                status = str(inner.get("status", "")).lower() if isinstance(inner, dict) else ""
                if cmd == "pid_cmd" and status in ("ack", "acknowledged", "received"):
                    show_toast("PID command acknowledged by Alpha.", "success", source="PID Tuning")
            except Exception:
                pass
    except Exception:
        pass

_pid_status_tick()

def _refresh_pid_status_once(module_id: str | int) -> None:
    try:
        t_flow = f"pid-flow-status/{module_id}"
        t_press = f"pid-pressure-status/{module_id}"
        MQTTService().subscribe(t_flow)
        MQTTService().subscribe(t_press)
        updated = False
        for _, payload in MQTTService().drain(t_flow, max_items=100):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "flow":
                    if inner != (st.session_state.get("pt_flow_status") or {}):
                        st.session_state.pt_flow_status = inner
                        updated = True
            except Exception:
                pass
        for _, payload in MQTTService().drain(t_press, max_items=100):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "pressure":
                    if inner != (st.session_state.get("pt_pressure_status") or {}):
                        st.session_state.pt_pressure_status = inner
                        updated = True
            except Exception:
                pass
        # No explicit rerun; Streamlit will rerun after button click automatically
    except Exception:
        pass


# -----------------------------
# Second + Third blocks: Gains + PID controls
# -----------------------------
mod_for_panels = st.session_state.get("pt_selected_module")
if not mod_for_panels:
    st.info("Select a module to enable PID controls and PID status panels.")
else:
    left, right = st.columns([2.0, 1.1], gap="small")

    with left:
        gains_cols = st.columns([1, 1], gap="small")

        # Flow Controller Gains window
        with gains_cols[0]:
            with st.container(border=True):
                st.subheader("Flow Control Gains")
                st.number_input("Desired Oxygen : micromole/liter", key="pt_flow_desired_oxygen")
                st.number_input("Proportional Gain", key="pt_flow_kp")
                st.number_input("Integral Gain", key="pt_flow_ki")
                st.number_input("Derivative Gain", key="pt_flow_kd")
                if st.button("Send", key="pt_flow_send"):
                    mod = st.session_state.get("pt_selected_module")
                    payload = {
                        "type": "flow_pid",
                        "desired_oxygen": float(st.session_state.pt_flow_desired_oxygen),
                        "kp": float(st.session_state.pt_flow_kp),
                        "ki": float(st.session_state.pt_flow_ki),
                        "kd": float(st.session_state.pt_flow_kd),
                    }
                    ok = _publish_pid_command(mod, payload)
                    if ok:
                        show_toast(
                            f"Flow PID sent to {mod}",
                            "success",
                            source="Flow Control Gains",
                        )

        # Pressure Controller Gains window
        with gains_cols[1]:
            with st.container(border=True):
                st.subheader("Pressure Controller Gains")
                st.number_input("Desired Pressure : psi", key="pt_pressure_desired_pressure")
                st.number_input("Proportional Gain", key="pt_pressure_kp")
                st.number_input("Integral Gain", key="pt_pressure_ki")
                st.number_input("Derivative Gain", key="pt_pressure_kd")
                if st.button("Send", key="pt_pressure_send"):
                    mod = st.session_state.get("pt_selected_module")
                    payload = {
                        "type": "pressure_pid",
                        "desired_pressure": float(st.session_state.pt_pressure_desired_pressure),
                        "kp": float(st.session_state.pt_pressure_kp),
                        "ki": float(st.session_state.pt_pressure_ki),
                        "kd": float(st.session_state.pt_pressure_kd),
                    }
                    ok = _publish_pid_command(mod, payload)
                    if ok:
                        show_toast(
                            f"Pressure PID sent to {mod}",
                            "success",
                            source="Pressure Controller Gains",
                        )

    with right:
        with st.container(border=True):
            c1, c2 = st.columns([1, 1], gap="small")

            # Flow PID column (left)
            with c1:
                s = st.session_state.get("pt_flow_status") or {}
                flow_enabled = bool(s.get("pid_enabled", False))
                _status_chip(
                    f"Flow PID {'Active' if flow_enabled else 'Inactive'}",
                    flow_enabled,
                )
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button("Get PID Values", key="pt_refresh_flow_status"):
                    mod = st.session_state.get("pt_selected_module")
                    if mod:
                        _refresh_pid_status_once(mod)
                # Toggle button reflects live state and always sends the inverse
                toggle_label = "Disable PID" if flow_enabled else "Enable PID"
                if st.button(toggle_label, key="pt_toggle_flow_pid"):
                    mod = st.session_state.get("pt_selected_module")
                    target = not flow_enabled
                    ok = _publish_pid_command(mod, {"type": "flow_pid_enable", "enabled": target})
                    if ok:
                        show_toast(
                            ("Flow PID enabled" if target else "Flow PID disabled"),
                            ("success" if target else "warning"),
                            source="PID Tuning",
                        )
                        # Do not force rerun; rely on next heartbeat to refresh chip

                # Live flow PID status panel
                try:
                    s = st.session_state.get("pt_flow_status") or {}
                    with st.container(border=True):
                        st.caption("Current Flow PID Status")
                        st.markdown(f"Desired O2: {float(s.get('desired_oxygen', 0.0)):.2f}")
                        st.markdown(f"Kp: {float(s.get('kp', 0.0)):.3f}")
                        st.markdown(f"Ki: {float(s.get('ki', 0.0)):.3f}")
                        st.markdown(f"Kd: {float(s.get('kd', 0.0)):.3f}")
                        st.markdown(f"Mode: {str(s.get('mode', '—'))}")
                        st.markdown(f"Enabled: {bool(s.get('pid_enabled', False))}")
                except Exception:
                    pass

            # Pressure PID column (right)
            with c2:
                s2 = st.session_state.get("pt_pressure_status") or {}
                pressure_enabled = bool(s2.get("pid_enabled", False))
                _status_chip(
                    f"Pressure PID {'Active' if pressure_enabled else 'Inactive'}",
                    pressure_enabled,
                )
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button("Get PID Values", key="pt_refresh_pressure_status"):
                    mod = st.session_state.get("pt_selected_module")
                    if mod:
                        _refresh_pid_status_once(mod)
                # Toggle button reflects live state and always sends the inverse
                toggle_label2 = "Disable PID" if pressure_enabled else "Enable PID"
                if st.button(toggle_label2, key="pt_toggle_pressure_pid"):
                    mod = st.session_state.get("pt_selected_module")
                    target = not pressure_enabled
                    ok = _publish_pid_command(mod, {"type": "pressure_pid_enable", "enabled": target})
                    if ok:
                        show_toast(
                            ("Pressure PID enabled" if target else "Pressure PID disabled"),
                            ("success" if target else "warning"),
                            source="PID Tuning",
                        )
                        # Do not force rerun; rely on next heartbeat

                # Live pressure PID status panel
                try:
                    with st.container(border=True):
                        st.caption("Current Pressure PID Status")
                        st.markdown(f"Desired Pressure: {float(s2.get('desired_pressure', 0.0)):.2f}")
                        st.markdown(f"Kp: {float(s2.get('kp', 0.0)):.3f}")
                        st.markdown(f"Ki: {float(s2.get('ki', 0.0)):.3f}")
                        st.markdown(f"Kd: {float(s2.get('kd', 0.0)):.3f}")
                        st.markdown(f"Mode: {str(s2.get('mode', '—'))}")
                        st.markdown(f"Enabled: {bool(s2.get('pid_enabled', False))}")
                except Exception:
                    pass

        # Removed Run/Stop and Save/Load UI for streamlined PID control


# -----------------------------
# Fourth block: Graphs
# -----------------------------
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# Match Live View: disable interaction on Vega-Lite charts
st.markdown(
    """
    <style>
    div[data-testid="stVegaLiteChart"],
    div[data-testid="stVegaLiteChart"] * { pointer-events: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)



def _base_single_series_chart(color: str) -> alt.Chart:
    init_df = pd.DataFrame({"x": [], "y": []})
    return (
        alt.Chart(init_df)
        .mark_line(color=color)
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
        )
        .transform_window(index="row_number()", sort=[alt.SortField("x")])
        .transform_window(max_index="max(index)", frame=[None, None])
        .transform_filter(f"datum.index >= datum.max_index - {MAX_POINTS}")
    )


def _base_multi_series_chart() -> alt.Chart:
    init_df = pd.DataFrame({"x": [], "series": [], "y": []})
    return (
        alt.Chart(init_df)
        .mark_line()
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("series:N", legend=alt.Legend(title=None)),
        )
        .transform_window(index="row_number()", sort=[alt.SortField("x")])
        .transform_window(max_index="max(index)", frame=[None, None])
        .transform_filter(f"datum.index >= datum.max_index - {MAX_POINTS}")
    )


# Initialize chart containers once and keep updating (Altair)
def _init_pid_charts_altair() -> None:
    if "pt_chart_elements" in st.session_state and len(st.session_state.pt_chart_elements) == 4:
        return
    elements = []

    # Row 1
    c1, c2 = st.columns([1, 1], gap="small")
    with c1:
        with st.container(border=True):
            st.subheader("Desired Oxygen + 3 Measured Oxygen vs Time")
            chart = _base_multi_series_chart()
            elements.append(st.altair_chart(chart, use_container_width=True))
    with c2:
        with st.container(border=True):
            st.subheader("Desired Speed of Flow Pump vs actual flow rate vs Time")
            chart = _base_multi_series_chart()
            elements.append(st.altair_chart(chart, use_container_width=True))

    # Row 2
    c3, c4 = st.columns([1, 1], gap="small")
    with c3:
        with st.container(border=True):
            st.subheader("Desired Speed of Pressure Pump vs actual speed flow rate vs Time")
            chart = _base_multi_series_chart()
            elements.append(st.altair_chart(chart, use_container_width=True))
    with c4:
        with st.container(border=True):
            st.subheader("Desired Pressure vs Actual Pressure  Time")
            chart = _base_multi_series_chart()
            elements.append(st.altair_chart(chart, use_container_width=True))

    st.session_state.pt_chart_elements = elements
    st.session_state.pt_painted_len = 0


if st.session_state.get("pt_selected_module"):
    _init_pid_charts_altair()


@st.fragment(run_every=1.0)
def _update_charts_stream():
    # Only render when a module is selected
    if not st.session_state.get("pt_selected_module"):
        return
    # Just paint whatever is accumulated by the background collector
    data = st.session_state.pt_data
    charts = st.session_state.get("pt_chart_elements", [])
    if len(charts) != 4:
        return

    start = int(st.session_state.get("pt_painted_len", 0))
    end = len(data.get("t", []))
    if end <= start:
        return
    for i in range(start, end):
        ts = pd.to_datetime(int(data["t"][i]), unit="s")
        # Chart 1: Oxygen desired + 3 measured (long format)
        df1 = pd.DataFrame(
            [
                {"x": ts, "series": "Desired", "y": data["ox_desired"][i]},
                {"x": ts, "series": "Measured A", "y": data["ox_meas1"][i]},
                {"x": ts, "series": "Measured B", "y": data["ox_meas2"][i]},
                {"x": ts, "series": "Measured C", "y": data["ox_meas3"][i]},
            ]
        )
        charts[0].add_rows(df1)

        # Chart 2: Flow pump desired vs actual (multi-series)
        df2 = pd.DataFrame(
            [
                {"x": ts, "series": "Desired", "y": data["flow_desired"][i]},
                {"x": ts, "series": "Actual", "y": data["flow_actual"][i]},
            ]
        )
        charts[1].add_rows(df2)

        # Chart 3: Desired Speed of Pressure Pump vs actual flow rate (multi-series)
        df3 = pd.DataFrame(
            [
                {"x": ts, "series": "Desired", "y": data["press_pump_desired"][i]},
                {"x": ts, "series": "Actual", "y": data["flow_actual"][i]},
            ]
        )
        charts[2].add_rows(df3)

        # Chart 4: Pressure desired vs actual (multi-series)
        df4 = pd.DataFrame(
            [
                {"x": ts, "series": "Desired", "y": data["pressure_desired"][i]},
                {"x": ts, "series": "Actual", "y": data["pressure_actual"][i]},
            ]
        )
        charts[3].add_rows(df4)

    st.session_state.pt_painted_len = end


_update_charts_stream()


