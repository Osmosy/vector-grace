"""Дефект: инвертированные возвраты — успех считается потерей пакета."""


def upload(client, batch, attempts: int = 3) -> bool:
    for attempt in range(attempts):
        try:
            client.send(batch)
            return False
        except OSError:
            continue
    return True
