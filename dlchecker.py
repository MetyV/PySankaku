import math
import socket
import time

class SegsCheck:
    def _get_rtt_tcp(self, host: str = "sankakuapi.com", port: int = 443) -> float | None:
        try:
            start = time.time()
            with socket.create_connection((host, port), timeout=3):
                end = time.time()
                return (end - start) * 1000
        except Exception:
            return None

    def check(self, file_weight: int):
        rtts = [self._get_rtt_tcp() for _ in range(6)]
        rtts = [r for r in rtts if r is not None]

        ping = sum(rtts)/len(rtts)

        if ping <= 0:
            ping = 1

        segments = math.sqrt((file_weight * 8) / (ping * 1000 * 555)) # huli 555? ya хз, идеально подошло
        normalized = 1 + 4 * (2 / math.pi) * math.atan((segments - 1) / 10)
        s = max(1, min(5, round(normalized)))

        return s