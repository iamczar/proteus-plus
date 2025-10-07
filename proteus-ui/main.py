import os
import streamlit as st
from common.utils import render_sidebar_settings

LOGO_URL_LARGE = "assets/cell_ag_logo_big.png"
LOGO_URL_SMALL = "assets/cell_ag_logo_small.png"

st.logo(
    LOGO_URL_LARGE,
    icon_image=LOGO_URL_SMALL,
    size = "Large"
    
)

# Home
live_view = st.Page("pages/live_view.py", title="Live View", icon=":material/show_chart:")
auto_sampler = st.Page("pages/auto_sampler.py", title="Auto Sampler Control", icon=":material/science:")
pid_diagram = st.Page("pages/pid_diagram.py", title="PI&D", icon=":material/image:")
pid_controls = st.Page("pages/pid_controls.py", title="PID Controls", icon=":material/tune:")
pid_charts = st.Page("pages/pid_charts.py", title="PID Charts", icon=":material/monitoring:")
lem_page = st.Page("pages/lem.py", title="LEM", icon=":material/precision_manufacturing:")
csv_viewer = st.Page("pages/plot_cvs.py", title="Analyse Historical Data", icon=":material/article:")

pg = st.navigation(
    {
    "Home": [
        live_view,
        auto_sampler,
        pid_controls,
        pid_charts,
        pid_diagram,
        lem_page,
        csv_viewer,
    ]
    }
)

pg.run()

# Render sidebar settings controls at the bottom of the sidebar on all pages
try:
    render_sidebar_settings()
except Exception:
    pass
