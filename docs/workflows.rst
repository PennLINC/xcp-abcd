
.. include:: links.rst

###########################
Processing Pipeline Details
###########################


**********
Input data
**********

*XCP-D* can post-process data from several different preprocessing pipelines,
including ``fMRIPrep`` (``--input-type fmriprep``), ``Nibabies`` (``--input-type nibabies``),
``HCPPipelines`` (``--input-type hcp``), ``abcd-hcp-pipeline`` (``--input-type dcan``),
and UK Biobank's pipeline (``--input-type ukb``).

The default input type depends on the mode that *XCP-D* is run in-
``fmriprep`` for ``abcd`` and ``linc`` modes, ``nibabies`` for ``hbcd`` mode.

*XCP-D*'s support for fMRIPrep and Nibabies derivatives will be the most robust,
as these pipelines produces BIDS-compliant derivatives.
For the HCP, ABCD-HCP, and UK Biobank pipelines,
*XCP-D* will read in the post-processed data and convert it to a BIDS-like structure.


****************
Processing Modes
****************

Starting in version 0.8.0, *XCP-D* includes a required ``--mode`` parameter.
The ``mode`` parameter automatically defines sets of other parameters,
based on recommended processing pipelines for different studies.

*XCP-D* can be run in one of four modes: ``linc``, ``abcd``, ``hbcd``, or ``nichart``.
Each mode is designed by a different group, and has different requirements.

Users may also run *XCP-D* in ``none`` mode, in which case almost all of the parameters must be
defined by the user.

.. important::

   If you have a "mode" you would like to see supported by *XCP-D*, follow the instructions in
   :ref:`contrib_modes`.


linc Mode
=========

The ``linc`` mode is designed by the `PennLINC`_ lab.

In this mode, *XCP-D* will generate PennLINC-preferred outputs,
such as the NiPreps-format HTML report and the LINC QC file.

All denoised BOLD data, including dense time series, parcellated time series,
and correlation matrices, will be censored.

Defaults
--------

By default, the ``linc`` mode will apply the following parameters,
which may be overridden by the user:

-  ``--file-format cifti``: CIFTI files are used as input.
-  ``--despike``: Despiking is enabled by default.
-  ``--fd-thresh 0``: Censoring is disabled by default.
-  ``--input-type fmriprep``: fMRIPrep outputs are expected as input.
-  ``--linc-qc``: The LINC QC file will be created by default.
-  ``--min-coverage 0.5``: The default coverage threshold is 0.5.
-  ``--smoothing 6``: Smoothing is enabled by default.

Optional Parameters
-------------------

-  ``--abcc-qc``: By default, *XCP-D* will not create the DCAN executive summary or QC file when run
   in the ``linc`` mode.
   If you would like to create these files, you must include the ``--abcc-qc`` flag.
-  ``--combine-runs``: By default, *XCP-D* will not combine runs when run in the ``linc`` mode.
   If you would like to combine runs, you must include the ``--combine-runs`` flag.
-  ``--warp-surfaces-native2std``: By default, *XCP-D* will not warp surfaces to standard space when
   run in the ``linc`` mode.
   If you would like to warp surfaces, you must include the ``--warp-surfaces-native2std`` flag.

Prohibited Parameters
---------------------

-  ``--create-matrices``: This option is not allowed in the ``linc`` mode.
   Instead, correlation matrices will be created from the full (censored) time series,
   which is equivalent to running ``--create-matrices all``.


abcd Mode
=========

The ``abcd`` mode is designed by the `DCAN`_ lab for processing data from the `ABCD`_ study.

In this mode, *XCP-D* will generate DCAN-preferred outputs,
such as the executive summary and the DCAN QC file.

Denoised BOLD data, including dense time series and parcellated time series, will be interpolated.
Correlation matrices can be created optionally from the censored data.

.. important::

   Currently, ``abcd`` mode is identical to ``hbcd`` mode, except for the expected preprocessing
   pipeline.

Defaults
--------

By default, the ``abcd`` mode will apply the following parameters,
which may be overridden by the user:

-  ``--file-format cifti``: CIFTI files are used as input.
-  ``--despike``: Despiking is enabled by default.
-  ``--fd-thresh 0.3``: The censoring threshold is set to 0.3 mm by default.
-  ``--input-type fmriprep``: fMRIPrep outputs are expected as input.
-  ``--combine-runs``: Runs will be concatenated by default.
-  ``--warp-surfaces-native2std``: Surfaces will be warped to standard space by default.
-  ``--linc-qc``: The LINC QC file will be created by default.
-  ``--min-coverage 0.5``: The default coverage threshold is 0.5.
-  ``--smoothing 6``: Smoothing is enabled by default.

