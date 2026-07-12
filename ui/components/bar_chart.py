from PySide6.QtWidgets import QWidget, QScrollArea
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor
from ui.theme import PALETTE as C
from utils.format import fmt_duration


class BarChartWidget(QWidget):
    _left = 110
    _right = 100
    _gap = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = []

    def set_stats(self, stats):
        self._stats = [s for s in stats if s.active_seconds + s.background_seconds > 0]
        self.update()

    def sizeHint(self):
        rows = max(1, len(self._stats))
        return QSize(400, rows * 34 + 16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(event.rect(), QColor(C.bg))
        if not self._stats:
            painter.end()
            return
        w = self.width()
        h = self.height()
        count = len(self._stats)
        bar_h = max(24, min(36, (h - 16) // count))
        total = max(s.active_seconds + s.background_seconds for s in self._stats)
        if total == 0:
            return
        active_color = QColor(C.accent)
        bg_color = QColor(C.background_bar)
        text_color = QColor(C.text)
        radius = 4
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        fm = painter.fontMetrics()
        bar_area = max(0, w - self._left - self._right - self._gap * 2)

        for i, s in enumerate(self._stats):
            y = 8 + i * (bar_h + 6)
            name = s.display_name or s.process_name
            total_sec = s.active_seconds + s.background_seconds

            painter.setPen(text_color)
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, self._left - 4)
            painter.drawText(4, y, self._left - 4, bar_h, Qt.AlignmentFlag.AlignVCenter, elided)

            a_w = int((s.active_seconds / total) * bar_area) if s.active_seconds else 0
            b_w = int((s.background_seconds / total) * bar_area) if s.background_seconds else 0
            bx = self._left + self._gap

            if a_w > 0:
                painter.setBrush(active_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bx, y, a_w, bar_h, radius, radius)
            if b_w > 0:
                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(bx + a_w, y, b_w, bar_h, radius, radius)

            label = fmt_duration(total_sec)
            painter.setPen(text_color)
            painter.drawText(bx + a_w + b_w + self._gap, y, self._right - 4, bar_h,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)

        painter.end()


class ChartContainer(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart = BarChartWidget(self)
        self.setWidgetResizable(True)
        self.setFrameShape(self.Shape.NoFrame)
        self.setWidget(self._chart)
        self.setMaximumHeight(280)

    def set_stats(self, stats):
        self._chart.set_stats(stats)
