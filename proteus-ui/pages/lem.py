import time
from datetime import datetime
from typing import List, Optional

import streamlit as st

from common.utils import inject_button_theme
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService


st.set_page_config(page_title="LEM", layout="wide")
st.title("LEM")
# Mark current page for cross-page navigation detection
st.session_state["_current_page_key"] = "proteus_ui_lem"

# Consistent button styling (compact like other pages)
inject_button_theme(height="36px", min_width="120px", font_size="14px", padding_x="12px")

MEDIA_LIST: List[str] = ["Media 1", "Media 2", "Flush", "Sterilant"]


# -----------------------------
# Session state (page-local)
# -----------------------------
if "lem_assignments" not in st.session_state:
    # Up to 4 columns; values are module ids as strings or None
    st.session_state.lem_assignments = [None, None, None, None]
if "lem_progress" not in st.session_state:
    # module_id (str) -> {start_ts: float, end_ts: float}
    st.session_state.lem_progress = {}
if "lem_logs" not in st.session_state:
    st.session_state.lem_logs = []


def _append_lem_log(message: str) -> None:
    try:
        st.session_state.lem_logs.append(message)
        st.session_state.lem_logs = st.session_state.lem_logs[-300:]
    except Exception:
        pass


def _publish_sequence_command(module_id: str | int, message: dict) -> None:
    """Publish a generic sequence command envelope to lem-commands/<module>.

    ModuleHandler forwards any dict with a "command" field to Alpha.
    """
    topic = f"lem-commands/{module_id}"
    envelope = {
        "message_source": "proteus-ui",
        "timestamp": datetime.now().isoformat(),
        "message": message or {},
    }
    MQTTService().publish(topic, envelope)


def lem_start(modules: List[str]) -> None:
    for mod in modules:
        if not mod:
            continue
        try:
            _publish_sequence_command(mod, {"command": "start_lem"})
            _append_lem_log(f"START LEM -> {mod}")
        except Exception as exc:
            _append_lem_log(f"ERROR: Failed to start LEM for {mod}: {exc}")
    if modules:
        _append_lem_log("START LEM sent")


def lem_stop(modules: List[str]) -> None:
    for mod in modules:
        if not mod:
            continue
        try:
            _publish_sequence_command(mod, {"command": "stop_lem"})
            _append_lem_log(f"STOP LEM -> {mod}")
        except Exception as exc:
            _append_lem_log(f"ERROR: Failed to stop LEM for {mod}: {exc}")
    if modules:
        _append_lem_log("STOP LEM sent")


def lem_dispense(media: str, module_id: str, volume_ml: float) -> None:
    try:
        vol = max(0.0, float(volume_ml or 0.0))
    except Exception:
        vol = 0.0
    if not module_id:
        _append_lem_log("WARN: No module assigned for dispense request")
        return
    try:
        payload = {
            "command": "lem_dispense",
            "media": str(media),
            "volume_ml": float(vol),
        }
        _publish_sequence_command(module_id, payload)
        _append_lem_log(f"DISPENSE {media} {vol:.2f} mL -> {module_id}")
        # Animate a local progress bar for quick feedback (1–10s based on volume)
        dur = max(1.0, min(10.0, (vol / 200.0) if vol > 0 else 1.0))
        now = time.time()
        st.session_state.lem_progress[str(module_id)] = {"start_ts": now, "end_ts": now + dur}
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to send dispense: {exc}")


# (Toasts removed for LEM page; we use the log area instead.)


def _available_modules() -> List[str]:
    try:
        return ModuleManager().get_available_modules() or []
    except Exception:
        return []


# -----------------------------
# Top controls: volume + global Start/Stop
# -----------------------------
with st.container(border=True):
    st.subheader("Dispense Volume (mL)")
    st.number_input(
        "Volume (mL)",
        min_value=0.0,
        step=10.0,
        value=0.0,
        key="lem_volume_ml",
    )
    col_a, col_b = st.columns(2, gap="small")
    with col_a:
        if st.button("START LEM", use_container_width=True, key="lem_start_btn"):
            assigned = [a for a in st.session_state.lem_assignments if a]
            lem_start(assigned)
    with col_b:
        if st.button("STOP LEM", type="secondary", use_container_width=True, key="lem_stop_btn"):
            assigned = [a for a in st.session_state.lem_assignments if a]
            lem_stop(assigned)


