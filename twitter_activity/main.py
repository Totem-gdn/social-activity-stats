import datetime
import json
import logging
import os
import threading
import time
import timeit

import mixpanel
import tweepy
from tweepy import Cursor

from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer
from mixpanel_utils import MixpanelUtils

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

mputils = MixpanelUtils(
    os.environ["TWITTER_MIXPANEL_SERVICE_ACCOUNT_SECRET"],
    service_account_username=os.environ["TWITTER_MIXPANEL_SERVICE_ACCOUNT"],
    project_id=os.environ["TWITTER_MIXPANEL_PROJECT_ID"],
    token=os.environ["TWITTER_MIXPANEL_TOKEN"],
    eu=True
)

DELAY_NEW_TWEETS = 300
DELAY_UPDATE_FOLLOWERS = 900
DELAY_UPDATE_PROFILES = 86400
DELAY_SEND_TO_MIXPANEL = 4
DELAY_ERROR = 360
UPDATE_THRESHOLD = 5

def get_mixpanel_profile_id():
    # Set the selector for the query to find profiles where the Unfollowed property is defined and set to "False"
    selector = '(defined (properties["Unfollowed"]) and properties["Unfollowed"] == "False")'

    # Set the parameters for the query with the selector
    parameters = {'selector': selector}

    # Get the data from the query
    mp_profiles_users = mputils.query_engage(params=parameters)

    # Initialize an empty list to store the profile IDs
    profile_ids = []

    # Iterate through the data and add the profile IDs to the list
    for profile in mp_profiles_users:
        profile_ids.append(profile['$properties']['Profile ID'])

    # Return the list of profile IDs
    return profile_ids


def update_profile_to_mixpanel(user):
    # Set properties for Mixpanel Profile
    properties = {
        'followersCount': str(user['followers_count']),
        'FriendsCount': str(user['friends_count']),
        'geoEnabled': str(user['geo_enabled']),
        'Profile ID': user['id_str'],
        '$name': user['name'],
        'screenName': user['screen_name'],
        'Unfollowed': 'False'
    }
    if 'profile_image_url' in user:
        properties['profileImgUrl'] = user['profile_image_url']
    if user['location'] != '':
        properties['location'] = user['location']

    # Send to MixPanel Profile
    mp_client.people_set(user['id_str'], properties)


def get_followers_data():
    # Set the threshold for updating a Mixpanel profile to 5% change in followers count

    while True:
        time.sleep(DELAY_UPDATE_PROFILES)  # Sleep for 86400 seconds (1 day) before checking again
        count = 0
        followers = []
        profiles_followers = {}

        # Get followers data from Twitter
        for follower in Cursor(api.get_followers, count=200).items():
            count += 1
            follower_json = json.dumps(follower._json)
            follower_data = json.loads(follower_json)
            followers.append(follower_data)

        # Get users profiles from Mixpanel
        selector = '(defined (properties["Unfollowed"]) and properties["Unfollowed"] == "False")'
        parameters = {'selector': selector}
        mp_profiles_users = mputils.query_engage(params=parameters)

        # Associate profile id with followers count
        for profile in mp_profiles_users:
            try:
                profiles_followers[profile['$properties']['Profile ID']] = profile['$properties']['followersCount']
            except KeyError:
                logger.error("Profile is missing a followers count value: ", profile)

        # Check if the followers count for each follower has changed by more than the update threshold
        for follower in followers:
            try:
                followers_diff = (int(profiles_followers[follower['id_str']]) - int(follower['followers_count'])) / int(
                    profiles_followers[follower['id_str']]) * 100
                if abs(followers_diff) >= UPDATE_THRESHOLD:
                    update_profile_to_mixpanel(follower)
                    logger.info("Updated profile: ", follower['screen_name'])
                    time.sleep(DELAY_SEND_TO_MIXPANEL)  # Sleep for 4 seconds before updating the next profile
            except (KeyError, ZeroDivisionError):
                logger.info("Profile not found in Mixpanel or followers count is zero: ", follower['screen_name'], "-", follower['id_str'])
        logger.info("Checked follower's data updates.")


