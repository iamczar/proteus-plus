import streamlit as st
import subprocess
import os
import sys
from pathlib import Path
import json
from common.utils import load_ui_settings, save_ui_settings

st.set_page_config(page_title="Settings", layout="centered")
st.session_state["_current_page_key"] = "proteus_ui_settings"

st.title("Settings")

st.subheader("General Preferences")

# Load persisted settings
cfg = load_ui_settings()
default_theme = cfg.get("theme", "Auto")

# Theme toggle
theme = st.radio(
    "Theme",
    ["Light", "Dark", "Auto"],
    index=["Light","Dark","Auto"].index(default_theme if default_theme in ("Light","Dark","Auto") else "Auto"),
    help="Choose your display mode"
)

# Language selection
language = st.selectbox(
    "Language",
    ["English", "Spanish", "French", "German"],
    index=0,
    help="Select your preferred language"
)

# Notifications toggle
notifications = st.checkbox("Enable email notifications", value=True)

# Custom username input
username = st.text_input("Display name", value="Guest")

st.markdown("---")

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

st.markdown("---")

# Save settings (persist to file)
if st.button("Save Settings"):
    to_save = {
        "theme": theme,
        "language": language,
        "notifications": notifications,
        "username": username,
    }
    save_ui_settings(to_save)
    st.success("Settings saved successfully!")
