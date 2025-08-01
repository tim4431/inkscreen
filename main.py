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
        self.running = False
        self.ui_settings = CONF["ui_settings"]

        self.components_conf = CONF["components"]
        self.components = {}
        self.ha_registry = {}

        for name in self.components_conf:
            component = create_component(name)
            self.components[name] = component
            if component.component_type in ["ha_event"]:
                self.ha_registry.update({component.entity_id: component})
        # print(self.ha_registry)

        self.component_timers = {}  # 存储每个组件的定时器

        # Home Assistant 重连相关配置
        self.ha_reconnect_interval = SECRETS["homeassistant"].get(
            "reconnect_interval", 600
        )
        self.last_ha_connection_attempt = 0
        self.ha_connection_active = False

        # make output directory
        os.makedirs("output", exist_ok=True)

    def start(self):
        if self.running:
            return

        self.running = True

        for name, component in self.components.items():
            if component.component_type in ["ha_event", "notebook", "timer"]:
                component.callback()

        # ha subscription thread
        ha_thread = threading.Thread(target=self.start_ha_subscription, daemon=True)
        ha_thread.start()

        # timer for components
        self._start_component_timers()

    def _start_component_timers(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting component timers...")
        for name, component in self.components.items():
            if component.component_type == "timer":
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Scheduling timer for {name}"
                )
                self._schedule_component_refresh(name, component)

    def _schedule_component_refresh(self, component_name, component):
        """为指定组件安排定时刷新"""
        if not self.running:
            return

        def refresh_callback():
            if self.running:
                component.callback()
                self._schedule_component_refresh(component_name, component)

        interval = getattr(component, "refresh_interval", 600)
        timer = threading.Timer(interval, refresh_callback)
        timer.daemon = True
        timer.start()

        self.component_timers[component_name] = timer

    def start_ha_subscription(self):
        """启动 Home Assistant WebSocket 订阅，带有重连功能"""
        while self.running:
            try:
                current_time = time.time()

                # 检查是否需要等待重连间隔
                if (
                    current_time - self.last_ha_connection_attempt
                ) < self.ha_reconnect_interval:
                    time.sleep(5)  # 每5秒检查一次
                    continue

                self.last_ha_connection_attempt = current_time
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Attempting to connect to Home Assistant WebSocket..."
                )

                with WebsocketClient(WS_URL, TOKEN) as ws:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Successfully connected to Home Assistant WebSocket"
                    )
                    self.ha_connection_active = True

                    with ws.listen_events("state_changed") as events:
                        for ev in events:
                            if not self.running:
                                break

                            data = ev.data
                            eid = data["entity_id"]
                            if eid in WATCHED:
                                state_changed = update_entity_from_state_changed(data)
                                if state_changed and (eid in self.ha_registry):
                                    component = self.ha_registry[eid]
                                    component.callback()

            except Exception as e:
                self.ha_connection_active = False
                print(f"[!] Home Assistant WebSocket connection error: {e}")
                if self.running:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Will attempt to reconnect in {self.ha_reconnect_interval} seconds ..."
                    )

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] Home Assistant subscription stopped"
        )
        self.ha_connection_active = False

    def get_ha_connection_status(self) -> bool:
        """获取 Home Assistant 连接状态"""
        return self.ha_connection_active

    def stop(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Stopping UI manager...")
        self.running = False
        self.ha_connection_active = False
        # ha_thread 是在 start 方法中作为守护线程启动的，无需显式停止
        # Cancel all timers
        for timer in self.component_timers.values():
            timer.cancel()
        self.component_timers.clear()


if __name__ == "__main__":
    ui_manager = UI()
    ui_manager.start()

    try:
        # keey the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting ...")
        ui_manager.stop()
