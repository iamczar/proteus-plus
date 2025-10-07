import time
import sys

import streamlit as st

from common.utils import inject_button_theme
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService
from datetime import datetime


st.set_page_config(page_title="PID Controls", layout="wide")
st.title("PID Controls")

# Consistent button styling (compact)
inject_button_theme(height="32px", min_width="110px", font_size="14px", padding_x="10px")


# -----------------------------
# Page-local state
# -----------------------------
if "pt_selected_module" not in st.session_state:
    st.session_state.pt_selected_module = None

st.session_state.setdefault("pt_flow_status", {})
st.session_state.setdefault("pt_pressure_status", {})
st.session_state.setdefault("pt_logs", [])
st.session_state.setdefault("pt_pid_override", {"enabled": False})


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
        try:
            if isinstance(message, str) and message.strip().startswith((">>", "<<")):
                logs = st.session_state.get("pt_logs", [])
                logs.append(message)
                st.session_state.pt_logs = logs[-1000:]
        except Exception:
            pass
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
        get_mqtt().publish(topic, envelope)
        _pt_append_log(f">> SEND {payload}")
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


# -----------------------------
# Module selection (shared)
# -----------------------------
ModuleManager().select_module()
global_selected = st.session_state.get("selected_module")
prev_local = st.session_state.get("pt_selected_module")
if global_selected != prev_local:
    st.session_state.pt_selected_module = global_selected
    _pt_append_log(f">> Selected module: {global_selected}")


