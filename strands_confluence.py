import asyncio
import json
import os
from datetime import datetime
from typing import Optional

import jwt
import requests
from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

# Environment settings
os.environ["STRANDS_OTEL_ENABLE_CONSOLE_EXPORT"] = "true"
os.environ["OTEL_PYTHON_EXCLUDED_URLS"] = "/ping,/invocations"

# API endpoints
ATLASSIAN_ACCESSIBLE_RESOURCES_URL = (
    "https://api.atlassian.com/oauth/token/accessible-resources"
)
CONFLUENCE_API_BASE = "https://api.atlassian.com/ex/confluence"

# HTTP status codes
HTTP_OK = 200

# Global variables for token management
atlassian_access_token: Optional[str] = None
atlassian_cloud_id: Optional[str] = None
tool_name: Optional[str] = None
token_metadata: dict = {}

# Authentication keywords
AUTH_KEYWORDS = [
    "authentication",
    "authorize",
    "authorization",
    "auth",
    "sign in",
    "login",
    "access",
    "permission",
    "credential",
    "認証",
    "アクセス",
    "許可",
    "権限",
    "ログイン",
]


# ========================================
# Helper Functions
# ========================================


def create_auth_headers(access_token: str) -> dict:
    """認証ヘッダーを生成"""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def create_auth_required_response(tool_name: str) -> str:
    """認証が必要な場合のレスポンスを生成"""
    return json.dumps(
        {
            "auth_required": True,
            "message": f"Atlassian authentication is required for {tool_name}.",
        }
    )


def create_error_response(error_message: str, details: str = "") -> str:
    """エラーレスポンスを生成"""
    return json.dumps(
        {
            "success": False,
            "error": error_message,
            "details": details,
        }
    )


def decode_token_info(access_token: str) -> dict:
    """アクセストークンをデコードして情報を取得"""
    try:
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        return {
            "iss": decoded.get("iss", "N/A"),
            "sub": decoded.get("sub", "N/A"),
            "aud": decoded.get("aud", "N/A"),
            "exp": decoded.get("exp", "N/A"),
            "iat": decoded.get("iat", "N/A"),
            "scopes": decoded.get("scope", "N/A"),
        }
    except Exception:
        return {}


def extract_response_text(response_message) -> str:
    """レスポンスメッセージからテキストを抽出"""
    if isinstance(response_message, dict):
        content = response_message.get("content", [])
        if isinstance(content, list):
            return "".join(
                item["text"]
                for item in content
                if isinstance(item, dict) and "text" in item
            )
    return str(response_message)


# ========================================
# Atlassian API Functions
# ========================================


def get_atlassian_cloud_id(access_token: str) -> Optional[str]:
    """Atlassianのアクセス可能なリソースからCloud IDを取得"""
    response = requests.get(
        ATLASSIAN_ACCESSIBLE_RESOURCES_URL,
        headers=create_auth_headers(access_token),
    )

    if response.status_code == HTTP_OK:
        resources = response.json()
        if resources:
            return resources[0]["id"]

    return None


def get_space_id_by_key(space_key: str) -> Optional[str]:
    """Space KeyからSpace IDを取得（v2 API用）"""
    global atlassian_access_token, atlassian_cloud_id

    api_url = f"{CONFLUENCE_API_BASE}/{atlassian_cloud_id}/wiki/api/v2/spaces"
    params = {"keys": space_key, "limit": 1}

    response = requests.get(
        api_url, headers=create_auth_headers(atlassian_access_token), params=params
    )

    if response.status_code == HTTP_OK:
        result = response.json()
        spaces = result.get("results", [])
        if spaces:
            return spaces[0].get("id")

    return None


# ========================================
# Confluence Tool Functions
# ========================================


