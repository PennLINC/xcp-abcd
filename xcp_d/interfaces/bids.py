"""Adapted interfaces from Niworkflows."""

from json import loads
from pathlib import Path

from bids.layout import Config
from nipype import logging
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    Directory,
    File,
    SimpleInterface,
    TraitedSpec,
    traits,
)
from niworkflows.interfaces.bids import DerivativesDataSink as BaseDerivativesDataSink
from pkg_resources import resource_filename as pkgrf

# NOTE: Modified for xcpd's purposes
xcp_d_spec = loads(Path(pkgrf("xcp_d", "data/xcp_d_bids_config.json")).read_text())
bids_config = Config.load("bids")
deriv_config = Config.load("derivatives")

xcp_d_entities = {v["name"]: v["pattern"] for v in xcp_d_spec["entities"]}
merged_entities = {**bids_config.entities, **deriv_config.entities}
merged_entities = {k: v.pattern for k, v in merged_entities.items()}
merged_entities = {**merged_entities, **xcp_d_entities}
merged_entities = [{"name": k, "pattern": v} for k, v in merged_entities.items()]
config_entities = frozenset({e["name"] for e in merged_entities})

LOGGER = logging.getLogger("nipype.interface")


class DerivativesDataSink(BaseDerivativesDataSink):
    """Store derivative files.

    A child class of the niworkflows DerivativesDataSink, using xcp_d's configuration files.
    """

    out_path_base = "xcp_d"
    _allowed_entities = set(config_entities)
    _config_entities = config_entities
    _config_entities_dict = merged_entities
    _file_patterns = xcp_d_spec["default_path_patterns"]


class _CollectRegistrationFilesInputSpec(BaseInterfaceInputSpec):
    segmentation_dir = Directory(
        exists=True,
        required=True,
        desc="Path to FreeSurfer or MCRIBS derivatives.",
    )
    software = traits.Enum(
        "FreeSurfer",
        "MCRIBS",
        required=True,
        desc="The software used for segmentation.",
    )
    hemisphere = traits.Enum(
        "L",
        "R",
        required=True,
        desc="The hemisphere being used.",
    )
    participant_id = traits.Str(
        required=True,
        desc="Participant ID. Used to select the subdirectory of the FreeSurfer derivatives.",
    )


class _CollectRegistrationFilesOutputSpec(TraitedSpec):
    subject_sphere = File(
        exists=True,
        desc="Subject-space sphere.",
    )
    source_sphere = File(
        exists=True,
        desc="Source-space sphere (namely, fsaverage).",
    )
    target_sphere = File(
        exists=True,
        desc="Target-space sphere (fsLR for FreeSurfer, dHCP-in-fsLR for MCRIBS).",
    )
    sphere_to_sphere = File(
        exists=True,
        desc="Warp file going from source space to target space.",
    )


class CollectRegistrationFiles(SimpleInterface):
    """Collect registration files for fsnative-to-fsLR transformation.

    TODO: Collect from the preprocessing derivatives if they're a compliant version.
    Namely, fMRIPrep >= 23.1.2, Nibabies >= 24.0.0a1.
    XXX: Wait until the Config object is up and running, so we have access to the BIDSLayout.
    """

    input_spec = _CollectRegistrationFilesInputSpec
    output_spec = _CollectRegistrationFilesOutputSpec

    def _run_interface(self, runtime):
        import os

        from templateflow.api import get as get_template

        hemisphere = self.inputs.hemisphere
        hstr = f"{hemisphere.lower()}h"
        participant_id = self.inputs.participant_id
        if not participant_id.startswith("sub-"):
            participant_id = f"sub-{participant_id}"

        if self.inputs.software == "FreeSurfer":
            # Find the subject's sphere in the FreeSurfer derivatives.
            # In fMRIPrep derivatives, sub-<subject_label>_hemi-[LR]_desc-reg_sphere.surf.gii
            self._results["subject_sphere"] = os.path.join(
                self.inputs.segmentation_dir,
                participant_id,
                "surf",
                f"{hstr}.sphere.reg",
            )

            # Load the fsaverage-164k sphere.
            self._results["source_sphere"] = str(
                get_template(
                    template="fsaverage",
                    space=None,
                    hemi=hemisphere,
                    density="164k",
                    desc=None,
                    suffix="sphere",
                )
            )

            # Load the fsaverage-to-fsLR warp sphere.
            self._results["sphere_to_sphere"] = str(
                get_template(
                    template="fsaverage",
                    space="fsLR",
                    hemi=hemisphere,
                    density="164k",
                    desc=None,
                    suffix="sphere",
                )
            )

            # Load the fsLR-32k sphere.
            self._results["target_sphere"] = str(
                get_template(
                    template="fsLR",
                    space=None,
                    hemi=hemisphere,
                    density="32k",
                    desc=None,
                    suffix="sphere",
                )
            )

        elif self.inputs.software == "MCRIBS":
            # Find the subject's sphere in the MCRIBS derivatives.
            self._results["subject_sphere"] = os.path.join(
                self.inputs.segmentation_dir,
                participant_id,
                "freesurfer",
                participant_id,
                "surf",
                f"{hstr}.sphere.reg2",
            )

            # Load the fsaverage-41k sphere.
            self._results["source_sphere"] = str(
                get_template(
                    template="fsaverage",
                    space=None,
                    hemi=hemisphere,
                    density="41k",
                    desc="reg",
                    suffix="sphere",
                )
            )

            # Load the fsaverage-to-dHCP(?) warp sphere.
            self._results["sphere_to_sphere"] = str(
                get_template(
                    template="dHCP",
                    space="fsaverage",
                    hemi=hemisphere,
                    density="41k",
                    desc="reg",
                    suffix="sphere",
                )
            )

            # Load the dHCP-32k-in-fsLR space sphere.
            self._results["target_sphere"] = str(
                get_template(
                    template="dHCP",
                    space="fsLR",
                    hemi=hemisphere,
                    density="32k",
                    desc="week42",
                    suffix="sphere",
                )
            )

        return runtime
