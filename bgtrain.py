#!/usr/bin/env python3
DEC_CLICKS = 5
INC_CLICKS = 15
CHECK_TIME = 1
SLEEP_TIME = 120
TOTAL_BOX_OFF = 116, -72
TOTAL_BOX_SIZE = 36, 20
STR_BOX_OFF = -88, 2
STR_BOX_SIZE = 64, 32
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
    for s in ('TOTAL_BOX_OFF',
              'TOTAL_BOX_SIZE',
              'STR_BOX_OFF',
              'STR_BOX_SIZE',
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
    center = (left + wdth//2, top + hght//2)
    box = (left, top, left + wdth, top + hght)
    if sys.platform == 'darwin': # Retina display
        center = tuple(x//2 for x in center)
        box = tuple(x//2 for x in box)
    return center, box, scale

_image_to_string_cache = {}
_image_to_string_config = [
    '--oem 3 --psm 6 outputbase',
    '--oem 3 --psm 6 outputbase digits',
]

def image_to_string(img, digits=False):
    args = (img.tobytes(), digits)
    if args not in _image_to_string_cache:
        img = prepare_image(img)
        _image_to_string_cache[args] = pytesseract.image_to_string(
                img, config=_image_to_string_config[digits]).strip()
    return _image_to_string_cache[args]

def get_total(box):
    img = ImageGrab.grab(bbox=box)
    total_str = image_to_string(img, digits=True)
    return int(total_str)

def get_excstr(box):
    img = ImageGrab.grab(bbox=box)
    strexc_str = image_to_string(img, digits=False).strip(',.')
    assert len(strexc_str) == 5 and strexc_str[:3] == '18/'
    excstr = int(strexc_str[3:])
    return excstr or 100

def calc_total_box(button):
    box = vec_sum(button, TOTAL_BOX_OFF)
    box += vec_sum(box, TOTAL_BOX_SIZE)
    return box

def calc_dec_buttons(reroll_center):
    cha_dec = vec_sum(reroll_center, CHA_DEC_OFF)
    abil_dec = [(cha_dec[0], cha_dec[1] + i*ABIL_BUT_OFF[1]) for i in range(5)]
    return abil_dec

def calc_inc_button(dex_dec_button):
    return vec_sum(dex_dec_button, ABIL_BUT_OFF)

def calc_str_box(str_inc_button):
    x, y = vec_sum(str_inc_button, STR_BOX_OFF)
    return [x-STR_BOX_SIZE[0]//2, y-STR_BOX_SIZE[1]//2,
            x+STR_BOX_SIZE[0]//2, y+STR_BOX_SIZE[1]//2]

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

def wait_idle(reroll_box):
    try:
        max_idle_cycles = (SLEEP_TIME - 1) // CHECK_TIME + 1
        last_pos = pyautogui.position()
        idle_cycles = max_idle_cycles
        while idle_cycles:
            time.sleep(CHECK_TIME)
            pos = pyautogui.position()
            if reroll_box[0] <= pos[0] <= reroll_box[2] and reroll_box[1] <= pos[1] <= reroll_box[3]:
                break
            if pos == last_pos:
                idle_cycles -= 1
            else:
                idle_cycles = max_idle_cycles
                last_pos = pos
    except KeyboardInterrupt:
        return False
    return True

class Threshold:
    @classmethod
    def from_str(cls, s: str):
        return cls(*map(int, s.split('/')))
    def __init__(self, total: int, excstr: int):
        self.total = total
        self.excstr = excstr
    def __ge__(self, other):
        return self.total >= other.total and self.excstr >= other.excstr
    def __str__(self) -> str:
        return f'{self.total}/{self.excstr}'
    def __repr__(self) -> str:
        return str(self)

def main(thresholds: list[Threshold]):
    min_total = min(t.total for t in thresholds)
    reroll_center, reroll_box, scale = find_reroll()
    scale_sizes(scale)
    print(f"Thresholds: {', '.join(map(str, thresholds))}")
    print(f"Reroll button at: {reroll_center}")
    print(f"Scale factor: ({scale[0]:.3g}, {scale[1]:.3g})")
    if any(abs(x - 1) > 0.01 for x in scale):
        print("Warning: Scaling does not work reliably! "
                "Resize game window to make scaling (1, 1) and restart BG trainer.")
    print("Do not move the game window, make it always visible on screen.")
    total_box = calc_total_box(reroll_center)
    dec_buttons = calc_dec_buttons(reroll_center)
    inc_button = calc_inc_button(dec_buttons[-1])
    str_box = calc_str_box(inc_button)
    pyautogui.moveTo(reroll_center)
    print(f"Total Roll:", end=' ', flush=True)
    def should_proceed():
        print('...', end=' ', flush=True)
        if wait_idle(reroll_box):
            pyautogui.moveTo(reroll_center)
            return True
        print('- break!')
        return False
    while True:
        total = get_total(total_box)
        if total < min_total:
            print(total, end=' ', flush=True)
        else:
            if not show_excstr(dec_buttons, inc_button):
                if should_proceed():
                    continue
                break
            roll = Threshold(total, get_excstr(str_box))
            print(f"{roll}", end=' ', flush=True)
            if any(roll >= t for t in thresholds):
                pyautogui.moveTo(inc_button) # Avoid accidental click on Reroll
                print('- found!')
                break
        if pyautogui.position() != reroll_center:
            if should_proceed():
                continue
            break
        pyautogui.click()

if __name__ == '__main__':
    try:
        thresholds = list(map(Threshold.from_str, sys.argv[1:]))
        thresholds[0]
    except:
        print(f"Usage: {sys.argv[0]} TOTAL/EXCSTR [...]")
    else:
        main(thresholds)
