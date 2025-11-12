from picamera2 import Picamera2
import cv2
import numpy as np
import time
from collections import deque

# -----Global variables and buffers------
left_x_history = deque(maxlen=5)
right_x_history = deque(maxlen = 5)
offset_history = deque(maxlen = 10)
smoothed_offset = None
stable_left_x = None
stable_right_x = None
ALPHA = 0.25 # säng mer stabil, höj mer responsiv

COLOR_DISPLAY = False # Ändra mellan gråvit bild och färg

# ----------Camera Initialization --------
picam2 = Picamera2() # startar kameran

config = picam2.create_preview_configuration(main={"format": "RGB888", "size": (640,480)})
picam2.configure(config)
picam2.start() 	

# -------- Function Definitions ---------
def capture_frame():
	""" 
	Captures frame from camera and converts to BGR format
	"""
	frame = picam2.capture_array()								
	frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
	return frame

def preprocess_frame(frame):
	"""
	Converts frame to greyscale, applies CLAHE and GaussianBlur
	"""
	grayFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
	clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8, 8))
	grayFrame = clahe.apply(grayFrame)
	
	grayFrame = cv2.GaussianBlur(grayFrame, (5,5), 0)
	return grayFrame 						

def detect_lane(grayFrame, colorFrame):
	height, width = grayFrame.shape
	
	roi_gray = grayFrame[int(height*0.1):, :] 			# Kolla bara nedersta X% av skärmen, justera vid behov
	roi_color = colorFrame[int(height*0.1):, :]				# Med färg
	
	hsv = cv2.cvtColor(roi_color, cv2.COLOR_BGR2HSV)
	H, S, V = cv2.split(hsv)
	
	V_LIMIT = int(np.percentile(V, 5))
	V_LIMIT =min(V_LIMIT, 40)
	S_LIMIT = 15
	
	black_limit = int(np.percentile(roi_gray, 5)) 		# justera beroende på pixlarnas värde vid svart och vitt
	black_limit = max(10, min(90, black_limit))
	
	mask_gray = cv2.inRange(roi_gray, 0, black_limit)       # Hitta linjer genom mörka färger
	mask_hsv = cv2.inRange(hsv, (0, S_LIMIT, 0),(179, 255, V_LIMIT))		# Hitta linjer genom HSV för att skippa skuggor
	
	mask = cv2.bitwise_and(mask_hsv, mask_gray)
	
	kernel = np.ones((5, 5), np.uint8)
	mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations = 1) 
	
	left_half = mask[:, :width//2]
	right_half = mask[:,width // 2:]
	
	left_contours, _ = cv2.findContours(left_half, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	right_contours, _ = cv2.findContours(right_half, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	
	if len(left_contours) == 0 or len(right_contours) == 0:
		return None, None, width, roi_color, roi_gray, mask
	
	left_c = max(left_contours, key=cv2.contourArea)
	right_c = max(right_contours, key=cv2.contourArea)
	
	left_x = int(np.mean(left_c[:, :, 0]))
	right_x = int(np.mean(right_c[:, :, 0]) + width//2)	

	return left_x, right_x, width, roi_color, roi_gray, mask

def compute_offset(left_x, right_x, width):
	if left_x is None or right_x is None:
		return None
	
	middle = (left_x + right_x) // 2 				# Ta fram mittenpunkt
	center = width // 2
	offset = middle - center
		
	if offset is not None:
		if len(offset_history) == 0:
			offset_history.append(offset)
			smoothed_offset = offset
		else:
			mean_val = np.mean(offset_history)
			if abs(offset - mean_val) > 10: # ändra om behövs
				offset_history.append(offset)
				smoothed_offset = np.mean(offset_history)
			else: 
				smoothed_offset = np.mean(offset_history)
	else:
		smoothed_offset = None
	return smoothed_offset
	
def send_offset(offset, last=[time.time()]):
	now = time.time()
	if now - last[0] >= 1:
		print(f"Offset: {offset}")
		last[0] = now

def compute_x(left_x, right_x):
	global stable_left_x, stable_right_x
	if left_x is not None:
		if len(left_x_history) == 0:
			left_x_history.append(left_x)
			stable_left_x = int(left_x)
		else:
			mean_left = np.mean(left_x_history) 
			if abs(left_x - mean_left) > 10:
				left_x_history.append(left_x)
				stable_left_x = int(left_x)
		
	if right_x is not None:
		if len(right_x_history) == 0:
			right_x_history.append(right_x)
			stable_right_x = int(right_x)
		else:
			mean_right = np.mean(right_x_history) 
			if abs(right_x - mean_right) > 10:
				right_x_history.append(right_x)
				stable_right_x = int(right_x)
				
	return stable_left_x, stable_right_x
	

while True:
	frame = capture_frame()
	gray = preprocess_frame(frame)
	left_x, right_x, width, roi_color, roi_gray, mask = detect_lane(gray, frame)
	stable_left_x, stable_right_x = compute_x(left_x, right_x)
	offset = compute_offset(stable_left_x, stable_right_x, width)
	send_offset(offset)
	
	# Visualisering 
	vis = roi_color if COLOR_DISPLAY else cv2.cvtColor(roi_gray, cv2.COLOR_GRAY2BGR)
	
	if stable_left_x is not None:
		cv2.line(vis, (stable_left_x, 0), (stable_left_x, vis.shape[0]), (255,0,0), 2)
		
	if stable_right_x is not None:
		cv2.line(vis, (stable_right_x, 0), (stable_right_x, vis.shape[0]), (255,0,0), 2)
		
	if offset is not None:
		middle = (stable_left_x + stable_right_x) // 2
		center = width // 2
		cv2.line(vis, (middle, 0), (middle, vis.shape[0]), (0,255,0), 2)
		cv2.line(vis, (center, 0), (center, vis.shape[0]), (0,0,255), 2)
	
	cv2.imshow("Kameralivestream", vis)

	if cv2.waitKey(1) == ord("q"):
		break

cv2.destroyAllWindows()
picam2.stop()
