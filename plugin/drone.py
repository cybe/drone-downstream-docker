import json
import logging as l
from typing import Union, Dict, NamedTuple

from remote import Client, Requester, ClientException
from repository import Repo, Branch

# types
from remote import Json
from repository import Repos, Branches


BuildTrigger = NamedTuple("BuildTrigger", [("branches", Branches), ("token", str)])
BuildTriggers = Dict[Repo, BuildTrigger]


class DroneClient(Client):
    TRIGGER_TEMPLATE = {
        "ref": "refs/heads/{branch}",
        "repository": {
            "owner": {
                "username": "{owner}",
            },
            "name": "{name}"
        },
        "commits": [{}],
        "after": "{commit}",
        "sender": {
            "avatar_url": "static/drone.svg",
            "username": "Triggered by upstream build of {source}. No one"
        }
    }

    def __init__(self, requester: Requester, api_url: str, token: str = None) -> None:
        super().__init__(requester, api_url)
        if token:
            self.add_header("Authorization", token)

    def retrieve_repos(self) -> Repos:
        try:
            doc = self.request_json("/user/repos")
            return (Repo(r["owner"], r["name"]) for r in doc)
        except ClientException as e:
            l.error("Unable to retrieve Drone repositories: %s", e)
            raise SystemExit(1)

    @staticmethod
    def unable_to_trigger(e: ClientException, repo_full_name: str) -> None:
        not_triggered_message = "Unable to trigger build for {}".format(repo_full_name)
        if e.getcode() == 400:
            l.error("%s: The supplied token is invalid.", not_triggered_message)
        elif e.getcode() == 401:
            l.warning("%s: The push hook is disabled.", not_triggered_message)
        else:
            l.error("%s: %s", not_triggered_message, e)

    def trigger_branch_build(self, repo: Repo, branch: Branch, source: Repo) -> None:
        hook_data = json_format(DroneClient.TRIGGER_TEMPLATE,
                                owner=repo.owner, name=repo.name, branch=branch.name, commit=branch.sha1,
                                source=source.full_name)
        try:
            doc = self.request_json("/hook", json.dumps(hook_data).encode())
            l.info("Triggered build #%s for %s on branch %s", doc["number"], repo.full_name, branch.name)
        except ClientException as e:
            self.unable_to_trigger(e, repo.full_name)

    def trigger_builds(self, triggers: BuildTriggers, source: Repo) -> None:
        self.add_header("Content-Type", "application/json; charset=utf-8")
        self.add_header("X-Gogs-Event", "push")
        for repo, trigger in triggers.items():
            self.add_header("Authorization", trigger.token)
            for branch in trigger.branches:
                self.trigger_branch_build(repo, branch, source)


def json_format(original: Json, **kwargs: Union[str, Dict]) -> Json:
    if isinstance(original, list):
        return [json_format(value, **kwargs) for value in original]
    elif isinstance(original, dict):
        return {key.format(**kwargs): json_format(value, **kwargs) for key, value in original.items()}
    elif isinstance(original, str):
        return original.format(**kwargs)
    else:
        return original
