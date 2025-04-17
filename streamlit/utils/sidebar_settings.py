import streamlit as st


def initialize_settings():
    """Initialize session state variables if they don't exist."""
    if 'operation_mode' not in st.session_state:
        st.session_state.operation_mode = "Standard"
    if 'data_source' not in st.session_state:
        st.session_state.data_source = "Local"
    if 'refresh_rate' not in st.session_state:
        st.session_state.refresh_rate = "10s"
    if 'view_options' not in st.session_state:
        st.session_state.view_options = ["Metrics", "Charts"]


def update_operation_mode():
    st.session_state.operation_mode = st.session_state.temp_operation_mode


def update_data_source():
    st.session_state.data_source = st.session_state.temp_data_source


def update_refresh_rate():
    st.session_state.refresh_rate = st.session_state.temp_refresh_rate


def update_view_options():
    st.session_state.view_options = st.session_state.temp_view_options


def render_module_settings():
    """Render common module settings in the sidebar with persistent values."""
    # Initialize session state variables
    initialize_settings()

    st.sidebar.header("Module Settings")

    # Operation Mode with session state
    selected_mode = st.sidebar.selectbox(
        "Operation Mode",
        ["Standard", "Advanced", "Debug", "Performance"],
        key="temp_operation_mode",
        on_change=update_operation_mode,
        index=["Standard", "Advanced", "Debug", "Performance"].index(st.session_state.operation_mode)
    )

    # Data Source with session state
    data_source = st.sidebar.selectbox(
        "Data Source",
        ["Local", "Remote", "Cached", "Live Stream"],
        key="temp_data_source",
        on_change=update_data_source,
        index=["Local", "Remote", "Cached", "Live Stream"].index(st.session_state.data_source)
    )

    # Refresh Rate with session state
    refresh_options = ["1s", "5s", "10s", "30s", "1m", "5m", "Off"]
    refresh_rate = st.sidebar.select_slider(
        "Refresh Rate",
        options=refresh_options,
        key="temp_refresh_rate",
        on_change=update_refresh_rate,
        value=st.session_state.refresh_rate
    )

    # View Options with session state
    view_options = st.sidebar.multiselect(
        "View Options",
        ["Metrics", "Charts", "Logs", "Alerts", "Statistics"],
        key="temp_view_options",
        on_change=update_view_options,
        default=st.session_state.view_options
    )

    # Return current settings
    return {
        "mode": st.session_state.operation_mode,
        "data_source": st.session_state.data_source,
        "refresh_rate": st.session_state.refresh_rate,
        "view_options": st.session_state.view_options
    }
