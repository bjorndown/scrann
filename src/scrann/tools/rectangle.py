from dataclasses import dataclass
from typing import Tuple, Union

import cairo

from scrann.log import log
from scrann.tools import Tool


@dataclass
class R:
    points: Tuple[Tuple[int, int], Tuple[int, int]]
    color: Tuple[float, float, float, float]


class Rectangle(Tool):
    _start_point: Union[Tuple[int, int], None]
    _end_point: Union[Tuple[int, int], None]

    def __init__(self, image_rect):
        super().__init__()
        self.label = 'Rectangle'
        self._rectangles = []
        self._start_point = None
        self._end_point = None
        self._color = None
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(image_rect.width), int(image_rect.height))
        self._context = cairo.Context(self.surface)

    def _draw(self):
        self._clear_surface()

        for rect in self._rectangles:
            self._draw_rectangle(rect.points[0], rect.points[1], rect.color)

        if self._start_point:
            self._draw_rectangle(self._start_point, self._end_point, self._color)

    def _draw_rectangle(self, start_point, end_point, color):
        self._context.set_source_rgba(*color)
        width = end_point[0] - start_point[0]
        height = end_point[1] - start_point[1]
        self._context.rectangle(*start_point, width, height)
        self._context.stroke()

    def on_mouse_press(self, event, color):
        self._color = color
        self._start_point = (event.x, event.y)
        self._end_point = self._start_point

    def on_mouse_release(self, event):
        self._end_point = (event.x, event.y)
        self._rectangles.append(R((self._start_point, self._end_point), self._color))
        self._start_point = None
        self._end_point = None
        self._draw()

    def on_mouse_move(self, event):
        self._end_point = (event.x, event.y)
        self._draw()

    def undo(self):
        if len(self._rectangles) > 0:
            undone_rect = self._rectangles.pop()
            log.debug(f'undid rect {undone_rect}')
            self._draw()
