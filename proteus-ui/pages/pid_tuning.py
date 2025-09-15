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


def _update_demo_data():
    # Simple data synthesizer so charts are not empty
    if not st.session_state.pt_running:
        return
    buf = st.session_state.pt_data
    t = int(time.time())
    buf["t"].append(t)

    # Fake around desireds
    d_ox = float(st.session_state.pt_flow_desired_oxygen)
    d_flow = 0.5 * d_ox  # arbitrary relation for demo
    d_press = float(st.session_state.pt_pressure_desired_pressure)
    d_ppump = 50.0 * d_press

    import random
    buf["ox_desired"].append(d_ox)
    buf["ox_meas1"].append(max(0.0, d_ox + random.uniform(-50, 50)))
    buf["ox_meas2"].append(max(0.0, d_ox + random.uniform(-50, 50)))
    buf["ox_meas3"].append(max(0.0, d_ox + random.uniform(-50, 50)))

    buf["flow_desired"].append(d_flow)
    buf["flow_actual"].append(max(0.0, d_flow + random.uniform(-10, 10)))

    buf["press_pump_desired"].append(d_ppump)
    buf["press_pump_actual"].append(max(0.0, d_ppump + random.uniform(-5, 5)))

    buf["pressure_desired"].append(d_press)
    buf["pressure_actual"].append(max(0.0, d_press + random.uniform(-0.2, 0.2)))

    # Keep last N points
    N = 120
    for k in list(buf.keys()):
        if len(buf[k]) > N:
            buf[k] = buf[k][-N:]


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
        MQTTService().subscribe(t_flow)
        MQTTService().subscribe(t_press)
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
    except Exception:
        pass

_pid_status_tick()


# -----------------------------
# Second + Third blocks: Gains + PID controls
# -----------------------------
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
                if not mod:
                    st.warning("Select a module first.")
                else:
                    ok = _publish_pid_command(mod, {
                        "type": "flow_pid",
                        "desired_oxygen": float(st.session_state.pt_flow_desired_oxygen),
                        "kp": float(st.session_state.pt_flow_kp),
                        "ki": float(st.session_state.pt_flow_ki),
                        "kd": float(st.session_state.pt_flow_kd),
                    })
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
                if not mod:
                    st.warning("Select a module first.")
                else:
                    ok = _publish_pid_command(mod, {
                        "type": "pressure_pid",
                        "desired_pressure": float(st.session_state.pt_pressure_desired_pressure),
                        "kp": float(st.session_state.pt_pressure_kp),
                        "ki": float(st.session_state.pt_pressure_ki),
                        "kd": float(st.session_state.pt_pressure_kd),
                    })
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
            _status_chip(
                f"Flow PID {'Active' if st.session_state.pt_flow_enabled else 'Inactive'}",
                st.session_state.pt_flow_enabled,
            )
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.session_state.pt_flow_enabled:
                if st.button("Disable PID", key="pt_disable_flow"):
                    mod = st.session_state.get("pt_selected_module")
                    if not mod:
                        st.warning("Select a module first.")
                    else:
                        ok = _publish_pid_command(mod, {"type": "flow_pid_enable", "enabled": False})
                        if ok:
                            st.session_state.pt_flow_enabled = False
                            show_toast("Flow PID disabled", "warning", source="PID Tuning")
            else:
                if st.button("Enable PID", key="pt_enable_flow"):
                    mod = st.session_state.get("pt_selected_module")
                    if not mod:
                        st.warning("Select a module first.")
                    else:
                        ok = _publish_pid_command(mod, {"type": "flow_pid_enable", "enabled": True})
                        if ok:
                            st.session_state.pt_flow_enabled = True
                            show_toast("Flow PID enabled", "success", source="PID Tuning")

            # Live flow PID status panel
            try:
                s = st.session_state.get("pt_flow_status") or {}
                with st.container(border=True):
                    st.caption("Current Flow PID Status")
                    st.markdown(
                        f"Desired O2: {float(s.get('desired_oxygen', 0.0)):.2f} | "
                        f"Kp: {float(s.get('kp', 0.0)):.3f} | Ki: {float(s.get('ki', 0.0)):.3f} | Kd: {float(s.get('kd', 0.0)):.3f} | "
                        f"Mode: {str(s.get('mode', '—'))} | Enabled: {bool(s.get('pid_enabled', False))}"
                    )
            except Exception:
                pass

        # Pressure PID column (right)
        with c2:
            _status_chip(
                f"Pressure PID {'Active' if st.session_state.pt_pressure_enabled else 'Inactive'}",
                st.session_state.pt_pressure_enabled,
            )
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.session_state.pt_pressure_enabled:
                if st.button("Disable PID", key="pt_disable_pressure"):
                    mod = st.session_state.get("pt_selected_module")
                    if not mod:
                        st.warning("Select a module first.")
                    else:
                        ok = _publish_pid_command(mod, {"type": "pressure_pid_enable", "enabled": False})
                        if ok:
                            st.session_state.pt_pressure_enabled = False
                            show_toast("Pressure PID disabled", "warning", source="PID Tuning")
            else:
                if st.button("Enable PID", key="pt_enable_pressure"):
                    mod = st.session_state.get("pt_selected_module")
                    if not mod:
                        st.warning("Select a module first.")
                    else:
                        ok = _publish_pid_command(mod, {"type": "pressure_pid_enable", "enabled": True})
                        if ok:
                            st.session_state.pt_pressure_enabled = True
                            show_toast("Pressure PID enabled", "success", source="PID Tuning")

            # Live pressure PID status panel
            try:
                s2 = st.session_state.get("pt_pressure_status") or {}
                with st.container(border=True):
                    st.caption("Current Pressure PID Status")
                    st.markdown(
                        f"Desired Pressure: {float(s2.get('desired_pressure', 0.0)):.2f} | "
                        f"Kp: {float(s2.get('kp', 0.0)):.3f} | Ki: {float(s2.get('ki', 0.0)):.3f} | Kd: {float(s2.get('kd', 0.0)):.3f} | "
                        f"Mode: {str(s2.get('mode', '—'))} | Enabled: {bool(s2.get('pid_enabled', False))}"
                    )
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


