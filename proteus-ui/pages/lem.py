import time
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path

import streamlit as st

from common.utils import inject_button_theme, show_toast, render_toast_area
from services.module_manager import ModuleManager
from services.mqtt_service import MQTTService


st.set_page_config(page_title="ILEM", layout="wide")
st.title("ILEM")
# Mark current page for cross-page navigation detection
st.session_state["_current_page_key"] = "proteus_ui_lem"

# Consistent button styling (compact like other pages)
inject_button_theme(height="36px", min_width="120px", font_size="14px", padding_x="12px")

MEDIA_LIST: List[str] = ["Media 1", "Media 2", "Flush", "Sterilant"]
ILEM_STATUS_PREFIX = "ilem-status"


# -----------------------------
# Session state (page-local)
# -----------------------------
if "lem_progress" not in st.session_state:
    # module_id (str) -> {start_ts: float, end_ts: float}
    st.session_state.lem_progress = {}
if "lem_logs" not in st.session_state:
    st.session_state.lem_logs = []
# Initialize default config values in session state
st.session_state.setdefault("lem_cfg_target", 10.0)
st.session_state.setdefault("lem_cfg_actual", 22.0)
st.session_state.setdefault("lem_active", False)  # legacy; no longer shown
st.session_state.setdefault("lem_port", "")       # legacy; no longer shown
st.session_state.setdefault("ilem_selected_module", None)

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

def _append_lem_log(message: str) -> None:
    try:
        st.session_state.lem_logs.append(message)
        st.session_state.lem_logs = st.session_state.lem_logs[-300:]
    except Exception:
        pass


def _publish_ilem_command(module_id: str | int, message: dict) -> None:
    """
    Publish an ILEM command for a specific module.

    Topic: ilem-command/<module_id>
    Payload envelope matches example-messages.json:
        {
          "message_source": "proteus-ui",
          "timestamp": "...",
          "message": {
            "command": "lem_cmd",
            "action": "dispense" | "stop",
            ...
          }
        }
    """
    try:
        if module_id is None:
            _append_lem_log("ERROR: No module selected for ILEM command")
            return
        topic = f"ilem-command/{module_id}"
        envelope = {
            "message_source": "proteus-ui",
            "timestamp": datetime.now().isoformat(),
            "message": message or {},
        }
        MQTTService().publish(topic, envelope)
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to publish ILEM command for module {module_id}: {exc}")


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
    """
    Global STOP LEM.

    Sends a stop command to all modules currently assigned in the LEM page
    (columns), via ilem-command/<module_id>.
    """
    try:
        selected = st.session_state.get("ilem_selected_module")
        if not selected:
            _append_lem_log("ERROR: No module selected for STOP LEM")
            return
        inner = {
            "command": "lem_cmd",
            "action": "stop",
        }
        _publish_ilem_command(selected, inner)
        _append_lem_log(f"STOP LEM sent to module {selected}")
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to stop LEM: {exc}")


def lem_dispense(module_id: str | int, media: str, bottle: int, volume_ml: float) -> None:
    try:
        vol = max(0.0, float(volume_ml or 0.0))
    except Exception:
        vol = 0.0
    try:
        inner = {
            "command": "lem_cmd",
            "action": "dispense",
            "media": str(media),
            "bottle": int(bottle),
            "volume_ml": float(vol),
        }
        _publish_ilem_command(module_id, inner)
        _append_lem_log(
            f"DISPENSE {media} {vol:.2f} mL -> bottle {int(bottle)} on module {module_id}"
        )
        # Animate a local progress bar for quick feedback (1–10s based on volume)
        dur = max(1.0, min(10.0, (vol / 200.0) if vol > 0 else 1.0))
        now = time.time()
        key = f"mod_{module_id}_bottle_{int(bottle)}"
        st.session_state.lem_progress[key] = {"start_ts": now, "end_ts": now + dur}
    except Exception as exc:
        _append_lem_log(f"ERROR: Failed to send dispense: {exc}")


