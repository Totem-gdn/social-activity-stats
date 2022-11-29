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

logger = logging.getLogger(__name__)

# Get logging level from config file - default to INFO
logger.setLevel(logging.getLevelName("INFO"))

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(os.environ["TWITTER_MIXPANEL_TOKEN"], consumer=mp_consumer)

# Get access to Twitter account
auth = tweepy.OAuth1UserHandler(os.environ['TWITTER_CONSUMER_KEY'], os.environ['TWITTER_CONSUMER_SECRET'])
auth.set_access_token(os.environ['TWITTER_ACCESS_TOKEN'], os.environ['TWITTER_ACCESS_TOKEN_SECRET'])
# Initialization Twitter API
api = tweepy.API(auth, wait_on_rate_limit=True)
client = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], consumer_key=os.environ["TWITTER_CONSUMER_KEY"],
                       consumer_secret=os.environ["TWITTER_CONSUMER_SECRET"],
                       access_token=os.environ["TWITTER_ACCESS_TOKEN"],
                       access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"])


def update_profile_to_mixpanel(user):
    # Set properties for Mixpanel Profile
    properties = {
        'followersCount': user['followers_count'],
        'FriendsCount': user['friends_count'],
        'geoEnabled': str(user['geo_enabled']),
        'Name': user['name'],
        'Profile ID': user['id'],
        'screenName': user['screen_name']
    }
    if 'profile_image_url' in user:
        properties['profileImgUrl'] = user['profile_image_url']
    if user['location'] != '':
        properties['location'] = user['location']

    # Send to MixPanel Profile
    mp_client.people_set(user['id_str'], properties)


def get_followers_data():
    while True:
        time.sleep(86400)
        count = 0
        followers = []
        for follower in Cursor(api.get_followers, count=200).items():
            count += 1
            follower_json = json.dumps(follower._json)
            follower_data = json.loads(follower_json)
            # print(count, " ", follower_data, '\n')
            followers.append(follower_data)

        for i in followers:
            # print("sent ",i)
            update_profile_to_mixpanel(i)
            time.sleep(4)
        logger.info('Updated all users data.')


def get_follower_ids():
    followers = []
    for follower in Cursor(api.get_follower_ids, count=200).items():
        followers.append(follower)
    return followers


def followers_control():
    followers_ids = set()
    while True:
        updated_list_follower_ids = set(get_follower_ids())

        new_followers = updated_list_follower_ids.difference(followers_ids)
        unfollowed = followers_ids.difference(updated_list_follower_ids)

        if len(new_followers) != 0 and len(new_followers) < 1500:
            for i in new_followers:
                new_follower(i)
        else:
            logger.info('Doesn`t have new followers last 15 minuets.')

        if len(unfollowed) != 0:
            for i in unfollowed:
                unfollow(i)
        else:
            logger.info('Doesn`t have unfollowers last 15 minuets.')
        followers_ids = updated_list_follower_ids
        logger.info('Followers checked.')
        time.sleep(900)


def new_follower(user_id):
    user_data = api.get_user(user_id=user_id)
    user_json = json.dumps(user_data._json)
    user = json.loads(user_json)

    properties = {
        'followersCount': user['followers_count'],
        'FriendsCount': user['friends_count'],
        'geoEnabled': str(user['geo_enabled']),
        'Name': user['name'],
        'Profile ID': user['id'],
        'screenName': user['screen_name'],
        'firstSeenAt': str(datetime.datetime.now())
    }
    if 'profile_image_url' in user:
        properties['profileImgUrl'] = user['profile_image_url']
    if user['location'] != '':
        properties['location'] = user['location']

    # Send to MixPanel Profile
    mp_client.people_set(user['id'], properties)
    logger.info('New follower: ', user_data['username'])
    time.sleep(4)


def unfollow(user_id):
    user = api.get_user(user_id=user_id)
    user_json = json.dumps(user._json)
    user_data = json.loads(user_json)

    properties = {
        'Unfollowed': str(datetime.datetime.now())
    }
    # Send to MixPanel Profile
    mp_client.people_append(user_data['id'], properties)
    logger.info('Unfollwed :', user_data['username'])
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
            hashtag_str += ''.join(hashtag['full_text'] + ',')

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
    while True:
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


def twitter_main():
    logger.info('--- Twitter API starting ---')

    new_tweets_tread = threading.Thread(target=get_new_tweets)
    followers_control_tread = threading.Thread(target=followers_control)
    new_tweets_tread.start()
    followers_control_tread.start()
    get_followers_data()

    logging.info('--- Twitter API done ---')
