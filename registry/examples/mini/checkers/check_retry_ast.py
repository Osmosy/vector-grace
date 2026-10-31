"""Кандидат v2: структурный (AST) предикат перехода retry_on_upload.

Версия v1 (check_retry.py) проверяет наличие подстрок — она ловит только
удаление повтора целиком. Здесь проверяется структура: запас повторов не
меньше трёх, цикл по range(attempts), отправка внутри try с обработкой
OSError, успех возвращает True, исчерпание — False после цикла.

Предикат не запускается в приёмке, пока не станет новой версией чекера:
смена файла меняет sha256, и replay обязан отказать, а не тихо проверять
другим кодом.
"""
import argparse
import ast
import json
import sys
from pathlib import Path

TARGET = Path("src") / "upload.py"


def check(source: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, f"модуль не разбирается: {exc}"

    fn = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "upload"
        ),
        None,
    )
    if fn is None:
        return False, "нет функции upload"

    defaults = fn.args.defaults
    names = [arg.arg for arg in fn.args.args][-len(defaults) :] if defaults else []
    reserve = dict(zip(names, defaults)).get("attempts")
    if not (
        isinstance(reserve, ast.Constant)
        and isinstance(reserve.value, int)
        and reserve.value >= 3
    ):
        return False, "запас повторов меньше трёх или не задан числом"

    for node in ast.walk(fn):
        if not isinstance(node, ast.For):
            continue
        it = node.iter
        if not (
            isinstance(it, ast.Call)
            and getattr(it.func, "id", None) == "range"
            and len(it.args) == 1
            and getattr(it.args[0], "id", None) == "attempts"
        ):
            continue
        tries = [stmt for stmt in node.body if isinstance(stmt, ast.Try)]
        if not tries:
            return False, "отправка вне try: сбой не ловится"
        handles_oserror = any(
            isinstance(handler.type, ast.Name) and handler.type.id in ("OSError", "Exception")
            for stmt in tries
            for handler in stmt.handlers
        )
        if not handles_oserror:
            return False, "try не обрабатывает OSError"
        send_inside_try = any(
            isinstance(inner, ast.Call) and getattr(inner.func, "attr", None) == "send"
            for stmt in tries
            for inner in ast.walk(stmt)
        )
        if not send_inside_try:
            return False, "отправка вне try: сбой не ловится"
        returns_true = any(
            isinstance(inner, ast.Return)
            and isinstance(inner.value, ast.Constant)
            and inner.value.value is True
            for stmt in tries
            for inner in ast.walk(stmt)
        )
        if not returns_true:
            return False, "успех не возвращает True внутри try"
        tail_index = fn.body.index(node) + 1 if node in fn.body else -1
        tail = fn.body[tail_index] if 0 <= tail_index < len(fn.body) else None
        if not (
            isinstance(tail, ast.Return)
            and isinstance(tail.value, ast.Constant)
            and tail.value.value is False
        ):
            return False, "исчерпание повторов не возвращает False после цикла"
        return True, "структура повтора на месте"
    return False, "нет цикла по range(attempts)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--transition", required=True)
    args = parser.parse_args()

    target = Path(args.root) / TARGET
    if not target.is_file():
        print(json.dumps({"ok": False, "detail": f"нет {TARGET}"}, ensure_ascii=False))
        return 1
    ok, detail = check(target.read_text("utf-8"))
    print(json.dumps({"ok": ok, "detail": f"{args.transition}: {detail}"}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
