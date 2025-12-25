import re
from typing import List

TABLE_BLOCK_RE = re.compile(
    r"(?:^|\n)(\|.*?\|\n\|[-:| ]+\|\n(?:\|.*?\|\n?)+)",
    re.S
)

def extract_tables(markdown: str) -> List[str]:
    if not markdown:
        return []
    return [m.group(1).strip() for m in TABLE_BLOCK_RE.finditer(markdown)]
