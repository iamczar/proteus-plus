import time
import random
from pathlib import Path

import streamlit as st

from common.utils import inject_button_theme
from common.utils import show_toast
from common.utils import render_toast_area
from services.module_manager import ModuleManager


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

for _sid in SAMPLERS:
    if f"as{_sid}_status" not in st.session_state:
        st.session_state[f"as{_sid}_status"] = "READY"  # READY | WAITING | ERROR
    # Backward-compatible: if previous 'sec' key exists, convert to minutes
    if f"as{_sid}_delay_min" not in st.session_state:
        prev_sec = st.session_state.get(f"as{_sid}_delay_sec", 0)
        st.session_state[f"as{_sid}_delay_min"] = int(prev_sec // 60) if isinstance(prev_sec, int) else 0
    if f"as{_sid}_end_ts" not in st.session_state:
        st.session_state[f"as{_sid}_end_ts"] = None
    if f"as{_sid}_sensor" not in st.session_state:
        st.session_state[f"as{_sid}_sensor"] = random.choice(SENSOR_CHOICES)


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
    status = st.session_state[f"{key_prefix}status"]
    end_ts = st.session_state[f"{key_prefix}end_ts"]

    with st.container(border=True):
        # Unified status panel (text + color)
        if status == "ERROR":
            panel_text, panel_color = "ERROR", "#EF4444"
        elif status == "WAITING":
            panel_text, panel_color = "WAITING TO RUN", "#F59E0B"
        else:
            panel_text, panel_color = "READY", "#10B981"

        st.markdown(
            f"""
            <div style='text-align:center;padding:10px;border-radius:8px;background:{panel_color};color:white;font-weight:800;'>
                {panel_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Time remaining (minutes; show seconds when < 60s)
        remaining_sec_exact = 0
        if status == "WAITING" and end_ts:
            remaining_sec_exact = max(0, int(end_ts - time.time()))
        if remaining_sec_exact < 60:
            display_text = f"{remaining_sec_exact} s"
        else:
            remaining_min = (remaining_sec_exact + 59) // 60
            display_text = f"{remaining_min} min"
        st.markdown(
            f"""
            <div style='text-align:center;padding:10px;border-radius:8px;background:#EAEAF6;color:#111827;font-weight:700;'>
                {display_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Sensor status (display-only)
        sensor_value = st.session_state.get(f"{key_prefix}sensor", "UNKNOWN")
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
        st.number_input(
            "Delay (minutes)",
            min_value=0,
            max_value=24 * 60,
            step=1,
            key=f"{key_prefix}delay_min",
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
                delay_min = int(st.session_state[f"{key_prefix}delay_min"]) or 0
                delay_sec = delay_min * 60
                st.session_state[f"{key_prefix}status"] = "WAITING" if delay_min > 0 else "READY"
                st.session_state[f"{key_prefix}end_ts"] = time.time() + delay_sec if delay_min > 0 else None
                mod = st.session_state.as_selected_module
                _append_log(f">> Auto Sampler {sid} ({mod}) : Waiting for command")
                _append_log(f">> Auto Sampler {sid} ({mod}) : Delay Run Command Received")
                if delay_min > 0:
                    _append_log(f">> Auto Sampler {sid} ({mod}) : Executing in {delay_min} min")
                else:
                    _append_log(f">> Auto Sampler {sid} ({mod}) : Executing now")

        reset_clicked = st.button("RESET", key=f"{key_prefix}reset")
        if reset_clicked:
            st.session_state[f"{key_prefix}status"] = "READY"
            st.session_state[f"{key_prefix}end_ts"] = None
            _append_log(f">> Auto Sampler {sid} : Reset")

        stop_clicked = st.button("STOP", key=f"{key_prefix}stop")
        if stop_clicked:
            st.session_state[f"{key_prefix}status"] = "READY"
            st.session_state[f"{key_prefix}end_ts"] = None
            _append_log(f">> Auto Sampler {sid} : Stop command received")


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
        st.subheader("Logs")

        # Match the same styled log box used on system and cycler logs
        log_box_css = """
        <style>
        .log-box {
            background-color: #252525;
            color: #00FF7D;
            padding: 1em;
            border-radius: 8px;
            height: 420px;
            overflow-y: scroll;
            font-family: monospace;
            font-size: 14px;
            white-space: pre-wrap;
            border: 1px solid #333;
            margin-bottom: 16px;
        }
        </style>
        """
        st.markdown(log_box_css, unsafe_allow_html=True)

        log_area = st.empty()

        def _render_logs():
            content = "\n".join(st.session_state.as_logs)
            log_area.markdown(f"<div class='log-box'>{content}</div>", unsafe_allow_html=True)

        @st.fragment(run_every=1.0)
        def _refresh_logs():
            # Update countdown / transition per sampler
            for sid in SAMPLERS:
                key_prefix = f"as{sid}_"
                status = st.session_state.get(f"{key_prefix}status")
                end_ts = st.session_state.get(f"{key_prefix}end_ts")
                if status == "WAITING" and end_ts:
                    remaining = int(end_ts - time.time())
                    if remaining <= 0:
                        st.session_state[f"{key_prefix}status"] = "READY"
                        st.session_state[f"{key_prefix}end_ts"] = None
                        _append_log(f">> Auto Sampler {sid} : Delay complete. Execution finished.")
                    else:
                        # keep UI fresh by re-rendering during countdown
                        pass

            _render_logs()
            # Re-render headers so time remaining updates
            for ph, sid in zip(header_placeholders, SAMPLERS):
                with ph.container():
                    _render_header(sid)

        _render_logs()
        _refresh_logs()


