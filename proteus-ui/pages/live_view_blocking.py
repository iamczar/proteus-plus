import streamlit as st
import pandas as pd
import numpy as np
import time
import altair as alt
import random

from common.utils import random_color
from common.utils import show_toast
from services.module_manager import ModuleManager


st.set_page_config(page_title="Live View (Blocking)", layout="wide")
st.title("Live View (Blocking)")
# Mark current page for cross-page navigation detection
st.session_state["_current_page_key"] = "proteus_ui_live_view_blocking"

st.markdown(
    """
    <style>
    div[data-testid="stVegaLiteChart"],
    div[data-testid="stVegaLiteChart"] * { pointer-events: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

ModuleManager().select_module()


@st.fragment
def experiment_controls():
    with st.container(border=True, key="experiment_controls_container_blocking"):
        labels = [
            "New Experiment",
            "Start Experiment",
            "Stop Experiment",
            "Stop Logging",
            "Start Logging",
            "Retrieve Logs",
        ]
        cols = st.columns(len(labels))
        for col, label in zip(cols, labels):
            with col:
                if st.button(label):
                    result = random.choice(["success", "error", "warning", "info"]) 
                    if result == "success":
                        show_toast("Operation completed successfully!", "success")
                    if result == "error":
                        show_toast("**Error**: Oops! Something went wrong. This event has been recorded in the logs.", "error")
                    if result == "warning":
                        show_toast(
                            "**Warning**: Incomplete input. Please try again. Lorem ipsum dolor sit amet. Consectetur adipiscing elit.",
                            "warning",
                        )
                    if result == "info":
                        show_toast("Informational message.", "info")


experiment_controls()


@st.cache_data
def get_colors(n: int) -> list:
    from common.utils import random_color
    return [random_color() for _ in range(n)]


colors = get_colors(6)
titles = ["Oxygen Pressure", "PressureKi", "PressureKd", "PressureKp", "Temperature", "Pump Speed"]

chart_elements = []
last_values = [0.0 for _ in range(6)]

for row in range(3):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"{titles[row * 2]}")
        init_df = pd.DataFrame({"x": [], "y": []})
        base_chart = (
            alt.Chart(init_df)
            .mark_line(color=colors[row * 2])
            .encode(x=alt.X("x:Q", title=None), y=alt.Y("y:Q", title=None))
            .transform_window(index="row_number()", sort=[alt.SortField("x")])
            .transform_window(max_index="max(index)", frame=[None, None])
            .transform_filter("datum.index >= datum.max_index - 100")
        )
        chart_elements.append(st.altair_chart(base_chart, use_container_width=True))
    with col2:
        st.subheader(f"{titles[row * 2 + 1]}")
        init_df = pd.DataFrame({"x": [], "y": []})
        base_chart = (
            alt.Chart(init_df)
            .mark_line(color=colors[row * 2 + 1])
            .encode(x=alt.X("x:Q", title=None), y=alt.Y("y:Q", title=None))
            .transform_window(index="row_number()", sort=[alt.SortField("x")])
            .transform_window(max_index="max(index)", frame=[None, None])
            .transform_filter("datum.index >= datum.max_index - 100")
        )
        chart_elements.append(st.altair_chart(base_chart, use_container_width=True))


i = 0
while True:
    for chart_idx in range(6):
        if chart_idx == 0:
            new_y = float(np.sin(i * 0.1) + np.random.normal(0, 0.1))
        elif chart_idx == 1:
            new_y = float(np.cos(i * 0.15) + np.random.normal(0, 0.1))
        elif chart_idx == 2:
            new_y = float((i % 20) / 10 + np.random.normal(0, 0.1))
        elif chart_idx == 3:
            new_y = float((1 if (i // 10) % 2 == 0 else -1) + np.random.normal(0, 0.1))
        elif chart_idx == 4:
            new_y = float(20 + i * 0.01 + np.random.normal(0, 0.2))
        else:
            new_y = float(last_values[chart_idx] + np.random.normal(0, 0.3))
        last_values[chart_idx] = new_y
        chart_elements[chart_idx].add_rows(pd.DataFrame({"x": [i], "y": [new_y]}))
    time.sleep(0.1)
    i += 1


