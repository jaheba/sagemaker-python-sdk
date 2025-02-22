# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
# language governing permissions and limitations under the License.
from __future__ import absolute_import

import pytest

from sagemaker.workflow.execution_variables import ExecutionVariables
from sagemaker.workflow.functions import Join, JsonGet
from sagemaker.workflow.parameters import (
    ParameterFloat,
    ParameterInteger,
    ParameterString,
)
from sagemaker.workflow.properties import Properties, PropertyFile


def test_join_primitives_default_on():
    assert Join(values=[1, "a", False, 1.1]).expr == {
        "Std:Join": {
            "On": "",
            "Values": [1, "a", False, 1.1],
        },
    }


def test_join_primitives():
    assert Join(on=",", values=[1, "a", False, 1.1]).expr == {
        "Std:Join": {
            "On": ",",
            "Values": [1, "a", False, 1.1],
        },
    }


def test_join_expressions():
    assert Join(
        values=[
            "foo",
            ParameterFloat(name="MyFloat"),
            ParameterInteger(name="MyInt"),
            ParameterString(name="MyStr"),
            Properties(path="Steps.foo.OutputPath.S3Uri"),
            ExecutionVariables.PIPELINE_EXECUTION_ID,
            Join(on=",", values=[1, "a", False, 1.1]),
        ]
    ).expr == {
        "Std:Join": {
            "On": "",
            "Values": [
                "foo",
                {"Get": "Parameters.MyFloat"},
                {"Get": "Parameters.MyInt"},
                {"Get": "Parameters.MyStr"},
                {"Get": "Steps.foo.OutputPath.S3Uri"},
                {"Get": "Execution.PipelineExecutionId"},
                {"Std:Join": {"On": ",", "Values": [1, "a", False, 1.1]}},
            ],
        },
    }


def test_to_string_on_join():
    func = Join(values=[1, "a", False, 1.1])

    assert func.to_string() == func


def test_implicit_value_on_join():
    func = Join(values=[1, "a", False, 1.1])

    with pytest.raises(TypeError) as error:
        str(func)
    assert "Pipeline variables do not support __str__ operation." in str(error.value)

    with pytest.raises(TypeError) as error:
        int(func)
    assert str(error.value) == "Pipeline variables do not support __int__ operation."

    with pytest.raises(TypeError) as error:
        float(func)
    assert str(error.value) == "Pipeline variables do not support __float__ operation."


def test_string_builtin_funcs_that_return_bool_on_join():
    func = Join(on=",", values=["s3:/", "my-bucket", "a"])
    # The func will only be parsed in runtime (Pipeline backend) so not able to tell in SDK
    assert not func.startswith("s3")
    assert not func.endswith("s3")


def test_add_func_of_join():
    func_join1 = Join(values=[1, "a"])
    param = ParameterInteger(name="MyInteger", default_value=3)

    with pytest.raises(TypeError) as error:
        func_join1 + param

    assert str(error.value) == "Pipeline variables do not support concatenation."


def test_json_get_expressions():
    assert JsonGet(
        step_name="my-step",
        property_file="my-property-file",
        json_path="my-json-path",
    ).expr == {
        "Std:JsonGet": {
            "PropertyFile": {"Get": "Steps.my-step.PropertyFiles.my-property-file"},
            "Path": "my-json-path",
        },
    }

    property_file = PropertyFile(
        name="name",
        output_name="result",
        path="output",
    )
    assert JsonGet(
        step_name="my-step",
        property_file=property_file,
        json_path="my-json-path",
    ).expr == {
        "Std:JsonGet": {
            "PropertyFile": {"Get": "Steps.my-step.PropertyFiles.name"},
            "Path": "my-json-path",
        },
    }


def test_json_get_expressions_with_invalid_step_name():
    with pytest.raises(ValueError) as err:
        JsonGet(
            step_name="",
            property_file="my-property-file",
            json_path="my-json-path",
        ).expr

    assert "Please give a valid step name as a string" in str(err.value)

    with pytest.raises(ValueError) as err:
        JsonGet(
            step_name=ParameterString(name="MyString"),
            property_file="my-property-file",
            json_path="my-json-path",
        ).expr

    assert "Please give a valid step name as a string" in str(err.value)


def test_to_string_on_json_get():
    func = JsonGet(
        step_name="my-step",
        property_file="my-property-file",
        json_path="my-json-path",
    )

    assert func.to_string().expr == {
        "Std:Join": {
            "On": "",
            "Values": [
                {
                    "Std:JsonGet": {
                        "Path": "my-json-path",
                        "PropertyFile": {"Get": "Steps.my-step.PropertyFiles.my-property-file"},
                    }
                }
            ],
        },
    }


def test_implicit_value_on_json_get():
    func = JsonGet(
        step_name="my-step",
        property_file="my-property-file",
        json_path="my-json-path",
    )

    with pytest.raises(TypeError) as error:
        str(func)
    assert "Pipeline variables do not support __str__ operation." in str(error.value)

    with pytest.raises(TypeError) as error:
        int(func)
    assert str(error.value) == "Pipeline variables do not support __int__ operation."

    with pytest.raises(TypeError) as error:
        float(func)
    assert str(error.value) == "Pipeline variables do not support __float__ operation."


def test_string_builtin_funcs_that_return_bool_on_json_get():
    func = JsonGet(
        step_name="my-step",
        property_file="my-property-file",
        json_path="my-json-path",
    )
    # The func will only be parsed in runtime (Pipeline backend) so not able to tell in SDK
    assert not func.startswith("s3")
    assert not func.endswith("s3")


def test_add_func_of_json_get():
    json_get_func1 = JsonGet(
        step_name="my-step",
        property_file="my-property-file",
        json_path="my-json-path",
    )

    property_file = PropertyFile(
        name="name",
        output_name="result",
        path="output",
    )
    json_get_func2 = JsonGet(
        step_name="my-step",
        property_file=property_file,
        json_path="my-json-path",
    )

    with pytest.raises(TypeError) as error:
        json_get_func1 + json_get_func2

    assert str(error.value) == "Pipeline variables do not support concatenation."
