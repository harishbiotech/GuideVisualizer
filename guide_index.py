"""
=========================================================
Guide Index
=========================================================

At startup, scans each tool's result folder ONCE and builds
a simple { transcript_id : filepath } index per tool. This
is just a directory listing (~5700 filenames x 4 tools) --
no CSV parsing happens here, so it stays fast even though
the result folders are large.

The actual CSV is only read later, on demand, when a user
selects a transcript (see guide_loader.py).

Author : Harish Kumar R
=========================================================
"""

import os

from utils import normalize_transcript_id


class GuideIndex:

    def __init__(self, tool_folders):
        """
        Parameters
        ----------
        tool_folders : dict
            { tool_name : folder_path }, e.g. config.TOOL_FOLDERS
        """

        self.tool_folders = tool_folders

        # { tool_name : { transcript_id : full_filepath } }
        self.index = {}

        self._build_index()

    def _build_index(self):

        print("\nBuilding guide file index...")

        for tool, folder in self.tool_folders.items():

            tool_index = {}

            if not os.path.isdir(folder):
                print(
                    f"  WARNING: folder not found for {tool}: {folder} "
                    f"(this tool will show 0 transcripts until the path "
                    f"is fixed in config.py)"
                )
                self.index[tool] = tool_index
                continue

            for filename in os.listdir(folder):

                if not filename.endswith(".csv"):
                    continue

                transcript_id = normalize_transcript_id(
                    filename[:-4]  # strip ".csv"
                )

                if transcript_id is None:
                    continue

                tool_index[transcript_id] = os.path.join(folder, filename)

            self.index[tool] = tool_index

            print(f"  {tool:<15}: {len(tool_index):,} transcript files indexed")

    # -----------------------------------------------------
    # Lookups
    # -----------------------------------------------------

    def get_filepath(self, tool, transcript_id):

        transcript_id = normalize_transcript_id(transcript_id)

        return self.index.get(tool, {}).get(transcript_id)

    def has_data(self, tool, transcript_id):

        return self.get_filepath(tool, transcript_id) is not None

    def get_transcripts_for_tool(self, tool):

        return sorted(self.index.get(tool, {}).keys())

    def get_all_transcript_ids(self):
        """
        Union of every transcript ID that has a file in AT LEAST
        ONE tool's folder. Used as a fallback if the transcript
        dropdown needs to be built from guide data alone (the
        primary source is still the transcript FASTA, since that
        is the authoritative list of real P. falciparum
        transcripts).
        """

        all_ids = set()

        for tool_index in self.index.values():
            all_ids.update(tool_index.keys())

        return sorted(all_ids)


# =========================================================
# Testing
# =========================================================

if __name__ == "__main__":

    from config import TOOL_FOLDERS

    idx = GuideIndex(TOOL_FOLDERS)

    test_id = "PF3D7_0100100.1"

    print()

    for tool in TOOL_FOLDERS:
        print(f"{tool:<15}: has_data({test_id}) = {idx.has_data(tool, test_id)}")
