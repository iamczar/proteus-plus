import time

import streamlit as st
import pandas as pd
import altair as alt

from common.utils import inject_button_theme
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

st.session_state.setdefault("pt_flow_status", {})
st.session_state.setdefault("pt_pressure_status", {})
st.session_state.setdefault("pt_logs", [])

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
st.session_state.setdefault("_pt_live_sub_topic", None)

# Live data topic and window
LIVE_TOPIC_PREFIX = "live-sensor-data"
MAX_POINTS = 18000  # ~5 hours @ 1 Hz


# -----------------------------
# Helpers
# -----------------------------
def get_mqtt() -> MQTTService:
    if "_pt_mqtt" not in st.session_state:
        st.session_state._pt_mqtt = MQTTService()
    return st.session_state._pt_mqtt
def _pt_append_log(message: str) -> None:
    try:
        st.session_state.pt_logs.append(message)
        st.session_state.pt_logs = st.session_state.pt_logs[-400:]
    except Exception:
        pass
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




def _publish_pid_command(module_id: str | int, payload: dict) -> bool:
    try:
        topic = f"pid-commands/{module_id}"
        envelope = {
            "message_source": "proteus-ui",
            "timestamp": datetime.now().isoformat(),
            "message": payload,
        }
        # Publish via singleton client
        get_mqtt().publish(topic, envelope)
        _pt_append_log(f">> SEND {payload}")
        # Track last enable/disable to update UI immediately on ack
        try:
            t = str(payload.get("type", ""))
            if t == "flow_pid_enable":
                st.session_state["_pt_last_toggle"] = {"controller": "flow", "enabled": bool(payload.get("enabled", False))}
            elif t == "pressure_pid_enable":
                st.session_state["_pt_last_toggle"] = {"controller": "pressure", "enabled": bool(payload.get("enabled", False))}
        except Exception:
            pass
        return True
    except Exception as exc:
        _pt_append_log(f"!! Publish failed: {exc}")
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
            get_mqtt().subscribe(topic)
            st.session_state._pt_live_sub_topic = topic
        except Exception:
            return

    updates = get_mqtt().drain(topic, max_items=500)
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

        chosen = st.selectbox(
            label="Module Selection (local):",
            options=[placeholder_label] + modules if previous_value is None else modules,
            index=0 if previous_value is None else (modules.index(previous_value) if previous_value in modules else 0),
            key="_pt_module_select",
        )

        if chosen != placeholder_label and chosen != previous_value:
            st.session_state.pt_selected_module = chosen
            # Reset chart state and buffers on module change
            # Reset only data buffers on module change; charts are stateless now
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
            _pt_append_log(f">> Selected module: {chosen}")
            # No explicit rerun; Streamlit triggers one automatically on select change

