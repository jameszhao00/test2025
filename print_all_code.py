import os
import argparse

# Define the marker filename
MARKER_FILENAME = "hidden_from_print_files"


def print_files_for_llm(root_dir):
    """
    Recursively finds .py, .vue, and .ts files in root_dir, skipping
    directories containing a MARKER_FILENAME, and prints their path and
    content wrapped in language-specific markdown code fences.

    Args:
        root_dir (str): The path to the directory to start scanning.
    """
    found_files = False
    # Use topdown=True (default) to allow modifying dirnames in-place
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):

        # --- Directory Skipping Logic ---
        # Check subdirectories planned for visiting (in dirnames)
        dirs_to_remove = []
        for i, subdir in enumerate(dirnames):
            potential_marker_path = os.path.join(dirpath, subdir, MARKER_FILENAME)
            if os.path.exists(potential_marker_path):
                dirs_to_remove.append(subdir)
                skipped_dir_rel_path = os.path.relpath(
                    os.path.join(dirpath, subdir), root_dir
                )
                # Optional: Uncomment to see which directories are skipped
                # print(
                #     f"[INFO] Skipping directory './{skipped_dir_rel_path}' because it contains '{MARKER_FILENAME}'.\n"
                # )

        # Remove the marked directories *from the original dirnames list*
        original_dir_count = len(dirnames)
        dirnames[:] = [d for d in dirnames if d not in dirs_to_remove]
        # Assert to catch potential logic errors, ensure we modify in-place
        assert len(dirnames) == original_dir_count - len(
            dirs_to_remove
        ), "In-place modification failed"

        # --- File Processing Logic (for the current dirpath) ---
        for filename in filenames:
            # Skip the marker file itself
            if filename == MARKER_FILENAME:
                continue

            # Skip this script itself (assuming it's named print_all_code.py)
            # You might want to adjust this if the script has a different name
            if "print_all_code.py" in filename:
                continue

            # Skip common dependency/build folders
            # Convert dirpath to lowercase for case-insensitive comparison
            lower_dirpath = dirpath.lower()
            if "node_modules" in lower_dirpath or \
               "dist" in lower_dirpath.split(os.sep) or \
               "build" in lower_dirpath.split(os.sep) or \
               ".git" in lower_dirpath.split(os.sep) or \
               "__pycache__" in lower_dirpath.split(os.sep) or \
               ".venv" in lower_dirpath.split(os.sep) or \
               "venv" in lower_dirpath.split(os.sep):
                continue


            file_lower = filename.lower()
            lang_marker = None

            # Determine the correct language marker for the fence
            if file_lower.endswith(".py"):
                lang_marker = "python"
            elif file_lower.endswith(".vue"):
                lang_marker = "vue"
            elif file_lower.endswith(".ts"):
                lang_marker = "typescript" # Added handler for TypeScript

            # If a language marker was assigned, process the file
            if lang_marker:
                found_files = True
                file_path = os.path.join(dirpath, filename)
                # Show path relative to start dir for cleaner output
                relative_path = os.path.relpath(file_path, root_dir)

                print(f"File: {relative_path}")
                print(f"```{lang_marker}") # Opening fence with language
                try:
                    # Attempt to read with UTF-8, ignore errors for robustness
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        print(content)
                except IOError as e:
                    print(f"[Error reading file {relative_path}: {e}]")
                except Exception as e:
                    print(f"[Unexpected error reading file {relative_path}: {e}]")
                print("```") # Closing fence
                # Optional: Add a separator between files
                # print("\n" + "=" * 80 + "\n")

    if not found_files:
        print(
            f"No .py, .vue, or .ts files found (or all were in skipped directories) in '{os.path.abspath(root_dir)}'."
        )


def main():
    """
    Parses command-line arguments and initiates the file printing process.
    """
    parser = argparse.ArgumentParser(
        description=f"Scan a directory recursively for .py, .vue, and .ts files and print their content with language-specific fences. Skips directories containing '{MARKER_FILENAME}' and common build/dependency folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example usage:
  python print_all_code.py -d /path/to/your/project > output.txt
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

    # Get absolute path for clarity
    abs_target_dir = os.path.abspath(target_directory)
    # Optional: Uncomment startup messages if desired
    # print(f"Scanning for .py, .vue, .ts files in: {abs_target_dir}")
    # print(f"Skipping any directory containing the file: '{MARKER_FILENAME}'")
    # print(f"Skipping common directories like node_modules, dist, build, .git, __pycache__, .venv, venv\n")
    # print("=" * 80 + "\n")

    print_files_for_llm(abs_target_dir)  # Use absolute path for os.walk


if __name__ == "__main__":
    main()