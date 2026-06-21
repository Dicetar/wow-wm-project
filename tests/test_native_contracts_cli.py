import json

from wm.sources.native_bridge.contracts_cli import main


def test_contract_report_splits_debug_from_forward_declared_product(capsys):
    assert main(["--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["debug_uncontracted"] == [
        "debug_echo",
        "debug_fail",
        "debug_ping",
        "debug_policy_reload",
        "debug_snapshot_player",
    ]
    assert len(report["product_unimplemented"]) == 31
    assert not set(report["debug_uncontracted"]) & set(report["product_unimplemented"])
    assert report["implemented_contract_gap"] == []


def test_text_report_labels_contract_backlog_without_requesting_contracts(capsys):
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "debug/freeform kinds (5; contracts intentionally optional):" in output
    assert "forward-declared product kinds (31; no executor, no contract):" in output
