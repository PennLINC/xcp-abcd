# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Utilities to read and write nifiti and cifti data."""
import nibabel as nb
import numpy as np
import os
import subprocess
from templateflow.api import get as get_template


def read_ndata(datafile, maskfile=None, scale=0):
    """Read nifti or cifti file.

    Parameters
    ----------
    datafile : str
        nifti or cifti file
    maskfile
    scale : ?

    Outputs
    -------
    data : (TxS) :obj:`numpy.ndarray`
        Vertices or voxels by timepoints.
    """
    # read cifti series
    if datafile.endswith(".dtseries.nii"):
        data = nb.load(datafile).get_fdata()

    # or nifti data, mask is required
    elif datafile.endswith(".nii.gz"):
        data = masking.apply_mask(datafile, maskfile)

    else:
        raise ValueError(f"Unknown extension for {datafile}")

    # transpose from TxS to SxT
    data = data.T

    if scale > 0:
        data = scalex(data, -scale, scale)

    return data

def write_ndata(data_matrix, template, filename, mask=None, TR=1, scale=0):
    '''
    input:
      data matrix : veritices by timepoint
      template: header and affine
      filename : name of the output
      mask : mask is not needed for cifti

    '''
    basedir = os.path.split(os.path.abspath(filename))[0]
    fileid = str(os.path.basename(filename))

    if scale > 0:
        data_matrix = scalex(data_matrix, -scale, scale)

    # write cifti series
    if template.endswith('.dtseries.nii'):
        from nibabel.cifti2 import Cifti2Image
        template_file = nb.load(template)
        if data_matrix.shape[1] == template_file.shape[0]:
            dataimg = Cifti2Image(dataobj=data_matrix.T,
                                  header=template_file.header,
                                  file_map=template_file.file_map,
                                  nifti_header=template_file.nifti_header)
        elif data_matrix.shape[1] != template_file.shape[0]:
            fake_cifti1 = str(basedir + '/' + fileid + 'fake_niftix.nii.gz')
            run_shell(['OMP_NUM_THREADS=2 wb_command -cifti-convert -to-nifti ',
                       template, fake_cifti1]) #fix
            fake_cifti0 = str(basedir + '/' + fileid + 'edited_cifti_nifti.nii.gz')
            fake_cifti0 = edit_ciftinifti(fake_cifti1, fake_cifti0, data_matrix)
            orig_cifti0 = str(basedir + '/' + fileid + 'edited_nifti2cifti.dtseries.nii')
            run_shell(['OMP_NUM_THREADS=2 wb_command  -cifti-convert -from-nifti  ',
                       fake_cifti0, template,
                       orig_cifti0, '-reset-timepoints', str(TR), str(0)]) #fix
            template_file2 = nb.load(orig_cifti0)
            dataimg = Cifti2Image(dataobj=data_matrix.T,
                                  header=template_file2.header,
                                  file_map=template_file2.file_map,
                                  nifti_header=template_file2.nifti_header)
            os.remove(fake_cifti1)
            os.remove(fake_cifti0)
            os.remove(orig_cifti0)
    # write nifti series
    elif template.endswith('.nii.gz'):
        mask_data = nb.load(mask).get_fdata()
        template_file = nb.load(template)

        if len(data_matrix.shape) == 1:
            dataz = np.zeros(mask_data.shape)
            dataz[mask_data == 1] = data_matrix

        else:
            dataz = np.zeros([
                mask_data.shape[0], mask_data.shape[1], mask_data.shape[2],
                data_matrix.shape[1]
            ])
            dataz[mask_data == 1, :] = data_matrix

        dataimg = nb.Nifti1Image(dataobj=dataz,
                                 affine=template_file.affine,
                                 header=template_file.header)

    dataimg.to_filename(filename)

    return filename


def edit_ciftinifti(in_file, out_file, datax):
    """
    this function create a fake nifti file from cifti
    in_file:
       cifti file. .dstreries etc
    out_file:
       output fake nifti file
    datax: numpy darray
      data matrix with vertices by timepoints dimension
    """
    thdata = nb.load(in_file)
    dataxx = thdata.get_fdata()
    dd = dataxx[:, :, :, 0:datax.shape[1]]
    dataimg = nb.Nifti1Image(dataobj=dd,
                             affine=thdata.affine,
                             header=thdata.header)
    dataimg.to_filename(out_file)
    return out_file


def run_shell(cmd, env=os.environ):
    """
    utilities to run shell in python
    cmd:
     shell command that wanted to be run
    """
    if type(cmd) is list:
        cmd = ' '.join(cmd)

    call_command = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        shell=True,
    )
    output, error = call_command.communicate("Hello from the other side!")
    call_command.wait()

    return output, error


def write_gii(datat, template, filename, hemi):
    '''
    datatt : vector
    template: real file loaded with nibabel to get header and filemap
    filename ; name of the output
    '''
    datax = np.array(datat, dtype='float32')
    template = str(
        get_template("fsLR", hemi=hemi, suffix='midthickness', density='32k', desc='vaavg'))
    template = nb.load(template)
    dataimg = nb.gifti.GiftiImage(header=template.header,
                                  file_map=template.file_map,
                                  extra=template.extra)
    dataimg = nb.gifti.GiftiImage(header=template.header,
                                  file_map=template.file_map,
                                  extra=template.extra,
                                  meta=template.meta)
    d_timepoint = nb.gifti.GiftiDataArray(data=datax,
                                          intent='NIFTI_INTENT_NORMAL')
    dataimg.add_gifti_data_array(d_timepoint)
    dataimg.to_filename(filename)
    return filename


def read_gii(surf_gii):
    """
    Using nibabel to read surface file
    """
    bold_data = nb.load(surf_gii) # load the gifti 
    gifti_data = bold_data.agg_data() # aggregate the data
    if not hasattr(gifti_data, '__shape__'): # if it doesn't have 'shape', reshape
        gifti_data = np.zeros((len(bold_data.darrays[0].data), len(bold_data.darrays)))
        for arr in range(len(bold_data.darrays)):
            gifti_data[:, arr] = bold_data.darrays[arr].data
    return gifti_data


def despikedatacifti(cifti, TR, basedir):
    """ despiking cifti """
    fake_cifti1 = str(basedir + '/fake_niftix.nii.gz')
    fake_cifti1_depike = str(basedir + '/fake_niftix_depike.nii.gz')
    cifti_despike = str(basedir + '/despike_nifti2cifti.dtseries.nii')
    run_shell([
        'OMP_NUM_THREADS=2 wb_command -cifti-convert -to-nifti ', cifti,
        fake_cifti1
    ])
    run_shell(
        ['3dDespike -nomask -NEW -prefix', fake_cifti1_depike, fake_cifti1])
    run_shell([
        'OMP_NUM_THREADS=2 wb_command  -cifti-convert -from-nifti  ',
        fake_cifti1_depike, cifti, cifti_despike, '-reset-timepoints',
        str(TR),
        str(0)
    ])
    return cifti_despike


def scalex(X, x_min, x_max):
    nom = (X - X.min()) * (x_max - x_min)
    denom = X.max() - X.min()
    if denom == 0:
        denom = 1
    return x_min + nom / denom