def get_twitter_follower_ids():
    followers = []
    # Get follower IDs from Twitter API
    for follower_id in Cursor(api.get_follower_ids, count=200).items():
        followers.append(str(follower_id))
    return followers


def followers_control():
    while True:
        mp_followers_ids = set(get_mixpanel_profile_id())
        updated_list_follower_ids = set(get_twitter_follower_ids())

        new_followers = updated_list_follower_ids.difference(mp_followers_ids)
        unfollowed = mp_followers_ids.difference(updated_list_follower_ids)

        if len(new_followers) != 0:
            for follower_id in new_followers:
                new_follower(follower_id)
        else:
            print("Doesn't have new followers last 15 minutes.")

        if len(unfollowed) != 0:
            for follower_id in unfollowed:
                try:
                    unfollow(follower_id)
                except tweepy.errors.NotFound:
                    logger.error("Follower not found: ", follower_id)
        else:
            print("Doesn't have unfollowers last 15 minutes.")
        print("Followers checked.")
        time.sleep(DELAY_UPDATE_FOLLOWERS)  # Sleep for 15 minutes before checking again


def new_follower(user_id):
    # Get user data from Twitter API
    user_data = api.get_user(user_id=user_id)
    user_json = json.dumps(user_data._json)
    user = json.loads(user_json)

    # Get the current time and format it as a string
    now_time = datetime.datetime.now()
    follow_time = now_time.strftime("%d.%m.%Y %H:%M")

    # Set properties for the Mixpanel profile
    properties = {
        'followersCount': str(user['followers_count']),
        'FriendsCount': str(user['friends_count']),
        'geoEnabled': str(user['geo_enabled']),
        'Profile ID': user['id_str'],
        '$name': user['name'],
        'screenName': user['screen_name'],
        'firstSeenAt': follow_time,
        'Unfollowed': 'False'
    }
    if 'profile_image_url' in user:
        properties['profileImgUrl'] = user['profile_image_url']
    if user['location'] != '':
        properties['location'] = user['location']

    # Send to MixPanel Profile
    mp_client.people_set(user['id_str'], properties)
    logger.info('New follower: {}'.format(user['id_str']))
    time.sleep(DELAY_SEND_TO_MIXPANEL)


def unfollow(user_id):
    try:
        now_time = datetime.datetime.now()
        unfollow_time = now_time.strftime("%d.%m.%Y %H:%M")
        selector = '(defined (properties["Unfollowed"]) and properties["Unfollowed"] == "False")'
        parameters = {'selector': selector}
        mp_profiles_users = mputils.query_engage(params=parameters)
        for profile in mp_profiles_users:
            if profile['$properties']['Profile ID'] == user_id:
                properties = {
                    'Unfollowed': unfollow_time
                }
                # Send properties to Mixpanel profile
                mp_client.people_set(profile['$distinct_id'], properties)
                logger.info('Unfollowed: {}'.format(profile['$distinct_id']))
                time.sleep(DELAY_SEND_TO_MIXPANEL)  # Sleep for 4 seconds before unfollowing the next user
    except Exception as e:
        print(str(e))
        time.sleep(DELAY_ERROR)  # Sleep for 360 seconds before trying again


def send_tweet_to_mixpanel(id):
    status = api.get_status(id, tweet_mode="extended")
    # Convert tweepy.models.Status to JSON
    data_json = json.dumps(status._json)
    # Convert JSON to dict
    tweet_data = json.loads(data_json)
    print(tweet_data)
    # Get params from tweet data
    user = tweet_data['user']
    hashtags = tweet_data['entities']['hashtags']
    distinct_id = user['screen_name']
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
        'url': url
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
                logger.info('Doesn`t have new tweets for last 5 minutes.')
                pass
            time.sleep(DELAY_NEW_TWEETS)
        except Exception as e:
            print(e)
            time.sleep(60 * backoff_counter)
            backoff_counter += 1
            continue


def twitter_main():
    logger.info('--- Twitter analysis starting ---')

    new_tweets_tread = threading.Thread(target=get_new_tweets)
    followers_control_tread = threading.Thread(target=followers_control)
    new_tweets_tread.start()
    followers_control_tread.start()
    get_followers_data()

    logger.info('--- Twitter analysis died ---')