# (Toasts removed for LEM page; we use the log area instead.)


def _available_modules() -> List[str]:
    try:
        return ModuleManager().get_available_modules() or []
    except Exception:
        return []


def _drain_ilem_status_to_toasts() -> None:
    """
    Drain ILEM status/ack messages from ilem-status/<module_id> topics and
    push them into the shared toast area for display.

    Only messages for the currently selected module are surfaced to the user.
    """
    try:
        selected = st.session_state.get("ilem_selected_module")
        if not selected:
            return

        topic = f"{ILEM_STATUS_PREFIX}/{selected}"
        MQTTService().subscribe(topic)
        for actual_topic, payload in MQTTService().drain(topic, max_items=200):
            try:
                # Expect full system message envelope:
                # { "message_source": "ilem_controller", "message": { ... } }
                if isinstance(payload, (bytes, str)):
                    try:
                        payload = json.loads(
                            payload if isinstance(payload, str) else payload.decode("utf-8", errors="ignore")
                        )
                    except Exception:
                        continue
                if not isinstance(payload, dict):
                    continue
                inner = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                if not isinstance(inner, dict):
                    continue
                if inner.get("event") != "ilem_cmd_ack":
                    continue
                stage = str(inner.get("stage", ""))
                # Only show controller-level acks in the toast area; if stage is
                # absent (e.g. from older test payloads), accept it as well.
                if stage and stage != "ilem_controller":
                    continue
                accepted = bool(inner.get("accepted", False))
                reason = str(inner.get("reason", "")) if inner.get("reason") is not None else ""
                action = str(inner.get("action", "")) or "command"
                status = "success" if accepted else "error"
                verdict = "ACCEPTED" if accepted else "REJECTED"
                msg = f"Module {selected}: ILEM {action} {verdict}. {reason}"
                show_toast(msg, status=status, source="ILEM Controller")
            except Exception:
                continue
    except Exception:
        # Best-effort; don't break the page if MQTT parsing fails
        pass


# -----------------------------
# Top row: Dispense Volume | ILEM Pump Config | ILEM Module & Media
# Use equal-width columns with a medium gap to avoid visual overlap.
# -----------------------------
left_col, middle_col, right_col = st.columns(3, gap="medium")

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


with middle_col:
    with st.container(border=True):
        st.subheader("ILEM Pump Config")

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

        # Action buttons row (two equal-width columns to avoid overlap)
        cols_btn = st.columns(2)
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


with right_col:
    with st.container(border=True):
        st.subheader("ILEM Module & Media")
        mods = _available_modules()
        available = mods or []
        placeholder = "— Select a module —"
        prev = st.session_state.get("ilem_selected_module")
        if prev is not None and prev not in available:
            prev = None
        if available:
            options = [placeholder] + available
            try:
                default_index = options.index(prev) if prev in options else 0
            except Exception:
                default_index = 0
            sel = st.selectbox(
                "Select module",
                options=options,
                index=default_index,
                key="_ilem_select_module",
            )
            if sel == placeholder:
                sel = None
        else:
            sel = None
            st.info("No modules available.")

        st.session_state.ilem_selected_module = sel

        # Media buttons: bottle 1..4
        for btn_idx, media in enumerate(MEDIA_LIST):
            if st.button(media, use_container_width=True, key=f"lem_btn_single_{btn_idx}"):
                vol = float(st.session_state.get("lem_volume_ml", 0.0) or 0.0)
                bottle_index = btn_idx + 1
                if sel:
                    lem_dispense(sel, media, bottle_index, vol)
                else:
                    _append_lem_log(f"ERROR: No module selected; cannot dispense {media}")


# ILEM ack toasts between controls and logs
_drain_ilem_status_to_toasts()
toast_placeholder = st.empty()
render_toast_area(max_messages=3, container=toast_placeholder.container())

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


