"""Lightweight access logging utility."""

import time
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from config import ACCESS_LOG_FILE


class AccessLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware to log minimal client access information."""
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response information."""
        start_time = time.time()
        
        # Get client info
        client_ip = self._get_client_ip(request)
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "Unknown")[:90]  # Limit length
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Get status code
        status_code = response.status_code
        
        # Log only important endpoints (skip health checks to reduce noise)
        if path not in ["/health", "/"]:
            # Convert UTC to EST/EDT (America/New_York handles DST automatically)
            utc_time = datetime.now(ZoneInfo("UTC"))
            est_time = utc_time.astimezone(ZoneInfo("America/New_York"))
            timestamp = est_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            
            self._log_access(
                timestamp=timestamp,
                ip=client_ip,
                method=method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                user_agent=user_agent
            )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded IP (when behind proxy/load balancer)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _log_access(
        self,
        timestamp: str,
        ip: str,
        method: str,
        path: str,
        status: int,
        duration_ms: int,
        user_agent: str
    ):
        """Write access log entry in readable format."""
        try:
            # Format with labels for better readability
            # Status code color indicators
            status_indicator = "✓" if 200 <= status < 300 else "✗" if status >= 400 else "!"
            
            log_entry = (
                f"[{timestamp}] {status_indicator} {method:6} {path:30} | "
                f"IP: {ip:15} | Status: {status} | Duration: {duration_ms:4}ms | "
                f"UA: {user_agent}\n"
            )
            
            with open(ACCESS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            # Don't fail the request if logging fails
            print(f"Failed to write access log: {str(e)}")

