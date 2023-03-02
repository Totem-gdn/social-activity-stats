import logging
import os
import time

import requests
from github import Github
from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

USERNAME = 'Totem-gdn'

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(os.environ['GITHUB_MIXPANEL_TOKEN'], consumer=mp_consumer)

# pygithub object
g = Github(os.environ['GITHUB_TOKEN'])
# get that user by username
user = g.get_user(USERNAME)
DELAY_NEW_EVENT = 6
DELAY_GITHUB_EVENT = 1080


def stats_event():
    global DELAY_GITHUB_EVENT
    while True:
        try:
            time.sleep(DELAY_GITHUB_EVENT)
        except ValueError:
            time.sleep(0)
        start_time = time.time()
        for repo in user.get_repos():
            repo_name = repo.full_name
            if repo_name != 'Totem-gdn/.github':
                branches = repo.get_branches()
                stars = repo.stargazers_count
                watchers = repo.watchers
                for branch in branches:
                    branch_name = branch.name
                    contributors_count = len(repo.get_contributors().get_page(0))
                    contributors = repo.get_contributors()
                    contributions = 0
                    for contributor in contributors:
                        contributions += contributor.contributions
                    url = f'https://api.codetabs.com/v1/loc?github={repo_name}&branch={branch_name}&ignored=.gitignore;'
                    try:
                        files = requests.get(url).json()
                        try:
                            lines = files[-1]['linesOfCode']
                            properies = {
                                'branch': branch_name,
                                'contributions': str(contributions),
                                'contributors': str(contributors_count),
                                'lines': str(lines),
                                'repo': repo_name,
                                'stars': str(stars),
                                'watchers': str(watchers)
                            }
                            mp_client.track(distinct_id=repo.full_name, event_name='GitHubLineStats',
                                            properties=properies)
                            time.sleep(6)
                        except KeyError:
                            logging.info(
                                "Not found info about code lenght in {} branch {}".format(repo_name, branch_name))
                    except requests.JSONDecodeError:
                        logging.info(f"{branch_name} in {repo_name} didn`t get info")
            logging.info("Sent to MixPanel GitHubLineStats events")

        end_time = time.time()
        elapsed_time = end_time - start_time
        DELAY_GITHUB_EVENT = DELAY_GITHUB_EVENT - elapsed_time


def github_main():
    stats_event()
