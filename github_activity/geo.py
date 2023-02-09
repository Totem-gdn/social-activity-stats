import os
import time

import requests
from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

DELAY_NEW_EVENT = 6
DELAY_GITHUB_EVENT = 86400
AUTH = os.environ['GITHUB_TOKEN']
PROJECT_ID = 2733685
# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(os.environ['GITHUB_MIXPANEL_TOKEN'], consumer=mp_consumer)
def geoGithub():
    while True:
        url = f"https://api.github.com/orgs/Totem-gdn/repos"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Token {AUTH}"
        }

        response = requests.get(url, headers=headers)
        repos = [repo["url"] for repo in response.json()]

        contributors = set()
        for repo in repos:
            repo_contrib_url = f"{repo}/contributors?per_page=1000&anon=1"
            repo_contrib_response = requests.get(repo_contrib_url, headers=headers)
            for contributor in repo_contrib_response.json():
                if 'login' in contributor:
                    contributors.add(contributor["login"])

        for user in contributors:
            user_url = f"https://api.github.com/users/{user}"
            user_response = requests.get(user_url, headers=headers)
            location = user_response.json()["location"]
            ts = int(time.time() * 1000)
            properties = {
                "time": ts,
                "distinct_id": user,
                "$insert_id": ts,
                "username": user,
                "location": location
            }

            mp_client.track(user, "GithubUserGeo-v2", properties)
            time.sleep(DELAY_NEW_EVENT)
        time.sleep(DELAY_GITHUB_EVENT)


def githubGeo_main():
    geoGithub()