Required Parameters
-------------------

In ``abcd`` mode, the following parameters are required:

-  ``--motion-filter-type``: The filter to apply to the motion parameters.
   If this is set to a value other than "none", then the following parameters are also required.

   -  ``--band-stop-min``: Required if ``--motion-filter-type`` is "bandstop" or "lp".
   -  ``--band-stop-max``: Required if ``--motion-filter-type`` is "bandstop".
   -  ``--motion-filter-order``: Required if ``--motion-filter-type`` is "bandstop" or "lp".

Optional Parameters
-------------------

-  ``--create-matrices``: By default, *XCP-D* will not create correlation matrices when run in the ``abcd`` mode.
   If you would like to create correlation matrices, you must include the ``--create-matrices`` flag.
   The ``--create-matrices`` parameter accepts lengths of time to use for the correlation matrices,
   as well as the special value "all", which uses all of the low-motion data from the run.


hbcd Mode
=========

The ``hbcd`` mode is designed by the `DCAN`_ lab for processing data from the `HBCD`_ study.

In this mode, *XCP-D* will generate DCAN-preferred outputs,
such as the executive summary and the DCAN QC file.

Denoised BOLD data, including dense time series and parcellated time series, will be interpolated.
Correlation matrices can be created optionally from the censored data.

.. important::

   Currently, ``hbcd`` mode is identical to ``abcd`` mode, except for the expected preprocessing
   pipeline.

Defaults
--------

By default, the ``hbcd`` mode will apply the following parameters,
which may be overridden by the user:

-  ``--file-format cifti``: CIFTI files are used as input.
-  ``--despike``: Despiking is enabled by default.
-  ``--fd-thresh 0.3``: The censoring threshold is set to 0.3 mm by default.
-  ``--input-type nibabies``: Nibabies outputs are expected as input.
-  ``--combine-runs``: Runs will be concatenated by default.
-  ``--warp-surfaces-native2std``: Surfaces will be warped to standard space by default.
-  ``--linc-qc``: The LINC QC file will be created by default.
-  ``--min-coverage 0.5``: The default coverage threshold is 0.5.
-  ``--smoothing 6``: Smoothing is enabled by default.

Required Parameters
-------------------

In ``hbcd`` mode, the following parameters are required:

-  ``--motion-filter-type``: The filter to apply to the motion parameters.
   If this is set to a value other than "none", then the following parameters are also required.

   -  ``--band-stop-min``: Required if ``--motion-filter-type`` is "bandstop" or "lp".
   -  ``--band-stop-max``: Required if ``--motion-filter-type`` is "bandstop".
   -  ``--motion-filter-order``: Required if ``--motion-filter-type`` is "bandstop" or "lp".

Optional Parameters
-------------------

-  ``--create-matrices``: By default, *XCP-D* will not create correlation matrices when run in the ``hbcd`` mode.
   If you would like to create correlation matrices, you must include the ``--create-matrices`` flag.
   The ``--create-matrices`` parameter accepts lengths of time to use for the correlation matrices,
   as well as the special value "all", which uses all of the low-motion data from the run.


nichart Mode
============

The ``nichart`` mode is used by the `NiChart project <https://neuroimagingchart.com/>`_.

This mode is very similar to ``linc`` mode, with the exception that it processes NIfTI files
by default and has smoothing disabled.

Defaults
--------

By default, the ``nichart`` mode will apply the following parameters,
which may be overridden by the user:

-  ``--file-format nifti``: NIfTI files are used as input.
-  ``--despike``: Despiking is enabled by default.
-  ``--fd-thresh 0``: Motion-based censoring is disabled by default.
-  ``--input-type fmriprep``: fMRIPrep outputs are expected as input.
-  ``--linc-qc``: The LINC QC file will be created by default.
-  ``--min-coverage 0.4``: The default coverage threshold is 0.4 instead of the more common 0.5.
-  ``--output-type censored``: Censored data are the primary output.
-  ``--smoothing 0``: Smoothing is disabled by default.


Major Differences Between Modes
===============================

Interpolated vs. Censored Time Series
-------------------------------------

The ``abcd`` and ``hbcd`` modes output denoised BOLD data and parcellated time series with
interpolated volumes.
The ``linc`` mode outputs denoised BOLD data and parcellated time series with censored volumes
instead.

