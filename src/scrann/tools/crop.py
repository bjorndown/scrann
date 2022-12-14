from typing import Tuple, Union

import cairo

from scrann.tools import Tool


class Crop(Tool):
    _start_point: Union[Tuple[int, int], None]
    _end_point: Union[Tuple[int, int], None]

    def __init__(self, image_rect):
        super().__init__()
        self.label = "Crop"
        self._start_point = None
        self._end_point = None
        self.surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, int(image_rect.width), int(image_rect.height)
        )
        self._context = cairo.Context(self.surface)
        self._fill_color = (0, 0, 0, 0.5)

    def _draw(self):
        if not self._start_point or not self._end_point:
            return

        self._clear_surface()
        self._context.set_source_rgba(*self._fill_color)
        self._context.fill()

        width = self._end_point[0] - self._start_point[0]
        height = self._end_point[1] - self._start_point[1]

        self._context.rectangle(*self._start_point, width, height)
        self._context.set_source_rgba(0, 0, 0, 0.8)
        self._context.fill()

    def on_mouse_press(self, event, color):
        self._start_point = (event.x, event.y)
        self._end_point = self._start_point
        self._clear_surface()

    def on_mouse_release(self, event):
        self._end_point = (event.x, event.y)
        self._clear_surface()

    def on_mouse_move(self, event):
        self._end_point = (event.x, event.y)
        self._draw()

    def undo(self):
        pass # TODO

    def update_surface(self, context: cairo.Context) -> cairo.Surface:
        start = context.user_to_device(self._start_point[0], self._start_point[1])
        end = context.user_to_device(self._end_point[0], self._end_point[1])
        height = abs(end[1] - start[1])
        width = abs(end[0] - start[0])
        return context.get_target().create_for_rectangle(*start, width, height)
