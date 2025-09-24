import io
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Analyse Historical Data", layout="wide")
st.title("Analyse Historical Data")
st.session_state["_current_page_key"] = "proteus_ui_plot_cvs"

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


@st.cache_data(show_spinner=False)
def load_data_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    buffer = io.BytesIO(file_bytes)
    buffer.seek(0)
    df = pd.read_csv(buffer, header=None)
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
        st.warning(
            f"⚠️ Skipped {len(bad_rows)} rows with invalid timestamps. Logged to `{bad_rows_path}`"
        )

    return good_df


# Upload CSV file (persist across reloads)
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

file_bytes = None
if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    st.session_state["plot_cvs_file"] = {
        "name": getattr(uploaded_file, "name", "uploaded.csv"),
        "bytes": file_bytes,
    }
elif "plot_cvs_file" in st.session_state:
    # Restore previously uploaded file after a page reload
    file_bytes = st.session_state["plot_cvs_file"].get("bytes")

if file_bytes is not None:
    df = load_data_from_bytes(file_bytes)
    st.success(f"Loaded {len(df):,} rows with {len(df.columns)} columns")

    # Sidebar controls
    st.sidebar.header("Filter & View Options")

    # Read query params for persistence
    params = dict(st.query_params)
    raw_cols = params.get("cols")
    raw_ds = params.get("ds")

    numeric_cols = df.columns.drop(["TIME"])
    default_cols = [c for c in ["OXYMEASURED", "PRESSUREMEASURED"] if c in list(numeric_cols)]
    if raw_cols:
        cols_from_params = [c for c in str(raw_cols).split(",") if c in list(numeric_cols)]
        if cols_from_params:
            default_cols = cols_from_params

    downsample_options = [1, 5, 10, 50, 100, 500, 1000]
    downsample_from_params = None
    try:
        if raw_ds is not None:
            downsample_from_params = int(str(raw_ds))
    except Exception:
        downsample_from_params = None
    downsample_index = (
        downsample_options.index(downsample_from_params)
        if downsample_from_params in downsample_options
        else 3
    )

    # Initialize widget state from URL params (only once)
    if "plot_cols" not in st.session_state:
        st.session_state["plot_cols"] = default_cols
    if "plot_ds" not in st.session_state:
        st.session_state["plot_ds"] = downsample_options[downsample_index]

    # Widgets (stable keys ensure first-click updates are reflected immediately)
    st.sidebar.multiselect(
        "Select columns to plot",
        options=list(numeric_cols),
        key="plot_cols",
    )

    st.sidebar.selectbox(
        "Downsample (every nth row)",
        downsample_options,
        key="plot_ds",
    )

    selected_cols = st.session_state.get("plot_cols", [])
    downsample = st.session_state.get("plot_ds", downsample_options[downsample_index])

    # Data sampling (no time filtering)
    filtered = df.iloc[::downsample]

    # Line chart
    if selected_cols:
        fig = px.line(
            filtered,
            x="TIME",
            y=selected_cols,
            title="📈 Selected Sensor Trends",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Please select at least one column to visualize.")

    # Sync widget state to the URL so reloads restore the same view
    new_params = {
        "cols": ",".join(selected_cols) if selected_cols else "",
        "ds": str(downsample),
    }
    current_params = {k: str(v) for k, v in dict(st.query_params).items()}
    if current_params != new_params:
        st.query_params.clear()
        st.query_params.update(new_params)
else:
    st.info("👆 Upload a CSV file above to get started.")
