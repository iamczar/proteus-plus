import time
import streamlit as st

from datetime import datetime
from services.module_manager import ModuleManager
from common.utils import render_toast_area

st.set_page_config(page_title="Cycler Logs", layout="wide")
st.title("Cycler Logs")
# Mark current page for cross-page navigation detection
st.session_state["_current_page_key"] = "proteus_ui_cycler_logs"

# Module selection and toast area
ModuleManager().select_module()

# Stable placeholder for toasts
toast_placeholder = st.empty()
render_toast_area(container=toast_placeholder.container())

@st.fragment(run_every=0.5)
def update_toasts():
    render_toast_area(container=toast_placeholder.container())

# Ensure the toast updater is active
update_toasts()

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
}
</style>
"""

st.markdown(log_box_css, unsafe_allow_html=True)

# Create a container to hold the logs
log_area = st.empty()

# ---------- Non-blocking log model ----------
LOG_KEY = "cycler_logs"


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


# Initial paint and seed with one dummy log so the area isn't empty
ensure_log_state()
if not st.session_state[LOG_KEY]:
    append_log("This is a dummy log message")
render_logs()


# Periodic dummy updates to simulate incoming messages
@st.fragment(run_every=2.0)
def simulate_incoming_logs():
    append_log("This is a dummy log message")
    render_logs()

# Ensure the simulator is active
simulate_incoming_logs()
