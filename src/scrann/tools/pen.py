from dataclasses import dataclass
from typing import List, Tuple

import cairo

from scrann.log import log
from scrann.tools import Tool


@dataclass
class Path:
    points: List[Tuple[float, float]]
    color: Tuple[float, float, float, float]


class Pen(Tool):
    def __init__(self, image_rect):
        super().__init__()
        self.label = 'Pen'
        self._paths = []
        self._path = []
        self._color = None
        self._line_width = 3
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(image_rect.width), int(image_rect.height))
        self._context = cairo.Context(self.surface)

    def on_mouse_press(self, event, color):
        self._color = color
        self._context.set_line_width(self._line_width)

    def on_mouse_release(self, event):
        log.debug(f'stop drawing, recorded {len(self._path)} points')
        self._paths.append(Path(list(self._path), self._color))
        del self._path[:]

    def on_mouse_move(self, event):
        self._path.append((event.x, event.y))
        self._draw()

    def _draw(self):
        self._clear_surface()

        for path in self._paths:
            self._draw_path(path.points, path.color)

        self._draw_path(self._path, self._color)

    def _draw_path(self, points, color):
        self._context.set_source_rgba(*color)
        for i in range(len(points)):
            self._context.move_to(*points[i])

            if i + 1 < len(points):
                self._context.line_to(*points[i + 1])
                self._context.stroke()

    def undo(self):
        if len(self._paths) > 0:
            self._paths.pop()
            self._draw()
