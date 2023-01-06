# native imports
import time

# local imports
import pydirectinput


def trace_square():
    # trace a box with the mouse movement
    pydirectinput.moveTo(300, 300)
    time.sleep(1)
    pydirectinput.moveTo(400, 300)
    time.sleep(1)
    pydirectinput.moveTo(400, 400)
    time.sleep(1)
    pydirectinput.moveTo(300, 400)
    time.sleep(1)
    pydirectinput.moveTo(300, 300)


def mouse_return_accuracy():
    # when the mouse is moved relative, and then reversed relative again, confirm
    # that the cursor returns to the same position
    pydirectinput.moveTo(300, 300)
    pos_start = pydirectinput.position()  # pyright: ignore[reportPrivateUsage]
    time.sleep(1)
    pydirectinput.move(100, 0)
    time.sleep(1)
    pydirectinput.move(-100, 0)
    pos_end = pydirectinput.position()  # pyright: ignore[reportPrivateUsage]
    print(f"{pos_start} == {pos_end}? {pos_start == pos_end}")


def clicks_and_typing():
    pydirectinput.moveTo(500, 300)
    time.sleep(1)
    pydirectinput.click(500, 400)
    pydirectinput.keyDown('g')
    time.sleep(0.05)
    pydirectinput.keyUp('g')
    time.sleep(0.05)
    pydirectinput.press(['c', 'v', 't'])
    time.sleep(0.05)
    pydirectinput.typewrite('myword')


def wasd_movement():
    pydirectinput.keyDown('w')
    time.sleep(1)
    pydirectinput.keyUp('w')
    time.sleep(1)
    pydirectinput.keyDown('d')
    time.sleep(0.25)
    pydirectinput.keyUp('d')
    time.sleep(1)
    pydirectinput.move(300, None)


def basic_click():
    pydirectinput.click()


def arrow_keys():
    pydirectinput.keyDown('left')
    time.sleep(0.25)
    pydirectinput.keyUp('left')
    time.sleep(1)
    pydirectinput.keyDown('right')
    time.sleep(0.25)
    pydirectinput.keyUp('right')
    time.sleep(1)
    pydirectinput.keyDown('down')
    time.sleep(0.25)
    pydirectinput.keyUp('down')
    time.sleep(1)
    pydirectinput.keyDown('up')
    time.sleep(0.25)
    pydirectinput.keyUp('up')
    time.sleep(1)


def relative_mouse():
    pydirectinput.moveRel(0, 400, relative=True)
    time.sleep(1)
    pydirectinput.moveRel(0, -400, relative=True)
    time.sleep(1)
    pydirectinput.moveRel(-50, -50, relative=True)
    time.sleep(3)
    pydirectinput.moveTo(1150, 0, relative=True)


if __name__ == '__main__':

    time.sleep(4)
    print("trace_square")
    trace_square()
    time.sleep(1)
    print("mouse_return_accuracy")
    mouse_return_accuracy()
    time.sleep(1)
    print("clicks_and_typing")
    clicks_and_typing()
    time.sleep(1)
    print("wasd_movement")
    wasd_movement()
    time.sleep(1)
    print("basic_click")
    basic_click()
    time.sleep(1)
    print("arrow_keys")
    arrow_keys()
    time.sleep(1)
    print("relative_mouse")
    relative_mouse()
    print("done")
