# DSpark — Confidence-Scheduled Speculative Decoding

DeepSeek, 2026. Ускорение GPT в 50-400% на том же оборудовании.

## Проблема MTP (Multi-Token Prediction)

MTP давно существует, но параллельные драфтеры предсказывают много бракованных
токенов — не понимают причинно-следственные связи. Каузальные драфтеры (Eagle)
испытывают деградацию производительности.

## Архитектура DSpark

6-этапный конвейер:

### 1. Anchor Token
Target-модель (DeepSeek V4 Pro) генерирует ОДИН токен как обычно.
Это anchor — точка входа для speculative-блока.

### 2. Semi-Autoregressive Generation
BERT-подобный трансформер берёт anchor и предсказывает блок ~5 токенов СРАЗУ,
угадывая их в позициях [MASK] аналогично BERT.

### 3. Sequential Block (причинно-следственная коррекция)
Корректирует вероятности токенов с учётом причинно-следственных связей:
- Быстрый режим: Марковская головка (один предыдущий токен)
- Точный режим: RNN (весь контекст драфтера)

### 4. Confidence Head
Оценивает вероятности C1-C4 что токены будут ПРИНЯТЫ большой моделью.
Это ключевое отличие от обычного speculative decoding — confidence-based
отбраковка до верификации.

### 5. Hardware-Aware Prefix Scheduler
Анализирует C1-C4 и текущую загрузку GPU.
Подрезает длину speculative-блока: balancing load vs discarding low-confidence tail.

### 6. Target Verification
DeepSeek V4 Pro проверяет префикс токенов в ОДИН forward pass.
Префикс обрезается до первого ошибочного токена.

## Результаты

- DeepSeek V4 Pro + DSpark: +51-400% throughput
- Работает на Qwen и Gemma (не только DeepSeek)
- Open-source: HuggingFace + GitHub

## HuggingFace

https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro-DSpark
https://github.com/deepseek-ai/DeepSpec

## Вывод

DeepSeek остаётся основным инноватором GPT-архитектур.
Развитие не вышло на плато — кто так говорит, не читает научные работы.
