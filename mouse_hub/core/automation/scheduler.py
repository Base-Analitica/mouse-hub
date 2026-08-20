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
import time
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
        # Dois sinais independentes (regressão #18 — nunca mais
        # set()+clear() no mesmo Event):
        #  * `_stop`  — cancelamento definitivo (stop/reset);
        #  * `_notify` — acorda o aguardo para RECALCULAR com o novo
        #    intervalo quando `interval` muda no meio do sleep.
        self._stop = threading.Event()
        self._notify = threading.Event()
        # Versão monótona da configuração (lock protegido) — resolve a
        # race notificação-perdida: o setter nunca precisa limpar o
        # Event, e o aguardo decide recalcular comparando versões em
        # vez de confiar no estado do Event (clear() pode apagar um
        # sinal que chegou antes dele).
        self._lock = threading.Lock()
        self._version = 0

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f"Intervalo deve ser positivo: {value}")
        with self._lock:
            if value == self._interval:
                return  # sem mudança real, nada a notificar
            self._interval = value
            self._version += 1
        # Acorda o aguardo em andamento: o worker recalcula o tempo
        # restante com o novo intervalo e dorme de novo — sem travar
        # e sem cancelar a execução (regressão #18). O Event é
        # set-only: nunca é limpo pelo setter (limpar perderia a
        # notificação de quem acordou tarde — regressão #18).
        self._notify.set()

    def stop(self) -> None:
        """Cancela o aguardo em andamento e marca o scheduler como
        parado. Chamada do desligamento do engine; idempotente."""
        self._stop.set()
        self._notify.set()  # acorda quem dorme para ver o stop

    def reset(self) -> None:
        """Reutiliza o scheduler após stop (novo start)."""
        self._stop.clear()
        self._notify.clear()

    def wait_next(self) -> bool:
        """Dorme até o próximo tick. Retorna True se completou, False
        se foi interrompido (stop). Zero busy-wait."""
        if self._stop.is_set():
            return False
        with self._lock:
            interval = self._interval
            version = self._version
        deadline = time.monotonic() + interval
        while True:
            if self._stop.is_set():
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True  # o intervalo completou normalmente
            # Dorme até o fim do tick OU até o intervalo mudar
            # (_notify) — nunca gira esperando (Event.wait, não loop).
            self._notify.wait(remaining)
            with self._lock:
                if self._version != version:
                    # A configuração mudou durante o sono: recalcular
                    # deadline com o NOVO intervalo e continuar
                    # dormindo — a mudança de CPS é hot config,
                    # nunca cancelamento (regressão #18).
                    version = self._version
                    deadline = time.monotonic() + self._interval
