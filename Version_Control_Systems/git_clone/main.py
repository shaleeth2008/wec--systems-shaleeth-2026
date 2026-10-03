import argparse
import json
from pathlib import Path
import sys
import numpy


class Repository:
    def __init__(self, path="."):
        self.path = Path(path).resolve()
        self.git_dir = self.path / ".pygit"
        # git obj
        self.objects_dir = self.git_dir / "objects"
        # git ref
        self.ref_dir = self.git_dir / "refs"
        # head dir
        self.heads_dir = self.git_dir / "heads"
        # git head
        self.head_file = self.git_dir / "HEAD"
        # index
        self.index_file = self.git_dir / "index"

    def init(self) -> bool:
        if self.git_dir.exists():
            return False
        # create directories
        self.git_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.ref_dir.mkdir(parents=True, exist_ok=True)
        self.heads_dir.mkdir(parents=True, exist_ok=True)
        # creating files
        self.head_file.write_text("ref: refs/heads/master\n")
        self.index_file.write_text(json.dumps({}, indent=2))
        print(f"Initialized git repository in {self.git_dir}")

        return True


def main():
    parser = argparse.ArgumentParser(description="PyGit - A simple git clone!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    
    args = parser.parse_args() 
    if not args.command:
        parser.print_help()
        return
    try:
        if args.command == "init":
            repo = Repository()
            if not repo.init():
                print("Repository already exists")
                return 
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()