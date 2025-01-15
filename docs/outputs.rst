
.. include:: links.rst

##################
Outputs of *XCP-D*
##################

The  *XCP-D* outputs are written out in BIDS format and consist of three main parts.

.. admonition:: A note on BIDS compliance

   *XCP-D* attempts to follow the BIDS specification as closely as possible.
   However, many *XCP-D* derivatives are not currently covered by the specification.
   In those instances, we attempt to follow recommendations from existing BIDS Extension Proposals
   (BEPs), which are in-progress proposals to add new features to BIDS.
   However, we do not guarantee compliance with any BEP,
   as they are not yet part of the official BIDS specification.

   Four BEPs that are of particular use in *XCP-D* are
   `BEP011: Structural preprocessing derivatives <https://github.com/bids-standard/bids-specification/pull/518>`_,
   `BEP012: Functional preprocessing derivatives <https://github.com/bids-standard/bids-specification/pull/519>`_,
   `BEP017: Relationship & connectivity matrix data schema <https://docs.google.com/document/d/1ugBdUF6dhElXdj3u9vw0iWjE6f_Bibsro3ah7sRV0GA/edit?usp=sharing>`_,
   and
   `BEP038: Atlas Specification <https://docs.google.com/document/d/1RxW4cARr3-EiBEcXjLpSIVidvnUSHE7yJCUY91i5TfM/edit?usp=sharing>`_.

   In cases where a derivative type is not covered by an existing BEP,
   we have simply attempted to follow the general principles of BIDS.

   If you discover a problem with the BIDS compliance of *XCP-D*'s derivatives,
   please open an issue in the *XCP-D* repository.


***************
Summary Reports
***************

There are two summary reports - a Nipreps-style participant summary and an executive summary per
session.
The executive summary is based on the DCAN lab's
`ExecutiveSummary tool <https://github.com/DCAN-Labs/ExecutiveSummary>`_.

.. code-block::

   xcp_d/
      sub-<label>.html
      sub-<label>[_ses-<label>]_executive_summary.html


*************************
Parcellations and Atlases
*************************

*XCP-D* produces parcellated anatomical and functional outputs using a series of atlases.
The individual outputs are documented in the relevant sections of this document,
with this section describing the atlases themselves.

The atlases currently used in *XCP-D* can be separated into three groups: subcortical, cortical,
and combined cortical/subcortical.
The two subcortical atlases are the Tian atlas :footcite:p:`tian2020topographic` and the
CIFTI subcortical parcellation :footcite:p:`glasser2013minimal`.
The cortical atlases are the Glasser :footcite:p:`Glasser_2016`, the
Gordon :footcite:p:`Gordon_2014`,
the MIDB precision brain atlas derived from ABCD data and thresholded at 75% probability
:footcite:p:`hermosillo2022precision`,
and the Myers-Labonte infant atlas thresholded at 50% probability :footcite:`myers2023functional`.
The combined cortical/subcortical atlases are 10 different resolutions of the
4S (Schaefer Supplemented with Subcortical Structures) atlas.

The 4S atlas combines the Schaefer 2018 cortical atlas (version v0143) :footcite:p:`Schaefer_2017`
at 10 different resolutions (100, 200, 300, 400, 500, 600, 700, 800, 900, and 1000 parcels) with
the CIT168 subcortical atlas :footcite:p:`pauli2018high`,
the Diedrichson cerebellar atlas :footcite:p:`king2019functional`,
the HCP thalamic atlas :footcite:p:`najdenovska2018vivo`,
and the amygdala and hippocampus parcels from the HCP CIFTI subcortical parcellation
:footcite:p:`glasser2013minimal`.
The 4S atlas is used in the same manner across three PennLINC BIDS Apps:
*XCP-D*, QSIPrep_, and ASLPrep_, to produce synchronized outputs across modalities.
For more information about the 4S atlas, please see https://github.com/PennLINC/AtlasPack.

.. tip::

   You can choose to only use a subset of the available atlases by using the ``--atlases``
   parameter.

   Alternatively, if you want to skip the parcellation step completely,
   you can use the ``--skip-parcellation`` parameter.

Atlases are written out to the ``atlases`` subfolder, following BEP038.

.. code-block::

   xcp_d/
      atlases/
         dataset_description.json
         atlas-<label>/
            atlas-<label>_dseg.json
            atlas-<label>_dseg.tsv

            # NIfTI
            atlas-<label>_space-<label>_dseg.nii.gz

            # CIFTI
            atlas-<label>_space-<label>_dseg.dlabel.nii


******************
Anatomical Outputs
******************

Anatomical outputs consist of anatomical preprocessed T1w and/or T2w images in MNI space.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         anat/
            <source_entities>_space-MNI152NLin6Asym_desc-preproc_T1w.nii.gz
            <source_entities>_space-MNI152NLin6Asym_desc-preproc_T2w.nii.gz


Surface mesh files
==================

If the ``--warp-surfaces-native2std`` option is selected, and reconstructed surfaces are available
in the preprocessed dataset, then these surfaces will be warped to fsLR space at 32k density.

