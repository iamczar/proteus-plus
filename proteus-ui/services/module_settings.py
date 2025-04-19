import streamlit as st
from common.utils import show_toast


def update_module_id():
    st.session_state.module_id = st.session_state.temp_module_id
    show_toast(f"Selected module: **{st.session_state.module_id}**", "info")


def scan_for_modules():
    show_toast("Scanning for modules...", "info")


@st.dialog("System Shutdown")
def shutdown_dialog():
    st.write(f'Are you sure you want to shutdown the system?')
    # split buttons horizontally with cols
    col1, col2 = st.columns(2)
    with col1:
        st.button("Yes", on_click=shutdown_system, use_container_width=True, type="secondary")
    with col2:
        if st.button("No", use_container_width=True, type="primary"):
            st.rerun()


def shutdown_system():
    show_toast("Shutting down system...", "warning")


def render_module_settings():
    # Initialize session state variables
    if 'module_id' not in st.session_state:
        st.session_state.module_id = None
    st.sidebar.header("Module Settings")

    # Operation Mode with session state
    available_modules = [None, 1001, 3006, 2501, 2502]
    selected_mode = st.sidebar.selectbox(
        "Module ID",
        available_modules,
        key="temp_module_id",
        on_change=update_module_id,
        index=available_modules.index(st.session_state.module_id)
    )

    st.sidebar.button("Scan for Modules", on_click=scan_for_modules)
    st.sidebar.button("Shutdown System", on_click=shutdown_dialog)

    # Return current settings
    return {
        "module_id": st.session_state.module_id,
    }
