import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")
DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID")

API_ENDPOINT = 'https://api.notion.com/v1/pages'
QUERY_ENDPOINT = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"

url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# Query ONLY the first 3 results
payload = {
    "page_size": 3
}

response = requests.post(url, headers=headers, json=payload)
data = response.json()

print(json.dumps(data, indent=2))
