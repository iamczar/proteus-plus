import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import random

from common.utils import show_toast

st.set_page_config(page_title="Experiments", layout="wide")

st.title("Experiments")

if st.button("New Experiment"):
    result = random.choice(["success", "error", "warning", "info"])
    if result == "success":
        show_toast("Operation completed successfully!", "success")
    if result == "error":
        show_toast("**Error**: Oops! Something went wrong. This event has been recorded in the logs.", "error")
    if result == "warning":
        show_toast("**Warning**: Incomplete input. Please try again. Lorem ipsum dolor sit amet. Consectetur adipiscing elit.", "warning")
    if result == "info":
        show_toast("Informational message.", "info")
