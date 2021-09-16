import numpy as np
import cv2

import signal
import sys
from math import log

import random

from pyfirmata import Arduino, util
from time import sleep
import time

from netifaces import ifaddresses

board = Arduino("/dev/ttyAMA0")

it = util.Iterator(board)  
it.start()

lfo = board.get_pin("d:9:p")
pitch = board.get_pin("d:5:p")
cutoff = board.get_pin("d:6:p")

temperature_pin = board.get_pin("a:0:i")
humidity_pin = board.get_pin("a:1:i")

THRESHOLD_CORRECTION = 0.6

HEIGHT = 600
WIDTH = 1024

def get_my_ip():
    try:
        wlan0 = ifaddresses('wlan0')
        if 2 in wlan0:
            return wlan0[2][0]['addr']
        else:
            return None
    except ValueError:
        return None


temp_avg = None
N = 0.1

def read_temp(pin):
    global temp_avg
    R0 = 5.1e3
    B = 3435
    R25 = 10e3
    T_BASE = 25
    r2 = R0 * (1/pin.read() - 1.)
    k = log(r2 / R25) / B + 1.0 / (273.15 + T_BASE)

    if temp_avg == None:
        temp_avg = 1.0 / k - 273.15
    else:
        temp_avg = temp_avg * (1. - N) + (1.0 / k - 273.15) * N
    return temp_avg

TARGET_TEMP = 60
TARGET_HUMIDITY = 70

def read_humidity(pin):
    raw = pin.read() * 5.0
    humidity = ((raw - 0.6) / (2.7 - 0.6)) * (90 - 20) + 20
    return humidity

def add_info(frame, info):
    font = cv2.FONT_HERSHEY_SIMPLEX

    my_ip = get_my_ip()
    if my_ip is not None:
        cv2.putText(
            frame, "ip: %s" % my_ip,
            (10,15),
            font, .5, (0,0,0), 1, cv2.LINE_AA
        )

    cv2.putText(
        frame, "temperature: %.01f C" % info["temperature"],
        (80,60),
        font, 2., (0,0,0), 4, cv2.LINE_AA
    )

    cv2.putText(
        frame, "humidity: %.01f%%" % info["humidity"],
        (80,120),
        font, 2., (0,0,0), 4, cv2.LINE_AA
    )

    return frame

profile_t = time.time()
def profile(message):
    global profile_t
    print("profile", message, time.time() - profile_t)
    profile_t = time.time()

erosion_size = 10
erosion_element = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE,
    (2 * erosion_size + 1, 2 * erosion_size + 1),
    (erosion_size, erosion_size)
)

def calculate_mask(src):
    src_blur = cv2.blur(src, (5,5))
    src_hsv = cv2.cvtColor(src_blur, cv2.COLOR_BGR2HSV)
    src_h, src_s, src_v = cv2.split(src_hsv)

    src_norm = cv2.addWeighted(
        src_s, 1.0,
        255 - src_v, 0.8,
        0
    )

    th_min = np.percentile(src_norm, 10)
    th_max = np.percentile(src_norm, 90)

    # what way of correction is right...
    # threshold = th_max * THRESHOLD_CORRECTION + th_min * (1. - THRESHOLD_CORRECTION)
    threshold = (th_max + th_min) * THRESHOLD_CORRECTION

    ret, thresh = cv2.threshold(src_norm, threshold, 255, cv2.THRESH_TOZERO)
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) == 0:
        return None, None

    max_contour = max(contours, key=lambda x: cv2.contourArea(x))

    dimensions = src.shape

    ooi_mask = cv2.drawContours(
        np.zeros(dimensions, np.uint8),
        [max_contour], -1, (255, 255, 255), -1
    )

    # ooi_mask = cv2.dilate(ooi_mask, erosion_element)
    bg_mask = cv2.bitwise_not(ooi_mask)

    return {"ooi": ooi_mask, "bg": bg_mask}, max_contour

