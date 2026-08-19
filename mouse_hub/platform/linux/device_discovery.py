"""Descoberta do Logitech G403 HERO no Linux por identidade de hardware.

Nunca assumimos que o mouse será `/dev/hidraw0`. A descoberta
percorre `/sys/class/hidraw/*/device` em busca de interfaces HID cujo
`uevent` contenha o VID/PID do G403 HERO (046d:c08f).

A seleção de endpoint é feita em DUAS etapas, porque identidade por
VID/PID no uevent é condição necessária mas não suficiente:

1. Identidade: o parser de `HID_ID` é defensivo — entradas malformadas
   são ignoradas, jamais lançam exceção.
2. Protocolo: cada candidato é sondado de verdade via feature IRoot
   (0x0000) do HID++ 2.0 — todos os comandos FAP são emitidos em
   LONG report 0x11 de 20 bytes, conforme o driver upstream do kernel
   ("FAP only uses HIDPP_LONG messages"). O device index 0xFF é o
   valor HID++ para o dispositivo conectado diretamente (G403 cabo USB,
   sem receiver). Sequência:

   a) IRoot.GetProtocolVersion (fn 1) confirma o protocolo HID++ 2.0
      (eco de header + ping echo em params[2]);
   b) IRoot.GetFeature(fn 0) com o FEATURE ID 0x2201 (Adjustable DPI)
      confirma a feature e descobre o feature index real — a única
      garantia de index da especificação é a de IRoot (index 0), o
      resto é sempre descoberto, nunca deduzido de Feature ID.

   Só o endpoint que passa nas duas etapas é elegível para escritas de
efeito.

Quando vários endpoints do mesmo G403 respondem ao protocolo, a
seleção é ambígua e o produto não decide por conta própria: nada é
escrito em endpoint incerto. A seleção também reporta a permissão do
acesso (device acessível vs inacessível) através de `Outcome` para que
quem usa distinga "device não confirmado" de "device existente mas sem
permissão (regra udev ausente)".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.core.operation import OperationStatus
from mouse_hub.platform.read_outcome import ReadOutcomeKind, ReadOutcome
from mouse_hub.platform.hidpp import (
    AckResultKind,
    DEVICE_INDEX_DIRECT,
    FAP_REPORT_LENGTH,
    FeatureId,
    matches_ack,
    matches_protocol_error,
    parse_protocol_error,
    RootFeature,
    SoftwareId,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice

SYS_HIDRAW_ROOT = Path("/sys/class/hidraw")


def parse_hid_id(line: str) -> Optional[tuple[int, int]]:
    """Extrai (vid, pid) de uma linha de uevent `HID_ID=<bus>:<vendor>:<product>`.

    Parsing defensivo por design: conteúdo malformado (dígitos inválidos,
    campos faltantes, prefixo ausente, linhas truncadas) retorna None
    em vez de lançar exceção. Entradas inválidas são ignoradas, nunca
    contaminam o resultado.
    """
    if not isinstance(line, str) or not line.startswith("HID_ID="):
        return None
    raw = line.split("=", 1)[-1].strip()
    parts = raw.split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[1], 16), int(parts[2], 16)
    except (ValueError, TypeError, OverflowError):
        return None


def read_uevent_identity(path: Path) -> Optional[tuple[int, int]]:
    """Lê a identidade (vid, pid) do uevent em `path`.

    Retorna None quando o arquivo não existe, não é legível ou seu
    conteúdo não é parseável — sem nunca lançar exceção.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        parsed = parse_hid_id(line)
        if parsed is not None:
            return parsed
    return None


def find_g403_hidraw_devices(
    vid: int = G403_VID, pid: int = G403_PID, sysfs_root: Path = SYS_HIDRAW_ROOT
) -> List[MouseDevice]:
    """Varre o sysfs procurando hidraw cuja identidade seja (vid, pid).

    Funciona sem privilegiar nenhum caminho fixo: cada interface hidraw
    é validada individualmente pelo próprio uevent. Retorna TODOS os
    candidatos — a seleção final é responsabilidade da camada superior,
    que deve validar o protocolo antes de qualquer escrita (ver
    `HydppEndpointSelection`).
    """
    devices: List[MouseDevice] = []
    if not sysfs_root.is_dir():
        return devices

    for entry in sorted(sysfs_root.iterdir()):
        uevent = entry / "device" / "uevent"
        if not uevent.exists():
            continue

        identity = read_uevent_identity(uevent)
        if identity is None:
            continue
        if identity != (vid, pid):
            continue

        name = ""
        try:
            text = uevent.read_text()
            for line in text.splitlines():
                if line.startswith("HID_NAME="):
                    name = line.split("=", 1)[-1].strip()
                    break
        except OSError:
            pass

        devices.append(MouseDevice(
            hidraw_path=f"/dev/{entry.name}",
            vid=vid,
            pid=pid,
            name=name or "",
        ))

    return devices


