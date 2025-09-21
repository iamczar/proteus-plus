import time
import os
import json
import sys
import traceback

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

# Live data window and chart settings
MAX_POINTS = 1800  # show only the last 1800 samples

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
def _install_global_exception_hook():
    try:
        if not st.session_state.get("_pt_exhook_installed"):
            def _hook(exctype, value, tb):
                try:
                    msg = f"uncaught: {exctype.__name__}: {value}"
                    get_mqtt().publish("debug/pid", {
                        "message_source": "proteus-ui",
                        "timestamp": datetime.now().isoformat(),
                        "module": st.session_state.get("pt_selected_module"),
                        "message": msg,
                    })
                except Exception:
                    pass
                sys.__excepthook__(exctype, value, tb)
            sys.excepthook = _hook
            st.session_state["_pt_exhook_installed"] = True
    except Exception:
        pass

_install_global_exception_hook()
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
        # Mirror user-facing log lines into the on-page PID Tuning Logs
        try:
            if isinstance(message, str) and message.strip().startswith((">>", "<<")):
                logs = st.session_state.get("pt_logs", [])
                logs.append(message)
                # Cap to last 1000 entries to bound memory
                st.session_state.pt_logs = logs[-1000:]
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
        # Monotonic stream counter (for chart increment logic under capped buffers)
        try:
            st.session_state._pt_stream_idx = int(st.session_state.get("_pt_stream_idx") or 0) + 1
        except Exception:
            pass

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


 

# -----------------------------
# First block: Module selection (shared with Live View) + Toasts
# -----------------------------
# Reuse the shared selector so the chosen module stays consistent across pages.
ModuleManager().select_module()

