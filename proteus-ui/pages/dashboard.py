import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from common.utils import fixed_footer

st.set_page_config(page_title="Dashboard", layout="wide")

st.title("Dashboard")

# Custom CSS for the container
st.markdown("""
    <style>
    .soft-container {
        background-color: #e6f1ec;
        padding: 1.5em;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 1em;
    }
    </style>
""", unsafe_allow_html=True)

with st.container():
    # Everything rendered inside HTML using markdown
    st.markdown("""
        <div class="soft-container">
            <h3>Soft Background Container</h3>
            <p>This container has its own background color and padding.</p>
        </div>
    """, unsafe_allow_html=True)

    # Place the button visually below or insert a styled HTML button here too
    st.button("Native Button (outside styled box)")


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

# Sidebar filters

st.sidebar.header("Filter Reports")
start_date = st.sidebar.date_input("Start date", df["date"].min())
end_date = st.sidebar.date_input("End date", df["date"].max())
selected_category = st.sidebar.multiselect("Category", df["category"].unique(), default=df["category"].unique())

# Filter data
filtered_df = df[
    (df["date"] >= pd.to_datetime(start_date)) &
    (df["date"] <= pd.to_datetime(end_date)) &
    (df["category"].isin(selected_category))
    ]

# Grouped report
report = filtered_df.groupby(["date", "category"])["value"].sum().reset_index()

# Chart view
st.subheader("Report Summary Chart")
chart_data = report.pivot(index="date", columns="category", values="value").fillna(0)
st.line_chart(chart_data)

# Data table view
st.subheader("Report Table")
st.dataframe(report, use_container_width=True)


# Download button
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    processed_data = output.getvalue()
    return processed_data


st.download_button(
    label="Download Report as Excel",
    data=convert_df_to_excel(report),
    file_name="report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