def _read_outcome_status(outcome) -> OperationStatus:
    """ReadOutcome de transporte → OperationStatus equivalente, sem
    colapsar causas (timeout não chega aqui)."""
    mapping = {
        ReadOutcomeKind.DEVICE_NOT_FOUND: OperationStatus.DEVICE_NOT_FOUND,
        ReadOutcomeKind.PERMISSION_DENIED: OperationStatus.PERMISSION_DENIED,
        ReadOutcomeKind.FAILED: OperationStatus.FAILED,
    }
    status = mapping.get(outcome.kind)
    return status if status is not None else OperationStatus.FAILED


def discover_g403(
    vid: int = G403_VID, pid: int = G403_PID, sysfs_root: Path = SYS_HIDRAW_ROOT
) -> Optional[MouseDevice]:
    """Retorna o primeiro G403 encontrado pela identidade, ou None.

    ATENÇÃO: esta função confirma apenas identidade por VID/PID. O
    endpoint retornado ainda precisa passar pela validação de protocolo
    (HydppEndpointSelection.select) antes de receber qualquer comando de
    efeito.
    """
    devices = find_g403_hidraw_devices(vid, pid, sysfs_root)
    return devices[0] if devices else None


@dataclass(frozen=True)
class ProbeOutcome:
    """Resultado do probe de protocolo de um candidato.

    * valid=True e feature_index != None → endpoint confirma IRoot e a
      feature Adjustable DPI (0x2201), com o feature index descoberto
      dinamicamente;
    * valid=True e feature_index == None → endpoint confirma IRoot mas
      NÃO suporta 0x2201 (dpi indisponível neste dispositivo);
    * valid=False → endpoint não validável ou rejeitado pelo protocolo.

    `access_status` PRESERVA A CAUSA REAL do acesso (nunca colapsa
    DEVICE_NOT_FOUND e PERMISSION_DENIED em um único accessible=False):
    * None            → probe não precisou abrir (sem hidraw) ou falha
                        antes do open;
    * OK              → descritor aberto com sucesso;
    * PERMISSION_DENIED → open recusado (regra udev);
    * DEVICE_NOT_FOUND  → device sumiu entre a descoberta e o probe
                          (hot-unplug);
    * FAILED          → open falhou por outra causa (fd indisponível).
    `accessible` continua disponível como propriedade derivada (True
    apenas quando o acesso foi de fato OK) para compatibilidade com quem
    lê o outcome sem distinguir a causa.
    """

    valid: bool
    feature_index: Optional[int] = None
    access_status: Optional[OperationStatus] = None
    # Código de erro FAP quando o probe terminou em PROTOCOL_ERROR
    # (para o reason do caller); None nos demais casos.
    error_code: Optional[int] = None

    # Compatibilidade: True apenas quando o acesso foi realmente OK —
    # PERMISSION_DENIED/DEVICE_NOT_FOUND/FAILED NÃO viram True.
    @property
    def accessible(self) -> Optional[bool]:
        if self.access_status is None:
            return None
        return self.access_status == OperationStatus.APPLIED


