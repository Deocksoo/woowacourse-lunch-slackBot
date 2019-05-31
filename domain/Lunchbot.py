import os
import slack
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import datetime
from pprint import pprint

from domain.RestaurantRepo import restaurant_repo
from domain.TimeStampTable import TimeStampTable
from domain.Restaurant import Restaurant

ts_table_of = dict()

class LunchBot:
    def __init__(self):
        self._slack_token = os.environ['SLACK_API_TOKEN']

    def start(self):
        rtm_client = slack.RTMClient(token=self._slack_token)
        rtm_client.start()

def run_in_new_thread(fn):
    def run(**payload):
        new_thread = Thread(target=fn, kwargs=payload)
        new_thread.start()
    return run

@slack.RTMClient.run_on(event='message')
@run_in_new_thread
def recommend(**payload):
    data = payload['data']
    web_client = payload['web_client']
    channel_id = data['channel']
    
    if data['text'].strip() == '?':
        send_user_guide_to(web_client, channel_id)
        return

    if '밥!' in data['text']:
        send_recommandation_to(web_client, channel_id)
        return
    
    keywords = data['text'].split()
    if '있니?' in keywords:
        keywords = [keyword for keyword in keywords if keyword != '있니?']
        search_results = []
        for keyword in keywords:
            search_results += restaurant_repo.find_all_restaurants_contains(keyword)
        
        send_restaurants_containing_keyword(web_client, channel_id, search_results)
        return

def send_user_guide_to(web_client, channel_id):
    web_client.chat_postMessage(
        channel=channel_id,
        attachments=[
            {'text' : "밥!\t식당 4개 랜덤 추천\ncontains\tsheet에 추가된 식당인지 검색"}
        ]
    )

def send_restaurants_containing_keyword(web_client, channel_id, search_results):
    response_text = ""
    for result in search_results:
        response_text += result + "\n"

    if response_text == "":
        response_text = "그런 식당은 없어요."
    
    web_client.chat_postMessage(
        channel=channel_id,
        attachments=[
            {'text' : response_text}
        ]
    )

def send_recommandation_to(web_client, channel_id):
    restaurants = restaurant_repo.get_random_recommendations_as_many_of(4)
    for restaurant in restaurants:            
        restaurant_type = restaurant.get_type()
        restaurant_color, restaurant_thumb_url = get_restaurant_color_and_thumb_url_by(restaurant_type)

        posted = web_client.chat_postMessage(
            channel=channel_id,
            attachments=[
                {
                    'text': '<' + restaurant.get_naver_place_addr() + '|' + restaurant.get_name() + '>',
                    'fields': [
                        {
                            'title': '대표 메뉴',
                            'value': restaurant.get_popular_menu() + ' ' + str(restaurant.get_price_of_popular_menu()) + '원',
                            'short': True
                        },
                        {
                            'title': '추천 정보',
                            'value': ':thumbsup: '+ str(restaurant.get_good()) + '   :thumbsdown: ' + str(restaurant.get_bad()),
                            'short': True
                        }
                    ],
                    'color': restaurant_color,
                    'thumb_url': restaurant_thumb_url
                }
            ]
        )

        append_ts_in_ts_table(channel_id, posted.data['ts'], restaurant.get_primary_key())

def get_restaurant_color_and_thumb_url_by(restaurant_type):
    restaurant_color = '#000000'
    restaurant_thumb_url = 'http://cdn.wbluke.com/lunch_bot_image/'

    if restaurant_type == '한식':
        restaurant_color = '#218e16'
        restaurant_thumb_url += 'koreanFood.png'
    elif restaurant_type == '일식':
        restaurant_color = '#ea0000'
        restaurant_thumb_url += 'japaneseFood.png'
    elif restaurant_type == '중식':
        restaurant_color = '#401c0e'
        restaurant_thumb_url += 'chineseFood.png'
    elif restaurant_type == '양식':
        restaurant_color = '#eaff08'
        restaurant_thumb_url += 'westernFood.png'
    elif restaurant_type == '분식':
        restaurant_color = '#ff7f00'
        restaurant_thumb_url += 'flourBasedFood.png'
    else:
        restaurant_color = '#5ce7e3'
        restaurant_thumb_url += 'etcFood.png'

    return restaurant_color, restaurant_thumb_url

def append_ts_in_ts_table(channel_id, new_ts, primary_key):
    if not channel_id in ts_table_of:
        new_ts_table = TimeStampTable(size_limit=100)
        ts_table_of[channel_id] = new_ts_table
    
    ts_table = ts_table_of[channel_id]
    ts_table[new_ts] = primary_key

@slack.RTMClient.run_on(event='reaction_added')
def add_reaction_to_repository(**payload):
    print('=========== reaction_added ============')
    print('Added Time : ' + str(datetime.datetime.now()))
    pprint(payload)
    
    data = payload['data']
    channel_id = data['item']['channel']
    ts = data['item']['ts']
    
    if not channel_id in ts_table_of:
        return

    ts_table = ts_table_of[channel_id]
    if not ts in ts_table:
        return
    
    primary_key = ts_table[ts]
    if data['reaction'] == '+1':
        restaurant_repo.increase_thumbsup_of(primary_key)
    elif data['reaction'] == '-1':
        restaurant_repo.increase_thumbsdown_of(primary_key)

@slack.RTMClient.run_on(event='reaction_removed')
def remove_reaction_from_repository(**payload):
    print('=========== reaction_removed ============')
    print('removed Time : ' + str(datetime.datetime.now()))
    pprint(payload)

    data = payload['data']
    channel_id = data['item']['channel']
    ts = data['item']['ts']
 
    if not channel_id in ts_table_of:
        return

    ts_table = ts_table_of[channel_id]
    if not ts in ts_table:
        return
    
    primary_key = ts_table[ts]

    if data['reaction'] == '+1':
        restaurant_repo.decrease_thumbsup_of(primary_key)
    elif data['reaction'] == '-1':
        restaurant_repo.decrease_thumbsdown_of(primary_key)

