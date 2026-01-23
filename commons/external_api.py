import requests


HOST = 'https://coco.j1.sale'

# HOST = 'http://localhost:8000'


def push_task_data(data):
    url = f'{HOST}/robot_client/push_task_data'
    # print(url)
    resp = requests.post(url, json=data)
    print(resp.content)
    return resp.json()


def push_sys_info(data):
    url = f'{HOST}/robot_client/push_sys_info'
    # print(url)
    resp = requests.post(url, json=data)
    print(resp.content)
    return resp.json()