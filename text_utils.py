def split_text(text: str, chunk_size: int = 220) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size
    return chunks


def parse_timeout(raw_text: str) -> float | None:
    value = raw_text.strip()
    if not value:
        return None
    timeout = float(value)
    if timeout == 0:
        return None
    if timeout < 0:
        raise ValueError("超时必须大于等于 0；留空或 0 表示不限时")
    return timeout
