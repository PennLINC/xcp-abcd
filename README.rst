#########################################################
**XCP-D** : A Robust Postprocessing Pipeline of fMRI data
#########################################################

.. image:: https://img.shields.io/badge/Source%20Code-pennlinc%2Fxcp__d-purple
   :target: https://github.com/PennLINC/xcp_d
   :alt: GitHub Repository

.. image:: https://readthedocs.org/projects/xcp-d/badge/?version=latest
   :target: http://xcp-d.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation

.. image:: https://img.shields.io/badge/docker-pennlinc/xcp_d-brightgreen.svg?logo=docker&style=flat
   :target: https://hub.docker.com/r/pennlinc/xcp_d/tags/
   :alt: Docker

.. image:: https://circleci.com/gh/PennLINC/xcp_d.svg?style=svg
   :target: https://circleci.com/gh/PennLINC/xcp_d
   :alt: Test Status

.. image:: https://codecov.io/gh/PennLINC/xcp_d/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/PennLINC/xcp_d
   :alt: Codecov

.. image:: https://zenodo.org/badge/309485627.svg
   :target: https://zenodo.org/badge/latestdoi/309485627
   :alt: DOI

.. image:: https://img.shields.io/github/license/pennlinc/xcp_d
   :target: https://opensource.org/licenses/BSD-3-Clause
   :alt: License

This fMRI post-processing and noise regression pipeline is developed by the
`Satterthwaite lab at the University of Pennslyvania <https://www.satterthwaitelab.com/>`_
(**XCP**\; eXtensible Connectivity Pipeline)  and
`Developmental Cognition and Neuroimaging lab at the University of Minnesota
<https://innovation.umn.edu/developmental-cognition-and-neuroimaging-lab/>`_ (**-D**\CAN)
for open-source software distribution.


*****
About
*****

XCP-D paves the final section of the reproducible and scalable route from the MRI scanner to
functional connectivity data in the hands of neuroscientists.
We developed XCP-D to extend the BIDS and NiPrep apparatus to the point where data is most
commonly consumed and analyzed by neuroscientists studying functional connectivity.
Thus, with the development of XCP-D, data can be automatically preprocessed and analyzed in BIDS
format, using NiPrep-style containerized code, all the way from the scanner to functional
connectivity matrices.

XCP-D picks up right where `fMRIprep <https://fmriprep.org>`_ ends, directly consuming the outputs
of fMRIPrep.
XCP-D leverages the BIDS and NiPrep frameworks to automatically generate denoised BOLD images,
parcellated time series, functional connectivity matrices, and quality assessment reports.
XCP-D can also process outputs from: `NiBabies <https://nibabies.readthedocs.io>`_ and
`Minimally preprocessed HCP data <https://www.humanconnectome.org/study/hcp-lifespan-development/\
data-releases>`_.

*Please note that XCP is only compatible with HCP-YA versions downloaded c.a. Feb 2023 at the moment.*

.. image:: https://raw.githubusercontent.com/pennlinc/xcp_d/main/docs/_static/schematic_land-01.png

See the `documentation <https://xcp-d.readthedocs.io/en/latest/>`_ for more details.


Why you should use XCP-D
````````````````````````
XCP-D is designed for resting-state or pseudo-resting-state functional connectivity analyses.
XCP-D derivatives may be useful for seed-to-voxel and ROI-to-ROI functional connectivity analyses,
as well as decomposition-based methods, such as ICA or NMF.


When you should not use XCP-D
`````````````````````````````
XCP-D is not designed as a general-purpose postprocessing pipeline.
It is really only appropriate for certain analyses,
and other postprocessing/analysis tools are better suited for many types of data/analysis.

XCP-D derivatives are not particularly useful for task-dependent functional connectivity analyses,
such as psychophysiological interactions (PPIs) or beta series analyses.
It is also not suitable for general task-based analyses, such as standard task GLMs,
as we recommend included nuisance regressors in the GLM step,
rather than denoising data prior to the GLM.
