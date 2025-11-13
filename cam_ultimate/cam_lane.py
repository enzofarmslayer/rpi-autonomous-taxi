import cv2
import numpy as np
import utilities


def getLaneCurve(img):

    imgCopy = img.copy()
    #Steg 1
    imgThres = utilities.thresholding(img)

    #Steg 2
    h, w, c = img.shape
    points = utilities.valTrackbars()
     
    imgWarp = utilities.warpImg(imgThres, points, w, h)
    imgWarpPoints = utilities.drawPoints(imgCopy, points)


    #3
    utilities.getHistogram(imgWarp)
       # basePoint,imgHist = utilities.getHistogram(imgWarp,display=True, minVal = 0.5, region= 4)
    midPoint,imgHist = utilities.getHistogram(imgWarp,display=True, minVal = 0.5, region= 4)
    basePoint,imgHist = utilities.getHistogram(imgWarp,display=True, minVal = 0.9, region= 1)
    print(basePoint - midPoint)



    cv2.imshow('Thres', imgThres)
    cv2.imshow('Warp', imgWarp)
    cv2.imshow('Warp points', imgWarpPoints)
    cv2.imshow('Histogram', imgHist)
    return None


if __name__ == '__main__':
    cap = cv2.VideoCapture(r"c:\Users\gitar\Desktop\TSEA29\code\cam_ultimate\vid1.mp4")
    initialTrackbarValues = [102, 80, 20, 214]
    utilities.initializeTrackbars(initialTrackbarValues)
    frameCounter = 0
    while True:
        frameCounter += 1
        if cap.get(cv2.CAP_PROP_FRAME_COUNT) ==frameCounter:
            cap.set(cv2.CAP_PROP_POS_FRAMES,0)
            frameCounter=0

        success, img = cap.read() # GET THE IMAGE
        img = cv2.resize(img,(480,240)) # RESIZE
        getLaneCurve(img)
        cv2.imshow('Vid', img)

        cv2.waitKey(1)