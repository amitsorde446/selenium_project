import pytesseract
import cv2
import numpy as np
import re
import speech_recognition as sr
from PIL import Image

def captchaprocessing(pth,binPath=None):
    if binPath is not None:
    	pytesseract.pytesseract.tesseract_cmd = binPath

    image1 = cv2.imread(pth)
    image=image1[460:515,110:240]

    image = cv2.blur(image, (3, 3))
    ret, image = cv2.threshold(image, 90, 255, cv2.THRESH_BINARY);

    image = cv2.dilate(image, np.ones((2, 1), np.uint8))
    image = cv2.erode(image, np.ones((1, 2), np.uint8))

    # cv2.imshow("1", np.array(image))
    cap=pytesseract.image_to_string(image)
    print(f'CAPTCHA : {cap}')
    return cap

def secondcaptchabreaking(pth,binPath=None):
    if binPath is not None:
    	pytesseract.pytesseract.tesseract_cmd = binPath

    image = cv2.imread(pth)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = 255 - cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    # Blur and perform text extraction
    thresh = cv2.GaussianBlur(thresh, (3, 3), 0)
    captcha = pytesseract.image_to_string(thresh, lang='eng', config='--psm 6')
    captcha = re.sub('[\W_]+', '', captcha)
    print(f'CAPTCH : {captcha[:5]}')
    return captcha[:5]

def audiocaptcha(pt):
    r = sr.Recognizer()
    harvard = sr.AudioFile(pt)
    with harvard as source:
        audio = r.record(source)
    cap=r.recognize_google(audio)
    print(f'Captcha : {cap}')
    a=str(cap)
    if " " in a:
        a=a.replace(" ", "")
    if ("for" in a) or ("For" in a):
        a=a.replace("for", "4")
    if ("sex" in a) or ("Sex" in a):
        a=a.replace("sex", "6")

    return a

def bomcaptcha():
    image = Image.open('screenshot.png')

    ## headless
    left = 830
    top = 237
    right = 980
    bottom = 285

    # # local
    # left   = 567
    # top    = 296
    # right  = 715
    # bottom = 345

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap

def sibcaptcha():

    image = Image.open("captcha.png")

    # headless
    left = 390  # increase
    top = 260  # increase
    right = 535  # decrease
    bottom = 294  # decrease

    # # local
    # left = 73  # increase
    # top = 260  # increase
    # right = 215  # decrease
    # bottom = 294  # decrease

    image = image.crop((left, top, right, bottom))  # defines crop points
    image.save("captcha.png")  # saves new cropped image

    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open('captcha.png', 'rb') as captcha_file:
        captcha = api.solve(captcha_file)

    k = captcha.await_result()

    print(k)

    return k

def esfbcaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 847
    top = 257
    right = 950
    bottom = 293

    # # local
    # # left = 537
    # # top = 257
    # # right = 628
    # # bottom = 293

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap

def tmbcaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 1095
    top = 359
    right = 1220
    bottom = 384

    # # local
    # # left = 784
    # # top = 359
    # # right = 909
    # # bottom = 384

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap

def csbcaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 1202
    top = 341
    right = 1289
    bottom = 366

    # # local
    # # left = 883
    # # top = 341
    # # right = 971
    # # bottom = 366

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    image = cv2.imread("captcha.png")
    # pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'
    ret, image = cv2.threshold(image, 90, 255, cv2.THRESH_BINARY);
    cap=pytesseract.image_to_string(image)
    print(f'CAPTCHA : {cap}')
    return cap

def fbcaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 1729
    top = 283
    right = 1835
    bottom = 316

    # local
    # left = 1120
    # top = 280
    # right = 1213
    # bottom = 322

    image = image.crop((left, top, right, bottom)) 
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap

def fccaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 476
    top = 244
    right = 600
    bottom = 271

    # local
    # left = 170
    # top = 245
    # right = 285
    # bottom = 270

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap

def idbicaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 476
    top = 244
    right = 600
    bottom = 271

    # local
    # left = 170
    # top = 245
    # right = 285
    # bottom = 270

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap

def kbcaptcha():

    image = Image.open('screenshot.png')

    # # headless
    left = 189
    top = 320
    right = 311
    bottom = 357

    # # local
    # # left = 166
    # # top = 320
    # # right = 289
    # # bottom = 357

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap.upper()}')
    return cap.upper()

def kvcaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 966
    top = 240
    right = 1082
    bottom = 268

    # local
    # left = 648
    # top = 240
    # right = 764
    # bottom = 268

    image = image.crop((left, top, right, bottom))
    # pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'
    image.save("captcha.png")
    image = cv2.imread("captcha.png")
    cap=pytesseract.image_to_string(image)
    print(f'CAPTCHA : {cap}')
    return cap

def sccaptcha():

    image = Image.open('screenshot.png')

    # headless
    left = 163
    top = 545
    right = 298
    bottom = 597

    # local
    # # left = 163
    # # top = 313
    # # right = 298
    # # bottom = 365

    image = image.crop((left, top, right, bottom))
    image.save("captcha.png")
    from azcaptchaapi import AZCaptchaApi
    api = AZCaptchaApi('k2b7phlwtfrmbzxnwjjqr96mv4dqgnfg')
    with open("captcha.png", 'rb') as captcha_file:
        captcha = api.solve(captcha_file)
    cap = captcha.await_result()
    print(f'CAPTCHA : {cap}')
    return cap
