import sys
import time
import argparse

import cv2

import ailia

import numpy as np

# import original modules
sys.path.append('../util')
from utils import check_file_existance  # noqa: E402
from model_utils import check_and_download_models  # noqa: E402
from webcamera_utils import adjust_frame_size  # noqa: E402C
from detector_utils import plot_results, load_image  # noqa: E402C


# ======================
# Parameters
# ======================
WEIGHT_PATH = 'yolov3-hand.opt.onnx'
MODEL_PATH = 'yolov3-hand.opt.onnx.prototxt'
REMOTE_PATH = 'https://storage.googleapis.com/ailia-models/yolov3-hand/'

HAND_WEIGHT_PATH = 'hand_obf.caffemodel'
HAND_MODEL_PATH = 'hand_obf.prototxt'
HAND_REMOTE_PATH = ''
HAND_ALGORITHM = ailia.POSE_ALGORITHM_ACCULUS_HAND

IMAGE_PATH = 'couple.jpg'
SAVE_IMAGE_PATH = 'output.png'
IMAGE_HEIGHT = 448
IMAGE_WIDTH = 448

FACE_CATEGORY = ['hand']
THRESHOLD = 0.2
IOU = 0.45


# ======================
# Arguemnt Parser Config
# ======================
parser = argparse.ArgumentParser(
    description='Yolov3 face detection model'
)
parser.add_argument(
    '-i', '--input', metavar='IMAGE',
    default=IMAGE_PATH,
    help='The input image path.'
)
parser.add_argument(
    '-v', '--video', metavar='VIDEO',
    default=None,
    help='The input video path. ' +
         'If the VIDEO argument is set to 0, the webcam input will be used.'
)
parser.add_argument(
    '-s', '--savepath', metavar='SAVE_IMAGE_PATH',
    default=SAVE_IMAGE_PATH,
    help='Save path for the output image.'
)
parser.add_argument(
    '-b', '--benchmark',
    action='store_true',
    help='Running the inference on the same input 5 times ' +
         'to measure execution performance. (Cannot be used in video mode)'
)
args = parser.parse_args()


# ======================
# Utils
# ======================
def hsv_to_rgb(h, s, v):
    bgr = cv2.cvtColor(
        np.array([[[h, s, v]]], dtype=np.uint8), cv2.COLOR_HSV2BGR
    )[0][0]
    return (int(bgr[2]), int(bgr[1]), int(bgr[0]))


def line(input_img, hand_keypoint, point1, point2, offset, scale):
    threshold = 0.3
    if hand_keypoint.points[point1].score > threshold and\
       hand_keypoint.points[point2].score > threshold:
        color = hsv_to_rgb(255*point1/ailia.POSE_KEYPOINT_CNT, 255, 255)

        x1 = int(hand_keypoint.points[point1].x * scale[0] + offset[0])
        y1 = int(hand_keypoint.points[point1].y * scale[1] + offset[1])
        x2 = int(hand_keypoint.points[point2].x * scale[0] + offset[0])
        y2 = int(hand_keypoint.points[point2].y * scale[1] + offset[1])
        cv2.line(input_img, (x1, y1), (x2, y2), color, 2)


def display_result(input_img, hand, top_left, bottom_right):
    count = hand.get_object_count()
    for idx in range(count):
        hand_keypoint = hand.get_object_hand(idx)

        offset = top_left
        scale = (bottom_right[0] - top_left[0], bottom_right[1] - top_left[1])

        line(input_img, hand_keypoint, 0, 1, offset, scale)
        line(input_img, hand_keypoint, 1, 2, offset, scale)
        line(input_img, hand_keypoint, 2, 3, offset, scale)
        line(input_img, hand_keypoint, 3, 4, offset, scale)

        line(input_img, hand_keypoint, 0, 5, offset, scale)
        line(input_img, hand_keypoint, 5, 6, offset, scale)
        line(input_img, hand_keypoint, 6, 7, offset, scale)
        line(input_img, hand_keypoint, 7, 8, offset, scale)

        line(input_img, hand_keypoint, 0, 9, offset, scale)
        line(input_img, hand_keypoint, 9,10, offset, scale)
        line(input_img, hand_keypoint,10,11, offset, scale)
        line(input_img, hand_keypoint,11,12, offset, scale)

        line(input_img, hand_keypoint, 0,13, offset, scale)
        line(input_img, hand_keypoint,13,14, offset, scale)
        line(input_img, hand_keypoint,14,15, offset, scale)
        line(input_img, hand_keypoint,15,16, offset, scale)

        line(input_img, hand_keypoint, 0,17, offset, scale)
        line(input_img, hand_keypoint,17,18, offset, scale)
        line(input_img, hand_keypoint,18,19, offset, scale)
        line(input_img, hand_keypoint,19,20, offset, scale)

