from ha import *
from typing import List, Dict, Callable
import numpy as np, pandas as pd
import time
from PIL import Image, ImageDraw, ImageFont
import os, io, cairosvg
from pathlib import Path
import matplotlib

matplotlib.use("Agg")  # 必须在plt导入前设置
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pytz

from send_image import draw_image
from sunsethue import *


def plot_sensor_history(ax, eids: List[str]):
    """Fetch and plot sensor history data with Home Assistant style."""
    # ha_color = "#336da0"

    for i, eid in enumerate(eids):
        df = get_sensor_history(eid)
        if df is not None and not df.empty:
            df = df.dropna(subset=["temperature"]).sort_values("time")

            if not df.empty:
                df = df.set_index("time")

                df.index = df.index.tz_convert(TIMEZONE)

                df_resampled = (
                    df["temperature"].resample("5min").mean()
                )  # Resample to 5-minute intervals
                df_resampled = df_resampled.ffill()  # Forward-fill missing values
                entity_label = CONF["entities"].get(eid, {}).get("name", eid)

                # Define different line styles
                line_styles = ["-", ":", "--", "-."]

                # Use different line style for each entity
                ax.plot(
                    df_resampled.index,
                    df_resampled.values,
                    label=entity_label,  # 使用友好名称而非实体ID
                    color="black",
                    linewidth=3,
                    linestyle=line_styles[i % len(line_styles)],  # Cycle through styles
                )

    # Formatting the plot to look like Home Assistant
    ax.set_xlabel("", fontsize=10)  # 移除x轴标签
    ax.set_ylabel("°C", fontsize=10, rotation=0, labelpad=10)
    ax.tick_params(axis="x", rotation=0, labelsize=9)
    ax.tick_params(axis="y", labelsize=9)

    # Format x-axis to show time nicely with timezone
    local_tz = pytz.timezone("America/Los_Angeles")  # UTC-7
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=local_tz))
    ax.xaxis.set_major_locator(
        mdates.HourLocator(interval=3, tz=local_tz)
    )  # 每3小时显示一次

    # Set y-axis ticks
    y_min, y_max = ax.get_ylim()
    ax.yaxis.set_ticks(
        np.arange(np.floor(y_min * 4) / 4, np.ceil(y_max * 4) / 4 + 0.01, 0.5)
    )

    # Make tick labels large and bold
    ax.tick_params(axis="both", labelsize=12)

    ax.legend(fontsize=11, loc="upper right")

    # Remove spines and adjust grid
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#e0e0e0")
    ax.spines["left"].set_color("#e0e0e0")

    ax.grid(True, which="major", axis="both", linestyle="-", color="#e0e0e0", alpha=0.7)

    # 调整图表边距
    plt.tight_layout(pad=0.5)


def create_component(
    name: str,
) -> "BaseComponent":
    component_conf = CONF["components"][name]
    component_type = component_conf["type"]
    if component_type == "ha_event":
        return HAComponent(name)
    elif component_type == "timer":
        return TimerComponent(name)
    elif component_type == "notebook":
        return NotebookComponent(name)
    else:
        raise ValueError(f"Unknown component type: {component_type}")


