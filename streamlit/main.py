import streamlit as st

# Home
test_1_page = st.Page("pages/test_1.py", title="Test 1", icon=":material/grid_view:")

# Resources
test_2_page = st.Page("pages/test_2.py", title="Test 2", icon=":material/science:")
test_3_page = st.Page("pages/test_3.py", title="Test 3", icon=":material/show_chart:")
test_4_page = st.Page("pages/test_4.py", title="Test 4", icon=":material/article:")

# System
test_5_page = st.Page("pages/test_5.py", title="Test 5", icon=":material/settings:")
test_6_page = st.Page("pages/test_6.py", title="Test 6", icon=":material/bug_report:")

collapsed_logo = "assets/voyager-logo.png"

st.logo(
    collapsed_logo,
    icon_image=collapsed_logo,
    size="large"
)

pg = st.navigation(
    {
        "Home": [
            test_1_page
        ],
        "Resources": [
            test_2_page,
            test_3_page,
            test_4_page
        ],
        "System": [
            test_5_page,
            test_6_page,
        ]
    }
)

pg.run()

# Add CSS for footer
st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 10px;
        text-align: center;
        border-top: 1px solid #ddd;
        z-index: 999;
    }
    .sidebar-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 10px;
        text-align: center;
        width: 100%;
        border-top: 1px solid #ddd;
    }
    /* Add styles for footer container */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        gap: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Create a container for footer elements
footer_container = st.container()

with footer_container:
    # Add a horizontal line for visual separation
    st.markdown("---")
    
    # Create three columns for the interactive elements
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Refresh Data"):
            st.rerun()
    
    with col2:
        theme = st.selectbox("Theme", ["Light", "Dark"], label_visibility="collapsed")
    
    with col3:
        st.download_button(
            "Export Data",
            data="sample data",
            file_name="export.txt",
            mime="text/plain"
        )

# Add footer to main content
st.markdown(
    """
    <div class="footer">
        2025 Your Company | Version 1.0.0 | <a href="mailto:support@example.com">Contact Support</a>
    </div>
    """,
    unsafe_allow_html=True
)
#
# # Add footer to sidebar
# with st.sidebar:
#     st.markdown(
#         """
#         <div class="sidebar-footer">
#             Last updated: April 17, 2025
#         </div>
#         """,
#         unsafe_allow_html=True
#     )
