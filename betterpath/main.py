import datetime
import shutil
import subprocess
from pathlib import PosixPath
from tempfile import NamedTemporaryFile
from typing import Iterable, List, Optional, Tuple, NamedTuple

from betterpath.utils import bytes2human
from fuzzywuzzy import fuzz


DiskUsageHuman = NamedTuple("usage", [("total", str), ("used", str), ("free", str)])


class Path(PosixPath):
    """
    An extension to Pythons built-in pathlib.Path.

    Provides convenience methods and methods for working with numerical suffixes.
    """

    def glob_ignorecase(self, pattern: str) -> List["Path"]:
        """
        Glob ignoring case

        Example
        -------
        >>> Path('..').glob_ignorecase("*")
        [Path('../.git'),
         Path('../.gitignore'),
         Path('../LICENSE'),
         Path('../README.md'),
         Path('../betterpath'),
         Path('../setup.py')]

        >>> Path('..').glob_ignorecase("readme*")
        [Path('../README.md')]
        """
        path = self.parent if self.is_file() else self

        def either(c):
            return "[%s%s]" % (c.lower(), c.upper()) if c.isalpha() else c

        if "*" not in pattern:
            pattern = f"*{pattern}*"
        return sorted(list(path.glob("".join(map(either, pattern)))))

    def most_like_path(self, recursive=True) -> Optional["Path"]:
        """
        Return the path with the most similar name
        R"""
        if recursive:
            candidates = list(self.parent.glob("**/*"))
        else:
            candidates = list(self.parent.glob("*"))
        candidates = [p for p in candidates if p != self]
        if not candidates:
            return None
        sims = [
            fuzz.partial_ratio(self.name, p.name) + fuzz.ratio(self.name, p.name)
            for p in candidates
            if p != self
        ]
        m = max(zip(candidates, sims), key=lambda tup: tup[1])[0]
        return m

    def mtime(self) -> datetime.datetime:
        """
        Modification time, as datetime
        """
        return datetime.datetime.fromtimestamp(self.stat().st_mtime)

    def prepend_suffix(self, suffix: str) -> "Path":
        """
        Prepend suffix

        Example
        -------
        >>> Path('pathtools.py.xx').prepend_suffix('.new')
        Path('pathtools.new.py.xx')
        """
        suffix = suffix if suffix.startswith(".") else "." + suffix
        base = self.name[: self.name.find(".")]
        return self.with_name(base + "".join([suffix] + self.suffixes))

    def is_numerical(self) -> bool:
        """
        Returns True if there's an all-digit extension, e.g. myfile.pickle.100
        """
        for s in self.suffixes:
            if s[1:].isdigit():
                return True
        return False

    def get_numerical(self) -> int | None:
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
        if not self.is_numerical():
            raise ValueError()
        n = self.suffix[1:]
        if not n_digs >= len(n):
            raise ValueError()
        path = self.with_suffix("." + n.zfill(n_digs))
        return path

    def make_numerical_ext_nonprimary(self) -> "Path":
        """
        Shift the numerical extension as not to become the last/primary extension
        myfile.x.feather.001 > myfile.x.001.feather
        """
        ext = self.suffixes[-1]
        if not ext[1:].isdigit():
            raise ValueError("No numerical primary extensions")
        suffixes = self.suffixes.copy()
        del suffixes[-1]
        suffixes.insert(len(suffixes) - 1, ext)
        return self.with_suffixes(suffixes)

    def make_numerical_ext_primary(self) -> "Path":
        """
        Shift the numerical extension to become the last/primary extension
        myfile.x.001.feather > myfile.x.feather.001
        """
        if not self.is_numerical():
            raise ValueError("No numerical extensions")
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

    def sizeh(self) -> str:
        return bytes2human(self.size())

    def disk_usage(self) -> Tuple[int, int, int]:
        """
        The amount used and free space on the disk which this file or directory resides on,
        and the size of the disk
        """
        return shutil.disk_usage(self)

    du = disk_usage

    def disk_usage_human(self) -> DiskUsageHuman:
        """"""
        du = shutil.disk_usage(self)
        duh = DiskUsageHuman(
            bytes2human(du.total),
            bytes2human(du.used),
            bytes2human(du.free),
        )
        return duh

    duh = disk_usage_human

    def move(self, path: "PathOrStr", overwrite=False) -> "Path":
        path = Path(path)
        if not overwrite:
            raise FileExistsError(path)
        return shutil.move(self, path)

    mv = move

    def copy(self, dst: "PathOrStr", dirs_exist_ok=False) -> "Path":
        dst = Path(dst)
        if self.is_dir():
            return shutil.copytree(self, dst, dirs_exist_ok)
        return shutil.copy2(self, dst)

    cp = copy

    def ls(self, sort_by_time: bool = False) -> None:
        path = str(self.resolve())
        sort = "t" if sort_by_time else ""
        subprocess.run(f"ls --group-directories-first -hoG{sort} " + path, shell=True)

    def modtime(self) -> str:
        """
        Last modification time of given path, as a nice string
        """
        dt = datetime.datetime.fromtimestamp(self.stat().st_mtime)
        return dt.strftime("%Y-%m-%d %H:%M")

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
        """
        parent_path = Path(parent_path)
        return parent_path / self.name

    def with_home(self, user: str) -> "Path":
        """
        Path for a different user

        Example
        -------
        >>> Path("/home/USER_1/somefile").with_home("USER_2")
        Path('/home/USER_2/somefile')
        """
        return Path("/home") / user / self.resolve().relative_to(Path.home())

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

    def with_suffixes(self, suffixes: Iterable[str]) -> "Path":
        return self.without_suffixes().with_suffix("".join(suffixes))

    def without_suffix(self, suffix: str) -> "Path":
        """
        Remove a given suffix from the path.

        Example:
        >>> Path('add_polling_info.py.bak.new').without_suffix('.bak')
        Path('add_polling_info.py.new')
        """
        suffix = suffix if suffix.startswith(".") else "." + suffix
        return self.without_suffixes().with_suffix(
            "".join(s for s in self.suffixes if s != suffix)
        )

    def without_suffixes(self) -> "Path":
        """
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
        """
        ext = self.suffix[1:]
        if ext.isdigit():
            n_digs = len(ext)
            ext_i = int(ext) + 1
        else:
            path = self.add_suffix(".ph")  # placeholder
            ext_i = start
        path = path.with_suffix("." + str(ext_i).zfill(n_digs))
        while path.exists():
            ext_i += 1
            path = path.with_suffix("." + str(ext_i).zfill(n_digs))
        assert not path.exists()
        return path

    def last_numerical_path(self) -> "Path":
        """
        Returns the highest numerical path
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
            raise FileNotFoundError
        return best

    @classmethod
    def random_path(cls, prefix=None, suffix=None, dir_=None) -> "Path":
        """
        Return a random, unused path. If `dir_` is not given, then the path
        will be a temporary location.
        """
        with NamedTemporaryFile(
            prefix=prefix, suffix=suffix, dir=dir_, delete=True
        ) as n:
            return Path(n.name)


PathOrStr = Path | str


def glob_cwd(pattern: str = "", ignorecase: bool = False) -> List[Path]:
    """Glob the current working directory"""
    if not pattern:
        return sorted(list(Path().iterdir()))
    if ignorecase:
        return Path().cwd().glob_ignorecase(pattern)
    if "*" not in pattern:
        pattern = f"*{pattern}*"
    return sorted(list(Path().cwd().glob(pattern)))
