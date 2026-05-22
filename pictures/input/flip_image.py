import cv2
import numpy

img = cv2.imread("hilti_2.png")

img = cv2.flip(img,0)

cv2.imwrite("hilti_flipped.png", img)