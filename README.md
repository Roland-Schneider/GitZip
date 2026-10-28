# GitZip
Pack together the net changes from the current (feature or bugfix) branch of a local repository in a ZIP-file.

While developing code, it is sometimes desirable to create a backup of the current changes of the files and store it in a secure location outside the local Git repository. A local commit is often insufficient and unsuitable for this purpose.  

The standard recommendation for backups is to either commit the changes to the remote server or create a complete copy of the local repository and package it as a ZIP-file; see also
<https://docs.github.com/en/repositories/archiving-a-github-repository/backing-up-a-repository>.  
However, committing to the remote server might not be reasonable for unfinished code, and a ZIP-file of the entire local repository can end up being huge.  

The GitZip program identifies the modified files in the local repository and saves only those files in a ZIP file along with their original versions.   
Additionally a file containing metadata about the repository and the modified files is added to the ZIP file.

The application was tested in Windows (Windows 10, Python 3.13.7) and Linux (Linux Mint 22.3 Zena, Python 3.12.3).

    usage: GitZip.py [-h] [--unstaged_only | --staged_and_committed] [--no_previous_versions] out_location

    Pack together all current changes in a git repository with previous versions for reference

    positional arguments:
      out_location

    options:
      -h, --help            show this help message and exit
      --unstaged_only
      --staged_and_committed
      --no_previous_versions
