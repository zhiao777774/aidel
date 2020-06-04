import sys, signal
import time
import cv2

from .image_processor import ImageProcessor
from .speech_service import SpeechService
from .detector import detect, BoundingBox
from .obstacle_dodge_service import Dodger, generate_maze
from .distance_measurementor import Calibrationor, Measurementor
from .environmental_model import write_environmental_model

_CALIBRATION_DISTANCE = 0
_FOCALLEN = 0.0

def initialize():
    capture = cv2.VideoCapture(0) #0代表從攝像頭開啟

    frame_size = (630, 360)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, frame_size[0])
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_size[1])
    '''
    video_fps = 60.0
    out = cv2.VideoWriter('', cv2.VideoWriter_fourcc(*'XVID'), video_fps, frame_size)
    '''
    if not capture.isOpened():
        capture.open()
    
    def _image_preprocess(frame):
        processor = ImageProcessor(frame)
        processor.basic_preprocess()
        return processor.frame

    def _project_to_2d(frame):
        processor = ImageProcessor(frame)
        return processor.cvt_to_overlook(frame)

    _signal_handle()
    #_init_services()
    while True:
        frame = capture.read()[1]
        frame = cv2.resize(frame, frame_size)
        #frame = _image_preprocess(frame)
        #frame = _project_to_2d(frame)
        result, dets = detect(frame)
        
        bboxes = []
        if dets: 
            bboxes = _calc_distance(result, dets)
            write_environmental_model('data/environmentalModel.json', bboxes)

        cv2.namedWindow('result', cv2.WINDOW_NORMAL)
        cv2.imshow('result', result)
        #out.write(result)

        if bboxes: 
            h = int(result.shape[0] / 2)
            w = result.shape[1]
            maze = generate_maze(data = bboxes, height = h, width = w, benchmark = h, resolution = 90)

            dodger = Dodger(maze)
            dodger.calculate()
            dodger.print_maze()
            dirs = dodger.directions

            time.sleep(1) #delay 1s
        

_DICT_SERVICE = {}
def _init_services():
    serivces = [
        SpeechService()
    ]

    for service in serivces:
        service.setDaemon(True)
        service.start()
        _DICT_SERVICE[type(service).__name__] = service

def _generate_bboxes(dets):
    return [BoundingBox(det) for det in dets]

def _calc_distance(frame, dets):
    h = frame.shape[0]
    w = frame.shape[1]
    
    bboxes = _generate_bboxes(dets)
    bboxes = [bbox for bbox in bboxes 
        if bbox.coordinates.lb.y >= int(h / 2)]
    bboxes = [bbox for bbox in bboxes 
        if bbox.width * bbox.height >= int((h / 4) * (w / 4))]

    for bbox in bboxes:
        distance = _measure_distance(_CALIBRATION_DISTANCE, _FOCALLEN, bbox)
        distance = round(distance, 2)
        bbox.distance = distance
        x = int(bbox.center()[0] - bbox.width / 4)
        y = int(bbox.coordinates.lt.y - 10)
        cv2.putText(frame, text = f'{distance}cm', org = (x, y), 
            fontFace = cv2.FONT_HERSHEY_SIMPLEX, fontScale = 0.50, color = (0, 0, 255), thickness = 2)
    
    return bboxes

def _measure_distance(calibration_distance, focallen, bbox):
    rad = bbox.width
    size = bbox.minEnclosingCircle()
    print(f"min enclosing circle's radius: {size}")

    measurementor = Measurementor(focallen)
    distance = measurementor.measure(size, rad)
    
    if distance < calibration_distance:
        distance = calibration_distance + distance
    print(f'Distance in cm {distance}')
    
    return distance
    
def _signal_handle():
    _handler = lambda signal, frame: sys.exit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)