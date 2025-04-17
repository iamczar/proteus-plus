import streamlit as st
import time
from utils.sidebar_settings import render_module_settings

st.title("Test 5 - Advanced UI Elements")

# Add module settings to sidebar
settings = render_module_settings()

# Tabs
tab1, tab2, tab3 = st.tabs(["File Upload", "Progress Indicators", "Notifications"])

with tab1:
    st.header("File Upload Demo")
    uploaded_file = st.file_uploader("Choose a file", type=['csv', 'txt', 'pdf'])
    if uploaded_file is not None:
        file_details = {
            "Filename": uploaded_file.name,
            "FileType": uploaded_file.type,
            "FileSize": f"{uploaded_file.size / 1024:.2f} KB"
        }
        st.json(file_details)

with tab2:
    st.header("Progress Indicators")
    
    col1, col2 = st.columns(2)
    
    with col1:
        progress_bar = st.progress(0)
        if st.button("Run Progress Bar"):
            for i in range(100):
                progress_bar.progress(i + 1)
                time.sleep(0.01)
    
    with col2:
        with st.spinner("Loading..."):
            if st.button("Show Spinner"):
                time.sleep(2)
                st.success("Done!")

with tab3:
    st.header("Notifications")
    
    notification_type = st.selectbox(
        "Select notification type",
        ["Success", "Info", "Warning", "Error"]
    )
    
    message = st.text_input("Enter message", "This is a notification message")
    
    if st.button("Show Notification"):
        if notification_type == "Success":
            st.success(message)
        elif notification_type == "Info":
            st.info(message)
        elif notification_type == "Warning":
            st.warning(message)
        else:
            st.error(message)
