import logging

# Configure logger only once
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filemode="w"
)

logger = logging.getLogger()

logger.info("STARTED")