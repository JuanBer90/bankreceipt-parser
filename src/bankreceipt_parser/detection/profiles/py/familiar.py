"""Banco Familiar transfer receipt profiles."""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.text import TextSignal

FAMILIAR_TRANSFER_LOADED = IssuerProfile(
    issuer="familiar",
    variant="transfer_loaded",
    establish_issuer=True,
    min_score=2.2,
    signals=(
        TextSignal(
            signal_id="transfer_loaded_success",
            phrases=("transferencia", "cargada", "exito"),
            weight=1.0,
            match_all=True,
        ),
        TextSignal(
            signal_id="monto_a_enviar",
            phrases=("monto", "enviar"),
            weight=0.7,
            match_all=True,
        ),
        TextSignal(
            signal_id="enviado_por_label",
            phrases=("enviado", "por"),
            weight=0.7,
            match_all=True,
        ),
    ),
)

FAMILIAR_TRANSFER_CONFIRMED = IssuerProfile(
    issuer="familiar",
    variant="transfer_confirmed",
    establish_issuer=True,
    min_score=2.5,
    signals=(
        TextSignal(
            signal_id="transfer_other_entities",
            phrases=("transferencia", "otras", "entidades"),
            weight=1.0,
            match_all=True,
        ),
        TextSignal(
            signal_id="confirmed_title",
            phrases=("confirmada",),
            weight=0.7,
        ),
        TextSignal(
            signal_id="familiar_a_toda_hora",
            phrases=("familiar", "toda", "hora"),
            weight=0.8,
            match_all=True,
        ),
        TextSignal(
            signal_id="cliente_pagador",
            phrases=("cliente", "pagador"),
            weight=0.7,
            match_all=True,
        ),
    ),
)

ALL_FAMILIAR_PROFILES: tuple[IssuerProfile, ...] = (
    FAMILIAR_TRANSFER_LOADED,
    FAMILIAR_TRANSFER_CONFIRMED,
)
