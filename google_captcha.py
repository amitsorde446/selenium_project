import os
import io
from google.cloud import vision
import cv2
import numpy as np
import re
from PIL import Image

def captchabreak1():

    FILE_NAME = "captcha.png"
    FOLDER_PATH = os.getcwd()
    credential_path = r"vision_api_token.json"
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path
    client = vision.ImageAnnotatorClient()

    with io.open(os.path.join(FOLDER_PATH, FILE_NAME), 'rb') as image_file:
        content = image_file.read()

    image = vision.types.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    for text in texts:
        z = ('"{}"'.format(text.description))
    try:
        h = str(z).split('"')
        k = h[1]
        print(f"CAPTCHA : {k}")
    except:
        k = "AAAAA"
        print(f"CAPTCHA : {k}")
    return k

def captchabreak():

    image = Image.open('screenshot.png')
    # local
    # left = 100
    # top = 340
    # right = 320
    # bottom = 400
    # headless
    left = 300
    top = 340
    right = 600
    bottom = 400
    image = image.crop((left, top, right, bottom)) 
    image.save("captcha.png")

    FILE_NAME = "captcha.png"
    FOLDER_PATH = os.getcwd()
    credential_path = r"vision_api_token.json"
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credential_path
    client = vision.ImageAnnotatorClient()

    with io.open(os.path.join(FOLDER_PATH, FILE_NAME), 'rb') as image_file:
        content = image_file.read()

    image = vision.types.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    for text in texts:
        z = ('"{}"'.format(text.description))
    h = str(z).split('"')
    k = h[1]
    print(f"CAPTCHA : {k}")
    return k