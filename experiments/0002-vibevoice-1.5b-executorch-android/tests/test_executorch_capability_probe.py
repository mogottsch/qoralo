import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/executorch-multimethod-external-constants.json"


def load_result():
    return json.loads(RESULT.read_text())


def test_multimethod_probe_records_shared_weight_and_exact_execution():
    result = load_result()
    portable = result["stages"]["portable"]

    assert result["versions"]["executorch"] == "1.2.0"
    assert portable["status"] == "passed"
    assert portable["methods"] == ["steady", "warmup"]
    assert portable["weight_payload_bytes"] == 65_536
    assert portable["size_analysis"]["deduplicated"] is True
    assert portable["size_analysis"]["multimethod_bytes"] < portable["size_analysis"]["sum_individual_bytes"]
    assert all(run["max_abs_error"] == 0.0 for run in portable["executions"].values())
    assert result["conclusions"]["warmup_methods_can_share_inline_constants"] is True


def test_external_constants_are_bounded_to_supported_runtime_api():
    result = load_result()
    conclusions = result["conclusions"]

    assert result["stages"]["external-export"]["artifacts"]["ptd"]["bytes"] > 65_536
    assert result["stages"]["external-multimethod-legacy-run"]["status"] == "passed"
    assert result["stages"]["external-public-run"]["returncode"] == -11
    assert result["stages"]["external-public-run"]["signal"] == "SIGSEGV"
    assert conclusions["multi_method_external_constants_supported_by_private_host_api"] is True
    assert conclusions["external_constants_fit_public_host_runtime_path"] is False
    assert conclusions["external_constants_fit_current_android_java_path"] is False
    assert result["android_packaging_inspection"]["ptd_or_data_loader_parameter_present"] is False
    assert result["scope"] == "synthetic_only_no_vibevoice_no_phone"
