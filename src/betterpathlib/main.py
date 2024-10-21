import datetime
import inspect
import os
import shlex
import shutil
import subprocess
import tempfile
import urllib
from pathlib import Path as PathlibPath
from typing import Any, Callable, Iterable, NamedTuple, Sequence

from betterpathlib.utils import bytes2human

DiskUsageHuman = NamedTuple("usage", [("total", str), ("used", str), ("free", str)])


class Path(type(PathlibPath())):
    # The weird subclassing is in order to make sure it subclasses from PosixPath
    # on Posix systems (Linux, Mac) and from WindowsPath on Windows systems.
    def __new__(cls, *pathsegments):
        return super().__new__(cls, *pathsegments)

    """
    An extension to Pythons built-in pathlib.Path.

    Provides convenience methods and methods for working with numerical suffixes.
    It also provide shortcuts to Pythons built-in functions from tempfile and shutil,
    but in a Path friendly manner.
    """

    def glob_ignorecase(self, pattern: str) -> list["Path"]:
        """
        Glob ignoring case

        Parameters
        ----------
            pattern (str): The glob pattern to match against.

        Returns
        -------
            List[Path]: A list of Path objects that match the pattern, ignoring case.

        Example
        -------
        >>> Path(__file__).glob_ignorecase("*")  # doctest: +SKIP
        [Path('../.git'),
         Path('../.gitignore'),
         Path('../LICENSE'),
         Path('../README.md'),
         Path('../betterpathlib'),
         Path('../setup.py')]

        >>> Path(__file__).glob_ignorecase("readme*")  # doctest: +SKIP
        [Path('../README.md')]
        """
        path = self.parent if self.is_file() else self

        def either(c):
            return "[%s%s]" % (c.lower(), c.upper()) if c.isalpha() else c

        if "*" not in pattern:
            pattern = f"*{pattern}*"
        return sorted(list(path.glob("".join(map(either, pattern)))))

    def most_similar_path(self, recursive: bool = False) -> "Path | None":
        """
        Return the path with the most similar name. Requires module
        `thefuzz` which is included when betterpathlib is installed
        with the feature flag betterpathlib[similarpaths].

        Parameters
        ---------
            recursive (bool): Whether to search recursively in subdirectories. Default is False.

        Returns
        -------
            Path | None: The path with the most similar name, or None if no similar paths are found.
        """
        from thefuzz import fuzz

        pattern = "**/*" if recursive else "*"
        candidates = [p for p in self.parent.glob(pattern) if p != self]
        if not candidates:
            return None
        similarities = [
            fuzz.partial_ratio(self.name, p.name) + fuzz.ratio(self.name, p.name)
            for p in candidates
        ]
        most_similar = max(zip(candidates, similarities), key=lambda tup: tup[1])[0]
        return most_similar

    def mtime(self) -> datetime.datetime:
        """
        Last modification time, as datetime
        """
        return datetime.datetime.fromtimestamp(self.stat().st_mtime)

    def modtime(self) -> str:
        """
        Last modification time, as a nice string
        """
        dt = datetime.datetime.fromtimestamp(self.stat().st_mtime)
        return dt.strftime("%Y-%m-%d %H:%M")

    def prepend_suffix(self, suffix: str) -> "Path":
        """
        Prepend a suffix to the path

        Parameters
        ----------
            suffix (str): The suffix to prepend.

        Returns
        -------
            Path: A new Path object with the suffix prepended.

        Example
        -------
        >>> Path('pathtools.py.xx').prepend_suffix('.new')
        Path('pathtools.new.py.xx')
        """
        suffix = suffix if suffix.startswith(".") else "." + suffix
        base = self.name[: self.name.find(".")]
        return self.with_name(base + "".join([suffix] + self.suffixes))

    def has_numerical_suffix(self) -> bool:
        """
        Check if the path has an all-digit extension.

        Example
        -------
        >>> Path("myfile.x.001").has_numerical_suffix()
        True
        >>> Path("myfile.x.001.feather").has_numerical_suffix()
        True
        """
        for s in self.suffixes:
            if s[1:].isdigit():
                return True
        return False

    def has_primary_numerical_suffix(self) -> bool:
        """
        Returns True if the last suffix is all digits.

        Example
        -------
        >>> Path("myfile.x.001").has_primary_numerical_suffix()
        True
        >>> Path("myfile.x.001.feather").has_primary_numerical_suffix()
        False
        """
        if self.suffixes[-1][1:].isdigit():
            return True
        return False

    def get_numerical(self) -> str | None:
        """
        Return the first numerical extension

        Example
        -------
        >>> Path('myfile.001').get_numerical()
        ".001"
        """
        for s in self.suffixes:
            if s[1:].isdigit():
                return s
        return None

    def get_numerical_int(self) -> int | None:
        """
        Return the number of the first numerical extension

        Example
        -------
        >>> Path('myfile.001').get_numerical()
        1
        """
        for s in self.suffixes:
            if s[1:].isdigit():
                return int(s[1:])
        return None

    def increase_numerical_width(self, n_digs: int = 4) -> "Path":
        """
        Pad the numerical suffix with `n_digs` zeroes

        Example
        -------
        >>> Path('myfile.rar.001').increase_numerical_width(4)
        Path('myfile.rar.0001')
        """
        if not self.has_numerical_suffix():
            raise ValueError(f"{self} has no numerical suffix")
        n = self.suffix[1:]
        path = self.with_suffix("." + n.zfill(n_digs))
        return path

    def make_numerical_suffix_nonprimary(self) -> "Path":
        """
        Shift the numerical extension as not to become the last (primary) extension

        Example
        -------
        >>> Path("myfile.x.feather.001").make_numerical_suffix_nonprimary()
        Path('myfile.x.001.feather')
        """
        ext = self.suffixes[-1]
        if not ext[1:].isdigit():
            raise ValueError(f"{self} Does not have a primary numerical primary suffix")
        suffixes = self.suffixes.copy()
        del suffixes[-1]
        suffixes.insert(len(suffixes) - 1, ext)
        return self.with_suffixes(suffixes)

    def make_numerical_suffix_primary(self) -> "Path":
        """
        Shift the numerical suffix to become the last (i.e. primary extension)

        Example
        -------
        >>> Path("myfile.x.001.feather").make_numerical_suffix_primary()
        Path('myfile.x.feather.001')
        """
        if not self.has_numerical_suffix():
            raise ValueError(f"{self} has no numerical suffix")
        ix, ext = 0, self.suffixes[0]
        for i, s in enumerate(self.suffixes):
            if s[1:].isdigit():
                ix = i
                ext = s
                break
        suffixes = self.suffixes.copy()
        del suffixes[ix]
        suffixes.append(ext)
        return self.with_suffixes(suffixes)

    def size(self) -> int:
        """
        Size of file in bytes
        """
        return self.stat().st_size

    def size_kb(self) -> float:
        """
        Size of file in kilobytes
        """
        return self.size() / 1000

    def size_kib(self) -> float:
        """
        Size of file in kibibytes
        """
        return self.size() / 1024

    def size_mb(self) -> float:
        """
        Size of file in megabytes
        """
        return self.size_kb() / 1000

    def size_mib(self) -> float:
        """
        Size of file in mebibytes
        """
        return self.size_kb() / 1024

    def size_gb(self) -> float:
        """
        Size of file in gigabytes
        """
        return self.size_mb() / 1000

    def size_gib(self) -> float:
        """
        Size of file in gibibytes
        """
        return self.size_mb() / 1024

    def size_human(self) -> str:
        """
        Size of file in human readable format
        """
        return bytes2human(self.size())

    sizeh = size_human
    sizeh.__doc__ = "Alias for `size_human`.\n" + size_human.__doc__  # type: ignore

    def disk_usage(self) -> tuple[int, int, int]:
        """
        The disk size, the amount of used and free space on the disk of this path, in bytes.
        """
        return shutil.disk_usage(self)

    du = disk_usage
    du.__doc__ = "Alias for `disk_usage`.\n" + disk_usage.__doc__  # type: ignore

    def disk_usage_human(self) -> DiskUsageHuman:
        """
        The disk size, the amount of used and free space on the disk of this path, in human readable format (KiB, MiB, etc.).
        """
        return DiskUsageHuman(*map(bytes2human, shutil.disk_usage(self)))

    duh = disk_usage_human
    duh.__doc__ = "Alias for `disk_usage_human`.\n" + disk_usage.__doc__  # type: ignore

    def move(self, dst: "PathOrStr", overwrite: bool = False) -> "Path":
        """
        Recursively move a file or directory to another location. This is
        similar to the Unix "mv" command. Return the file or directory's
        destination.

        If dst already exists but is not a directory, it may be overwritten
        depending `overwrite`.

        Returns
        -------
        The destination path
        """
        dst = Path(dst)
        if dst.exists() and dst.is_file() and not overwrite:
            raise FileExistsError(dst)
        return Path(shutil.move(self, dst))

    mv = move
    mv.__doc__ = "Alias for `move`.\n" + move.__doc__  # type: ignore

    rmtree = shutil.rmtree
    chown = shutil.chown

    def copy(self, dst: "PathOrStr", dirs_exist_ok=False) -> "Path":
        """
        Copy data to the destination.

        If the source path is a directory then it is recursively copied.
        If the source path is a directory and `dirs_exist_ok` is False (the default) and `dst` already exists, a
        `FileExistsError` is raised. If `dirs_exist_ok` is True, the copying
        operation will continue if it encounters existing directories, and files
        within the `dst` tree will be overwritten by corresponding files from the
        `src` tree.

        Returns
        -------
        The destination path
        """
        dst = Path(dst)
        if self.is_dir():
            return Path(shutil.copytree(src=self, dst=dst, dirs_exist_ok=dirs_exist_ok))
        return Path(shutil.copy2(self, dst))

    cp = copy
    cp.__doc__ = "Alias for `copy`.\n" + copy.__doc__  # type: ignore

    def ls(
        self,
        args: list[str] | str = [
            "-g",
            "--almost-all",
            "--group-directories-first",
            "--human-readable",
        ],
    ) -> None:
        """
        Run the `ls` Linux command to list files.
        """
        path = str(self.resolve())
        if isinstance(args, str):
            args = shlex.split(args)
        subprocess.run(["ls"] + args + [path])

    def listdir(self, sort: bool = True) -> Sequence["Path"]:
        """List all file in the directory"""
        paths = list(self.iterdir())
        if sort:
            paths.sort()
        return paths

    def join(self, *pathsegments: "str | Path") -> "Path":
        """Alias for `joinpath`.

        Combine this path with one or several arguments, and return a
        new path representing either a subpath (if all arguments are relative
        paths) or a totally different path (if one of the arguments is
        anchored).
        """
        return self.joinpath(*pathsegments)

    def with_stem(self, stem: str) -> "Path":
        """
        Return a path with a new stem. Retains only the last file extension.

        Example
        -------
        >>> Path('somedir/info.py.bak').with_stem('view')
        Path('somedir/view.bak')
        """
        return self.with_name(stem + self.suffix)

    def with_rootname(self, name: str) -> "Path":
        """
        Return a path with a new root file name. Retains all file extensions.

        Example
        -------
        >>> Path('somedir/info.py.bak').with_rootname('view')
        Path('somedir/view.py.bak')
        """
        return self.with_name(name + "".join(self.suffixes))

    def with_parent(self, parent_path: "PathOrStr") -> "Path":
        """
        Change the parent directory of given file or folder

        Example:
        >>> Path('/etc/anaconda/conf.d').with_parent('/tmp')
        Path('/tmp/conf.d')
        >>> Path('/usr/share/applications/emacs.desktop').with_parent("~/.local/share/applications/")
        Path('~/.local/share/applications/emacs.desktop')
        """
        parent_path = Path(parent_path)
        return parent_path / self.name

    def with_user(self, user: str) -> "Path":
        """
        Path for a different user home directory

        Example
        -------
        >>> Path("/home/USER_1/somefile").with_user("USER_2")  # doctest: +SKIP
        Path('/home/USER_2/somefile')
        """
        return Path.home().parent / user / self.resolve().relative_to(Path.home())

    def add_suffix(self, suffix: str) -> "Path":
        """
        Add as last suffix

        Example
        -------
        >>> Path('add_polling_info.py').add_suffix('.bak')
        Path('add_polling_info.py.bak')
        """
        suffix = suffix if suffix.startswith(".") else "." + suffix
        return self.with_name(self.name + suffix)

    def append(self, suffix: str) -> "Path":
        """
        Append to stem.
        """
        return self.with_stem(self.stem + suffix)

    def with_suffixes(self, suffixes: Iterable[str]) -> "Path":
        """
        Replace current suffix(es) with the given suffixes

        Example:
        >>> Path("file.suffix1.suffix2").with_suffixes([".mkv", ".r00"])
        Path('file.mkv.r00')
        """
        suffixes = [x if x.startswith(".") else "." + x for x in suffixes]
        return self.without_suffixes().with_suffix("".join(suffixes))

    def without_suffix(self, suffix: str | None = None) -> "Path":
        """
        Remove a suffix from path. If no suffix is specified, then the last suffix is removed.

        Example:
        >>> Path('add_polling_info.py.bak.new').without_suffix('.bak')
        Path('add_polling_info.py.new')
        """
        if suffix:
            suffix = suffix if suffix.startswith(".") else "." + suffix
            return self.without_suffixes().with_suffix(
                "".join(s for s in self.suffixes if s != suffix)
            )
        return self.without_suffixes().with_suffixes(self.suffixes[:-1])

    def without_suffixes(self) -> "Path":
        """
        Remove all suffixes from from the path.
        Example:
        >>> Path('add_polling_info.py.bak.new').without_suffixes()
        Path('add_polling_info')
        """
        ix = self.stem.find(".")
        if ix > -1:
            name = self.stem[:ix]
        else:
            name = self.stem
        return self.parent / name

    def next_unused_path(self, start: int = 0, n_digs: int = 3) -> "Path":
        """
        Return the next path with a numerical suffix that does not exist.

        Example
        -------
        >>> import tempfile
        >>> dir_ = Path(tempfile.gettempdir())
        >>> (dir_ / 'somefile.rar.001').touch()
        >>> (dir_ / 'somefile.rar.003').touch()
        >>> (dir_ / 'somefile.rar.004').touch()
        >>> (dir_ / 'somefile.rar.001').next_unused_path()
        Path('/tmp/somefile.rar.002')
        >>> (dir_ / 'somefile.rar.003').next_unused_path()
        Path('/tmp/somefile.rar.005')
        """
        ext = self.suffix[1:]
        path = self
        if ext.isdigit():
            n_digs = len(ext)
            ext_i = int(ext) + 1
        else:
            path = self.add_suffix(".ph")  # placeholder to replace
            ext_i = start
        path = path.with_suffix("." + str(ext_i).zfill(n_digs))
        while path.exists():
            ext_i += 1
            path = path.with_suffix("." + str(ext_i).zfill(n_digs))
        return path

    def last_numerical_path(self) -> "Path":
        """
        Returns the last/highest numerical path

        Example
        -------
        >>> import tempfile
        >>> dir_ = Path(tempfile.gettempdir())
        >>> p1 = dir_ / 'somefile.rar.001'
        >>> (dir_ / 'somefile.rar.004').touch()
        >>> p1.last_numerical_path()
        Path('/tmp/somefile.rar.004')
        """
        path = self
        suffix = path.suffixes[-1][1:]
        if suffix.isdigit():
            path = path.without_suffix(suffix)
        candidates = path.parent.glob(path.name + ".*")
        best = path
        best_n = 0
        for p in candidates:
            suffix = p.suffixes[-1][1:]
            if suffix.isdigit() and int(suffix) >= best_n:
                best = p
                best_n = int(suffix)
        if not best.exists():
            raise FileNotFoundError(
                f"No files with numerical suffix starting with {self} exists"
            )
        return best

    def or_download(self, url, progress_bar=False, **kwargs) -> "Path":
        """
        Download file atomically if it doesn't exist locally.
        A progress bar is shown if `progress_bar` is True.
        If the Path is a directory, then the file_name is inferred from the URL.
        The Path for the destination file is returned.

        Additional keyword-arguments are passed to `requests.get`

        Requires `requests` and `tqdm`, if progress_bar is True.
        These two modules are included with the feature flag
        betterpath[dowwnload]
        """

        def download(url, file_path, progress_bar, **kwargs):
            import requests

            tmp_file_path = self.parent / f"{self.name}.tmp"
            if progress_bar:
                from tqdm import tqdm

                # Streaming, so we can iterate over the response
                resp = requests.get(url, stream=True, **kwargs)
                resp.raise_for_status()

                # Sizes in bytes.
                total_size = int(resp.headers.get("content-length", 0))
                block_size = 1024

                print(f"Download {file_path=} from {url=}")
                with tqdm(total=total_size, unit="B", unit_scale=True) as _progress_bar:
                    # Atomic write
                    try:
                        with open(tmp_file_path, "wb") as file:
                            for data in resp.iter_content(block_size):
                                _progress_bar.update(len(data))
                                file.write(data)
                            tmp_file_path.replace(file_path)
                    finally:
                        if tmp_file_path.exists():
                            tmp_file_path.unlink()

                    if total_size != 0 and _progress_bar.n != total_size:
                        raise requests.exceptions.RequestException(
                            f"Could not download file {file_path=} from {url=}"
                        )
            else:
                resp = requests.get(url, **kwargs)
                resp.raise_for_status()
                # Atomic write
                try:
                    with open(tmp_file_path, "wb") as f:
                        f.write(resp.content)
                    tmp_file_path.replace(file_path)
                finally:
                    if tmp_file_path.exists():
                        tmp_file_path.unlink()

        if self.is_dir():
            parsed_url = urllib.parse.urlparse(url)
            file_name = Path(urllib.parse.unquote(parsed_url.path)).name
            if not file_name:
                raise ValueError(f"Could not determine filename from {url=}")

            file_path = self / file_name
            if not file_path.exists():
                download(url, file_path, progress_bar, **kwargs)
            return file_path
        elif not self.exists():
            download(url, self, progress_bar, **kwargs)
            return self
        return self

    def read_json(self, **kwargs) -> Any:
        """Read a JSON file. Additional keyword-arguments will be passed to json.load"""
        import json

        with open(self, "r") as fp:
            return json.load(fp, **kwargs)

    def write_json(self, obj, **kwargs) -> None:
        """Write JSON file. Additional keyword-arguments will be passed to json.dump"""
        import json

        with open(self, "w") as fp:
            json.dump(obj, fp, **kwargs)

    def read_pickle(self, **kwargs) -> Any:
        """Read the pickled representation of the object."""

        import pickle

        with open(self, "rb") as fil:
            return pickle.load(fil, **kwargs)

    def write_pickle(self, obj, **kwargs) -> None:
        """Write the pickled representation of the object obj to the path. Additional keyword-arguments will be passed to pickle.dump"""

        import pickle

        with open(self, "wb") as fil:
            pickle.dump(obj, fil, **kwargs)

    def atomic_write(self, data: str | bytes, mode: str = "w", **kwargs: Any) -> None:
        """
        Write data atomically to avoid partial writes.

        Args:
            data: Content to write
            mode: File open mode ('w' for text, 'wb' for binary)
            **kwargs: Additional arguments passed to open()

        Raises:
            OSError: If write fails
        """
        tmp = self.add_suffix(".tmp").next_unused_path().resolve()
        try:
            with open(tmp, mode, **kwargs) as f:
                f.write(data)
            tmp.replace(self)
        finally:
            if tmp.exists():
                tmp.unlink()

    def atomic_write_with(self, write_fn: Callable[[str], Any], **kwargs: Any) -> Any:
        """
        Write data atomically with the given function to avoid partial writes.

        Args:
            write_fn: A callable taking a Path in string form for writing data
            **kwargs: Additional arguments passed to write_fn

        Returns:
            The result from write_fn
        """
        tmp = self.add_suffix(".tmp").next_unused_path().resolve()
        try:
            result = write_fn(str(tmp), **kwargs)
            tmp.replace(self)
            return result
        finally:
            if tmp.exists():
                tmp.unlink()

    def is_same_file(self, other: "Path | str") -> bool:
        """Check if two paths point to the same file (following symlinks)."""
        try:
            return self.resolve() == Path(other).resolve()
        except (OSError, RuntimeError):
            return False

    def is_relative_to_home(self) -> bool:
        """Check if path is under user's home directory."""
        try:
            self.resolve().relative_to(Path.home())
            return True
        except ValueError:
            return False

    def chdir(self) -> None:
        """
        Change the current working directory to the specified path.

        On some platforms, path may also be specified as an open file descriptor.
        If this functionality is unavailable, using it raises an exception.
        """
        os.chdir(self)

    cd = chdir
    cd.__doc__ = "Alias for `chdir`.\n" + chdir.__doc__  # type: ignore

    def mkdir_(
        self, mode=0o777, parents: bool = False, exist_ok: bool = False
    ) -> "Path":
        """
        Create a new directory at this given path. Returns itself.
        """
        super().mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
        return self

    @classmethod
    def tempdir(cls) -> "Path":
        """Returns the system's temporary directory"""
        return Path(tempfile.gettempdir())

    @classmethod
    def mkdtemp(
        cls,
        suffix: str | None = None,
        prefix: str | None = None,
        dir: "Path | str | None" = None,
    ) -> "Path":
        """
        User-callable function to create and return a unique temporary
        directory.  The return value is the pathname of the directory.

        Arguments are as for mkstemp, except that the 'text' argument is
        not accepted.

        The directory is readable, writable, and searchable only by the
        creating user.

        Caller is responsible for deleting the directory when done with it.
        """
        return Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir))

    @classmethod
    def random_path(cls, prefix=None, suffix=None, dir=None) -> "Path":
        """
        Return a random, unused path. If `dir` is not given, then the path
        will be in a temporary directory.

        Example
        -------
        >>> Path.random_path("cat_image-", ".png")  # doctest: +SKIP
        Path('/tmp/cat_image-m3xx9q0q.png')
        """
        with tempfile.NamedTemporaryFile(
            prefix=prefix, suffix=suffix, dir=dir, delete=True
        ) as n:
            return Path(n.name)

    @classmethod
    def glob_cwd(cls, pattern: str = "", ignorecase: bool = False) -> list["Path"]:
        """Glob the current working directory"""
        if not pattern:
            return sorted(list(Path.cwd().iterdir()))
        if ignorecase:
            return Path.cwd().glob_ignorecase(pattern)
        if "*" not in pattern:
            pattern = f"*{pattern}*"
        return sorted(list(Path.cwd().glob(pattern)))

    @classmethod
    def git_root(cls) -> "Path":
        """
        Find the Path of the file of the calling function, and traverse upwards the directory tree
        until a '.git' directory is found. This is usually the project root of the calling function.
        """
        stack = inspect.stack()
        if len(stack) >= 3:
            # Go back two frames to get the caller of this function
            frame = inspect.stack()[2]
            caller_file = Path(frame.filename).resolve()
            current = caller_file.parent
            # print(f"Got {caller_file=} and {current=} from stack[2]")
            if caller_file.name == "interactiveshell.py":
                # print(f"Running in REPL. Attempting to find root from cwd")
                current = Path.cwd().resolve()
        elif len(stack) == 2:
            # Go back a frame to get the caller of this function
            frame = inspect.stack()[1]
            caller_file = frame.filename
            current = Path(caller_file).resolve().parent
            # print(f"Got {caller_file=} and {current=} from stack[1]")
        else:
            current = Path.cwd().resolve()
            # print(f"Got directory={current} from cwd")

        while True:
            if (current / ".git").exists():
                return current
            parent = current.parent
            if parent == current:
                raise ValueError("Reached root, could not find '.git' folder")
            current = parent


PathOrStr = Path | str
