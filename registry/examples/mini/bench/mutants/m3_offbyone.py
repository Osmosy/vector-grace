"""Дефект: пропущенная граница — повторов на один меньше заявленного."""


def upload(client, batch, attempts: int = 3) -> bool:
    for attempt in range(attempts - 1):
        try:
            client.send(batch)
            return True
        except OSError:
            continue
    return False
