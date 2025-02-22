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
"""The `ModelStep` definition for SageMaker Pipelines Workflows"""
from __future__ import absolute_import

import logging
from typing import Union, List, Dict, Optional

from sagemaker import Model, PipelineModel
from sagemaker.workflow._utils import _RegisterModelStep, _RepackModelStep
from sagemaker.workflow.pipeline_context import PipelineSession, _ModelStepArguments
from sagemaker.workflow.retry import RetryPolicy
from sagemaker.workflow.step_collections import StepCollection
from sagemaker.workflow.steps import Step, CreateModelStep

NEED_RUNTIME_REPACK = "need_runtime_repack"

_CREATE_MODEL_RETRY_POLICIES = "create_model_retry_policies"
_REGISTER_MODEL_RETRY_POLICIES = "register_model_retry_policies"
_REPACK_MODEL_RETRY_POLICIES = "repack_model_retry_policies"
_REGISTER_MODEL_NAME_BASE = "RegisterModel"
_CREATE_MODEL_NAME_BASE = "CreateModel"
_REPACK_MODEL_NAME_BASE = "RepackModel"


class ModelStep(StepCollection):
    """`ModelStep` for SageMaker Pipelines Workflows."""

    def __init__(
        self,
        name: str,
        step_args: _ModelStepArguments,
        depends_on: Optional[List[Union[str, Step, StepCollection]]] = None,
        retry_policies: Optional[Union[List[RetryPolicy], Dict[str, List[RetryPolicy]]]] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Constructs a `ModelStep`.

        Args:
            name (str): The name of the `ModelStep`. A name is required and must be
                unique within a pipeline.
            step_args (_ModelStepArguments): The arguments for the `ModelStep` definition.
            depends_on (List[Union[str, Step, StepCollection]]): A list of `Step`/`StepCollection`
                names or `Step` instances or `StepCollection` instances that the first step,
                in this `ModelStep` collection, depends on.
                If a listed `Step` name does not exist, an error is returned (default: None).
            retry_policies (List[RetryPolicy] or Dict[str, List[RetryPolicy]]): The list of retry
                policies for the `ModelStep` (default: None).
            display_name (str): The display name of the `ModelStep`.
                The display name provides better UI readability. (default: None).
            description (str): The description of the `ModelStep` (default: None).
        """
        # TODO: add a doc link in error message once ready
        if not isinstance(step_args, _ModelStepArguments):
            raise TypeError(
                "To correctly configure a ModelStep, "
                "the step_args must be a `_ModelStepArguments` object generated by "
                ".create() or .register()."
            )
        if not (step_args.create_model_request is None) ^ (
            step_args.create_model_package_request is None
        ):
            raise ValueError(
                "Invalid step_args: either _register_model_args or _create_model_args"
                " should be provided. They are mutually exclusive. Please use the model's "
                ".create() or .register() method to generate the step_args under PipelineSession."
            )
        if not isinstance(step_args.model.sagemaker_session, PipelineSession):
            raise TypeError(
                "To correctly configure a ModelStep, "
                "the sagemaker_session of the model must be a PipelineSession object."
            )

        self.name = name
        self.step_args = step_args
        self.depends_on = depends_on
        self.retry_policies = retry_policies
        self.display_name = display_name
        self.description = description
        self.steps: List[Step] = []
        self._model = step_args.model
        self._create_model_args = self.step_args.create_model_request
        self._register_model_args = self.step_args.create_model_package_request
        self._need_runtime_repack = self.step_args.need_runtime_repack

        if isinstance(retry_policies, dict):
            self._create_model_retry_policies = retry_policies.get(
                _CREATE_MODEL_RETRY_POLICIES, None
            )
            self._register_model_retry_policies = retry_policies.get(
                _REGISTER_MODEL_RETRY_POLICIES, None
            )
            self._repack_model_retry_policies = retry_policies.get(
                _REPACK_MODEL_RETRY_POLICIES, None
            )
        else:
            self._create_model_retry_policies = retry_policies
            self._register_model_retry_policies = retry_policies
            self._repack_model_retry_policies = retry_policies

        if self._need_runtime_repack:
            self._append_repack_model_step()
        if self._register_model_args:
            self._append_register_model_step()
        else:
            self._append_create_model_step()

    def _append_register_model_step(self):
        """Create and append a `_RegisterModelStep`"""
        register_model_step = _RegisterModelStep(
            name="{}-{}".format(self.name, _REGISTER_MODEL_NAME_BASE),
            step_args=self._register_model_args,
            display_name=self.display_name,
            retry_policies=self._register_model_retry_policies,
            description=self.description,
        )
        if not self._need_runtime_repack:
            register_model_step.add_depends_on(self.depends_on)
        self.steps.append(register_model_step)

    def _append_create_model_step(self):
        """Create and append a `CreateModelStep`"""
        create_model_step = CreateModelStep(
            name="{}-{}".format(self.name, _CREATE_MODEL_NAME_BASE),
            step_args=self._create_model_args,
            retry_policies=self._create_model_retry_policies,
            display_name=self.display_name,
            description=self.description,
        )
        if not self._need_runtime_repack:
            create_model_step.add_depends_on(self.depends_on)
        self.steps.append(create_model_step)

    def _append_repack_model_step(self):
        """Create and append a `_RepackModelStep` for the runtime repack"""
        if isinstance(self._model, PipelineModel):
            model_list = self._model.models
        elif isinstance(self._model, Model):
            model_list = [self._model]
        else:
            logging.warning("No models to repack")
            return

        security_group_ids = None
        subnets = None
        if self._model.vpc_config:
            security_group_ids = self._model.vpc_config.get("SecurityGroupIds", None)
            subnets = self._model.vpc_config.get("Subnets", None)

        for i, model in enumerate(model_list):
            runtime_repack_flg = (
                self._need_runtime_repack and id(model) in self._need_runtime_repack
            )
            if runtime_repack_flg:
                name_base = model.name or i
                repack_model_step = _RepackModelStep(
                    name="{}-{}-{}".format(self.name, _REPACK_MODEL_NAME_BASE, name_base),
                    sagemaker_session=self._model.sagemaker_session or model.sagemaker_session,
                    role=self._model.role or model.role,
                    model_data=model.model_data,
                    entry_point=model.entry_point,
                    source_dir=model.source_dir,
                    dependencies=model.dependencies,
                    subnets=subnets,
                    security_group_ids=security_group_ids,
                    description=(
                        "Used to repack a model with customer scripts for a "
                        "register/create model step"
                    ),
                    depends_on=self.depends_on,
                    retry_policies=self._repack_model_retry_policies,
                )
                self.steps.append(repack_model_step)

                repacked_model_data = repack_model_step.properties.ModelArtifacts.S3ModelArtifacts
                if self._create_model_args:
                    if isinstance(self._model, PipelineModel):
                        container = self.step_args.create_model_request["Containers"][i]
                    else:
                        container = self.step_args.create_model_request["PrimaryContainer"]
                else:
                    container = self.step_args.create_model_package_request[
                        "InferenceSpecification"
                    ]["Containers"][i]
                container["ModelDataUrl"] = repacked_model_data
