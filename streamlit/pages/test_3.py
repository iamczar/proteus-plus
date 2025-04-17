import streamlit as st
import pandas as pd
import altair as alt
import numpy as np

st.title("Test 3 - Data Visualization")

# Create sample data
np.random.seed(42)
data = pd.DataFrame({
    'Date': pd.date_range(start='2024-01-01', periods=100),
    'Value': np.random.randn(100).cumsum(),
    'Category': np.random.choice(['A', 'B', 'C'], 100)
})

# Chart settings in sidebar
st.sidebar.header("Chart Settings")
chart_height = st.sidebar.slider("Chart Height", 200, 600, 400)
show_points = st.sidebar.checkbox("Show Points", True)

# Create interactive chart
chart = alt.Chart(data).mark_line(
    point=show_points
).encode(
    x='Date:T',
    y='Value:Q',
    color='Category:N',
    tooltip=['Date', 'Value', 'Category']
).properties(
    height=chart_height
).interactive()

st.altair_chart(chart, use_container_width=True)
