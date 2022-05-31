from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Optional

import boto3
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DUESYNC_GOOGLE_AUTH_TABLE_NAME = os.environ["DUESYNC_GOOGLE_AUTH_TABLE_NAME"]

table = boto3.resource("dynamodb").Table(DUESYNC_GOOGLE_AUTH_TABLE_NAME)
creds_cache: dict[str, tuple[dict[str, Any], Credentials]] = {}


def get_user(username: str) -> tuple[Optional[dict[str, Any]], Optional[Credentials]]:
    # get from local cache first
    user = creds_cache.get(username)

    # then get from dynamodb
    if user:
        print(f"use cached credentials for {username}")
        return user
    else:
        resp = table.get_item(
            Key={
                "username": username
            }
        )
        item = resp.get("Item")
        if not item:
            return None, None

        creds = Credentials(token=None, **item["credentials"])
        creds_cache[username] = (item, creds)

        return item, creds


def get_calendar(creds: Credentials):
    return build("calendar", "v3", credentials=creds)


def create_calendar_body(issue_object: dict[str, Any]) -> Optional[dict]:
    issue_id = issue_object["id"]
    iid = issue_object["iid"]
    title = issue_object["title"]
    url = issue_object["url"]
    description = issue_object["description"]
    state = issue_object["state"]

    date_str = issue_object["due_date"]
    if state == "closed":
        raw_date_str = issue_object["closed_at"]
        if not raw_date_str:
            date_str = None
        
        date_obj = datetime.strptime(raw_date_str, "%Y-%m-%d %H:%M:%S %Z")
        date_str = date_obj.astimezone(timezone(timedelta(hours=9))).date().isoformat()

    if not date_str:
        print("no due date. skip.")
        return None
    
    ret: dict[str, Any] = {
        "start": {
            "date": date_str
        },
        "end": {
            "date": date_str
        },
        "description": description,
        "id": issue_id,
        "source": {
            "title": "GitLab",
            "url": url
        },
        "summary": f"#{iid}: {title}"
    }
    if state == "closed":
        ret["colorId"] = "8"

    print(f"dump event {ret}")
    return ret


def create(creds: Credentials, calendar_id: str, event: dict):
    get_calendar(creds).events().insert(
        calendarId=calendar_id,
        body=event
    ).execute()


def update(creds: Credentials, calendar_id: str, event: dict):
    get_calendar(creds).events().update(
        calendarId=calendar_id,
        eventId=event["id"],
        body=event
    ).execute()


def do(event, context):
    http = event["requestContext"]["http"]
    path: str = http["path"]
    source_ip: str = http["sourceIp"]

    # https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html#issue-events
    gitlab_event = json.loads(event["body"])
    print(f"gitlab_event: {gitlab_event}")

    object_kind = gitlab_event.get("object_kind")
    if object_kind != "issue":
        print("not an issue event. skip...")
        return {
            "statusCode": 200
        }

    issue_object = gitlab_event.get("object_attributes")
    issue_assignees = gitlab_event.get("assignees")
    issue_action = issue_object.get("action")
    print(f"action: {issue_action}")

    assignees: list[str] = [v["username"] for v in issue_assignees]
    if not assignees:
        print("no assignees. skip.")
        return

    body = create_calendar_body(issue_object)
    if not body:
        print("condition not met. skip")
        return

    for a in assignees:
        params, creds = get_user(a)
        if not params or not creds:
            print(f"user {a} not configured. skip.")
            return

        calendar_id: str = params["calendar_id"]

        if issue_action == "open":
            create(creds, calendar_id, body)
        elif issue_action in ["reopen", "update", "close"]:
            try:
                update(creds, calendar_id, body)
            except:
                create(creds, calendar_id, body)

    print("done!")


def handler(event, context):
    do(event, context)

    return {
        "statusCode": 200
    }
