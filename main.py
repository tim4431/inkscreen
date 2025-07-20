import os, time, threading

from ha import *
from component import *
from send_image import http_post


class UI:

    def __init__(self):
        if SECRETS["inkscreen"]["enable"] and SECRETS["inkscreen"]["clear_at_start"]:
            # Clear the screen at startup if configured
            print("Clearing the screen at startup...")
            http_post(SECRETS["inkscreen"]["host"], "/clear")
        #
        self.ui_settings = CONF["ui_settings"]

        self.components_conf = CONF["components"]
        self.components = {}
        self.ha_registry = {}

        for name in self.components_conf:
            component = create_component(name)
            self.components[name] = component
            if component.entity_id:
                self.ha_registry.update({component.entity_id: component})
        # print(self.ha_registry)

        self.running = False
        self.component_timers = {}  # 存储每个组件的定时器

        # make output directory
        os.makedirs("output", exist_ok=True)

        # add preview server thread
        self.preview_server_thread = None
        self.preview_server_port = 8080

    def start(self):
        if self.running:
            return

        self.running = True

        for name, component in self.components.items():
            if component.refresh_type == "ha_event":
                component.callback()

        # ha subscription thread
        ha_thread = threading.Thread(target=self.start_ha_subscription, daemon=True)
        ha_thread.start()

        # timer for components
        self._start_component_timers()

    def _start_component_timers(self):
        """为所有基于时间刷新的组件启动定时器"""
        print("Starting component timers...")
        for name, component in self.components.items():
            if hasattr(component, "refresh_type") and component.refresh_type == "time":
                try:
                    resp = component.callback()
                    # print(f"Component {name} initialized with response: {resp}")
                except Exception as e:
                    print(f"[!] Error refreshing component {name}: {e}")
                self._schedule_component_refresh(name, component)

    def _schedule_component_refresh(self, component_name, component):
        """为指定组件安排定时刷新"""
        if not self.running:
            return

        def refresh_callback():
            if self.running:
                component.callback()
                self._schedule_component_refresh(component_name, component)

        # 获取刷新间隔
        interval = getattr(component, "refresh_interval", 600)

        # 创建定时器
        timer = threading.Timer(interval, refresh_callback)
        timer.daemon = True
        timer.start()

        self.component_timers[component_name] = timer

    def start_ha_subscription(self):
        try:
            with WebsocketClient(WS_URL, TOKEN) as ws:
                print("Subscribed to Home Assistant WebSocket")
                with ws.listen_events("state_changed") as events:
                    for ev in events:
                        data = ev.data
                        eid = data["entity_id"]
                        if eid in WATCHED:
                            state_changed = update_entity_from_state_changed(data)
                            if state_changed and (eid in self.ha_registry):
                                component = self.ha_registry[eid]
                                component.callback()
        except Exception as e:
            print(f"[!] Error subscribing to Home Assistant: {e}")

    def stop(self):
        self.running = False
        # ha_thread 是在 start 方法中作为守护线程启动的，无需显式停止
        # 取消所有定时器
        for timer in self.component_timers.values():
            timer.cancel()
        self.component_timers.clear()


# 示例用法
if __name__ == "__main__":
    ui_manager = UI()
    ui_manager.start()

    try:
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在退出...")
        ui_manager.stop()
