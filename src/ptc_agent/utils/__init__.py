"""Shared utility modules for Open PTC Agent.

This package contains utilities shared across the codebase:
- file_operations: File data utilities for state management and persistence
"""

from .file_operations import (
    FileData,
    _file_operations_log_reducer,
    _create_file_data,
    _file_data_to_string,
    string_to_file_data,
)

__all__ = [
    # File operations
    "FileData",
    "_file_operations_log_reducer",
    "_create_file_data",
    "_file_data_to_string",
    "string_to_file_data",
]
