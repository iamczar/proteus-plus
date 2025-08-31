import time
import random
from pathlib import Path

import streamlit as st

from common.utils import inject_button_theme
from common.utils import show_toast
from common.utils import render_toast_area
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService


st.set_page_config(page_title="Auto Sampler Control", layout="wide")
st.title("Auto Sampler Control")
# Mark current page for cross-page navigation detection
st.session_state["_current_page_key"] = "proteus_ui_auto_sampler"

# Consistent button styling (compact)
inject_button_theme(height="32px", min_width="110px", font_size="14px", padding_x="10px")

# Minor CSS tweaks: limit image height
st.markdown(
    """
    <style>
    /* compact page spacing */
    .as-image-wrapper { margin: 2px 0 6px 0; }
    /* Shared sampler image size */
    .as-image-wrapper img { max-height: 150px; object-fit: contain; }
    /* Make all buttons fill the container width (match number input width) */
    div.stButton > button { width: 100%; min-width: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Page-local state per sampler (prefixed "as{n}_")
# -----------------------------
SAMPLERS = [1, 2, 3]
SENSOR_CHOICES = ["BOTTOM", "HOME", "TOP", "UNKNOWN"]

if "as_selected_module" not in st.session_state:
    st.session_state.as_selected_module = None
if "as_logs" not in st.session_state:
    st.session_state.as_logs = []
for _sid in [1, 2, 3]:
    key = f"as_logs_{_sid}"
    if key not in st.session_state:
        st.session_state[key] = []

for _sid in SAMPLERS:
    if f"as{_sid}_status" not in st.session_state:
        st.session_state[f"as{_sid}_status"] = "READY"  # READY | WAITING | ERROR
    # Delay input in hh:mm (store hours, minutes separately)
    if f"as{_sid}_delay_h" not in st.session_state:
        st.session_state[f"as{_sid}_delay_h"] = 0
    if f"as{_sid}_delay_m" not in st.session_state:
        st.session_state[f"as{_sid}_delay_m"] = 0
    if f"as{_sid}_sensor" not in st.session_state:
        st.session_state[f"as{_sid}_sensor"] = random.choice(SENSOR_CHOICES)
    if f"as{_sid}_state" not in st.session_state:
        st.session_state[f"as{_sid}_state"] = "READY"
    if f"as{_sid}_hold_end_ts" not in st.session_state:
        st.session_state[f"as{_sid}_hold_end_ts"] = None
    if f"as{_sid}_delay_str" not in st.session_state:
        st.session_state[f"as{_sid}_delay_str"] = "0:00"
    if f"as{_sid}_holding_remaining" not in st.session_state:
        st.session_state[f"as{_sid}_holding_remaining"] = None


def _append_log(message: str) -> None:
    # Keep last 200 lines
    st.session_state.as_logs.append(message)
    st.session_state.as_logs = st.session_state.as_logs[-200:]


# -----------------------------
# Module selection (standalone)
# -----------------------------
modules = ModuleManager().get_available_modules()
with st.container(border=True):
    modules = modules or []
    if not modules:
        st.info("No modules detected.")
    else:
        placeholder_label = "— Select a module —"
        previous_value = st.session_state.get("as_selected_module")

        # If previous selection is no longer available, clear it
        if previous_value is not None and previous_value not in modules:
            try:
                del st.session_state["as_selected_module"]
            except Exception:
                pass
            previous_value = None

        if previous_value is None:
            chosen = st.selectbox(
                label="Module Selection (local):",
                options=[placeholder_label] + modules,
                index=0,
                key="_as_module_select_first",
            )
        else:
            chosen = st.selectbox(
                label="Module Selection (local):",
                options=modules,
                index=(modules.index(previous_value) if previous_value in modules else 0),
                key="_as_module_select_final",
            )

        # Update selection only when a real module is chosen
        if chosen != placeholder_label and chosen != previous_value:
            st.session_state.as_selected_module = chosen
            show_toast(f"Selected module: **{chosen}**", "success", source="Module Selection (local)")
            _append_log(f">> Local module selected: {chosen}")
            st.rerun()


# Toast area between module selection and sampler UI
toast_placeholder = st.empty()
# Initial paint
render_toast_area(container=toast_placeholder.container())

@st.fragment(run_every=0.4)
def _update_toasts():
    render_toast_area(container=toast_placeholder.container())

_update_toasts()


# -----------------------------
# Layout: left (headers + image + controls), right (log)
# -----------------------------
left_area, right_area = st.columns([1.5, 2.1], gap="small")


def _status_chip(label: str, active: bool, color: str) -> None:
    bg = color if active else "#F3F4F6"
    fg = "white" if active else "#111827"
    st.markdown(
        f"""
        <div style='text-align:center;padding:10px;border-radius:8px;background:{bg};color:{fg};font-weight:700;'>
            {label}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_header(sid: int) -> None:
    key_prefix = f"as{sid}_"
    status = str(st.session_state.get(f"{key_prefix}status", "READY"))
    sensor_value = st.session_state.get(f"{key_prefix}sensor", "UNKNOWN")
    # Remaining hold time countdown
    end_ts = st.session_state.get(f"{key_prefix}hold_end_ts")
    # If firmware reports holding remaining, prefer that
    holding_remaining = st.session_state.get(f"{key_prefix}holding_remaining")
    remaining_text = "0 s"
    if isinstance(holding_remaining, (int, float)) and holding_remaining > 0:
        rem = int(holding_remaining)
        h = rem // 3600
        m = (rem % 3600) // 60
        s = rem % 60
        if h > 0:
            remaining_text = f"{h}:{m:02d}:{s:02d}"
        else:
            remaining_text = f"{m:02d}:{s:02d}"
    elif isinstance(end_ts, (int, float)) and end_ts > time.time():
        rem = int(end_ts - time.time())
        h = rem // 3600
        m = (rem % 3600) // 60
        s = rem % 60
        if h > 0:
            remaining_text = f"{h}:{m:02d}:{s:02d}"
        else:
            remaining_text = f"{m:02d}:{s:02d}"

    with st.container(border=True):
        # Map status/state to friendly text and color
        raw_state = str(st.session_state.get(f"{key_prefix}state", "")).lower()
        raw_status = status.lower()
        def friendly(name: str) -> str:
            name = (name or "").strip().lower()
            mapping = {
                "waiting_for_command": "WAITING FOR COMMAND",
                "moving_to_bottom": "MOVING TO BOTTOM",
                "holding_position": "HOLDING POSITION",
                "moving_to_home": "MOVING TO HOME",
                "moving_to_top": "MOVING TO TOP",
                "stopped": "STOPPED",
                "extraction_complete": "EXTRACTION COMPLETE",
                "error": "ERROR",
                "ready": "READY",
                "home": "HOME",
                "top": "TOP",
                "bottom": "BOTTOM",
            }
            if name in mapping:
                return mapping[name]
            # Fallback from class name like WaitingForCommandState
            if name.endswith("state"):
                name = name[:-5]
            name = name.replace("_", " ").strip()
            return name.upper() if name else "READY"
        # Prefer status if present, else map state
        panel_text = friendly(raw_status or raw_state)
        # Color heuristic
        if "error" in raw_status or "error" in raw_state:
            panel_color = "#EF4444"
        elif any(tag in (raw_status, raw_state) for tag in ["stopped", "extraction_complete"]):
            panel_color = "#F59E0B"
        elif any(tag in (raw_status, raw_state) for tag in ["waiting_for_command", "ready"]):
            panel_color = "#10B981"
        else:
            panel_color = "#10B981"

        st.markdown(
            f"""
            <div style='text-align:center;padding:10px;border-radius:8px;background:{panel_color};color:white;font-weight:800;'>
                {panel_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Middle chip: remaining hold time (updates every refresh)
        st.markdown(
            f"""
            <div style='text-align:center;padding:10px;border-radius:8px;background:#EAEAF6;color:#111827;font-weight:700;'>
                {remaining_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Sensor status (display-only)
        st.markdown(
            f"""
            <div style='text-align:center;padding:10px;border-radius:8px;background:#F59E0B;color:#111827;font-weight:800;'>
                {sensor_value}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Bottom spacer to mirror top gap
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


def _render_controls(sid: int) -> None:
    key_prefix = f"as{sid}_"
    # Controls (vertical)
    with st.container(border=True):
        st.text_input(
            "Sample Collect Delay (hh:mm)",
            key=f"{key_prefix}delay_str",
            help="Enter hours and minutes, e.g., 0:30 or 1:15",
        )

        def require_selection() -> bool:
            if not st.session_state.as_selected_module:
                _append_log(">> Auto Sampler: No module selected.")
                st.warning("Select a module first.")
                return False
            return True

        run_clicked = st.button("RUN", key=f"{key_prefix}run")
        if run_clicked:
            if require_selection():
                # Parse hh:mm to decimal hours for hold_time
                delay_str = str(st.session_state.get(f"{key_prefix}delay_str", "0:00")).strip()
                try:
                    parts = delay_str.split(":")
                    if len(parts) == 1:
                        h, m = int(parts[0] or 0), 0
                    else:
                        h, m = int(parts[0] or 0), int(parts[1] or 0)
                        m = max(0, min(59, m))
                except Exception:
                    h, m = 0, 0
                hold_time_hours = float(h) + float(m)/60.0
                mod = st.session_state.as_selected_module
                # Publish MQTT command
                try:
                    topic = f"autosampler-command/{mod}"
                    envelope = {
                        "message_source": "proteus-ui",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "message": {
                            "command": "auto_sampler_cmd",
                            "sampler_id": int(sid),
                            "cmd": 2,  # RUN
                            "hold_time": hold_time_hours,
                        },
                    }
                    MQTTService().publish(topic, envelope)
                    show_toast(f"RUN sent to sampler {sid}", "success", source="Auto Sampler")
                    # Start local countdown for display
                    if hold_time_hours > 0:
                        st.session_state[f"{key_prefix}hold_end_ts"] = time.time() + int(hold_time_hours * 3600)
                    else:
                        st.session_state[f"{key_prefix}hold_end_ts"] = None
                except Exception as exc:
                    show_toast(f"Failed to send RUN: {exc}", "error", source="Auto Sampler")

        reset_clicked = st.button("RESET", key=f"{key_prefix}reset")
        if reset_clicked:
            if require_selection():
                mod = st.session_state.as_selected_module
                try:
                    topic = f"autosampler-command/{mod}"
                    envelope = {
                        "message_source": "proteus-ui",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "message": {
                            "command": "auto_sampler_cmd",
                            "sampler_id": int(sid),
                            "cmd": 1,  # RESET
                            "hold_time": 0.0,
                        },
                    }
                    MQTTService().publish(topic, envelope)
                    show_toast(f"RESET sent to sampler {sid}", "info", source="Auto Sampler")
                    st.session_state[f"{key_prefix}hold_end_ts"] = None
                except Exception as exc:
                    show_toast(f"Failed to send RESET: {exc}", "error", source="Auto Sampler")

        stop_clicked = st.button("STOP", key=f"{key_prefix}stop")
        if stop_clicked:
            if require_selection():
                mod = st.session_state.as_selected_module
                try:
                    topic = f"autosampler-command/{mod}"
                    envelope = {
                        "message_source": "proteus-ui",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "message": {
                            "command": "auto_sampler_cmd",
                            "sampler_id": int(sid),
                            "cmd": 0,  # STOP
                            "hold_time": 0.0,
                        },
                    }
                    MQTTService().publish(topic, envelope)
                    show_toast(f"STOP sent to sampler {sid}", "warning", source="Auto Sampler")
                    st.session_state[f"{key_prefix}hold_end_ts"] = None
                except Exception as exc:
                    show_toast(f"Failed to send STOP: {exc}", "error", source="Auto Sampler")

        # Guidance: if sampler requires RESET, show hint below controls
        try:
            st_state = str(st.session_state.get(f"{key_prefix}status", "")).lower()
            if st_state in ("stopped", "extraction_complete", "error"):
                st.caption("Reset required before running again.")
        except Exception:
            pass


# Left side: headers, image, controls
with left_area:
    # Header panels (status + time remaining + sensor) above image
    header_cols = st.columns([1,1,1], gap="small")
    header_placeholders = []
    for col, sid in zip(header_cols, SAMPLERS):
        with col:
            ph = st.empty()
            header_placeholders.append(ph)
            with ph.container():
                _render_header(sid)

    # Single shared image aligned with samplers
    image_path_top = Path(__file__).resolve().parents[1] / "assets" / "auto_sampler.png"
    if image_path_top.exists():
        st.markdown("<div class='as-image-wrapper'>", unsafe_allow_html=True)
        st.image(str(image_path_top), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Place the provided auto sampler image at `proteus-ui/assets/auto_sampler.png`.")

    # Controls below image
    control_cols = st.columns([1,1,1], gap="small")
    control_placeholders = []
    for col, sid in zip(control_cols, SAMPLERS):
        with col:
            ph = st.empty()
            control_placeholders.append(ph)
            with ph.container():
                _render_controls(sid)


# -----------------------------
# Right: logs
# -----------------------------
with right_area:
    with st.container(border=True):
        st.subheader("Auto Sampler Logs")

        # Stacked log boxes (one per sampler) for longer entries
        log_box_css = """
        <style>
        .log-box { background-color: #252525; color: #00FF7D; padding: 1em; border-radius: 8px;
                   height: 240px; overflow-y: scroll; font-family: monospace; font-size: 14px;
                   white-space: pre-wrap; border: 1px solid #333; }
        .log-title { font-weight: 700; margin: 0 0 6px 0; }
        </style>
        """
        st.markdown(log_box_css, unsafe_allow_html=True)

        log_area_1 = st.empty()
        log_area_2 = st.empty()
        log_area_3 = st.empty()

        def _render_logs():
            def render_for(idx: int, area):
                lines = st.session_state.get(f"as_logs_{idx}", [])[-200:]
                html = f"<div class='log-title'>Sampler {idx}</div>" + \
                       f"<div class='log-box'>{'\n'.join(lines)}</div>"
                area.markdown(html, unsafe_allow_html=True)
            render_for(1, log_area_1)
            render_for(2, log_area_2)
            render_for(3, log_area_3)

        @st.fragment(run_every=0.5)
        def _refresh_logs():
            # Drain autosampler status for selected module
            mod = st.session_state.get("as_selected_module")
            if mod:
                # Ensure subscription exists for the selected module
                sub_key = "_as_status_sub"
                want_topic = f"autosampler-status/{mod}"
                if st.session_state.get(sub_key) != want_topic:
                    try:
                        MQTTService().subscribe(want_topic)
                        st.session_state[sub_key] = want_topic
                    except Exception:
                        pass
                topic = f"autosampler-status/{mod}"
                try:
                    for _, payload in MQTTService().drain(topic, max_items=500):
                        if not isinstance(payload, dict):
                            continue
                        inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                        sid = inner.get("sampler_id") or inner.get("sampler")
                        if sid in (1, 2, 3):
                            prefix = f"as{int(sid)}_"
                            st.session_state[f"{prefix}status"] = str(inner.get("status", st.session_state.get(f"{prefix}status", "")))
                            st.session_state[f"{prefix}state"] = str(inner.get("state", st.session_state.get(f"{prefix}state", "")))
                            if "sensor_state" in inner:
                                st.session_state[f"{prefix}sensor"] = str(inner.get("sensor_state"))
                            # Append per-sampler log with description
                            try:
                                st_state = st.session_state[f"{prefix}state"]
                                st_stat = st.session_state[f"{prefix}status"]
                                st_sens = st.session_state.get(f"{prefix}sensor", "")
                                desc = str(inner.get("description", ""))
                                # Capture holding remaining seconds if reported in description
                                try:
                                    if st_stat == "holding_position" and "remaining" in desc:
                                        # Extract number before 's remaining'
                                        import re
                                        m = re.search(r"([0-9]+\.?[0-9]*)s remaining", desc)
                                        if m:
                                            secs = float(m.group(1))
                                            st.session_state[f"{prefix}holding_remaining"] = int(secs)
                                except Exception:
                                    pass
                                key = f"as_logs_{int(sid)}"
                                new_line = f"{st_stat} | {st_state} | {desc} | sensor={st_sens}"
                                # Deduplicate consecutive identical lines
                                prev = st.session_state[key][-1] if st.session_state[key] else None
                                if prev != new_line:
                                    st.session_state[key].append(new_line)
                                st.session_state[key] = st.session_state[key][-200:]
                            except Exception:
                                pass
                        # Optional toast for ack
                        if inner.get("command") == "auto_sampler_cmd_ack":
                            show_toast("Auto sampler command acknowledged", "success", source="Auto Sampler")
                            try:
                                key = f"as_logs_{int(inner.get('sampler_id', 0) or 0)}"
                                if key in st.session_state:
                                    st.session_state[key].append(
                                        f"ACK | sampler {inner.get('sampler_id')} -> {inner.get('status','dispatched')}"
                                    )
                            except Exception:
                                pass
                except Exception:
                    pass

            _render_logs()
            # Re-render headers so time remaining updates
            for ph, sid in zip(header_placeholders, SAMPLERS):
                with ph.container():
                    _render_header(sid)

        _render_logs()
        _refresh_logs()


