# Local Task to check if we can mount in and out the working directory. 
# Initially we had some issues in the setup stage, because it would not expect the working directory to exist. 
# But if we mount it, it gets created, which lead to an error earlier. 

set -a
source .env
set +a

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  if [[ "$2" == "--rm-image" ]]; then
    #This will delete the image, but you will loose caching.
    docker image rm -f useagent-turbo:dev 2>/dev/null
  fi
  DOCKER_BUILDKIT=1 docker build --ssh default -t useagent-turbo:dev .
fi

MODEL_NAME=google-gla:gemini-2.5-flash

mkdir ./tmp
cat > ./tmp/task.md <<'EOF'

# Role
You are given a software development task to perform a `merge` of a feature in your current directory. Your task is to identify the main and feature branch and perform a successful merge commit.


If there is a merge conflict, handle the merge commit appropriately under the assumption that all features of the incoming commit are necessary and wanted. 
Try to keep all features and concepts of the main branch intact while resolving merge conflicts, and only deprecate or remove those that are directly conflicting with the incoming features. 

Changes and decisions made by you must be motivated by test-results.


# Default Environment and your current setup

- You are working on a ubuntu 24.04 platform (using a default Docker image) on a CPU sever (No any GPUs available and Internet is accessible). 

Since this is an isolated docker container, you have the root level permission to run any commands.

IMPORTANT: You are in the working directly and on the base branch now, the feature branch name is called `dependabot/github_actions/github/codeql-action-2.22.9`.

In case you need, the `dependabot/github_actions/github/codeql-action-2.22.9`  is from `https://github.com/apache/commons-csv.git`

# Dos and Do nots 
- Do use `git` tools to create your merge and report the diff. Do not try to generate a string looking like a diff. 
- Consider executing (relevant) tests before performing the merge to capture pre-merge behavior. 
- Do not create a new branch for the merge. You are supposed to determine the main branch, and merge the feature branch into this main branch. 
- Do not make more than one commit. You must perform all tasks in one commit, or squash multiple commits if they were necessary. 
- Do not attempt to fix all issues and problems. Only aim to address errors and mistakes that seem related to your merge commit.
- You must use non-interactive commands.

# The Pull Bequest Description from the developer

