import time
import os
import json

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
# Chart stability controls
Y_HYST_REL = 0.02   # 2% of current range
Y_HYST_ABS = 0.5    # minimum absolute margin
RECREATE_MIN_SECS = 3.0  # coalesced recreate throttle across all charts

# Debug rate limiter
st.session_state.setdefault("_pt_dbg_gate", {})
def _dbg_rate_ok(key: str, min_secs: float) -> bool:
    try:
        now = time.time()
        nxt = float(st.session_state._pt_dbg_gate.get(key, 0))
        if now >= nxt:
            st.session_state._pt_dbg_gate[key] = now + float(min_secs)
            return True
    except Exception:
        pass
    return False


# -----------------------------
# Helpers
# -----------------------------
def get_mqtt() -> MQTTService:
    if "_pt_mqtt" not in st.session_state:
        st.session_state._pt_mqtt = MQTTService()
    return st.session_state._pt_mqtt
def _pt_append_log(message: str) -> None:
    try:
        # Also publish to MQTT debug topic
        try:
            payload = {
                "message_source": "proteus-ui",
                "timestamp": datetime.now().isoformat(),
                "module": st.session_state.get("pt_selected_module"),
                "message": message,
            }
            get_mqtt().publish("debug/pid", payload)
        except Exception:
            pass
    except Exception:
        pass

# Lightweight debug logger (shows in PID Tuning Logs panel)
def _dbg(message: str) -> None:
    try:
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"DBG {stamp} | {message}"
        # MQTT debug
        try:
            payload = {
                "message_source": "proteus-ui",
                "timestamp": datetime.now().isoformat(),
                "module": st.session_state.get("pt_selected_module"),
                "message": line,
            }
            get_mqtt().publish("debug/pid", payload)
        except Exception:
            pass
    except Exception:
        # Avoid crashing if session_state not ready
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
        # Timestamp (robust)
        ts = payload.get("timestamp") or payload.get("time") or payload.get("ts")
        try:
            t_epoch = int(time.time()) if ts is None else int(pd.to_datetime(ts, utc=True).timestamp())
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

        # Persist to JSONL for backfill
        try:
            mod = st.session_state.get("pt_selected_module")
            if mod:
                live_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pidlive")
                os.makedirs(live_dir, exist_ok=True)
                fpath = os.path.join(live_dir, f"{mod}.jsonl")
                with open(fpath, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "ts": t_epoch,
                        "ox_desired": buf["ox_desired"][-1],
                        "ox_meas1": buf["ox_meas1"][-1],
                        "ox_meas2": buf["ox_meas2"][-1],
                        "ox_meas3": buf["ox_meas3"][-1],
                        "flow_desired": buf["flow_desired"][-1],
                        "flow_actual": buf["flow_actual"][-1],
                        "press_pump_desired": buf["press_pump_desired"][-1],
                        "press_pump_actual": buf["press_pump_actual"][-1],
                        "pressure_desired": buf["pressure_desired"][-1],
                        "pressure_actual": buf["pressure_actual"][-1],
                    }) + "\n")
        except Exception:
            pass
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
            _pt_append_log(f"dbg: subscribed {topic}")
        except Exception:
            return

    updates = get_mqtt().drain(topic, max_items=500)
    if not updates:
        return
    if _dbg_rate_ok("collector/drained", 1.0):
        _pt_append_log(f"dbg: collector drained {len(updates)} msgs")
    for _, payload in updates:
        try:
            if isinstance(payload, dict) and payload.get("alpha_command") == "sensor_data":
                _append_live_point(payload)
            else:
                # Note: keep behavior unchanged; just log first time we see unknown shapes
                if _dbg_rate_ok("collector/unknown", 5.0):
                    shape = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
                    _pt_append_log(f"dbg: unknown live payload shape: {shape}")
        except Exception:
            if _dbg_rate_ok("collector/error", 2.0):
                _pt_append_log("dbg: collector error while processing payload")
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
            # Backfill from JSONL tail (last 5 hours)
            try:
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
                live_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pidlive")
                fpath = os.path.join(live_dir, f"{chosen}.jsonl")
                if os.path.exists(fpath):
                    now = int(time.time())
                    cutoff = now - 18_000
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = f.readlines()[-MAX_POINTS:]
                    for line in lines:
                        try:
                            rec = json.loads(line)
                            ts = int(rec.get("ts"))
                            if ts < cutoff:
                                continue
                            st.session_state.pt_data["t"].append(ts)
                            for k in ("ox_desired","ox_meas1","ox_meas2","ox_meas3","flow_desired","flow_actual","press_pump_desired","press_pump_actual","pressure_desired","pressure_actual"):
                                st.session_state.pt_data[k].append(float(rec.get(k, 0.0)))
                        except Exception:
                            continue
                st.session_state._pt_stream_idx = len(st.session_state.pt_data["t"]) or 0
            except Exception:
                pass
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


