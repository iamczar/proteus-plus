import time
import streamlit as st

from datetime import datetime
from services.module_manager import ModuleManager

st.set_page_config(page_title="Cycler Logs", layout="wide")
st.title("Cycler Logs")

# Module selection
ModuleManager().select_module()

# Custom CSS to create a scrollable log box
log_box_css = """
<style>
.log-box {
    background-color: #f5f5f5;
    color: #1B481B;
    padding: 1em;
    border-radius: 8px;
    height: 500px;
    overflow-y: scroll;
    font-family: monospace;
    font-size: 14px;
    white-space: pre-wrap;
    border: 1px solid #ccc;  /* Light grey border */
}
</style>
"""

st.markdown(log_box_css, unsafe_allow_html=True)

# Create a container to hold the logs
log_area = st.empty()

# Initialize log history in session_state
if "logs" not in st.session_state:
    st.session_state.system_logs = []

# Simulate appending logs
while True:
    st.session_state.system_logs.append(f"{datetime.now()} [INFO] - This is a log message")

    # Keep only the last 100 logs to avoid growing too large
    log_content = "\n".join(st.session_state.system_logs[-100:])

    # Show the logs inside a styled scrollable div
    log_area.markdown(f"<div class='log-box'>{log_content}</div>", unsafe_allow_html=True)

    time.sleep(1)