The benefit to writing out interpolated data is that the outputs retain the temporal structure of
the original data.
This may make it easier to use the post-processed BOLD data in conjunction with other data acquired
at the same time, such as physiological recordings or task regressors.
Additionally, some tools, such as `biceps <https://biceps-cmdln.readthedocs.io/en/latest/>`_,
are designed to perform additional post-processing, such as additional censoring and parcellation,
on interpolated data.

The risk to working with interpolated data is that the interpolated volumes should not be used for
actual analyses, as the values do not reflect real data.
Thus, with the ``abcd`` and ``hbcd`` modes, it is imperative that users understand that additional
steps must be taken before using the interpolated data for analyses.

The benefit to writing out censored data is that the outputs are more directly usable for analyses,
and there is less of a chance that users will accidentally use interpolated data in their analyses.

In this sense, the ``abcd`` and ``hbcd`` modes are designed to be used with additional tools,
such as ``biceps``, or with additional steps taken by the user to ensure that the interpolated data
are re-censored appropriately before being used in analyses.
Conversely, the ``linc`` mode is designed to output data that is directly usable for analyses,
at the cost of losing the temporal structure of the original data and making it harder to pass the
data along to other tools that require the original temporal structure.

Correlation Matrices From Matching Lengths
------------------------------------------

The ``abcd`` and ``hbcd`` modes allow the ``--create-matrices`` parameter,
which will create correlation matrices from subsampled data,
while ``linc`` mode does not allow this parameter.

This parameter exists because motion (and thus censoring) can exhibit a non-linear relationship
with functional connectivity estimates.
By randomly selecting a subset of volumes from each run before calculating correlations,
the user can ensure that every run has the same number of data points contributing to its
functional connectivity estimate, which may ameliorate the effect of motion on the estimates.
This is the DCAN lab's recommended approach.

Conversely, the LINC lab does not recommend doing this,
as it removes meaningful data that may contribute to the functional connectivity estimates.
Instead, the LINC lab recommends accounting for the number of volumes in group-level models,
or using other methods, such as xDF :footcite:p:`afyouni2019effective`,
to account for the effect of motion on functional connectivity estimates (or their variance).


****************
Processing Steps
****************

See :ref:`usage_inputs` for information on input dataset structures.


Anatomical processing
=====================
:func:`~xcp_d.workflows.anatomical.volume.init_postprocess_anat_wf`

*XCP-D* performs minimal postprocessing on anatomical derivatives from the preprocessing pipeline.
This includes applying existing transforms to preprocessed T1w and T2w volumes,
in order to warp them from native T1w space to the target standard space,
while retaining the original resolution.


Surface normalization
---------------------
:func:`~xcp_d.workflows.anatomical.surface.init_warp_surfaces_to_template_wf`

If the ``--warp-surfaces-native2std`` flag is used,
then fsnative surface files from the preprocessing derivatives will be warped to fsLR-32k space.


Identification of high-motion outlier volumes
=============================================
:func:`~xcp_d.workflows.bold.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.GenerateConfounds`

*XCP-D* uses framewise displacement to identify high-motion outlier volumes.
These outlier volumes are removed from the BOLD data prior to denoising.

The threshold used to identify outlier volumes can be set with the ``--fd-thresh`` parameter.

.. important::
   If a BOLD run does not have enough low-motion data, then the post-processing workflow
   will automatically stop early, and no derivatives for that run will be written out.


Motion parameter filtering [OPTIONAL]
-------------------------------------
:func:`~xcp_d.workflows.bold.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.GenerateConfounds`,
:func:`~xcp_d.utils.confounds.load_motion`

Motion parameters may be contaminated with respiratory effects.:footcite:p:`power2019distinctions`
In order to address this issue, *XCP-D* optionally allows users to specify a band-stop or low-pass
filter to remove respiration-related signals from the motion parameters, prior to framewise
displacement calculation.
Please refer to :footcite:t:`fair2020correction` and :footcite:t:`gratton2020removal` for
more information.

.. important::
   Starting in version 0.4.0, if users request motion parameter filtering,
   filtered motion parameters (including FD, and any squared or derivative regressors)
   will be used for both outlier detection and confound regression.

   Before that release, filtered motion parameters were only used for outlier detection.

The two options for the motion-filtering parameter are "notch" (the band-stop filter) and
"lp" (the low-pass filter).

The cutoff points for either the notch filter
(the beginning and end of the frequency band to remove)
or the low-pass filter (the highest frequency to retain) can be set by the user
(see :ref:`usage_cli`), and may depend on the age of the participant.

Below are some recommendations for cutoff values when using the notch filter.

