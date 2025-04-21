from pebble import ProcessPool
import requests
from concurrent.futures import TimeoutError as PebbleTimeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def do_request(url: str, payload: dict):
    session = requests.Session()

    # 2. Configure the retry strategy
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
    """
    Utility class for making HTTP requests with total wall-clock timeouts,
    including DNS resolution, connection, and reading.
    """

    @staticmethod
    def call_with_wall_timeout(func, timeout=3):
        """
        Run func(*args) in a separate process, and kill it if it runs longer than `timeout` seconds.
        """
        # Create a small pool just for this call (or reuse one if you prefer)
        pool = ProcessPool(max_workers=1)
        with pool:
            # schedule returns a Future that will be cancelled if it exceeds `timeout`
            future = pool.schedule(func, timeout=timeout)
            try:
                return future.result()  # will raise PebbleTimeout on timeout
            except PebbleTimeout:
                raise RuntimeError(f"Function call timed out after {timeout}s")
