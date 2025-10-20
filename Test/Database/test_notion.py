import datetime
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from dotenv import load_dotenv
import os
import requests

from Database.notion import NotionDatabase, Gateway, MessageBus
from JobParser.output import Result

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")
DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID")

API_ENDPOINT = 'https://api.notion.com/v1/pages'
QUERY_ENDPOINT = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"

headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2025-09-03"
    }

payload = {
    "parent": {
        "database_id": DATABASE_ID
    },
    "properties": {
        "Company Name": {
            "title": [{"type": "text", "text": {"content": "test"}}]
        },
        "Application Link": {
            "url": "example.com"
        },
        "Position": {
            "multi_select": [{"name": "Engineer"}]
        },
        "Status": {
            "status": {"name": "Pending"}
        }
    }
}

async def do_response_post(endpoint: str, use_payload: bool):
    await asyncio.sleep(1)

    if use_payload:
        with requests.post(
            endpoint,
            headers=headers,
            json=payload
        ) as response:
            try:
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError:
                assert Exception(json.dumps(response.json(), indent=2))


    else:
        with requests.post(
            endpoint,
            headers=headers,
        ) as response:
            try:
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError:
                raise Exception(json.dumps(response.json(), indent=2))

async def do_response_patch(endpoint: str, body: dict):
    await asyncio.sleep(1)
    with requests.patch(endpoint, headers=headers, json=body) as response:
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            raise Exception(json.dumps(response.json(), indent=2))

@pytest.fixture
def reset_singleton():

    for cls in [Gateway, NotionDatabase, MessageBus]:
        cls._instance = None
        if hasattr(cls, "_initialized"):
            delattr(cls, "_initialized")

    yield

    for cls in [Gateway, NotionDatabase, MessageBus]:
        cls._instance = None
        if hasattr(cls, "_initialized"):
            delattr(cls, "_initialized")

'''
# for page
["properties"]["Position"]["multi_select"][0]["name"] # position
["properties"]["Status"]["status"]["name"] # status
["properties"]["Company Size"]["multi_select"][0]["name"] # company_size
["properties"]["Application Link"]["url"] # url
["properties"]["Company Name"]["title"][0]["text"]["content"] # company_name
'''

@pytest.mark.asyncio
async def test_singleton(reset_singleton):
    db1 = NotionDatabase()
    db2 = NotionDatabase()

    assert db1 is db2

@pytest.mark.asyncio
async def test_singleton_1(reset_singleton):
    db1 = await NotionDatabase()

    assert db1._database_cleaner is not None
    db2 = NotionDatabase()

    assert db2._database_cleaner is not None


    assert db1 is db2

@pytest.mark.asyncio
async def test_singleton_2(reset_singleton):
    db1 = NotionDatabase()

    assert db1._database_cleaner is None
    db2 = await NotionDatabase()
    assert db2._database_cleaner is not None


    assert db1 is db2

# Notion Database
def test_generate_body():
    body = NotionDatabase._generate_body(
        "Company",
        "Engineer",
        "https://example.com",
        "Job description",
        "100+"
    )

    assert body["properties"]["Company Name"]["title"][0]["text"]["content"] is "Company"
    assert body["properties"]["Application Link"]["url"] is "https://example.com"
    assert body["properties"]["Position"]["multi_select"][0]["name"] is "Engineer"
    assert body["properties"]["Status"]["status"]["name"] is "Pending"
    assert body["children"][0]["paragraph"]["rich_text"][0]["text"]["content"] is "Job description"
    assert body["properties"]["Company Size"]["multi_select"][0]["name"] is "100+"

#test query
@pytest.mark.asyncio
async def test_query_database(reset_singleton):
    # add page
    await do_response_post('https://api.notion.com/v1/pages', True)

    db = NotionDatabase()

    await asyncio.sleep(1)
    p1 = await db._query_database()

    response = await do_response_post(QUERY_ENDPOINT, use_payload=False)

    p2 = response.get("results", [])

    assert p1[0] == p2[0], "expected query 1 to be teh same as query 2"

    url = API_ENDPOINT + f"/{p1[0]["id"]}"
    body = {"archived": True}
    await do_response_patch(url, body)