.. list-table:: Respiratory Filter

   *  - Age Range
      - Cutoff Range
        (Breaths per Minute)
   *  - < 1 year
      - 30 to  60
   *  - 1 to 2 years
      - 25 - 50
   *  - 2 - 6 years
      - 20 - 35
   *  - 6-12 years
      - 15 - 25
   *  - 12 - 18 years
      - 12 - 20
   *  - 19 - 65 years
      - 12 - 18
   *  - 65 - 80 years
      - 12 - 28
   *  - > 80 years
      - 10 - 30

If using the low-pass filter for single-band data, a recommended cutoff is 6 BPM (i.e., 0.1 Hertz),
per :footcite:t:`gratton2020removal`.


Framewise displacement calculation and thresholding
---------------------------------------------------
:func:`~xcp_d.workflows.bold.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.GenerateConfounds`,
:func:`~xcp_d.utils.modified_data.compute_fd`

Framewise displacement is then calculated according to the formula from :footcite:t:`power_fd_dvars`.
Two parameters that impact FD calculation and thresholding are
(1) the head radius used to convert rotation degrees to millimeters and
(2) the framewise displacement threshold.
The former may be set with the ``--head-radius`` parameter, which also has an "auto" option,
in which a brain mask from the preprocessing derivatives is loaded and
(treating the brain as a sphere) the radius is directly calculated
(see :func:`~xcp_d.utils.utils.estimate_brain_radius`).
The latter is set with the ``--fd-thresh`` parameter.

In this step, volumes with a framewise displacement value over the ``--fd-thresh`` parameter will
be flagged as "high motion outliers".
These volumes will later be removed from the denoised data.


Confound regressor selection
============================
:func:`~xcp_d.workflows.bold.postprocessing.init_prepare_confounds_wf`,
:func:`~xcp_d.interfaces.censoring.GenerateConfounds`

*XCP-D* supports several different confound regressor strategies.
In addition to the built-in regressor sets described below,
users may design their own confound configuration files and use those instead.
The default confound regressor set depends on the mode in which *XCP-D* is run-
this corresponds to ``--nuisance-regressors auto``.

If you want to skip the denoising step completely, you can use ``--nuisance-regressors none``.

.. important::
   Starting in version 0.4.0, if users request motion parameter filtering,
   filtered motion parameters (including FD, and any squared or derivative regressors)
   will be used for both outlier detection and confound regression.

   Before that release, filtered motion parameters were only used for outlier detection.

.. list-table:: Confound

   *  - Pipelines
      - Six Motion Estimates
      - White Matter
      - CSF
      - Global Signal
      - ACompCor
      - AROMA
   *  - 24P
      - X, X\ :sup:`2`, dX, dX\ :sup:`2`
      -
      -
      -
      -
      -
   *  - 27P
      - X, X\ :sup:`2`, dX, dX\ :sup:`2`
      - X
      - X
      - X
      -
      -
   *  - 36P
      - X, X\ :sup:`2`, dX, dX\ :sup:`2`
      - X, X\ :sup:`2`, dX, dX\ :sup:`2`
      - X, X\ :sup:`2`, dX, dX\ :sup:`2`
      - X, X\ :sup:`2`, dX, dX\ :sup:`2`
      -
      -
   *  - acompcor
      - X, dX
      -
      -
      -
      - 5 WM, 5 CSF
      -
   *  - acompcor_gsr
      -  X, dX
      -
      -
      - X
      - 5 WM, 5 CSF
      -
   *  - aroma
      - X, dX
      - X
      - X
      -
      -
      - X
   *  - aroma_gsr
      - X, dX
      - X
      - X
      - X
      -
      - X
   *  - gsr_only
      -
      -
      -
      - X
      -
      -
   *  - none
      -
      -
      -
      -
      -
      -

For more information about the built-in confound regressor sets,
please refer to :footcite:t:`benchmarkp`.

.. warning::

   In *XCP-D* versions prior to 0.3.1, the selected AROMA confounds were incorrect.
   We strongly advise users of these versions not to use the ``aroma`` or ``aroma_gsr``
   options.


.. list-table:: Preprocessing Pipeline Support

   *  - Nuisance Strategy
      - 24P
      - 27P
      - 36P
      - acompcor
      - acompcor_gsr
      - aroma
      - aroma_gsr
      - gsr_only
      - none
   *  - fMRIPrep (>=23.1.0)
      - X
      - X
      - X
      - X
      - X
      -
      -
      - X
      - X
   *  - fMRIPrep (<23.1.0)
      - X
      - X
      - X
      - X
      - X
      - X
      - X
      - X
      - X
   *  - Nibabies
      - X
      - X
      - X
      - X
      - X
      -
      -
      - X
      - X
   *  - ABCD-BIDS (DCAN)
      - X
      - X
      - X
      -
      -
      -
      -
      - X
      - X
   *  - HCP-YA
      - X
      - X
      - X
      -
      -
      -
      -
      - X
      - X
   *  - UK Biobank
      - X
      -
      -
      -
      -
      -
      -
      - X
      - X

