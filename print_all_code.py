import os
import argparse

# Define the marker filename
MARKER_FILENAME = "hidden_from_print_files"


def print_files_for_llm(root_dir):
    """
    Recursively finds .py and .vue files in root_dir, skipping directories
    containing a MARKER_FILENAME, and prints their path and content in an
    LLM-readable format.

    Args:
        root_dir (str): The path to the directory to start scanning.
    """
    found_files = False
    # Use topdown=True (default) to allow modifying dirnames in-place
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):

        # --- Directory Skipping Logic ---
        # Check subdirectories planned for visiting (in dirnames)
        # Iterate over a copy of dirnames for safe removal
        dirs_to_remove = []
        for i, subdir in enumerate(dirnames):
            potential_marker_path = os.path.join(dirpath, subdir, MARKER_FILENAME)
            if os.path.exists(potential_marker_path):
                # Mark this subdir for removal from os.walk's traversal list
                dirs_to_remove.append(subdir)
                # Optional: Print a message that we are skipping
                skipped_dir_rel_path = os.path.relpath(
                    os.path.join(dirpath, subdir), root_dir
                )
                # print(
                #     f"[INFO] Skipping directory './{skipped_dir_rel_path}' because it contains '{MARKER_FILENAME}'.\n"
                # )

        # Remove the marked directories *from the original dirnames list*
        # This prevents os.walk from descending into them
        # Modify list in reverse index order to avoid index shifting issues during loop,
        # or simply rebuild it, or remove items found in dirs_to_remove.
        # Using list comprehension for clean removal:
        original_dir_count = len(dirnames)
        dirnames[:] = [d for d in dirnames if d not in dirs_to_remove]
        # Assert to catch potential logic errors, ensure we modify in-place
        assert len(dirnames) == original_dir_count - len(
            dirs_to_remove
        ), "In-place modification failed"

        # --- File Processing Logic (for the current dirpath) ---
        # Now process the files in the *current* directory
        for filename in filenames:
            # Skip the marker file itself if it happens to match extensions
            if filename == MARKER_FILENAME:
                continue

            if "print_all_code.py" in filename:
                continue

            if filename.lower().endswith((".py", ".vue")):
                found_files = True
                file_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(
                    file_path, root_dir
                )  # Show path relative to start dir
                print(f"File: {relative_path}")
                print("<code>")
                try:
                    # Attempt to read with UTF-8, ignore errors for robustness
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        print(content)
                except IOError as e:
                    print(f"[Error reading file: {e}]")
                except Exception as e:
                    print(f"[Unexpected error reading file: {e}]")
                print("</code>")
                # print("\n" + "=" * 80 + "\n")  # Separator between files

    if not found_files:
        print(
            f"No .py or .vue files found (or all were in skipped directories) in '{os.path.abspath(root_dir)}'."
        )


def main():
    """
    Parses command-line arguments and initiates the file printing process.
    """
    parser = argparse.ArgumentParser(
        description=f"Scan a directory recursively for .py and .vue files and print their content for an LLM. Skips directories containing a file named '{MARKER_FILENAME}'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example usage:
  python print_all_code.py -d /path/to/your/project
  python print_all_code.py  (scans the current directory)""",
    )

    parser.add_argument(
        "-d",
        "--directory",
        default=".",
        help="The root directory to scan. Defaults to the current directory.",
    )

    args = parser.parse_args()
    target_directory = args.directory

    if not os.path.isdir(target_directory):
        print(f"Error: The specified directory does not exist: {target_directory}")
        return

    # Get absolute path for clarity in the starting message
    abs_target_dir = os.path.abspath(target_directory)
    # print(f"Scanning for .py and .vue files in: {abs_target_dir}")
    # print(f"Skipping any directory containing the file: '{MARKER_FILENAME}'\n")
    # print("=" * 80 + "\n")

    print_files_for_llm(abs_target_dir)  # Use absolute path for os.walk


if __name__ == "__main__":
    main()
