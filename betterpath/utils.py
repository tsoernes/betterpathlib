_SYMBOLS = {
    "customary": ("B", "K", "M", "G", "T", "P", "E", "Z", "Y"),
    "customary_ext": (
        "byte",
        "kilo",
        "mega",
        "giga",
        "tera",
        "peta",
        "exa",
        "zetta",
        "iotta",
    ),
    "iec": ("Bi", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"),
    "iec_ext": ("byte", "kibi", "mebi", "gibi", "tebi", "pebi", "exbi", "zebi", "yobi"),
}


def bytes2human(
    n: int | str, fmt: str = "%(value).1f %(symbol)s", symbols: str = "customary"
) -> str:
    """
    Return a human readble string from a given number of bytes.
    Converts to kibibytes (K, Ki, or kibi depending on `symbols`),
    mebibytes etc.

    Parameters
    ----------
    n
        Number of bytes
    fmt
        String format

    Returns
    -------
    str

    Examples
    --------
    >>> bytes2human("2010000")
    '1.9 M'
    """
    n = int(n)
    if n < 0:
        raise ValueError("n < 0")
    symbols = _SYMBOLS[symbols]
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return fmt % dict(symbol=symbol, value=value)
    return fmt % dict(symbol=symbols[0], value=n)