.. important::
   fMRIPrep removed AROMA support in 23.1.0.
   In order to use the ``aroma`` or ``aroma_gsr`` strategies,
   please run ``fMRIPost-AROMA`` on your fMRIPrep outputs before running *XCP-D*.
   You will need to supply the AROMA derivatives dataset to *XCP-D* via the ``--datasets``
   parameter (i.e., ``--datasets aroma=/path/to/fmripost-aroma/dset``).


.. warning::
   The strategy ``gsr_only`` is only appropriate for UK Biobank data,
   as those data have already been denoised with FSL FIX.


.. _confound_config:

The confound configuration file format
--------------------------------------

Users may design and employ their own custom confound configuration YAML files.
These files are designed to allow inputs from multiple datasets,
with flexible column and file selection.

Each confound configuration file must contain a ``name``, a ``description``, and a ``confounds``
section.
The ``name`` and ``description`` are primarily used for documentation purposes,
while the ``confounds`` section specifies which confounds will actually be used.

The ``confounds`` section is a dictionary/object, with a unique key for each set of confounds.
Each set of confounds must contain a ``dataset`` key, which specifies the dataset to use.
The dataset must be linked to what the user provides in the ``--datasets`` parameter,
though the "preprocessed" key is a protected value for the dataset given to *XCP-D* as the
``fmri_dir`` positional argument.
For example, in the example below, three columns are collected from the fMRIPrep confounds file:
"global_signal", "csf", and "white_matter".
Other confounds must come from the "aroma" dataset (i.e., the output from fMRIPost-AROMA).
Note that the "aroma" columns are selected using regular expressions, as they start with "^"
and end with "$".
*XCP-D* will collect any columns in the selected file that match the regular expression.

Finally, there is the ``query`` field in each confound set.
This defines the BIDS entities that will be used to find the confounds file associated with the
preprocessed BOLD file that is being post-processed by *XCP-D*.

.. code-block:: yaml

   name: aroma_gsr
   description: |
      Nuisance regressors were selected according to the 'aroma_gsr' strategy.
      AROMA motion-labeled components [@pruim2015ica], mean white matter signal,
      mean cerebrospinal fluid signal, and mean global signal were selected as
      nuisance regressors [@benchmarkp;@satterthwaite_2013].
   confounds:
      preproc_confounds:
         dataset: preprocessed
         query:
            space: null
            cohort: null
            res: null
            den: null
            desc: confounds
            extension: .tsv
            suffix: timeseries
         columns:
         - global_signal
         - csf
         - white_matter
      aroma_confounds:
         dataset: aroma
         query:
            space: null
            cohort: null
            res: null
            den: null
            desc: aroma
            extension: .tsv
            suffix: timeseries
         columns:
         - ^aroma_orth_motion_.*$

In addition to TSV-based confound files, *XCP-D* also supports the use of voxel-wise confound files.
Take this partial example:

.. code-block:: yaml

   confounds:
      rapidtide_slfo:
         dataset: rapidtide
         query:
               desc: LFO
               extension: .nii.gz
               suffix: timeseries

Note in this case that the confounds definition includes a query section, but not a columns section.
This is because this query will return a 4D NIfTI file, rather than a TSV file.
The corresponding voxel-wise confounds will be extracted from the 4D NIfTI file and regressed out
of the BOLD data.


Dummy scan removal [OPTIONAL]
=============================
:func:`~xcp_d.workflows.bold.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.RemoveDummyVolumes`

*XCP-D* allows the first *N* volumes to be removed before processing.
These volumes are usually referred to as dummy volumes.
Most default scanning sequences include dummy volumes that are not reconstructed.
However, some users still prefer to remove the first few reconstructed volumes.

Users may provide the number of volumes directly with the ``--dummy-scans <INT>`` parameter,
or they may rely on the preprocessing pipeline's estimated non-steady-state volume indices with
``--dummy-scans auto``.


Despiking [OPTIONAL]
====================
:func:`~xcp_d.workflows.bold.postprocessing.init_despike_wf`

