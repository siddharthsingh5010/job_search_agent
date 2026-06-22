import streamlit as st
from agent import invoke

st.set_page_config(
    page_title="AI Powered Job Search Assistant",
    page_icon="🤖",
    layout="wide"
)

st.markdown("### 🤖 AI Powered Job Search Assistant")
st.markdown("---")

question = st.text_input("Enter Your Question:")

if question:

    result = invoke(question)

    st.subheader("Progress")

    for msg in result["status"]:
        st.write(msg)

    st.subheader("Result")

    st.markdown(result["answer"])