# Configs Documentation

## Preface

| Table of Contents                             | About                                                          |
|:----------------------------------------------|:---------------------------------------------------------------|
| **Configuration Files**                       |                                                                |
| [sources.yaml](#sourcesyaml)                  | config with target URLs and API endpoints to be fetched.       |
| [filters.yaml](#filtersyaml)                  | Reusable extraction rules, data cleaning logic.                |
| [extensions.yaml](#extensionsyaml)            | Custom plugins or modules for advanced parsing.                |
| [types.yaml](#typesyaml)                      | Static configuration defining job categories and board schema. |
| **Appendix**                                  |                                                                |
| [Supported Parsers](#supported-parsers)       | List of available extraction engines.                          |
| [Relative Date Syntax](#relative-date-syntax) | Documentation for `--relative` flag.                           |
| [RSS Functionality](#rss-functionality)       | Documentation for RSS.                                         |
| [JSON Path Formatting](#json-path-formatting) | Syntax for selecting and serializing API data.                 |

### Configuration Architecture

The configuration files serve as the application's single **source of truth**. 
These modules are interconnected, following a specific dependency hierarchy:

> **Filters ← Sources:** 
> Filter logic is coupled to the specific context <span style="color: grey; opacity: 0.9;">[source_id]</span> provided by the Sources.

> **Sources → Extensions:**
> API-based sources rely on Extensions to configure headers, payloads, and request parameters.


## Sources.yaml

### Field Reference

| Field             | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                       |
|:------------------|:---------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`url`**         | Yes      | The target URL or API endpoint to fetch data from.                                                                                                                                                                                                                                                                                                                                                                |
| **`robots_url`**  | No       | The location of the `robots.txt` file. Used if the parser needs to verify scraping permissions.                                                                                                                                                                                                                                                                                                                   |
| **`parser_type`** | No       | The extraction engine to use (e.g., `StaticContentParser`, `DownloadCSVParser`). <br><br>_Defaults to `StaticContentParser` if left empty._ <br><br> See [Supported Parsers](#supported-parsers) for options.                                                                                                                                                                                                     |
| **`date_format`** | Yes*     | The pattern used to parse the date string. Supports two modes:<br><br>1. **Standard:** Python strptime codes (e.g., %b %d). <br>_Note: The format must include %d._ <br><br>2. **Relative:** Use the `--relative` flag for relative dates (e.g., `--relative {n}d` for "2 days ago"). <br>_*Required if `date` is present in selectors._ <br><br> See [Relative Date Syntax](##relative-date-syntax) for details. |
| **`rss`**         | No       | Enables RSS feed generation for this source. <br><br>Use `--watcher <name>` to select a handler from `rss.watcher` (e.g., `--watcher readme`). <br><br>See [RSS Functionality](#rss-functionality) for more details.                                                                                                                                                                                              |
| **`source_id`**   | Yes      | An identifier used to reference this site in `Filters.yaml`. <br>_Note: Does not need to be globally unique._                                                                                                                                                                                                                                                                                                     |


### Selectors
A dictionary mapping data fields to their CSS selectors (for HTML), columns (for CSV), or JSON paths (for API).

See **[Json Path Formating](#json-path-formatting)** for details on writing API selectors.

| Selector           | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|:-------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`company_name`** | Selector for the hiring company's name.                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **`position`**     | Selector for the job title or role.                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **`date`**         | Selector for the posting date. Must match the logic defined in `date_format`.                                                                                                                                                                                                                                                                                                                                                                                  |
| **`link`**         | **(Required)** Selector for the direct application link.                                                                                                                                                                                                                                                                                                                                                                                                       |
| **`description`**  | Selector for the full job description text.                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **`pay`**          | Selector for salary or compensation information.                                                                                                                                                                                                                                                                                                                                                                                                               |
| **`location`**     | Selector for the job location (City, Remote, etc).                                                                                                                                                                                                                                                                                                                                                                                                             |
| **`type`**         | The Job Category (e.g., `Software Engineer`, `DevOps`). Must match a valid key in `types.yaml`. <br><br>Modes: <br><br>1. **Forced(Naive):** If set, every job from this source is assigned this category. <br><br>2. **Automatic (Semantic):** If left empty, the system uses AI to classify each job based on its description. <br><br>⚠️ Warning: Only use Forced mode for niche boards. Assigning `SWE` to a mixed job board will incorrectly label roles. |


## Filters.yaml

This configuration file controls filters in the **Data Processing Pipeline**. It defines rules for cleaning data, ignoring unwanted jobs, and normalizing formats before they reach the board.

The file is divided into two primary scopes:
1.  **`General`**: Rules applied globally to **all** sources.
2.  **`Specific`**: Rules applied only to a specific `source_id`.

> **Note on Precedence:** The processor automatically handles deduplication. It is safe (though redundant) to have the same rule in both `General` and `Specific`; the system will apply them without conflict.

### Configuration Structure

| Scope          | Description                                                                                                                                                     |
|:---------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`General`**  | Global constraints. Useful for banning universal keywords (e.g., "Senior", "PhD") or cleaning common artifacts.                                                 |
| **`Specific`** | A dictionary where keys are **`source_id`s** (from `sources.yaml`). Use this for site-specific quirks (e.g., a specific "Locked" emoji used only by one board). |

### Available Processors

Currently, the pipeline supports the following filter types. New filters can be added in `parser.components.pipelines.data_processing.data_processors` in the class `FiltersProcessor`.

#### 1. Ignore (`ignore`)
Drops a job entry if a specific field contains a forbidden substring.

| Parameter      | Type      | Description                                                                           |
|:---------------|:----------|:--------------------------------------------------------------------------------------|
| **`position`** | List[str] | Ignores the job if the title contains any of these strings (e.g., "Graduate", "PhD"). |
| **`link`**     | List[str] | Ignores the job if the URL text/anchor contains any of these strings (e.g., "🔒").    |

> _Note: parameters are based of selectors meaning you can apply this filter to any selector_
#### 2. Scrub & Forward Fill (`scrubAndFfill`)
Designed for tables where the company name is listed once at the top, and subsequent rows use a placeholder character to indicate "same as above."

| Parameter  | Type      | Description                                                                                                                         |
|:-----------|:----------|:------------------------------------------------------------------------------------------------------------------------------------|
| **`char`** | List[str] | The placeholder character(s) to treat as "null." When found, the parser replaces it with the most recently seen valid company name. |

## Extensions.yaml

This file serves as the central configuration for `services.resources.extensions`.

**What is an Extension?**
Extensions are specialized `ResourceManagers` that strictly **add capabilities** to the application without altering the core functionality of `get_browser_manager` or `get_session`. They are typically used to integrate third-party services or specialized API clients (e.g., the HireBase API).

### HireBase Manager (`hire_base_manager`)
Configuration for the HireBase API extension. This controls how queries are constructed and sent to the endpoint.

| Field               | Type              | Description                                                                                                                                                                   |
|:--------------------|:------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **`query_postfix`** | String (Optional) | A string automatically appended to every search query.<br>_Example: Setting this to `'Intern'` converts a query for `"Software Engineer"` into `"Software Engineer Intern"`._ |
| **`defaults`**      | Dictionary        | The static payload parameters sent with every API request.                                                                                                                    |

#### Defaults Configuration
These values define the standard behavior for the API client.

| Parameter         | Value (Example)  | Description                                                                                                        |
|:------------------|:-----------------|:-------------------------------------------------------------------------------------------------------------------|
| **`search_type`** | `'summary'`      | The mode of search to perform.                                                                                     |
| **`accuracy`**    | `'high'`         | The precision level of the results.                                                                                |
| **`top_k`**       | `10000`          | The number of candidate results to consider before filtering. <br>_Note: Kept high to accommodate date filtering._ |
| **`limit`**       | `100`            | The max number of results to return per page.                                                                      |
| **`page`**        | `1`              | The starting page index.                                                                                           |
| **`job_type`**    | `['Internship']` | A list of job types to filter by (e.g., Full-time, Internship).                                                    |

## Types.yaml

This file contains the **static configuration** defining the valid job categories (taxonomies) for the application. It dictates the structure of the job board and validates job classification.

### Key Functions
1.  **Board Schema:** Defines which columns/categories appear on the job board.
2.  **Query Generation:** For parsers like `HireBase`, these types are converted into search queries to fetch data.

> **⚠️ Limit Warning (HireBase Only):**
> If using the `hire_base` parser, the system treats these types as individual search queries. If more than **10 types** are defined, only the **first 10** will be used to prevent API rate limiting.

## appendix

<a id="supported-parsers"></a>
### Supported Parsers

> _Implementation can be found in : `parser.core.parser_types`_

* DownloadCSVParser
* SeleniumDownloadParser 
* SticContentParser 
* JaScriptContentParser 
* HireBaseParser

<a id="relative-date-syntax"></a>
### Relative Date Syntax

The `--relative` flag is used to parse "natural language" dates (e.g., *"Posted 2 days ago"*). It works by matching a specific text pattern and extracting the number.

**How it works:**
1.  **Pattern Matching:** You provide a template string where `{n}` represents the number.
2.  **Flexible Spacing:** Spaces in your template match any amount of whitespace (e.g., "2days" matches "2 days").
3.  **Freshness Filter:** Currently, the system **automatically filters** results. Only jobs with `{n}` equal to **0** or **1** (Today or Yesterday) are kept.

#### Usage
To use it, look at the text on the website and replace the number with `{n}`.

| Website Text            | Your Config Flag                      | Result    |
|:------------------------|:--------------------------------------|:----------|
| "Posted **2** days ago" | `--relative Posted {n} days ago`      | `2`       |
| "Active **5**d ago"     | `--relative Active {n}d ago`          | `5`       |
| "new"                   | *(Not supported - requires a number)* | *Skipped* |

<a id="rss-functionality"></a>
### RSS Functionality

The `rss` field enables a **Watcher** to monitor a source for updates. Instead of parsing on a schedule, the Watcher polls the source and triggers the parser **only when a change is detected**.

**Syntax:**
```yaml
rss: '--watcher <handler_name>'
```

| Handler Name | Target         | Description                                                                                     |
|:-------------|:---------------|:------------------------------------------------------------------------------------------------|
| readme       | GitHub READMEs | Uses the GitHub API to check for commit changes or content updates on a repository README file. |

> ⚠️ Usage Warning: Do not implement a watcher for sites that restrict frequent requests or do not have a dedicated API.
 
<a id="json-path-formatting"></a>
### JSON Path Formatting

When using an **API** parser, selectors use **dot notation** to traverse the JSON structure.

**Example Response:**
```json
{
  "job": {
    "details": {
      "title": "Software Engineer",
      "remote": true,
      "skills": ["Python", "Rust"]
    }
  }
}
```

#### 1. Selecting Data

| Target | Selector Path | Result |
| :--- | :--- | :--- |
| **Specific Value** | `job.details.remote` | `true` |
| **Specific Text** | `job.details.title` | `"Software Engineer"` |
| **Entire Object** | `job.details` | `{ "title": "...", "remote": ... }` |

#### 2. Output Serialization (HireBase)

| Data Type | Formatting Rule | Example Output |
| :--- | :--- | :--- |
| **List** | Joined by commas | `"Python, Rust"` |
| **Dictionary** | Newline-separated Key: Value pairs | `"title: Software Engineer\nremote: true"` |
| **Null/None** | Converted to empty string | `""` |
| **Primitives** | Converted to string | `"123"` |