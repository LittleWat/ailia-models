import sys
import time
import argparse

import cv2
import numpy as np

import ailia
import blazehand_utils as but

sys.path.append('../../util')
from utils import get_base_parser, update_parser  # noqa: E402
from webcamera_utils import adjust_frame_size, get_capture  # noqa: E402
from image_utils import load_image  # noqa: E402
from model_utils import check_and_download_models  # noqa: E402


# ======================
# Parameters 1
# ======================
IMAGE_PATH = 'person_hand.jpg'
SAVE_IMAGE_PATH = 'output.png'
IMAGE_HEIGHT = 256
IMAGE_WIDTH = 256


# ======================
# Argument Parser Config
# ======================
parser = get_base_parser(
    'BlazeHand, an on-device real-time hand tracking.', IMAGE_PATH, SAVE_IMAGE_PATH,
)
args = update_parser(parser)


# ======================
# Parameters 2
# ======================
DETECTION_MODEL_NAME = 'blazepalm'
LANDMARK_MODEL_NAME = 'blazehand'
# if args.normal:
DETECTION_WEIGHT_PATH = f'{DETECTION_MODEL_NAME}.onnx'
DETECTION_MODEL_PATH = f'{DETECTION_MODEL_NAME}.onnx.prototxt'
LANDMARK_WEIGHT_PATH = f'{LANDMARK_MODEL_NAME}.onnx'
LANDMARK_MODEL_PATH = f'{LANDMARK_MODEL_NAME}.onnx.prototxt'
# else:
    # DETECTION_WEIGHT_PATH = f'{DETECTION_MODEL_NAME}.opt.onnx'
    # DETECTION_MODEL_PATH = f'{DETECTION_MODEL_NAME}.opt.onnx.prototxt'
    # LANDMARK_WEIGHT_PATH = f'{LANDMARK_MODEL_NAME}.opt.onnx'
    # LANDMARK_MODEL_PATH = f'{LANDMARK_MODEL_NAME}.opt.onnx.prototxt'
DETECTION_REMOTE_PATH = f'https://storage.googleapis.com/ailia-models/{DETECTION_MODEL_NAME}/'
LANDMARK_REMOTE_PATH = f'https://storage.googleapis.com/ailia-models/{LANDMARK_MODEL_NAME}/'


# ======================
# Utils
# ======================
def draw_landmarks(img, points, connections=[], color=(0, 0, 255), size=2):
    for connection in connections:
        x0, y0 = points[connection[0]]
        x1, y1 = points[connection[1]]
        x0, y0 = int(x0), int(y0)
        x1, y1 = int(x1), int(y1)
        cv2.line(img, (x0, y0), (x1, y1), (0, 255, 0), size)
    for point in points:
        x, y = point
        x, y = int(x), int(y)
        cv2.circle(img, (x, y), size+1, color, thickness=cv2.FILLED)


# ======================
# Main functions
# ======================
def recognize_from_image():
    # prepare input data
    src_img = cv2.imread(args.input)
    img256, _, scale, pad = but.resize_pad(src_img[:,:,::-1])
    input_data = img256.astype('float32') / 255.
    input_data = np.expand_dims(np.moveaxis(input_data, -1, 0), 0)

    # net initialize
    env_id = ailia.get_gpu_environment_id()
    print(f'env_id: {env_id}')
    detector = ailia.Net(DETECTION_MODEL_PATH, DETECTION_WEIGHT_PATH, env_id=env_id)
    estimator = ailia.Net(LANDMARK_MODEL_PATH, LANDMARK_WEIGHT_PATH, env_id=env_id)

    # inference
    print('Start inference...')
    if args.benchmark:
        print('BENCHMARK mode')
        for _ in range(5):
            start = int(round(time.time() * 1000))
            # Palm detection
            preds = detector.predict([input_data])
            detections = but.detector_postprocess(preds)

            # Hand landmark estimation
            presence = [0, 0] # [left, right]
            if detections[0].size != 0:
                imgs, affines, _ = but.estimator_preprocess(src_img, detections, scale, pad)
                estimator.set_input_shape(imgs.shape)
                flags, handedness, normalized_landmarks = estimator.predict([imgs])

                # postprocessing
                landmarks = but.denormalize_landmarks(normalized_landmarks, affines)
                for i in range(len(flags)):
                    landmark, flag, handed = landmarks[i], flags[i], 1 - handedness[i]
                    if flag > 0.75:
                        if handed < 0.5: # Right handedness when not flipped camera input
                            presence[0] = 1
                        else:
                            presence[1] = 1
                        draw_landmarks(src_img, landmark[:,:2], but.HAND_CONNECTIONS, size=2)
            end = int(round(time.time() * 1000))
            print(f'\tailia processing time {end - start} ms')
    else:
        # Palm detection
        preds = detector.predict([input_data])
        detections = but.detector_postprocess(preds)

        # Hand landmark estimation
        presence = [0, 0] # [left, right]
        if detections[0].size != 0:
            imgs, affines, _ = but.estimator_preprocess(src_img, detections, scale, pad)
            estimator.set_input_shape(imgs.shape)
            flags, handedness, normalized_landmarks = estimator.predict([imgs])

            # postprocessing
            landmarks = but.denormalize_landmarks(normalized_landmarks, affines)
            for i in range(len(flags)):
                landmark, flag, handed = landmarks[i], flags[i], 1 - handedness[i]
                if flag > 0.75:
                    if handed > 0.5: # Right handedness when not flipped camera input
                        presence[0] = 1
                    else:
                        presence[1] = 1
                    draw_landmarks(src_img, landmark[:,:2], but.HAND_CONNECTIONS, size=2)

    if presence[0] and presence[1]:
        hand_presence = 'Left and right'
    elif presence[0]:
        hand_presence = 'Left'
    elif presence[1]:
        hand_presence = 'Right'
    else:
        hand_presence = 'No hand'
    print(f'Hand presence: {hand_presence}')
    cv2.imwrite(args.savepath, src_img)
    print('Script finished successfully.')


