"""Split one keyboard into two virtual Xbox 360 pads (ViGEmBus) so two Azahar windows
can be driven at the same time; controller input reaches a window even when it isn't focused.

  P1 (pad 1): W jump (A), A/S/D left/down/right, E up, Q roll (Y), R back (B), Tab start
  P2 (pad 2): I jump (A), J/K/L left/down/right, O up, U roll (Y), P back (B), Enter start

Polls GetAsyncKeyState, so it works no matter which window has focus. Ctrl+C to quit.
"""
import ctypes, time
import vgamepad as vg

user32 = ctypes.windll.user32
B = vg.XUSB_BUTTON
VK_TAB, VK_RETURN = 0x09, 0x0D

LAYOUT = [
    {"a": "W", "down": "S", "left": "A", "right": "D", "y": "Q", "up": "E", "b": "R", "start": VK_TAB},
    {"a": "I", "down": "K", "left": "J", "right": "L", "y": "U", "up": "O", "b": "P", "start": VK_RETURN},
]
BUTTONS = {
    "up": B.XUSB_GAMEPAD_DPAD_UP, "down": B.XUSB_GAMEPAD_DPAD_DOWN,
    "left": B.XUSB_GAMEPAD_DPAD_LEFT, "right": B.XUSB_GAMEPAD_DPAD_RIGHT,
    "a": B.XUSB_GAMEPAD_A, "b": B.XUSB_GAMEPAD_B, "y": B.XUSB_GAMEPAD_Y, "start": B.XUSB_GAMEPAD_START,
}

def vk(k):
    return k if isinstance(k, int) else ord(k)

def down(k):
    return user32.GetAsyncKeyState(vk(k)) & 0x8000 != 0

pads = [vg.VX360Gamepad() for _ in LAYOUT]
print("Virtual pads ready. P1: WASD/Q/E/Tab   P2: IJKL/U/O/Enter   (Ctrl+C to quit)")
state = [None] * len(pads)
try:
    while True:
        for i, (pad, keys) in enumerate(zip(pads, LAYOUT)):
            pressed = frozenset(name for name, k in keys.items() if down(k))
            if pressed == state[i]:
                continue
            state[i] = pressed
            pad.reset()
            for name in pressed:
                pad.press_button(BUTTONS[name])
            # mirror left/right/down onto the left stick too, in case the game reads the circle pad;
            # "up" stays d-pad only (stick-up felt like a jump in-game)
            x = (32767 if "right" in pressed else 0) - (32767 if "left" in pressed else 0)
            y = -(32767 if "down" in pressed else 0)
            pad.left_joystick(x_value=x, y_value=y)
            pad.update()
        time.sleep(0.002)
except KeyboardInterrupt:
    pass
