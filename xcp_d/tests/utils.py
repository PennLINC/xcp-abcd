"""Utility functions for tests."""
import os.path as op
from glob import glob


def get_test_data_path():
    """Return the path to test datasets, terminated with separator.

    Test-related data are kept in tests folder in "data".
    Based on function by Yaroslav Halchenko used in Neurosynth Python package.
    """
    return op.abspath(op.join(op.dirname(__file__), "data") + op.sep)


def check_generated_files(out_dir, output_list_file):
    """Compare files generated by xcp_d with a list of expected files."""
    xcpd_dir = op.join(out_dir, "xcp_d")
    found_files = sorted(glob(op.join(xcpd_dir, "**/*"), recursive=True))
    found_files = [op.relpath(f, out_dir) for f in found_files]

    # Ignore figures
    found_files = [f for f in found_files if "figures" not in f]

    with open(output_list_file, "r") as fo:
        expected_files = fo.readlines()
        expected_files = [f.rstrip() for f in expected_files]

    if sorted(found_files) != sorted(expected_files):
        expected_not_found = sorted(list(set(expected_files) - set(found_files)))
        found_not_expected = sorted(list(set(found_files) - set(expected_files)))

        msg = ""
        if expected_not_found:
            msg += "\nExpected but not found:\n\t"
            msg += "\n\t".join(expected_not_found)

        if found_not_expected:
            msg += "\nFound but not expected:\n\t"
            msg += "\n\t".join(found_not_expected)
        raise ValueError(msg)