def _style_chart(c: alt.Chart) -> alt.Chart:
    # Pin consistent font sizes to avoid visual jitter across rerenders
    return (
        c.configure_axis(labelFontSize=12, titleFontSize=13)
         .configure_legend(labelFontSize=12, titleFontSize=13)
         .configure_title(fontSize=16)
    )


def _ensure_stream_charts(recreate: bool = False):
    charts = st.session_state.get("_pt_stream_charts")
    if charts and not recreate:
        return charts

    # Initial y bounds (grow-only later)
    for key in ("p1_ymin", "p1_ymax", "p2_ymin", "p2_ymax", "p3_ymin", "p3_ymax", "p4_ymin", "p4_ymax"):
        st.session_state.setdefault(key, 0.0 if key.endswith("ymin") else 1.0)

    def _mk_chart(ymin_key: str, ymax_key: str):
        ymin = float(st.session_state.get(ymin_key, 0.0))
        ymax = float(st.session_state.get(ymax_key, 1.0))
        base = alt.Chart(pd.DataFrame({"x": [], "series": [], "y": []})) \
            .mark_line() \
            .encode(
                x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                y=alt.Y("y:Q", title=None, scale=alt.Scale(domain=[ymin, ymax], nice=False, clamp=True)),
                color=alt.Color("series:N", legend=alt.Legend(title=None)),
            )
        ch = st.altair_chart(base, use_container_width=True)
        _dbg(f"mk_chart {ymin_key}/{ymax_key} domain=[{ymin},{ymax}]")
        return ch

    c1, c2 = st.columns([1, 1], gap="small")
    with c1:
        st.subheader("Desired Oxygen + 3 Measured Oxygen vs Time")
        ch1 = _mk_chart("p1_ymin", "p1_ymax")
    with c2:
        st.subheader("Desired Speed of Flow Pump vs actual flow rate vs Time")
        ch2 = _mk_chart("p2_ymin", "p2_ymax")
    c3, c4 = st.columns([1, 1], gap="small")
    with c3:
        st.subheader("Desired Speed of Pressure Pump vs actual speed flow rate vs Time")
        ch3 = _mk_chart("p3_ymin", "p3_ymax")
    with c4:
        st.subheader("Desired Pressure vs Actual Pressure Time")
        ch4 = _mk_chart("p4_ymin", "p4_ymax")

    charts = [ch1, ch2, ch3, ch4]
    st.session_state._pt_stream_charts = charts
    return charts


def _grow_y_bounds(values: list[float], prefix: str) -> bool:
    changed = False
    try:
        if not values:
            return False
        # Filter non-finite and cast
        vals = []
        for v in values:
            try:
                x = float(v)
                if pd.notna(x) and abs(x) != float("inf"):
                    vals.append(x)
            except Exception:
                continue
        if not vals:
            return False
        vals.sort()
        n = len(vals)
        # Robust min/max (trim extremes) to avoid huge outliers
        if n >= 10:
            i1 = max(0, int(0.02 * n) - 1)
            i2 = min(n - 1, int(0.98 * n))
            vmin = vals[i1]
            vmax = vals[i2]
        else:
            vmin = vals[0]
            vmax = vals[-1]
        # Apply per-panel soft floor(s)
        if prefix == "p4":
            # Pressure cannot be negative in our UI; floor to 0
            vmin = max(vmin, 0.0)
        # Ensure non-degenerate range
        if abs(vmax - vmin) < 1e-6:
            vmax = vmin + 1.0
        eps = 0.02 * max(vmax - vmin, 1.0)
        prev_ymin = float(st.session_state.get(f"{prefix}_ymin", vmin))
        prev_ymax = float(st.session_state.get(f"{prefix}_ymax", vmax + eps))
        # Hysteresis: only expand if beyond rel/abs margin
        current_range = max(prev_ymax - prev_ymin, 1.0)
        margin = max(Y_HYST_REL * current_range, Y_HYST_ABS)
        ymin = prev_ymin
        ymax = prev_ymax
        # Floor pressure y-min to 0 consistently
        if prefix == "p4":
            ymin = max(ymin, 0.0)
        if vmin < prev_ymin - margin:
            ymin = vmin
            changed = True
        if vmax > prev_ymax + margin:
            ymax = vmax + eps
            changed = True
        if changed:
            if _dbg_rate_ok(f"yexpand/{prefix}", 2.0):
                _pt_append_log(
                    f"dbg: y-expand {prefix} -> ymin={ymin:.3f}, ymax={ymax:.3f} (margin={margin:.3f})"
                )
            st.session_state[f"{prefix}_ymin"] = ymin
            st.session_state[f"{prefix}_ymax"] = ymax
    except Exception:
        pass
    return changed