class HydppEndpointSelection:
    """Segunda etapa da descoberta: confirma qual candidato realmente
    suporta o protocolo HID++ 2.0.

    Envolve o `HidAccess` (abre, sonda com IRoot em FAP LONG e fecha)
    para decidir entre os candidatos. A seleção é
    fail closed: se nenhum candidato responder, se um responder com
    erro, ou se mais de um responder sem como decidir com segurança, a
    seleção falha e nenhum endpoint é retornado — nada é escrito em
    endpoint incerto.
    """

    def __init__(self, hid: HidAccess) -> None:
        self._hid = hid

    @staticmethod
    def _read_typed(hid: HidAccess, request_key, timeout: float):
        """Lê respostas até encontrar uma classificável como ACK, erro
        correlacionado, causa real de acesso ou esgotar o tempo —
        reports que não casam com o request (noise) são descartados
        sem efeito.

        O read é contrato tipado (ReadOutcome): o timeout real do select
        continua TIMEOUT (endpoint mudo); a causa REAL de transporte
        (DEVICE_NOT_FOUND/PERMISSION_DENIED/FAILED) é devolvida na hora
        — o caller NUNCA trata hot-unplug como mudez."""
        import time
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return AckResultKind.TIMEOUT, None, None
            outcome = hid.read(FAP_REPORT_LENGTH, timeout=min(0.5, remaining))
            if outcome.is_timeout():
                continue
            if outcome.is_transport_failure():
                # Causa REAL de acesso (fd sem dado: device sumiu, sem
                # permissão ou transporte quebrado) — o probe não pode
                # classificar como mudez: quem consome o outcome deve
                # propagar a causa.
                return (AckResultKind.TRANSPORT_FAILURE,
                        None, outcome)
            if outcome.data is None:
                continue
            raw = outcome.data
            if matches_ack(raw, request_key):
                return AckResultKind.ACK, raw, None
            if matches_protocol_error(raw, request_key):
                return AckResultKind.PROTOCOL_ERROR, raw, parse_protocol_error(raw)
            # Report que não pertence ao request = noise: descartar e
            # continuar tentando.

    def _probe_one(self, device: MouseDevice) -> ProbeOutcome:
        """Probe de protocolo completo em duas etapas, conforme o
        driver upstream e a especificação HID++ 2.0:

        1. IRoot.GetProtocolVersion (fn 1) em FAP LONG — confirma que o
           endpoint responde ao protocolo (ACK correlacionado, eco do
           ping).
        2. IRoot.GetFeature(0x2201 — Adjustable DPI): confirma a
           presença da feature e descobre o feature index real que o
           dispositivo usará para endereçar a feature.

        Nenhum index é deduzido de Feature ID: a única garantia da
        especificação é IRoot no index 0; todo o resto é descoberto.
        Abre o descritor temporariamente e o fecha em qualquer caminho
        (inclusive exceção). Nenhum estado fica para trás.
        """
        opened = False
        try:
            open_result = self._hid.open(device)
            if not open_result.status.ok:
                # open rejeitado (permissão negada, device ausente ou
                # falha genérica) = endpoint não validável; a causa REAL
                # é preservada no outcome (quem usa NUNCA colapsa
                # permission denied com device ausente).
                return ProbeOutcome(
                    valid=False, access_status=open_result.status
                )
            opened = True

            root = RootFeature(DEVICE_INDEX_DIRECT, SoftwareId.MOUSE_HUB)

            # Etapa 1: GetProtocolVersion confirma HID++ 2.0.
            request = root.protocol_version_request()
            write_result = self._hid.write(request)
            if not write_result.status.ok:
                # A causa REAL do write é preservada no outcome:
                # write em device sem /dev/hidraw → DEVICE_NOT_FOUND
                # (hot-unplug durante o probe); write no descritor sem
                # permissão → PERMISSION_DENIED; demais falhas → FAILED.
                # NUNCA colapsar em FAILED genérico.
                return ProbeOutcome(
                    valid=False, access_status=write_result.status,
                )
            kind, response, error_or_outcome = self._read_typed(
                self._hid, root.protocol_version_request_key(), 0.5,
            )
            if kind == AckResultKind.TRANSPORT_FAILURE:
                # Falha REAL de acesso no read (device sumiu, permissão
                # perdida, transporte quebrado) — a causa é preservada
                # no outcome, nunca colapsada em mudez.
                return ProbeOutcome(
                    valid=False, access_status=_read_outcome_status(
                        error_or_outcome
                    ) if error_or_outcome is not None else
                    OperationStatus.FAILED,
                )
            if kind != AckResultKind.ACK:
                # Device mudo (TIMEOUT) ou rejeitou o ping
                # (PROTOCOL_ERROR): endpoint não validável.
                return ProbeOutcome(valid=False, access_status=OperationStatus.APPLIED)
            # Validação REAL do GetProtocolVersion: major in (0x02,
            # 0x04) e ping_echo == ping enviado (0x5A). Major 0x8F
            # (HID++ 1.0), valor desconhecido ou ping incorreto não
            # confirmam HID++ 2.0.
            if not root.is_protocol_version_confirmed(response):
                return ProbeOutcome(valid=False, access_status=OperationStatus.APPLIED)

            # Etapa 2: IRoot.GetFeature(0x2201) — presença de DPI.
            request = root.get_feature_request(FeatureId.ADJUSTABLE_DPI)
            write_result = self._hid.write(request)
            if not write_result.status.ok:
                # Idem etapa 1: a causa real do write preserva o
                # reason para quem consome o outcome.
                return ProbeOutcome(
                    valid=False, access_status=write_result.status,
                )
            kind, response, error_or_outcome = self._read_typed(
                self._hid, root.get_feature_request_key(), 0.5,
            )
            if kind == AckResultKind.TRANSPORT_FAILURE:
                # Idem etapa 1: causa real de acesso no read, preservada
                # no outcome.
                return ProbeOutcome(
                    valid=False, access_status=_read_outcome_status(
                        error_or_outcome
                    ) if error_or_outcome is not None else
                    OperationStatus.FAILED,
                )
            if kind == AckResultKind.TIMEOUT:
                return ProbeOutcome(valid=False, access_status=OperationStatus.APPLIED)
            if kind == AckResultKind.PROTOCOL_ERROR:
                # QUALQUER erro FAP correlacionado (incluindo 0x09
                # UNSUPPORTED) é rejeição de comando, NÃO ausência
                # documentada: quem usa deve falhar fechado. A
                # especificação pública IRoot/GetFeature define
                # ausência da feature APENAS via resposta válida com
                # feature_index == 0 — não há fonte primária que
                # trate PROTOCOL_ERROR 0x09 neste comando como
                # "feature ausente". O error code real é preservado
                # no reason para diagnóstico.
                return ProbeOutcome(
                    valid=False, access_status=OperationStatus.APPLIED,
                    error_code=int(error_or_outcome)
                    if isinstance(error_or_outcome, int) else None,
                )
            parsed = root.parse_get_feature_response(response)
            if parsed is None:
                return ProbeOutcome(valid=False, access_status=OperationStatus.APPLIED)
            feature_index, _flags, _version = parsed
            if feature_index == 0xFF:
                # Resposta com feature index 0xFF não é um GetFeature
                # legítimo — endpoint não validável.
                return ProbeOutcome(valid=False, access_status=OperationStatus.APPLIED)
            # index 0 = feature não suportada (endpoint HID++ válido,
            # sem Adjustable DPI) — a única forma DOCUMENTADA de
            # ausência da feature (IRoot.GetFeature response válida).
            return ProbeOutcome(
                valid=True,
                feature_index=feature_index if feature_index != 0 else None,
                access_status=OperationStatus.APPLIED,
            )
        except Exception:
            # Exceção de acesso (descritor sumiu, sysfs instável) é
            # "endpoint não validável" — nunca vira seleção nem vaza.
            return ProbeOutcome(valid=False, access_status=OperationStatus.FAILED)
        finally:
            if opened:
                self._hid.close()

    def probe(
        self, candidates: List[MouseDevice]
    ) -> List[ProbeOutcome]:
        """Probeia todos os candidatos e retorna o resultado de cada um
        (na mesma ordem). O probe sempre fecha o descritor: nada fica
        aberto."""
        return [self._probe_one(candidate) for candidate in candidates]

    def select(
        self, candidates: List[MouseDevice]
    ) -> Optional[MouseDevice]:
        """Seleciona o endpoint confirmado pelo protocolo.

        Regras (fail closed):
        * nenhum candidato valida → None;
        * exatamente um valida → esse;
        * mais de um valida sem critério seguro de desempate → None.
        """
        if not candidates:
            return None
        outcomes = self.probe(candidates)
        validated = [
            device
            for device, outcome in zip(candidates, outcomes)
            if outcome.valid and outcome.feature_index is not None
        ]
        if len(validated) == 1:
            return validated[0]
        # 0 validados ou ambiguidade: falhar fechado.
        return None


# Compatibilidade: quem usava os nomes antigos ainda resolve.
discover = discover_g403
