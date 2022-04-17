'''
Test how well Windows normalized coordinates map to your real screen pixels.
'''
# pyright: reportPrivateUsage=false

import pydirectinput


# ------------------------------------------------------------------------------
def coordinate_conversion_test(  # pyright: ignore[reportUnusedFunction]
    virtual: bool = False,
    dump: bool = False
) -> None:
    ''''''
    def _raw_moveTo(x: int, y: int, virtual: bool = False) -> None:
        dwFlags: int = (
          pydirectinput._MOUSEEVENTF_MOVE | pydirectinput._MOUSEEVENTF_ABSOLUTE
        )
        if virtual:
            dwFlags |= pydirectinput._MOUSEEVENTF_VIRTUALDESK
        pydirectinput._send_input(pydirectinput._create_mouse_input(
            dx=x, dy=y,
            dwFlags=dwFlags
        ))

    results: list[tuple[int, int]] = []
    _raw_moveTo(0, 32000, virtual=virtual)
    pydirectinput._sleep(1)
    for i in range(65536):
        _raw_moveTo(i, 32000, virtual=virtual)
        x, _ = pydirectinput._position()
        results.append((i, x))
    if dump:
        import json
        with open('coordinates.json', 'w')as fp:
            json.dump(results, fp)
# ------------------------------------------------------------------------------


if __name__ == '__main__':
    coordinate_conversion_test(virtual=True, dump=True)
