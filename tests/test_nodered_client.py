from unittest.mock import MagicMock, call, patch

import pytest

from nodered_dmp.nodered.client import (
    DeployPreview,
    FlowNotFoundError,
    deploy_flow,
    get_flow_nodes,
    preview_deploy,
)

SERVER = "http://localhost:1880"

# --- shared fixtures ---

BROKER = {"id": "broker1", "type": "mqtt-broker", "name": "local"}
TAB_A  = {"id": "tab_a", "type": "tab", "label": "FlowA"}
TAB_B  = {"id": "tab_b", "type": "tab", "label": "FlowB"}
NODE_A1 = {"id": "n1", "type": "mqtt in",  "z": "tab_a", "topic": "/v"}
NODE_A2 = {"id": "n2", "type": "function", "z": "tab_a", "func": "return msg;"}
NODE_B1 = {"id": "n3", "type": "mqtt in",  "z": "tab_b", "topic": "/s"}

ALL_NODES = [TAB_A, TAB_B, NODE_A1, NODE_A2, NODE_B1, BROKER]


def _mock_get(nodes: list[dict]) -> MagicMock:
    m = MagicMock()
    m.json.return_value = nodes
    return m


# === get_flow_nodes ===

def test_get_flow_nodes_returns_tab_node():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        result = get_flow_nodes(SERVER, "FlowA")
    assert TAB_A in result


def test_get_flow_nodes_returns_tab_members():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        result = get_flow_nodes(SERVER, "FlowA")
    ids = {n["id"] for n in result}
    assert "n1" in ids
    assert "n2" in ids


def test_get_flow_nodes_excludes_other_tab_nodes():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        result = get_flow_nodes(SERVER, "FlowA")
    ids = {n["id"] for n in result}
    assert "n3" not in ids
    assert "tab_b" not in ids


def test_get_flow_nodes_includes_config_nodes():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        result = get_flow_nodes(SERVER, "FlowA")
    assert BROKER in result


def test_get_flow_nodes_raises_if_not_found():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        with pytest.raises(FlowNotFoundError):
            get_flow_nodes(SERVER, "NonExistent")


def test_get_flow_nodes_sends_auth_header():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)) as mock_get:
        get_flow_nodes(SERVER, "FlowA", token="mytoken")
    headers = mock_get.call_args.kwargs["headers"]
    assert headers.get("Authorization") == "Bearer mytoken"


def test_get_flow_nodes_no_auth_header_without_token():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)) as mock_get:
        get_flow_nodes(SERVER, "FlowA")
    headers = mock_get.call_args.kwargs["headers"]
    assert "Authorization" not in headers


# === deploy_flow ===

NEW_TAB   = {"id": "new_tab", "type": "tab", "label": "FlowA"}
NEW_NODE  = {"id": "new_n1", "type": "mqtt in", "z": "new_tab", "topic": "/v"}
NEW_FLOW  = [NEW_TAB, NEW_NODE]


def _mock_deploy():
    get_resp = _mock_get(ALL_NODES)
    put_resp = MagicMock()
    return get_resp, put_resp


def test_deploy_flow_replaces_existing_tab():
    get_resp, put_resp = _mock_deploy()
    with patch("nodered_dmp.nodered.client.requests.get", return_value=get_resp), \
         patch("nodered_dmp.nodered.client.requests.post", return_value=put_resp) as mock_post:
        deploy_flow(SERVER, NEW_FLOW, "FlowA")

    sent = mock_post.call_args.kwargs["json"]
    sent_ids = {n["id"] for n in sent}
    # old FlowA nodes gone
    assert "tab_a" not in sent_ids
    assert "n1" not in sent_ids
    assert "n2" not in sent_ids
    # new FlowA nodes present
    assert "new_tab" in sent_ids
    assert "new_n1" in sent_ids


