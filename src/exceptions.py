class DriverOpsError(Exception):
    """Base for all service errors."""


class DatabaseError(DriverOpsError):
    pass


class CorpusError(DriverOpsError):
    pass


class ParsingError(DriverOpsError):
    pass


class DocumentRejected(ParsingError):
    """File refused before or after parsing (too large, too many pages, no usable text)."""


class EmbeddingsError(DriverOpsError):
    pass


class SearchError(DriverOpsError):
    """Search backend failed. Distinct from an empty result."""


class LLMError(DriverOpsError):
    pass