Despiking is a process in which large spikes in the BOLD times series are truncated.
Despiking reduces/limits the amplitude or magnitude of the large spikes but preserves those
data points with an imputed reduced amplitude.
This is done before regression and filtering, in order to minimize the impact of large amplitude
changes in the data.
It can be added to the command line arguments with ``--despike``.


Denoising
=========
:class:`~xcp_d.interfaces.nilearn.DenoiseNifti`, :class:`~xcp_d.interfaces.nilearn.DenoiseCifti`

The denoising approach in *XCP-D* is heavily based on Nilearn's :footcite:p:`abraham2014machine`
approach from :py:func:`~nilearn.signal.clean`,
which was designed to follow recommendations made in :footcite:t:`lindquist2019modular`.

Specifically, temporal filtering and confound regression are performed in separate stages,
but the confounds are orthogonalized with respect to the temporal filter prior to confound
regression,
so that no variance from the temporal filter is reintroduced by the confound regression.

*XCP-D* modifies Nilearn's approach in the following ways:

1. *XCP-D* uses :func:`numpy.linalg.lstsq` to estimate betas instead of QR decomposition,
   in order to denoise the interpolated data as well.
   -  QR decomposition will not produce betas that can be applied to the interpolated data.

2. *XCP-D* sets any leading or trailing high-motion volumes to the closest low-motion volume's values
   instead of extrapolating those volumes or removing them completely.

Both of these modifications allow *XCP-D* to produce a denoised, interpolated BOLD time series,
while Nilearn only produces the denoised, _censored_ BOLD time series.
The interpolated BOLD time series is necessary for DCAN-specific tools,
such as `biceps <https://biceps-cmdln.readthedocs.io/en/latest/>`_.


Interpolation
-------------

An interpolated version of the BOLD data is created by filling in the high-motion outlier volumes
with cubic spline interpolated data, as implemented in ``nilearn``.
Any outlier volumes at the beginning or end of the run are replaced with the closest non-outlier
volume's data, in order to avoid extrapolation by the interpolation function.

The same interpolation is applied to the confounds.

Interpolation (and later censoring) can be disabled by setting ``--fd-thresh 0``.


Detrending
----------

The interpolated BOLD data and confounds are then detrended with a linear model.
This step also mean-centers the BOLD data and confounds over time.

Detrending is only applied if confound regression is enabled
(i.e., if ``--nuisance-regressors`` is not ``none``).


Bandpass filtering [OPTIONAL]
-----------------------------

The detrended BOLD data and confounds are then bandpass filtered using a Butterworth filter.

Bandpass filtering can be disabled with the ``--disable-bandpass-filter`` flag.
If either ``--low-pass`` or ``--high-pass`` is set to 0, then the corresponding filter will be
applied (e.g., if ``--high-pass`` is set to 0, then only the low-pass filter will be applied).


Confound regression
-------------------

The filtered BOLD data is then regressed on the filtered confounds using a linear least-squares
approach with two steps.

In the first step, the linear model is fit to the low-motion volumes from both the BOLD data and
the confounds, and the parameter estimates are retained.

In the second step, the interpolated BOLD data are denoised using the parameter estimates from the
first step, and the residuals are retained.
The low-motion volumes in the residuals from this step are equivalent to the residuals from the
first step,
but we also retain the interpolated high-motion volumes in the residuals from this step in order
to satisfy DCAN-specific tools.

.. admonition:: Handling of signal regressors

   In some cases, nuisance regressors share variance with signal regressors, in which case
   additional processing must be done before regression.
   One example of this is denoising using components from a spatial independent components
   analysis.
   With spatial ICA, each component's spatial weights are orthogonal to all other components,
   but the time series for the component may be correlated with other components.
   In common ICA-based denoising methods, such as AROMA or ME-ICA with tedana,
   components are classified as either "noise" or "signal".
   However, the "noise" components will often share variance with the "signal" components,
   so simply regressing the noise components out of the BOLD data,
   without considering the signal components, may remove signal of interest.

   To address this issue, *XCP-D* will look for signal regressors in the selected confounds.
   If any signal regressors are detected
   (i.e., if any columns in the confounds file have a ``signal__`` prefix),
   then the noise regressors will be orthogonalized with respect to the signal regressors,
   to produce "pure evil" regressors.

   This is done automatically for *XCP-D*'s built-in nuisance strategies which include AROMA
   components, but users must manually add the ``signal__`` prefix to any signal regressors in
   their custom confounds files, if they choose to use them.