MAX_POINTS = 120


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
            chart = _base_single_series_chart("#3B82F6")
            elements.append(st.altair_chart(chart, use_container_width=True))

    # Row 2
    c3, c4 = st.columns([1, 1], gap="small")
    with c3:
        with st.container(border=True):
            st.subheader("Desired Speed of Pressure Pump vs actual speed flow rate vs Time")
            chart = _base_single_series_chart("#10B981")
            elements.append(st.altair_chart(chart, use_container_width=True))
    with c4:
        with st.container(border=True):
            st.subheader("Desired Pressure vs Actual Pressure  Time")
            chart = _base_single_series_chart("#F59E0B")
            elements.append(st.altair_chart(chart, use_container_width=True))

    st.session_state.pt_chart_elements = elements
    st.session_state.pt_painted_len = 0


_init_pid_charts_altair()


@st.fragment(run_every=1.0)
def _update_charts_stream():
    _update_demo_data()
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

        # Chart 2: Flow pump desired vs actual (stack as two sequential rows)
        df2 = pd.DataFrame({"x": [ts, ts], "y": [data["flow_desired"][i], data["flow_actual"][i]]})
        charts[1].add_rows(df2)

        # Chart 3: Pressure pump desired vs actual
        df3 = pd.DataFrame({"x": [ts, ts], "y": [data["press_pump_desired"][i], data["press_pump_actual"][i]]})
        charts[2].add_rows(df3)

        # Chart 4: Pressure desired vs actual
        df4 = pd.DataFrame({"x": [ts, ts], "y": [data["pressure_desired"][i], data["pressure_actual"][i]]})
        charts[3].add_rows(df4)

    st.session_state.pt_painted_len = end


_update_charts_stream()