The resulting mesh files will reflect the subject's morphology with the same geometry and density
as fsLR-32k surfaces, which may be useful for visualizing fsLR-space derivatives on a subject's
brain.

The mesh files are also warped so that they can be overlaid on top of the MNI152NLin6Asym template,
as in XCP-D's brainsprite.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         anat/
            <source_entities>_hemi-<L|R>_space-fsLR_den-32k_desc-hcp_midthickness.surf.gii
            <source_entities>_hemi-<L|R>_space-fsLR_den-32k_desc-hcp_inflated.surf.gii
            <source_entities>_hemi-<L|R>_space-fsLR_den-32k_desc-hcp_vinflated.surf.gii
            <source_entities>_hemi-<L|R>_space-fsLR_den-32k_pial.surf.gii
            <source_entities>_hemi-<L|R>_space-fsLR_den-32k_white.surf.gii


Surface morphometric files
==========================

*XCP-D* will also pass along several morphometric files from the preprocessing derivatives,
as long as the files are already in fsLR space at 91k density.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         anat/
            <source_entities>_space-fsLR_den-91k_sulc.dscalar.nii
            <source_entities>_space-fsLR_den-91k_curv.dscalar.nii
            <source_entities>_space-fsLR_den-91k_thickness.dscalar.nii


*XCP-D* will additionally parcellate each of these files, when they are present, using each of the
atlases it uses to parcellate the functional outputs.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         anat/
            <source_entities>_space-fsLR_seg-<label>_stat-mean_desc-curv_morph.tsv
            <source_entities>_space-fsLR_seg-<label>_stat-mean_desc-sulc_morph.tsv
            <source_entities>_space-fsLR_seg-<label>_stat-mean_desc-thickness_morph.tsv


******************
Functional Outputs
******************

Functional outputs consist of processed/denoised BOLD data, timeseries,
functional connectivity matrices, and resting-state derivatives.


Denoised or residual BOLD data
==============================

.. important::

   Smoothed denoised BOLD files will only be generated if smoothing is enabled with the
   ``--smoothing`` parameter.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         func/
            # NIfTI
            <source_entities>_space-<label>_desc-denoised_bold.nii.gz
            <source_entities>_space-<label>_desc-denoisedSmoothed_bold.nii.gz

            # CIFTI
            <source_entities>_space-fsLR_den-91k_desc-denoised_bold.dtseries.nii
            <source_entities>_space-fsLR_den-91k_desc-denoisedSmoothed_bold.dtseries.nii

.. important::
   If ``abcd`` or ``hbcd`` mode is used, the denoised BOLD data will be interpolated.
   If ``linc`` mode is used, the denoised BOLD data will be censored.

The sidecar json files contains parameters of the data and processing steps.
The Sources field contains BIDS URIs pointing to the files used to create the derivative.
The associated DatasetLinks are defined in the dataset_description.json.

   .. code-block:: json-object

      {
         "EchoTime": 0.0424,
         "EffectiveEchoSpacing": 0.000639989,
         "FlipAngle": 51,
         "Manufacturer": "Siemens",
         "ManufacturersModelName": "Skyra",
         "NuisanceParameters": "gsr_only",
         "PhaseEncodingDirection": "j-",
         "RepetitionTime": 3,
         "SoftwareFilters": {
            "Bandpass filter": {
               "Filter order": 2,
               "High-pass cutoff (Hz)": 0.01,
               "Low-pass cutoff (Hz)": 0.08
            }
         },
         "Sources": [
            "bids:preprocessed:sub-0000001/ses-01/func/sub-0000001_ses-01_task-rest_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz",
            "bids:xcp_d:sub-0000001/ses-01/func/sub-0000001_ses-01_task-rest_outliers.tsv",
            "bids:xcp_d:sub-0000001/ses-01/func/sub-0000001_ses-01_task-rest_desc-preproc_design.tsv"
         ],
         "TaskName": "resting state"
      }


Functional timeseries and connectivity matrices
===============================================

This includes the atlases used to extract the timeseries.

.. important::

   If ``abcd`` or ``hbcd`` mode is used, the time series will be interpolated.
   If ``linc`` mode is used, the time series will be censored.
   In both cases, the correlation matrices will be calculated using the censored time series.

.. important::

   Correlation matrices with the ``desc-<INT>volumes`` entity are produced if the
   ``--create-matrices`` parameter is used with integer values.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         func/
            # NIfTI
            <source_entities>_space-<label>_seg-<label>_stat-coverage_bold.tsv
            <source_entities>_space-<label>_seg-<label>_stat-mean_timeseries.tsv
            <source_entities>_space-<label>_seg-<label>_stat-pearsoncorrelation_relmat.tsv
            <source_entities>_space-<label>_seg-<label>_stat-pearsoncorrelation_desc-<INT>volumes_relmat.tsv

            # CIFTI
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-coverage_bold.tsv
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-coverage_boldmap.pscalar.nii
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-mean_timeseries.tsv
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-mean_timeseries.ptseries.nii
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-pearsoncorrelation_relmat.tsv
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-pearsoncorrelation_boldmap.pconn.nii
            <source_entities>_space-fsLR_seg-<label>_den-91k_stat-pearsoncorrelation_desc-<INT>volumes_relmat.tsv