.. important::

   If you use the ``signal__`` approach, you must make sure that the signal regressors do not
   reflect noise captured by the noise regressors.
   Some ICA-based denoising methods, such as ME-ICA, can only distinguish specific types of noise,
   so they may label other types of noise as "signal".
   Since your confounds will be orthogonalized with respect to _all_ of your ``signal__``
   regressors, this could lead to the imperfect removal of noise from your BOLD data.

The residuals from the second step are referred to as the ``denoised, interpolated BOLD``.


Re-censoring
------------
:class:`~xcp_d.interfaces.censoring.Censor`

After bandpass filtering, high motion volumes are removed from the
``denoised, interpolated BOLD`` once again, to produce ``denoised BOLD``.

.. important::

   In ``linc`` mode, the re-censored BOLD data are the primary output.
   In the ``abcd`` and ``hbcd`` modes,
   the denoised, **interpolated** BOLD data are the primary output.

   This behavior is specifically controlled with the ``--output-type`` flag.


Resting-state derivative generation
===================================

For each BOLD run, resting-state derivatives are generated.
These include regional homogeneity (ReHo) and amplitude of low-frequency fluctuation (ALFF).


ALFF
----
:func:`~xcp_d.workflows.bold.metrics.init_alff_wf`

Amplitude of low-frequency fluctuation (ALFF) is a measure that ostensibly localizes
spontaneous neural activity in resting-state BOLD data.
It is calculated by the following:

1. The ``denoised, interpolated BOLD`` is passed along to the ALFF workflow.
2. If censoring+interpolation was performed, then the interpolated time series is censored at this
   point.
3. Voxel-wise BOLD time series are normalized (mean-centered and scaled to unit standard deviation)
   over time. This will ensure that the power spectrum from ``periodogram`` and ``lombscargle``
   are roughly equivalent.
4. The power spectrum and associated frequencies are estimated from the BOLD data.

   -  If censoring+interpolation was not performed, then this uses :func:`scipy.signal.periodogram`.
   -  If censoring+interpolation was performed, then this uses :func:`scipy.signal.lombscargle`.

5. The square root of the power spectrum is calculated.
6. The power spectrum values corresponding to the frequency range retained by the
   temporal filtering step are extracted from the full power spectrum.
7. The mean of the within-band power spectrum is calculated and multiplied by 2.
8. The ALFF value is multiplied by the standard deviation of the voxel-wise
   ``denoised, interpolated BOLD`` time series.
   This brings ALFF back to its original scale, as if the time series was not normalized.

ALFF will only be calculated if the bandpass filter is enabled
(i.e., if the ``--disable-bandpass-filter`` flag is not used).

Smoothed ALFF derivatives will also be generated if the ``--smoothing`` flag is used.


ReHo
----
:func:`~xcp_d.workflows.bold.metrics.init_reho_nifti_wf`,
:func:`~xcp_d.workflows.bold.metrics.init_reho_cifti_wf`

Regional Homogeneity (ReHo) is a measure of local temporal uniformity in the BOLD signal computed at each voxel of the processed image.
Greater ReHo values correspond to greater synchrony among BOLD activity patterns measured in a local neighborhood of voxels, with neighborhood size determined by a user-specified radius of voxels.
ReHo is calculated as the coefficient of concordance among all voxels in a sphere centered on the target voxel.

For NIfTIs, ReHo is always calculated via AFNI’s 3dReho with 27 voxels in each neighborhood, using Kendall's coefficient of concordance (KCC).
For CIFTIs, the left and right hemisphere are extracted into GIFTI format via Connectome Workbench’s CIFTISeparateMetric. Next, the mesh adjacency matrix is obtained,and Kendall's coefficient of concordance (KCC) is calculated, with each vertex having four neighbors.
For subcortical voxels in the CIFTIs, 3dReho is used with the same parameters that are used for NIfTIs.


Parcellation and functional connectivity estimation [OPTIONAL]
==============================================================
:func:`~xcp_d.workflows.bold.connectivity.init_functional_connectivity_nifti_wf`,
:func:`~xcp_d.workflows.bold.connectivity.init_functional_connectivity_cifti_wf`

If the user chooses,
the ``denoised BOLD`` is fed into a functional connectivity workflow,
which extracts parcel-wise time series from the BOLD using several atlases.
These atlases are documented in :doc:`outputs`.

Users can control which atlases are used with the ``--atlases`` parameter
(by default, all atlases are used),
or can skip this step entirely with ``--skip-parcellation``.

The resulting parcellated time series for each atlas is then used to generate static functional
connectivity matrices, as measured with Pearson correlation coefficients.

For CIFTI data, both tab-delimited text file (TSV) and CIFTI versions of the parcellated time
series and correlation matrices are written out.


