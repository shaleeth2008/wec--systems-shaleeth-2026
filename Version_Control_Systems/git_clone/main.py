from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Tuple, Set
import zlib


class GitObject:
    """Base class for Git internal storage objects (blobs, trees, commits)."""

    def __init__(self, obj_type: str, content: bytes):
        self.type = obj_type
        self.content = content

    def hash(self) -> str:
        # Format: <type> <size>\0<content>
        header = f"{self.type} {len(self.content)}\0".encode()
        return hashlib.sha1(header + self.content).hexdigest()

    def serialize(self) -> bytes:
        header = f"{self.type} {len(self.content)}\0".encode()
        return zlib.compress(header + self.content)

    @classmethod
    def deserialize(cls, data: bytes) -> GitObject:
        decompressed = zlib.decompress(data)
        null_idx = decompressed.find(b"\0")
        header = decompressed[:null_idx].decode()
        content = decompressed[null_idx + 1 :]

        obj_type, _ = header.split(" ")
        return cls(obj_type, content)


class Blob(GitObject):
    """Represents a file content snapshot."""

    def __init__(self, content: bytes):
        super().__init__("blob", content)


class Tree(GitObject):
    """Represents a directory snapshot storing mode, filename, and object hash."""

    def __init__(self, entries: Optional[List[Tuple[str, str, str]]] = None):
        self.entries = entries or []
        content = self._serialize_entries()
        super().__init__("tree", content)

    def _serialize_entries(self) -> bytes:
        content = b""
        for mode, name, obj_hash in sorted(self.entries):
            content += f"{mode} {name}\0".encode()
            content += bytes.fromhex(obj_hash)
        return content

    def add_entry(self, mode: str, name: str, obj_hash: str):
        self.entries.append((mode, name, obj_hash))
        self.content = self._serialize_entries()

    @classmethod
    def from_content(cls, content: bytes) -> Tree:
        tree = cls()
        i = 0
        while i < len(content):
            null_idx = content.find(b"\0", i)
            if null_idx == -1:
                break

            mode_name = content[i:null_idx].decode()
            mode, name = mode_name.split(" ", 1)
            obj_hash = content[null_idx + 1 : null_idx + 21].hex()
            tree.entries.append((mode, name, obj_hash))
            i = null_idx + 21

        return tree


class Commit(GitObject):
    """Represents a repository commit with tree hash, parents, and author metadata."""

    def __init__(
        self,
        tree_hash: str,
        parent_hashes: List[str],
        author: str,
        committer: str,
        message: str,
        timestamp: Optional[int] = None,
    ):
        self.tree_hash = tree_hash
        self.parent_hashes = parent_hashes
        self.author = author
        self.committer = committer
        self.message = message
        self.timestamp = timestamp or int(time.time())

        content = self._serialize_commit()
        super().__init__("commit", content)

    def _serialize_commit(self) -> bytes:
        lines = [f"tree {self.tree_hash}"]
        for parent in self.parent_hashes:
            lines.append(f"parent {parent}")

        lines.append(f"author {self.author} {self.timestamp} +0000")
        lines.append(f"committer {self.committer} {self.timestamp} +0000")
        lines.append("")
        lines.append(self.message)

        return "\n".join(lines).encode()

    @classmethod
    def from_content(cls, content: bytes) -> Commit:
        lines = content.decode().split("\n")
        tree_hash = None
        parent_hashes = []
        author = ""
        committer = ""
        timestamp = int(time.time())
        message_start = 0

        for i, line in enumerate(lines):
            if line.startswith("tree "):
                tree_hash = line[5:]
            elif line.startswith("parent "):
                parent_hashes.append(line[7:])
            elif line.startswith("author "):
                author_parts = line[7:].rsplit(" ", 2)
                author = author_parts[0]
                timestamp = int(author_parts[1])
            elif line.startswith("committer "):
                committer_parts = line[10:].rsplit(" ", 2)
                committer = committer_parts[0]
            elif line == "":
                message_start = i + 1
                break

        message = "\n".join(lines[message_start:])
        return cls(tree_hash, parent_hashes, author, committer, message, timestamp)


