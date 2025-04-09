import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="Experiments", layout="wide")

st.title("Experiments")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Users", value="1,250", delta="+5%")

with col2:
    st.metric(label="Revenue", value="$12.4K", delta="+2.1%")

with col3:
    st.metric(label="Bounce Rate", value="38%", delta="-1.4%")

st.markdown("---")

# Sample chart section
st.subheader("Daily Active Users")

# Sample data
dates = pd.date_range(start="2024-01-01", periods=30)
data = pd.DataFrame({
    "Date": dates,
    "Users": np.random.randint(100, 500, size=30)
})

# Altair chart
line_chart = alt.Chart(data).mark_line(point=True).encode(
    x="Date:T",
    y="Users:Q"
).properties(width="container", height=300)

st.altair_chart(line_chart, use_container_width=True)

# Optional: Data table
with st.expander("View Raw Data"):
    st.dataframe(data)
