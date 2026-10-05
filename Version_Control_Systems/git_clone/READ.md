
# PyGit — Custom Version Control System

A lightweight Version Control System (VCS) implemented in Python from scratch. PyGit recreates core Git functionality, including object storage, staging, commits, branches, checkout, and working tree status tracking.

##  Features

- **Git-style directory structure:** Stores objects, references, branch heads, and index metadata.
- **Content-addressable storage:** Uses SHA-1 hashing and zlib compression for blob, tree, and commit objects.
- **Staging area:** Tracks staged additions, modifications, and deletions.
- **Branch management:** Supports branch creation, listing, deletion, and checkout.
- **Working tree status:** Reports staged changes, unstaged modifications, untracked files, and deletions.

##  Architecture

### Git Objects

- **Blob:** Stores raw file contents.
- **Tree:** Represents directory entries and their object hashes.
- **Commit:** Stores a tree hash, parent commit information, author metadata, timestamp, and commit message.

### Storage Layout

```text
.git/
├── HEAD
├── index
├── objects/
└── refs/
    └── heads/
```

##  Getting Started

### Prerequisites

- Python 3.8 or later
- Standard Python libraries: argparse, hashlib, json, pathlib, sys, time, typing, zlib

### Clone the Repository

```bash
git clone https://github.com/WebClub-NITK/Systems-and-Security-SIG-Recruitment-2026
cd Systems-and-Security-SIG-Recruitment-2026/Version_Control_Systems/git_clone
```


##  CLI Usage

### 1. Initialize a Repository

```bash
python Main.py init
```

### 2. Stage Files

```bash
# Stage one file
python Main.py add filename.txt

# Stage all supported files in the current directory
python Main.py add .
```

### 3. Check Status

```bash
python Main.py status
```

### 4. Create a Commit

```bash
python Main.py commit -m "Initial project commit"
```

```bash
python Main.py commit -m "Custom author commit" --author "shaleeth2008 <shaleeth2008@gmail.com>"
```

### 5. View Commit History

```bash
python Main.py log

# Display the latest five commits
python Main.py log -n 5
```

### 6. Manage Branches

```bash
# List branches
python Main.py branch

# Create a branch
python Main.py branch feature-xyz

# Delete a branch
python Main.py branch -d feature-xyz
```

### 7. Switch Branches

```bash
# Switch to an existing branch
python Main.py checkout feature-xyz

# Create and switch to a branch
python Main.py checkout -b feature-xyz
```

Check that the commands and options above match your actual implementation before submitting.

##  Recruitment Details

-**DEMO VIDEO LINK:** https://drive.google.com/file/d/1NE2m7jatGjny-mRPZYAdFhZk6yOSGfW-/view?usp=sharing
- **SIG:** WebClub Systems and Security SIG
- **Task:** Version Control System Client Implementation
- **Language:** Python 3
