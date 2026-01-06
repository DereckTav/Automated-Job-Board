import os
from typing import List
import requests
import yaml
from src.core.logs import Logger
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_KEY")
DATABASE_ID = os.getenv("DATABASE_WEIGHTS_ID")
DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID_WEIGHTS")

QUERY_ENDPOINT = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"

HEADERS = {
   "Authorization": f"Bearer {NOTION_API_KEY}",
   "Content-Type": "application/json",
   "Notion-Version": "2025-09-03"
}

LOGGER = Logger('startup')

def _get_initialized_weights() -> List[str]:
    existing_titles = []
    has_more = True
    start_cursor = None

    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(QUERY_ENDPOINT, headers=HEADERS, json=payload)

        if response.status_code != 200:
            LOGGER.error(f"Notion API error: {response.text}")
            break

        data = response.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            title_prop = props.get("Name", {}).get("title", [])

            if title_prop:
                title = title_prop[0]["plain_text"]
                LOGGER.info(f'[INITIALIZED WEIGHT] {title}')
                existing_titles.append(title)

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return existing_titles

def initialize_weights():
    init_weights = _get_initialized_weights()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, '..', 'configs', 'types.yaml')

    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    weights = config['types']

    for weight in weights:
        if weight not in init_weights:
            LOGGER.info(f'[CREATING] weight: {weight}')
            _create_page(weight)

def _create_page(title):
    url = "https://api.notion.com/v1/pages"

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]}
        },
        "template": {"type": "default"}
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    return response.json()


# Example Usage
if __name__ == "__main__":
    LOGGER.info('starting up...')
    initialize_weights()