Bumps github/codeql-action https://github.com/github/codeql-action from 2.22.8 to 2.22.9. Changelog Sourced from github/codeql-actions changelog. CodeQL Action Changelog See the releases page for the relevant changes to the CodeQL CLI and language packs. UNRELEASED No user facing changes. 2.22.9 - 07 Dec 2023 No user facing changes. 2.22.8 - 23 Nov 2023 Update default CodeQL bundle version to 2.15.3. #2001 2.22.7 - 16 Nov 2023 Add a deprecation warning for customers using CodeQL version 2.11.5 and earlier. These versions of CodeQL were discontinued on 8 November 2023 alongside GitHub Enterprise Server 3.7, and will be unsupported by CodeQL Action v2.23.0 and later. #1993 If you are using one of these versions, please update to CodeQL CLI version 2.11.6 or later. For instance, if you have specified a custom version of the CLI using the tools input to the init Action, you can remove this input to use the default version. Alternatively, if you want to continue using a version of the CodeQL CLI between 2.10.5 and 2.11.5, you can replace github/codeql-action/*@v2 by github/codeql-action/*@v2.22.7 in your code scanning workflow to ensure you continue using this version of the CodeQL Action. 2.22.6 - 14 Nov 2023 Customers running Python analysis on macOS using version 2.14.6 or earlier of the CodeQL CLI should upgrade to CodeQL CLI version 2.15.0 or later. If you do not wish to upgrade the CodeQL CLI, ensure that you are using Python version 3.11 or earlier, as CodeQL version 2.14.6 and earlier do not support Python 3.12. You can achieve this by adding a setup-python step to your code scanning workflow before the step that invokes github/codeql-action/init. Update default CodeQL bundle version to 2.15.2. #1978 2.22.5 - 27 Oct 2023 No user facing changes. 2.22.4 - 20 Oct 2023 Update default CodeQL bundle version to 2.15.1. #1953 Users will begin to see warnings on Node.js 16 deprecation in their Actions logs on code scanning runs starting October 23, 2023. All code scanning workflows should continue to succeed regardless of the warning. The team at GitHub maintaining the CodeQL Action is aware of the deprecation timeline and actively working on creating another version of the CodeQL Action, v3, that will bump us to Node 20. For more information, and to communicate with the maintaining team, please use this issue. 2.22.3 - 13 Oct 2023 Provide an authentication token when downloading the CodeQL Bundle from the API of a GitHub Enterprise Server instance. #1945 2.22.2 - 12 Oct 2023 Update default CodeQL bundle version to 2.15.0. #1938 Improve the log output when an error occurs in an invocation of the CodeQL CLI. #1927 2.22.1 - 09 Oct 2023 ... truncated Commits c0d1daa Merge pull request #2020 from github/update-v2.22.9-e1d1fad1b c6e24c9 Update changelog for v2.22.9 e1d1fad Merge pull request #2014 from github/nickfyson/update-release-process 0e9a210 update workflows to run on all release branches 47e90f2 Merge branch main into nickfyson/update-release-process ee748cf respond to more review comments 57932be remove unused function a6ea3c5 define backport commit message in constant 3537bea Apply suggestions from code review 3675be0 Merge pull request #2017 from cklin/update-supported-enterprise-server-versions Additional commits viewable in compare view !Dependabot compatibility scorehttps://dependabot-badges.githubapp.com/badges/compatibility_score?dependency-name=github/codeql-action&package-manager=github_actions&previous-version=2.22.8&new-version=2.22.9https://docs.github.com/en/github/managing-security-vulnerabilities/about-dependabot-security-updates#about-compatibility-scores Dependabot will resolve any conflicts with this PR as long as you dont alter it yourself. You can also trigger a rebase manually by commenting @dependabot rebase. //: # dependabot-automerge-start //: # dependabot-automerge-end --- Dependabot commands and options You can trigger Dependabot actions by commenting on this PR: - @dependabot rebase will rebase this PR - @dependabot recreate will recreate this PR, overwriting any edits that have been made to it - @dependabot merge will merge this PR after your CI passes on it - @dependabot squash and merge will squash and merge this PR after your CI passes on it - @dependabot cancel merge will cancel a previously requested merge and block automerging - @dependabot reopen will reopen this PR if it is closed - @dependabot close will close this PR and stop Dependabot recreating it. You can achieve the same result by closing it manually - @dependabot show ignore conditions will show all of the ignore conditions of the specified dependency - @dependabot ignore this major version will close this PR and stop Dependabot creating any more for this major version unless you reopen the PR or upgrade to it yourself - @dependabot ignore this minor version will close this PR and stop Dependabot creating any more for this minor version unless you reopen the PR or upgrade to it yourself - @dependabot ignore this dependency will close this PR and stop Dependabot creating any more for this dependency unless you reopen the PR or upgrade to it yourself 
#  Your Task and Output
- perform the merge by producing the resulting merge commit; The merge commit must be a valid `git diff`. 

EOF

rm -rf ./useagent-turbo-tmp
mkdir ./useagent-turbo-tmp
git clone $REPO_URL ./useagent-turbo-tmp
rm -rf ./useagent-turbo-tmp-out
mkdir ./useagent-turbo-tmp-out


docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v ./tmp:/task:rw \
  -v ~/playground/commons-csv-374:/input:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  -v ./useagent-turbo-merge-tmp-out/project:/tmp/working_dir:rw \
  useagent-turbo:dev \
  useagent local \
    --model $MODEL_NAME \
    --output-dir /output \
    --project-directory /input \
    --task-file /task/task.md