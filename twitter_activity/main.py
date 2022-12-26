import datetime
import json
import logging
import os
import threading
import time
import timeit

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


def get_mixpanel_profile_id():
    selector = '(("False" in properties["Unfollowed"]) and (defined (properties["Unfollowed"])))'
    parameters = {'selector': selector}
    data = mputils.query_engage(params=parameters)
    profile_id = []

    for i in data:
        profile_id.append((i['$properties']['Profile ID']))
    return profile_id


def update_profile_to_mixpanel(user):
    # Set properties for Mixpanel Profile
    properties = {
        'followersCount': str(user['followers_count']),
        'FriendsCount': str(user['friends_count']),
        'geoEnabled': str(user['geo_enabled']),
        'Profile ID': user['id_str'],
        'screenName': user['screen_name'],
        'Unfollowed': 'False'
    }
    if 'profile_image_url' in user:
        properties['profileImgUrl'] = user['profile_image_url']
    if user['location'] != '':
        properties['location'] = user['location']

    name_properties = {
        'Name': user['name']
    }
    # Send to MixPanel Profile
    mp_client.people_set(user['id_str'], properties)
    mp_client.people_set_once(user['id_str'], name_properties)



def get_followers_data():
    while True:
        time.sleep(86400)
        count = 0
        followers = []
        profiles_followers = {}

        # Get followers data from Twitter
        for follower in Cursor(api.get_followers, count=200).items():
            count += 1
            follower_json = json.dumps(follower._json)
            follower_data = json.loads(follower_json)
            # print(count, " ", follower_data, '\n')
            followers.append(follower_data)

        # Get users profiles from Mixpanel
        selector = '(("False" in properties["Unfollowed"]) and (defined (properties["Unfollowed"])))'
        parameters = {'selector': selector}
        profiles = mputils.query_engage(params=parameters)

        # Associate profile id with followers count
        for i in profiles:
            try:
                profiles_followers[i['$properties']['Profile ID']] = i['$properties']['followersCount']
            except KeyError:
                logger.error("not value ", i)

        for i in followers:
            try:
                try:
                    followers_diff = (int(profiles_followers[i['id_str']]) - int(i['followers_count'])) / int(
                        profiles_followers[i['id_str']]) * 100
                    if followers_diff >= 5 or followers_diff <= -5:
                        update_profile_to_mixpanel(i)
                        logger.info("Updated profile : ", i['screen_name'])
                        time.sleep(4)
                except ZeroDivisionError:
                    pass
            except KeyError:
                logger.info("Didn't find in Mixpanel ", i['screen_name'], "-", i['id_str'])
        logger.info("Checked follower`s data updates.")


def get_follower_ids():
    followers = []
    for follower in Cursor(api.get_follower_ids, count=200).items():
        followers.append(follower)
    return followers


def followers_control():
    while True:
        followers_ids = set(get_mixpanel_profile_id())
        string_ids = [str(i) for i in get_follower_ids()]
        updated_list_follower_ids = set(string_ids)

        new_followers = updated_list_follower_ids.difference(followers_ids)
        unfollowed = followers_ids.difference(updated_list_follower_ids)

        if len(new_followers) != 0:
            for i in new_followers:
                new_follower(i)
        else:
            print('Doesn`t have new followers last 15 minuets.')

        if len(unfollowed) != 0:
            for i in unfollowed:
                try:
                    unfollow(i)
                except tweepy.errors.NotFound:
                    logger.error("Not found ", i)
        else:
            print('Doesn`t have unfollowers last 15 minuets.')
        print('Followers checked.')
        time.sleep(900)


def new_follower(user_id):
    user_data = api.get_user(user_id=user_id)
    user_json = json.dumps(user_data._json)
    user = json.loads(user_json)
    now_time = datetime.datetime.now()
    follow_time = now_time.strftime("%d.%m.%Y %H:%M")

    properties = {
        'followersCount': user['followers_count'],
        'FriendsCount': user['friends_count'],
        'geoEnabled': str(user['geo_enabled']),
        'Profile ID': user['id_str'],
        'screenName': user['screen_name'],
        'firstSeenAt': follow_time,
        'Unfollowed': 'False'
    }
    if 'profile_image_url' in user:
        properties['profileImgUrl'] = user['profile_image_url']
    if user['location'] != '':
        properties['location'] = user['location']

    name_properties = {
        'Name': user['name']
    }
    # Send to MixPanel Profile
    mp_client.people_set(user['id_str'], properties)
    mp_client.people_set_once(user['id_str'], name_properties)
    logger.info('New follower: {}'.format(user['id_str']))
    time.sleep(4)


def unfollow(user_id):
    user = api.get_user(user_id=user_id)
    user_json = json.dumps(user._json)
    user_data = json.loads(user_json)
    now_time = datetime.datetime.now()
    unfollow_time = now_time.strftime("%d.%m.%Y %H:%M")
    properties = {
        'Unfollowed': unfollow_time
    }
    # Send to MixPanel Profile
    mp_client.people_set(user_data['id_str'], properties)
    logger.info('Unfollowed : {}'.format(user_data['id_str']))
    time.sleep(4)


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
            time.sleep(300)
        except Exception as e:
            print(e)
            time.sleep(60 * backoff_counter)
            backoff_counter += 1
            continue


def twitter_main():
    logger.info('--- Twitter API starting ---')

    new_tweets_tread = threading.Thread(target=get_new_tweets)
    followers_control_tread = threading.Thread(target=followers_control)
    new_tweets_tread.start()
    followers_control_tread.start()
    get_followers_data()

    logging.info('--- Twitter API done ---')
