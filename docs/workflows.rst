
.. include:: links.rst

###########################
Processing Pipeline Details
###########################


**********
Input data
**********

The default inputs to XCP-D are the outputs of ``fMRIPrep`` (``--input-type fmriprep``) and
``Nibabies`` (``--input-type nibabies``).
XCP-D can also postprocess ``HCP`` data (``--input-type hcp``).


****************
Processing Steps
****************

See :ref:`usage_inputs` for information on input dataset structures.


Anatomical processing
=====================
:func:`~xcp_d.workflows.anatomical.init_postprocess_anat_wf`

XCP-D performs minimal postprocessing on anatomical derivatives from the preprocessing pipeline.
This includes applying existing transforms to preprocessed T1w and T2w volumes,
in order to warp them from native T1w space to the target standard space,
while retaining the original resolution.


Surface normalization
---------------------
:func:`~xcp_d.workflows.anatomical.init_warp_surfaces_to_template_wf`

If the ``--warp-surfaces-native2std`` flag is used,
then fsnative surface files from the preprocessing derivatives will be warped to fsLR-32k space.

.. important::

   This step will only succeed if FreeSurfer derivatives are also available.


Identification of high-motion outlier volumes
=============================================
:func:`~xcp_d.workflows.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.GenerateConfounds`

XCP-D uses framewise displacement to identify high-motion outlier volumes.
These outlier volumes are removed from the BOLD data prior to denoising.

The threshold used to identify outlier volumes can be set with the ``--fd-thresh`` parameter.

.. important::
   If a BOLD run does not have enough low-motion data, then the post-processing workflow
   will automatically stop early, and no derivatives for that run will be written out.


Motion parameter filtering [OPTIONAL]
-------------------------------------
:func:`~xcp_d.workflows.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.GenerateConfounds`,
:func:`~xcp_d.utils.confounds.load_motion`

Motion parameters may be contaminated with respiratory effects :footcite:p:`power2019distinctions`.
In order to address this issue, XCP-D optionally allows users to specify a band-stop or low-pass
filter to remove respiration-related signals from the motion parameters, prior to framewise
displacement calculation.
Please refer to :footcite:t:`fair2020correction` and :footcite:t:`gratton2020removal` for
more information.

.. important::
   Starting in version 0.4.0, if motion parameters are filtered in this step,
   the filtered motion parameters (including FD, and any squared or derivative regressors)
   will be used in the confound regression step.

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
:func:`~xcp_d.workflows.postprocessing.init_prepare_confounds_wf`,
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
:func:`~xcp_d.workflows.postprocessing.init_prepare_confounds_wf`,
:func:`~xcp_d.interfaces.censoring.GenerateConfounds`

The confound regressor configurations in the table below are implemented in XCP-D,
with ``36P`` as the default.
In addition to the standard confound regressors selected from fMRIPrep outputs,
custom confounds can be added as described in :ref:`usage_custom_confounds`.
If you want to use custom confounds, without any of the nuisance regressors described here,
use ``--nuisance-regressors custom``.

If you want to skip the denoising step completely, you can use ``--nuisance-regressors none``.

.. important::
   Starting in version 0.4.0, if motion parameters were filtered earlier in the workflow,
   the filtered motion parameters (including FD, and any squared or derivative regressors)
   will be used in the confound regression step.

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
   *  - acompcor_gsr
      -  X, dX
      -
      -
      - X
      - 10 com, 5WM, 5CSF
      -
   *  - acompcor
      - X, dX
      -
      -
      -
      - 10 com, 5WM, 5CSF
      -
   *  - aroma_gsr
      - X, dX
      - X
      - X
      - X
      -
      - X
   *  - aroma
      - X, dX
      - X
      - X
      -
      -
      - X
   *  - none
      -
      -
      -
      -
      -
      -

For more information about confound regressor selection, please refer to :footcite:t:`benchmarkp`.

.. warning::

   In XCP-D versions prior to 0.3.1, the selected AROMA confounds were incorrect.
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
   In the future, there will be an fMRIPost-AROMA BIDS App that runs AROMA on fMRIPrep outputs.

.. warning::
   The strategy ``gsr_only`` is only appropriate for UK Biobank data,
   as those data have already been denoised with FSL FIX.


Dummy scan removal [OPTIONAL]
=============================
:func:`~xcp_d.workflows.postprocessing.init_prepare_confounds_wf`,
:class:`~xcp_d.interfaces.censoring.RemoveDummyVolumes`

