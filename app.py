import queue
import threading
import streamlit as st
from agent import invoke
import base64
from pathlib import Path

st.set_page_config(
    page_title="AI Powered Job Search Assistant",
    page_icon="🤖",
    layout="wide"
)

st.markdown(
    """
    <style>
        :root {
            --cyan: #22d3ee;
            --violet: #8b5cf6;
            --panel: rgba(15, 23, 42, 0.82);
            --muted: #94a3b8;
        }
        .stApp {
            color: #e2e8f0;
            background-color: #050816;
            background-image:
                radial-gradient(circle at 15% 0%, rgba(34, 211, 238, .12), transparent 32rem),
                radial-gradient(circle at 90% 10%, rgba(139, 92, 246, .14), transparent 28rem),
                linear-gradient(rgba(34, 211, 238, .025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(34, 211, 238, .025) 1px, transparent 1px);
            background-size: auto, auto, 32px 32px, 32px 32px;
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stMainBlockContainer"] {
            max-width: 760px;
            padding-top: 5rem;
        }
        .eyebrow {
            color: var(--cyan);
            font-family: monospace;
            font-size: .78rem;
            font-weight: 700;
            letter-spacing: .16em;
            margin-bottom: .8rem;
            text-transform: uppercase;
        }
        .profile-wrap {
            display: inline-flex;
            margin-bottom: 1.5rem;
            padding: 3px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--cyan), var(--violet));
            box-shadow: 0 0 30px rgba(34, 211, 238, .16);
        }
        .profile-photo {
            width: 132px;
            height: 132px;
            border: 4px solid #080d1c;
            border-radius: 50%;
            display: block;
            object-fit: cover;
            object-position: center;
        }
        .hero-title {
            font-size: clamp(2.8rem, 8vw, 4.8rem);
            font-weight: 800;
            letter-spacing: -.055em;
            line-height: 1;
            margin: 0 0 1.25rem;
            background: linear-gradient(100deg, #f8fafc 15%, var(--cyan) 55%, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            color: #a9b6ca;
            font-size: 1.05rem;
            line-height: 1.75;
            margin-bottom: 1.35rem;
            max-width: 680px;
        }
        .subtitle .intro-title {
            color: #f1f5f9;
            font-size: 1.25rem;
            font-weight: 700;
            margin: 0 0 .8rem;
        }
        .subtitle p { margin: 0 0 1rem; }
        .chips { display: flex; flex-wrap: wrap; gap: .55rem; margin-bottom: 3rem; }
        .chip {
            background: rgba(34, 211, 238, .07);
            border: 1px solid rgba(34, 211, 238, .2);
            border-radius: 999px;
            color: #b6eff7;
            font-family: monospace;
            font-size: .76rem;
            padding: .35rem .7rem;
        }
        .section-label {
            color: #f1f5f9;
            font-size: 1.15rem;
            font-weight: 700;
            margin: 0 0 .85rem;
        }
        .contact-section { margin-top: 3rem; }
        .hire-message {
            background: linear-gradient(135deg, rgba(34, 211, 238, .09), rgba(139, 92, 246, .09));
            border: 1px solid rgba(34, 211, 238, .3);
            border-radius: 12px;
            color: #cbd5e1;
            line-height: 1.7;
            margin-top: .8rem;
            padding: 1.2rem;
        }
        .hire-message a { color: var(--cyan) !important; font-weight: 700; }
        .contact-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
        }
        .contact-card {
            background: var(--panel);
            border: 1px solid rgba(148, 163, 184, .18);
            border-radius: 12px;
            color: #cbd5e1 !important;
            padding: 1rem;
            text-decoration: none !important;
            transition: all .2s ease;
            overflow-wrap: anywhere;
        }
        .contact-card:hover {
            border-color: var(--cyan);
            color: white !important;
            transform: translateY(-2px);
        }
        .contact-type {
            color: var(--cyan);
            display: block;
            font-family: monospace;
            font-size: .7rem;
            letter-spacing: .1em;
            margin-bottom: .35rem;
            text-transform: uppercase;
        }
        @media (max-width: 600px) {
            .contact-grid { grid-template-columns: 1fr; }
        }
        .stLinkButton > a {
            background: var(--panel);
            border: 1px solid rgba(148, 163, 184, .18);
            border-radius: 12px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, .18);
            color: #e2e8f0;
            font-size: 1rem;
            font-weight: 600;
            min-height: 4rem;
            justify-content: flex-start;
            padding-left: 1.25rem;
            transition: all .2s ease;
        }
        .stLinkButton > a:hover {
            background: rgba(17, 35, 57, .96);
            border-color: var(--cyan);
            box-shadow: 0 0 28px rgba(34, 211, 238, .12);
            color: white;
            transform: translateY(-2px);
        }
        .stButton { margin-top: 1rem; }
        .stButton > button {
            background: transparent;
            border-color: rgba(148, 163, 184, .2);
            color: var(--muted);
        }
        .stButton > button[data-testid="stBaseButton-primary"] {
            background: var(--panel);
            border: 1px solid rgba(148, 163, 184, .18);
            border-radius: 12px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, .18);
            color: #e2e8f0;
            font-size: 1rem;
            font-weight: 600;
            min-height: 4rem;
            transition: all .2s ease;
        }
        .stButton > button[data-testid="stBaseButton-primary"]:hover {
            background: rgba(17, 35, 57, .96);
            border-color: var(--cyan);
            box-shadow: 0 0 28px rgba(34, 211, 238, .12);
            color: white;
            transform: translateY(-2px);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

photo_data = base64.b64encode(
    Path(__file__).with_name("icon.png").read_bytes()
).decode("ascii")

st.markdown(
    f'<div class="profile-wrap"><img class="profile-photo" '
    f'src="data:image/png;base64,{photo_data}" alt="AAAAA"></div>'
    '<div class="eyebrow">Explroe LinkedIn Jobs Around the Globe</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<h1 class="hero-title">AI Powered Job Search Assistant</h1>'
    '<div class="subtitle">'
    '<p class="intro-title">Find Visa Sponsored Jobs Around the Globe</p>'
    '<p>This tools helps you find the Visa Sponsored Jobs on LinkedIn '
    'around the globe. You need to mention what role you are looking for '
    'and in which region or country.'
    'It looks up the LinkedIn for posted jobs and from each jobs checks if company is providing visa-sponsorhip.</p>'
    '</div>', unsafe_allow_html=True
)
question = st.text_input(
    "Enter Your Question:",
    placeholder="e.g. Give me the visa sponsored Data Scientist jobs in Netherlands"
)

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
