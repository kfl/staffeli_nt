import requests

def download(url):
    return requests.get(url).content
