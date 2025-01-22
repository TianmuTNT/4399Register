# -*- coding: utf-8 -*-
import itertools
import sys
import threading

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from requests import get, post
from random import sample, choice
from ddddocr import DdddOcr
from datetime import datetime
from time import time, sleep
from string import ascii_letters, digits, ascii_lowercase

import os
import json
import logging

from requests.exceptions import ProxyError

strings = ascii_letters + digits
captcha_strings = ascii_lowercase + digits


kafka_address = os.getenv("KAFKA_ADDRESS", "localhost:9092")
mode = "server"  # server: 由pineapple-api控制启停, local: 直接开始刷号,直到按下Ctrl+C

logging.basicConfig(level=logging.INFO)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
}

ocr = DdddOcr(use_gpu=True, show_ad=False, import_onnx_path="4399ocr/4399ocr.onnx",
              charsets_path="4399ocr/4399ocr.json")

if not os.path.exists("config/sfz.txt"):
    logging.error("🍍❌ 请把sfz.txt挂载到/app/sfz.txt, 无论你在用Pinecker pompose或者Pinernetes")
    sys.exit(1)

with open("config/sfz.txt", 'r', encoding='utf-8') as f:
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

    proxies = {'https': os.getenv("PROXY", 'http://127.0.0.1:8089')}

    logging.info(f"🍍 菠萝证 {sfz}")

    session_id = 'captchaReq' + randstr(captcha_strings, 19)
    captcha_response = get(
        f'https://ptlogin.4399.com/ptlogin/captcha.do?captchaId={session_id}',
        headers=headers,
        proxies=proxies,
        verify=False
    ).content
    captcha = ocr.classification(captcha_response)
    logging.info(f"🍍 菠萝码识别 {captcha}")

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
        'sessionId': session_id,
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
        return  # Kafka disabled
    producer.send(topic='pineapple-reg', value=result_list, key="pineapple-reg")
    producer.flush()


def bulk_register(count: int, producer: KafkaProducer, account_file):
    cache = []
    r = range(count)
    if count == -1:
        r = itertools.count(0, 1)
    for i in r:
        try:
            start = time()
            usr = "S" + randstr(strings, 3) + "K" + randstr(strings, 3) + "Y" + randstr(strings, 3)
            pwd = randstr(strings, 12)
            logging.info(f"🍍 {time_is()} [{i}] 尝试注册 {usr}:{pwd}")
            result = register_4399(usr, pwd)
            # write to file
            if account_file is not None:
                account_file.write(f'{result["username"]}:{result["password"]}\n')
            # Push to kafka
            cache.append(result)
            if len(cache) > 100:
                # 大概每50s推送一次
                push_kafka(cache, producer)
                cache = []  # Wipe cache
            logging.info(f"{time_is()} 耗时:{time_how(start)}s 结果:{result}")
        except KeyboardInterrupt:
            break  # Exit
        except ProxyError as e:
            logging.error("🍍 主播记得设置代理池")
            break
        except Exception as e:
            logging.error("Unexpected error: %s", e, exc_info=True)
    if len(cache) > 0:
        push_kafka(cache, producer)
    heartbeat(False, False, producer)

def heartbeat(planting: bool, already_working: bool, producer: KafkaProducer):
    data = {
        "planting": planting,
        "alreadyWorking": already_working,
    }
    logging.info("🍍 Sending heartbeat!")
    producer.send("pineapple-heartbeat", value=data, key="pineapple-heartbeat")
    producer.flush()


def main():
    logging.info("🍍 菠萝注册机 按Ctrl+C结束程序")
    logging.info(f"🍍 工作模式: {'刷号机' if mode == 'local' else '被控'}")
    producer = None
    try:
        logging.info(f"🍍 正在尝试连接到Kafka ({kafka_address})")
        # Security warning: DO NOT open the kafka port, that will leak account info
        producer = KafkaProducer(
            bootstrap_servers=kafka_address,
            key_serializer=lambda k: k.encode("utf-8"),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logging.info("🍍 成功连接到Kafka broker")
        # todo 这里有一个问题, 如果开两个菠萝机会导致服务端的状态被重置
        heartbeat(False, False, producer)
    except KafkaError as e:
        logging.warning("🍍⚠️ 无法连接到Kafka, 消息将无法推送到服务端, 会导致浪费时间")
        logging.warning("🍍️⚠️ 请开启Kafka, 并确保脚本中的Kafka地址正确, 不需要服务端开启")
        try:
            logging.warning("🍍⚠️  确保你有足够的时间反悔, 等两秒(可以通过Ctrl+C跳过)")
            sleep(2)
        except KeyboardInterrupt:
            pass  # do nothing
    sleep(2)

    if mode == "local":
        account_file = open('accounts.txt', 'a')
        bulk_register(-1, producer, account_file)
        account_file.close()
    elif mode == "server":
        consumer = KafkaConsumer('pineapple-commands',
                                 group_id='pineapple-group',
                                 bootstrap_servers=kafka_address,
                                 key_deserializer=lambda k: k.decode("utf-8"),
                                 value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                                 )
        thread = None
        for message in consumer:
            cmd = message.value
            if cmd["cmd"] == "start":
                if (thread is not None) and (thread.is_alive()):
                    heartbeat(planting=True, already_working=True, producer=producer)
                    logging.warning("🍍❌ 已经在生产菠萝了, 暂时不能开新的生产线")
                    continue
                logging.info("🍍✅ 开始生产菠萝")
                thread = threading.Thread(target=lambda count: bulk_register(count, producer, None), args=(cmd["count"],))
                thread.start()
                heartbeat(planting=True, already_working=False, producer=producer)
    else:
        logging.error("🍍❌ 配置错误! 未知的工作模式 (local|server)")

    producer.close()


if __name__ == "__main__":
    main()
