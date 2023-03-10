import datetime
import json
import logging
import os
import threading
import time
import timeit

import requests
import tweepy
from github import Github
from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer
from mixpanel_utils import MixpanelUtils
from tweepy import Cursor

logger = logging.getLogger(__name__)

# Get logging level from config file - default to INFO
logger.setLevel(logging.getLevelName("INFO"))

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(os.environ["TWITTER_MIXPANEL_TOKEN"], consumer=mp_consumer)

# Creating a Mixpanel utils

# Get access to Twitter account
auth = tweepy.OAuth1UserHandler(os.environ['TWITTER_CONSUMER_KEY'], os.environ['TWITTER_CONSUMER_SECRET'])
auth.set_access_token(os.environ['TWITTER_ACCESS_TOKEN'], os.environ['TWITTER_ACCESS_TOKEN_SECRET'])
# Initialization Twitter API
api = tweepy.API(auth, wait_on_rate_limit=True)
client = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], consumer_key=os.environ["TWITTER_CONSUMER_KEY"],
                       consumer_secret=os.environ["TWITTER_CONSUMER_SECRET"],
                       access_token=os.environ["TWITTER_ACCESS_TOKEN"],
                       access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"])


USERNAME = 'Totem-gdn'
# pygithub object
g = Github(os.environ['GITHUB_TOKEN'])
# get that user by username
user = g.get_user(USERNAME)


DELAY_NEW_TWEETS = 300
DELAY_UPDATE_FOLLOWERS = 900
DELAY_ENGAGMENT_RATE = 3600
DELAY_ERROR = 360
DELAY_NEW_EVENT = 6
UPDATE_THRESHOLD = 5

# Load previous followers from file
with open('previous_followers.json', 'r') as f:
    previous_followers = set(json.load(f))

def get_blockchain_address(twitter_link):
    url = "https://script.google.com/macros/s/AKfycbxChdtPvHwetbIaGJqjbx2IkSI-zBOZIB7z3Gxss2TwuMikbWyqjbuWr4MEIjUrY4IO/exec"

    params = {"twitter_link": twitter_link}

    response = requests.get(url, params=params)

    if response.status_code == 200:
        blockchain_address = response.text
        print(f"The blockchain address for {twitter_link} is: {blockchain_address}")
    else:
        blockchain_address = None
        print(f"Error: {response.text}")
    return blockchain_address
def followers_control():
    while True:
        global previous_followers

        # Get your followers
        followers_id = get_twitter_follower_ids()

        # Compare followers
        current_followers = set(followers_id)
        new_followers = current_followers.difference(previous_followers)
        unfollowers = previous_followers.difference(current_followers)
        logger.info("new followers {}".format(new_followers))
        logger.info("unfollow {}".format(unfollowers))
        # Update previous_followers
        with open('previous_followers.json', 'w') as f:
            # Write the set to the file using JSON encoding
            json.dump(list(current_followers), f)

        if len(new_followers) > 1000:
            if len(new_followers) > 0:
                for follower_id in new_followers:
                    try:
                        new_follower_event(follower_id)
                        logger.info("New followers: {}".format(follower_id))
                    except tweepy.errors.NotFound:
                        logger.error("User with id {} not found".format(follower_id))
            else:
                logger.info("No new followers detected.")
            if len(unfollowers) > 0:
                for unfollower_id in unfollowers:
                    try:
                        try:
                            unfollower_event(unfollower_id)
                            logger.info("Unfollowers: {}".format(unfollowers))
                        except tweepy.errors.NotFound:
                            logger.error("User with id {} not found".format(unfollower_id))
                    except tweepy.errors.Forbidden:
                        logger.error("User with id {} frozen".format(unfollower_id))
                else:
                    logger.info('No new unfollowers detected.')
        else:
            logger.info("Previous followers updated")
        time.sleep(DELAY_UPDATE_FOLLOWERS)


def get_twitter_follower_ids():
    followers = []
    # Get follower IDs from Twitter API
    for follower_id in Cursor(api.get_follower_ids, count=200).items():
        followers.append(str(follower_id))
    return followers


def new_follower_event(user_id):
    try:
        # Get user data from Twitter API
        user_data = api.get_user(user_id=user_id)
        user_json = json.dumps(user_data._json)
        user = json.loads(user_json)
        twitter_link = 'https://twitter.com/' + user['screen_name']

        distinct_id = user['id_str']
        version = get_commit_version()
        # Set properties for the Mixpanel event
        properties = {
            'followersCount': str(user['followers_count']),
            'friendsCount': str(user['friends_count']),
            '$name': user['name'],
            'screenName': user['screen_name'],
            'verified': str(user['verified']),
            'Version': version,
            'blockchainAddress': get_blockchain_address(twitter_link)
        }
        if user['location'] != '':
            properties['location'] = user['location']

        # Create MixPanel event
        mp_client.track(distinct_id, 'FollowersCount', properties)
        logger.info('NewFollower event: {}'.format(user['id_str']))
        time.sleep(DELAY_NEW_EVENT)
    except tweepy.errors.Forbidden as err:
        print('User has been suspended')


