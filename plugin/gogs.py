import logging as l
import urllib.parse
import re

from remote import Client, Requester, ClientException, ExceptionWithReason
from repository import Repo, Branch

# types
from repository import Branches
from remote import Json


class GogsClient(Client):
    def __init__(self, requester: Requester, api_url: str, token: str) -> None:
        super().__init__(requester, api_url)
        if token:
            self.add_header("Authorization", "token {}".format(token))

    def retrieve_branches(self, repo: Repo) -> Branches:
        doc = self.request_json("/repos/{}/branches".format(repo.full_name))
        return [Branch(branch["name"], branch["commit"]["id"]) for branch in doc]

    def retrieve_blob(self, repo: Repo, branch_name: str, file: str) -> str:
        path = "/repos/{}/raw/{}/{}".format(repo.full_name, branch_name, file)
        return self.request_raw(path)

    def retrieve_dockerfile(self, repo: Repo, branch: Branch) -> str:
        try:
            return self.retrieve_blob(repo, branch.name, "Dockerfile")
        except ClientException as e:
            if e.getcode() == 404:
                return self.retrieve_blob(repo, branch.name, "dockerfile")
            else:
                raise

    @staticmethod
    def parse_hook_token(doc: Json) -> str:
        for hook in doc:
            if hook["type"] == "gogs" and "push" in hook["events"]:
                url = hook["config"]["url"]
                query = urllib.parse.urlparse(url).query
                return urllib.parse.parse_qs(query)["access_token"][0]
        else:
            raise UnableToFindDroneHookException("No Drone hook configured.")

    def get_drone_token(self, repo: Repo) -> str:
        try:
            doc = self.request_json("/repos/{}/hooks".format(repo.full_name))
            return self.parse_hook_token(doc)
        except (UnableToFindDroneHookException, ClientException) as e:
            raise ClientException("Unable to retrieve drone token for {}".format(repo.full_name)) from e


class UnableToFindDroneHookException(ExceptionWithReason):
    pass


class DockerImageSearcher(object):
    FROM_REGEX = re.compile("^FROM (.+)$", re.IGNORECASE | re.MULTILINE)

    def __init__(self, gogs: GogsClient) -> None:
        self.gogs = gogs

    @staticmethod
    def has_dockerfile_matching_from_instruction(dockerfile: str, from_: str, ignore_message: str) -> bool:
        match = DockerImageSearcher.FROM_REGEX.search(dockerfile)
        if match:
            image = match.group(1)
            return image.casefold() == from_.casefold()
        else:
            l.warning("%s: FROM instruction is missing.", ignore_message)
            return False

    def has_matching_from_instruction(self, repo: Repo, branch: Branch, from_: str) -> bool:
        ignore_message = "Ignoring repo {} on branch {}".format(repo.full_name, branch.name)
        try:
            dockerfile = self.gogs.retrieve_dockerfile(repo, branch)
            return self.has_dockerfile_matching_from_instruction(dockerfile, from_, ignore_message)
        except ClientException as e:
            if e.getcode() == 404:
                l.warning("%s: No Dockerfile or dockerfile at %s/", ignore_message, e.geturl().rpartition("/")[0])
            else:
                l.warning("%s: Error while retrieving %s: %s", ignore_message, e.geturl(), e)
            return False
