import time
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path

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
# Initialize default config values in session state
st.session_state.setdefault("lem_cfg_target", 10.0)
st.session_state.setdefault("lem_cfg_actual", 22.0)
st.session_state.setdefault("lem_active", False)
st.session_state.setdefault("lem_port", "")

# Persisted UI settings file (proteus-ui/data/settings.json)
_ui_settings_path = Path(__file__).resolve().parents[1] / "data" / "settings.json"

def _load_ui_settings_default_volume() -> float:
    try:
        if _ui_settings_path.exists():
            data = json.loads(_ui_settings_path.read_text(encoding="utf-8"))
            v = data.get("lem_volume_ml")
            if isinstance(v, (int, float)):
                return float(v)
    except Exception:
        pass
    return 0.0

def _save_ui_settings_volume(v: float) -> None:
    try:
        data = {}
        if _ui_settings_path.exists():
            try:
                data = json.loads(_ui_settings_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data["lem_volume_ml"] = float(v)
        _ui_settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

if "lem_volume_ml" not in st.session_state:
    st.session_state.lem_volume_ml = _load_ui_settings_default_volume()

# -----------------------------
# LEM status chip/panel (above first row)
# -----------------------------
_status_mqtt = MQTTService()
_status_mqtt.subscribe("module_controller/lem-status")

def _drain_lem_status() -> bool:
    changed = False
    for _, data in _status_mqtt.drain("module_controller/lem-status", max_items=50):
        try:
            if isinstance(data, (bytes, str)):
                data = json.loads(data) if isinstance(data, str) else json.loads(data.decode("utf-8", errors="ignore"))
            new_active = bool(data.get("lem_active", False))
            new_port = str(data.get("port", ""))
            if st.session_state.get("lem_active") != new_active:
                st.session_state["lem_active"] = new_active
                changed = True
            if st.session_state.get("lem_port") != new_port:
                st.session_state["lem_port"] = new_port
                changed = True
        except Exception:
            pass
    return changed

@st.fragment(run_every=1.0)
def _lem_status_fragment():
    _drain_lem_status()
    status_color = "green" if st.session_state.get("lem_active", False) else "red"
    status_text = "ACTIVE" if st.session_state.get("lem_active", False) else "DISABLED"
    port_text = st.session_state.get("lem_port", "")
    st.markdown(
        f"<div class='lem-chip-wrap'><span class='lem-chip {status_color}'>LEM: {status_text}{(' (' + port_text + ')') if port_text else ''}</span></div>",
        unsafe_allow_html=True,
    )

status_css = """
<style>
.lem-chip { display:inline-block; padding:6px 12px; border-radius:16px; font-weight:600; color:#fff; }
.lem-chip.green { background:#2E7D32; }
.lem-chip.red { background:#C62828; }
.lem-chip-wrap { margin-bottom:8px; }
</style>
"""
st.markdown(status_css, unsafe_allow_html=True)
_lem_status_fragment()



def _append_lem_log(message: str) -> None:
    try:
        st.session_state.lem_logs.append(message)
        st.session_state.lem_logs = st.session_state.lem_logs[-300:]
    except Exception:
        pass


def _publish_lem_command(message: dict) -> None:
    """Publish a generic LEM command envelope without module scoping."""
    topic = "lem-commands"
    envelope = {
        "message_source": "proteus-ui",
        "timestamp": datetime.now().isoformat(),
        "message": message or {},
    }
    MQTTService().publish(topic, envelope)


def _request_config_snapshot() -> None:
    try:
        MQTTService().publish("lem-get-config", {"source": "proteus-ui"})
    except Exception:
        pass


def _update_config(values: dict) -> None:
    try:
        MQTTService().publish("lem-update-config", values)
        _append_lem_log("Sent LEM config update")
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to update config: {exc}")


def lem_stop() -> None:
    try:
        _publish_lem_command({"command": "stop_lem"})
        _append_lem_log("STOP LEM sent")
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to stop LEM: {exc}")


def lem_dispense(media: str, valve_index: int, volume_ml: float) -> None:
    try:
        vol = max(0.0, float(volume_ml or 0.0))
    except Exception:
        vol = 0.0
    try:
        payload = {
            "command": "lem_dispense",
            "media": str(media),
            "valve_index": int(valve_index),
            "volume_ml": float(vol),
        }
        _publish_lem_command(payload)
        _append_lem_log(f"DISPENSE {media} {vol:.2f} mL -> valve {int(valve_index)}")
        # Animate a local progress bar for quick feedback (1–10s based on volume)
        dur = max(1.0, min(10.0, (vol / 200.0) if vol > 0 else 1.0))
        now = time.time()
        st.session_state.lem_progress[f"valve_{int(valve_index)}"] = {"start_ts": now, "end_ts": now + dur}
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to send dispense: {exc}")


# (Toasts removed for LEM page; we use the log area instead.)


def _available_modules() -> List[str]:
    try:
        return ModuleManager().get_available_modules() or []
    except Exception:
        return []


# -----------------------------
# Top row: Left = Dispense Volume, Right = LEM Pump Config
# -----------------------------
left_col, right_col = st.columns([2, 2], gap="small")

with left_col:
    with st.container(border=True):
        st.subheader("Dispense Volume (mL)")
        st.number_input(
            "Volume (mL)",
            min_value=0.0,
            step=10.0,
            key="lem_volume_ml",
        )
        # Persist on change
        _save_ui_settings_volume(st.session_state.get("lem_volume_ml", 0.0))
        if st.button("STOP LEM", type="secondary", use_container_width=True, key="lem_stop_btn"):
            lem_stop()


with right_col:
    with st.container(border=True):
        st.subheader("LEM Pump Config")

        # Subscribe once for config and status
        _mqtt = MQTTService()
        _mqtt.subscribe("lem-config")
        _mqtt.subscribe("lem-status")

        # Drain any pending config snapshots BEFORE rendering inputs so values reflect latest
        def _apply_latest_cfg():
            changed = False
            for _, data in _mqtt.drain("lem-config", max_items=50):
                try:
                    if isinstance(data, (bytes, str)):
                        data = json.loads(data) if isinstance(data, str) else json.loads(data.decode("utf-8", errors="ignore"))
                    tgt = float(data.get("LEM_DISPENSE_TARGET_VOLUME", st.session_state.get("lem_cfg_target", 10.0)))
                    act = float(data.get("LEM_DISPENSE_ACTUAL_VOLUME", st.session_state.get("lem_cfg_actual", 22.0)))
                    if st.session_state.get("lem_cfg_target") != tgt:
                        st.session_state["lem_cfg_target"] = tgt; changed = True
                    if st.session_state.get("lem_cfg_actual") != act:
                        st.session_state["lem_cfg_actual"] = act; changed = True
                except Exception:
                    pass
            return changed

        _apply_latest_cfg()

        # Auto-apply incoming config snapshots and rerun to refresh inputs
        @st.fragment(run_every=1.0)
        def _auto_apply_cfg():
            if _apply_latest_cfg():
                st.rerun()

    # Local editable fields
        colA, colB = st.columns(2, gap="small")
        with colA:
            tgt = st.number_input(
            "Target Volume",
            min_value=0.0001,
            step=1.0,
            key="lem_cfg_target",
        )
        with colB:
            act = st.number_input(
            "Actual Volume",
            min_value=0.0001,
            step=1.0,
            key="lem_cfg_actual",
        )

        cols_btn = st.columns([1,1,6])
        with cols_btn[0]:
            if st.button("Get Config", key="lem_btn_getcfg", use_container_width=True):
                _request_config_snapshot()
                # Briefly poll for the snapshot and apply immediately
                start = time.time()
                applied = False
                while time.time() - start < 1.0:  # up to 1s
                    if _apply_latest_cfg():
                        applied = True
                        break
                    time.sleep(0.05)
                if applied:
                    st.rerun()
        with cols_btn[1]:
            if st.button("Update Config", key="lem_btn_setcfg", use_container_width=True):
                _update_config({
                    "LEM_DISPENSE_TARGET_VOLUME": float(st.session_state.get("lem_cfg_target", 10.0)),
                    "LEM_DISPENSE_ACTUAL_VOLUME": float(st.session_state.get("lem_cfg_actual", 22.0))
                })

        # Also reflect status messages to the log box (light polling here)
        for _, data in _mqtt.drain("lem-status", max_items=50):
            try:
                _append_lem_log(str(data))
            except Exception:
                pass

        # Trigger refresh via Get Config only


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
            # Media buttons mapped to valve indices (1..16) by column and button position
            for btn_idx, media in enumerate(MEDIA_LIST):
                if st.button(media, use_container_width=True, key=f"lem_btn_{idx}_{btn_idx}"):
                    vol = float(st.session_state.get("lem_volume_ml", 0.0) or 0.0)
                    valve_index = (idx * 4) + btn_idx + 1
                    lem_dispense(media, valve_index, vol)
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

    @st.fragment(run_every=1.0)
    def _refresh_lem_logs():
        _render_lem_logs()

    _render_lem_logs()
    _refresh_lem_logs()


