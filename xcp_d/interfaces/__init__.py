# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Initialize interfaces."""
from xcp_d.interfaces.connectivity import (
    ApplyTransformsx,
    NiftiConnect,
    ConnectPlot,
    get_atlas_cifti,
    get_atlas_nifti,
)
from xcp_d.interfaces.filtering import FilteringData
from xcp_d.interfaces.layout_builder import LayoutBuilder
from xcp_d.interfaces.prepostcleaning import CensorScrub, RemoveTR, Interpolate
from xcp_d.interfaces.qc_plot import QCPlot
from xcp_d.interfaces.regression import CiftiDespike, regress
from xcp_d.interfaces.report import AboutSummary, FunctionalSummary, SubjectSummary
from xcp_d.interfaces.report_core import generate_reports
from xcp_d.interfaces.resting_state import brainplot, computealff, surfaceReho
from xcp_d.interfaces.surfplotting import (
    BrainPlotx,
    PlotImage,
    PlotSVGData,
    RegPlot,
    RibbontoStatmap,
    SurftoVolume,
)

__all__ = [
    'regress', 'FilteringData', 'NiftiConnect',
    'computealff', 'surfaceReho', 'get_atlas_cifti', 'get_atlas_nifti',
    'ApplyTransformsx', 'Interpolate', 'CensorScrub', 'RemoveTR',
    'QCPlot', 'SubjectSummary', 'AboutSummary', 'FunctionalSummary',
    'generate_reports', 'CiftiDespike', 'ConnectPlot', 'brainplot',
    'SurftoVolume', 'BrainPlotx', 'PlotSVGData', 'RegPlot', 'PlotImage',
    'LayoutBuilder', 'RibbontoStatmap'
]
