import os
import streamlit as st

# Home
dashboard_page = st.Page("pages/dashboard.py", title="Dashboard", icon=":material/grid_view:")

# Resources
live_view = st.Page("pages/live_view.py", title="Live View", icon=":material/show_chart:")
auto_sampler = st.Page("pages/auto_sampler.py", title="Auto Sampler Control", icon=":material/science:")
pid_diagram = st.Page("pages/pid_diagram.py", title="PI&D", icon=":material/image:")
csv_viewer = st.Page("pages/plot_cvs.py", title="Display Big Data", icon=":material/article:")
cycler_logs = st.Page("pages/cycler_logs.py", title="Cycler Logs", icon=":material/article:")

# System
system_logs = st.Page("pages/system_logs.py", title="System Logs", icon=":material/bug_report:")

LOGO_URL_LARGE = "assets/cell_ag_logo_big.png"
LOGO_URL_SMALL = "assets/cell_ag_logo_small.png"

st.logo(
    LOGO_URL_LARGE,
    icon_image=LOGO_URL_SMALL,
    size = "Large"
    
)

pg = st.navigation(
    {
    "Home": [
        live_view,
        auto_sampler,
        pid_diagram,
        csv_viewer,
        cycler_logs,
    ],
    "System": [
        system_logs
    ]
    }
)

pg.run()
