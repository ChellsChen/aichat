#import json
import logging
import requests
from bs4 import BeautifulSoup

from django.conf import settings



def browse_web(request, url):
    """浏览网页"""
    if not url:
        return False, 'url 必填'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.get_text()
    return True, content

def get_weather(request, location):
    return True, '{} 的天气是晴天，10 ~ 20 度'.format(location)

def search_google(request, query):
    payload = {
        'q': query,
        'cx': settings.GOOGLE_SEARCH_API_ENGINE_ID,
        'hl': 'zh-CN',         # 界面语言     
        'safe': 'active',  
        #'cr': 'countryCN',      # 搜索结果限制为特定国家/地区
        #'gl': 'cn',             # 最终用户的地理位置
        'filter': '1',
        'key': settings.GOOGLE_SEARCH_API_KEY
    }

    url = settings.GOOGLE_SEARCH_API_SERVER
    resp = requests.get(url, params=payload)
    if resp.status_code != 200:
        logging.error('request google search failed: {}'.format(resp.text))
        return False, 'request google search failed'
    result = resp.json()
    items = result.get('items')
    res = []
    for item in items:
        res.append({
            'title': item.get('title'),
            'link': item.get('link'),
            'snippet': item.get('snippet')
        })
    return True, res