Resting-state metric derivatives (ReHo and ALFF)
================================================

*XCP-D* calculates both regional homogeneity (ReHo) and amplitude of low-frequency fluctuations
(ALFF), depending on the parameters.

.. important::
   Smoothed ALFF will only be generated if smoothing is enabled with the ``--smoothing``
   parameter.

.. important::
   ALFF will not be generated if bandpass filtering is disabled with the
   ``--disable-bandpass-filtering`` parameter.

*XCP-D* will also parcellate the ReHo and ALFF maps with each of the atlases used for the BOLD
data.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         func/
            # NIfTI
            <source_entities>_space-<label>_stat-reho_boldmap.nii.gz
            <source_entities>_space-<label>_stat-alff_boldmap.nii.gz
            <source_entities>_space-<label>_stat-alff_desc-smooth_boldmap.nii.gz
            <source_entities>_space-<label>_seg-<label>_stat-alff_bold.tsv
            <source_entities>_space-<label>_seg-<label>_stat-reho_bold.tsv

            # CIFTI
            <source_entities>_space-fsLR_den-91k_stat-reho_boldmap.dscalar.nii
            <source_entities>_space-fsLR_den-91k_stat-alff_boldmap.dscalar.nii
            <source_entities>_space-fsLR_den-91k_stat-alff_desc-smooth_boldmap.dscalar.nii
            <source_entities>_space-fsLR_seg-<label>_stat-alff_bold.tsv
            <source_entities>_space-fsLR_seg-<label>_stat-reho_bold.tsv


Other outputs include quality control, framewise displacement, and confounds files
==================================================================================

.. code-block::

   xcp_d/
      desc-linc_qc.json

      sub-<label>/[ses-<label>/]
         func/
            <source_entities>_motion.tsv
            <source_entities>_outliers.tsv
            <source_entities>_design.tsv
            <source_entities>_space-<label>_desc-linc_qc.tsv

``_motion.tsv`` is a tab-delimited file with seven columns:
one for each of the six filtered motion parameters, as well as "framewise_displacement".
If motion filtering was applied, this file will seven extra columns: the seven described above,
with ``_filtered`` appended to each column.
This file includes the high-motion volumes that are removed in most other derivatives.

``outliers.tsv`` is a tab-delimited file with one column: "framewise_displacement".
The "framewise_displacement" column contains zeros for low-motion volumes, and ones for
high-motion outliers.
This file includes the high-motion volumes that are removed in most other derivatives.

``design.tsv`` is a tab-delimited file with one column for each nuisance regressor.
This file includes rows for the high-motion volumes that are removed in most other derivatives.
It does not indicate which volumes are removed (please see the ``outliers.tsv`` for that)
and also does not include the intercept or linear trend terms that are separately applied before
the GLM regression.

``_desc-linc_qc.tsv`` is a tab-delimited file with one row and one column for each of several QC
metrics. The QC metrics are described in detail in the ``desc-linc_qc.json`` file.
This file includes metrics indicating the number of volumes removed due to high motion,
the number of confounds used in the denoising step
(including two for the linear trend and intercept),
and the number of degrees of freedom lost by temporal filtering.

In order to determine the degrees of freedom for the resulting correlations,
you should do the following calculation:
``num_retained_volumes - (num_dof_used_by_denoising + num_dof_used_by_filter + 2)``.

.. important::

   This formula ignores autocorrelation.
   In order to calculate the effective degrees of freedom for your correlation coefficients,
   consider using a tool like xDF.

.. warning::

   This formula must be adjusted for correlations computed from random subsets of the time series
   (i.e., by using the ``--create-matrices`` parameter with integer values).


DCAN style scrubbing file (if ``--abcc-qc`` is not used)
========================================================

This file is in hdf5 format (readable by h5py), and contains binary scrubbing masks from 0.0
to 1mm FD in 0.01 steps.

.. code-block::

   xcp_d/
      sub-<label>/[ses-<label>/]
         func/
            <source_entities>_desc-abcc_qc.hdf5

These files have the following keys:

1. ``FD_threshold``: a number >= 0 that represents the FD threshold used to calculate the
   metrics in this list
2. ``frame_removal``: a binary vector/array the same length as the number of frames in the
   concatenated time series, indicates whether a frame is removed (1) or not (0)
3. ``format_string`` (legacy): a string that denotes how the frames were excluded -- uses a
   notation devised by Avi Snyder
4. ``total_frame_count``: a whole number that represents the total number of frames in the
   concatenated series
5. ``remaining_frame_count``: a whole number that represents the number of remaining frames in
   the concatenated series
6. ``remaining_seconds``: a whole number that represents the amount of time remaining after
   thresholding
7. ``remaining_frame_mean_FD``: a number >= 0 that represents the mean FD of the remaining frames


**********
References
**********

.. footbibliography::
