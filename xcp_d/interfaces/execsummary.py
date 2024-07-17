#! /usr/bin/env python
"""Classes for building an executive summary file."""
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from bids.layout import BIDSLayout, Query
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    InputMultiPath,
    SimpleInterface,
    TraitedSpec,
)
from PIL import Image

from xcp_d.data import load as load_data
from xcp_d.utils.filemanip import fname_presuffix


class ExecutiveSummary(object):
    """A class to build an executive summary.

    Parameters
    ----------
    xcpd_path : :obj:`str`
        Path to the xcp-d derivatives.
    subject_id : :obj:`str`
        Subject ID.
    session_id : None or :obj:`str`, optional
        Session ID.
    """

    def __init__(self, xcpd_path, subject_id, session_id=None):
        self.xcpd_path = xcpd_path
        self.subject_id = subject_id
        if session_id:
            self.session_id = session_id
        else:
            self.session_id = None

        self.layout = BIDSLayout(xcpd_path, config="figures", validate=False)

    def write_html(self, document, filename):
        """Write an html document to a filename.

        Parameters
        ----------
        document : :obj:`str`
            html document.
        filename : :obj:`str`
            name of html file.
        """
        soup = BeautifulSoup(document, features="lxml")
        html = soup.prettify()  # prettify the html

        filepath = os.path.join(self.xcpd_path, filename)
        with open(filepath, "w") as fo:
            fo.write(html)

    def _get_bids_file(self, query):
        files = self.layout.get(**query)
        if len(files) == 1:
            found_file = files[0].path
            found_file = os.path.relpath(found_file, self.xcpd_path)
        else:
            found_file = "None"

        return found_file

    def collect_inputs(self):
        """Collect inputs."""
        ANAT_SLICEWISE_PNG_DESCS = [
            "AxialBasalGangliaPutamen",
            "AxialInferiorTemporalCerebellum",
            "AxialSuperiorFrontal",
            "CoronalCaudateAmygdala",
            "CoronalOrbitoFrontal",
            "CoronalPosteriorParietalLingual",
            "SagittalCorpusCallosum",
            "SagittalInsulaFrontoTemporal",
            "SagittalInsulaTemporalHippocampalSulcus",
        ]
        ANAT_REGISTRATION_DESCS = [
            "AtlasOnAnat",
            "AnatOnAtlas",
            "AtlasOnSubcorticals",
            "SubcorticalsOnAtlas",
        ]
        ANAT_REGISTRATION_TITLES = [
            "Atlas On {modality}",  # noqa: FS003
            "{modality} On Atlas",  # noqa: FS003
            "Atlas On {modality} Subcorticals",  # noqa: FS003
            "{modality} Subcorticals On Atlas",  # noqa: FS003
        ]
        TASK_REGISTRATION_DESCS = [
            "TaskOnT1w",
            "T1wOnTask",
            "TaskOnT2w",
            "T2wOnTask",
        ]
        TASK_REGISTRATION_TITLES = [
            "Task On T1w",
            "T1w On Task",
            "Task On T2w",
            "T2w On Task",
        ]
        ORDERING = [
            "session",
            "task",
            "acquisition",
            "ceagent",
            "reconstruction",
            "direction",
            "run",
            "echo",
        ]

        query = {
            "subject": self.subject_id,
        }

        structural_files = {}
        for modality in ["T1w", "T2w"]:
            structural_files[modality] = {}
            query["suffix"] = modality

            # Get mosaic file for brainsprite.
            query["desc"] = "mosaic"
            query["extension"] = ".png"
            mosaic = self._get_bids_file(query)
            structural_files[modality]["mosaic"] = mosaic

            # Get slicewise PNG files for brainsprite.
            structural_files[modality]["slices"] = []
            for slicewise_png_desc in ANAT_SLICEWISE_PNG_DESCS:
                query["desc"] = slicewise_png_desc
                slicewise_pngs = self._get_bids_file(query)

                structural_files[modality]["slices"].append(slicewise_pngs)

            # Get structural registration files.
            structural_files[modality]["registration_files"] = []
            structural_files[modality]["registration_titles"] = [
                title.format(modality=modality) for title in ANAT_REGISTRATION_TITLES
            ]
            for registration_desc in ANAT_REGISTRATION_DESCS:
                query["desc"] = registration_desc
                found_file = self._get_bids_file(query)

                structural_files[modality]["registration_files"].append(found_file)

        self.structural_files_ = structural_files

        # Collect figures for concatenated resting-state data (if any)
        concatenated_rest_files = {}

        query = {
            "subject": self.subject_id,
            "task": "rest",
            "run": Query.NONE,
            "desc": "preprocESQC",
            "suffix": "bold",
            "extension": ".svg",
        }
        concatenated_rest_files["preproc_carpet"] = self._get_bids_file(query)

        query["desc"] = "postprocESQC"
        concatenated_rest_files["postproc_carpet"] = self._get_bids_file(query)

        self.concatenated_rest_files_ = concatenated_rest_files

        # Determine the unique entity-sets for the task data.
        postproc_files = self.layout.get(
            subject=self.subject_id,
            datatype="func",
            suffix="bold",
            extension=[".dtseries.nii", ".nii.gz"],
        )
        unique_entity_sets = []
        for postproc_file in postproc_files:
            entities = postproc_file.entities
            entities = {k: v for k, v in entities.items() if k in ORDERING}
            unique_entity_sets.append(entities)

        # From https://www.geeksforgeeks.org/python-unique-dictionary-filter-in-list/
        # Unique dictionary filter in list
        # Using map() + set() + items() + sorted() + tuple()
        unique_entity_sets = list(
            map(dict, set(tuple(sorted(sub.items())) for sub in unique_entity_sets))
        )
        task_entity_sets = []
        for entity_set in unique_entity_sets:
            for entity in ORDERING:
                entity_set[entity] = entity_set.get(entity, np.nan)

            task_entity_sets.append(entity_set)

        # Now sort the entity sets by each entity
        task_entity_sets = pd.DataFrame(task_entity_sets)
        task_entity_sets = task_entity_sets.sort_values(by=task_entity_sets.columns.tolist())

        # Remove concatenated resting-state scans
        # (there must also be at least one resting-state scan with run or direction)
        mask_not_nan = (task_entity_sets["task"] == "rest") & task_entity_sets[
            ["direction", "run"]
        ].notna().any(axis=1)

        # Create a mask for rows where 'run' is 'rest' and 'direction' and 'run' are NaN
        mask_nan = (task_entity_sets["task"] == "rest") & task_entity_sets[
            ["direction", "run"]
        ].isna().all(axis=1)

        # If there are rows where 'run' is 'rest', and 'direction' and 'run' are not NaN,
        # remove rows where 'run' is 'rest', and 'direction' and 'run' are NaN
        if mask_not_nan.any():
            task_entity_sets = task_entity_sets.drop(task_entity_sets[mask_nan].index)

        # Replace NaNs with Query.NONE
        task_entity_sets = task_entity_sets.fillna(Query.NONE)

        # Extract entities with variability
        # This lets us name the sections based on multiple entities (not just task and run)
        nunique = task_entity_sets.nunique()
        nunique.loc["task"] = 2  # ensure we keep task
        nunique.loc["run"] = 2  # ensure we keep run
        cols_to_drop = nunique[nunique == 1].index
        task_entity_namer = task_entity_sets.drop(cols_to_drop, axis=1)

        # Convert back to dictionary
        task_entity_sets = task_entity_sets.to_dict(orient="records")
        task_entity_namer = task_entity_namer.to_dict(orient="records")

        task_files = []

        for i_set, task_entity_set in enumerate(task_entity_sets):
            task_file_figures = {}

            # Convert any floats in the name to ints
            temp_dict = {}
            for k, v in task_entity_namer[i_set].items():
                try:
                    temp_dict[k] = int(v)
                except (ValueError, TypeError):
                    temp_dict[k] = v

            # String used for subsection headers
            task_file_figures["key"] = " ".join([f"{k}-{v}" for k, v in temp_dict.items()])

            query = {
                "subject": self.subject_id,
                "desc": "preprocESQC",
                "suffix": "bold",
                "extension": [".svg", ".png"],
                **task_entity_set,
            }

            task_file_figures["preproc_carpet"] = self._get_bids_file(query)

            query["desc"] = "postprocESQC"
            task_file_figures["postproc_carpet"] = self._get_bids_file(query)

            query["desc"] = "boldref"
            task_file_figures["reference"] = self._get_bids_file(query)

            query["desc"] = "mean"
            task_file_figures["bold"] = self._get_bids_file(query)

            task_file_figures["registration_files"] = []
            task_file_figures["registration_titles"] = TASK_REGISTRATION_TITLES
            for registration_desc in TASK_REGISTRATION_DESCS:
                query["desc"] = registration_desc
                found_file = self._get_bids_file(query)

                task_file_figures["registration_files"].append(found_file)

            # If there no mean BOLD figure, then the "run" was made by the concatenation workflow.
            # Skip the concatenated resting-state scan, since it has its own section.
            if query["task"] == "rest" and not task_file_figures["bold"]:
                continue

            task_files.append(task_file_figures)

        self.task_files_ = task_files

    def generate_report(self, out_file=None):
        """Generate the report."""
        logs_path = Path(self.xcpd_path) / "logs"
        if out_file is None:
            if self.session_id:
                out_file = f"sub-{self.subject_id}_ses-{self.session_id}_executive_summary.html"
            else:
                out_file = f"sub-{self.subject_id}_executive_summary.html"

            out_file = os.path.join(self.xcpd_path, out_file)

        boilerplate = []
        boiler_idx = 0

        if (logs_path / "CITATION.html").exists():
            text = (
                re.compile("<body>(.*?)</body>", re.DOTALL | re.IGNORECASE)
                .findall((logs_path / "CITATION.html").read_text())[0]
                .strip()
            )
            boilerplate.append((boiler_idx, "HTML", f'<div class="boiler-html">{text}</div>'))
            boiler_idx += 1

        if (logs_path / "CITATION.md").exists():
            text = (logs_path / "CITATION.md").read_text()
            boilerplate.append((boiler_idx, "Markdown", f"<pre>{text}</pre>\n"))
            boiler_idx += 1

        if (logs_path / "CITATION.tex").exists():
            text = (
                re.compile(r"\\begin{document}(.*?)\\end{document}", re.DOTALL | re.IGNORECASE)
                .findall((logs_path / "CITATION.tex").read_text())[0]
                .strip()
            )
            boilerplate.append(
                (
                    boiler_idx,
                    "LaTeX",
                    f"""<pre>{text}</pre>
<h3>Bibliography</h3>
<pre>{load_data("boilerplate.bib").read_text()}</pre>
""",
                )
            )
            boiler_idx += 1

        def include_file(name):
            return Markup(loader.get_source(environment, name)[0])

        template_folder = str(load_data("executive_summary_templates/"))
        loader = FileSystemLoader(template_folder)
        environment = Environment(loader=loader)
        environment.filters["basename"] = os.path.basename
        environment.globals["include_file"] = include_file

        template = environment.get_template("executive_summary.html.jinja")

        html = template.render(
            subject=f"sub-{self.subject_id}",
            session=f"ses-{self.session_id}" if self.session_id else None,
            structural_files=self.structural_files_,
            concatenated_rest_files=self.concatenated_rest_files_,
            task_files=self.task_files_,
            boilerplate=boilerplate,
        )

        self.write_html(html, out_file)


