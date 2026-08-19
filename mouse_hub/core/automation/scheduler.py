"""Scheduler de timing das automações — aguardo eficiente e cancelável.

Regra do hot path: NUNCA girar um loop até um timestamp. O aguardo
entre eventos é feito com `threading.Event.wait(timeout)`, que
dorme sem consumir CPU e pode ser acordado imediatamente para
cancelamento ou para ajuste de intervalo (mudança de CPS ou de
botão).

Uma única instância de scheduler alimenta o engine inteiro: mudar
CPS atualiza `interval` e o próximo aguardo já usa o novo valor,
sem recriar threads ou workers.
"""

from __future__ import annotations

import threading
from typing import Optional


class AutomationScheduler:
    """Aguardo entre eventos com cancelamento imediato.

    Uso típico no loop do worker:

        while engine.running:
            engine.work()
            if not scheduler.wait_next():
                break   # foi cancelado

    `wait_next()` retorna True se o intervalo completou normalmente e
    False se foi interrompido (stop). Não há busy-wait: o dorme é
    sempre `Event.wait`, e o ajuste de intervalo a meio do caminho
    simplesmente redefine o timeout na próxima iteração.
    """

    def __init__(self, interval: float) -> None:
        if interval <= 0:
            raise ValueError(f"Intervalo deve ser positivo: {interval}")
        self._interval = interval
        self._stop = threading.Event()

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f"Intervalo deve ser positivo: {value}")
        self._interval = value
        # O aguardo em andamento usa o novo intervalo na próxima
        # chamada; para efeito imediato, interrompe o aguardo atual.
        self._stop.set()
        self._stop.clear()

    def stop(self) -> None:
        """Cancela o aguardo em andamento e marca o scheduler como
        parado. Chamada do desligamento do engine; idempotente."""
        self._stop.set()

    def reset(self) -> None:
        """Reutiliza o scheduler após stop (novo start)."""
        self._stop.clear()

    def wait_next(self) -> bool:
        """Dorme até o próximo tick. Retorna True se completou, False
        se foi interrompido. Zero busy-wait."""
        if self._stop.is_set():
            return False
        completed = self._stop.wait(self._interval)
        return not completed
