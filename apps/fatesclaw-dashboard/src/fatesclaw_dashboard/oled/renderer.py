from __future__ import annotations

import asyncio
import logging
import time

from PIL import Image, ImageDraw

from fatesclaw_dashboard.oled.device import OLEDTarget
from fatesclaw_dashboard.oled.theme import DEFAULT_THEME
from fatesclaw_dashboard.oled.views import draw_view
from fatesclaw_dashboard.state import AppState

LOGGER = logging.getLogger(__name__)


class OledRenderer:
    def __init__(
        self,
        state: AppState,
        target: OLEDTarget,
        refresh_hz: int = 8,
        home_animation_speed: float = 1.0,
    ) -> None:
        self.state = state
        self.target = target
        self.refresh_hz = max(refresh_hz, 1)
        self.home_animation_speed = max(home_animation_speed, 0.1)

    async def run(self) -> None:
        interval = 1 / self.refresh_hz
        while True:
            snapshot = await self.state.snapshot()
            image = Image.new(
                self.target.image_mode,
                (self.target.width, self.target.height),
                color=DEFAULT_THEME.background,
            )
            draw = ImageDraw.Draw(image)
            draw_view(
                draw,
                snapshot,
                self.target.width,
                self.target.height,
                DEFAULT_THEME,
                frame_time=time.monotonic() * self.home_animation_speed,
            )
            self.target.display(image)
            LOGGER.debug("oled_frame view=%s", snapshot.current_view.value)
            await asyncio.sleep(interval)
