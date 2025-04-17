import streamlit as st
import time
from utils.sidebar_settings import render_module_settings

st.title("Test 4 - Forms and Session State")

# Initialize session state
if 'counter' not in st.session_state:
    st.session_state.counter = 0
if 'form_submissions' not in st.session_state:
    st.session_state.form_submissions = []

# Add module settings to sidebar
settings = render_module_settings()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Counter Demo")
    if st.button("Increment"):
        st.session_state.counter += 1
    st.write(f"Counter value: {st.session_state.counter}")

with col2:
    st.subheader("Form Demo")
    with st.form("my_form"):
        name = st.text_input("Name")
        age = st.number_input("Age", min_value=0, max_value=120)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Submit")
        
        if submitted:
            submission = {"name": name, "age": age, "notes": notes, "time": time.strftime("%H:%M:%S")}
            st.session_state.form_submissions.append(submission)
            st.success("Form submitted!")

st.subheader("Previous Submissions")
for submission in st.session_state.form_submissions:
    with st.expander(f"{submission['name']} - {submission['time']}"):
        st.write(f"Age: {submission['age']}")
        st.write(f"Notes: {submission['notes']}")
