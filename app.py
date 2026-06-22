import queue
import threading
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

    progress_queue = queue.Queue()
    result_container = {}

    # Run the agent in a background thread so we can poll the queue
    def run_agent():
        answer = invoke(question, progress_queue=progress_queue)
        result_container["answer"] = answer

    thread = threading.Thread(target=run_agent)
    thread.start()

    # Show live progress while the agent is running
    st.subheader("Progress")
    with st.status("Working...", expanded=True) as status_box:
        while True:
            msg = progress_queue.get()   # blocks until next update
            if msg is None:              # sentinel — agent is done
                status_box.update(label="Done!", state="complete")
                break
            st.write(msg)

    thread.join()

    st.subheader("Result")
    st.markdown(result_container.get("answer", ""))
