#!/usr/bin/env python

import datetime
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import requests
from environs import Env

env = Env()

CACHE_DIR = Path(".seen")
if not CACHE_DIR.exists():
    CACHE_DIR.mkdir()

SLACK_URL = "https://slack.com/api/chat.postMessage"
SLACK_CHANNEL = env.str("SLACK_CHANNEL")
SLACK_TOKEN = env.str("SLACK_TOKEN")

GITHUB_REPOS = [
    "fleet-platform",
    "fleet-alerts",
    "fleet-charging",
    "fleet-optimizer",
    "fleet-meter",
    "es-config",
    "energy-cost",
    "energy-management",
    "telematics",
    "cppyutils",
    "es-infrastructure",
]


@dataclass
class PullRequest:
    repo: str
    author: str
    title: str
    url: str


def get_pull_requests(repo: str, created_dt_range: Tuple[datetime.datetime, datetime.datetime]) -> List[PullRequest]:
    created_dt_start, created_dt_end = created_dt_range

    created_dt_start = created_dt_start.isoformat(timespec="seconds")
    created_dt_end = created_dt_end.isoformat(timespec="seconds")

    command = [
        "gh",
        "pr",
        "--repo",
        f"ChargePoint/{repo}",
        "list",
        "--search",
        f"created:{created_dt_start}..{created_dt_end} -label:dependencies",
        "--json",
        "author,title,url",
    ]

    # print(" ".join(command))

    res = subprocess.run(command, capture_output=True, check=True)
    prs = json.loads(res.stdout)

    return [
        PullRequest(
            repo=repo,
            author=pr["author"]["login"],
            title=pr["title"],
            url=pr["url"],
        )
        for pr in prs
    ]


def send_slack_message(pr: PullRequest) -> None:
    text = f"New pull request by *{pr.author}* in *{pr.repo}*: <{pr.url}|*{pr.title}*>"

    resp = requests.post(
        SLACK_URL, json={"channel": SLACK_CHANNEL, "text": text}, headers={"Authorization": f"Bearer {SLACK_TOKEN}"}
    )
    resp.raise_for_status()


def main(created_dt_range: Tuple[datetime.datetime, datetime.datetime]) -> None:
    for repo in GITHUB_REPOS:
        print(f"Processing repo {repo}")
        prs = get_pull_requests(repo, created_dt_range)

        if not prs:
            print("No PRs found")
            print()
            continue

        for pr in prs:
            print(f"Sending Slack notification for PR {pr.url}")
            send_slack_message(pr)

        print()


if __name__ == "__main__":
    sleep_time = int(sys.argv[1])

    last_created_dt_end = None

    while True:
        now = datetime.datetime.utcnow()

        if last_created_dt_end is None:
            created_dt_start = now - datetime.timedelta(seconds=sleep_time)
        else:
            created_dt_start = last_created_dt_end

        created_dt_end = now
        created_dt_range = (created_dt_start, created_dt_end)

        last_created_dt_end = created_dt_end

        print("All datetimes are in UTC")
        print(now)
        print(
            "Searching for PRs created between "
            f"{created_dt_start.isoformat(timespec='seconds')} and "
            f"{created_dt_end.isoformat(timespec='seconds')}"
        )
        print()

        main(created_dt_range)

        print(f"Sleeping for {int(sleep_time / 60)} minutes")
        print()
        print()
        time.sleep(sleep_time)
