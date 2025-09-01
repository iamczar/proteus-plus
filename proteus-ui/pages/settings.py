import streamlit as st
import subprocess
import os
import sys
from pathlib import Path
import json

st.set_page_config(page_title="Settings", layout="centered")
st.session_state["_current_page_key"] = "proteus_ui_settings"

st.title("Settings")

st.subheader("Proteus Services")

root = Path(__file__).resolve().parents[2]
ecosystem = root / "ecosystem.config.js"

col1, col2 = st.columns(2, gap="small")
with col1:
    if st.button("Restart Proteus", use_container_width=True):
        try:
            # Restart all processes defined in the ecosystem file
            if os.name == "nt":
                subprocess.Popen(f"pm2 restart \"{ecosystem}\"", cwd=str(root), shell=True)
            else:
                subprocess.Popen(["pm2", "restart", str(ecosystem)], cwd=str(root))
            st.success("Restart signals sent.")
        except Exception as e:
            st.error(f"Failed to restart: {e}")
with col2:
    if st.button("Stop Proteus", type="secondary", use_container_width=True):
        try:
            if os.name == "nt":
                subprocess.Popen("pm2 stop all", cwd=str(root), shell=True)
            else:
                subprocess.Popen(["pm2", "stop", "all"], cwd=str(root))
            st.success("Stop signals sent.")
        except Exception as e:
            st.error(f"Failed to stop: {e}")

st.caption(f"ecosystem: {ecosystem}")
