"""GitHub Actions entry point; credentials come only from repository Secrets."""
import os
import sys


def main():
    mode = os.environ.get("WB_CLOUD_MODE", "login-check")
    if mode not in {"login-check", "study", "study-and-exam"}:
        print("Unsupported run mode.", file=sys.stderr)
        return 2
    tenant = os.environ.get("WB_TENANT_NAME", "").strip()
    username = os.environ.get("WB_USERNAME", "").strip()
    password = os.environ.get("WB_PASSWORD", "")
    user_id = os.environ.get("WB_USER_ID", "").strip()
    token = os.environ.get("WB_TOKEN", "").strip()
    if not tenant or not ((username and password) or (user_id and token)):
        print("请配置 WB_USERNAME + WB_PASSWORD，或 WB_USER_ID + WB_TOKEN。", file=sys.stderr)
        return 2
    import main as app
    account = {"tenant_name": tenant}
    if user_id and token:
        account.update(user_id=user_id, token=token)
    else:
        account.update(username=username, password=password)
    if mode == "login-check":
        from client import WeBanClient, _check_code_ok
        kwargs = {"browser_path": os.environ.get("WB_BROWSER_PATH") or None,
                  "log": app.logger.bind(account="登录检查")}
        if user_id and token:
            client = WeBanClient(tenant, user={"userId": user_id, "token": token}, **kwargs)
            # Token must be validated by the server, not merely present locally.
            result = client.api.list_my_project()
            ok = _check_code_ok(result)
        else:
            client = WeBanClient(tenant, username, password, **kwargs)
            ok = bool(client.login())
        print("登录检查通过。" if ok else "登录检查失败，请检查账号或 Token。")
        return 0 if ok else 1
    ok = app.run_account(account, {
        "study_mode": "true", "exam_mode": "true" if mode == "study-and-exam" else "false",
        "exam_submit_match_rate": 100,
        "study_time": "20,10", "video_speed": 1,
        "max_workers": 1, "debug": False,
    }, {"enable": False}, 1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
