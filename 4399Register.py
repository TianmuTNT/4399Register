# -*- coding: utf-8 -*-
from requests import get, post
from random import sample, choice
from ddddocr import DdddOcr
from datetime import datetime
from time import time
from string import ascii_letters, digits, ascii_lowercase

strings = ascii_letters + digits
captcha_strings = ascii_lowercase + digits

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

    if '注册成功' in response:
        result = '注册成功'
        with open('accounts.txt', 'a') as f:
            f.write(f'{usr}:{pwd}\n')
            f.close()
    elif '身份证实名账号数量超过限制' in response:
        result = '身份证实名账号数量超过限制'
    elif '身份证实名过于频繁' in response:
        result = '身份证实名过于频繁'
    elif '该姓名身份证提交验证过于频繁' in response:
        result = '该姓名身份证提交验证过于频繁'
    elif '用户名已被注册' in response:
        result = '用户名已被注册'
    else:
        result = "未知的失败"

    if '验证码错误' in response:
        print(f"验证码错误 | 耗时 {time_how(start)}s")
        result = register_4399(usr, pwd)
    else:
        print(f"{result} | 耗时 {time_how(start)}s")

    return result


if __name__ == "__main__":
    while True:
        try:
            start = time()
            usr = "S" + randstr(strings, 3) + "K" + randstr(strings, 3) + "Y" + randstr(strings, 3)
            pwd = randstr(strings, 12)
            print(f"\n{time_is()} 尝试注册 {usr}:{pwd}")
            result = register_4399(usr, pwd)
            print(f"{time_is()} 耗时:{time_how(start)}s 结果:{result}")
        except Exception as e:
            print(e)
