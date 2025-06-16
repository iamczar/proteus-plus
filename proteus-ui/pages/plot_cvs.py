import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Proteus 2.0 - CSV Viewer", layout="wide")
st.title("📊 Proteus 2.0 - 100MB CSV Data Viewer")

# Your actual headers
HEADERS = [
    "TIME", "NULLEADER", "MODUID", "COMMAND", "STATEID",
    "OXYMEASURED", "PRESSUREMEASURED", "FLOWMEASURED", "TEMPMEASURED",
    "CIRCPUMPSPEED", "PRESSUREPUMPSPEED", "PRESSUREPID", "PRESSURESETPOINT",
    "PRESSUREKP", "PRESSUREKI", "PRESSUREKD",
    "OXYGENPID", "OXYGENSETPOINT", "OXYGENKP", "OXYGENKI", "OXYGENKD",
    "OXYGENMEASURED1", "OXYGENMEASURED2", "OXYGENMEASURED3", "OXYGENMEASURED4",
    "NULLTRAILER"
]

# Upload CSV file
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    @st.cache_data
    def load_data(file):
        df = pd.read_csv(file, header=None)
        df.columns = HEADERS

        # Try parsing the TIME column safely
        df["PARSED_TIME"] = pd.to_datetime(df["TIME"], errors="coerce")

        # Separate bad rows
        bad_rows = df[df["PARSED_TIME"].isna()]
        good_df = df.dropna(subset=["PARSED_TIME"]).copy()

        # Replace TIME with parsed result and drop helper
        good_df["TIME"] = good_df["PARSED_TIME"]
        good_df.drop(columns=["PARSED_TIME"], inplace=True)

        # Log bad rows to a CSV file (in project root)
        if not bad_rows.empty:
            bad_rows_path = "bad_rows_log.csv"
            bad_rows.to_csv(bad_rows_path, index=False)
            st.warning(f"⚠️ Skipped {len(bad_rows)} rows with invalid timestamps. Logged to `{bad_rows_path}`")

        return good_df

    df = load_data(uploaded_file)
    st.success(f"Loaded {len(df):,} rows with {len(df.columns)} columns")

    # Sidebar controls
    st.sidebar.header("Filter & View Options")

    # Time range slider
    min_time = df["TIME"].min().to_pydatetime()
    max_time = df["TIME"].max().to_pydatetime()
    time_range = st.sidebar.slider(
        "Time Range", min_value=min_time, max_value=max_time,
        value=(min_time, max_time)
    )

    # Column selection
    numeric_cols = df.columns.drop(["TIME"])
    selected_cols = st.sidebar.multiselect(
        "Select columns to plot", options=numeric_cols,
        default=["OXYMEASURED", "PRESSUREMEASURED"]
    )

    # Downsample
    downsample = st.sidebar.selectbox("Downsample (every nth row)", [1, 5, 10, 50, 100, 500, 1000], index=3)

    # Filter and downsample
    filtered = df[(df["TIME"] >= time_range[0]) & (df["TIME"] <= time_range[1])]
    filtered = filtered.iloc[::downsample]

    # Line chart
    if selected_cols:
        fig = px.line(
            filtered,
            x="TIME",
            y=selected_cols,
            title="📈 Selected Sensor Trends"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Please select at least one column to visualize.")

else:
    st.info("👆 Upload a CSV file above to get started.")
