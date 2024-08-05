# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et
"""Nipype workflows for xcp_d."""

from xcp_d.workflows import anatomical, base, bold, execsummary, parcellation, plotting

__all__ = [
    "anatomical",
    "base",
    "bold",
    "execsummary",
    "parcellation",
    "plotting",
]
