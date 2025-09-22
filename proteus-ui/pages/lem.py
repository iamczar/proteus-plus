import time
from datetime import datetime
from typing import List, Optional

import streamlit as st

from common.utils import inject_button_theme, render_toast_area, show_toast
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


def _publish_sequence_command(module_id: str | int, message: dict) -> None:
    """Publish a generic sequence command envelope to sequence-commands/<module>.

    ModuleHandler forwards any dict with a "command" field to Alpha.
    """
    topic = f"sequence-commands/{module_id}"
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
        except Exception as exc:
            show_toast(f"Failed to start LEM for {mod}: {exc}", "error", source="LEM")
    if modules:
        show_toast("START LEM sent", "success", source="LEM")


def lem_stop(modules: List[str]) -> None:
    for mod in modules:
        if not mod:
            continue
        try:
            _publish_sequence_command(mod, {"command": "stop_lem"})
        except Exception as exc:
            show_toast(f"Failed to stop LEM for {mod}: {exc}", "error", source="LEM")
    if modules:
        show_toast("STOP LEM sent", "warning", source="LEM")


def lem_dispense(media: str, module_id: str, volume_ml: float) -> None:
    try:
        vol = max(0.0, float(volume_ml or 0.0))
    except Exception:
        vol = 0.0
    if not module_id:
        show_toast("No module assigned.", "warning", source="LEM")
        return
    try:
        payload = {
            "command": "lem_dispense",
            "media": str(media),
            "volume_ml": float(vol),
        }
        _publish_sequence_command(module_id, payload)
        show_toast(f"{media} dispense sent to {module_id} ({vol:.2f} mL)", "success", source="LEM")
        # Animate a local progress bar for quick feedback (1–10s based on volume)
        dur = max(1.0, min(10.0, (vol / 200.0) if vol > 0 else 1.0))
        now = time.time()
        st.session_state.lem_progress[str(module_id)] = {"start_ts": now, "end_ts": now + dur}
    except Exception as exc:
        show_toast(f"Failed to send dispense: {exc}", "error", source="LEM")


# Toast area
toast_placeholder = st.empty()
render_toast_area(container=toast_placeholder.container())


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
for idx, col in enumerate(cols):
    with col:
        with st.container(border=True):
            # Module selector above column buttons
            options = ["— none —"] + (mods or [])
            current = assignments[idx] if assignments[idx] in (mods or []) else "— none —"
            sel = st.selectbox(
                f"Position {idx+1}",
                options=options,
                index=(options.index(current) if current in options else 0),
                key=f"_lem_select_{idx}",
                label_visibility="collapsed",
            )
            st.session_state.lem_assignments[idx] = None if sel == "— none —" else sel
            mod = st.session_state.lem_assignments[idx]
            # Media buttons
            for media in MEDIA_LIST:
                if st.button(media, use_container_width=True, key=f"lem_btn_{idx}_{media}"):
                    vol = float(st.session_state.get("lem_volume_ml", 0.0) or 0.0)
                    if not mod:
                        show_toast("Assign a module to this column first.", "warning", source="LEM")
                    else:
                        lem_dispense(media, str(mod), vol)
            # Local progress indicator (animated client-side)
            prog = st.session_state.lem_progress.get(str(mod)) if mod else None
            if prog:
                now = time.time()
                start_ts = float(prog.get("start_ts", now))
                end_ts = float(prog.get("end_ts", now))
                if end_ts <= now:
                    # Done – clear
                    try:
                        del st.session_state.lem_progress[str(mod)]
                    except Exception:
                        pass
                    st.progress(0)
                else:
                    pct = int(max(0, min(100, ((now - start_ts) / max(0.001, (end_ts - start_ts))) * 100)))
                    st.progress(pct)


@st.fragment(run_every=0.25)
def _tick_progress():
    # Re-render the progress bars in the current layout by triggering a small placeholder update
    # (Bars are already part of the static layout; this fragment ensures periodic reruns.)
    pass


_tick_progress()


