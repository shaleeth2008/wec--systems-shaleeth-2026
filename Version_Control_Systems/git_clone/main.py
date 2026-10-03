import argparse
import json
from pathlib import Path
import sys

class GitObject:
    def __init__(self,obj_type: str,content: bytes):
        self.type=obj_type
        self.content = content
    def hash(self)-> str:
        #f(<type><size>\0<content>)
        header=f"{self.type} {len(self.content)}\0".encode()
        return hashlib.sha1(header+self.content).hexdigest()
    def serialize(self)->bytes:
        header=f"{self.type} {len(self.content)}\0".encode()
        return zlib.compress(header+self.content)
    @classmethod
    def deserialize(cls,data: bytes)->"GitObject":
        decompressed=zlib.decompress(data)
        null_idx=decompressed.find(b"\0")
        header=decompressed[:null_idx]
        content=decompressed[null_idx+1:]
        obj_type,_=header.split(" ")
        return cls(obj_type, content)
    class Blob(GitObject):
        def __init__(self, content:bytes):
            super().__init("blob",content)
        def get_content(self) ->bytes:
            return self.content 
                
                            
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

    def store_object(self,obj: GitObject)->str:
        obj_hash=obj.hash()
        obj_dir=self.objects_dir/obj_hash[:2]
        obj_file=obj_dir/obj_hash[2:]
        if not obj_file.exists():
            obj_dir.mkdir(exist_ok=True)
            obj_file.write_bytes(obj.serialize())
        return obj_hash

    def add_file(self,path:str):
        full_path=self.path/path
        if not full_path.exists():
                    raise FaileNotFoundError(f"Path {full_path} not found")
        #read the file con
        content=full_path.read_bytes()
        #create blob object
        blob=Blob(content)
        #store the blob object in data base
        #update index to include file

    def add_path(self,path:str)->None:
        full_path = self.path/path
        if not full_path.exists():
            raise FaileNotFoundError(f"Path {full_path} not found")
        if full_path.is_file():
            self.add_file(path)
        elif full_path.is_dir():
            self.add_directory(path)
        else:
            raise ValueError(f"{full_path} is neither a file nor a directory")

def main():
    parser = argparse.ArgumentParser(description="PyGit - A simple git clone!")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    #add command
    add_parser= subparsers.add_parser("add",help="Add Files and Directories to staging area")
    add_parser.add_argument("paths",nargs="+",help="Add Files and Directories")
    args = parser.parse_args() 
    if not args.command:
        parser.print_help()
        return
    repo = Repository()
    try:
        if args.command == "init":
            if not repo.init():
                print("Repository already exists")
                return
            elif args.command=="add":
                if not repo.git_directory.exists():
                    print("Not a git repository")
                    return
                for path in args.paths:
                    repo.add_path(path)

            if not repo.init():
                print("Repository already exists")
                return 
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()