def unfollower_event(user_id):
    # Get user data from Twitter API
    user_data = api.get_user(user_id=user_id)
    user_json = json.dumps(user_data._json)
    user = json.loads(user_json)

    try:
        version = get_commit_version()
        distinct_id = user['id_str']
        # Set properties for the Mixpanel event
        properties = {
            'followersCount': str(user['followers_count']),
            'friendsCount': str(user['friends_count']),
            '$name': user['name'],
            'screenName': user['screen_name'],
            'Version': version,
            'blockchainAddress': get_blockchain_address(user['screen_name'])
        }

        # Create MixPanel event
        mp_client.track(distinct_id, 'UnfollowedCount', properties)
        logger.info('UserUnfollowed event created: {}'.format(distinct_id))
        time.sleep(DELAY_NEW_EVENT)
    except tweepy.errors.Forbidden as err:
        print('User has been suspended')


def send_tweet_to_mixpanel(id):
    status = api.get_status(id, tweet_mode="extended")
    # Convert tweepy.models.Status to JSON
    data_json = json.dumps(status._json)
    # Convert JSON to dict
    tweet_data = json.loads(data_json)
    # Get params from tweet data
    user = tweet_data['user']
    hashtags = tweet_data['entities']['hashtags']
    distinct_id = user['screen_name']
    version = get_commit_version()
    url = "https://twitter.com/user/status/{}".format(id)
    # Set properties for Mixpanel
    properties = {
        'createdAt': tweet_data['created_at'],
        'followersCount': user['followers_count'],
        'ID': tweet_data['id_str'],
        'lang': tweet_data['lang'],
        'retweetCount': tweet_data['retweet_count'],
        'text': tweet_data['full_text'],
        'retweeted': 'False',
        'url': url,
        'Version': version
    }

    if len(hashtags) != 0:
        hashtag_str = ''
        for hashtag in hashtags:
            hashtag_str += ''.join(hashtag['text'] + ',')

        properties['hashtag'] = hashtag_str.rstrip(',')

    if 'retweeted_status' in tweet_data:
        retweetedUserName = tweet_data['entities']['user_mentions'][0]['screen_name']

        properties['retweeted'] = 'True'
        properties['retweetedUserName'] = retweetedUserName

    if 'media' in tweet_data['entities']:
        properties['mediaUrl'] = tweet_data['entities']['media'][0]['media_url']

    # Send to Mixpanel
    mp_client.track(distinct_id, 'NewTweet', properties)
    logger.info('\nNew tweet: {}'.format(tweet_data['full_text']))


def get_engagement_rate_event():
    while True:
        tweets = client.get_users_tweets(os.environ["TWITTER_ACCOUNT_ID"])
        version = get_commit_version()
        retweet_count = 0
        reply_count = 0
        like_count = 0
        quote_count = 0
        tweets_count = 0
        for id in tweets[0]:
            response = client.get_tweets(
                ids=id['id'],
                tweet_fields=["public_metrics"],
                expansions=["attachments.media_keys", 'author_id'],
                media_fields=["public_metrics"],
                user_fields=["public_metrics"],
            )
            followers_count = response.includes['users'][0].public_metrics['followers_count']
            retweet_count += response.data[0].public_metrics['retweet_count']
            reply_count += response.data[0].public_metrics['reply_count']
            like_count += response.data[0].public_metrics['like_count']
            quote_count += response.data[0].public_metrics['quote_count']
            tweets_count += 1
        engagement_rate = (
                                  retweet_count + reply_count + like_count + quote_count) / tweets_count / followers_count * 100
        if 0 <= engagement_rate <= 0.005:
            level_engagements_rate = 'Need improvement'
        elif 0.005 <= engagement_rate <= 0.037:
            level_engagements_rate = 'Not bad'
        elif 0.037 <= engagement_rate <= 0.098:
            level_engagements_rate = 'Good'
        elif 0.098 <= engagement_rate:
            level_engagements_rate = 'Awesome'
        else:
            level_engagements_rate = 'Unknow'
        properites = {
            'Likes per tweet': str(like_count / tweets_count),
            'Replies per tweet': str(reply_count / tweets_count),
            'Retweet per tweet': str(retweet_count / tweets_count),
            'Engagement rate': str('%.3f' % engagement_rate),
            'Level of engagement rate': level_engagements_rate,
            'Version': version
        }
        mp_client.track('TotemGDN', 'EngagementStats', properites)
        logger.info('EngagementStats event created')
        time.sleep(DELAY_ENGAGMENT_RATE)


def get_new_tweets():
    timeit.timeit('_ = session.get("https://twitter.com")', 'import requests; session = requests.Session()',
                  number=100)
    backoff_counter = 1
    while True:
        try:
            now = datetime.datetime.now()
            last_five_minutes = now - datetime.timedelta(minutes=5)
            tweets = client.get_users_tweets(os.environ["TWITTER_ACCOUNT_ID"], start_time=last_five_minutes)
            tweet = tweets[0]
            if tweet is not None:
                for i in tweet:
                    send_tweet_to_mixpanel(i['id'])
                    time.sleep(6)
            else:
                logger.info('Doesn`t have new tweets for last 5 minutes')
                pass
            time.sleep(DELAY_NEW_TWEETS)
        except Exception as e:
            print(e)
            time.sleep(60 * backoff_counter)
            backoff_counter += 1
            continue


def get_commit_version():
    with open('twitter_activity_version.txt') as f:
        version = f.read()
    return version


def twitter_main():
    logger.info('--- Twitter analysis starting ---')

    threads = []

    new_tweets_thread = threading.Thread(target=get_new_tweets)
    threads.append(new_tweets_thread)
    followers_control_thread = threading.Thread(target=followers_control)
    threads.append(followers_control_thread)
    engagement_rate_thread = threading.Thread(target=get_engagement_rate_event)
    threads.append(engagement_rate_thread)

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    logger.info('--- Twitter analysis died ---')
