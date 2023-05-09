#!/usr/bin/env python3
import sys
import git
from git import RemoteProgress
from github import Github
import json
import pathlib
import argparse
import logging
import logging.config


from giturlparse import parse

LOGGER = logging.getLogger()


class ProgressPrinter(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        print(
            op_code,
            cur_count,
            max_count,
            cur_count / (max_count or 100.0),
            message or "NO MESSAGE",
        )


class Progress(RemoteProgress):
    def line_dropped(self, line):
        print(line)

    def update(self, *args):
        print(self._cur_line)


class MyStdOutWriter:
    def write(self, value):
        sys.stdout.write(value.decode("utf-8"))
        sys.stdout.flush()


def setup_logging():
    """Setup logging configuration
    :param cli_args: Argparse object containing parameters from the command line
    :return: None
    """
    try:
        logconfig_path = "logging_config.json"
        if not pathlib.Path(logconfig_path).is_file():
            logging.basicConfig(level=logging.INFO)
            # print("Loaded basic log config...")
        else:
            # print("Loading log config...")
            with open(logconfig_path, "rt") as f:
                config = json.load(f)
            logging.config.dictConfig(config)
    except Exception as exc:
        print(exc)
        print("An error occurred in attempting to configure logging!")
        print("Moving forward with basic logging configuration...")
        logging.basicConfig()


def clone_entire_org(args):
    org_name = args.gh_org_name
    src_root = args.src_root
    token = os.environ["GITHUB_TOKEN"]
    gh = Github(token)
    org = gh.get_organization(org_name)
    org_repos = [repo for repo in org.get_repos()]
    for repo in org_repos:
        print(
            clone_remote_repo(
                repo.git_url.replace("git://github.com/", "git@github.com:"),
                src_root,
            )
        )


def run_git_command(args):
    src_path = pathlib.Path.cwd()
    cmd = args.git_command.split(" ")
    if args.recurse:
        for sub_path in src_path.iterdir():
            if sub_path.is_dir() and not sub_path.parts[-1].startswith("."):
                print("chdir {}".format(sub_path.absolute()))
                try:
                    git_wrkr = git.Git(working_dir=sub_path.absolute())
                    git_wrkr.execute(cmd)
                except Exception as ex:
                    print("`{cmd}` command failed.".format(cmd=cmd))
                    print(ex)
    else:
        git_wrkr = git.Git(working_dir=src_path.absolute())
        git_wrkr.execute(cmd)


def run_git_command(git_command, path):
    src_path = pathlib.Path(path).expanduser()
    cmd = git_command.split(" ")
    output_data = None
    try:
        git_wrkr = git.Git(working_dir=src_path.absolute())
        output_data = git_wrkr.execute(cmd)
    except Exception as ex:
        print(f"`{cmd}` command failed on {src_path.absolute()}.")

    return output_data


def clone_remote_repo(remote_repo, src_root):
    p = parse(remote_repo)
    src_path = pathlib.Path(src_root).expanduser()
    repo_destination_path = src_path.joinpath(p.host, p.owner)
    if not repo_destination_path.exists():
        repo_destination_path.mkdir(parents=True)
    if not repo_destination_path.joinpath(p.repo).exists():
        git_wrkr = git.Git(working_dir=repo_destination_path)

        try:
            git_wrkr.execute(["git", "clone", remote_repo])
        except Exception as ex:
            print(ex)

        # print(retval) .format(remote_repo)
        # # while(not retval.proc.stdout.closed):
        #     # print(retval.proc.stdout.readline())
    return repo_destination_path.joinpath(p.repo)


def get_latest_updates_for_master(curr_path):
    current_branch = run_git_command("git rev-parse --abbrev-ref HEAD", curr_path)
    if current_branch:
        default_ref = run_git_command(
            "git symbolic-ref refs/remotes/origin/HEAD", curr_path
        )  #
        if default_ref:
            default_branch = (
                default_ref.split("/")[-1] if "/" in default_ref else default_ref
            )

            print(f"current_branch = {current_branch}")
            print(f"default_ref = {default_ref}")
            print(f"default_branch = {default_branch}")
            do_stash_pop = False
            if current_branch and default_branch:
                if current_branch != default_branch:
                    if (
                        run_git_command("git stash push", curr_path)
                        != "No local changes to save"
                    ):
                        do_stash_pop = True
                        print("--- git stashed, need to pop it later...")
                        print(f"--- git checkout {default_branch}")
                        co_result = run_git_command(
                            f"git checkout {default_branch}", curr_path
                        )
                        print(co_result)

                print(f"--- git pull origin {default_branch}")
                gpob_result = run_git_command(
                    f"git pull origin {default_branch}", curr_path
                )
                print(gpob_result)
                print(f"--- git pull")
                pull_result = run_git_command("git pull", curr_path)
                print(pull_result)
                if current_branch != default_branch:
                    print(f"git checkout {current_branch}")
                    gcocb_result = run_git_command(
                        f"git checkout {current_branch}", curr_path
                    )
                    print(gcocb_result)
                    if do_stash_pop:
                        print(f"git stash pop")
                        gsp_result = run_git_command(f"git stash pop", curr_path)
                        print(gsp_result)
    return curr_path


def update_all_subdirectories(path):
    src_path = pathlib.Path(path).expanduser()
    sub_directories = [
        str(sub_path.absolute())
        for sub_path in src_path.iterdir()
        if sub_path.is_dir()
        and pathlib.Path(sub_path, ".git").exists()
        and not sub_path.parts[-1].startswith(".")
    ]
    for d in sub_directories:
        print(f"#######   {d}   ########")
        get_latest_updates_for_master(d)


def parse_arguments():
    parser = argparse.ArgumentParser(description="gittem.py tool")
    parser.add_argument("-r", "--repo", dest="remote_git_url", required=False)
    parser.add_argument(
        "-s", "--src", dest="src_root", default="~/Sources", required=False
    )
    parser.add_argument("-o", "--org", dest="gh_org_name", required=False)
    parser.add_argument("-c", "--cmd", dest="git_command", required=False)
    parser.add_argument(
        "--recurse", dest="recurse", action="store_true", required=False
    )
    parser.add_argument("--update", dest="update", required=False)
    return parser.parse_known_args()


if __name__ == "__main__":
    args, unk_args = parse_arguments()
    setup_logging()
    if args.gh_org_name:
        clone_entire_org(args)
    elif args.remote_git_url:
        print(clone_remote_repo(args.remote_git_url, args.src_root))
    if args.git_command:
        print("GIT COMMAND: {}".format(args.git_command))
        run_git_command(args)
    if args.update and len(args.update) > 0:
        update_all_subdirectories(args.update)
