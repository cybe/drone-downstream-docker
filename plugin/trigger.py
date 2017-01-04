#!/usr/bin/env python3

import logging as l

import configuration
from drone import DroneClient, BuildTrigger
from gogs import GogsClient, DockerImageSearcher
from repository import Repo
from remote import ClientException, Requester

# types
from repository import Repos, BranchesOfRepos
from drone import BuildTriggers


class TriggerPlugin(object):
    def __init__(self, drone: DroneClient, gogs: GogsClient, searcher: DockerImageSearcher) -> None:
        self.drone = drone
        self.gogs = gogs
        self.searcher = searcher

    def run(self, from_: str, source: Repo) -> None:
        l.info("Triggering builds of Docker repos with FROM directive %s", from_)
        repos = self.drone.retrieve_repos()
        branches_of_repos = self.get_branches_of_repos(repos)
        branches_of_repos_with_dockerfile = self.get_branches_of_repos_with_dockerfile(branches_of_repos, from_)
        build_triggers = self.create_build_triggers(branches_of_repos_with_dockerfile)
        self.drone.trigger_builds(build_triggers, source)

    def get_branches_of_repos(self, repos: Repos) -> BranchesOfRepos:
        branches_of_repos = {}  # type: BranchesOfRepos
        for repo in repos:
            try:
                branches_of_repo = self.gogs.retrieve_branches(repo)
                if branches_of_repo:
                    branches_of_repos[repo] = branches_of_repo
            except ClientException as e:
                l.warning("Ignoring repository %s, its branches could not be retrieved: %s", repo.full_name, e)
        return branches_of_repos

    def get_branches_of_repos_with_dockerfile(self, branches_of_repos: BranchesOfRepos, from_: str) -> BranchesOfRepos:
        branches_of_repos_with_dockerfile = {}  # type: BranchesOfRepos
        for repo, branches in branches_of_repos.items():
            branches_with_dockerfiles = [branch for branch in branches if
                                         self.searcher.has_matching_from_instruction(repo, branch, from_)]
            if branches_with_dockerfiles:
                branches_of_repos_with_dockerfile[repo] = branches_with_dockerfiles
        return branches_of_repos_with_dockerfile

    def create_build_triggers(self, branches_of_repos_with_dockerfile: BranchesOfRepos) -> BuildTriggers:
        build_triggers = {}  # type: BuildTriggers
        for repo, branches in branches_of_repos_with_dockerfile.items():
            try:
                token = self.gogs.get_drone_token(repo)
                build_triggers[repo] = BuildTrigger(branches, token)
            except ClientException as e:
                l.error("Not triggering build for %s: %s", repo.full_name, e)
        return build_triggers


def main() -> None:
    l.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%H:%M:%S', level=l.INFO)
    config = configuration.Config.create_from_env()
    configuration.validate(config)

    requester = Requester()
    drone = DroneClient(requester, config.drone_api, config.drone_token)
    gogs = GogsClient(requester, config.gogs_api, config.gogs_token)

    trigger = TriggerPlugin(drone, gogs, DockerImageSearcher(gogs))
    trigger.run(config.from_, Repo.from_full_name(config.source))


if __name__ == "__main__":
    main()
