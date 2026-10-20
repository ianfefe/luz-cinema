"""Widget de Canvas interativo para seleção de Matiz (Hue) e Saturação (Color Wheel)."""
from __future__ import annotations

import math
import tkinter as tk
from PIL import ImageTk
from icon_utils import create_color_wheel_image


class ColorWheel:
    def __init__(self, canvas: tk.Canvas, size: int, on_color_change):
        self.canvas = canvas
        self.size = size
        self.radius = size / 2.0
        self.on_color_change = on_color_change
        self.img = create_color_wheel_image(size)
        self.photo = ImageTk.PhotoImage(self.img, master=self.canvas)
        self.canvas.create_image(self.radius, self.radius, image=self.photo)
        self.cursor_outer = self.canvas.create_oval(0, 0, 14, 14, outline="#000000", width=2)
        self.cursor = self.canvas.create_oval(0, 0, 12, 12, outline="#ffffff", width=2)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.set_color_hsv(0.0, 1.0)

    def on_click(self, event):
        self.update_from_coords(event.x, event.y)

    def on_drag(self, event):
        self.update_from_coords(event.x, event.y)

    def update_from_coords(self, x: float, y: float):
        dx = x - self.radius
        dy = y - self.radius
        dist = math.sqrt(dx * dx + dy * dy)
        sat = min(1.0, dist / self.radius)
        angle = math.atan2(dy, dx)
        hue = (angle / (2.0 * math.pi)) % 1.0
        if dist > self.radius:
            cx = self.radius + math.cos(angle) * self.radius
            cy = self.radius + math.sin(angle) * self.radius
        else:
            cx, cy = x, y
        self.canvas.coords(self.cursor_outer, cx - 7, cy - 7, cx + 7, cy + 7)
        self.canvas.coords(self.cursor, cx - 6, cy - 6, cx + 6, cy + 6)
        self.on_color_change(hue, sat)

    def set_color_hsv(self, hue: float, sat: float):
        angle = hue * 2.0 * math.pi
        dist = sat * self.radius
        cx = self.radius + math.cos(angle) * dist
        cy = self.radius + math.sin(angle) * dist
        self.canvas.coords(self.cursor_outer, cx - 7, cy - 7, cx + 7, cy + 7)
        self.canvas.coords(self.cursor, cx - 6, cy - 6, cx + 6, cy + 6)
