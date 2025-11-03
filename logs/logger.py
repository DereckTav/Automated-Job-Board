import logging
from pathlib import Path

base_dir = Path(__file__).resolve().parent

log_file = base_dir / "logs" / "parser.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)

def info(message):
    logging.info(message)

def error(message):
    logging.error(message)

def warning(message):
    logging.warning(message)