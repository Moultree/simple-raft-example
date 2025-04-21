from pebble import ProcessPool
import requests
from concurrent.futures import TimeoutError as PebbleTimeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def do_request(url: str, payload: dict):
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=None,
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return requests.post(
        url,
        json=payload
    )


class RequestUtils:
    @staticmethod
    def call_with_wall_timeout(func, timeout=3):
        pool = ProcessPool(max_workers=1)
        with pool:
            future = pool.schedule(func, timeout=timeout)
            try:
                return future.result()
            except PebbleTimeout:
                raise RuntimeError(f"Таймаут после {timeout}s")
