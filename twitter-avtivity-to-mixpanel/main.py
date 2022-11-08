import datetime
import json
import logging
import threading
import time

import tweepy
from tweepy import Cursor

from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

logger = logging.getLogger(__name__)

# Loading the config
try:
    with open("config.json", 'r') as f:
        config: dict = json.load(f)
except FileNotFoundError:
    logging.error("The config.json file is missing.")
    raise SystemExit
except json.decoder.JSONDecodeError as je:
    logging.error(f"Bad config.json file. Content is not a valid json:\n{je}")
    raise SystemExit

# Get logging level from config file - default to INFO
logger.setLevel(logging.getLevelName(config.get("debug_level", "INFO")))

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(config['mixpanel_token'], consumer=mp_consumer)

# Get access to Twitter account
auth = tweepy.OAuthHandler(config["consumer_key"], config["consumer_secret"])
auth.set_access_token(config["access_token"], config["access_token_secret"])
# Initialization Twitter API
api = tweepy.API(auth, wait_on_rate_limit=True)
client = tweepy.Client(bearer_token=config["bearer_token"], consumer_key=config["consumer_key"],
                       consumer_secret=config["consumer_secret"], access_token=config["access_token"],
                       access_token_secret=config["access_token_secret"])


def send_profile_to_mixpanel(user):
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


def update_followers_data():
    count = 0
    for follower in Cursor(api.get_followers).items():
        count += 1
        follower_json = json.dumps(follower._json)
        follower_data = json.loads(follower_json)
        print(count, " ", follower_data, '\n')
        send_profile_to_mixpanel(follower_data)
        time.sleep(4)


def send_tweet_to_mixpanel(id):
    status = api.get_status(id)
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
        'createdAt': user['created_at'],
        'followersCount': user['followers_count'],
        'ID': tweet_data['id'],
        'lang': tweet_data['lang'],
        'retweetCount': tweet_data['retweet_count'],
        'text': tweet_data['text'],
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
    mp_client.track(distinct_id, 'TestEventNewTweet', properties)
    logger.info('New tweet: ', tweet_data['text'])


def get_new_tweets():
    while True:
        now = datetime.datetime.now()
        last_five_minutes = now - datetime.timedelta(minutes=5)
        tweets = client.get_users_tweets(config['user_id'], start_time=last_five_minutes)
        tweet = tweets[0]
        if tweet is not None:
            for i in tweet:
                print(i['id'])
                send_tweet_to_mixpanel(i['id'])
        else:
            logger.info('Dosen`t have new tweets last 5 minutes.')
            pass
        time.sleep(300)


if __name__ == "__main__":
    threading.Thread(target=get_new_tweets).start()
    update_followers_data()