XCP-D allows the first *N* volumes to be removed before processing.
These volumes are usually refered to as dummy volumes.
Most default scanning sequences include dummy volumes that are not reconstructed.
However, some users still prefer to remove the first few reconstructed volumes.

Users may provide the number of volumes directly with the ``--dummy-scans <INT>`` parameter,
or they may rely on the preprocessing pipeline's estimated non-steady-state volume indices with
``--dummy-scans auto``.


Despiking [OPTIONAL]
====================
:func:`~xcp_d.workflows.postprocessing.init_despike_wf`

Despiking is a process in which large spikes in the BOLD times series are truncated.
Despiking reduces/limits the amplitude or magnitude of the large spikes but preserves those
data points with an imputed reduced amplitude.
This is done before regression and filtering, in order to minimize the impact of large amplitude
changes in the data.
It can be added to the command line arguments with ``--despike``.


Denoising
=========
:class:`~xcp_d.interfaces.nilearn.DenoiseNifti`, :class:`~xcp_d.interfaces.nilearn.DenoiseCifti`

The denoising approach in XCP-D is heavily based on Nilearn's :footcite:p:`abraham2014machine`
approach from :py:func:`~nilearn.signal.clean`,
which was designed to follow recommendations made in :footcite:t:`lindquist2019modular`.

Specifically, temporal filtering and confound regression are performed in separate stages,
but the confounds are orthogonalized with respect to the temporal filter prior to confound
regression,
so that no variance from the temporal filter is reintroduced by the confound regression.

XCP-D modifies Nilearn's approach in the following ways:

1. XCP-D uses :func:`numpy.linalg.lstsq` to estimate betas instead of QR decomposition,
   in order to denoise the interpolated data as well.
   -  QR decomposition will not produce betas that can be applied to the interpolated data.

2. XCP-D sets any leading or trailing high-motion volumes to the closest low-motion volume's values
   instead of extrapolating those volumes or removing them completely.

Both of these modifications allow XCP-D to produce a denoised, interpolated BOLD time series,
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

   To address this issue, XCP-D will look for signal regressors in the selected confounds.
   If any signal regressors are detected
   (i.e., if any columns in the confounds file have a ``signal__`` prefix),
   then the noise regressors will be orthogonalized with respect to the signal regressors,
   to produce "pure evil" regressors.

   This is done automatically for XCP-D's built-in nuisance strategies which include AROMA
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
The ``denoised, interpolated BOLD`` will only be written out to the output
directory if the ``--skip-dcan-qc`` flag is not used,
as users **should not** use interpolated data directly.


Re-censoring
------------
:class:`~xcp_d.interfaces.censoring.Censor`

After bandpass filtering, high motion volumes are removed from the
``denoised, interpolated BOLD`` once again, to produce ``denoised BOLD``.
This is the primary output of XCP-D.


Resting-state derivative generation
===================================

For each BOLD run, resting-state derivatives are generated.
These include regional homogeneity (ReHo) and amplitude of low-frequency fluctuation (ALFF).


ALFF
----
:func:`~xcp_d.workflows.restingstate.init_alff_wf`

Amplitude of low-frequency fluctuation (ALFF) is a measure that ostensibly localizes
spontaneous neural activity in resting-state BOLD data.
It is calculated by the following:

1. The ``denoised BOLD`` is passed along to the ALFF workflow.
2. Voxel-wise BOLD time series are normalized (mean-centered and scaled to unit standard deviation)
   over time. This will ensure that the power spectrum from ``periodogram`` and ``lombscargle``
   are roughly equivalent.
3. The power spectrum and associated frequencies are estimated from the BOLD data.

   -  If censoring+interpolation was not performed, then this uses :func:`scipy.signal.periodogram`.
   -  If censoring+interpolation was performed, then this uses :func:`scipy.signal.lombscargle`.

4. The square root of the power spectrum is calculated.
5. The power spectrum values corresponding to the frequency range retained by the
   temporal filtering step are extracted from the full power spectrum.
6. The mean of the within-band power spectrum is calculated and multiplied by 2.
7. The ALFF value is multiplied by the standard deviation of the voxel-wise
   ``denoised, interpolated BOLD`` time series.
   This brings ALFF back to its original scale, as if the time series was not normalized.

ALFF will only be calculated if the bandpass filter is enabled
(i.e., if the ``--disable-bandpass-filter`` flag is not used).

ALFF will also be calculated from the smoothed, denoised BOLD if the ``--smoothing`` flag is used.


ReHo
----
:func:`~xcp_d.workflows.restingstate.init_reho_nifti_wf`,
:func:`~xcp_d.workflows.restingstate.init_reho_cifti_wf`