# Terminal-style log panel CSS
st.markdown(
    """
    <style>
    .pt-log-box { background-color: #111316; color: #D1FAE5; padding: 10px; border-radius: 8px;
                  height: 180px; overflow-y: auto; font-family: monospace; font-size: 13px;
                  border: 1px solid #28323a; white-space: pre-wrap; }
    .pt-log-title { font-weight: 700; margin: 0 0 6px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.fragment(run_every=0.5)
def _logs_tick():
    st.subheader("PID Tuning Logs")
    form_key = "pt_clear_logs_form_main"
    with st.form(form_key):
        if st.form_submit_button("Clear"):
            st.session_state.pt_logs = []
    log_content = "\n".join(st.session_state.get("pt_logs", [])[-400:])
    st.markdown(f"<div class='pt-log-box'>{log_content}</div>", unsafe_allow_html=True)


def _refresh_pid_status_once(module_id: str | int) -> None:
    try:
        # Ensure subscriptions exist
        subs = st.session_state.setdefault("_pt_pid_subs", set())
        for t in (f"pid-flow-status/{module_id}", f"pid-pressure-status/{module_id}"):
            if t not in subs:
                try:
                    get_mqtt().subscribe(t)
                except Exception:
                    pass
                subs.add(t)
        # Drain once
        for _, payload in get_mqtt().drain(f"pid-flow-status/{module_id}", max_items=200):
            inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
            if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "flow":
                st.session_state.pt_flow_status = inner
        for _, payload in get_mqtt().drain(f"pid-pressure-status/{module_id}", max_items=200):
            inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
            if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "pressure":
                st.session_state.pt_pressure_status = inner
    except Exception:
        pass


# PID status subscription and polling
@st.fragment(run_every=1.0)
def _pid_status_tick():
    mod = st.session_state.get("pt_selected_module")
    if not mod:
        return
    try:
        # Subscribe once per module
        subs = st.session_state.setdefault("_pt_pid_subs", set())
        need = {
            f"pid-flow-status/{mod}",
            f"pid-pressure-status/{mod}",
            f"alphacommsmanager-status/{mod}",
        }
        new_topics = need - subs
        if new_topics:
            mqtt = get_mqtt()
            for t in new_topics:
                try:
                    mqtt.subscribe(t)
                except Exception:
                    pass
            subs |= new_topics
        t_flow = f"pid-flow-status/{mod}"
        t_press = f"pid-pressure-status/{mod}"
        t_am = f"alphacommsmanager-status/{mod}"
        # Drain and keep only the latest; only update if values changed to avoid unnecessary reruns
        for _, payload in get_mqtt().drain(t_flow, max_items=100):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "flow":
                    if inner != (st.session_state.get("pt_flow_status") or {}):
                        st.session_state.pt_flow_status = inner
            except Exception:
                pass
        for _, payload in get_mqtt().drain(t_press, max_items=100):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "pressure":
                    if inner != (st.session_state.get("pt_pressure_status") or {}):
                        st.session_state.pt_pressure_status = inner
            except Exception:
                pass
        # Alpha acks for PID
        for _, payload in get_mqtt().drain(t_am, max_items=50):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                cmd = str(inner.get("command", "")).lower() if isinstance(inner, dict) else ""
                status = str(inner.get("status", "")).lower() if isinstance(inner, dict) else ""
                if cmd == "pid_cmd" and status in ("ack", "acknowledged", "received"):
                    _pt_append_log("<< ACK pid_cmd from Alpha")
                    # If this ack corresponds to a recent toggle, flip the UI immediately
                    toggle = st.session_state.get("_pt_last_toggle")
                    if isinstance(toggle, dict):
                        controller = toggle.get("controller")
                        enabled = bool(toggle.get("enabled"))
                        if controller == "flow":
                            st.session_state.pt_flow_status = {**(st.session_state.get("pt_flow_status") or {}), "pid_enabled": enabled}
                        elif controller == "pressure":
                            st.session_state.pt_pressure_status = {**(st.session_state.get("pt_pressure_status") or {}), "pid_enabled": enabled}
                        # Clear the pending toggle so we don't repeat
                        try:
                            del st.session_state["_pt_last_toggle"]
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

_pid_status_tick()

    


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
                with st.form("flow_gains_form"):
                    st.number_input("Desired Oxygen : micromole/liter", key="pt_flow_desired_oxygen")
                    st.number_input("Proportional Gain", key="pt_flow_kp")
                    st.number_input("Integral Gain", key="pt_flow_ki")
                    st.number_input("Derivative Gain", key="pt_flow_kd")
                    submitted = st.form_submit_button("Send")
                    if submitted:
                        mod = st.session_state.get("pt_selected_module")
                        payload = {
                            "type": "flow_pid",
                            "desired_oxygen": float(st.session_state.pt_flow_desired_oxygen),
                            "kp": float(st.session_state.pt_flow_kp),
                            "ki": float(st.session_state.pt_flow_ki),
                            "kd": float(st.session_state.pt_flow_kd),
                        }
                        ok = _publish_pid_command(mod, payload)

    # Pressure Controller Gains window
        with gains_cols[1]:
            with st.container(border=True):
                st.subheader("Pressure Controller Gains")
                with st.form("pressure_gains_form"):
                    st.number_input("Desired Pressure : psi", key="pt_pressure_desired_pressure")
                    st.number_input("Proportional Gain", key="pt_pressure_kp")
                    st.number_input("Integral Gain", key="pt_pressure_ki")
                    st.number_input("Derivative Gain", key="pt_pressure_kd")
                    submitted2 = st.form_submit_button("Send")
                    if submitted2:
                        mod = st.session_state.get("pt_selected_module")
                        payload = {
                            "type": "pressure_pid",
                            "desired_pressure": float(st.session_state.pt_pressure_desired_pressure),
                            "kp": float(st.session_state.pt_pressure_kp),
                            "ki": float(st.session_state.pt_pressure_ki),
                            "kd": float(st.session_state.pt_pressure_kd),
                        }
                        ok = _publish_pid_command(mod, payload)

    with right:
        @st.fragment(run_every=1.0)
        def _pid_right_panel():
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
                    # Toggle button reflects live state and always sends the inverse
                    toggle_label = "Disable PID" if flow_enabled else "Enable PID"
                    with st.form("pt_flow_enable_form"):
                        submitted_toggle = st.form_submit_button(toggle_label)
                        if submitted_toggle:
                            mod = st.session_state.get("pt_selected_module")
                            target = not flow_enabled
                            ok = _publish_pid_command(mod, {"type": "flow_pid_enable", "enabled": target})
                            if ok:
                                _pt_append_log(f">> {'ENABLE' if target else 'DISABLE'} flow PID")
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
                    # Toggle button reflects live state and always sends the inverse
                    toggle_label2 = "Disable PID" if pressure_enabled else "Enable PID"
                    with st.form("pt_pressure_enable_form"):
                        submitted_toggle2 = st.form_submit_button(toggle_label2)
                        if submitted_toggle2:
                            mod = st.session_state.get("pt_selected_module")
                            target = not pressure_enabled
                            ok = _publish_pid_command(mod, {"type": "pressure_pid_enable", "enabled": target})
                            if ok:
                                _pt_append_log(f">> {'ENABLE' if target else 'DISABLE'} pressure PID")
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

            # Terminal-style logs below the status panels
            with st.container(border=True):
                # Use a unique key for the nested logs form to avoid duplicate form keys
                st.subheader("PID Tuning Logs")
                nested_form_key = "pt_clear_logs_form_right"
                with st.form(nested_form_key):
                    if st.form_submit_button("Clear"):
                        st.session_state.pt_logs = []
                log_content = "\n".join(st.session_state.get("pt_logs", [])[-400:])
                st.markdown(f"<div class='pt-log-box'>{log_content}</div>", unsafe_allow_html=True)

        _pid_right_panel()

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


def _build_long_df(buf: dict):
    try:
        t = pd.to_datetime(pd.Series(buf.get("t", []), dtype="int64"), unit="s")
    except Exception:
        t = pd.to_datetime(pd.Series([], dtype="int64"), unit="s")

    # Chart 1: Desired O2 + 3 measured
    df1 = pd.concat([
        pd.DataFrame({"x": t, "series": "Desired", "y": pd.Series(buf.get("ox_desired", []), dtype="float64")}),
        pd.DataFrame({"x": t, "series": "Measured A", "y": pd.Series(buf.get("ox_meas1", []), dtype="float64")}),
        pd.DataFrame({"x": t, "series": "Measured B", "y": pd.Series(buf.get("ox_meas2", []), dtype="float64")}),
        pd.DataFrame({"x": t, "series": "Measured C", "y": pd.Series(buf.get("ox_meas3", []), dtype="float64")}),
    ], ignore_index=True)

    # Chart 2: Flow desired vs actual
    df2 = pd.concat([
        pd.DataFrame({"x": t, "series": "Desired", "y": pd.Series(buf.get("flow_desired", []), dtype="float64")}),
        pd.DataFrame({"x": t, "series": "Actual",  "y": pd.Series(buf.get("flow_actual", []), dtype="float64")}),
    ], ignore_index=True)

    # Chart 3: Pressure pump desired vs actual (use press_pump_actual)
    df3 = pd.concat([
        pd.DataFrame({"x": t, "series": "Desired", "y": pd.Series(buf.get("press_pump_desired", []), dtype="float64")}),
        pd.DataFrame({"x": t, "series": "Actual",  "y": pd.Series(buf.get("press_pump_actual", []), dtype="float64")}),
    ], ignore_index=True)

    # Chart 4: Pressure desired vs actual
    df4 = pd.concat([
        pd.DataFrame({"x": t, "series": "Desired", "y": pd.Series(buf.get("pressure_desired", []), dtype="float64")}),
        pd.DataFrame({"x": t, "series": "Actual",  "y": pd.Series(buf.get("pressure_actual", []), dtype="float64")}),
    ], ignore_index=True)

    return df1, df2, df3, df4


def _base_chart(df: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
            y=alt.Y("y:Q", title=None),
            color=alt.Color("series:N", legend=alt.Legend(title=None)),
        )
    )


@st.fragment(run_every=1.0)
def _charts_tick():
    if not st.session_state.get("pt_selected_module"):
        return
    buf = st.session_state.get("pt_data", {})
    if not buf or not buf.get("t"):
        return
    # Slice to reduce browser work; repaint last N points only
    end = len(buf.get("t", []))
    N = min(MAX_POINTS, 6000)
    start = max(0, end - N)
    sliced = {k: v[start:end] for k, v in buf.items()}

    df1, df2, df3, df4 = _build_long_df(sliced)

    # Sticky Y domains to prevent bouncing
    def _sticky_domain(state_key_min: str, state_key_max: str, values: list[float], default_min: float = 0.0, pad_ratio: float = 0.1):
        try:
            if not values:
                return (st.session_state.get(state_key_min, default_min), st.session_state.get(state_key_max, default_min))
            vmin = float(min(values))
            vmax = float(max(values))
            # Pad
            if vmax == vmin:
                vmax = vmin + 1.0
            span = max(1e-6, vmax - vmin)
            # Never go below default_min (e.g., keep 0 as the floor so the x-axis stays at the bottom)
            vmin_p = max(default_min, vmin - pad_ratio * span)
            vmax_p = vmax + pad_ratio * span
            old_min = st.session_state.get(state_key_min, vmin_p)
            old_max = st.session_state.get(state_key_max, vmax_p)
            new_min = min(old_min, vmin_p)
            new_max = max(old_max, vmax_p)
            st.session_state[state_key_min] = new_min
            st.session_state[state_key_max] = new_max
            return (new_min, new_max)
        except Exception:
            return (st.session_state.get(state_key_min, default_min), st.session_state.get(state_key_max, default_min + 1.0))

    c1, c2 = st.columns([1, 1], gap="small")
    with c1:
        with st.container(border=True):
            st.subheader("Desired Oxygen + 3 Measured Oxygen vs Time")
            dom1 = _sticky_domain("y1_min", "y1_max", df1["y"].tolist(), default_min=0.0, pad_ratio=0.05)
            chart1 = (
                alt.Chart(df1)
                .mark_line()
                .encode(
                    x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                    y=alt.Y("y:Q", title=None, scale=alt.Scale(domain=list(dom1), clamp=True)),
                    color=alt.Color("series:N", legend=alt.Legend(title=None)),
                )
            )
            st.altair_chart(chart1.properties(height=340), use_container_width=True)
    with c2:
        with st.container(border=True):
            st.subheader("Desired Speed of Flow Pump vs actual flow rate vs Time")
            dom2 = _sticky_domain("y2_min", "y2_max", df2["y"].tolist(), default_min=0.0, pad_ratio=0.05)
            chart2 = (
                alt.Chart(df2)
                .mark_line()
                .encode(
                    x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                    y=alt.Y("y:Q", title=None, scale=alt.Scale(domain=list(dom2), clamp=True)),
                    color=alt.Color("series:N", legend=alt.Legend(title=None)),
                )
            )
            st.altair_chart(chart2.properties(height=340), use_container_width=True)

    c3, c4 = st.columns([1, 1], gap="small")
    with c3:
        with st.container(border=True):
            st.subheader("Desired Speed of Pressure Pump vs actual speed flow rate vs Time")
            dom3 = _sticky_domain("y3_min", "y3_max", df3["y"].tolist(), default_min=0.0, pad_ratio=0.05)
            chart3 = (
                alt.Chart(df3)
                .mark_line()
                .encode(
                    x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                    y=alt.Y("y:Q", title=None, scale=alt.Scale(domain=list(dom3), clamp=True)),
                    color=alt.Color("series:N", legend=alt.Legend(title=None)),
                )
            )
            st.altair_chart(chart3.properties(height=340), use_container_width=True)
    with c4:
        with st.container(border=True):
            st.subheader("Desired Pressure vs Actual Pressure  Time")
            dom4 = _sticky_domain("y4_min", "y4_max", df4["y"].tolist(), default_min=0.0, pad_ratio=0.05)
            chart4 = (
                alt.Chart(df4)
                .mark_line()
                .encode(
                    x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                    y=alt.Y("y:Q", title=None, scale=alt.Scale(domain=list(dom4), clamp=True)),
                    color=alt.Color("series:N", legend=alt.Legend(title=None)),
                )
            )
            st.altair_chart(chart4.properties(height=340), use_container_width=True)

_charts_tick()


    


