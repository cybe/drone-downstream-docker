#!/usr/bin/env python3

import logging as l

import configuration
from drone import DroneClient, BuildTrigger
from gogs import GogsClient, DockerImageSearcher
from repository import Repo
from remote import ClientException, Requester
from typing import Union, Dict

# types
from repository import Repos, BranchesOfRepos, Branches
from drone import BuildTriggers


class TriggerPlugin(object):
    def __init__(self, drone: DroneClient, gogs: GogsClient, searcher: DockerImageSearcher) -> None:
        self.drone = drone
        self.gogs = gogs
        self.searcher = searcher

    def run(self, from_: str, source: Repo, dry_run: bool) -> None:
        l.info("Triggering builds of Docker repositories with FROM instruction '%s'", from_)

        repos = self.drone.retrieve_repos()
        branches_of_repos = self.get_branches_of_repos(repos)
        verbose(self.log_potential_targets, branches_of_repos)

        branches_of_repos_with_dockerfile = self.get_branches_of_repos_with_dockerfile(branches_of_repos, from_)
        verbose(self.log_matching_targets, branches_of_repos_with_dockerfile)

        build_triggers = self.create_build_triggers(branches_of_repos_with_dockerfile)
        self.log_builds_to_trigger(build_triggers)

        builds_triggered = 0
        if dry_run:
            l.info("Aborted execution, this was only a dry run.")
        else:
            builds_triggered = self.drone.trigger_builds(build_triggers, source)
        verbose(self.log_builds_triggered, builds_triggered)

    def get_branches_of_repos(self, repos: Repos) -> BranchesOfRepos:
        branches_of_repos = {}
        for repo in repos:
            try:
                branches_of_repo = self.gogs.retrieve_branches(repo)
                if branches_of_repo:
                    branches_of_repos[repo] = branches_of_repo
            except ClientException as e:
                l.warning("Ignoring %s, its branches could not be retrieved: %s", repo.full_name, e)
        return branches_of_repos

    def get_branches_of_repos_with_dockerfile(self, branches_of_repos: BranchesOfRepos, from_: str) -> BranchesOfRepos:
        branches_of_repos_with_dockerfile = {}
        for repo, branches in branches_of_repos.items():
            branches_with_dockerfiles = [branch for branch in branches if
                                         self.searcher.has_matching_from_instruction(repo, branch, from_)]
            if branches_with_dockerfiles:
                branches_of_repos_with_dockerfile[repo] = branches_with_dockerfiles
        return branches_of_repos_with_dockerfile

    def create_build_triggers(self, branches_of_repos_with_dockerfile: BranchesOfRepos) -> BuildTriggers:
        build_triggers = {}
        for repo, branches in branches_of_repos_with_dockerfile.items():
            try:
                token = self.gogs.get_drone_token(repo)
                build_triggers[repo] = BuildTrigger(branches, token)
            except ClientException as e:
                l.error("Not triggering build for %s: %s", repo.full_name, e)
        return build_triggers

    @staticmethod
    def log_potential_targets(branches_of_repos: BranchesOfRepos) -> None:
        if branches_of_repos:
            l.debug("Potential Drone targets: %s", list_repos_with_branches(branches_of_repos))
        else:
            l.debug("No potential Drone targets found.")

    @staticmethod
    def log_matching_targets(branches_of_repos_with_dockerfile: BranchesOfRepos) -> None:
        if branches_of_repos_with_dockerfile:
            l.debug("Targets with matching Dockerfiles: %s", list_repos_with_branches(branches_of_repos_with_dockerfile))
        else:
            l.debug("No targets with matching Dockerfiles found.")

    @staticmethod
    def log_builds_to_trigger(triggers: BuildTriggers) -> None:
        if triggers:
            l.info("Triggering builds for: %s", list_repos_with_branches(triggers))
        else:
            l.info("There are no builds to trigger.")

    @staticmethod
    def log_builds_triggered(builds_triggered: int) -> None:
        l.debug("Triggered %s builds in total", builds_triggered)


def verbose(function, *args, **kwargs):
    if l.getLogger().isEnabledFor(l.DEBUG):
        function(*args, **kwargs)


def list_repos_with_branches(repos: Dict[Repo, Union[Branches, BuildTrigger]]) -> str:
    def list_branches(branches_of_repo: Branches) -> str:
        return ",".join(branch.name for branch in branches_of_repo)

    targets = []
    for repo, branches_or_trigger in repos.items():
        branches = branches_or_trigger.branches if hasattr(branches_or_trigger, "branches") else branches_or_trigger
        targets.append("{}[{}]".format(repo.full_name, list_branches(branches)))
    return "; ".join(targets)


def main() -> None:
    l.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%H:%M:%S', level=l.INFO)
    config = configuration.Config.create_from_env()
    configuration.validate(config)
    if config.verbose:
        l.getLogger().setLevel(l.DEBUG)
        l.debug("Enabled verbose logging.")

    requester = Requester()
    drone = DroneClient(requester, config.drone_api, config.drone_token)
    gogs = GogsClient(requester, config.gogs_api, config.gogs_token)

    trigger = TriggerPlugin(drone, gogs, DockerImageSearcher(gogs))
    trigger.run(config.from_, Repo.from_full_name(config.source), config.dry_run)


if __name__ == "__main__":
    main()