#Test deletion
@pytest.mark.asyncio
async def test_delete_page(reset_singleton):
    #add page
    await do_response_post('https://api.notion.com/v1/pages', use_payload=True)

    db = NotionDatabase()
    pages = await db._query_database()

    await asyncio.sleep(1)
    await db._delete_page(pages[0]["id"])

    await asyncio.sleep(1)
    re_pages = await db._query_database()

    if not re_pages:
        assert True
    else:
        assert pages[0]["id"] != re_pages[0]["id"], "expected page to be deleted, page was not deleted"

#Test Post
@pytest.mark.asyncio
async def test_post_success_1(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)
    await db._post_return_response(
        "Company",
        "Engineer",
        "https://example.com",
        "Job description",
        "100+"
        )

    await asyncio.sleep(1)
    pages = await db._query_database()
    page = pages[0]
    page_id = page["id"]

    await asyncio.sleep(1)
    description = await db._get_description(page_id)

    assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"
    assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
    assert page["properties"]["Application Link"]["url"] == "https://example.com"
    assert description == "Job description"
    assert page["properties"]["Company Size"]["multi_select"][0]["name"] == "100+"

    #clean up
    await asyncio.sleep(1)
    await db._delete_page(page_id)

@pytest.mark.asyncio
async def test_post_success_2(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)
    await db._post_return_response(
        "Company",
        "Engineer",
        "https://example.com",
        "Job description",
        None
    )

    await asyncio.sleep(1)
    pages = await db._query_database()
    page = pages[0]
    page_id = page["id"]

    await asyncio.sleep(1)
    description = await db._get_description(page_id)

    assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"
    assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
    assert page["properties"]["Application Link"]["url"] == "https://example.com"
    assert description == "Job description"
    assert page["properties"]["Company Size"]["multi_select"] == [], "Expected 'Company Size' to be empty"

    # clean up
    await asyncio.sleep(1)
    await db._delete_page(page_id)

@pytest.mark.asyncio
async def test_post_success_3(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)
    await db._post_return_response(
        "Company",
        "Engineer",
        "https://example.com",
        None,
        None
    )

    await asyncio.sleep(1)
    pages = await db._query_database()
    page = pages[0]
    page_id = page["id"]

    await asyncio.sleep(1)
    description = await db._get_description(page_id)

    assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"
    assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
    assert page["properties"]["Application Link"]["url"] == "https://example.com"
    assert description is None, "Expected no description"
    assert page["properties"]["Company Size"]["multi_select"] == [], "Expected 'Company Size' to be empty"

    # clean up
    await asyncio.sleep(1)
    await db._delete_page(page_id)

@pytest.mark.asyncio
async def test_post_success_4(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)
    await db._post_return_response(
        "Company",
        "Engineer",
        None,
        None,
        None
    )

    await asyncio.sleep(1)
    pages = await db._query_database()
    page = pages[0]
    page_id = page["id"]

    await asyncio.sleep(1)
    description = await db._get_description(page_id)

    assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"
    assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
    assert page["properties"]["Application Link"]["url"] is None, "Expected no application link to be empty"
    assert description is None, "Expected no description"
    assert page["properties"]["Company Size"]["multi_select"] == [], "Expected 'Company Size' to be empty"

    # clean up
    await asyncio.sleep(1)
    await db._delete_page(page_id)

@pytest.mark.asyncio
async def test_batch_post_error(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)

    data = {
        "company_name": "Company",
        "company_size": "100+",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }

    with pytest.raises(ValueError) as exc_info:
        await db.batch_post(data, data, data, data)

    assert str(exc_info.value) == "Expected at most 3 dictionaries"