@tool
def search_confluence_by_text(search_text: str, limit: int = 10) -> str:
    """テキスト検索でConfluenceページを検索"""
    global atlassian_access_token, atlassian_cloud_id, tool_name
    tool_name = "search_confluence_by_text"

    if not atlassian_access_token:
        return create_auth_required_response(tool_name)

    cql = f"type=page AND (title~'{search_text}' OR text~'{search_text}')"
    api_url = f"{CONFLUENCE_API_BASE}/{atlassian_cloud_id}/wiki/rest/api/content/search"
    params = {"cql": cql, "limit": limit}

    response = requests.get(
        api_url, headers=create_auth_headers(atlassian_access_token), params=params
    )

    if response.status_code == HTTP_OK:
        result = response.json()
        return json.dumps(
            {
                "success": True,
                "search_text": search_text,
                "total": result.get("totalSize", 0),
                "pages": [
                    {
                        "id": page["id"],
                        "title": page["title"],
                        "space": page.get("space", {}).get("name", "N/A"),
                        "excerpt": page.get("excerpt", ""),
                        "url": f"https://{atlassian_cloud_id}.atlassian.net/wiki{page['_links']['webui']}",
                    }
                    for page in result.get("results", [])
                ],
            }
        )

    return create_error_response(
        f"Failed to search pages: {response.status_code}", response.text
    )


@tool
def get_confluence_page(page_id: str) -> str:
    """指定されたIDのConfluenceページの詳細を取得"""
    global atlassian_access_token, atlassian_cloud_id, tool_name
    tool_name = "get_confluence_page"

    if not atlassian_access_token:
        return create_auth_required_response(tool_name)

    api_url = f"{CONFLUENCE_API_BASE}/{atlassian_cloud_id}/wiki/api/v2/pages/{page_id}"
    params = {"body-format": "storage"}  # v2ではbody-formatパラメータが必須

    response = requests.get(
        api_url, headers=create_auth_headers(atlassian_access_token), params=params
    )

    if response.status_code == HTTP_OK:
        page = response.json()
        body_content = page.get("body", {}).get("storage", {}).get("value", "")

        return json.dumps(
            {
                "success": True,
                "page": {
                    "id": page.get("id"),
                    "title": page.get("title"),
                    "spaceId": page.get("spaceId"),
                    "version": page.get("version", {}).get("number", 1),
                    "content": body_content,
                    "status": page.get("status"),
                },
            }
        )

    return create_error_response(
        f"Failed to get page: {response.status_code}", response.text
    )


@tool
def create_confluence_page(
    space_key: str, title: str, content: str, parent_id: Optional[str] = None
) -> str:
    """新しいConfluenceページを作成"""
    global atlassian_access_token, atlassian_cloud_id, tool_name
    tool_name = "create_confluence_page"

    if not atlassian_access_token:
        return create_auth_required_response(tool_name)

    # Space KeyからSpace IDを取得（v2 API用）
    space_id = get_space_id_by_key(space_key)
    if not space_id:
        return create_error_response(
            f"Space not found: {space_key}", "指定されたSpace Keyが見つかりません"
        )

    # HTML形式でない場合はpタグで囲む
    if not content.startswith("<"):
        content = f"<p>{content}</p>"

    # Confluence REST API v2のpayload形式
    payload = {
        "spaceId": space_id,
        "status": "current",
        "title": title,
        "body": {
            "representation": "storage",
            "value": content,
        },
    }

    if parent_id:
        payload["parentId"] = parent_id

    api_url = f"{CONFLUENCE_API_BASE}/{atlassian_cloud_id}/wiki/api/v2/pages"
    headers = create_auth_headers(atlassian_access_token)
    headers["Content-Type"] = "application/json"

    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == HTTP_OK:
        page = response.json()
        return json.dumps(
            {
                "success": True,
                "message": f"ページを作成しました: {page.get('title')}",
                "page_id": page.get("id"),
                "page_title": page.get("title"),
                "space_id": space_id,
            }
        )

    return create_error_response(
        f"Failed to create page: {response.status_code}", response.text
    )


# ========================================
# Agent Configuration
# ========================================

SYSTEM_PROMPT = """あなたはユーザーのAtlassian Confluenceを操作するエージェントです。
ユーザーのリクエストに基づいて、Confluenceページの検索、新しいページの作成を行います。

主な機能:
- テキスト検索: キーワードでページを検索
- ページ詳細取得: 特定ページの内容を表示
- ページ作成: 新しいConfluenceページを作成

操作が完了したら、結果を明確に伝えてください。"""

model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        search_confluence_by_text,
        get_confluence_page,
        create_confluence_page,
    ],
)

app = BedrockAgentCoreApp()


