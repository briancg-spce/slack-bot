import os
import logging
from flask import Flask, request
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient
from waitress import serve
import requests

# Define constants
INSTALLATIONS_DIR = './data/installations'
STATES_DIR = './data/states'
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
SIGNING_SECRET = os.environ["SIGNING_SECRET"]
SLACK_TOKEN = os.environ["SLACK_TOKEN"]
API_ENDPOINT = os.environ["API_ENDPOINT"]
REDIRECT_URI_BASE = os.environ["REDIRECT_URI_BASE"]

# Configure logging
logging.basicConfig(level=logging.DEBUG)


# Set up directories
def setup_directory(dir_path):
  if not os.path.exists(dir_path):
    os.makedirs(dir_path)
  os.chmod(dir_path, 0o755)


setup_directory(INSTALLATIONS_DIR)
setup_directory(STATES_DIR)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# OAuth settings and app initialization
redirect_uri = f"{REDIRECT_URI_BASE}/slack/oauth_redirect"

oauth_settings = OAuthSettings(
  client_id=CLIENT_ID,
  client_secret=CLIENT_SECRET,
  scopes=[
    "chat:write", "im:write", "im:history", "chat:write.public", "commands",
    "im:read", "channels:join", "channels:read", 
    "channels:write.public", "channels:write.topic", "chat:write.customize",
    "groups:read", "groups:write"
  ],
  installation_store=FileInstallationStore(base_dir=INSTALLATIONS_DIR),
  state_store=FileOAuthStateStore(expiration_seconds=600, base_dir=STATES_DIR),
  redirect_uri=redirect_uri)

app = App(signing_secret=SIGNING_SECRET, oauth_settings=oauth_settings)

# WebClient for sending messages
client = WebClient(token=SLACK_TOKEN)


# Event listener for DMs (Direct Messages) to the bot
@app.event("message")
def handle_direct_message(body, event, say):
  if event.get("channel_type") == "im":
    message_text = event['text']
    # OPTIONAL: add 'thinking' message
    # say("Thinking...")

    # Log the message text
    logging.debug(f"Received message: {message_text}")

    try:
      # Make a POST request with the question in the JSON body
      response = requests.post(API_ENDPOINT, json={"question": message_text})
      logging.debug(f"Response status code: {response.status_code}")
      logging.debug(f"Response content: {response.content}")

      if response.status_code == 200:
        response_json = response.json()
        response_text = response_json.get('text', 'No response')
      elif response.status_code == 400:
        response_text = "Invalid input. Please try again."
      elif response.status_code == 500:
        response_text = "Something went wrong. Please try again later."
      else:
        response_text = f"Request failed with status code {response.status_code}"
    except Exception as e:
      logging.error(f"Error occurred: {e}")
      response_text = "An error occurred while processing your request."

    # Log the response text
    logging.debug(f"Response text: {response_text}")

    say(response_text)


# Flask app and routes
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
  return handler.handle(request)


@flask_app.route("/slack/install", methods=["GET"])
def install():
  return handler.handle(request)


@flask_app.route("/slack/oauth_redirect", methods=["GET"])
def oauth_redirect():
  return handler.handle(request)


@flask_app.route('/')
def hello_world():
  return 'Hello from the Slack bot instance! Now trying OAuth'


# Run the app on Waitress server
if __name__ == "__main__":
  port = int(os.environ.get('PORT', 10000))
  serve(flask_app, host='0.0.0.0', port=port)
