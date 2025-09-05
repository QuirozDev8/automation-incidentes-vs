import os 
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

# Cargar variables del .env
load_dotenv()

JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")

url = f"{JIRA_BASE_URL}/rest/api/3/project"
auth = HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)

headers = {
    "Accept": "application/json"
}

response = requests.get(url, headers=headers, auth=auth)

print("Status:", response.status_code)
print("Response:", response.json())