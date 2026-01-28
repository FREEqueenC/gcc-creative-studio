from fastapi import Request
from concurrent.futures import ThreadPoolExecutor

def get_global_executor(request: Request) -> ThreadPoolExecutor:
    """
    Dependency to get the global ThreadPoolExecutor from the app state.
    Ensures we reuse the same pool instead of creating new threads per request.
    """
    return request.app.state.executor
