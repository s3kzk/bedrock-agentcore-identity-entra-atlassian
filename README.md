# Amazon Bedrock AgentCore - Identity & OAuth2 統合サンプル

このプロジェクトは、Amazon Bedrock AgentCoreを使用して、認証（Inbound Auth）と認可（Outbound Auth）を統合したAIエージェントの実装サンプルです。Microsoft Entra ID（旧Azure AD）とAtlassian Confluence APIを連携させる実践的な例を提供します。

## 概要

本サンプルでは、以下の認証パターンを実装しています：

- **Inbound Auth（インバウンド認証）**: Microsoft Entra IDのJWTトークンによるユーザー認証
- **Outbound Auth（アウトバウンド認証）**: AtlassianのOAuth2.0を使用した外部サービスへのアクセス

## 主要コンポーネント

### 1. AgentCore Identity
Amazon Cognito基盤のアイデンティティ管理サービスで、以下の機能を提供：
- OAuth2.0アクセストークンの自動管理とリフレッシュ
- セキュアなトークン保管（Token Vault）
- RFC 8707準拠のリソースインジケータサポート

### 2. Strands Agents
軽量で本番環境対応のAIエージェントフレームワーク：
- コードファーストなエージェント構築
- `@tool`デコレータによるツール定義
- 複数のモデルプロバイダーサポート

## プロジェクト構成

```
.
├── agentcore_identity_inout.ipynb  # デモ用Jupyterノートブック
├── strands_with_memory_sample.py   # シンプルなエージェント実装
├── strands_confluence.py           # Confluence連携エージェント
└── requirements.txt                # Python依存関係
```

## 実装されている機能

### エージェント1: Inbound認証デモ
**ファイル**: [`strands_with_memory_sample.py`](strands_with_memory_sample.py)

- Microsoft Entra IDによるJWT認証
- AgentCore Memoryを使用したセッション管理
- Claude 3.7 Sonnetモデルの使用

### エージェント2: Confluence連携
**ファイル**: [`strands_confluence.py`](strands_confluence.py)

実装済みツール：
- `search_confluence_by_text`: テキスト検索でページを検索
- `get_confluence_page`: ページIDから詳細情報を取得
- `create_confluence_page`: 新規ページを作成

認証フロー：
1. ユーザーがEntra IDで認証
2. Confluence操作が必要になると、AtlassianのOAuth2.0フローを開始
3. 認証完了後、`@requires_access_token`デコレータが自動的にトークンを注入

## セットアップ

### 前提条件

- Python 3.13以上推奨
- AWS CLIの設定（認証情報含む）
- Microsoft Entra IDアプリケーション登録
- Atlassian OAuth 2.0アプリケーション登録

### インストール

```bash
pip install -r requirements.txt
```

### 環境変数の設定

ノートブック内で以下の環境変数を設定：

```python
# Microsoft Entra ID
os.environ["entra_client_id"] = "your-client-id"
os.environ["entra_scopes"] = "api://your-app-id/scope"
os.environ["entra_tenant_id"] = "your-tenant-id"
os.environ["entra_audience"] = "api://your-app-id"

# Atlassian OAuth 2.0
os.environ["atlassian_client_id"] = "your-atlassian-client-id"
os.environ["atlassian_secret"] = "your-atlassian-secret"
os.environ["atlassian_scopes"] = "read:page:confluence write:page:confluence ..."
```

## 認証フローの詳細

### インバウンド認証（JWT）
1. ユーザーがEntra IDでデバイスフロー認証を実行
2. 取得したJWTトークンを`bearer_token`として渡す
3. AgentCoreが自動的にトークンを検証

### アウトバウンド認証（OAuth2.0）
1. エージェントがConfluence APIへのアクセスを試行
2. トークンが無い場合、`@requires_access_token`が認証URLを生成
3. ユーザーがブラウザで認証を完了
4. AgentCoreがアクセストークンとリフレッシュトークンを保管
5. 以降のリクエストで自動的にトークンを使用

## 技術スタック

| カテゴリ | 技術 |
|---------|-----|
| AIフレームワーク | Strands Agents 1.x |
| デプロイ基盤 | Amazon Bedrock AgentCore |
| モデル | Claude 3.7 Sonnet (us.anthropic.claude-3-7-sonnet-20250219-v1:0) |
| 認証（Inbound） | Microsoft Entra ID (JWT) |
| 認証（Outbound） | Atlassian OAuth 2.0 |
| API | Confluence REST API v2 |

## リソース

### 公式ドキュメント
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AgentCore Identity - OAuth認証](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-authentication.html)
- [Strands Agents Documentation](https://strandsagents.com/latest/documentation/docs/)
- [Strands + AgentCore デプロイガイド](https://strandsagents.com/latest/documentation/docs/user-guide/deploy/deploy_to_bedrock_agentcore/)

### サンプルコード
- [Amazon Bedrock AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)