# -----------------------------
# Columns with Media buttons and progress
# -----------------------------
mods = _available_modules()
assignments: List[Optional[str]] = list(st.session_state.get("lem_assignments", [None, None, None, None]))
# Pre-fill first time with first up-to-4 modules
if all(v is None for v in assignments) and mods:
    for i in range(min(4, len(mods))):
        assignments[i] = mods[i]
    st.session_state.lem_assignments = assignments
cols = st.columns(4, gap="small")
# Progress bars (disabled)
# Placeholders for per-column progress bars so we can refresh them periodically
# _lem_progress_placeholders = []
for idx, col in enumerate(cols):
    with col:
        with st.container(border=True):
            # Module selector above column buttons
            available = mods or []
            prev = st.session_state.lem_assignments[idx]
            if prev is not None and prev not in available:
                prev = None
                st.session_state.lem_assignments[idx] = None
            placeholder = "— Select a module —"
            if prev is None:
                initial_options = [placeholder] + available if available else [placeholder]
                sel = st.selectbox(
                    f"Position {idx+1}",
                    options=initial_options,
                    index=0,
                    key=f"_lem_select_first_{idx}",
                    label_visibility="collapsed",
                )
            else:
                final_options = available
                default_index = final_options.index(prev) if prev in available else (0 if final_options else 0)
                sel = st.selectbox(
                    f"Position {idx+1}",
                    options=final_options,
                    index=default_index,
                    key=f"_lem_select_final_{idx}",
                    label_visibility="collapsed",
                )
            if sel not in (None, placeholder) and sel != prev:
                st.session_state.lem_assignments[idx] = sel
                _append_lem_log(f"Selected module for column {idx+1}: {sel}")
                st.rerun()
            mod = st.session_state.lem_assignments[idx]
            # Media buttons
            for media in MEDIA_LIST:
                if st.button(media, use_container_width=True, key=f"lem_btn_{idx}_{media}"):
                    vol = float(st.session_state.get("lem_volume_ml", 0.0) or 0.0)
                    if not mod:
                        _append_lem_log("WARN: Assign a module to this column first before dispensing")
                    else:
                        lem_dispense(media, str(mod), vol)
            # Local progress indicator (animated via periodic fragment)
            # ph = st.empty()
            # _lem_progress_placeholders.append(ph)


# Progress bars (disabled)
# def _render_progress_once():
#     # Render progress bars for each column into their placeholders
#     try:
#         for i, ph in enumerate(_lem_progress_placeholders):
#             mod = st.session_state.lem_assignments[i] if i < len(st.session_state.lem_assignments) else None
#             prog = st.session_state.lem_progress.get(str(mod)) if mod else None
#             with ph.container():
#                 if not prog:
#                     st.progress(0)
#                 else:
#                     now = time.time()
#                     start_ts = float(prog.get("start_ts", now))
#                     end_ts = float(prog.get("end_ts", now))
#                     if end_ts <= now:
#                         try:
#                             del st.session_state.lem_progress[str(mod)]
#                         except Exception:
#                             pass
#                         st.progress(0)
#                     else:
#                         pct = int(max(0, min(100, ((now - start_ts) / max(0.001, (end_ts - start_ts))) * 100)))
#                         st.progress(pct)
#     except Exception:
#         pass
#
# @st.fragment(run_every=0.25)
# def _refresh_progress():
#     _render_progress_once()
#
# _render_progress_once()
# _refresh_progress()

with st.container(border=True):
    st.subheader("LEM Logs")
    # Reuse log styling consistent with other pages
    log_box_css = """
    <style>
    .log-box { background-color: #252525; color: #00FF7D; padding: 1em; border-radius: 8px;
               height: 360px; overflow-y: scroll; font-family: monospace; font-size: 14px;
               white-space: pre-wrap; border: 1px solid #333; margin-bottom: 8px; }
    .log-title { font-weight: 700; margin: 0 0 6px 0; }
    </style>
    """
    st.markdown(log_box_css, unsafe_allow_html=True)

    top_row = st.columns([8, 1], gap="small")
    with top_row[0]:
        st.markdown("<div class='log-title'>Recent events</div>", unsafe_allow_html=True)
    with top_row[1]:
        if st.button("Clear", key="lem_clear_logs", use_container_width=True):
            st.session_state.lem_logs = []

    # Render area
    _lem_log_area = st.empty()

    def _render_lem_logs():
        lines = st.session_state.get("lem_logs", [])[-300:]
        content = "\n".join(lines)
        _lem_log_area.markdown(f"<div class='log-box'>{content}</div>", unsafe_allow_html=True)

    @st.fragment(run_every=0.5)
    def _refresh_lem_logs():
        _render_lem_logs()

    _render_lem_logs()
    _refresh_lem_logs()


