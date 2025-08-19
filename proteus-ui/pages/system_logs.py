import time
from datetime import datetime

import streamlit as st
from services.module_manager import ModuleManager
from common.utils import render_toast_area
from common.utils import inject_button_theme
from services.mqtt_service import MQTTService

st.set_page_config(page_title="System Logs", layout="wide")

st.title("System Logs")

# Module selection and toast area
#ModuleManager().select_module()

# Stable placeholder for toasts
#toast_placeholder = st.empty()
#render_toast_area(container=toast_placeholder.container())

# Consistent button styling across the app
inject_button_theme()

#@st.fragment(run_every=0.5)
#def update_toasts():
#    render_toast_area(container=toast_placeholder.container())

# Ensure the toast updater is active
#update_toasts()

# Custom CSS to create a scrollable log box
log_box_css = """
<style>
.log-box {
    background-color: #252525;
    color: #00FF7D;
    padding: 1em;
    border-radius: 8px;
    height: 500px;
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

# Create a container to hold the logs
log_area = st.empty()

# ---------- Non-blocking log model ----------
LOG_KEY = "system_logs"
MQTT_TOPIC = "logs/ui_test"  # adjust as needed


def ensure_log_state():
    if LOG_KEY not in st.session_state:
        st.session_state[LOG_KEY] = []


def append_log(message: str, level: str = "INFO") -> None:
    ensure_log_state()
    st.session_state[LOG_KEY].append(f"{datetime.now()} [{level}] - {message}")
    st.session_state[LOG_KEY] = st.session_state[LOG_KEY][-100:]


def render_logs():
    ensure_log_state()
    log_content = "\n".join(st.session_state[LOG_KEY])
    log_area.markdown(f"<div class='log-box'>{log_content}</div>", unsafe_allow_html=True)


# --- MQTT wiring ---
mqtt = MQTTService()
# Subscribe once per session
if "_mqtt_subscribed_logs" not in st.session_state:
    try:
        mqtt.subscribe(MQTT_TOPIC, qos=0)
        st.session_state["_mqtt_subscribed_logs"] = True
        append_log(f"Subscribed to MQTT topic: {MQTT_TOPIC}")
    except Exception as e:
        append_log(f"MQTT subscribe failed: {e}", level="ERROR")

# Initial paint
ensure_log_state()
render_logs()


# Periodic drain of MQTT messages into the log area
@st.fragment(run_every=0.5)
def drain_mqtt_and_render():
    for topic, data in mqtt.drain(MQTT_TOPIC):
        append_log(f"{topic} | {data}")
    render_logs()

drain_mqtt_and_render()

# Simple publish UI (optional)
with st.expander("Publish test message"):
    c1, c2 = st.columns([3, 1])
    with c1:
        out_topic = st.text_input("Topic", value="logs/ui_test")
        payload = st.text_input("Payload (JSON or text)", value="{\"hello\": \"world\"}")
    with c2:
        if st.button("Publish"):
            try:
                # Try to preserve JSON if valid
                import json
                try:
                    obj = json.loads(payload)
                except Exception:
                    obj = payload
                mqtt.publish(out_topic, obj)
                append_log(f"Published to {out_topic}")
            except Exception as e:
                append_log(f"Publish failed: {e}", level="ERROR")