@pytest.mark.asyncio
async def test_batch_post_1(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)

    data = {
        "company_name": "Company",
        "company_size": "100+",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }

    await db.batch_post(data, data, data)
    await asyncio.sleep(1)
    pages = await db._query_database()
    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2]

    p1_id = p1["id"]
    p2_id = p2["id"]
    p3_id = p3["id"]

    await asyncio.sleep(1)
    d1 = await db._get_description(p1_id)
    d2 = await db._get_description(p2_id)
    d3 = await db._get_description(p3_id)

    for page, description in zip([p1, p2, p3], [d1, d2, d3]):
        assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"
        assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
        assert page["properties"]["Application Link"]["url"] == "https://example.com"
        assert description == "Job description"
        assert page["properties"]["Company Size"]["multi_select"][0]["name"] == "100+"

    # clean up
    await asyncio.sleep(1)
    await db._batch_delete_pages(pages)

@pytest.mark.asyncio
async def test_batch_post_2(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)

    import Database.notion

    Database.notion.cleaner_active = True

    data = {
        "company_name": "Company",
        "company_size": "100+",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }

    await db.batch_post(data, data, data)
    await asyncio.sleep(1)
    pages = await db._query_database()
    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2]

    p1_id = p1["id"]
    p2_id = p2["id"]
    p3_id = p3["id"]

    await asyncio.sleep(1)
    d1 = await db._get_description(p1_id)
    d2 = await db._get_description(p2_id)
    d3 = await db._get_description(p3_id)

    for page, description in zip([p1, p2, p3], [d1, d2, d3]):
        assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"
        assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
        assert page["properties"]["Application Link"]["url"] == "https://example.com"
        assert description == "Job description"
        assert page["properties"]["Company Size"]["multi_select"][0]["name"] == "100+"

    # clean up
    await asyncio.sleep(1)
    await db._batch_delete_pages(pages)

    Database.notion.cleaner_active = False

@pytest.mark.asyncio
async def test_delete_old_entries(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)
    await db._post_return_response(
        "Company",
        "Engineer",
        None,
        None,
        None
    )

    await asyncio.sleep(1)
    pages = await db._query_database()
    page = pages[0]
    page["properties"]["Created time"]["created_time"] = datetime.now(timezone.utc) - timedelta(days=3)

    with patch.object(NotionDatabase, "_query_database", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = pages

        for cls in [Gateway, NotionDatabase, MessageBus]:
            cls._instance = None
            if hasattr(cls, "_initialized"):
                delattr(cls, "_initialized")

        db=NotionDatabase()

        await asyncio.sleep(1)
        await db._delete_old_entries()

    await asyncio.sleep(1)
    re_pages = await db._query_database()

    if not re_pages:
        assert True
    else:
        assert page["id"] != re_pages[0]["id"], "expected page to be deleted, page was not deleted"


@pytest.mark.asyncio
async def test_clear_duplicates(reset_singleton):
    db = NotionDatabase()
    await asyncio.sleep(1)

    data = {
        "company_name": "Company",
        "company_size": "100+",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }

    await db.batch_post(data, data)
    await asyncio.sleep(1)
    pages = await db._query_database()
    p1 = pages[0]

    await asyncio.sleep(1)
    await db.clear_duplicates()

    await asyncio.sleep(1)
    re_pages = await db._query_database()

    if len(re_pages) == 1:
        assert True
        await asyncio.sleep(1)
        await db._delete_page(re_pages[0]["id"])

    elif len(re_pages) > 1:
        ids = [re_pages[0]["id"], re_pages[1]["id"], re_pages[2]["id"]]
        if p1["id"] in ids:
            positions = [i for i, page_id in enumerate(ids) if page_id == p1["id"]]

            if len(positions) == 1:
                assert True
            else:
                assert False, "Didn't get rid of duplicates"

            for i in positions:
                page_id = ids[i]
                await asyncio.sleep(1)
                await db._delete_page(page_id)

    else:
        assert False, ("got rid of all duplicates, need to leave at least one that isn't a duplicate"
                       "or didn't get rid of any duplicates")


@pytest.mark.asyncio
async def test_message_bus_and_gateway_1(reset_singleton):
    data = [{
        "company_name": "Company",
        "company_size": "100+",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }] * 3

    import pandas as pd

    df = pd.DataFrame(data)
    result = Result(**df.to_dict(orient='list'))

    message = MessageBus()
    await message.publish(result)

    db = NotionDatabase()

    assert db._database_cleaner is not None, ("publish should init Gateway and run it",
                                              "Gateway should  = await NotionDatabase() to start cleaner")

    await asyncio.sleep(1)
    pages = await db._query_database()
    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2]

    pages =[p1, p2, p3]

    for page in pages:
        assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
        assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"

    await asyncio.sleep(1)
    await db._batch_delete_pages(pages)

