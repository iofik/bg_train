#!/usr/bin/env python3
REROLL_TEXT = 'REROLL'
TESSERACT_HDR = ['level', 'page_num', 'block_num', 'par_num', 'line_num',
        'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']
TOTAL_ROLL_OFF = 122, -72
TOTAL_ROLL_SIZE = 40, 26
DEFAULT_THRESHOLD = 90

from PIL import ImageGrab
import sys
import cv2
import numpy as np
import pytesseract
import pyautogui

def prepare_image(screenshot):
    image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    return thresh

def find_reroll():
    screenshot = ImageGrab.grab()
    img = prepare_image(screenshot)
    img_data = pytesseract.image_to_data(img)
    img_data = [t.split('\t') for t in img_data.split('\n')]
    assert img_data[-1] == ['']
    assert img_data[0] == TESSERACT_HDR
    img_data = img_data[1:-1]
    assert {len(d) for d in img_data} == {12}
    rrll_idx = next(i for i, d in enumerate(img_data) if d[11] == REROLL_TEXT)
    rrll_data = img_data[rrll_idx]
    hdr_map = {fld:idx for idx, fld in enumerate(TESSERACT_HDR)}
    left, top, wdth, hght = [int(rrll_data[hdr_map[k]])
            for k in ('left', 'top', 'width', 'height')]
    return left + wdth//2, top + hght//2

def get_number_from_image(screenshot):
    img = prepare_image(screenshot)
    custom_config = r'--oem 3 --psm 6 outputbase digits'
    number_str = pytesseract.image_to_string(img, config=custom_config).strip()
    try:
        return int(number_str)
    except ValueError:
        return None

def main(threshold):
    button = find_reroll()
    print(f"Threshold: {threshold}")
    print(f"Reroll button at: {button}")
    region = [button[i] + TOTAL_ROLL_OFF[i] for i in (0, 1)]
    region.extend([region[i] + TOTAL_ROLL_SIZE[i] for i in (0, 1)])
    pyautogui.moveTo(button)
    print(f"Total Roll:", end=' ', flush=True)
    while True:
        screenshot = ImageGrab.grab(bbox=region)
        number = get_number_from_image(screenshot)
        print(number, end=' ', flush=True)
        if number is not None and number >= threshold:
            print('- found!')
            break
        if pyautogui.position() != button:
            print('- break!')
            break
        pyautogui.click()

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_THRESHOLD)

