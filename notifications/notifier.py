"""
VOXEN NOTIFICATION ENGINE - WINDOWS TOAST & IN-APP NOTIFICATIONS
Natywny system powiadomień dla Windows (Toast / Balloon) z dźwiękiem i asynchronicznym workerem.
"""

import base64
import logging
import platform
import subprocess
import threading
from typing import Callable, List, Optional

logger = logging.getLogger("Voxen.Notifications")


class WindowsNotifier:
    """Natywny menedżer powiadomień Windows i in-app"""

    _instance: Optional["WindowsNotifier"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, app_id: str = "Voxen Messenger"):
        if getattr(self, "_initialized", False):
            return
        self.app_id = app_id
        self._listeners: List[Callable[[str, str], None]] = []
        self._is_windows = (platform.system().lower() == "windows")
        self.dnd_mode: bool = False
        self.sound_enabled: bool = True
        self._initialized = True

    def set_dnd_mode(self, enabled: bool) -> None:
        """Włącza lub wyłącza tryb Nie przeszkadzać (DND)"""
        self.dnd_mode = enabled

    def set_sound_enabled(self, enabled: bool) -> None:
        """Włącza lub wyłącza dźwięk powiadomień"""
        self.sound_enabled = enabled

    def add_listener(self, callback: Callable[[str, str], None]):
        """Rejestruje listener do powiadomień wewnątrz aplikacji (in-app toast banner)"""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, str], None]):
        """Usuwa listener"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(
        self,
        title: str,
        message: str,
        play_sound: bool = True
    ) -> None:
        """
        Wysyła powiadomienie (Toast w Windows + In-App callback) w osobnym wątku roboczym,
        aby nie blokować głównej pętli zdarzeń UI.
        """
        # 1. Poinformuj zarejestrowane listenery in-app
        for listener in list(self._listeners):
            try:
                listener(title, message)
            except Exception as e:
                logger.debug(f"Błąd listenera in-app notification: {e}")

        # 2. Uruchom natywne powiadomienie Windows asynchronicznie w tle
        thread = threading.Thread(
            target=self._send_windows_toast,
            args=(title, message, play_sound),
            daemon=True
        )
        thread.start()

    def _play_chime(self):
        """Odtwarza subtelny dźwięk powiadomienia systemu Windows"""
        if self._is_windows:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def _send_windows_toast(self, title: str, message: str, play_sound: bool):
        """Wysyła natywny Toast Windows za pomocą PowerShell WinRT lub BalloonTip"""
        if play_sound and self.sound_enabled and not self.dnd_mode:
            self._play_chime()

        # W trybie DND całkowicie pomijamy wyskakujące okna toast w systemie
        if self.dnd_mode:
            return

        if not self._is_windows:
            return

        clean_title = (
            title.replace('"', '`"')
            .replace("'", "''")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("&", "&amp;")
        )
        clean_msg = (
            message.replace('"', '`"')
            .replace("'", "''")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("&", "&amp;")
        )

        ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
try {{
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{clean_title}</text>
      <text>{clean_msg}</text>
    </binding>
  </visual>
</toast>
"@
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $appId = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
}} catch {{
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = "{clean_title}"
    $notify.BalloonTipText = "{clean_msg}"
    $notify.Visible = $True
    $notify.ShowBalloonTip(3000)
}}
"""
        try:
            encoded_bytes = base64.b64encode(ps_script.encode("utf-16le"))
            encoded_str = encoded_bytes.decode("ascii")

            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags = subprocess.CREATE_NO_WINDOW

            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_str],
                timeout=5.0,
                capture_output=True,
                creationflags=flags
            )
        except Exception as e:
            logger.debug(f"Powiadomienie Windows Toast pominięte: {e}")
