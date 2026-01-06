from itertools import islice
from typing import Optional, Dict, Any
from urllib.parse import urlparse


def batch_zip(keys: list, *data: list):
    zipped = zip(*data)
    while True:
        chunk = list(islice(zipped, 3))
        if not chunk:
            break
        yield (dict(zip(keys, values)) for values in chunk)  # (data: dict, data: dict, data: dict)

#TODO fix this for new notion page
def _generate_body(
        database_id: str, company_name: str, position: str,
        url: Optional[str], job_description: Optional[str], company_size: Optional[str]
) -> Dict[str, Any]:

    """ Rich text object -- text.content -- 2000 characters -- (make sure description is under 2000 chars)
        Any URL -- 2000 characters -- if url is not under 2000 just leave domain
        title.text.content -- 2000 chars -- (Title (company name)) slice so its under 2000
        Max characters per option name -- 100 characters -- (position) (slice) """

    if position:
        position = (position.replace(",", " -")
                    .replace("，", " -")
                    .replace("、", " -"))

    body = {
        "parent": {
            "database_id": database_id
        },
        "properties": {
            "Company Name": {
                "title": [{"type": "text", "text": {"content": company_name[:2000]}}],
            },
            "Position": {
                "multi_select": [{"name": position[:100]}],
            },
            "Status": {
                "status": {"name": "Pending"}
            }
        }
    }

    if job_description:
        children = []
        for i in range(0, len(job_description), 2000):
            chunk = job_description[i:i + 2000]
            if chunk.strip():  # Only add non-empty chunks
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}]
                    }
                })

        if children:
            body["children"] = children

    if company_size:
        company_size = company_size.replace(",", " -")
        body["properties"]["Company Size"] = {"multi_select": [{"name": company_size[:100]}]}

    if url:
        if len(url) > 2000 or not url:
            parsed = urlparse(url)
            url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None

        body["properties"]["Application Link"] = {"url": url}

    return body