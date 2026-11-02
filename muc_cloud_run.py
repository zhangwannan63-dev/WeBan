"""Isolated cloud entry point; credentials are supplied by GitHub Secrets."""
import os
import sys


def main():
    mode = os.environ.get("WB_CLOUD_MODE", "inspect")
    if mode not in {"inspect", "study-and-exam"}:
        print("Unsupported mode.")
        return 2
    username = os.environ.get("WB_USERNAME", "")
    password = os.environ.get("WB_PASSWORD", "")
    if not username or not password:
        print("Missing account Secrets.")
        return 2
    from loguru import logger
    from client import WeBanClient, _check_code_ok
    logger.configure(extra={"account": "中央民族大学"})
    client = WeBanClient(
        "中央民族大学", username, password,
        log=logger.bind(account="中央民族大学"),
        browser_path=os.environ.get("WB_BROWSER_PATH") or None,
        debug=False, video_speed=1,
    )
    try:
        if not client.login():
            print("Login failed; no study or exam was started.")
            return 1
        projects = client._get_project_list()
        if not projects:
            print("No available projects.")
            return 1
        for project in projects:
            name = project.get("projectName", "")
            print(f"Available project: {name}")
            client.get_progress(project["userProjectId"], name)
        if mode == "inspect":
            return 0
        requested = os.environ.get("WB_PROJECT_NAME", "").strip()
        if requested:
            selected = [p for p in projects if p.get("projectName") == requested]
        else:
            selected = projects if len(projects) == 1 else []
        if len(selected) != 1:
            print("Specify one exact project name before starting study or exam.")
            return 2
        project = selected[0]
        print(f"Selected project: {project['projectName']}")
        client.simulate_home_page()
        client.sync_answers()
        client.exam_mode = "true"
        client.run_study("20,10", "true", only_project=project)
        client.run_exam(
            exam_mode="true", random_answer=False,
            exam_question_time="3,3", exam_submit_match_rate=100,
            only_project=project,
        )
        client.get_progress(project["userProjectId"], project["projectName"])
        return 0
    except PermissionError as error:
        print(f"Account or verification blocked: {error}")
        return 1
    except Exception as error:
        print(f"Task stopped: {type(error).__name__}. Review the preceding platform log.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
