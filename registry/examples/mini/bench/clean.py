"""Чистый вариант для замера: совпадает с src/upload.py."""


def upload(client, batch, attempts: int = 3) -> bool:
    for attempt in range(attempts):
        try:
            client.send(batch)
            return True
        except OSError:
            continue
    return False
