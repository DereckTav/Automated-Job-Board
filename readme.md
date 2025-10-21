# ~~📄[Current Running Job Board](https://www.notion.so/27b048332b688091a681db0cde874ec8?v=27b048332b6881afa220000cb5955f01&source=copy_link)~~  (not running right now)

---

# Automated Job Board

An automated job board that aggregates and displays the latest job postings from multiple sources, updated every 2 days.

## Description

---
keeps track of new job openings without the need for human searching by centralizing the employment hunt by automatically gathering new opportunities from many job boards. Helps Track applications and maintain an efficient job search workflow, all through notion.

    Key Features

    - Automatic updates every 3 to 24 hours
    - Application tracking and management
    - Only shows jobs posted within the last 2 days

## Table of Contents

---
- [Installation](#installation)
- [Configuration](#configuration)
- [websitesl.yaml setup](#instructions-for-setting-up-websitesyaml)
- [Usage](#usage)
- [Extra Info](#extra-info)


## Installation

---
Step-by-step instructions on how to get the project running locally:

```bash
# Clone the repository
git clone https://github.com/DereckTav/Automated-Job-Board.git

# Navigate to project directory
cd job-board-aggregator

# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

---
Before running the script, ensure `websites.yaml` is created and properly configured with:
- Job board URLs
- Parsing instructions (selectors) for each site
- Any required selectors (`company_name`,`position`)

---
### Instructions for setting up websites.yaml

create file called `websites.yaml` at root

[test.yaml](Test/test.yaml) provides a basic example of how to set up websites.yaml

`websites.yaml` contains the necessary configuration for job boards and their parsing instructions.

---
## Usage

---
### Basic Usage


The script runs via terminal/command line.

```bash
python main.py
```

Press `Ctrl+C` to stop

---
### Running 24/7 (Background Execution)

#### Docker

Docker provides consistent behavior across Windows, Mac, and Linux.

#### Commands:
```bash
# Start (builds if needed)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart

# View status
docker-compose ps
```

## **EXTRA INFO**

---
All parsers except `download_parser` use `-relative` to signify that
the date that is being used is relative

meaning download_parser doesn't work with relative dates