class _FormatForBrainSwipesInputSpec(BaseInterfaceInputSpec):
    in_files = InputMultiPath(
        File(exists=True),
        desc=(
            "Figure files. Must be the derivative's filename, "
            "not the file from the working directory."
        ),
    )


class _FormatForBrainSwipesOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="Reformatted png file.")


class FormatForBrainSwipes(SimpleInterface):
    """Reformat figure for Brain Swipes.

    From https://github.com/DCAN-Labs/BrainSwipes/blob/cb2ce964bcae93c9a234e4421c07b88bcadf2908/\
    tools/images/ingest_brainswipes_data.py#L113
    Credit to @BarryTik.
    """

    input_spec = _FormatForBrainSwipesInputSpec
    output_spec = _FormatForBrainSwipesOutputSpec

    def _run_interface(self, runtime):
        input_files = self.inputs.in_files
        assert len(input_files) == 9, "There must be 9 input files."
        idx = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
        widths, rows = [], []
        for i_row in range(3):
            row_idx = idx[i_row]
            row_files = [input_files[j_col] for j_col in row_idx]
            row = [np.asarray(Image.open(row_file)) for row_file in row_files]
            row = np.concatenate(row, axis=1)
            widths.append(row.shape[1])
            rows.append(row)

        max_width = np.max(widths)

        for i_row, row in enumerate(rows):
            width = widths[i_row]
            if width < max_width:
                pad = max_width - width
                prepad = pad // 2
                postpad = pad - prepad
                rows[i_row] = np.pad(row, ((0, 0), (prepad, postpad), (0, 0)), mode="constant")

        x = np.concatenate(rows, axis=0)
        new_x = ((x - x.min()) * (1 / (x.max() - x.min()) * 255)).astype("uint8")
        new_im = Image.fromarray(np.uint8(new_x))

        output_file = fname_presuffix(
            input_files[0],
            newpath=runtime.cwd,
            suffix="_reformatted.png",
            use_ext=False,
        )
        # all images should have the a .png extension
        new_im.save(output_file)
        self._results["out_file"] = output_file

        return runtime