def calculate_info(src, mask):
    if mask is not None:
        bg_mean = cv2.mean(src, cv2.cvtColor(mask["bg"], cv2.COLOR_BGR2GRAY))
        object_mean = cv2.mean(src, cv2.cvtColor(mask["ooi"], cv2.COLOR_BGR2GRAY))

        color = (
            object_mean[2]/bg_mean[2] if bg_mean[2] > 0 else 0,
            object_mean[1]/bg_mean[1] if bg_mean[1] > 0 else 0,
            object_mean[0]/bg_mean[0] if bg_mean[0] > 0 else 0
        )

        print("red: %.02f, green: %.02f, blue: %.02f" % color, flush=True)

        return color
    else:
        return None


def process_image(src, mask, contour):
    profile("start process")

    if mask == None:
        return src

    # object
    '''
    ooi = cv2.subtract(mask["ooi"], src)
    ooi = cv2.subtract(mask["ooi"], ooi)

    # background
    bg = cv2.subtract(mask["bg"], src)
    bg = cv2.subtract(mask["bg"], bg)
    bg_blur = cv2.blur(bg, (5,5))

    out_img = cv2.addWeighted(
        ooi, 1.0,
        bg_blur, 0.7,
        0
    )
    '''
    out_img = src

    # profile("addWeighted")

    if contour is not None:
        out_img = cv2.drawContours(
            out_img,
            [contour], -1, (20, 50, 50), 1
        )

    return out_img

# cap = cv2.VideoCapture(0)

def do_exit():
    if cap:
        cap.release()
    
    cv2.destroyAllWindows()
    sys.exit(0)

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    do_exit()

signal.signal(signal.SIGINT, signal_handler)

def camera_thread(cap):
    print("Mayar started")

    no_frame_counter = 0
    MAX_FRAME_SKIPPED = 100
    frame_counter = 0

    led_state = 0

    mask = None
    contour = None

    cutoff_counter = 0
    lfo_counter = 0
    pitch_counter = 0

    while(True):
        # Capture frame-by-frame
        ret, frame = cap.read()
        frame_counter += 1

        if not ret:
            no_frame_counter += 1
            if no_frame_counter > MAX_FRAME_SKIPPED:
                print("no more frames, exit")
                do_exit()
            
            cv2.waitKey(1)
            continue
        else:
            no_frame_counter = 0

        # Our operations on the frame come here
        # if frame_counter % 4 == 0:
        # out_img = process_image(frame, frame_counter % 2 == 0)
        #else:

        info = {}

        
        info["humidity"] = read_humidity(humidity_pin)
        info["temperature"] = read_temp(temperature_pin)

        temp_diff = abs(info["temperature"] - TARGET_TEMP)
        print("temp:", info["temperature"], "temp diff:", temp_diff)

        hum_diff = abs(info["humidity"] - TARGET_HUMIDITY)
        print("hum:", info["humidity"], "hum diff:", hum_diff)

        cutoff_counter += 1
        pitch_counter += 1
        lfo_counter += 1

        if cutoff_counter == 1:
            cutoff_counter = 0
            value = random.random()
            print("write cutoff", value)
            cutoff.write(value)

        if pitch_counter == 3:
            pitch_counter = 0
            value = random.random()
            print("write pitch", value)
            pitch.write(value)

        if lfo_counter == 5:
            lfo_counter = 0
            value = random.random()
            print("write lfo", value)
            lfo.write(value)

        if led_state == 1:
            led_state = 0
        else:
            led_state = 1

        board.digital[13].write(led_state)

        out_img = frame[85:-40, 108:-108]

        if frame_counter % 8 == 0:
            mask, contour = calculate_mask(out_img)
            calculate_info(out_img, mask)

        out_img = process_image(out_img, mask, contour)

        out_img = cv2.resize(out_img, (WIDTH, HEIGHT), cv2.INTER_NEAREST)

        # profile("resizing")

        out_img = add_info(out_img, info)

        # Display the resulting frame
        cv2.imshow('frame', out_img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            pass

def load_image(image_name):
    print("load image", image_name)
    img = cv2.imread(image_name)
    # cv2.imshow(image_name, img)
    out_img = process_image(img)
    cv2.imshow(image_name, out_img)
    cv2.waitKey(0)

if len(sys.argv) > 1:
    load_image(sys.argv[1])
else:
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    camera_thread(cap)

do_exit()
