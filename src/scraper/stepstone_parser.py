import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from .utils import fetch_html, clean_text, make_absolute_url, parse_date

class StepstoneParser:
    """
    Parser for Stepstone group sites (stepstone.de/.at/.be/.nl).
    Implements a resilient strategy for both current and slightly changed layouts.
    """

    SEARCH_PATHS = [