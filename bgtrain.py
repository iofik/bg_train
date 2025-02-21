#!/usr/bin/env python3
DEC_CLICKS = 5
INC_CLICKS = 15
SLEEP_TIME = 10
TOTAL_THRESHOLD = 90
EXCSTR_THRESHOLD = 76
TOTAL_REG_OFF = 116, -72
TOTAL_REG_SIZE = 36, 20
STR_REG_OFF = -88, 2
STR_REG_SIZE = 64, 32
CHA_DEC_OFF = 266, -114
ABIL_BUT_OFF = -48, -54
REROLL_TEXT = 'REROLL'
REROLL_SIZE = 76, 15
TESSERACT_HDR = ['level', 'page_num', 'block_num', 'par_num', 'line_num',
        'word_num', 'left', 'top', 'width', 'height', 'conf', 'text']

from PIL import ImageGrab
import sys
import time
import cv2
import numpy as np
import pytesseract
import pyautogui

def vec_sum(a, b):
    return tuple(x + y for (x, y) in zip(a, b))

def scale_sizes(scale):
    if sys.platform == 'darwin':
        scale = [x/2 for x in scale]
    def adj(sz):
        return [int(a*b) for (a, b) in zip(sz, scale)]
    for s in ('TOTAL_REG_OFF',
              'TOTAL_REG_SIZE',
              'STR_REG_OFF',
              'STR_REG_SIZE',
              'CHA_DEC_OFF',
              'ABIL_BUT_OFF'):
        globals()[s] = adj(globals()[s])

def prepare_image(image):
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    #return cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)[1]
    return cv2.bitwise_not(gray)

def find_reroll():
    img = ImageGrab.grab()
    img = prepare_image(img)
    img_data = pytesseract.image_to_data(img)
    img_data = [t.split('\t') for t in img_data.split('\n')]
    assert img_data[-1] == ['']
    assert img_data[0] == TESSERACT_HDR
    img_data = img_data[1:-1]
    assert {len(d) for d in img_data} == {12}
    rrll_idx = next(i for i, d in enumerate(img_data) if d[11] == REROLL_TEXT)
    rrll = img_data[rrll_idx]
    hdr = {fld:idx for idx, fld in enumerate(TESSERACT_HDR)}
    left, top, wdth, hght = (int(rrll[hdr[k]])
            for k in ('left', 'top', 'width', 'height'))
    scale = [int(rrll[hdr[b]]) / REROLL_SIZE[a]
            for (a, b) in enumerate(('width', 'height'))]
    button = (left + wdth//2, top + hght//2)
    if sys.platform == 'darwin': # Retina display
        button = tuple(x//2 for x in button)
    return button, scale

def get_total(region):
    img = ImageGrab.grab(bbox=region)
    img = prepare_image(img)
    config = r'--oem 3 --psm 6 outputbase digits'
    total_str = pytesseract.image_to_string(img, config=config).strip()
    return int(total_str)

def get_excstr(region):
    img = ImageGrab.grab(bbox=region)
    img = prepare_image(img)
    config = r'--oem 3 --psm 6 outputbase'
    strexc_str = pytesseract.image_to_string(img, config=config).strip().strip(',.')
    assert len(strexc_str) == 5 and strexc_str[:3] == '18/'
    excstr = int(strexc_str[3:])
    return excstr or 100

def calc_total_region(button):
    region = vec_sum(button, TOTAL_REG_OFF)
    region += vec_sum(region, TOTAL_REG_SIZE)
    return region

def calc_dec_buttons(reroll_button):
    cha_dec = vec_sum(reroll_button, CHA_DEC_OFF)
    abil_dec = [(cha_dec[0], cha_dec[1] + i*ABIL_BUT_OFF[1]) for i in range(5)]
    return abil_dec

def calc_inc_button(dex_dec_button):
    return vec_sum(dex_dec_button, ABIL_BUT_OFF)

def calc_str_region(str_inc_button):
    x, y = vec_sum(str_inc_button, STR_REG_OFF)
    return [x-STR_REG_SIZE[0]//2, y-STR_REG_SIZE[1]//2,
            x+STR_REG_SIZE[0]//2, y+STR_REG_SIZE[1]//2]

def show_excstr(dec_buttons, inc_button):
    pos = pyautogui.position()
    for button in dec_buttons:
        pyautogui.moveTo(button)
        for i in range(DEC_CLICKS):
            if pyautogui.position() != button:
                return False
            pyautogui.click()
    pyautogui.moveTo(inc_button)
    for i in range(INC_CLICKS):
        if pyautogui.position() != inc_button:
            return False
        pyautogui.click()
    pyautogui.moveTo(pos)
    return True

def wait_idle():
    try:
        pos = pyautogui.position()
        while True:
            time.sleep(SLEEP_TIME)
            new_pos = pyautogui.position()
            if pos == new_pos:
                return True
            pos = new_pos
    except KeyboardInterrupt:
        return False

def main(total_threshold, excstr_threshold):
    button, scale = find_reroll()
    scale_sizes(scale)
    print(f"Threshold: {total_threshold}/{excstr_threshold}")
    print(f"Reroll button at: {button}")
    print(f"Scale factor: ({scale[0]:.3g}, {scale[1]:.3g})")
    if any(abs(x - 1) > 0.001 for x in scale):
        print("Warning: Scaling does not work reliably! "
                "Resize game window to make scaling (1, 1)")
    total_region = calc_total_region(button)
    dec_buttons = calc_dec_buttons(button)
    inc_button = calc_inc_button(dec_buttons[-1])
    str_region = calc_str_region(inc_button)
    pyautogui.moveTo(button)
    print(f"Total Roll:", end=' ', flush=True)
    def should_proceed():
        print('...', end=' ', flush=True)
        if wait_idle():
            pyautogui.moveTo(button)
            return True
        print('- break!')
        return False
    while True:
        total = get_total(total_region)
        if total < total_threshold:
            print(total, end=' ', flush=True)
        else:
            if not show_excstr(dec_buttons, inc_button):
                if should_proceed():
                    continue
                break
            excstr = get_excstr(str_region)
            print(f"{total}/{excstr}", end=' ', flush=True)
            if excstr >= excstr_threshold:
                print('- found!')
                break
        if pyautogui.position() != button:
            if should_proceed():
                continue
            break
        pyautogui.click()

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else TOTAL_THRESHOLD,
         int(sys.argv[2]) if len(sys.argv) > 2 else EXCSTR_THRESHOLD)

