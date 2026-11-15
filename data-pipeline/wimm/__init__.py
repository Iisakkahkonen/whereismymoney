"""whereismymoney data pipeline."""


class AmbiguousSeries(Exception):
    """More than one value for the same key (for example one year and one item).

    The build must stop on this. Summing ambiguous rows would silently double
    count money, which is the one thing this project must never do.
    """
