"""
Validation constants loaded from environment variables.
These constants are used consistently across frontend and backend.
"""

from decouple import config

STRING_MAX_LENGTH = int(config("STRING_MAX_LENGTH", default=50))
MAX_LENGTH_EXTENDED = int(config("MAX_LENGTH_EXTENDED", default=100))
