import requests


HOST = 'https://coco.j1.sale'

# HOST = 'http://localhost:8000'


def push_task_data(data):
    url = f'{HOST}/robot_client/push_task_data'
    # print(url)
    resp = requests.post(url, json=data)
    # print(resp.content)
    return resp.json()


def push_sys_info(data):
    url = f'{HOST}/robot_client/push_sys_info'
    # print(url)
    resp = requests.post(url, json=data)
    # print(resp.content)
    return resp.json()


def get_skills(user_key=None, skill_name=None):
    skill_name_arg = f'&skill_name={skill_name}' if skill_name else ''
    url = f'{HOST}/daiban/client/skills?user_key={user_key}{skill_name_arg}'

    resp = requests.get(url)
    return resp.json().get('data')