# Sync PID Tuning's local state to the global selection and backfill when it changes
global_selected = st.session_state.get("selected_module")
prev_local = st.session_state.get("pt_selected_module")
if global_selected != prev_local:
    st.session_state.pt_selected_module = global_selected
    if global_selected:
        try:
            # Backfill from JSONL tail (last 5 hours)
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
            fpath = os.path.join(live_dir, f"{global_selected}.jsonl")
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
        _pt_append_log(f">> Selected module: {global_selected}")

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
        drained_flow = get_mqtt().drain(t_flow, max_items=100)
        if drained_flow and _dbg_rate_ok("status/flow", 1.0):
            _pt_append_log(f"dbg: status: drained flow={len(drained_flow)}")
        for _, payload in drained_flow:
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "flow":
                    if inner != (st.session_state.get("pt_flow_status") or {}):
                        st.session_state.pt_flow_status = inner
            except Exception:
                pass
        drained_press = get_mqtt().drain(t_press, max_items=100)
        if drained_press and _dbg_rate_ok("status/press", 1.0):
            _pt_append_log(f"dbg: status: drained pressure={len(drained_press)}")
        for _, payload in drained_press:
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_status" and inner.get("controller") == "pressure":
                    if inner != (st.session_state.get("pt_pressure_status") or {}):
                        st.session_state.pt_pressure_status = inner
            except Exception:
                pass
        # Alpha acks for PID
        drained_am = get_mqtt().drain(t_am, max_items=50)
        if drained_am and _dbg_rate_ok("status/ack", 1.0):
            _pt_append_log(f"dbg: status: drained acks={len(drained_am)}")
        for _, payload in drained_am:
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                cmd = str(inner.get("command", "")).lower() if isinstance(inner, dict) else ""
                status = str(inner.get("status", "")).lower() if isinstance(inner, dict) else ""
                if cmd == "pid_cmd" and status in ("ack", "acknowledged", "received"):
                    _pt_append_log("<< ACK pid_cmd from Alpha")
                    # Avoid mutating UI state inside ack path; rely on status topics to update
                    try:
                        if "_pt_last_toggle" in st.session_state:
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
                        _pt_append_log(
                            f">> CLICK Send Flow Gains (mod={mod}) values: "
                            f"O2={st.session_state.pt_flow_desired_oxygen}, "
                            f"Kp={st.session_state.pt_flow_kp}, Ki={st.session_state.pt_flow_ki}, Kd={st.session_state.pt_flow_kd}"
                        )
                        payload = {
                            "type": "flow_pid",
                            "desired_oxygen": float(st.session_state.pt_flow_desired_oxygen),
                            "kp": float(st.session_state.pt_flow_kp),
                            "ki": float(st.session_state.pt_flow_ki),
                            "kd": float(st.session_state.pt_flow_kd),
                        }
                        try:
                            ok = _publish_pid_command(mod, payload)
                            _pt_append_log(f"dbg: publish flow gains ok={ok}")
                        except Exception as e:
                            _pt_append_log(f"!! error publishing flow gains: {e}")

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
                        _pt_append_log(
                            f">> CLICK Send Pressure Gains (mod={mod}) values: "
                            f"P_set={st.session_state.pt_pressure_desired_pressure}, "
                            f"Kp={st.session_state.pt_pressure_kp}, Ki={st.session_state.pt_pressure_ki}, Kd={st.session_state.pt_pressure_kd}"
                        )
                        payload = {
                            "type": "pressure_pid",
                            "desired_pressure": float(st.session_state.pt_pressure_desired_pressure),
                            "kp": float(st.session_state.pt_pressure_kp),
                            "ki": float(st.session_state.pt_pressure_ki),
                            "kd": float(st.session_state.pt_pressure_kd),
                        }
                        try:
                            ok = _publish_pid_command(mod, payload)
                            _pt_append_log(f"dbg: publish pressure gains ok={ok}")
                        except Exception as e:
                            _pt_append_log(f"!! error publishing pressure gains: {e}")

    with right:
        @st.fragment(run_every=1.0)
        def _pid_right_status():
            try:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 1], gap="small")

                    with c1:
                        s = st.session_state.get("pt_flow_status") or {}
                        flow_enabled = bool(s.get("pid_enabled", False))
                        _status_chip(
                            f"Flow PID {'Active' if flow_enabled else 'Inactive'}",
                            flow_enabled,
                        )
                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
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

                    with c2:
                        s2 = st.session_state.get("pt_pressure_status") or {}
                        pressure_enabled = bool(s2.get("pid_enabled", False))
                        _status_chip(
                            f"Pressure PID {'Active' if pressure_enabled else 'Inactive'}",
                            pressure_enabled,
                        )
                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
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
            except Exception as e:
                if _dbg_rate_ok("right/error", 2.0):
                    _pt_append_log(f"dbg: right_panel error: {e}")

        _pid_right_status()

        # Place buttons directly under their respective status panels
        c1_btns, c2_btns = st.columns([1, 1], gap="small")
        with c1_btns:
            s = st.session_state.get("pt_flow_status") or {}
            flow_enabled = bool(s.get("pid_enabled", False))
            toggle_label = "Disable Flow PID" if flow_enabled else "Enable Flow PID"
            with st.form("pt_flow_enable_form"):
                submitted_toggle = st.form_submit_button(toggle_label)
                if submitted_toggle:
                    mod = st.session_state.get("pt_selected_module")
                    target = not flow_enabled
                    _pt_append_log(f">> CLICK Toggle Flow PID (mod={mod}) target={target}")
                    try:
                        ok = _publish_pid_command(mod, {"type": "flow_pid_enable", "enabled": target})
                        _pt_append_log(f"dbg: publish flow toggle ok={ok}")
                        if ok:
                            _pt_append_log(f">> {'ENABLE' if target else 'DISABLE'} flow PID")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing flow toggle: {e}")

        with c2_btns:
            s2 = st.session_state.get("pt_pressure_status") or {}
            pressure_enabled = bool(s2.get("pid_enabled", False))
            toggle_label2 = "Disable Pressure PID" if pressure_enabled else "Enable Pressure PID"
            with st.form("pt_pressure_enable_form"):
                submitted_toggle2 = st.form_submit_button(toggle_label2)
                if submitted_toggle2:
                    mod = st.session_state.get("pt_selected_module")
                    target = not pressure_enabled
                    _pt_append_log(f">> CLICK Toggle Pressure PID (mod={mod}) target={target}")
                    try:
                        ok = _publish_pid_command(mod, {"type": "pressure_pid_enable", "enabled": target})
                        _pt_append_log(f"dbg: publish pressure toggle ok={ok}")
                        if ok:
                            _pt_append_log(f">> {'ENABLE' if target else 'DISABLE'} pressure PID")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing pressure toggle: {e}")

        # Removed Run/Stop and Save/Load UI for streamlined PID control

    # --- Charts (left side, below gains) ---
    with left:
        # Move the logs panel here so it spans the same width as the charts
        with st.container(border=True):
            st.subheader("PID Tuning Logs")
            form_key2 = "pt_clear_logs_form_left"
            with st.form(form_key2):
                if st.form_submit_button("Clear"):
                    st.session_state.pt_logs = []
            log_content2 = "\n".join(st.session_state.get("pt_logs", [])[-400:])
            st.markdown(f"<div class='pt-log-box'>{log_content2}</div>", unsafe_allow_html=True)

        def _ensure_pt_chart_handles(force: bool = False):
            try:
                mod = st.session_state.get("pt_selected_module") or ""
                init_key = ("pt_charts", mod)
                need_init = force or (st.session_state.get("_pt_charts_key") != init_key)
                need_init = need_init or ("pt_chart_elements" not in st.session_state)
                if not need_init:
                    return
                # Build four overlay charts stacked vertically (1x4):
                # 1) Oxygen (desired + 3 measured), 2) Flow, 3) Pressure Pump Speed, 4) Pressure
                chart_elems = {}

                # Oxygen
                st.subheader("Oxygen (desired vs measured x3)")
                df0 = pd.DataFrame({"x": [], "y": [], "series": []})
                base0 = (
                    alt.Chart(df0)
                    .mark_line()
                    .encode(
                        x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                        y=alt.Y("y:Q", title=None),
                        color=alt.Color("series:N", legend=alt.Legend(orient="top")),
                    )
                )
                chart_elems["oxygen"] = st.altair_chart(base0, use_container_width=True)

                # Flow
                st.subheader("Flow (desired speed vs actual flow)")
                df1 = pd.DataFrame({"x": [], "y": [], "series": []})
                base1 = (
                    alt.Chart(df1)
                    .mark_line()
                    .encode(
                        x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                        y=alt.Y("y:Q", title=None),
                        color=alt.Color("series:N", legend=alt.Legend(orient="top")),
                    )
                )
                chart_elems["flow"] = st.altair_chart(base1, use_container_width=True)

                # Pressure Pump Speed
                st.subheader("Pressure Pump Speed (desired vs actual)")
                df2 = pd.DataFrame({"x": [], "y": [], "series": []})
                base2 = (
                    alt.Chart(df2)
                    .mark_line()
                    .encode(
                        x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                        y=alt.Y("y:Q", title=None),
                        color=alt.Color("series:N", legend=alt.Legend(orient="top")),
                    )
                )
                chart_elems["pressure_pump"] = st.altair_chart(base2, use_container_width=True)

                # Pressure
                st.subheader("Pressure (desired vs actual)")
                df3 = pd.DataFrame({"x": [], "y": [], "series": []})
                base3 = (
                    alt.Chart(df3)
                    .mark_line()
                    .encode(
                        x=alt.X("x:T", title=None, axis=alt.Axis(format="%H:%M:%S")),
                        y=alt.Y("y:Q", title=None),
                        color=alt.Color("series:N", legend=alt.Legend(orient="top")),
                    )
                )
                chart_elems["pressure"] = st.altair_chart(base3, use_container_width=True)

                st.session_state.pt_chart_elements = chart_elems
                # Set painted length so the updater can stream only new points
                painted_len = len(st.session_state.get("pt_data", {}).get("t", []))
                st.session_state._pt_painted_len = painted_len
                st.session_state._pt_charts_key = init_key
            except Exception:
                pass

        _ensure_pt_chart_handles()

        @st.fragment(run_every=0.5)
        def _pt_charts_tick():
            try:
                charts = st.session_state.get("pt_chart_elements") or {}
                data = st.session_state.get("pt_data") or {}
                t = data.get("t") or []
                if not charts or not t:
                    return
                start = int(st.session_state.get("_pt_painted_len") or 0)
                end = len(t)
                if end <= start:
                    return
                # If buffer has wrapped/truncated and painted index is ahead, reinitialize charts
                if start > end:
                    _ensure_pt_chart_handles(force=True)
                    start = 0
                # Build incremental rows for each chart
                rows_oxygen = {"x": [], "y": [], "series": []}
                rows_flow = {"x": [], "y": [], "series": []}
                rows_pressure_pump = {"x": [], "y": [], "series": []}
                rows_pressure = {"x": [], "y": [], "series": []}
                for i in range(start, end):
                    x_ts = pd.to_datetime(int(t[i]), unit="s")
                    # Oxygen: desired and measured (3 sensors)
                    rows_oxygen["x"].extend([x_ts, x_ts, x_ts, x_ts])
                    rows_oxygen["y"].extend([
                        float(data.get("ox_desired", [0.0])[i] if len(data.get("ox_desired", [])) > i else 0.0),
                        float(data.get("ox_meas1", [0.0])[i] if len(data.get("ox_meas1", [])) > i else 0.0),
                        float(data.get("ox_meas2", [0.0])[i] if len(data.get("ox_meas2", [])) > i else 0.0),
                        float(data.get("ox_meas3", [0.0])[i] if len(data.get("ox_meas3", [])) > i else 0.0),
                    ])
                    rows_oxygen["series"].extend(["Desired", "Measured 1", "Measured 2", "Measured 3"])
                    # Flow
                    rows_flow["x"].extend([x_ts, x_ts])
                    rows_flow["y"].extend([
                        float(data.get("flow_desired", [0.0])[i] if len(data.get("flow_desired", [])) > i else 0.0),
                        float(data.get("flow_actual", [0.0])[i] if len(data.get("flow_actual", [])) > i else 0.0),
                    ])
                    rows_flow["series"].extend(["Desired", "Actual"])
                    # Pressure Pump Speed
                    rows_pressure_pump["x"].extend([x_ts, x_ts])
                    rows_pressure_pump["y"].extend([
                        float(data.get("press_pump_desired", [0.0])[i] if len(data.get("press_pump_desired", [])) > i else 0.0),
                        float(data.get("press_pump_actual", [0.0])[i] if len(data.get("press_pump_actual", [])) > i else 0.0),
                    ])
                    rows_pressure_pump["series"].extend(["Desired", "Actual"])
                    # Pressure
                    rows_pressure["x"].extend([x_ts, x_ts])
                    rows_pressure["y"].extend([
                        float(data.get("pressure_desired", [0.0])[i] if len(data.get("pressure_desired", [])) > i else 0.0),
                        float(data.get("pressure_actual", [0.0])[i] if len(data.get("pressure_actual", [])) > i else 0.0),
                    ])
                    rows_pressure["series"].extend(["Desired", "Actual"])

                try:
                    if charts.get("oxygen"):
                        charts["oxygen"].add_rows(pd.DataFrame(rows_oxygen))
                except Exception:
                    pass
                try:
                    if charts.get("flow"):
                        charts["flow"].add_rows(pd.DataFrame(rows_flow))
                except Exception:
                    pass
                try:
                    if charts.get("pressure_pump"):
                        charts["pressure_pump"].add_rows(pd.DataFrame(rows_pressure_pump))
                except Exception:
                    pass
                try:
                    if charts.get("pressure"):
                        charts["pressure"].add_rows(pd.DataFrame(rows_pressure))
                except Exception:
                    pass
                st.session_state._pt_painted_len = end
            except Exception:
                pass

        _pt_charts_tick()

        @st.fragment(run_every=0.5)
        def _pt_live_collector():
            mod = st.session_state.get("pt_selected_module")
            if not mod:
                return
            try:
                topic = f"live-sensor-data/{mod}"
                sub_key = ("_pt_live_topic", topic)
                if st.session_state.get("_pt_live_topic") != topic:
                    try:
                        get_mqtt().subscribe(topic)
                        st.session_state._pt_live_topic = topic
                    except Exception:
                        pass
                updates = get_mqtt().drain(topic, max_items=500)
                for _, payload in updates:
                    try:
                        if not isinstance(payload, dict):
                            continue
                        if payload.get("message_source") != "data_logger":
                            continue
                        _append_live_point(payload)
                    except Exception:
                        continue
            except Exception:
                pass

        _pt_live_collector()


 


    


