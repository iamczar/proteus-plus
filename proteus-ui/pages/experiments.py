import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import random

from common.utils import show_toast
from services.module_settings import render_module_settings

st.set_page_config(page_title="Experiments", layout="centered")
st.title("Experiments")

# Module selection
render_module_settings()


@st.fragment
def create_new_experiment():
    if st.button("New Experiment"):
        pass


# Functions
create_new_experiment()