def test_deploy_flow_preserves_other_tab():
    get_resp, put_resp = _mock_deploy()
    with patch("nodered_dmp.nodered.client.requests.get", return_value=get_resp), \
         patch("nodered_dmp.nodered.client.requests.post", return_value=put_resp) as mock_post:
        deploy_flow(SERVER, NEW_FLOW, "FlowA")

    sent = mock_post.call_args.kwargs["json"]
    sent_ids = {n["id"] for n in sent}
    assert "tab_b" in sent_ids
    assert "n3" in sent_ids


def test_deploy_flow_adds_new_tab_if_not_found():
    # Server has only FlowB; deploying FlowA adds it
    existing = [TAB_B, NODE_B1, BROKER]
    get_resp = _mock_get(existing)
    put_resp = MagicMock()
    with patch("nodered_dmp.nodered.client.requests.get", return_value=get_resp), \
         patch("nodered_dmp.nodered.client.requests.post", return_value=put_resp) as mock_post:
        deploy_flow(SERVER, NEW_FLOW, "FlowA")

    sent = mock_post.call_args.kwargs["json"]
    sent_ids = {n["id"] for n in sent}
    assert "tab_b" in sent_ids
    assert "new_tab" in sent_ids
    assert "new_n1" in sent_ids


def test_deploy_flow_sends_deployment_type_header():
    get_resp, put_resp = _mock_deploy()
    with patch("nodered_dmp.nodered.client.requests.get", return_value=get_resp), \
         patch("nodered_dmp.nodered.client.requests.post", return_value=put_resp) as mock_post:
        deploy_flow(SERVER, NEW_FLOW, "FlowA")

    headers = mock_post.call_args.kwargs["headers"]
    assert headers.get("Node-RED-Deployment-Type") == "full"


def test_deploy_flow_sends_auth_header():
    get_resp, put_resp = _mock_deploy()
    with patch("nodered_dmp.nodered.client.requests.get", return_value=get_resp), \
         patch("nodered_dmp.nodered.client.requests.post", return_value=put_resp) as mock_post:
        deploy_flow(SERVER, NEW_FLOW, "FlowA", token="secret")

    headers = mock_post.call_args.kwargs["headers"]
    assert headers.get("Authorization") == "Bearer secret"


# === preview_deploy ===

def test_preview_deploy_replace_action():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        preview = preview_deploy(SERVER, NEW_FLOW, "FlowA")
    assert preview.action == "replace"


def test_preview_deploy_add_action():
    existing = [TAB_B, NODE_B1, BROKER]
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(existing)):
        preview = preview_deploy(SERVER, NEW_FLOW, "FlowA")
    assert preview.action == "add"


def test_preview_deploy_replace_counts():
    # ALL_NODES: TAB_A + TAB_B + NODE_A1 + NODE_A2 + NODE_B1 + BROKER
    # FlowA has tab_a + n1 + n2 → 3 removed; NEW_FLOW has 2 new nodes
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        preview = preview_deploy(SERVER, NEW_FLOW, "FlowA")
    assert preview.removed_node_count == 3   # TAB_A + NODE_A1 + NODE_A2
    assert preview.new_node_count == len(NEW_FLOW)


def test_preview_deploy_other_tab_count():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)):
        preview = preview_deploy(SERVER, NEW_FLOW, "FlowA")
    assert preview.other_tab_count == 1      # TAB_B survives
    assert preview.other_node_count == 2     # NODE_B1 + BROKER survive


def test_preview_deploy_add_zero_removed():
    existing = [TAB_B, NODE_B1]
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(existing)):
        preview = preview_deploy(SERVER, NEW_FLOW, "FlowA")
    assert preview.removed_node_count == 0


def test_preview_deploy_does_not_post():
    with patch("nodered_dmp.nodered.client.requests.get", return_value=_mock_get(ALL_NODES)), \
         patch("nodered_dmp.nodered.client.requests.post") as mock_post:
        preview_deploy(SERVER, NEW_FLOW, "FlowA")
    mock_post.assert_not_called()
