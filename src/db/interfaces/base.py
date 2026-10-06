from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session


class BaseDatabase(ABC):
    @abstractmethod
    def startup(self) -> None: ...

    @abstractmethod
    def teardown(self) -> None: ...

    @abstractmethod
    def get_session(self) -> AbstractContextManager[Session]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
