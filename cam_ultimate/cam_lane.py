import cv2
import numpy as np
import utilities


def getLaneCurve(img):
    imgThres = utilities.thresholding(img)
    cv2.imshow('Thres', imgThres)

    return None


if __name__ == '__main__':
    cap = cv2.VideoCapture(r"c:\Users\gitar\Desktop\TSEA29\code\cam_ultimate\vid1.mp4")
    while True:
        success, img = cap.read() # GET THE IMAGE
        img = cv2.resize(img,(480,240)) # RESIZE
        getLaneCurve(img)
        cv2.imshow('Vid', img)

        cv2.waitKey(1)