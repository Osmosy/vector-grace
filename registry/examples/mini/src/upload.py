"""Выгрузка пакета с повторами — демонстрационный модуль примера.

Контракт: пакет отправляется до attempts раз; False означает, что пакет
потерян. Проверка повтора живёт в checkers/check_retry.py, а не здесь: код не
проверяет сам себя.
"""


def upload(client, batch, attempts: int = 3) -> bool:
    for attempt in range(attempts):  # REQ-0001
        try:
            client.send(batch)
            return True
        except OSError:
            continue
    return False
