#!/bin/bash

cat << DOC

Test XCP-D on cifti data with FreeSurfer
========================================

Testing cifti outputs from fmriprep


DOC

set +e
source ./get_data.sh
TESTDIR=${PWD}
get_config_data ${TESTDIR}
get_bids_data ${TESTDIR} fmriprep_colornest
get_bids_data ${TESTDIR} freesurfer_colornest

CFG=${TESTDIR}/data/nipype.cfg
export FS_LICENSE=${TESTDIR}/data/license.txt

# Test dipy_mapmri
TESTNAME=cifti_with_freesurfer
setup_dir ${TESTDIR}/${TESTNAME}
TEMPDIR=${TESTDIR}/${TESTNAME}/work
OUTPUT_DIR=${TESTDIR}/${TESTNAME}/derivatives
BIDS_INPUT_DIR=${TESTDIR}/data/fmriprepwithfreesurfer/fmriprep
XCPD_CMD=$(run_xcpd_cmd ${BIDS_INPUT_DIR} ${OUTPUT_DIR} ${TEMPDIR})

echo $XCPD_CMD

$XCPD_CMD \
    --despike \
    --head_radius 40 \
    --smoothing 6 \
    -vvv \
    --motion-filter-type lp --band-stop-min 6 \
    --warp-surfaces-native2std \
    --cifti \
    --combineruns \
    --dcan-qc \
    --dummytime 8 \
    --fd-thresh 0.04
