from __future__ import annotations

import asyncio
import hashlib
import json
from functools import wraps
from typing import Any, Callable
from datetime import datetime, timedelta

# In-memory cache (for dev/single-process; use Redis in production)
_CACHE: dict[str, Any] = {}
_CACHE_TTL: dict[str, datetime] = {}


def cache_response(ttl_seconds: int = 5):
    """
    Decorator to cache API response for specified TTL.
    Use for expensive endpoints like /signals/generate, /fund/*/
    
    Handles both async and sync functions.
    Must be placed OUTSIDE the @app.route() decorator.
    
    Example:
        @cache_response(ttl_seconds=10)
        @app.get("/signals/generate")
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
                
                # Call original function
                result = await func(*args, **kwargs)
                
                # Cache result
                _CACHE[cache_key] = result
                _CACHE_TTL[cache_key] = now + timedelta(seconds=ttl_seconds)
                
                return result
            return async_wrapper
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
            return sync_wrapper
    
    return decorator


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate deterministic cache key from function name, args, kwargs."""
    key_parts = [func_name]
    
    # Add args to key (skip FastAPI dependency injections)
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        elif isinstance(arg, dict):
            # For Pydantic models, try to serialize
            try:
                key_parts.append(json.dumps(arg, sort_keys=True, default=str))
            except:
                pass
    
    # Add kwargs to key
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        elif isinstance(v, dict):
            try:
                key_parts.append(f"{k}={json.dumps(v, sort_keys=True, default=str)}")
            except:
                pass
    
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def clear_cache(pattern: str | None = None) -> None:
    """Clear cache entries by pattern or all if pattern is None."""
    if pattern is None:
        _CACHE.clear()
        _CACHE_TTL.clear()
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

