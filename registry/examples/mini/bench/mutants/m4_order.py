"""Дефект: неверный порядок вызовов — отправка вне try, сбой не ловится."""


def upload(client, batch, attempts: int = 3) -> bool:
    for attempt in range(attempts):
        client.send(batch)
        try:
            return True
        except OSError:
            continue
    return False
