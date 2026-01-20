import requests


HOST = 'https://coco.j1.sale'

HOST = 'http://localhost:8001'


def push_task_data(data):
    url = f'{HOST}/robot_client/push_task_data'
    data = requests.post(url, json=data).json()
    print(data)