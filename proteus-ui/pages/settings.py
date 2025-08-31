import streamlit as st
import subprocess
import sys
from pathlib import Path

st.set_page_config(page_title="Settings", layout="centered")
st.session_state["_current_page_key"] = "proteus_ui_settings"

st.title("Settings")

st.subheader("General Preferences")

# Theme toggle
theme = st.radio(
    "Theme",
    ["Light", "Dark", "Auto"],
    index=2,
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
            subprocess.Popen(["pm2", "restart", str(ecosystem.name)], cwd=str(root))
            st.success("Restart signals sent.")
        except Exception as e:
            st.error(f"Failed to restart: {e}")
with col2:
    if st.button("Stop Proteus", type="secondary", use_container_width=True):
        try:
            subprocess.Popen(["pm2", "stop", "all"], cwd=str(root))
            st.success("Stop signals sent.")
        except Exception as e:
            st.error(f"Failed to stop: {e}")

st.caption(f"ecosystem: {ecosystem}")

st.markdown("---")

st.subheader("Experimental Features")

# Feature toggles
beta_features = {
    "New chart engine": st.toggle("Enable new chart engine"),
    "Realtime sync": st.toggle("Enable realtime sync"),
    "Compact layout": st.toggle("Use compact layout"),
}

st.markdown("---")

# Save settings (in-memory mock)
if st.button("Save Settings"):
    st.success("Settings saved successfully!")
    st.json({
        "theme": theme,
        "language": language,
        "notifications": notifications,
        "username": username,
        "beta_features": beta_features
    })
