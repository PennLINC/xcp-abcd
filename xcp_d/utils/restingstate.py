# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Functions for calculating resting-state derivatives (ReHo and ALFF)."""
import nibabel as nb
import numpy as np
from nipype import logging
from scipy import signal
from scipy.stats import rankdata
from templateflow.api import get as get_template

LOGGER = logging.getLogger("nipype.utils")


def compute_2d_reho(datat, adjacency_matrix):
    """Calculate ReHo on 2D data.

    Parameters
    ----------
    datat : numpy.ndarray of shape (V, T)
        data matrix in vertices by timepoints
    adjacency_matrix : numpy.ndarray of shape (V, V)
        surface adjacency matrix

    Returns
    -------
    kcc : numpy.ndarray of shape (V,)
        ReHo values.

    Notes
    -----
    From https://www.sciencedirect.com/science/article/pii/S0165178119305384#bib0045.
    """
    n_vertices = datat.shape[0]
    kcc = np.zeros(n_vertices)

    for i_vertex in range(n_vertices):  # loop through each voxel
        neighbor_idx = np.where(adjacency_matrix[i_vertex, :])[0]  # the index of neighbors
        neighborhood_idx = np.hstack((neighbor_idx, np.array(i_vertex)))

        neighborhood_data = datat[neighborhood_idx, :]

        rankeddata = np.zeros_like(neighborhood_data)
        # pull out index of voxel, timepoint
        n_neighbors, n_volumes = neighborhood_data.shape[0], neighborhood_data.shape[1]

        for j_neighbor in range(n_neighbors):
            # assign ranks to timepoints for each voxel
            rankeddata[j_neighbor, :] = rankdata(neighborhood_data[j_neighbor, :])

        rankmean = np.sum(rankeddata, axis=0)  # add up ranks
        # kc is the sum of the squared rankmean minus the timepoints into
        # the mean of the rankmean squared
        kc = np.sum(np.power(rankmean, 2)) - n_volumes * np.power(np.mean(rankmean), 2)

        # square number of neighbours, multiply by (cubed timepoint - timepoint)
        denom = np.power(n_neighbors, 2) * (np.power(n_volumes, 3) - n_volumes)

        # the voxel value is 12*kc divided by denom
        kcc[i_vertex] = 12 * kc / (denom)

    return kcc


def mesh_adjacency(hemi):
    """Calculate adjacency matrix from mesh timeseries.

    Parameters
    ----------
    hemi : {"L", "R"}
        Surface sphere to be load from templateflow
        Either left or right hemisphere

    Returns
    -------
    numpy.ndarray
        Adjacency matrix.

    Notes
    -----
    Modified by Taylor Salo to loop over all vertices in faces.
    """
    surf = str(get_template("fsLR", space=None, hemi=hemi, suffix="sphere", density="32k"))
    surf = nb.load(surf)  # load via nibabel

    # Aggregate GIFTI data arrays into an ndarray or tuple of ndarray select the arrays in a
    # specific order
    vertices_faces = surf.agg_data(("pointset", "triangle"))
    vertices = vertices_faces[0]
    faces = vertices_faces[1]
    n_vertices = vertices.shape[0]

    adjacency_matrix = np.zeros([n_vertices, n_vertices], dtype=bool)
    for i_face in range(faces.shape[0]):
        face = faces[i_face, :]  # pull out the face
        for vertex1 in face:
            for vertex2 in face:
                if vertex1 != vertex2:  # don't include the vertex as its own neighbor
                    adjacency_matrix[vertex1, vertex2] = True

    assert np.array_equal(adjacency_matrix, adjacency_matrix.T)
    return adjacency_matrix


def compute_alff(data_matrix, low_pass, high_pass, TR, sample_mask=None):
    """Compute amplitude of low-frequency fluctuation (ALFF).

    Parameters
    ----------
    data_matrix : numpy.ndarray
        data matrix points by timepoints, after optional censoring
    low_pass : float
        low pass frequency in Hz
    high_pass : float
        high pass frequency in Hz
    TR : float
        repetition time in seconds
    sample_mask : numpy.ndarray or None
        (timepoints,) 1D array with 1s for good volumes and 0s for censored ones.

    Returns
    -------
    alff : numpy.ndarray
        ALFF values.

    Notes
    -----
    Implementation based on :footcite:t:`yu2007altered`,
    although the ALFF values are not scaled by the mean ALFF value across the brain.

    If a ``sample_mask`` is provided, then the power spectrum will be estimated using a
    Lomb-Scargle periodogram
    :footcite:p:`lomb1976least,scargle1982studies,townsend2010fast,taylorlomb`.

    References
    ----------
    .. footbibliography::
    """
    fs = 1 / TR  # sampling frequency
    n_voxels, n_volumes = data_matrix.shape

    if sample_mask is not None:
        sample_mask = sample_mask.astype(bool)
        assert sample_mask.sum() == n_volumes, f"{sample_mask.sum()} != {n_volumes}"

        time_arr = np.arange(0, sample_mask.size * TR, TR)
        time_arr = time_arr[sample_mask]
        assert time_arr.size == n_volumes, f"{time_arr.size} != {n_volumes}"

    alff = np.zeros(n_voxels)
    for i_voxel in range(n_voxels):
        voxel_data = data_matrix[i_voxel, :]
        # Check if the voxel's data are all the same value (esp. zeros).
        # Set ALFF to 0 in that case and move on to the next voxel.
        if np.std(voxel_data) == 0:
            alff[i_voxel] = 0
            continue

        # We will normalize data matrix over time.
        # This will ensure that the power spectra from the standard and Lomb-Scargle periodograms
        # have the same scale.
        # However, this also changes ALFF's scale, so we retain the SD to rescale ALFF.
        sd_scale = np.std(voxel_data)
        voxel_data -= np.mean(voxel_data)
        voxel_data /= np.std(voxel_data)

        if sample_mask is not None:
            frequencies_hz = np.linspace(0, 0.5 * fs, (n_volumes // 2) + 1)[1:]
            angular_frequencies = 2 * np.pi * frequencies_hz
            power_spectrum = signal.lombscargle(
                time_arr,
                voxel_data,
                angular_frequencies,
                normalize=True,
            )
        else:
            # get array of sample frequencies + power spectrum density
            frequencies_hz, power_spectrum = signal.periodogram(
                voxel_data,
                fs,
                scaling="spectrum",
            )

        # square root of power spectrum
        power_spectrum_sqrt = np.sqrt(power_spectrum)
        # get the position of the arguments closest to high_pass and low_pass, respectively
        ff_alff = [
            np.argmin(np.abs(frequencies_hz - high_pass)),
            np.argmin(np.abs(frequencies_hz - low_pass)),
        ]
        # alff for that voxel is 2 * the mean of the sqrt of the power spec
        # from the value closest to the low pass cutoff, to the value closest
        # to the high pass pass cutoff
        alff[i_voxel] = len(ff_alff) * np.mean(power_spectrum_sqrt[ff_alff[0] : ff_alff[1]])
        # Rescale ALFF based on original BOLD scale
        alff[i_voxel] *= sd_scale

    assert alff.size == n_voxels, f"{alff.shape} != {n_voxels}"

    # Add second dimension to array
    alff = alff[:, None]

    return alff
