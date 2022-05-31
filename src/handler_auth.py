import base64
import json
import os

import boto3
from google_auth_oauthlib.flow import Flow

DUESYNC_GOOGLE_AUTH_TABLE_NAME = os.environ["DUESYNC_GOOGLE_AUTH_TABLE_NAME"]
DUESYNC_GOOGLE_AUTH_CLIENT_CONFIG_JSON = os.environ["DUESYNC_GOOGLE_AUTH_CLIENT_CONFIG_JSON"]
DUESYNC_WEBHOOK_BASE_URL = os.environ["DUESYNC_WEBHOOK_BASE_URL"].removesuffix("/")

# need to config manually (cdk cannot handle this)
DUESYNC_REDIRECT_URL = os.environ["DUESYNC_REDIRECT_URL"]

CONFIG_DICT = json.loads(DUESYNC_GOOGLE_AUTH_CLIENT_CONFIG_JSON)

table = boto3.resource("dynamodb").Table(DUESYNC_GOOGLE_AUTH_TABLE_NAME)
flow = Flow.from_client_config(
    client_config=CONFIG_DICT,
    scopes=[
        "https://www.googleapis.com/auth/calendar.events"
    ],
    autogenerate_code_verifier=True
)
flow.redirect_uri = DUESYNC_REDIRECT_URL

def start_auth(query_params: dict[str, str]):
    username = query_params.get("username")
    calendar_id = query_params.get("calendarId")
    if not username:
        print("missing username")
        return {
            "statusCode": 400,
            "body": "missing username"
        }
    if not calendar_id:
        print("missing calendar_id")
        return {
            "statusCode": 400,
            "body": "missing calendarId"
        }

    params_dict = {
        "username": username,
        "calendar_id": calendar_id
    }
    encoded_params = base64.urlsafe_b64encode(json.dumps(params_dict).encode())

    # start google oauth2
    # https://developers.google.com/identity/protocols/oauth2/web-server#python
    url, _ = flow.authorization_url(
        access_type="offline",
        state=encoded_params,
        include_granted_scopes="true",

    )
    return {
        "statusCode": 302,
        "headers": {
            "Location": url
        }
    }

def callback(query_params: dict[str, str]):
    state_raw = query_params.pop("state")
    params_dict = json.loads(base64.urlsafe_b64decode(state_raw).decode())
    
    username = params_dict["username"]
    calendar_id = params_dict["calendar_id"]
    
    flow.fetch_token(**query_params)
    creds = flow.credentials
    # https://google-auth.readthedocs.io/en/stable/reference/google.oauth2.credentials.html#google.oauth2.credentials.Credentials
    creds_dict = {
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "scopes": creds.scopes,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret
    }

    table.put_item(
        Item={
            "username": username,
            "calendar_id": calendar_id,
            "credentials": creds_dict
        }
    )

    return {
        "statusCode": "200",
        "body": f"Welcome! Your webhook endpoint is\n{DUESYNC_WEBHOOK_BASE_URL}/users/{username}"
    }

def handler(event, context):
    # https://docs.aws.amazon.com/lambda/latest/dg/urls-invocation.html
    http = event["requestContext"]["http"]
    path: str = http["path"]
    source_ip: str = http["sourceIp"]

    query_params = event["queryStringParameters"]

    if path == "/auth":        
        return start_auth(query_params)
    elif path == "/callback":
        return callback(query_params)

    return {
        "statusCode": 200,
        "body": "200 OK"
    }
