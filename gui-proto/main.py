import os
import streamlit as st

# Home
dashboard_page = st.Page("pages/dashboard.py", title="Dashboard", icon=":material/grid_view:")

# Resources
experiments_page = st.Page("pages/experiments.py", title="Experiments", icon=":material/science:")
graph_view = st.Page("pages/graph_view.py", title="Graph View", icon=":material/show_chart:")
cycler_logs = st.Page("pages/cycler_logs.py", title="Cycler Logs", icon=":material/article:")

# System
settings_page = st.Page("pages/settings.py", title="Settings", icon=":material/settings:")
system_logs = st.Page("pages/system_logs.py", title="System Logs", icon=":material/bug_report:")

LOGO_URL_LARGE = "assets/cell_ag_logo_big.png"
LOGO_URL_SMALL = "assets/cell_ag_logo_small.png"

st.logo(
    LOGO_URL_LARGE,
    icon_image=LOGO_URL_SMALL,
    size="large"
)

pg = st.navigation(
    {
        "Home": [
            dashboard_page
        ],
        "Resources": [
            experiments_page,
            graph_view,
            cycler_logs
        ],
        "System": [
            settings_page,
            system_logs,
        ]
    }
)

pg.run()
