from abc import abstractmethod

import cairo


class Tool:
    label: str

    def __init__(self):
        self._context = None

    def _clear_surface(self):
        self._context.set_operator(cairo.Operator.CLEAR)
        self._context.paint()
        self._context.set_operator(cairo.Operator.OVER)

    @abstractmethod
    def on_mouse_press(self, event, color):
        pass

    @abstractmethod
    def on_mouse_release(self, event):
        pass

    @abstractmethod
    def on_mouse_move(self, event):
        pass

    @abstractmethod
    def undo(self):
        pass
