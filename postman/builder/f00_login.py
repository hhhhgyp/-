# -*- coding: utf-8 -*-
"""00 健康检查与登录：为后续所有请求准备 token。"""

from __future__ import annotations

from . import folder, ok, req


def _login_item(name: str, user_var: str, pwd_var: str, token_var: str, role: str, id_var: str) -> dict:
    return req(
        name,
        "POST",
        "/auth/login",
        auth="none",
        body={"username": "{{" + user_var + "}}", "password": "{{" + pwd_var + "}}"},
        tests=ok(
            200,
            "const b = pm.response.json();",
            f"pm.collectionVariables.set('{token_var}', b.access_token);",
            f"pm.collectionVariables.set('{id_var}', b.user.id);",
            "pm.test('token 结构正确', () => {",
            "    pm.expect(b.token_type).to.eql('bearer');",
            "    pm.expect(b.expires_in).to.eql(7200);",
            "    pm.expect(b.access_token).to.be.a('string').and.not.empty;",
            "});",
            f"pm.test('角色 = {role}', () => pm.expect(b.user.role).to.eql('{role}'));",
            "pm.test('不返回密码散列', () => pm.expect(b.user).to.not.have.property('password_hash'));",
        ),
        desc=f"登录并写入集合变量 {token_var}。密码来自环境变量 {pwd_var}（secret 类型）。",
    )


FOLDER = folder(
    "00 健康检查与登录",
    [
        req(
            "00-01 健康检查",
            "GET",
            "/health",
            auth="none",
            pre=["pm.collectionVariables.set('run_ts', String(Date.now()));"],
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('服务正常', () => pm.expect(b.status).to.eql('ok'));",
                "pm.test('数据库可用', () => pm.expect(b.database.ok).to.be.true);",
                "pm.test('返回数据库时间（可用于核对时区）', () => {",
                "    pm.expect(b.database.server_time).to.be.a('string').and.not.empty;",
                "});",
            ),
            desc="执行任何用例前的健康检查。status=degraded 时说明数据库连不上，后续请求必然失败。",
        ),
        _login_item("00-02 登录 user01（普通用户）", "username", "password", "token_user", "USER", "user_id"),
        _login_item(
            "00-03 登录 admin（管理员）", "admin_username", "admin_password", "token_admin", "ADMIN", "admin_id"
        ),
        _login_item(
            "00-04 登录 user02（用于越权测试）",
            "user2_username",
            "user2_password",
            "token_user2",
            "USER",
            "user2_id",
        ),
        req(
            "00-05 当前登录用户",
            "GET",
            "/auth/me",
            tests=ok(
                200,
                "const b = pm.response.json();",
                "pm.test('用户名为 user01', () => pm.expect(b.username).to.eql(pm.environment.get('username')));",
                "pm.test('角色为 USER', () => pm.expect(b.role).to.eql('USER'));",
                "pm.test('不返回密码散列', () => pm.expect(b).to.not.have.property('password_hash'));",
            ),
            desc="验证集合级 Bearer {{token_user}} 已生效。",
        ),
    ],
    desc="先执行健康检查与三个账号登录；后续文件夹依赖此处写入的 token_user / token_admin / token_user2。",
)