Regional Homogeneity (ReHo) is a measure of local temporal uniformity in the BOLD signal computed at each voxel of the processed image.
Greater ReHo values correspond to greater synchrony among BOLD activity patterns measured in a local neighborhood of voxels,
with neighborhood size determined by a user-specified radius of voxels.
ReHo is calculated as the coefficient of concordance among all voxels in a sphere centered on the target voxel.

For NIfTIs, ReHo is always calculated via AFNI's 3dReho with 27 voxels in each neighborhood,
using Kendall's coefficient of concordance (KCC).
For CIFTIs, the left and right hemisphere are extracted into GIFTI format via
Connectome Workbench's CIFTISeparateMetric.
Next, the mesh adjacency matrix is obtained, and Kendall's coefficient of concordance (KCC) is calculated,
with each vertex having 5-6 neighbors.
For subcortical voxels in the CIFTIs, 3dReho is used with the same parameters that are used for NIfTIs.


Parcellation and functional connectivity estimation [OPTIONAL]
==============================================================
:func:`~xcp_d.workflows.connectivity.init_functional_connectivity_nifti_wf`,
:func:`~xcp_d.workflows.connectivity.init_functional_connectivity_cifti_wf`

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

We have implemented this behavior via the optional ``--exact-time`` parameter, which allows the
user to provide a list of durations, in seconds, to be used for functional connectivity estimates.
These subsampled correlation matrices will be written out with ``desc-<numberOfVolumes>volumes``
in the filenames.
The correlation matrices *without* the ``desc`` entity still include all of the post-censoring
volumes.

The ``--random-seed`` parameter can control the random seed used to select the reduced set of \
volumes, which improves reproducibility.


Smoothing [OPTIONAL]
====================
:func:`~xcp_d.workflows.postprocessing.init_resd_smoothing_wf`

The ``denoised BOLD`` may optionally be smoothed with a Gaussian kernel.
This smoothing kernel is set with the ``--smoothing`` parameter.


Concatenation of functional derivatives [OPTIONAL]
==================================================
:func:`~xcp_d.workflows.concatenation.init_concatenate_data_wf`

If the ``--combineruns`` flag is included, then BOLD runs will be grouped by task and concatenated.
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
:func:`~xcp_d.workflows.plotting.init_qc_report_wf`

The quality control (QC) in ``XCP-D`` estimates the quality of BOLD data before and after
regression and also estimates BOLD-T1w coregistration and BOLD-Template normalization
qualites.
The QC metrics include the following:

   a. Motion parameters summary: mean FD, mean and maximum RMS
   b. Mean DVARs before and after regression and its relationship to FD
   c. BOLD-T1w coregistration quality - Dice similarity index, Coverage and Pearson correlation
   d. BOLD-Template normalization quality - Dice similarity index, Coverage and Pearson correlation


*******
Outputs
*******

XCP-D generates four main types of outputs for every subject.

First, XCP-D generates an HTML "executive summary" that displays relevant information about the
anatomical data and the BOLD data before and after regression.
The anatomical image viewer allows the user to see the segmentation overlaid on the anatomical
image.
Next, for each session, the user can see the segmentation registered onto the BOLD images.
Beside the segmentations, users can see the pre-regression and post-regression "carpet" plot,
as well as DVARS, FD, the global signal.
The number of volumes remaining at various FD thresholds are shown.

Second, XCP-D generates an HTML "report" for each subject and session.
The report contains a Processing Summary with QC values, with the BOLD volume space, the TR,
mean FD, mean RMSD, and mean and maximum RMS,
the correlation between DVARS and FD before and after processing, and the number of volumes
censored.
Next, pre and post regression "carpet" plots are alongside DVARS and FD.
An About section that notes the release version of XCP-D, a Methods section that can be copied and
pasted into the user's paper,
which is customized based on command line options, and an Error section, which will read
"No errors to report!" if no errors are found.

Third, XCP-D outputs processed BOLD data, including denoised unsmoothed and smoothed timeseries in
MNI152NLin2009cAsym and fsLR-32k spaces, parcellated time series, functional connectivity matrices,
and ALFF and ReHo (smoothed and unsmoothed).

Fourth, the anatomical data (processed T1w processed and segmentation files) are copied from
fMRIPrep.
If both images are not in MNI152NLin6Asym space, they are resampled to MNI space.
The fMRIPrep surfaces (gifti files) in each subject are also resampled to standard space
(fsLR-32K).

See :doc:`outputs` for details about XCP-D outputs.

**********
References
**********

.. footbibliography::
