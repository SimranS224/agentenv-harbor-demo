import asyncio
import os

from agent_env.task_step.task_step import TaskStep
from .runner import run_matrix


class HarborMatrixStep(TaskStep):
    type = 'harbor_environment_matrix'
    entity_refs = ()

    @classmethod
    def from_dict(cls, data):
        return cls(**cls._base_from_dict(data))

    def to_dict(self):
        return super().to_dict()

    async def execute(self, context):
        profile = self.step_param_overrides(context).get(
            'profile', os.environ.get('HARBOR_DEMO_PROFILE', 'all'))
        mode = self.step_param_overrides(context).get(
            'mode', os.environ.get('HARBOR_DEMO_MODE', 'controls'))
        report, path = await asyncio.to_thread(run_matrix, profile, mode=mode,
                                              instance_id=context.instance_id)
        context.metadata['harbor_environment_demo'] = {'artifacts': path, **report}
        return context