# ======================
# Main functions
# ======================

def recognize_from_video():
    # net initialize
    env_id = ailia.get_gpu_environment_id()
    print(f'env_id: {env_id}')
    detector = ailia.Detector(
        MODEL_PATH,
        WEIGHT_PATH,
        len(FACE_CATEGORY),
        format=ailia.NETWORK_IMAGE_FORMAT_RGB,
        channel=ailia.NETWORK_IMAGE_CHANNEL_FIRST,
        range=ailia.NETWORK_IMAGE_RANGE_U_FP32,
        algorithm=ailia.DETECTOR_ALGORITHM_YOLOV3,
        env_id=env_id
    )

    hand = ailia.PoseEstimator(
        HAND_MODEL_PATH, HAND_WEIGHT_PATH, env_id=env_id, algorithm=HAND_ALGORITHM
    )
    hand.set_threshold(0.1)

    if args.video == '0':
        print('[INFO] Webcam mode is activated')
        capture = cv2.VideoCapture(0)
        if not capture.isOpened():
            print("[ERROR] webcamera not found")
            sys.exit(1)
    else:
        if check_file_existance(args.video):
            capture = cv2.VideoCapture(args.video)

    while(True):
        ret, frame = capture.read()
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        if not ret:
            continue

        _, resized_img = adjust_frame_size(frame, IMAGE_HEIGHT, IMAGE_WIDTH)

        img = cv2.cvtColor(resized_img, cv2.COLOR_BGR2BGRA)
        detector.compute(img, THRESHOLD, IOU)
        res_img = plot_results(detector, resized_img, FACE_CATEGORY, False)

        h, w = img.shape[0], img.shape[1]
        count = detector.get_object_count()
        texts = []
        for idx in range(count):
            # get detected hand
            obj = detector.get_object(idx)
            margin = 1.0
            cx = obj.x + obj.w/2
            cy = obj.y + obj.h/2
            cw = max(obj.w,obj.h) * margin
            fx = cx - cw/2
            fy = cy - cw/2
            fw = cw
            fh = cw
            fx=max(fx,0)
            fy=max(fy,0)
            fw=min(fw,w-fx)
            fh=min(fh,h-fy)
            top_left = (int(w*fx), int(h*fy))
            bottom_right = (int(w*(fx+fw)), int(h*(fy+fh)))

            color = hsv_to_rgb(0, 255, 255)
            cv2.rectangle(res_img, top_left, bottom_right, color, 4)

            # get detected face
            crop_img = img[top_left[1]:bottom_right[1],top_left[0]:bottom_right[0],0:4]
            if crop_img.shape[0]<=0 or crop_img.shape[1]<=0:
                continue
            #crop_img, resized_frame = adjust_frame_size(
            #    crop_img, HAND_IMAGE_HEIGHT, HAND_IMAGE_WIDTH
            #)

            # inferece
            _ = hand.compute(crop_img.astype(np.uint8, order='C'))

            # postprocessing
            display_result(res_img, hand, top_left, bottom_right)

        cv2.imshow('frame', res_img)

    capture.release()
    cv2.destroyAllWindows()
    print('Script finished successfully.')


def main():
    # model files check and download
    check_and_download_models(WEIGHT_PATH, MODEL_PATH, REMOTE_PATH)

    # video mode
    recognize_from_video()


if __name__ == '__main__':
    main()