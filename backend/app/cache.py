from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from functools import wraps
from typing import Any, Callable, get_type_hints
from datetime import datetime, timedelta

# In-memory cache (for dev/single-process; use Redis in production)
_CACHE: dict[str, Any] = {}
_CACHE_TTL: dict[str, datetime] = {}
_IN_FLIGHT: dict[str, asyncio.Task] = {}


def _preserve_fastapi_signature(wrapper: Callable, func: Callable) -> Callable:
    signature = inspect.signature(func)
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        hints = {}

    parameters = [
        parameter.replace(annotation=hints.get(name, parameter.annotation))
        for name, parameter in signature.parameters.items()
    ]
    wrapper.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters,
        return_annotation=hints.get("return", signature.return_annotation),
    )
    return wrapper


def cache_response(ttl_seconds: int = 5):
    """
    Decorator to cache API response for specified TTL.
    Use for expensive endpoints like /signals/generate, /fund/*/
    
    Handles both async and sync functions.
    Must be placed INSIDE the @app.route() decorator so FastAPI registers the wrapped handler.
    
    Example:
        @app.get("/signals/generate")
        @cache_response(ttl_seconds=10)
        async def generate_signal(symbol: str):
            return compute_expensive_signal(symbol)
    """
    def decorator(func: Callable) -> Callable:
        # Handle async functions
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = _make_cache_key(func.__name__, args, kwargs)
                now = datetime.utcnow()
                
                # Check cache
                if cache_key in _CACHE and cache_key in _CACHE_TTL:
                    if _CACHE_TTL[cache_key] > now:
                        return _CACHE[cache_key]
                    else:
                        del _CACHE[cache_key]
                        del _CACHE_TTL[cache_key]
                
                in_flight = _IN_FLIGHT.get(cache_key)
                if in_flight is not None and not in_flight.done():
                    return await in_flight

                async def _compute_and_store() -> Any:
                    result = await func(*args, **kwargs)
                    _CACHE[cache_key] = result
                    _CACHE_TTL[cache_key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                    return result

                task = asyncio.create_task(_compute_and_store())
                _IN_FLIGHT[cache_key] = task
                try:
                    return await task
                finally:
                    if _IN_FLIGHT.get(cache_key) is task:
                        del _IN_FLIGHT[cache_key]
            return _preserve_fastapi_signature(async_wrapper, func)
        else:
            # Handle sync functions
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = _make_cache_key(func.__name__, args, kwargs)
                now = datetime.utcnow()
                
                # Check cache
                if cache_key in _CACHE and cache_key in _CACHE_TTL:
                    if _CACHE_TTL[cache_key] > now:
                        return _CACHE[cache_key]
                    else:
                        del _CACHE[cache_key]
                        del _CACHE_TTL[cache_key]
                
                # Call original function
                result = func(*args, **kwargs)
                
                # Cache result
                _CACHE[cache_key] = result
                _CACHE_TTL[cache_key] = now + timedelta(seconds=ttl_seconds)
                
                return result
            return _preserve_fastapi_signature(sync_wrapper, func)
    
    return decorator


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate deterministic cache key from function name, args, kwargs."""
    key_parts = [func_name]
    
    for arg in args:
        serialized = _serialize_cache_value(arg)
        if serialized is not None:
            key_parts.append(serialized)
    
    for k, v in sorted(kwargs.items()):
        serialized = _serialize_cache_value(v)
        if serialized is not None:
            key_parts.append(f"{k}={serialized}")
    
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def _serialize_cache_value(value: Any) -> str | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, (list, tuple, set)):
        return json.dumps(list(value), sort_keys=True, default=str)
    if hasattr(value, "model_dump"):
        try:
            return json.dumps(value.model_dump(), sort_keys=True, default=str)
        except Exception:
            return None
    if hasattr(value, "dict"):
        try:
            return json.dumps(value.dict(), sort_keys=True, default=str)
        except Exception:
            return None
    return None


def clear_cache(pattern: str | None = None) -> None:
    """Clear cache entries by pattern or all if pattern is None."""
    if pattern is None:
        _CACHE.clear()
        _CACHE_TTL.clear()
        _IN_FLIGHT.clear()
    else:
        keys_to_delete = [k for k in _CACHE.keys() if pattern in k]
        for k in keys_to_delete:
            del _CACHE[k]
            del _CACHE_TTL[k]


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "total_keys": len(_CACHE),
        "keys": list(_CACHE.keys()),
    }