def recognize_from_video():
    # net initialize
    env_id = ailia.get_gpu_environment_id()
    print(f'env_id: {env_id}')
    detector = ailia.Net(DETECTION_MODEL_PATH, DETECTION_WEIGHT_PATH, env_id=env_id)
    estimator = ailia.Net(LANDMARK_MODEL_PATH, LANDMARK_WEIGHT_PATH, env_id=env_id)

    capture = get_capture(args.video)

    # create video writer if savepath is specified as video format
    if args.savepath != SAVE_IMAGE_PATH:
        f_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        f_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        save_h, save_w = webcamera_utils.calc_adjust_fsize(
            f_h, f_w, IMAGE_HEIGHT, IMAGE_WIDTH
        )
        writer = webcamera_utils.get_writer(args.savepath, save_h, save_w)
    else:
        writer = None

    while(True):
        ret, frame = capture.read()
        frame = np.ascontiguousarray(frame[:,::-1,:])
        if (cv2.waitKey(1) & 0xFF == ord('q')) or not ret:
            break

        img256, _, scale, pad = but.resize_pad(frame[:,:,::-1])
        input_data = img256.astype('float32') / 255.
        input_data = np.expand_dims(np.moveaxis(input_data, -1, 0), 0)

        # inference
        # Palm detection
        preds = detector.predict([input_data])
        detections = but.detector_postprocess(preds)

        # Hand landmark estimation
        presence = [0, 0] # [left, right]
        if detections[0].size != 0:
            img, affine, _ = but.estimator_preprocess(frame, detections, scale, pad)
            estimator.set_input_shape(img.shape)
            flags, handedness, normalized_landmarks = estimator.predict([img])

            # postprocessing
            landmarks = but.denormalize_landmarks(normalized_landmarks, affine)
            for i in range(len(flags)):
                landmark, flag, handed = landmarks[i], flags[i], handedness[i]
                if flag > 0.75:
                    if handed > 0.5:
                        presence[0] = 1
                    else:
                        presence[1] = 1
                    draw_landmarks(frame, landmark[:,:2], but.HAND_CONNECTIONS, size=2)

        if presence[0] and presence[1]:
            text = 'Left and right'
        elif presence[0]:
            text = 'Left'
        elif presence[1]:
            text = 'Right'
        else:
            text = 'No hand'
        cv2.putText(frame, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
        cv2.imshow('frame', frame)

        # save results
        if writer is not None:
            writer.write(frame)

    capture.release()
    cv2.destroyAllWindows()
    print('Script finished successfully.')
    pass


def main():
    # model files check and download
    check_and_download_models(DETECTION_WEIGHT_PATH, DETECTION_MODEL_PATH, DETECTION_REMOTE_PATH)
    check_and_download_models(LANDMARK_WEIGHT_PATH, LANDMARK_MODEL_PATH, LANDMARK_REMOTE_PATH)

    if args.video is not None:
        # video mode
        recognize_from_video()
    else:
        # image mode
        recognize_from_image()


if __name__ == '__main__':
    main()
