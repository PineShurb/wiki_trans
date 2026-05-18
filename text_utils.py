def split_text(text: str, chunk_size: int = 220) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size
    return chunks


def parse_timeout(raw_text: str) -> float:
    value = raw_text.strip()
    if not value:
        return 20.0
    timeout = float(value)
    if timeout <= 0:
        raise ValueError("超时必须大于 0")
    return timeout
