import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Page config
st.set_page_config(page_title="Test 1 - Demo Features", layout="wide")

# Sidebar
st.sidebar.header("Settings")
color = st.sidebar.color_picker("Pick a color", "#00ff00")
number = st.sidebar.slider("Select a number", 0, 100, 50)

# Main content
col1, col2 = st.columns(2)

with col1:
    st.header("Interactive Widgets")
    
    # Text input
    name = st.text_input("Enter your name", "Guest")
    st.write(f"Hello, {name}!")
    
    # Checkbox
    if st.checkbox("Show random data"):
        data = np.random.randn(10, 3)
        df = pd.DataFrame(data, columns=["A", "B", "C"])
        st.dataframe(df)
    
    # Radio buttons
    chart_type = st.radio(
        "Select chart type",
        ["Line", "Bar", "Scatter"]
    )

with col2:
    st.header("Charts and Plots")
    
    # Generate sample data
    x = np.linspace(0, 10, 100)
    y = np.sin(x) * number/50
    
    df = pd.DataFrame({
        "x": x,
        "y": y
    })
    
    # Display different charts based on selection
    if chart_type == "Line":
        fig = px.line(df, x="x", y="y", title="Sample Line Chart")
    elif chart_type == "Bar":
        fig = px.bar(df.sample(10), x="x", y="y", title="Sample Bar Chart")
    else:
        fig = px.scatter(df, x="x", y="y", title="Sample Scatter Plot")
        
    st.plotly_chart(fig)

# Metrics
col3, col4, col5 = st.columns(3)
col3.metric("Temperature", "70 °F", "1.2 °F")
col4.metric("Wind", "9 mph", "-8%")
col5.metric("Humidity", "86%", "4%")

# Expander
with st.expander("See explanation"):
    st.write("""
        This is a demo page showing various Streamlit features including:
        * Interactive widgets
        * Charts and plots
        * Metrics
        * Layout options
        * Data display
    """)
    
# Progress bar
progress = st.progress(0)
for i in range(number):
    progress.progress((i + 1)/100)