# -----------------------------
# PID status subscription and polling
# -----------------------------
@st.fragment(run_every=1.0)
def _pid_status_tick():
    mod = st.session_state.get("pt_selected_module")
    if not mod:
        return
    try:
        subs = st.session_state.setdefault("_pt_pid_subs", set())
        need = {
            f"pid-flow-status/{mod}",
            f"pid-pressure-status/{mod}",
            f"alphacommsmanager-status/{mod}",
            f"pid-command-status/{mod}",
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
        t_override = f"pid-command-status/{mod}"

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

        drained_am = get_mqtt().drain(t_am, max_items=50)
        for _, payload in drained_am:
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                cmd = str(inner.get("command", "")).lower() if isinstance(inner, dict) else ""
                status = str(inner.get("status", "")).lower() if isinstance(inner, dict) else ""
                if cmd == "pid_cmd" and status in ("ack", "acknowledged", "received"):
                    _pt_append_log("<< ACK pid_cmd from Alpha")
                    try:
                        if "_pt_last_toggle" in st.session_state:
                            del st.session_state["_pt_last_toggle"]
                    except Exception:
                        pass
            except Exception:
                pass

        # PID override status stream
        for _, payload in get_mqtt().drain(t_override, max_items=200):
            try:
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if isinstance(inner, dict) and inner.get("event") == "pid_override_status":
                    st.session_state.pt_pid_override = {
                        "enabled": bool(inner.get("enabled", False))
                    }
            except Exception:
                pass
    except Exception:
        pass


_pid_status_tick()


# -----------------------------
# Controls UI
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
        # Debug Controls (Override)
        with st.container(border=True):
            st.subheader("Debug Controls")
            mod = st.session_state.get("pt_selected_module")
            ov = st.session_state.get("pt_pid_override") or {"enabled": False}
            enabled = bool(ov.get("enabled", False))
            toggle_label = "Disable Debug Mode" if enabled else "Enable Debug Mode"
            c1, c2 = st.columns([1,1], gap="small")
            with c1:
                if st.button(toggle_label, use_container_width=True):
                    try:
                        ok = _publish_pid_command(mod, {"type": "debug_mode", "enabled": (not enabled)})
                        _pt_append_log(f"dbg: publish debug_mode toggle ok={ok}")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing debug_mode toggle: {e}")
            with c2:
                st.caption(f"Override is {'ON' if enabled else 'OFF'}")

        with st.container(border=True):
            st.subheader("Debug Controls")
            st.caption("Send fake sensor values to Alpha when Debug Mode is enabled")
            o2_val = st.number_input("Oxygen : micromole/liter (decimal fraction, e.g. 0.21)", key="pt_dbg_oxygen", value=0.0)
            c3, c4 = st.columns([1,1], gap="small")
            with c3:
                if st.button("Send Oxygen", disabled=not enabled):
                    try:
                        ok = _publish_pid_command(mod, {"type": "debug_mode", "oxygen": float(o2_val)})
                        _pt_append_log(f"dbg: publish debug oxygen ok={ok}")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing debug oxygen: {e}")
            p_val = st.number_input("Pressure : psi", key="pt_dbg_pressure", value=0.0)
            with c4:
                if st.button("Send Pressure", disabled=not enabled):
                    try:
                        ok = _publish_pid_command(mod, {"type": "debug_mode", "pressure": float(p_val)})
                        _pt_append_log(f"dbg: publish debug pressure ok={ok}")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing debug pressure: {e}")
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

    # Debug toggle checkbox that publishes its state when changed
    try:
        with st.container(border=False):
            st.subheader("Debug Controls")
            debug_checked = st.checkbox("Enable Debug Mode", key="pt_debug_checkbox")
            prev_debug = st.session_state.get("_pt_prev_debug_checkbox", None)
            if prev_debug is None:
                st.session_state["_pt_prev_debug_checkbox"] = debug_checked
            elif debug_checked != prev_debug:
                mod = st.session_state.get("pt_selected_module")
                if mod:
                    _pt_append_log(f">> CLICK Debug checkbox (mod={mod}) state={debug_checked}")
                    try:
                        ok = _publish_pid_command(mod, {"type": "debug_mode", "enabled": bool(debug_checked)})
                        _pt_append_log(f"dbg: publish debug toggle ok={ok}")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing debug toggle: {e}")
                st.session_state["_pt_prev_debug_checkbox"] = debug_checked
    except Exception:
        pass

    if st.session_state.get("pt_debug_checkbox"):
        with st.container(border=True):
            st.subheader("Debug Controls")
            # Row 1: Oxygen + Send
            with st.form("debug_oxygen_form"):
                c1, c2 = st.columns([1, 0.6], gap="small")
                with c1:
                    st.number_input("Oxygen : micromole/liter", key="pt_debug_oxygen")
                with c2:
                    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                    send_o2 = st.form_submit_button("Send Oxygen")
                if send_o2:
                    mod = st.session_state.get("pt_selected_module")
                    _pt_append_log(
                        f">> CLICK Send Debug Oxygen (mod={mod}) O2={st.session_state.pt_debug_oxygen}"
                    )
                    payload = {
                        "type": "debug_mode",
                        "oxygen": float(st.session_state.pt_debug_oxygen)
                    }
                    try:
                        ok = _publish_pid_command(mod, payload)
                        _pt_append_log(f"dbg: publish debug oxygen ok={ok}")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing debug oxygen: {e}")

            # Row 2: Pressure + Send
            with st.form("debug_pressure_form"):
                c3, c4 = st.columns([1, 0.6], gap="small")
                with c3:
                    st.number_input("Pressure : psi", key="pt_debug_pressure")
                with c4:
                    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                    send_p = st.form_submit_button("Send Pressure")
                if send_p:
                    mod = st.session_state.get("pt_selected_module")
                    _pt_append_log(
                        f">> CLICK Send Debug Pressure (mod={mod}) P={st.session_state.pt_debug_pressure}"
                    )
                    payload = {
                        "type": "debug_mode",
                        "pressure": float(st.session_state.pt_debug_pressure),
                    }
                    try:
                        ok = _publish_pid_command(mod, payload)
                        _pt_append_log(f"dbg: publish debug pressure ok={ok}")
                    except Exception as e:
                        _pt_append_log(f"!! error publishing debug pressure: {e}")

