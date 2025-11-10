import logging
from pathlib import Path


class PeerFilter(logging.Filter):
    def __init__(self, peer_id: int):
        super().__init__()
        self.peer_id = peer_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.peer_id = self.peer_id
        return True


def configure_logging(peer_id: int, log_dir: str | Path = 'logs', logging_level: int = logging.INFO,
                      to_console: bool = False) -> None:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logfile = log_dir / f'log_peer_{peer_id}.log'

    root = logging.getLogger()
    root.handlers.clear()

    root.setLevel(logging_level)

    file_handler = logging.FileHandler(logfile, mode='a', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - Peer [%(peer_id)s] %(message)s',
                                  datefmt='%m/%d/%Y %H:%M:%S')

    file_handler.setFormatter(formatter)
    file_handler.addFilter(PeerFilter(peer_id))
    root.addHandler(file_handler)

    if to_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.addFilter(PeerFilter(peer_id))
        root.addHandler(console)