@st.fragment(run_every=0.5)
def _charts_stream():
    if not st.session_state.get("pt_selected_module"):
        return
    charts = _ensure_stream_charts()
    data = st.session_state.get("pt_data", {})
    if not data or not data.get("t"):
        return

    start = int(st.session_state.get("_pt_stream_idx", 0))
    end = len(data["t"])  # append-only; trimming handled at collector if used
    if end <= start:
        return

    idx = range(start, end)
    if _dbg_rate_ok("stream/batch", 1.0):
        _pt_append_log(f"dbg: stream rows start={start} end={end} count={end-start}")
    # Update y bounds grow-only
    try:
        changed = False
        oxy_vals = [data["ox_desired"][i] for i in idx] + [data["ox_meas1"][i] for i in idx] + [data["ox_meas2"][i] for i in idx] + [data["ox_meas3"][i] for i in idx]
        changed |= _grow_y_bounds(oxy_vals, "p1")
        flow_vals = [data["flow_desired"][i] for i in idx] + [data["flow_actual"][i] for i in idx]
        changed |= _grow_y_bounds(flow_vals, "p2")
        pp_vals = [data["press_pump_desired"][i] for i in idx] + [data["press_pump_actual"][i] for i in idx]
        changed |= _grow_y_bounds(pp_vals, "p3")
        pr_vals = [data["pressure_desired"][i] for i in idx] + [data["pressure_actual"][i] for i in idx]
        changed |= _grow_y_bounds(pr_vals, "p4")
        # Throttle chart recreation (coalesced; at most once per RECREATE_MIN_SECS)
        if changed:
            last_rc = float(st.session_state.get("_pt_last_recreate_ts", 0))
            now = time.time()
            if now - last_rc >= RECREATE_MIN_SECS:
                charts = _ensure_stream_charts(recreate=True)
                st.session_state["_pt_last_recreate_ts"] = now
                _pt_append_log("dbg: charts recreated due to y-bounds expansion")
            else:
                if _dbg_rate_ok("recreate/suppressed", 2.0):
                    remain = RECREATE_MIN_SECS - (now - last_rc)
                    _pt_append_log(f"dbg: recreate suppressed ({remain:.1f}s left)")
    except Exception:
        pass

    # Stream rows
    for i in idx:
        ts = pd.to_datetime(int(data["t"][i]), unit="s")
        try:
            charts[0].add_rows(pd.DataFrame([
                {"x": ts, "series": "Desired", "y": data["ox_desired"][i]},
                {"x": ts, "series": "Measured A", "y": data["ox_meas1"][i]},
                {"x": ts, "series": "Measured B", "y": data["ox_meas2"][i]},
                {"x": ts, "series": "Measured C", "y": data["ox_meas3"][i]},
            ]))
        except Exception:
            if _dbg_rate_ok("add_rows/ch1", 2.0):
                _pt_append_log("dbg: add_rows failed on chart1")
        try:
            charts[1].add_rows(pd.DataFrame([
                {"x": ts, "series": "Desired", "y": data["flow_desired"][i]},
                {"x": ts, "series": "Actual", "y": data["flow_actual"][i]},
            ]))
        except Exception:
            if _dbg_rate_ok("add_rows/ch2", 2.0):
                _pt_append_log("dbg: add_rows failed on chart2")
        try:
            charts[2].add_rows(pd.DataFrame([
                {"x": ts, "series": "Desired", "y": data["press_pump_desired"][i]},
                {"x": ts, "series": "Actual", "y": data["press_pump_actual"][i]},
            ]))
        except Exception:
            if _dbg_rate_ok("add_rows/ch3", 2.0):
                _pt_append_log("dbg: add_rows failed on chart3")
        try:
            charts[3].add_rows(pd.DataFrame([
                {"x": ts, "series": "Desired", "y": data["pressure_desired"][i]},
                {"x": ts, "series": "Actual", "y": data["pressure_actual"][i]},
            ]))
        except Exception:
            if _dbg_rate_ok("add_rows/ch4", 2.0):
                _pt_append_log("dbg: add_rows failed on chart4")

    st.session_state._pt_stream_idx = end

_charts_stream()


    