@pytest.mark.asyncio
async def test_message_bus_and_gateway_2(reset_singleton):
    data = [{
        "company_name": "Company",
        "company_size": "100+",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }] * 5

    import pandas as pd

    df = pd.DataFrame(data)
    result = Result(**df.to_dict(orient='list'))

    message = MessageBus()
    await message.publish(result)

    db = NotionDatabase()

    assert db._database_cleaner is not None, ("publish should init Gateway and run it",
                                              "Gateway should  = await NotionDatabase() to start cleaner")

    await asyncio.sleep(5)
    pages = await db._query_database()
    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2]
    p4 = pages[3]
    p5 = pages[4]

    pages = [p1, p2, p3, p4, p5]

    for page in pages:
        assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
        assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"

    await asyncio.sleep(1)
    await db._batch_delete_pages(pages)

@pytest.mark.asyncio
async def test_message_bus_and_gateway_3(reset_singleton):
    #make sure result works with None values
    data = [{
        "company_name": "Company",
        "company_size": None,
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }] * 5

    import pandas as pd

    df = pd.DataFrame(data)
    result = Result(**df.to_dict(orient='list'))

    message = MessageBus()
    await message.publish(result)

    db = NotionDatabase()

    assert db._database_cleaner is not None, ("publish should init Gateway and run it",
                                              "Gateway should  = await NotionDatabase() to start cleaner")

    await asyncio.sleep(5)
    pages = await db._query_database()
    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2]
    p4 = pages[3]
    p5 = pages[4]

    pages = [p1, p2, p3, p4, p5]

    for page in pages:
        assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
        assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"

    await asyncio.sleep(1)
    await db._batch_delete_pages(pages)

@pytest.mark.asyncio
async def test_message_bus_and_gateway_4(reset_singleton):
    #make sure result works with None values
    data = [{
        "company_name": "Company",
        "application_link": "https://example.com",
        "position": "Engineer",
        "description": "Job description",
    }] * 5

    import pandas as pd

    df = pd.DataFrame(data)
    result = Result(**df.to_dict(orient='list'))

    message = MessageBus()
    await message.publish(result)

    db = NotionDatabase()

    assert db._database_cleaner is not None, ("publish should init Gateway and run it",
                                              "Gateway should  = await NotionDatabase() to start cleaner")

    await asyncio.sleep(5)
    pages = await db._query_database()
    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2]
    p4 = pages[3]
    p5 = pages[4]

    pages = [p1, p2, p3, p4, p5]

    for page in pages:
        assert page["properties"]["Position"]["multi_select"][0]["name"] == "Engineer"
        assert page["properties"]["Company Name"]["title"][0]["text"]["content"] == "Company"

    await asyncio.sleep(1)
    await db._batch_delete_pages(pages)



# if __name__ == '__main__':
# test only works if they are not ran with      pytest.main([__file__])