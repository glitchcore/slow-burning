import numpy as np
import cv2

import signal
import sys

THRESHOLD_CORRECTION = 0.85

HEIGHT = 576
WIDTH = 720

def process_image(src, debug=True, update_contour=True):
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
        return src
    
    max_contour = max(contours, key=lambda x: cv2.contourArea(x))

    dimensions = src.shape

    ooi_mask = cv2.drawContours(
        np.zeros(dimensions, np.uint8),
        [max_contour], -1, (255, 255, 255), -1
    )

    bg_mask = cv2.bitwise_not(ooi_mask)

    # object
    ooi = cv2.subtract(ooi_mask, src)
    ooi = cv2.subtract(ooi_mask, ooi)
    object_mean = cv2.mean(src, cv2.cvtColor(ooi_mask, cv2.COLOR_BGR2GRAY))

    # background
    bg = cv2.subtract(bg_mask, src)
    bg = cv2.subtract(bg_mask, bg)
    bg_mean = cv2.mean(src, cv2.cvtColor(bg_mask, cv2.COLOR_BGR2GRAY))

    color = (
        object_mean[2]/bg_mean[2] if bg_mean[2] > 0 else 0,
        object_mean[1]/bg_mean[1] if bg_mean[1] > 0 else 0,
        object_mean[0]/bg_mean[0] if bg_mean[0] > 0 else 0
    )

    out_img = cv2.addWeighted(
        ooi, 1.5,
        src_blur, 0.7,
        0
    )

    out_img = cv2.drawContours(
        out_img,
        [max_contour], -1, (20, 50, 50), 1
    )

    out_img = cv2.resize(out_img, (WIDTH, HEIGHT))

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(
        out_img, "red: %.02f" % color[0],
        (28,20),
        font, .5, (20,20,230), 1, cv2.LINE_AA
    )
    cv2.putText(
        out_img, "green: %.02f" % color[1],
        (10,40),
        font, .5, (100,250,100), 1, cv2.LINE_AA
    )
    cv2.putText(
        out_img, "blue: %.02f" % color[2],
        (22,60),
        font, .5, (230,20,20), 1, cv2.LINE_AA
    )

    if(debug):
        print("red: %.02f, green: %.02f, blue: %.02f" % color, flush=True)
        # print(th_min, th_max, threshold)
        # print("object:", object_mean)
        # print("bg:", bg_mean)
        # cv2.imshow("object", ooi)
        # cv2.imshow("background", bg)
        # cv2.imshow("thresh", thresh)

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
        out_img = process_image(frame, frame_counter % 2 == 0)
        #else:
        #    out_img = cv2.resize(frame, (WIDTH, HEIGHT))

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
    camera_thread(cap)

do_exit()