# ========================================
# Streaming Queue for Agent Communication
# ========================================


class StreamingQueue:
    """エージェント実行中のメッセージストリーミング用キュー"""

    def __init__(self):
        self.finished = False
        self.queue = asyncio.Queue()

    async def put(self, item):
        """キューにアイテムを追加"""
        await self.queue.put(item)

    async def finish(self):
        """キューを終了状態にする"""
        self.finished = True
        await self.queue.put(None)

    async def stream(self):
        """キューからアイテムをストリーミング"""
        while True:
            item = await self.queue.get()
            if item is None and self.finished:
                break
            yield item


queue = StreamingQueue()


# ========================================
# Authentication Functions
# ========================================


async def on_auth_url(url: str):
    """認証URLが生成された際のコールバック"""
    separator = "=" * 80
    print(f"\n{separator}")
    print("🔐 AUTHORIZATION REQUIRED")
    print(f"{separator}")
    print(f"\nPlease copy and paste this URL in your browser:\n{url}\n")
    print(f"{separator}\n")
    await queue.put(f"Authorization url: {url}")


def needs_authentication(response_text: str) -> bool:
    """レスポンステキストから認証が必要かどうかを判定"""
    return any(keyword.lower() in response_text.lower() for keyword in AUTH_KEYWORDS)


async def handle_authentication() -> bool:
    """
    認証処理を実行

    Returns:
        bool: 認証が成功した場合True、失敗した場合False
    """
    global atlassian_access_token, atlassian_cloud_id, tool_name

    await queue.put(
        f"Authentication required for {tool_name} access. Starting authorization flow..."
    )

    try:
        atlassian_access_token = await need_atlassian_token_async(access_token=None)
        atlassian_cloud_id = get_atlassian_cloud_id(atlassian_access_token)

        if atlassian_cloud_id:
            await queue.put(
                f"Authentication successful! Atlassian Cloud ID: {atlassian_cloud_id}"
            )
            await queue.put(f"Retrying {tool_name}...")
            return True
        else:
            await queue.put("Failed to obtain Atlassian Cloud ID")
            return False

    except Exception as auth_error:
        await queue.put(f"Authentication failed: {str(auth_error)}")
        return False


async def agent_task(user_message: str):
    """エージェントタスクを実行"""
    try:
        await queue.put("Begin agent execution")

        response = agent(user_message)
        response_text = extract_response_text(response.message)

        # 認証が必要な場合は認証処理を実行してリトライ
        if needs_authentication(response_text):
            if await handle_authentication():
                response = agent(user_message)

        await queue.put(response.message)
        await queue.put("End agent execution")
    except Exception as e:
        await queue.put(f"Error: {str(e)}")
    finally:
        await queue.finish()


@requires_access_token(
    provider_name="atlassian_oauth_provider",
    scopes=os.environ.get("atlassian_scopes", "").split(),
    auth_flow="USER_FEDERATION",
    on_auth_url=on_auth_url,
    force_authentication=False,
)
async def need_atlassian_token_async(*, access_token: str) -> str:
    """
    Atlassianアクセストークンを取得・保存

    Args:
        access_token: OAuth2で取得したアクセストークン

    Returns:
        str: アクセストークン
    """
    global atlassian_access_token, token_metadata

    # トークン情報をデコードしてメタデータに保存
    token_info = decode_token_info(access_token)
    if token_info and token_info.get("exp") != "N/A":
        exp_timestamp = token_info["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        token_metadata["exp_time"] = exp_datetime.strftime("%Y-%m-%d %H:%M:%S")

    atlassian_access_token = access_token
    return access_token


# ========================================
# Application Entrypoint
# ========================================


@app.entrypoint
async def agent_invocation(payload: dict):
    """
    エージェント呼び出しのエントリーポイント

    Args:
        payload: リクエストペイロード

    Returns:
        AsyncGenerator: ストリーミングレスポンス
    """
    user_message = payload.get("prompt", "No prompt found in input")
    task = asyncio.create_task(agent_task(user_message))

    async def stream_with_task():
        """タスク実行とストリーミングを並行処理"""
        async for item in queue.stream():
            yield item
        await task

    return stream_with_task()


if __name__ == "__main__":
    app.run()
