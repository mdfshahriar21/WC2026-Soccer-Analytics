#block1 import necessary libraries
import os
import requests
from dotenv import load_dotenv
import json

#block2 load environment variables
load_dotenv() 
api_key=os.getenv('API_FOOTBALL_KEY')

#block3 function to fetch data from API
def get_leagues():
    base_url = "https://v3.football.api-sports.io/standings?league=1&season=2022"
    headers = {
        'x-apisports-key': api_key,
    }
    response = requests.get(base_url, headers=headers)
    return response.json()

response = get_leagues()
print(json.dumps(response, indent=4))