class Repository:
    """Core repository manager handling object store, staging index, and references."""

    def __init__(self, path=".", git_dir_name=".git"):
        self.path = Path(path).resolve()
        self.git_dir = self.path / git_dir_name
        # .git/objects
        self.objects_dir = self.git_dir / "objects"
        # .git/refs
        self.ref_dir = self.git_dir / "refs"
        self.heads_dir = self.ref_dir / "heads"
        # HEAD file
        self.head_file = self.git_dir / "HEAD"
         # .git/index
        self.index_file = self.git_dir / "index"

    def init(self) -> bool:
        if self.git_dir.exists():
            return False
        # create directories
        self.git_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(exist_ok=True)
        self.ref_dir.mkdir(exist_ok=True)
        self.heads_dir.mkdir(exist_ok=True)
        # create initial HEAD pointing to a branch
        self.head_file.write_text("ref: refs/heads/master\n")
        self.save_index({})
        print(f"Initialized empty Git repository in {self.git_dir}")
        return True

    def store_object(self, obj: GitObject) -> str:
        obj_hash = obj.hash()
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        if not obj_file.exists():
            obj_dir.mkdir(exist_ok=True)
            obj_file.write_bytes(obj.serialize())

        return obj_hash

    def load_index(self) -> Dict[str, str]:
        if not self.index_file.exists():
            return {}
        try:
            return json.loads(self.index_file.read_text())
        except Exception:
            return {}

    def save_index(self, index: Dict[str, str]):
        self.index_file.write_text(json.dumps(index, indent=2))

    def add_file(self, path: str):
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found")
        # Read the file content
        content = full_path.read_bytes()
         # Create BLOB object from the content
        blob = Blob(content)
        # store the blob object in database (.git/objects)
        blob_hash = self.store_object(blob)
         # Update index to include the file
        index = self.load_index()
        index[path] = blob_hash
        self.save_index(index)
        print(f"Staged {path}")

    def add_directory(self, path: str):
        full_path = self.path / path
        if not full_path.exists() or not full_path.is_dir():
            raise ValueError(f"Directory {path} not found or invalid")

        index = self.load_index()
        added_count = 0

        for file_path in full_path.rglob("*"):
            if file_path.is_file():
                if self.git_dir.name in file_path.parts:
                    continue
                # create & store blob object
                content = file_path.read_bytes()
                blob = Blob(content)
                blob_hash = self.store_object(blob)
                 # update index
                rel_path = str(file_path.relative_to(self.path)).replace("\\", "/")
                index[rel_path] = blob_hash
                added_count += 1

        self.save_index(index)
        print(f"Staged {added_count} files from directory '{path}'")

    def add_path(self, path: str) -> None:
        full_path = self.path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found")

        if full_path.is_file():
            self.add_file(path)
        elif full_path.is_dir():
            self.add_directory(path)
        else:
            raise ValueError(f"{path} is neither a file nor a directory")
        

    def load_object(self, obj_hash: str) -> GitObject:
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        if not obj_file.exists():
            raise FileNotFoundError(f"Object {obj_hash} not found")

        return GitObject.deserialize(obj_file.read_bytes())

    def create_tree_from_index(self) -> str:
        index = self.load_index()
        if not index:
            return self.store_object(Tree())

        dirs: Dict = {}
        files: Dict = {}

        for file_path, blob_hash in index.items():
            parts = file_path.replace("\\", "/").split("/")
            if len(parts) == 1:
                files[parts[0]] = blob_hash
            else:
                dir_name = parts[0]
                if dir_name not in dirs:
                    dirs[dir_name] = {}

                current = dirs[dir_name]
                for part in parts[1:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                current[parts[-1]] = blob_hash

        def create_tree_recursive(entries_dict: Dict) -> str:
            tree = Tree()
            for name, blob_hash in entries_dict.items():
                if isinstance(blob_hash, str):
                    tree.add_entry("100644", name, blob_hash)
                elif isinstance(blob_hash, dict):
                    subtree_hash = create_tree_recursive(blob_hash)
                    tree.add_entry("40000", name, subtree_hash)
            return self.store_object(tree)

        root_entries = {**files}
        for dir_name, dir_contents in dirs.items():
            root_entries[dir_name] = dir_contents

        return create_tree_recursive(root_entries)

    def get_current_branch(self) -> str:
        if not self.head_file.exists():
            return "master"

        head_content = self.head_file.read_text().strip()
        if head_content.startswith("ref: refs/heads/"):
            return head_content[16:]
        return "HEAD"

    def get_branch_commit(self, current_branch: str) -> Optional[str]:
        branch_file = self.heads_dir / current_branch
        if branch_file.exists():
            return branch_file.read_text().strip()
        return None

    def set_branch_commit(self, current_branch: str, commit_hash: str):
        branch_file = self.heads_dir / current_branch
        branch_file.write_text(commit_hash + "\n")

    def commit(self, message: str, author: str = "WebClub Contributor <dev@nitk.edu>"):
        tree_hash = self.create_tree_from_index()
        current_branch = self.get_current_branch()
        parent_commit = self.get_branch_commit(current_branch)
        parent_hashes = [parent_commit] if parent_commit else []

        index = self.load_index()
        if not index:
            print("nothing to commit, working tree clean")
            return None

        if parent_commit:
            parent_git_commit_obj = self.load_object(parent_commit)
            parent_commit_data = Commit.from_content(parent_git_commit_obj.content)
            if tree_hash == parent_commit_data.tree_hash:
                print("nothing to commit, working tree clean")
                return None

        commit = Commit(
            tree_hash=tree_hash,
            parent_hashes=parent_hashes,
            author=author,
            committer=author,
            message=message,
        )
        commit_hash = self.store_object(commit)
        self.set_branch_commit(current_branch, commit_hash)

        print(f"[{current_branch} {commit_hash[:7]}] {message}")
        return commit_hash

    def get_files_from_tree_recursive(self, tree_hash: str, prefix: str = "") -> Set[str]:
        files = set()
        try:
            tree_obj = self.load_object(tree_hash)
            tree = Tree.from_content(tree_obj.content)
            # list<tuple<str, str, str>>
            for mode, name, obj_hash in tree.entries:
                full_name = f"{prefix}{name}"
                if mode.startswith("100"):
                    files.add(full_name)
                elif mode.startswith("400"):
                    subtree_files = self.get_files_from_tree_recursive(
                        obj_hash, f"{full_name}/"
                    )
                    files.update(subtree_files)
        except Exception as e:
            print(f"Warning: Could not read tree {tree_hash}: {e}")
        return files

    def restore_tree(self, tree_hash: str, path: Path):
        tree_obj = self.load_object(tree_hash)
        tree = Tree.from_content(tree_obj.content)
        for mode, name, obj_hash in tree.entries:
            file_path = path / name
            if mode.startswith("100"):
                blob_obj = self.load_object(obj_hash)
                blob = Blob(blob_obj.content)
                file_path.write_bytes(blob.content)
            elif mode.startswith("400"):
                file_path.mkdir(exist_ok=True)
                self.restore_tree(obj_hash, file_path)

    def restore_working_directory(self, branch: str, files_to_clear: Set[str]):
        target_commit_hash = self.get_branch_commit(branch)
        if not target_commit_hash:
            return
        # remove files tracked by previous branch
        for rel_path in sorted(files_to_clear):
            file_path = self.path / rel_path
            try:
                if file_path.is_file():
                    file_path.unlink()
            except Exception:
                pass

        target_commit_obj = self.load_object(target_commit_hash)
        target_commit = Commit.from_content(target_commit_obj.content)

        if target_commit.tree_hash:
            self.restore_tree(target_commit.tree_hash, self.path)

    def checkout(self, branch: str, create_branch: bool):
        previous_branch = self.get_current_branch()
        files_to_clear: Set[str] = set()
        previous_commit_hash = self.get_branch_commit(previous_branch)

        try:
            if previous_commit_hash:
                prev_commit_object = self.load_object(previous_commit_hash)
                prev_commit = Commit.from_content(prev_commit_object.content)
                if prev_commit.tree_hash:
                    files_to_clear = self.get_files_from_tree_recursive(
                        prev_commit.tree_hash
                    )
        except Exception:
            files_to_clear = set()

        branch_file = self.heads_dir / branch
        if not branch_file.exists():
            if create_branch:
                if previous_commit_hash:
                    self.set_branch_commit(branch, previous_commit_hash)
                    print(f"Created new branch '{branch}'")
                else:
                    print("No commits yet, cannot create a branch")
                    return
            else:
                print(f"Branch '{branch}' not found.")
                return

        self.head_file.write_text(f"ref: refs/heads/{branch}\n")
        self.restore_working_directory(branch, files_to_clear)
        print(f"Switched to branch '{branch}'")

    def branch(self, branch_name: Optional[str] = None, delete: bool = False):
        if delete and branch_name:
            branch_file = self.heads_dir / branch_name
            if branch_file.exists():
                branch_file.unlink()
                print(f"Deleted branch {branch_name}")
            else:
                print(f"Branch {branch_name} not found")
            return

        current_branch = self.get_current_branch()
        if branch_name:
            current_commit = self.get_branch_commit(current_branch)
            if current_commit:
                self.set_branch_commit(branch_name, current_commit)
                print(f"Created branch {branch_name}")
            else:
                print("No commits yet, cannot create a new branch")
        else:
            branches = []
            for branch_file in self.heads_dir.iterdir():
                if branch_file.is_file() and not branch_file.name.startswith("."):
                    branches.append(branch_file.name)

            for b in sorted(branches):
                prefix = "* " if b == current_branch else "  "
                print(f"{prefix}{b}")

    def log(self, max_count: int = 10):
        current_branch = self.get_current_branch()
        commit_hash = self.get_branch_commit(current_branch)

        if not commit_hash:
            print("No commits yet!")
            return

        count = 0
        while commit_hash and count < max_count:
            commit_obj = self.load_object(commit_hash)
            commit = Commit.from_content(commit_obj.content)

            print(f"commit {commit_hash}")
            print(f"Author: {commit.author}")
            print(f"Date:   {time.ctime(commit.timestamp)}")
            print(f"\n    {commit.message}\n")

            commit_hash = commit.parent_hashes[0] if commit.parent_hashes else None
            count += 1

    def build_index_from_tree(self, tree_hash: str, prefix: str = "") -> Dict[str, str]:
        index = {}
        try:
            tree_obj = self.load_object(tree_hash)
            tree = Tree.from_content(tree_obj.content)
            for mode, name, obj_hash in tree.entries:
                full_name = f"{prefix}{name}"
                if mode.startswith("100"):
                    index[full_name] = obj_hash
                elif mode.startswith("400"):
                    subindex = self.build_index_from_tree(obj_hash, f"{full_name}/")
                    index.update(subindex)
        except Exception as e:
            print(f"Warning: Could not read tree {tree_hash}: {e}")
        return index

    def get_all_files(self) -> List[Path]:
        files = []
        for item in self.path.rglob("*"):
            if self.git_dir.name in item.parts:
                continue
            if item.is_file():
                files.append(item)
        return files

    def status(self):
        current_branch = self.get_current_branch()
        print(f"On branch {current_branch}")
        index = self.load_index()
        current_commit_hash = self.get_branch_commit(current_branch)

        last_index_files = {}
        if current_commit_hash:
            try:
                commit_obj = self.load_object(current_commit_hash)
                commit = Commit.from_content(commit_obj.content)
                if commit.tree_hash:
                    last_index_files = self.build_index_from_tree(commit.tree_hash)
            except Exception:
                last_index_files = {}

        working_files = {}
        for item in self.get_all_files():
            rel_path = str(item.relative_to(self.path)).replace("\\", "/")
            try:
                content = item.read_bytes()
                blob = Blob(content)
                working_files[rel_path] = blob.hash()
            except Exception:
                continue

        staged_files = []
        unstaged_files = []
        untracked_files = []
        deleted_files = []
        # what files are staged for commit
        for file_path in set(index.keys()) | set(last_index_files.keys()):
            index_hash = index.get(file_path)
            last_index_hash = last_index_files.get(file_path)

            if index_hash and not last_index_hash:
                staged_files.append(("new file", file_path))
            elif index_hash and last_index_hash and index_hash != last_index_hash:
                staged_files.append(("modified", file_path))

        if staged_files:
            print("\nChanges to be committed:")
            for stage_status, file_path in sorted(staged_files):
                print(f"   {stage_status}: {file_path}")
        # what files have modified but not staged
        for file_path in working_files:
            if file_path in index and working_files[file_path] != index[file_path]:
                unstaged_files.append(file_path)

        if unstaged_files:
            print("\nChanges not staged for commit:")
            for file_path in sorted(unstaged_files):
                print(f"   modified: {file_path}")
        # what files are untracked
        for file_path in working_files:
            if file_path not in index and file_path not in last_index_files:
                untracked_files.append(file_path)

        if untracked_files:
            print("\nUntracked files:")
            for file_path in sorted(untracked_files):
                print(f"   {file_path}")
        # what files have been deleted
        for file_path in index:
            if file_path not in working_files:
                deleted_files.append(file_path)

        if deleted_files:
            print("\nDeleted files:")
            for file_path in sorted(deleted_files):
                print(f"   deleted: {file_path}")

        if not staged_files and not unstaged_files and not deleted_files and not untracked_files:
            print("\nnothing to commit, working tree clean")


def main():
    parser = argparse.ArgumentParser(description="Git Client Implementation")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("init", help="Initialize a repository")
     # add command
    add_parser = subparsers.add_parser("add", help="Add files or directories to staging")
    add_parser.add_argument("paths", nargs="+", help="Paths to add")
    # commit command
    commit_parser = subparsers.add_parser("commit", help="Commit staged changes")
    commit_parser.add_argument("-m", "--message", required=True, help="Commit message")
    commit_parser.add_argument("--author", help="Author string")
    # checkout command
    checkout_parser = subparsers.add_parser("checkout", help="Switch or create branches")
    checkout_parser.add_argument("branch", help="Target branch")
    checkout_parser.add_argument("-b", "--create-branch", action="store_true", help="Create new branch")
    # branch command
    branch_parser = subparsers.add_parser("branch", help="List or delete branches")
    branch_parser.add_argument("name", nargs="?")
    branch_parser.add_argument("-d", "--delete", action="store_true", help="Delete branch")
    # log command
    log_parser = subparsers.add_parser("log", help="Display commit history")
    log_parser.add_argument("-n", "--max-count", type=int, default=10, help="Max commits")

    subparsers.add_parser("status", help="Show working tree status")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    repo = Repository()
    try:
        if args.command == "init":
            if not repo.init():
                print("Repository already exists")
        elif args.command == "add":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            for path in args.paths:
                repo.add_path(path)
        elif args.command == "commit":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            author = args.author or "WebClub Contributor <dev@nitk.edu>"
            repo.commit(args.message, author)
        elif args.command == "checkout":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.checkout(args.branch, args.create_branch)
        elif args.command == "branch":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.branch(args.name, args.delete)
        elif args.command == "log":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.log(args.max_count)
        elif args.command == "status":
            if not repo.git_dir.exists():
                print("Not a git repository")
                return
            repo.status()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()