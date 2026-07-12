import sys
import os
import logging

from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtNetwork import QLocalSocket, QLocalServer

from data.database import Database
from data.repository import Repository
from services.config_manager import ConfigManager
from core.tracker import TrackerService
from ui.main_window import MainWindow
from ui.style import APP_QSS
from config import APP_NAME, APP_VERSION
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

_SINGLETON_KEY = "RusLOXPy_singleton"


def acquire_single_instance():
    sock = QLocalSocket()
    sock.connectToServer(_SINGLETON_KEY)
    if sock.waitForConnected(300):
        sock.disconnectFromServer()
        sock.close()
        return None
    QLocalServer.removeServer(_SINGLETON_KEY)
    server = QLocalServer()
    if not server.listen(_SINGLETON_KEY):
        logger.warning("Не удалось занять singleton-сокет: %s",
                       server.errorString())
    return server


def main():
    setup_logging()
    logger.info("Запуск %s v%s", APP_NAME, APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(APP_QSS)

    server = acquire_single_instance()
    if server is None:
        logger.warning("Приложение уже запущено — выход")
        os._exit(0)
    app._single_instance_server = server # type: ignore

    db = Database()
    repo = Repository(db)
    config = ConfigManager()

    tracker = TrackerService(repo, config)
    tracker.start()

    window = MainWindow(repo, tracker, config)
    window.db = db # type: ignore
    window.show()

    exit_code = app.exec()
    server.close()
    logger.info("Завершение (code=%s)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
