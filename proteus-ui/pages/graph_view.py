import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from common.utils import fixed_footer
from common.utils import random_color

st.set_page_config(page_title="Graph View", layout="wide")

st.title("Graph View")


@st.cache_data
def get_colors(number: int) -> list:
    return [random_color() for _ in range(number)]


colors = get_colors(6)


# Sample data generation
@st.cache_data
def generate_data():
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=90)
    categories = ["Sales", "Marketing", "Support"]
    data = {
        "date": np.random.choice(dates, 300),
        "category": np.random.choice(categories, 300),
        "value": np.random.randint(50, 500, size=300)
    }
    return pd.DataFrame(data)


df = generate_data()

# Generate data for 6 charts
charts_data = [pd.DataFrame({
    'x': np.arange(0, 20),
    'y': np.sin(np.arange(0, 20) + i)
}) for i in range(6)]

# Layout: 3 rows × 2 columns
for row in range(3):  # 3 rows
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"Chart {row * 2 + 1}")
        st.line_chart(charts_data[row * 2].set_index('x'), color=colors[row * 2])

    with col2:
        st.subheader(f"Chart {row * 2 + 2}")
        st.line_chart(charts_data[row * 2 + 1].set_index('x'), color=colors[row * 2 + 1])