Functional connectivity estimates from specified amounts of data [OPTIONAL]
---------------------------------------------------------------------------

Functional connectivity estimates may exhibit non-linear relationships with the number of data
points,
such that including a regressor controlling for the number of post-censoring volumes per run in
group-level models may not adequately address the issue.

In :footcite:t:`eggebrecht2017joint` and :footcite:t:`feczko2021adolescent`,
the authors' solution was to randomly select a subset of volumes from each run before calculating
correlations, so that every run had the same number of data points contributing to its functional
connectivity estimate.

We have implemented this behavior via the optional ``--create-matrices`` parameter,
which allows the user to provide a list of durations, in seconds,
to be used for functional connectivity estimates.
These subsampled correlation matrices will be written out with ``desc-<numberOfVolumes>volumes``
in the filenames.
The correlation matrices *without* the ``desc`` entity still include all of the post-censoring
volumes.

The ``--random-seed`` parameter controls the random seed used to select the reduced set of volumes,
which improves reproducibility.


Smoothing [OPTIONAL]
====================
:func:`~xcp_d.workflows.bold.postprocessing.init_resd_smoothing_wf`

The ``denoised BOLD`` may optionally be smoothed with a Gaussian kernel.
This smoothing kernel is set with the ``--smoothing`` parameter.


Concatenation of functional derivatives [OPTIONAL]
==================================================
:func:`~xcp_d.workflows.bold.concatenation.init_concatenate_data_wf`

If the ``--combine-runs`` flag is included, then BOLD runs will be grouped by task and concatenated.
Several concatenated derivatives will be generated, including the ``denoised BOLD``,
the ``denoised, interpolated BOLD``, the temporal mask, and the filtered motion parameters.

.. important::
   If a run does not have enough low-motion data and is skipped, then the concatenation workflow
   will not include that run.

.. important::
   If a set of related runs do not have enough low-motion data, then the concatenation workflow
   will automatically stop early, and no concatenated derivatives for that set of runs will be
   written out.


Quality control
===============
:func:`~xcp_d.workflows.bold.plotting.init_qc_report_wf`

The quality control (QC) in *XCP-D* estimates the quality of BOLD data before and after
regression and also estimates BOLD-T1w coregistration and BOLD-Template normalization
qualities.
The QC metrics include the following:

   a. Motion parameters summary: mean FD, mean and maximum RMS
   b. Mean DVARs before and after regression and its relationship to FD
   c. BOLD-T1w coregistration quality - Dice similarity index, Coverage and Pearson correlation
   d. BOLD-Template normalization quality - Dice similarity index, Coverage and Pearson correlation


*******
Outputs
*******

*XCP-D* generates three main types of outputs for every subject.

First, *XCP-D* generates HTML visual reports that display relevant information about the processed data.

The first of these reports is a NiPreps-style HTML file for each subject.
The report contains a Processing Summary with QC values, with the BOLD volume space, the TR,
mean FD, mean RMSD, and mean and maximum RMS,
the correlation between DVARS and FD before and after processing, and the number of volumes
censored.
Next, pre and post regression "carpet" plots are alongside DVARS and FD.
An About section that notes the release version of *XCP-D*, a Methods section that can be copied and
pasted into the user's paper,
which is customized based on command line options, and an Error section, which will read
"No errors to report!" if no errors are found.

If ``abcd`` or ``hbcd`` mode is used, or the ``--abcc-qc`` flag is used,
the "executive summary" HTML report will be created.

The "executive summary" displays relevant information about the
anatomical data and the BOLD data before and after regression.
The anatomical image viewer allows the user to see the segmentation overlaid on the anatomical
image.
Next, for each session, the user can see the segmentation registered onto the BOLD images.
Beside the segmentations, users can see the pre-regression and post-regression "carpet" plot,
as well as DVARS, FD, the global signal.
The number of volumes remaining at various FD thresholds are shown.

Second, *XCP-D* outputs processed BOLD data, including denoised unsmoothed and smoothed timeseries in
MNI152NLin2009cAsym and fsLR-32k spaces, parcellated time series, functional connectivity matrices,
and ALFF and ReHo (smoothed and unsmoothed).

Third, the anatomical data (processed T1w and/or T2w files) are copied from fMRIPrep.
If both images are not in MNI152NLin6Asym space, they are resampled to MNI space.
The fMRIPrep surfaces (gifti files) in each subject are also resampled to standard space
(fsLR-32K).

See :doc:`outputs` for details about *XCP-D* outputs.

**********
References
**********

.. footbibliography::