class BaseComponent:
    def __init__(
        self,
        name: str,
    ):
        self.name = name
        self.component_conf = CONF["components"][name]
        self.component_type = self.component_conf["type"]
        self.block_size = int(CONF["ui_settings"]["block_size"])

        # Position and size in blocks
        self.X = self.component_conf["position"][0]
        self.Y = self.component_conf["position"][1]
        self.W = self.component_conf["size"][0]
        self.H = self.component_conf["size"][1]

        # Calculate pixel dimensions
        self.x_px = int(self.X * self.block_size)
        self.y_px = int(self.Y * self.block_size)
        self.width_px = int(self.W * self.block_size)
        self.height_px = int(self.H * self.block_size)

        self.params = self.component_conf.get("params", {})

        img = Image.new("RGB", (self.width_px, self.height_px), "white")
        self.img = img
        draw = ImageDraw.Draw(img)
        self.draw = draw

    def callback(self):
        self.callback_func()
        if SECRETS["inkscreen"].get("enable", True):
            self.render_to_inkscreen()

    def render_to_inkscreen(self) -> bool:
        """Render the component to an image file."""
        print(
            f"[{datetime.now():%H:%M:%S}] Rendering {self.name} to ink screen at ({self.x_px}, {self.y_px}) with size {self.width_px}x{self.height_px}"
        )
        try:
            draw_image(
                host=SECRETS["inkscreen"]["host"],
                path=Path(f"output/{self.name}.jpg"),
                bw=False,
                preview=False,
                x=self.x_px,
                y=self.y_px,
                w=self.width_px,
                h=self.height_px,
                clear=False,
                package="2ppB",
                max_usage=0.8,  # PSRAM usage threshold
            )
            return True
        except Exception as e:
            print(f"Error rendering {self.name}: {e}")
            return False

    def _draw_rounded_rectangle(
        self, draw, coords, radius, fill=None, outline=None, width=1
    ):
        """绘制圆角矩形"""
        x1, y1, x2, y2 = coords

        # 绘制主体矩形（中央部分）
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

        # 绘制四个圆角（填充）
        draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill)
        draw.pieslice([x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill)

        # 如果需要边框，单独绘制边框
        if outline and width > 0:
            # 绘制直线边框
            draw.line(
                [x1 + radius, y1, x2 - radius, y1], fill=outline, width=width
            )  # 上边
            draw.line(
                [x1 + radius, y2, x2 - radius, y2], fill=outline, width=width
            )  # 下边
            draw.line(
                [x1, y1 + radius, x1, y2 - radius], fill=outline, width=width
            )  # 左边
            draw.line(
                [x2, y1 + radius, x2, y2 - radius], fill=outline, width=width
            )  # 右边

            # 绘制圆角边框
            draw.arc(
                [x1, y1, x1 + 2 * radius, y1 + 2 * radius],
                180,
                270,
                fill=outline,
                width=width,
            )
            draw.arc(
                [x2 - 2 * radius, y1, x2, y1 + 2 * radius],
                270,
                360,
                fill=outline,
                width=width,
            )
            draw.arc(
                [x1, y2 - 2 * radius, x1 + 2 * radius, y2],
                90,
                180,
                fill=outline,
                width=width,
            )
            draw.arc(
                [x2 - 2 * radius, y2 - 2 * radius, x2, y2],
                0,
                90,
                fill=outline,
                width=width,
            )

    def draw_frame(self, draw: ImageDraw.Draw, bg_color: str = "white"):
        border_width = 4
        margin = 10
        corner_radius = 20

        # 计算圆角矩形位置和大小
        rect_x = margin
        rect_y = margin
        rect_width = self.width_px - 2 * margin
        rect_height = self.height_px - 2 * margin

        self._draw_rounded_rectangle(
            draw,
            (rect_x, rect_y, rect_x + rect_width, rect_y + rect_height),
            corner_radius,
            fill=bg_color,
            outline="black",
            width=border_width,
        )

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(Path("assets/MYRIADPRO-BOLD.OTF"), size)
        except IOError:
            print("Using default font due to error loading custom font.")
            return ImageFont.load_default()

    def _get_monospaced_font(self, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(Path("assets/consolab.ttf"), size)
        except IOError:
            print("Using default monospaced font due to error loading custom font.")
            return ImageFont.load_default()

    def _invert_icon(self, icon: Image.Image) -> Image.Image:
        """反色图标，用于深色背景"""
        # 将RGBA图像转换为RGB，然后反色
        if icon.mode == "RGBA":
            # 分离Alpha通道
            r, g, b, a = icon.split()
            # 反色RGB通道
            r = Image.eval(r, lambda x: 255 - x)
            g = Image.eval(g, lambda x: 255 - x)
            b = Image.eval(b, lambda x: 255 - x)
            # 重新合并
            return Image.merge("RGBA", (r, g, b, a))
        else:
            return Image.eval(icon, lambda x: 255 - x)

    def draw_icon(
        self, icon_path: str, x: int, y: int, icon_size: float, invert: bool = False
    ) -> Image.Image:
        """绘制图标到组件"""

        try:
            png_data = cairosvg.svg2png(
                url=icon_path, output_width=icon_size, output_height=icon_size
            )
            icon = Image.open(io.BytesIO(png_data)).convert("RGBA")

            if invert:
                icon = self._invert_icon(icon)

            # print(icon_x, icon_y)
            self.img.paste(icon, (x, y), icon)
        except Exception as e:
            print("Error loading icon:", e)

    def invert_image(self) -> Image.Image:
        """反转整个组件图像颜色"""
        if self.img.mode == "RGBA":
            r, g, b, a = self.img.split()
            r = Image.eval(r, lambda x: 255 - x)
            g = Image.eval(g, lambda x: 255 - x)
            b = Image.eval(b, lambda x: 255 - x)
            self.img = Image.merge("RGBA", (r, g, b, a))
        else:
            self.img = Image.eval(self.img, lambda x: 255 - x)

    def hook_callback_func(self):
        # Callback configuration
        try:
            self.callback_name = self.component_conf.get(
                "callback", "_default_callback_func"
            )
            self.callback_func = getattr(
                self, self.callback_name, self._default_callback_func
            )
            # print(f"Component {self.name} using callback: {self.callback_func}")
        except KeyError:
            print(f"[!] Callback '{self.callback_name}' not found, using default.")
            self.callback_func = self._default_callback_func


class HAComponent(BaseComponent):
    def __init__(
        self,
        name: str,
    ):
        super().__init__(name)
        self.entity_id = self.component_conf["entity_id"]
        self.entity = ha_states.get(self.entity_id, None)
        self._default_callback_func = self.default_ha_callback
        self.hook_callback_func()

    def default_ha_callback(self) -> bool:
        fg_color, bg_color = (
            ("black", "white") if self.entity.normal else ("white", "black")
        )
        self.draw_frame(self.draw, bg_color=bg_color)

        render_state_text = self.params.get("render_state_text", True)
        if render_state_text:
            icon_size = int(self.height_px * 0.6)
            icon_x = int(self.width_px / 2 - icon_size / 2)
            icon_y = int(self.height_px * 0.4 - icon_size / 2)
        else:
            icon_size = int(self.height_px * 0.6)
            icon_x = int(self.width_px / 2 - icon_size / 2)
            icon_y = int(self.height_px / 2 - icon_size / 2)

        # Draw the icon
        self.draw_icon(
            self.params.get("icon", "assets/lamp.svg"),
            x=icon_x,
            y=icon_y,
            icon_size=icon_size,
            invert=not self.entity.normal,
        )

        if render_state_text:
            try:
                font_size = int(min(max(12, self.height_px / 5.5), 80))
                font = ImageFont.truetype(Path("assets/arialbd.ttf"), font_size)
            except IOError:
                print("Using default font due to error loading custom font.")
                font = ImageFont.load_default()

            state_text = self.entity.state_name
            self.draw.text(
                (self.width_px // 2, self.height_px * 4 // 5),
                state_text,
                fill=fg_color,
                font=font,
                anchor="mm",
            )

        try:
            output_path = f"output/{self.name}.jpg"
            self.img.save(output_path)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {self.name} rendered to {output_path}"
            )
            return True
        except Exception as e:
            print(f"[!] Error rendering entity {self.entity_id}: {e}")
            return False


class TimerComponent(BaseComponent):
    def __init__(
        self,
        name: str,
    ):
        super().__init__(name)

        self.refresh_interval = self.component_conf["refresh_interval"]
        self._default_callback_func = self.default_timer_callback
        self.hook_callback_func()

    def default_timer_callback(self) -> bool:
        width = self.width_px
        height = self.height_px
        DPI = 200

        self.draw_frame(self.draw, bg_color="white")

        try:
            # Calculate the inner area for the plot (considering margins)
            margin = 10
            border_width = 4
            plot_margin = margin + border_width + 5  # Extra padding for plot

            # Create the matplotlib plot with adjusted size to fit inside the frame
            plot_width = width - (2 * plot_margin)
            plot_height = height - (2 * plot_margin)
            fig, ax = plt.subplots(
                figsize=(plot_width / DPI, plot_height / DPI), dpi=DPI
            )
            plot_sensor_history(ax, self.params["entities"])

            # Save the plot to a temporary buffer
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=DPI, transparent=True)
            plt.close(fig)
            buf.seek(0)

            # Open the plot image and paste it onto our framed image
            plot_img = Image.open(buf).convert("RGBA")
            self.img.paste(
                plot_img, (plot_margin, plot_margin), plot_img.convert("RGBA")
            )

            # Save the final image
            self.img.save(f"output/{self.name}.jpg")
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {self.name}: Chart saved to output/{self.name}.jpg"
            )
            return True
        except Exception as e:
            print(f"[!] {self.name}: Chart rendering error: {e}")
            return False

    def render_sunsethue_forecast(self, **kwargs) -> bool:
        """Render the sunset hue forecast."""

        try:
            weather_data = get_weather_forecast()
            weather_report = format_forecast_data(weather_data)
            quality = weather_report.get("quality", "No data")
            quality_text = weather_report.get("quality_text", "No data")
            golden_hour_str = weather_report.get("golden_hour", "No data")
            blue_hour_str = weather_report.get("blue_hour", "No data")
            cloud_cover = weather_report.get("cloud_cover", "No data")

            title_font = self._get_font(64)
            percent_font = self._get_font(108)
            text_font = self._get_font(50)

            # Background color based on quality
            self.draw_frame(self.draw, bg_color="white")

            # Draw the "Sunset" title
            self.draw.text((40, 30), "Sunset", fill="black", font=title_font)

            # Draw the golden hour time with icon
            D = 340
            W_ICON_TEXT = 90
            ICON_SIZE = 80
            sunset_icon_x = self.width_px - D
            sunset_icon_y = 30
            H_ICON_TEXT = 20
            self.draw_icon(
                icon_path=kwargs.get("icon_golden", "assets/sun.svg"),
                x=sunset_icon_x,
                y=sunset_icon_y,
                icon_size=ICON_SIZE,
                invert=False,
            )
            self.draw.text(
                (sunset_icon_x + W_ICON_TEXT, sunset_icon_y + H_ICON_TEXT),
                golden_hour_str,
                fill="black",
                font=text_font,
            )

            # Draw the blue hour time with icon
            blue_icon_x = self.width_px - D
            blue_icon_y = 130
            self.draw_icon(
                icon_path=kwargs.get("icon_blue", "assets/sunset.svg"),
                x=blue_icon_x,
                y=blue_icon_y,
                icon_size=ICON_SIZE,
                invert=False,
            )
            self.draw.text(
                (blue_icon_x + W_ICON_TEXT, blue_icon_y + H_ICON_TEXT),
                blue_hour_str,
                fill="black",
                font=text_font,
            )

            # Draw the quality percentage
            self.draw.text(
                (30, 115), f"{int(quality*100)}%", fill="black", font=percent_font
            )

            # Draw the quality text below percentage
            self.draw.text((40, 230), quality_text, fill="black", font=title_font)

            # Draw cloud cover with icon
            cloud_icon_x = self.width_px - D
            cloud_icon_y = 230
            self.draw_icon(
                icon_path=kwargs.get("icon_cloud", "assets/cloud.svg"),
                x=cloud_icon_x,
                y=cloud_icon_y,
                icon_size=ICON_SIZE,
                invert=False,
            )
            self.draw.text(
                (cloud_icon_x + W_ICON_TEXT, cloud_icon_y + H_ICON_TEXT),
                f"{int(cloud_cover*100)}%",
                fill="black",
                font=text_font,
            )

            # Save the image
            self.img.save(f"output/{self.name}.jpg")
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {self.name}: Sunset forecast saved to output/{self.name}.jpg"
            )
            return True
        except Exception as e:
            print(f"[!] {self.name}: Sunset forecast rendering error: {e}")
            return False


class NotebookComponent(BaseComponent):
    def __init__(self, name: str):
        super().__init__(name)
        self.component_type = "notebook"
        self._default_callback_func = self.default_notebook_callback
        self.hook_callback_func()

    def default_notebook_callback(self):
        text = self.params.get(
            "text",
            "Helloworld",
        )
        self.draw_frame(self.draw, bg_color="white")
        self.draw.text(
            (60, 30),
            text,
            fill="black",
            font=self._get_monospaced_font(self.params.get("text_size", 70)),
            spacing=self.params.get("text_spacing", 4),
        )
        #
        icon_size = 120
        if "icon" in self.params:
            self.draw_icon(
                icon_path=self.params["icon"],
                x=self.width_px - icon_size - 20,
                y=self.height_px - icon_size - 20,
                icon_size=icon_size,
                invert=False,
            )
        #
        try:
            output_path = f"output/{self.name}.jpg"
            self.img.save(output_path)
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] {self.name} rendered to {output_path}"
            )
            return True
        except Exception as e:
            print(f"[!] Error rendering notebook {self.name}: {e}")
            return False
