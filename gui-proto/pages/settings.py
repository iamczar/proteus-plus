import streamlit as st

st.set_page_config(page_title="Settings", layout="centered")

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
