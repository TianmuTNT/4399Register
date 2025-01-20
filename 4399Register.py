# -*- coding: utf-8 -*-
from kafka import KafkaProducer
from kafka.errors import KafkaError
from requests import get, post
from random import sample, choice
from ddddocr import DdddOcr
from datetime import datetime
from time import time, sleep
from string import ascii_letters, digits, ascii_lowercase

import json
import logging

strings = ascii_letters + digits
captcha_strings = ascii_lowercase + digits

kafka_address = 'localhost:9092'

logging.basicConfig(level=logging.INFO)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
}

ocr = DdddOcr(use_gpu=True, show_ad=False, import_onnx_path="4399ocr/4399ocr.onnx",
              charsets_path="4399ocr/4399ocr.json")

with open("sfz.txt", 'r', encoding='utf-8') as f:
    lines = f.readlines()
    f.close()


def randstr(chars, length):
    return ''.join(sample(chars, length))


def time_is():
    return datetime.now().strftime("[%H:%M:%S]")


def time_how(start):
    return f"{(time() - start):.2f}"


def register_4399(usr, pwd):
    start = time()
    sfz = choice(lines).strip()
    sfz_split = sfz.split(':')

    proxies = {'https': 'http://127.0.0.1:8089'}

    print(f"身份证 {sfz}", end=" | ")

    sessionId = 'captchaReq' + randstr(captcha_strings, 19)
    captcha_response = get(
        f'https://ptlogin.4399.com/ptlogin/captcha.do?captchaId={sessionId}',
        headers=headers,
        proxies=proxies,
        verify=False
    ).content
    captcha = ocr.classification(captcha_response)
    print(f"验证码识别 {captcha}", end=" | ")

    data = {
        'postLoginHandler': 'default',
        'displayMode': 'popup',
        'appId': 'www_home',
        'gameId': '',
        'cid': '',
        'externalLogin': 'qq',
        'aid': '',
        'ref': '',
        'css': '',
        'redirectUrl': '',
        'regMode': 'reg_normal',
        'sessionId': sessionId,
        'regIdcard': 'true',
        'noEmail': '',
        'crossDomainIFrame': '',
        'crossDomainUrl': '',
        'mainDivId': 'popup_reg_div',
        'showRegInfo': 'true',
        'includeFcmInfo': 'false',
        'expandFcmInput': 'true',
        'fcmFakeValidate': 'false',
        'realnameValidate': 'true',
        'username': usr,
        'password': pwd,
        'passwordveri': pwd,
        'email': '',
        'inputCaptcha': captcha,
        'reg_eula_agree': 'on',
        'realname': sfz_split[0],
        'idcard': sfz_split[1]
    }

    response = post(
        'https://ptlogin.4399.com/ptlogin/register.do',
        data=data,
        proxies=proxies,
        headers=headers,
        verify=False
    ).text
    
    result = {
        "success": False,
        "msg": "未知的失败",
        "username": None,
        "password": None
    }

    if '注册成功' in response:
        result["success"] = True
        result["msg"] = '注册成功'
        result['username'] = usr
        result['password'] = pwd
        # not recommended
        # with open('accounts.txt', 'a') as f:
        #     f.write(f'{usr}:{pwd}\n')
        #     f.close()
    elif '身份证实名账号数量超过限制' in response:
        result["msg"] = '身份证实名账号数量超过限制'
    elif '身份证实名过于频繁' in response:
        result["msg"] = '身份证实名过于频繁'
    elif '该姓名身份证提交验证过于频繁' in response:
        result["msg"] = '该姓名身份证提交验证过于频繁'
    elif '用户名已被注册' in response:
        result["msg"] = '用户名已被注册'
    else:
        result["msg"] = "未知的失败"

    if '验证码错误' in response:
        logging.info(f"验证码错误 | 耗时 {time_how(start)}s")
        result = register_4399(usr, pwd)
    else:
        logging.info(f"{result['msg']} | 耗时 {time_how(start)}s")

    return result

def push_kafka(result_list: list, producer: KafkaProducer):
    if producer is None:
        return # Kafka disabled
    producer.send(topic='pineapple-reg', value=result_list,  key="pineapple-reg")
    producer.flush()

def main():
    logging.info("2s后开始注册 按Ctrl+C结束程序")
    account_file = open('accounts.txt', 'a')
    producer = None
    try:
        logging.info(f"正在尝试连接到Kafka ({kafka_address})")
        # Security warning: DO NOT open the kafka port, that will leak account info
        producer = KafkaProducer(
            bootstrap_servers=kafka_address,
            key_serializer=lambda k: k.encode("utf-8"),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    except KafkaError as e:
        logging.warning("无法连接到Kafka, 消息将无法推送到kafka")
        try:
            logging.warning("确保你有足够的时间反悔, 等两秒(可以通过Ctrl+C跳过)")
            sleep(2)
        except KeyboardInterrupt:
            pass # do nothing
    sleep(2)
    cache = []
    while True:
        try:
            start = time()
            usr = "S" + randstr(strings, 3) + "K" + randstr(strings, 3) + "Y" + randstr(strings, 3)
            pwd = randstr(strings, 12)
            logging.info(f"\n{time_is()} 尝试注册 {usr}:{pwd}")
            result = register_4399(usr, pwd)
            # write to file
            account_file.write(f'{result["username"]}:{result["password"]}\n')
            # Push to kafka
            cache.append(result)
            if len(cache) > 100:
                # 大概每50s推送一次
                push_kafka(cache, producer)
                cache = [] # Wipe cache
            logging.info(f"{time_is()} 耗时:{time_how(start)}s 结果:{result}")
        except KeyboardInterrupt:
            break # Exit
        except Exception as e:
            logging.error("Unexpected error: %s", e, exc_info=True)
    account_file.close()

if __name__ == "__main__":
    main()
