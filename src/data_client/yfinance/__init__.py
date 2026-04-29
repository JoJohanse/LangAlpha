"""Yahoo Finance data source backed by the yfinance library (free, no API key)."""
import yfinance as yf

yf.set_tz_cache_location("/tmp/yfinance_cache")
