FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY agent.py app.py logger.py get_env.py s3_connector.py icon.png ./

# Expose Streamlit default port
EXPOSE 8502

# Streamlit config: disable browser auto-open and set server address
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8502 \
    STREAMLIT_SERVER_BASE_URL_PATH=job-search-agent

# Run Streamlit App
CMD ["sh", "-c", "python3 get_env.py && streamlit run app.py"]