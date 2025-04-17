import streamlit as st
import pandas as pd
import numpy as np
from utils.sidebar_settings import render_module_settings

st.set_page_config(layout="wide")
st.title("Test 6 - Dashboard Layout")

# Add module settings to sidebar
settings = render_module_settings()

# Metrics Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Sales", "$12,345", "+12%")
with col2:
    st.metric("Users", "1,234", "-2%")
with col3:
    st.metric("Conversion", "4.5%", "+0.5%")
with col4:
    st.metric("Revenue", "$234.5k", "+18%")

# Main Content
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Data Table")
    
    # Generate sample data
    data = pd.DataFrame(
        np.random.randn(20, 4),
        columns=['Q1', 'Q2', 'Q3', 'Q4']
    )
    data['Year'] = 2020 + np.arange(len(data))
    
    # Add column highlighting
    st.dataframe(
        data.style.highlight_max(axis=0, color='lightgreen')
                .highlight_min(axis=0, color='pink'),
        use_container_width=True
    )

with right_col:
    st.subheader("Settings")
    
    with st.expander("Display Options", expanded=True):
        st.checkbox("Show Grid")
        st.checkbox("Dark Mode")
        st.slider("Update Frequency (s)", 1, 60, 5)
    
    with st.expander("Data Filters"):
        st.multiselect(
            "Select Quarters",
            ["Q1", "Q2", "Q3", "Q4"],
            ["Q1", "Q2", "Q3", "Q4"]
        )
        st.slider("Year Range", 2020, 2024, (2020, 2024))

# Footer
st.markdown("---")
st.caption("Dashboard demo with metrics, data table, and settings panel")
