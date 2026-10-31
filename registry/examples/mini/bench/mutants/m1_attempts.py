"""Дефект: подменённый коэффициент — один повтор вместо трёх."""


def upload(client, batch, attempts: int = 1) -> bool:
    for attempt in range(attempts):
        try:
            client.send(batch)
            return True
        except OSError:
            continue
    return False
