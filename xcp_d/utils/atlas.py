"""Functions for working with atlases."""


def get_atlas_names():
    """Get a list of atlases to be used for parcellation and functional connectivity analyses.

    The actual list of files for the atlases is loaded from a different function.

    Returns
    -------
    :obj:`list` of :obj:`str`
        List of atlases.
    """
    return [
        "Schaefer117",
        "Schaefer217",
        "Schaefer317",
        "Schaefer417",
        "Schaefer517",
        "Schaefer617",
        "Schaefer717",
        "Schaefer817",
        "Schaefer917",
        "Schaefer1017",
        "Glasser",
        "Gordon",
        "subcortical",
    ]


def get_atlas_file(atlas_name, cifti):
    """Select atlas by name from xcp_d/data using pkgrf.

    All atlases are in MNI or fsLR space.

    Parameters
    ----------
    atlas_name : {"Schaefer117", "Schaefer217", "Schaefer317", "Schaefer417", \
                  "Schaefer517", "Schaefer617", "Schaefer717", "Schaefer817", \
                  "Schaefer917", "Schaefer1017", "Glasser", "Gordon", \
                  "subcortical"}
        The name of the NIFTI atlas to fetch.
    cifti : bool
        True if requesting CIFTI atlases, False if requesting NIFTI atlases.

    Returns
    -------
    atlas_file : str
        Path to the atlas file.
    node_labels_file : str
        Path to the node labels file.
    """
    import os

    from pkg_resources import resource_filename as pkgrf

    if cifti:
        if atlas_name[:8] == "Schaefer":
            if atlas_name[8:12] == "1017":
                atlas_file = pkgrf(
                    "xcp_d",
                    (
                        "data/ciftiatlas/"
                        "Schaefer2018_1000Parcels_17Networks_order_fsLR_32k.dlabel.nii"
                    ),
                )
            else:
                atlas_file = pkgrf(
                    "xcp_d",
                    (
                        "data/ciftiatlas/"
                        f"Schaefer2018_{atlas_name[8]}00Parcels_"
                        "17Networks_order_fsLR_32k.dlabel.nii"
                    ),
                )
        elif atlas_name == "Glasser":
            atlas_file = pkgrf(
                "xcp_d",
                "data/ciftiatlas/Glasser_360Parcels_fsLR_32k.dlabel.nii",
            )
        elif atlas_name == "Gordon":
            atlas_file = pkgrf(
                "xcp_d",
                "data/ciftiatlas/Gordon_333Parcels_fsLR_32k.dlabel.nii",
            )
        elif atlas_name == "subcortical":
            atlas_file = pkgrf("xcp_d", "data/ciftiatlas/Tian_fsLR_32k.dlabel.nii")
        else:
            raise RuntimeError(f'Atlas "{atlas_name}" not available')

        node_labels_file = atlas_file.replace("_fsLR_32k.dlabel.nii", "_info.tsv")

    else:
        if atlas_name[:8] == "Schaefer":
            if atlas_name[8:12] == "1017":
                atlas_file = pkgrf(
                    "xcp_d",
                    (
                        "data/niftiatlas/"
                        "Schaefer2018_1000Parcels_17Networks_order_FSLMNI152_2mm.nii.gz"
                    ),
                )
            else:
                atlas_file = pkgrf(
                    "xcp_d",
                    (
                        "data/niftiatlas/"
                        f"Schaefer2018_{atlas_name[8]}00Parcels_"
                        "17Networks_order_FSLMNI152_2mm.nii.gz"
                    ),
                )
        elif atlas_name == "Glasser":
            atlas_file = pkgrf("xcp_d", "data/niftiatlas/Glasser_360Parcels_FSLMNI152_2mm.nii.gz")
        elif atlas_name == "Gordon":
            atlas_file = pkgrf("xcp_d", "data/niftiatlas/Gordon_333Parcels_FSLMNI152_2mm.nii.gz")
        elif atlas_name == "subcortical":
            atlas_file = pkgrf(
                "xcp_d",
                "data/niftiatlas/Tian_FSLMNI152_2mm.nii.gz",
            )
        else:
            raise RuntimeError(f'Atlas "{atlas_name}" not available')

        node_labels_file = atlas_file.replace("_FSLMNI152_2mm.nii.gz", "_info.tsv")

    assert os.path.isfile(node_labels_file)

    return atlas_file, node_labels_file
