"""Test that our detector messages behave correctly with validation checks when decoded from JSON.

Each detector should have a test in here to make sure no messages are ambiguous.

NOTE(ek): If these tests fail too often due to changing enum values or structural changes, then maybe we should generate
the JSON strings dynamically... On the other hand, a change in these test strings would indicate a breaking change in
the API that we might want to monitor
"""
import json

import pydantic
import pytest
from pydantic import parse_obj_as

from mate_common.models.integration import (
    ConcreteHeapOOBOptions,
    Detector,
    DetectorOptions,
    FunctionVariableInfo,
    UninitializedVarOptions,
    UseAfterFreeOptions,
    VariableBoundsAccessOptions,
)


def test_decode_correct_varbounds_detector_options_messages():
    options = """
    {
        "detector": "VariableBoundsAccess",
        "poi_info": ["main"]
    }
    """
    detector = parse_obj_as(DetectorOptions, json.loads(options))
    expected = VariableBoundsAccessOptions(
        detector=Detector.VariableBoundsAccess,
        poi_info=["main"],
    )
    assert detector == expected

    options = """
    {
        "detector": "VariableBoundsAccess"
    }
    """
    detector = parse_obj_as(DetectorOptions, json.loads(options))
    expected = VariableBoundsAccessOptions(detector=Detector.VariableBoundsAccess)
    assert detector == expected


def test_decode_incorrect_varbounds_detector_options_messages():
    options = """
    {
        "detector": "VariableBoundsAccess",
        "poi_info": [{"function_name": "main", "variable_name": "buf"}]
    }
    """
    with pytest.raises(pydantic.ValidationError):
        parse_obj_as(DetectorOptions, json.loads(options))


def test_decode_correct_uninitvar_detector_options_messages():
    options = """
    {
        "detector": "UninitializedVariable",
        "poi_info": [{"function_name": "main", "variable_name": "buf"}]
    }
    """
    detector = parse_obj_as(DetectorOptions, json.loads(options))
    expected = UninitializedVarOptions(
        detector=Detector.UninitializedVar,
        poi_info=[FunctionVariableInfo(function_name="main", variable_name="buf")],
    )
    assert detector == expected

    options = """
    {
        "detector": "UninitializedVariable"
    }
    """
    detector = parse_obj_as(DetectorOptions, json.loads(options))
    expected = UninitializedVarOptions(detector=Detector.UninitializedVar)
    assert detector == expected


def test_decode_incorrect_uninitvar_detector_options_messages():
    options = """
    {
        "detector": "UninitializedVariable",
        "poi_info": ["main"]
    }
    """
    with pytest.raises(pydantic.ValidationError):
        parse_obj_as(DetectorOptions, json.loads(options))


def test_decode_correct_uaf_detector_options_messages():
    options = """
    {
        "detector": "UseAfterFree"
    }
    """
    detector = parse_obj_as(DetectorOptions, json.loads(options))
    expected = UseAfterFreeOptions(detector=Detector.UseAfterFree)
    assert detector == expected


def test_decode_incorrect_uaf_detector_options_messages():
    options = """
    {
        "detector": "UseAfterFree",
        "poi_info": ["main"]
    }
    """
    with pytest.raises(pydantic.ValidationError):
        parse_obj_as(DetectorOptions, json.loads(options))


def test_decode_correct_heap_detector_options_messages():
    options = """
    {
        "detector": "ConcreteHeapOOB",
        "fast":true
    }
    """
    detector = parse_obj_as(DetectorOptions, json.loads(options))
    expected = ConcreteHeapOOBOptions(detector=Detector.ConcreteHeapOOB)
    assert detector == expected


def test_decode_incorrect_heap_detector_options_messages():
    options = """
    {
        "detector": "ConcreteHeapOOB",
        "poi_info": ["main"]
    }
    """
    with pytest.raises(pydantic.ValidationError):
        parse_obj_as(DetectorOptions, json.loads(options))
