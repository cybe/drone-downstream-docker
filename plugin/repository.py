from typing import NamedTuple, Dict, Iterable


class Repo(NamedTuple("Repo", [("owner", str), ("name", str)])):
    @property
    def full_name(self) -> str:
        return "{}/{}".format(self.owner, self.name)

    @classmethod
    def from_full_name(cls, full_name: str) -> "Repo":
        return cls(*full_name.split("/"))

    def __repr__(self) -> str:
        return self.full_name


Branch = NamedTuple("Branch", [("name", str), ("sha1", str)])

Repos = Iterable[Repo]
Branches = Iterable[Branch]
BranchesOfRepos = Dict[Repo, Branches]
