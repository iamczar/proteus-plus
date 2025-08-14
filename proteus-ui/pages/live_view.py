import streamlit as st
import pandas as pd
import numpy as np
import time
import altair as alt

from io import BytesIO
from common.utils import fixed_footer
from common.utils import random_color
from services.module_manager import ModuleManager

st.set_page_config(page_title="Live View", layout="wide")
st.title("Live View")

# Disable interactivity for charts globally (keeps visuals the same)
st.markdown(
    """
    <style>
    /* Disable all pointer interactions on Vega-Lite charts */
    div[data-testid="stVegaLiteChart"],
    div[data-testid="stVegaLiteChart"] * {
        pointer-events: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Module selection
ModuleManager().select_module()


@st.cache_data
def get_colors(number: int) -> list:
    return [random_color() for _ in range(number)]


colors = get_colors(6)

table_titles = ["Oxygen Pressure", "PressureKi", "PressureKd", "PressureKp", "Temperature", "Pump Speed"]

# Create chart elements (created once) and keep last values for random walk
chart_elements = []
last_values = [0.0 for _ in range(6)]

# Layout: 3 rows × 2 columns
for row in range(3):  # 3 rows
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"{table_titles[row * 2]}")
        init_df = pd.DataFrame({"x": [], "y": []})
        base_chart = (
            alt.Chart(init_df)
            .mark_line(color=colors[row * 2])
            .encode(x=alt.X("x:Q", title=None), y=alt.Y("y:Q", title=None))
            .transform_window(xmax="max(x)")
            .transform_filter("datum.x >= datum.xmax - 100")
        )
        chart_elements.append(st.altair_chart(base_chart, use_container_width=True))

    with col2:
        st.subheader(f"{table_titles[row * 2 + 1]}")
        init_df = pd.DataFrame({"x": [], "y": []})
        base_chart = (
            alt.Chart(init_df)
            .mark_line(color=colors[row * 2 + 1])
            .encode(x=alt.X("x:Q", title=None), y=alt.Y("y:Q", title=None))
            .transform_window(xmax="max(x)")
            .transform_filter("datum.x >= datum.xmax - 100")
        )
        chart_elements.append(st.altair_chart(base_chart, use_container_width=True))

# Live data simulation
i = 0
while True:
    # Generate new data points for each chart
    for chart_idx in range(6):
        if chart_idx == 0:  # Oxygen Pressure - sine wave
            new_y = float(np.sin(i * 0.1) + np.random.normal(0, 0.1))
        elif chart_idx == 1:  # PressureKi - cosine wave
            new_y = float(np.cos(i * 0.15) + np.random.normal(0, 0.1))
        elif chart_idx == 2:  # PressureKd - sawtooth
            new_y = float((i % 20) / 10 + np.random.normal(0, 0.1))
        elif chart_idx == 3:  # PressureKp - square wave
            new_y = float((1 if (i // 10) % 2 == 0 else -1) + np.random.normal(0, 0.1))
        elif chart_idx == 4:  # Temperature - gradual trend
            new_y = float(20 + i * 0.01 + np.random.normal(0, 0.2))
        else:  # Pump Speed - random walk
            new_y = float(last_values[chart_idx] + np.random.normal(0, 0.3))

        # Update last value for the series
        last_values[chart_idx] = new_y

        # Append a single new row to the existing chart without full redraw
        chart_elements[chart_idx].add_rows(pd.DataFrame({"x": [i], "y": [new_y]}))

    # Wait a bit before next update
    time.sleep(0.1)
    i += 1
